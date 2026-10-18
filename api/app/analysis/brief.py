"""The executive summary for the person who decides: one page that pulls every part of the analysis together.

It is written for a chief executive who has to make the call. It leads with the recommendation and the amount,
then the reasons with the numbers that matter (profit, liquidity, debt, cash flow, the cash cycle), what the
rating agencies say, what the screening found (sanctions, entity register, news), what the filing's notes and
auditor say, how it behaves if sales fall, what is not known, and the points the decision-maker should settle.

Every sentence is built from the analysis itself, so it can never say something the evidence does not. It is a
recommendation only: the underwriter's recorded decision is the decision (P-09)."""

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from app.analysis.formats import money, pct, times
from app.ratings.scale import AGENCY_NAMES
from app.recommendation.analysis_report import AnalysisReport, BriefSection, ExecutiveBrief

DIMENSION_WORDS = {
    "OK": "OK",
    "WEAK": "weak",
    "DISTRESSED": "distressed",
    "NOT_ASSESSED": "not assessed",
}


@dataclass
class Recommendation:
    """What the server's policy will recommend, worked out before the draft is stored."""

    outcome: str  # APPROVE | DECLINE
    band: str  # FULL | REDUCED | DECLINE
    amount: float | None  # in currency units
    requested: float
    proposed: float
    currency: str
    factors: list[tuple[str, str, float]]  # code, explanation, share cut
    rules: list[str]


def _chg(x: float | None) -> str:
    """A change as a person says it: up 0.2%, down 22.4%."""
    if x is None:
        return "not calculable"
    return f"{'up' if x >= 0 else 'down'} {abs(x) * 100:.1f}%"


def _join(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def _m(x: float | None, currency: str) -> str:
    """Currency units to the report's millions-based wording."""
    return money(None if x is None else x / 1e6, currency)


def _recommendation(rec: Recommendation, name: str) -> str:
    cur = rec.currency
    if rec.outcome == "DECLINE":
        why = "; ".join(r.replace("_", " ") for r in rec.rules) if rec.rules else "the policy rules"
        return (
            f"Decline. The UW Analyzer recommends no credit for {name} against the {_m(rec.requested, cur)} "
            f"requested (policy rule: {why})."
        )
    share = (rec.amount or 0) / rec.requested * 100 if rec.requested else 0
    head = (
        f"Approve the full {_m(rec.amount, cur)} requested."
        if rec.band == "FULL"
        else f"Approve a reduced {_m(rec.amount, cur)}, {share:.0f}% of the {_m(rec.requested, cur)} requested."
    )
    cuts = [f"{explain.rstrip('.')} (-{cut * 100:.0f}%)" for _, explain, cut in rec.factors]
    if rec.band == "REDUCED" and cuts:
        head += " The reduction comes from: " + "; ".join(cuts) + "."
    return head


def _financial(nums: dict[str, Any], cur: str) -> str:
    n = nums
    parts = [
        f"Revenue {money(n['revenue'], cur)}"
        + (f" ({_chg(n['growth'])} on the year before)" if n.get("growth") is not None else "")
        + f"; net income {money(n['net_income'], cur)}, a net margin of {pct(n['net_margin'])}"
        + (f" (was {pct(n['prior_net_margin'])})" if n.get("prior_net_margin") is not None else "")
        + f"; EBITDA margin {pct(n['ebitda_margin'])}.",
        f"Cash from operations {money(n['ocf'], cur)}, {times(n['ocf_to_ni'])} net income"
        + (
            f", {_chg(n['ocf_change'])} on the year before"
            if n.get("ocf_change") is not None
            else ""
        )
        + f"; free cash flow {money(n['fcf'], cur)}, {money(n['fcf_after'], cur)} after dividends and buybacks.",
        f"Current ratio {times(n['current_ratio'])}"
        + (
            f" (was {times(n['prior_current_ratio'])})"
            if n.get("prior_current_ratio") is not None
            else ""
        )
        + f", cash less debt due within 12 months {money(n['buffer'], cur)}.",
        f"Debt to equity {times(n['de'])}, net debt {times(n['nd'])} EBITDA, interest cover {times(n['cover'])}, "
        f"equity {money(n['equity'], cur)} ({pct(n['equity_ratio'])} of assets).",
    ]
    return " ".join(parts)


def _clip(text: str, limit: int) -> str:
    """Cut at a sentence end where possible, never mid-word. The recorder's own source notes ("Reported by
    ..."), which repeat what the summary already says about the source, are left out."""
    text = " ".join(text.split())
    kept = [
        s
        for s in re.split(r"(?<=[.!?]) ", text)
        if not re.match(r"(Reported by|Source:|Per |This supersedes)", s)
    ]
    text = " ".join(kept) or text
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("; "))
    return (cut[: end + 1] if end > limit // 2 else cut.rsplit(" ", 1)[0] + "…").rstrip()


def _ratings(report: AnalysisReport) -> str:
    """Each agency's grade, outlook and, in its own reported words, why. A rating taken from the press still
    carries the agency's stated reasons: they are the substance a decision-maker needs, with their source named."""
    if not report.published_ratings:
        return "No published agency rating is recorded for this company, so there is no external view to weigh."
    bits = []
    for r in report.published_ratings:
        action = (
            r.last_action_on.strftime("%d %b %Y").lstrip("0")
            if r.last_action_on
            else "date not recorded"
        )
        extra = []
        if r.change == "DOWNGRADE":
            extra.append("downgraded")
        elif r.change == "UPGRADE":
            extra.append("upgraded")
        extra.append(f"{r.outlook.lower()} outlook")
        if r.under_review:
            extra.append("under review")
        host = (urlsplit(r.source_url).hostname or "its source").removeprefix("www.")
        where = (
            "the agency's own site"
            if r.source_kind == "AGENCY_SITE"
            else f"{host}, a secondary source"
        )
        reason = _clip(r.rationale, 330) if r.rationale else None
        line = f"{AGENCY_NAMES[r.agency]} {r.grade} ({', '.join(extra)}, last action {action})."
        line += (
            f" Its stated reason, as reported by {where}: {reason}"
            if reason
            else f" No reason was recorded (source: {where})."
        )
        bits.append(line)
    text = " ".join(bits)
    if report.ratings_reconciliation:
        # The comparison with the financial picture, without its trailing note on source quality.
        sentences = re.split(r"(?<=[.!?]) ", report.ratings_reconciliation)
        compare = " ".join(
            s for s in sentences if " came from" not in s and not s.startswith("Confirm ")
        ).strip()
        if compare:
            text += " Against the financials: " + compare.rstrip(".") + "."
    if any(r.source_kind != "AGENCY_SITE" for r in report.published_ratings):
        text += " Confirm the ratings and the reasons on the agencies' own sites."
    text += " The agencies' views are shown for information and do not change the amount."
    return text


def _screening(report: AnalysisReport) -> str:
    wanted = (
        "Sanctions list (OFAC SDN)",
        "Entity register (Global LEI)",
        "Adverse-information search",
        "Court records and other regulators",
        "Country economy (World Bank)",
    )
    by = {c.title: c for c in report.other_checks}
    out = []
    for title in wanted:
        c = by.get(title)
        if c is None:
            continue
        label = {
            "Sanctions list (OFAC SDN)": "OFAC sanctions list",
            "Entity register (Global LEI)": "Entity register",
            "Adverse-information search": "News and adverse information",
            "Court records and other regulators": "Courts and other regulators",
            "Country economy (World Bank)": "Country economy",
        }[title]
        out.append(f"{label}: {c.detail.replace(' gdp ', ' GDP ').rstrip('.')}.")
    return " ".join(out) if out else "No screening results were recorded."


def _filing(report: AnalysisReport) -> str:
    notes = report.notes_review
    if notes is None:
        return "The printed annual report (notes and auditor's report) was not read in this run, so going concern, covenants and the auditor's opinion are unconfirmed."
    by = {f.topic: f for f in notes.findings}
    concerns = [f for f in notes.findings if f.state == "CONCERN"]
    if concerns:
        return (
            "The filing states: "
            + " ".join(f"{f.title}: {f.summary}" for f in concerns)
            + " Read the quotes in Step 1."
        )
    bits = []
    for topic in (
        "AUDITOR_OPINION",
        "GOING_CONCERN",
        "COVENANTS",
        "CREDIT_FACILITIES",
        "CUSTOMER_CONCENTRATION",
        "INTERNAL_CONTROL",
    ):
        f = by.get(topic)
        if f is None or f.state == "NOT_FOUND":
            continue
        if topic in ("CREDIT_FACILITIES", "CUSTOMER_CONCENTRATION") and f.quotes:
            bits.append(
                f"“{f.quotes[0].text.rstrip('.')}”"
            )  # the filing's own words carry the numbers
        else:
            bits.append(f.summary.rstrip("."))
    return ("From the filing's own text: " + "; ".join(bits) + ".") if bits else notes.summary


def _stress(report: AnalysisReport) -> str | None:
    rows = [r for r in report.stress if "cost of sales falls" in r.scenario]
    if not rows:
        return None
    first = rows[0]
    text = (
        f"If revenue fell 10% with cost of sales falling in line, operating profit would be {first.earnings} and "
        f"cash from operations {first.cash_from_operations}"
    )
    if len(rows) > 1:
        text += f"; at 20% operating profit would be {rows[1].earnings}"
    text += "."
    m = re.search(r"reaches zero if revenue falls about ([\d.]+)%", report.stress_note or "")
    if m:
        text += f" Operating profit reaches zero if revenue falls about {m.group(1)}%."
    return text


def _unknown(report: AnalysisReport) -> str | None:
    gaps = [g.rstrip(".") for g in report.gaps]
    if not gaps:
        return None
    shown = gaps[:4]
    more = f", and {len(gaps) - 4} more" if len(gaps) > 4 else ""
    return "; ".join(shown) + more + "."


def _points(report: AnalysisReport) -> list[str]:
    """What the person deciding should settle first: the most important points lead."""
    points: list[str] = []
    for note in report.notes_review.findings if report.notes_review else []:
        if note.state == "CONCERN":
            points.append(f"In the filing, {note.title.lower()}: {note.summary}")
    if report.published_ratings and any(
        r.source_kind != "AGENCY_SITE" for r in report.published_ratings
    ):
        points.append("Confirm the agency ratings on the agencies' own websites.")
    cc = report.cash_cycle
    ccc = next((r for r in cc.rows if r.key == "ccc"), None) if cc is not None else None
    if ccc is not None and ccc.direction == "worse":
        points.append(
            f"The cash conversion cycle lengthened: {ccc.movement.lower()}. Ask what is behind it "
            "(collections, stock, supplier terms)."
        )
    for f in report.red_flags:
        if f.state == "TRIGGERED":
            points.append(f"{f.text}: {f.detail}")
    if (
        cc is not None
        and cc.status in ("WEAK", "DISTRESSED")
        and cc.standing
        and "What to do: " in cc.standing
    ):
        first = cc.standing.split("What to do: ", 1)[1].split(". ")[0]
        points.insert(2 if len(points) > 2 else len(points), f"Cash conversion cycle: {first}.")
    return [p[:600] for p in points][:8]


def _headline(report: AnalysisReport, rec: Recommendation, name: str) -> str:
    core = [a for a in report.areas if a.feeds_draft]
    good = [a.title.lower() for a in core if a.status == "OK"]
    bad = [a.title.lower() for a in core if a.status in ("WEAK", "DISTRESSED")]
    lead = _recommendation(rec, name).split(". The reduction")[0]
    bits = []
    if good:
        bits.append(f"{_join(good)} {'is' if len(good) == 1 else 'are'} sound")
    if bad:
        bits.append(f"{_join(bad)} {'is' if len(bad) == 1 else 'are'} under pressure")
    if report.published_ratings:
        negative = [
            r
            for r in report.published_ratings
            if r.outlook == "NEGATIVE" or r.change == "DOWNGRADE"
        ]
        if negative:
            bits.append(
                "the rating agencies have turned cautious ("
                + ", ".join(f"{AGENCY_NAMES[r.agency]} {r.grade}" for r in negative)
                + ")"
            )
    text = lead if lead.endswith(".") else lead + "."
    if bits:
        text += (
            " "
            + bits[0][0].upper()
            + bits[0][1:]
            + ("; " + "; ".join(bits[1:]) if len(bits) > 1 else "")
            + "."
        )
    return text[:600]


def build_brief(
    report: AnalysisReport, rec: Recommendation, nums: dict[str, Any], name: str
) -> ExecutiveBrief:
    cur = rec.currency
    dims = "; ".join(
        f"{a.title} {DIMENSION_WORDS[a.status]} ({a.finding.lower()}, {a.trend.lower()})"
        for a in report.areas
        if a.feeds_draft
    )
    sections = [
        BriefSection(heading="Recommendation", text=_recommendation(rec, name)[:900]),
        BriefSection(heading="How the four core dimensions stand", text=(dims + ".")[:600]),
        BriefSection(heading="Financial position in numbers", text=_financial(nums, cur)[:900]),
    ]
    if report.cash_cycle is not None:
        cc = report.cash_cycle
        word = {
            "OK": "OK",
            "WEAK": "weak",
            "DISTRESSED": "distressed",
            "NOT_ASSESSED": "not rated",
        }[cc.status]
        sections.append(
            BriefSection(
                heading="Cash conversion cycle",
                text=(f"Rated {word} ({cc.finding.lower()}, {cc.trend.lower()}). {cc.summary}")[
                    :900
                ],
            )
        )
    sections.append(
        BriefSection(heading="What the rating agencies say", text=_ratings(report)[:1700])
    )
    sections.append(
        BriefSection(heading="Screening and external checks", text=_screening(report)[:900])
    )
    sections.append(
        BriefSection(heading="Annual report notes and auditor", text=_filing(report)[:900])
    )
    stress = _stress(report)
    if stress:
        sections.append(BriefSection(heading="If sales fall", text=stress[:600]))
    unknown = _unknown(report)
    if unknown:
        sections.append(BriefSection(heading="What is not known", text=unknown[:600]))
    return ExecutiveBrief(
        headline=_headline(report, rec, name),
        sections=sections,
        points_to_settle=_points(report),
    )
