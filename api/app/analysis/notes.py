"""Reads the printed 10-K: the notes to the financial statements and the auditor's report.

The figures alone cannot show a going-concern warning, a covenant breach, an auditor's qualification or a
customer that is half of revenue. Those sit in the text. This reads the stored copy of the filing (hash-checked
by the caller) and reports, topic by topic, what the filing itself says, **quoting the filing's own
sentences**. Nothing is paraphrased into a finding the text does not contain (P-01, P-02).

How it decides, so a person can judge it:

- A topic is a CONCERN only when a sentence states the adverse fact in the past or present tense. Sentences
  that are hypothetical ("could", "may", "if") are risk-factor boilerplate and never raise a concern.
- A topic is NO_CONCERN when the filing states the reassuring fact (for example "in compliance with all
  covenants") or when the filing never uses the warning words at all (said so, with the words searched).
- Anything else is INFO (quoted, for a person to read) or NOT_FOUND (the filing does not discuss it).

It is a reader, not a judge: it never changes the amount or the outcome, and a person reads the quotes."""

import hashlib
import html
import re
from dataclasses import dataclass, field
from typing import Literal

from app.recommendation.analysis_report import NoteFinding, NoteQuote, NotesReview

State = Literal["CONCERN", "NO_CONCERN", "INFO", "NOT_FOUND"]

_HIDDEN = re.compile(r"<ix:header>.*?</ix:header>", re.S | re.I)
_DROP = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
_BLOCK = re.compile(r"</?(p|div|tr|br|li|h[1-6]|table|section|title)\b[^>]*>", re.I)
_CELL = re.compile(r"</?(td|th)\b[^>]*>", re.I)
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"[ \t\r\f\v  ​]+")
_SENTENCE_END = re.compile(r"(?<=[.!?])[\"”’)]?\s+(?=[A-Z“\"(])")
_MODAL = re.compile(
    r"\b(could|may|might|would|should|if|whether|potential(ly)?|possible|any of)\b", re.I
)
_NEGATED = re.compile(
    r"\b(no|not|never|without|absence of|did not|does not|do not|none|neither|nor)\b", re.I
)


def text_of(body: bytes) -> str:
    """Plain text of an HTML filing. Hidden XBRL headers and scripts are dropped; cells keep a gap."""
    raw = body.decode("utf-8", errors="replace")
    raw = _HIDDEN.sub(" ", raw)
    raw = _DROP.sub(" ", raw)
    raw = _BLOCK.sub("\n", raw)
    raw = _CELL.sub(" | ", raw)
    raw = _TAG.sub(" ", raw)
    raw = html.unescape(raw)
    lines = [_SPACE.sub(" ", line).strip() for line in raw.split("\n")]
    return "\n".join(line for line in lines if line)


def sentences(text: str) -> list[str]:
    out: list[str] = []
    for line in text.split("\n"):
        for part in _SENTENCE_END.split(line):
            part = part.strip(" |")
            if 25 <= len(part) <= 1500:
                out.append(part)
    return out


def _clip(sentence: str, limit: int = 500) -> str:
    return sentence if len(sentence) <= limit else sentence[: limit - 1].rstrip() + "…"


def _quotes(found: list[str], where: str | None = None, limit: int = 2) -> list[NoteQuote]:
    unique = list(dict.fromkeys(found))[:limit]
    return [NoteQuote(text=_clip(s), where=where) for s in unique]


def _section(text: str, heading: str, size: int = 1500, last: bool = True) -> str | None:
    """The text after a heading. The last match is used, because the first is usually the contents page."""
    hits = [m.end() for m in re.finditer(heading, text, re.I)]
    if not hits:
        return None
    start = hits[-1] if last else hits[0]
    return text[start : start + size]


@dataclass
class _Topic:
    key: str
    title: str
    state: State
    summary: str
    quotes: list[NoteQuote] = field(default_factory=list)

    def build(self) -> NoteFinding:
        return NoteFinding(
            topic=self.key,
            title=self.title,
            state=self.state,
            summary=self.summary[:600],
            quotes=self.quotes[:3],
        )


def _going_concern(sents: list[str]) -> _Topic:
    title = "Going concern"
    related = [s for s in sents if re.search(r"going concern|substantial doubt", s, re.I)]
    adverse = [
        s
        for s in related
        if re.search(
            r"(raise|raises|raised|exist|exists|existed)\b[^.]{0,60}substantial doubt", s, re.I
        )
        and not _NEGATED.search(s)
        and not _MODAL.search(s)
    ]
    if adverse:
        return _Topic(
            "GOING_CONCERN", title, "CONCERN",
            "The filing states a doubt about the company's ability to continue as a going concern.",
            _quotes(adverse),
        )  # fmt: skip
    if related:
        reassuring = [s for s in related if _NEGATED.search(s)] or related
        return _Topic(
            "GOING_CONCERN", title, "NO_CONCERN",
            "The filing mentions going concern, but does not state a doubt about it.",
            _quotes(reassuring),
        )  # fmt: skip
    return _Topic(
        "GOING_CONCERN", title, "NO_CONCERN",
        "Searched the whole filing for 'going concern' and 'substantial doubt': neither appears, so no "
        "going-concern warning was found.",
    )  # fmt: skip


_OPINION_ADVERSE = re.compile(
    r"adverse opinion|disclaimer of opinion|do not express an opinion|did not express an opinion|"
    r"qualified opinion|except for the effects|except for the matter|basis for (qualified|adverse)",
    re.I,
)


def _auditor_opinion(text: str, sents: list[str]) -> _Topic:
    title = "Auditor's opinion"
    region_start = [
        m.start()
        for m in re.finditer(r"Report of Independent Registered Public Accounting Firm", text, re.I)
    ]
    region = " ".join(text[s : s + 9000] for s in region_start)
    firm = re.findall(
        r"/s/\s*([A-Z][A-Za-z&.,' ]{3,60}?(?:LLP|LLC|Ltd\.?|Limited|AG|GmbH))", region
    )
    firm_text = f" Signed by {firm[0].strip()}." if firm else ""
    adverse = [s for s in sentences(region) if _OPINION_ADVERSE.search(s) and not _MODAL.search(s)]
    if adverse:
        return _Topic(
            "AUDITOR_OPINION", title, "CONCERN",
            "The auditor's report contains qualifying or adverse wording." + firm_text,
            _quotes(adverse, "Auditor's report"),
        )  # fmt: skip
    clean = [s for s in sents if re.search(r"present fairly, in all material respects", s, re.I)]
    if clean:
        return _Topic(
            "AUDITOR_OPINION", title, "NO_CONCERN",
            "The auditor gives a clean (unqualified) opinion: the statements present fairly, in all material "
            "respects." + firm_text,
            _quotes(clean[:1], "Auditor's report"),
        )  # fmt: skip
    return _Topic(
        "AUDITOR_OPINION", title, "NOT_FOUND",
        "The auditor's report was not found in the text, so the opinion could not be read.",
    )  # fmt: skip


def _auditor_change(text: str) -> _Topic:
    title = "Change of auditor or disagreements"
    segment = _section(text, r"Changes in and Disagreements with Accountants[^\n]*\n?", 400)
    if segment is None:
        return _Topic("AUDITOR_CHANGE", title, "NOT_FOUND", "Item 9 was not found in the text.")
    first = segment.strip().split("\n")[0]
    if re.match(r"^\W*(none|not applicable)\b", first, re.I):
        return _Topic(
            "AUDITOR_CHANGE", title, "NO_CONCERN",
            "Item 9 (changes in and disagreements with accountants) says there were none.",
            [NoteQuote(text=_clip(first, 200), where="Item 9")],
        )  # fmt: skip
    if re.search(r"dismiss|resign|engaged|disagree", first, re.I) and not _NEGATED.search(first):
        return _Topic(
            "AUDITOR_CHANGE", title, "CONCERN",
            "Item 9 describes a change of auditor or a disagreement.",
            [NoteQuote(text=_clip(first), where="Item 9")],
        )  # fmt: skip
    return _Topic(
        "AUDITOR_CHANGE", title, "INFO",
        "Item 9 was found but its wording needs a person to read it.",
        [NoteQuote(text=_clip(first), where="Item 9")],
    )  # fmt: skip


_COV_ADVERSE = re.compile(
    r"not in compliance|non-?compliance|in breach|breached|violated|violation|waiver|waived|event of default|"
    r"was in default|were in default|has defaulted",
    re.I,
)


def _covenants(sents: list[str]) -> _Topic:
    title = "Loan covenants"
    cov = [s for s in sents if re.search(r"covenant", s, re.I)]
    adverse = [
        s
        for s in cov
        if _COV_ADVERSE.search(s)
        and not _MODAL.search(s)
        and not re.search(r"\bno (event|breach|default)", s, re.I)
    ]
    if adverse:
        return _Topic(
            "COVENANTS", title, "CONCERN",
            "The filing states a covenant breach, waiver or default.",
            _quotes(adverse),
        )  # fmt: skip
    positive = [
        s
        for s in cov
        if re.search(r"in compliance|complied|compliance with (all|each|the)", s, re.I)
        and not _MODAL.search(s)
        and not re.search(r"not in compliance|non-?compliance", s, re.I)
    ]
    if positive:
        return _Topic(
            "COVENANTS", title, "NO_CONCERN",
            "The filing states that the company complied with its covenants.",
            _quotes(positive),
        )  # fmt: skip
    if cov:
        return _Topic(
            "COVENANTS", title, "INFO",
            "Covenants are mentioned, but the filing gives no statement of compliance or breach.",
            _quotes(cov),
        )  # fmt: skip
    return _Topic(
        "COVENANTS", title, "NOT_FOUND",
        "The filing does not discuss loan covenants.",
    )  # fmt: skip


_CUSTOMER = re.compile(r"customer", re.I)
_PCT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s?(?:%|percent)")


def _customers(sents: list[str]) -> tuple[_Topic, float | None, bool]:
    """The topic, the largest customer share the text states (percent), and whether it says none is 10%+."""
    title = "Customer concentration"
    cust = [
        s
        for s in sents
        if _CUSTOMER.search(s)
        and re.search(r"accounted for|represent|concentration|10%|10 percent", s, re.I)
    ]
    none = [
        s
        for s in cust
        if re.search(
            r"\bno\b[^.]{0,60}customer[^.]{0,80}(10%|10 percent|ten percent|more than)", s, re.I
        )
        or re.search(
            r"\bno (single |individual |one )?customer\b[^.]{0,60}(accounted|represent)", s, re.I
        )
    ]
    shares: list[tuple[float, str]] = []
    for s in cust:
        if s in none or _MODAL.search(s):
            continue
        for m in _PCT.finditer(s):
            value = float(m.group(1))
            if 10 <= value <= 100 and re.search(r"revenue|sales|receivable", s, re.I):
                shares.append((value, s))
    if shares:
        top = max(shares, key=lambda x: x[0])
        state: State = "CONCERN" if top[0] >= 50 else "INFO"
        return (
            _Topic(
                "CUSTOMER_CONCENTRATION", title, state,
                f"The filing states a customer share of up to {top[0]:g}%.",
                _quotes([s for _, s in shares]),
            ),
            top[0],
            False,
        )  # fmt: skip
    if none:
        return (
            _Topic(
                "CUSTOMER_CONCENTRATION", title, "NO_CONCERN",
                "The filing says no single customer reaches 10% of revenue.",
                _quotes(none, limit=1),
            ),
            None,
            True,
        )  # fmt: skip
    return (
        _Topic(
            "CUSTOMER_CONCENTRATION", title, "NOT_FOUND",
            "The filing does not state a customer concentration.",
        ),
        None,
        False,
    )  # fmt: skip


def _facilities(sents: list[str]) -> _Topic:
    title = "Committed credit facilities and borrowing"
    found = [
        s
        for s in sents
        if re.search(
            r"(revolving )?credit (facility|agreement)|commercial paper|committed (credit|facilit)",
            s,
            re.I,
        )
        and re.search(r"\$\s?\d|billion|million", s, re.I)
        and re.search(r"no (amounts|borrowings)|undrawn|outstanding|available|matur", s, re.I)
        and not _MODAL.search(s)
    ]
    if found:
        return _Topic(
            "CREDIT_FACILITIES", title, "INFO",
            "Facilities and borrowings the filing describes (these are not in the figures).",
            _quotes(found),
        )  # fmt: skip
    return _Topic("CREDIT_FACILITIES", title, "NOT_FOUND", "No committed facility was described.")


def _internal_control(sents: list[str]) -> _Topic:
    title = "Internal control over financial reporting"
    weak = [s for s in sents if re.search(r"material weakness", s, re.I)]
    adverse = [
        s
        for s in weak
        if re.search(
            r"(identified|existence of|had|have|there (is|was|were)|resulted in)\b[^.]{0,40}material weakness",
            s,
            re.I,
        )
        and not _NEGATED.search(s)
        and not _MODAL.search(s)
    ]
    if adverse:
        return _Topic(
            "INTERNAL_CONTROL", title, "CONCERN",
            "The filing reports a material weakness in internal control.", _quotes(adverse)
        )  # fmt: skip
    effective = [
        s
        for s in sents
        if re.search(
            r"maintained,? in all material respects,? effective internal control|internal control over financial reporting (was|is) effective|did not identify any material weakness",
            s,
            re.I,
        )
    ]
    if effective:
        return _Topic(
            "INTERNAL_CONTROL", title, "NO_CONCERN",
            "Internal control over financial reporting is reported as effective.", _quotes(effective, limit=1)
        )  # fmt: skip
    return _Topic(
        "INTERNAL_CONTROL", title, "NOT_FOUND", "No statement on internal control was found."
    )


def _legal(text: str) -> _Topic:
    title = "Legal proceedings and contingencies"
    segment = _section(text, r"Item 3\.?\s*Legal Proceedings[^\n]*\n?", 900)
    if segment is None:
        return _Topic(
            "LEGAL", title, "NOT_FOUND", "Item 3 (legal proceedings) was not found in the text."
        )
    got = sentences(segment)[:2]
    if not got:
        return _Topic(
            "LEGAL", title, "NOT_FOUND", "Item 3 was found but gave no readable statement."
        )
    return _Topic(
        "LEGAL", title, "INFO",
        "What the filing says about legal proceedings (read it; this is not scored).",
        _quotes(got, "Item 3", limit=2),
    )  # fmt: skip


def _allowance(sents: list[str]) -> _Topic:
    title = "Allowance for credit losses on receivables"
    found = [
        s
        for s in sents
        if re.search(r"allowance for (credit losses|doubtful accounts)", s, re.I)
        and re.search(r"\$\s?\d", s)
        and not _MODAL.search(s)
    ]
    if found:
        return _Topic(
            "ALLOWANCE", title, "INFO",
            "The filing states the allowance for credit losses.", _quotes(found, limit=1)
        )  # fmt: skip
    return _Topic(
        "ALLOWANCE", title, "NOT_FOUND", "No allowance for credit losses was stated in the text."
    )


def _subsequent(text: str) -> _Topic:
    title = "Events after the balance sheet date"
    segment = _section(text, r"Subsequent Events?[^\n]*\n?", 700)
    got = sentences(segment)[:2] if segment else []
    if got:
        return _Topic(
            "SUBSEQUENT_EVENTS", title, "INFO",
            "What the filing says about later events (read it; this is not scored).",
            _quotes(got, "Subsequent events"),
        )  # fmt: skip
    return _Topic("SUBSEQUENT_EVENTS", title, "NOT_FOUND", "No subsequent-events note was found.")


@dataclass
class Scan:
    review: NotesReview
    largest_customer_pct: float | None
    no_customer_over_10: bool


def scan(body: bytes, *, label: str, url: str | None, filed: str | None) -> Scan:
    """Read the filing text and report, topic by topic, what it says."""
    text = text_of(body)
    sents = sentences(text)
    customers, largest, none_over_10 = _customers(sents)
    topics = [
        _going_concern(sents),
        _auditor_opinion(text, sents),
        _auditor_change(text),
        _covenants(sents),
        customers,
        _facilities(sents),
        _internal_control(sents),
        _legal(text),
        _allowance(sents),
        _subsequent(text),
    ]
    findings = [t.build() for t in topics]
    concerns = [f.title for f in findings if f.state == "CONCERN"]
    summary = (
        "Concerns stated in the filing: " + "; ".join(concerns).lower() + ". Read the quotes."
        if concerns
        else "No going-concern warning, covenant breach, auditor qualification or material weakness was "
        "stated in the filing text that was read."
    )
    if len(text) < 20_000:
        summary = (
            "The filing text is short or unreadable, so this review may be incomplete. " + summary
        )
    review = NotesReview(
        source=label[:300],
        url=url,
        filed=filed,
        sha256=hashlib.sha256(body).hexdigest(),
        characters=len(text),
        summary=summary[:600],
        findings=findings,
    )
    return Scan(review, largest, none_over_10)
