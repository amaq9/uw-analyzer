"""Turns a finished research run into findings and a draft recommendation (analyzer v1).

It reads only what the connectors stored (hash-checked snapshots), applies the written rules in
`assess.py`, records evidence and claims through the same append-only stores everything else uses,
and submits the draft through the same validated draft path. It never decides anything: the draft is
labelled as a draft, the server's approved policy sets the outcome and amount, and a person decides.

Not covered, and said so in every draft: reading the printed 10-K text, adverse-news content, court
records and any sector-level outlook."""

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import ROUND_DOWN, Decimal
from typing import Any

from fastapi import Request

from app.analysis import assess as rules
from app.analysis.assess import Level, Section, money, pct, times
from app.analysis.dimensions import dimension_metrics
from app.analysis.facts import METRICS, YearFigures, extract, to_figures
from app.analysis.ratios import compute
from app.analysis.report import FINDING_WORD, STATUS_WORD, build_report
from app.auth.models import Principal
from app.cases.schemas import CaseRecord
from app.escalations.store import PostgresEscalationStore
from app.evidence.rules import Relation
from app.evidence.store import PostgresEvidenceStore
from app.ratings.scale import AGENCY_NAMES
from app.ratings.schemas import to_out as to_rating_out
from app.recommendation.analysis_report import OtherCheck
from app.recommendation.policy import POLICY_VERSION
from app.recommendation.schemas import (
    DraftImport,
    DraftOut,
    EvidenceRef,
    Factor,
    Reason,
    SourceInfo,
)
from app.research.run_store import PostgresRunQueue
from app.research.schemas import CallRecord, RunRecord
from app.research.snapshots import SnapshotStore
from app.research.store import PostgresResearchStore
from app.sources.store import PostgresSourceStore
from app.statements.schemas import UNIT_TO_MILLIONS, StatementRecord
from app.statements.store import PostgresStatementStore

_REF = re.compile(r"^snapshot://(snapshots/[^#]+)#sha256=([0-9a-f]{64})$")
SEC_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
ORIGINS = {
    "sec-edgar": "sec.gov",
    "gleif": "gleif.org",
    "ofac-sdn": "treasury.gov",
    "world-bank": "worldbank.org",
}


_FIGURE_NAMES = {
    "cash": "Cash",
    "ebit": "EBIT",
    "ebitda": "EBITDA",
    "inventory": "Inventory",
    "interest_expense": "Interest expense",
}


def _derived_notes(derived: dict[str, str]) -> list[str]:
    """Plain notes on figures that were derived, with names a person recognises."""
    return [
        f"Figure derived: {_FIGURE_NAMES.get(key, key.replace('_', ' '))} is {text}"
        for key, text in derived.items()
    ]


class AnalysisUnavailable(Exception):
    """The analysis cannot be made yet. The message says what is missing, in plain words."""


@dataclass
class Outcome:
    status: str
    message: str
    sections: list[Section] = field(default_factory=list)
    consolidated: tuple[Level, str] | None = None
    draft: DraftOut | None = None
    proposed: Decimal | None = None
    requested: Decimal | None = None
    currency: str | None = None
    factors: list[rules.Factor] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    periods: list[str] = field(default_factory=list)
    evidence_created: int = 0
    claims_created: int = 0
    escalation_id: uuid.UUID | None = None


def _read(storage: Any, ref: str) -> bytes:
    match = _REF.match(ref)
    if not match:
        raise AnalysisUnavailable("A stored source reference could not be read.")
    body = SnapshotStore(storage).read(match.group(1))
    if hashlib.sha256(body).hexdigest() != match.group(2):
        raise AnalysisUnavailable(
            "A stored source no longer matches its recorded hash; it was not used."
        )
    return body


def _latest_run(
    research: PostgresResearchStore,
    queue: PostgresRunQueue,
    case: CaseRecord,
    run_id: uuid.UUID | None,
) -> tuple[RunRecord, list[CallRecord]]:
    runs = research.list_runs(case.id, case.tenant_id)
    if run_id is not None:
        runs = [r for r in runs if r.id == run_id]
    for run in runs:
        if run.status.value not in ("COMPLETED", "FAILED"):
            continue
        calls = [c for c in queue.calls_for_run(run.id) if c.outcome == "SUCCESS"]
        if calls:
            return run, calls
    raise AnalysisUnavailable(
        "No finished research run with a successful source call was found. Plan and start research first."
    )


def _by_source(calls: list[CallRecord]) -> dict[str, CallRecord]:
    latest: dict[str, CallRecord] = {}
    for call in calls:  # oldest first, so later calls win
        latest[call.source_key] = call
    return latest


def _evidence(
    store: PostgresEvidenceStore,
    sources: PostgresSourceStore,
    case: CaseRecord,
    principal: Principal,
    call: CallRecord,
    *,
    evidence_type: str,
    title: str,
    excerpt: str,
    published_on: date | None = None,
    event_on: date | None = None,
) -> tuple[Any, bool]:
    for existing in store.list_evidence(case.id, case.tenant_id):
        if existing.connector_call_id == call.id and existing.title == title:
            return existing, False
    source = sources.get(call.source_id)
    assert source is not None  # noqa: S101 - a logged call always names a registered source
    created = store.add_evidence(
        {
            "tenant_id": case.tenant_id,
            "case_id": case.id,
            "kind": "CONNECTOR",
            "evidence_type": evidence_type,
            "source_class": source.source_class.value,
            "class_basis": "registry",
            "source_id": call.source_id,
            "connector_call_id": call.id,
            "document_id": None,
            "title": title,
            "origin": ORIGINS.get(call.source_key, call.source_key),
            "url": None,
            "published_on": published_on,
            "event_on": event_on or call.ended_at.date(),
            "accessed_at": call.ended_at,
            "excerpt": excerpt[:1000],
            "provenance_ref": call.provenance_ref,
            "content_hash": None,
            "is_primary": True,
            "discovery_only": call.access_status == "DISCOVERY_ONLY",
            "created_by": principal.subject,
        }
    )
    return created, True


class _Claims:
    """Creates claims once: a claim whose exact text already exists on the case is reused."""

    def __init__(
        self, store: PostgresEvidenceStore, case: CaseRecord, principal: Principal
    ) -> None:
        self.store, self.case, self.principal = store, case, principal
        self.known = {c.text: c for c in store.list_claims(case.id, case.tenant_id)}
        self.created = 0

    def add(
        self,
        text: str,
        *,
        classification: str,
        material: bool,
        adverse: bool = False,
        category: str,
        relevance: str,
        evidence: list[Any] | None = None,
        basis: list[uuid.UUID] | None = None,
    ) -> Any:
        if text in self.known:
            return self.known[text]
        claim = self.store.add_claim(
            {
                "tenant_id": self.case.tenant_id,
                "case_id": self.case.id,
                "text": text,
                "classification": classification,
                "material": material,
                "adverse": adverse,
                "credit_relevance": relevance,
                "category": category,
                "unavailable_step_id": None,
                "created_by": self.principal.subject,
            },
            basis or [],
            [(e.id, Relation.SUPPORTS, None) for e in (evidence or [])],
        )
        self.known[text] = claim
        self.created += 1
        return claim


def _fact_text(key: str, sec: dict[str, Any], f: dict[str, float | None], fy: str, cur: str) -> str:
    """The figures behind one dimension, stated plainly with the period they come from."""
    m = dimension_metrics(sec, f, None)
    if key == "liquidity":
        lq = m["liquidity"]
        return (
            f"At {fy} the current ratio was {times(lq['current_ratio'])} (current assets {money(f.get('current_assets'), cur)} "
            f"over current liabilities {money(f.get('current_liabilities'), cur)}) and the quick ratio {times(lq['quick_ratio'])}; "
            f"working capital was {money(lq['working_capital'], cur)} and cash from operations was "
            f"{times(lq['ocf_to_current_liabilities'])} current liabilities."
        )
    if key == "profitability":
        pr = m["profitability"]
        return (
            f"For the year to {fy} revenue was {money(pr['revenue'], cur)}; net margin was {pct(pr['net_margin'])}, "
            f"operating margin {pct(pr['operating_margin'])} and EBITDA margin {pct(pr['ebitda_margin'])}; "
            f"return on average assets was {pct(pr['return_on_assets'])}."
        )
    if key == "leverage":
        gr, lv = sec["gearing"], m["leverage"]
        return (
            f"At {fy} financial debt was {money(gr['financial_debt'], cur)} against cash and short-term investments of "
            f"{money(f.get('cash'), cur)} (net {'cash' if (gr['net_debt_before_leases'] or 0) <= 0 else 'debt'} of "
            f"{money(abs(gr['net_debt_before_leases'] or 0), cur)} before leases); lease liabilities were "
            f"{money(f.get('lease_liabilities'), cur)}; {money(f.get('debt_due_12m'), cur)} of debt falls due within 12 months; "
            f"debt to equity was {times(lv['debt_to_equity'])}, net debt including leases {times(gr['net_debt_to_ebitda'])} EBITDA "
            f"and interest cover {times(gr['interest_cover'])}; equity was {pct(lv['equity_ratio'])} of assets."
        )
    cf = sec["cash_flow"]
    return (
        f"For the year to {fy} operating cash flow was {money(cf['operating_cash_flow'], cur)}, "
        f"{times(cf['ocf_to_net_income'])} net income; free cash flow was {money(cf['free_cash_flow'], cur)} against "
        f"dividends and buybacks of {money(cf['distributions'], cur)} ({money(cf['fcf_after_distributions'], cur)} after distributions)."
    )


@dataclass
class _Financials:
    years: list[YearFigures]
    figures: list[dict[str, float | None]]
    evidence: Any
    created: int
    label: str
    reference: Any  # (quote) -> EvidenceRef
    gaps: list[str]


def _from_sec(
    storage: Any,
    by_source: dict[str, CallRecord],
    case: CaseRecord,
    principal: Principal,
    evidence_store: PostgresEvidenceStore,
    sources: PostgresSourceStore,
) -> _Financials:
    if "sec-edgar" not in by_source:
        raise AnalysisUnavailable(
            "No financial statements were retrieved from a connected source (SEC EDGAR covers U.S. SEC filers). "
            "Upload the company's financial statements, check the figures and confirm them, then run the analysis again."
        )
    sec_call = by_source["sec-edgar"]
    manifest = json.loads(_read(storage, sec_call.provenance_ref or ""))
    facts_file = next((f for f in manifest["files"] if f["label"] == "companyfacts"), None)
    if facts_file is None:
        raise AnalysisUnavailable("The SEC retrieval did not include reported financial data.")
    company_facts = json.loads(_read(storage, facts_file["ref"]))
    years: list[YearFigures] = extract(company_facts, 3)
    if not years:
        raise AnalysisUnavailable("No annual (10-K) financial figures were found for this company.")
    figures = [
        to_figures(y, years[i + 1] if i + 1 < len(years) else None) for i, y in enumerate(years)
    ]
    latest, fy = years[0], years[0].period_end.isoformat()
    ev, made = _evidence(
        evidence_store,
        sources,
        case,
        principal,
        sec_call,
        evidence_type="FINANCIAL",
        title=f"{case.legal_name} annual report data for the year ended {fy} (SEC 10-K {latest.accession}, XBRL company facts)",
        excerpt=(
            f"Year ended {fy} (USD m unless stated): total assets {figures[0]['total_assets']}; equity {figures[0]['total_equity']}; "
            f"current assets {figures[0]['current_assets']}; current liabilities {figures[0]['current_liabilities']}; "
            f"cash and short-term investments {figures[0]['cash']}; financial debt {figures[0]['financial_debt']}; "
            f"receivables {figures[0]['receivables']}; revenue {figures[0]['revenue']}; operating cash flow {figures[0]['ocf']}; "
            f"net income {figures[0]['net_income']}; dividends {figures[0]['dividends']}; buybacks {figures[0]['buybacks']}."
        ),
        published_on=latest.filed,
        event_on=latest.period_end,
    )
    url = SEC_URL.format(cik=manifest["cik"])

    def reference(quote: str) -> EvidenceRef:
        return EvidenceRef(kind="web", url=url, retrieved_at=sec_call.ended_at, quote=quote)

    gaps = ["The printed 10-K text, notes and auditor's report were not read"]
    gaps += _derived_notes(latest.derived)
    return _Financials(years, figures, ev, int(made), "SEC XBRL company facts", reference, gaps)


def _from_uploaded(
    request: Request,
    principal: Principal,
    case: CaseRecord,
    uploaded: list[StatementRecord],
    evidence_store: PostgresEvidenceStore,
    currency: str,
) -> _Financials:
    if any(s.currency != currency for s in uploaded):
        raise AnalysisUnavailable(
            f"The confirmed statements are in {uploaded[0].currency} but the exposure is requested in {currency}. "
            "Use the same currency for both."
        )
    uploaded = sorted(uploaded, key=lambda s: s.period_end, reverse=True)[:3]
    years: list[YearFigures] = []
    for s in uploaded:
        factor = UNIT_TO_MILLIONS[s.unit.value]
        years.append(
            YearFigures(
                period_end=s.period_end,
                values={
                    m: (float(s.figures[m]) * factor if s.figures.get(m) is not None else None)
                    for m in METRICS
                },
            )
        )
    figures = [
        to_figures(y, years[i + 1] if i + 1 < len(years) else None) for i, y in enumerate(years)
    ]
    latest_stmt, latest = uploaded[0], years[0]
    fy = latest.period_end.isoformat()
    document = request.app.state.document_store.get(latest_stmt.document_id)
    filename = document.filename if document else "uploaded statement"
    declared_class = "COMMERCIAL" if latest_stmt.audit_status.value == "AUDITED" else "SECONDARY"
    title = f"{filename}: statements for the year ended {fy} ({latest_stmt.audit_status.value.lower()}, supplied by the company)"
    existing = next(
        (
            e
            for e in evidence_store.list_evidence(case.id, case.tenant_id)
            if e.document_id == latest_stmt.document_id and e.title == title
        ),
        None,
    )
    created = 0
    if existing is None:
        f = figures[0]
        existing = evidence_store.add_evidence(
            {
                "tenant_id": case.tenant_id,
                "case_id": case.id,
                "kind": "DOCUMENT",
                "evidence_type": "FINANCIAL",
                "source_class": declared_class,
                "class_basis": "author_declared",
                "source_id": None,
                "connector_call_id": None,
                "document_id": latest_stmt.document_id,
                "title": title,
                "origin": rules_name(case.legal_name) or "the company",
                "url": None,
                "published_on": None,
                "event_on": latest.period_end,
                "accessed_at": latest_stmt.confirmed_at,
                "excerpt": (
                    f"Year ended {fy}, figures confirmed by {latest_stmt.confirmed_by} from the uploaded document "
                    f"(USD m unless stated): total assets {f['total_assets']}; equity {f['total_equity']}; "
                    f"current assets {f['current_assets']}; current liabilities {f['current_liabilities']}; "
                    f"receivables {f['receivables']}; revenue {f['revenue']}; operating cash flow {f['ocf']}; net income {f['net_income']}."
                )[:1000],
                "provenance_ref": f"document:{latest_stmt.document_id}",
                "content_hash": document.sha256 if document else None,
                "is_primary": True,
                "discovery_only": False,
                "created_by": principal.subject,
            }
        )
        created = 1

    def reference(quote: str) -> EvidenceRef:
        return EvidenceRef(kind="document", document_id=latest_stmt.document_id, quote=quote)

    gaps = [
        f"The figures were read from an uploaded document and confirmed by {latest_stmt.confirmed_by}; the rest of the document was not analysed",
        "Statements are "
        + (
            "audited"
            if latest_stmt.audit_status.value == "AUDITED"
            else "NOT audited ("
            + latest_stmt.audit_status.value.lower()
            + ") and were supplied by the company, so they count as weaker evidence"
        ),
    ]
    gaps += _derived_notes(latest.derived)
    return _Financials(
        years, figures, existing, created, f"uploaded statement {filename}", reference, gaps
    )


def analyse(
    request: Request,
    principal: Principal,
    case: CaseRecord,
    run_id: uuid.UUID | None,
    financials: str = "auto",
) -> Outcome:
    from app.recommendation.router import import_draft

    state = request.app.state
    research: PostgresResearchStore = state.research_store
    queue: PostgresRunQueue = state.run_queue
    evidence_store: PostgresEvidenceStore = state.evidence_store
    sources: PostgresSourceStore = state.source_store
    service = getattr(state, "document_service", None)
    if service is None:
        raise AnalysisUnavailable(
            "Stored source material cannot be read because storage is not set up."
        )
    storage = service.storage
    if case.exposure_amount is None or case.exposure_amount <= 0:
        raise AnalysisUnavailable(
            "The case has no requested exposure. Add it on the case, then run the analysis again."
        )

    statements: PostgresStatementStore = state.statement_store
    uploaded = statements.latest_per_period(case.id, case.tenant_id)
    if financials == "uploaded" and not uploaded:
        raise AnalysisUnavailable(
            "No confirmed uploaded financial statements were found. Upload a statement, check the figures and confirm them first."
        )
    use_uploaded = bool(uploaded) and financials != "sec"
    try:
        run, calls = _latest_run(research, queue, case, run_id)
    except AnalysisUnavailable:
        if not use_uploaded:
            raise
        run, calls = None, []  # figures were uploaded, so a finished research run is not required
    by_source = _by_source(calls)
    steps = research.steps_for_run(run.id) if run else []
    currency = case.exposure_currency or "USD"
    out = Outcome(status="", message="", requested=case.exposure_amount, currency=currency)
    claims = _Claims(evidence_store, case, principal)

    # --- sanctions first: a possible match needs a person, so no draft is made ------------------
    ofac_note: tuple[Any, Any] | None = None
    if "ofac-sdn" in by_source:
        call = by_source["ofac-sdn"]
        result = json.loads(_read(storage, call.provenance_ref or ""))
        exact, possible = result["exact_match_count"], result["possible_match_count"]
        ev, made = _evidence(
            evidence_store,
            sources,
            case,
            principal,
            call,
            evidence_type="LEGAL_REGULATORY",
            title=f"OFAC sanctions list name search for {case.legal_name or 'the entity'}",
            excerpt=(
                f"Searched '{result['searched_name']}' against the OFAC SDN list and aliases: {exact} exact and "
                f"{possible} possible matches. Name search only. Files sha256 "
                + ", ".join(f["sha256"][:12] for f in result["files"])
            ),
            event_on=call.ended_at.date(),
        )
        out.evidence_created += int(made)
        if exact or possible:
            text = (
                f"The OFAC sanctions list name search for {case.legal_name} returned {exact} exact and {possible} possible "
                "matches. A name match is not proof the entity is sanctioned; a person must review it."
            )
            claims.add(
                text,
                classification="FACT",
                material=True,
                adverse=True,
                category="ADVERSE_SEARCH",
                relevance="Sanctions",
                evidence=[ev],
            )
            escalations: PostgresEscalationStore = state.escalation_store
            row = escalations.add(
                {
                    "tenant_id": case.tenant_id,
                    "case_id": case.id,
                    "kind": "MATERIAL_AMBIGUITY",
                    "claim_id": None,
                    "description": text,
                    "raised_by_system": True,
                    "created_by": "system",
                }
            )
            out.claims_created = claims.created
            out.status = "NEEDS_REVIEW"
            out.escalation_id = row["id"]
            out.message = (
                "The sanctions-list search found a possible match. No draft was made. A person must review the "
                "item under Review items first."
            )
            return out
        ofac_note = (
            ev,
            claims.add(
                f"A name search of the OFAC SDN list and its aliases for {case.legal_name} found no exact or possible match "
                "(name screening only; UN, EU and Canadian lists were not searched).",
                classification="FACT",
                material=True,
                category="ADVERSE_SEARCH",
                relevance="Sanctions",
                evidence=[ev],
            ),
        )

    other_checks: list[OtherCheck] = []
    if ofac_note:
        other_checks.append(
            OtherCheck(
                title="Sanctions list (OFAC SDN)",
                state="CLEAR",
                detail="Name search found no exact or possible match. Name screening only; UN, EU and Canadian lists were not searched.",
            )
        )
    else:
        other_checks.append(
            OtherCheck(
                title="Sanctions list (OFAC SDN)",
                state="NOT_SEARCHED",
                detail="The OFAC sanctions list was not searched in this run.",
            )
        )

    # --- financial statements -------------------------------------------------------------------
    if use_uploaded:
        fin = _from_uploaded(request, principal, case, uploaded, evidence_store, currency)
    else:
        fin = _from_sec(storage, by_source, case, principal, evidence_store, sources)
    years, figures, fin_ev, latest = fin.years, fin.figures, fin.evidence, fin.years[0]
    out.evidence_created += fin.created
    contexts = [rules.YearContext(ratios=compute(f), figures=f) for f in figures]
    sections = rules.assess(contexts, currency)
    level, why = rules.consolidated(sections)
    fy = latest.period_end.isoformat()
    out.periods = [y.period_end.isoformat() for y in years]
    out.sections = [sections[k] for k in rules.SECTIONS]
    out.consolidated = (level, why)

    ratios0 = contexts[0].ratios
    fact_claims: dict[str, Any] = {}
    for key in rules.SECTIONS:
        sec = sections[key]
        if sec.level is Level.NOT_ASSESSED:
            continue
        fact_claims[key] = claims.add(
            _fact_text(key, ratios0, figures[0], fy, currency),
            classification="FACT",
            material=True,
            adverse=sec.level in (Level.NEEDS_ATTENTION, Level.WEAK),
            category="FINANCIALS",
            relevance=sec.title,
            evidence=[fin_ev],
        )
    for key, fact in fact_claims.items():
        sec = sections[key]
        claims.add(
            f"{sec.title}: {FINDING_WORD[sec.level]} ({sec.trend.lower()}). {sec.why}",
            classification="INTERPRETATION",
            material=True,
            category="FINANCIALS",
            relevance=sec.title,
            basis=[fact.id],
        )
    if fact_claims:
        claims.add(
            f"Consolidated financial findings: {FINDING_WORD[level]}. {why}",
            classification="INTERPRETATION",
            material=True,
            category="FINANCIALS",
            relevance="Consolidated financial findings",
            basis=[c.id for c in fact_claims.values()],
        )

    # --- other research areas -------------------------------------------------------------------
    gaps: list[str] = []
    if "gleif" in by_source:
        call = by_source["gleif"]
        body = json.loads(_read(storage, call.provenance_ref or ""))
        wanted = rules_name(case.legal_name)
        exact = [
            r
            for r in body.get("data", [])
            if rules_name(r["attributes"]["entity"]["legalName"]["name"]) == wanted
        ]
        ev, made = _evidence(
            evidence_store,
            sources,
            case,
            principal,
            call,
            evidence_type="REGISTRY",
            title=f"GLEIF legal entity search for {case.legal_name}",
            excerpt=f"{len(body.get('data', []))} records returned; {len(exact)} match the legal name exactly"
            + (
                f" ({exact[0]['id']}, entity status {exact[0]['attributes']['entity']['status']})."
                if exact
                else "."
            ),
        )
        out.evidence_created += int(made)
        if exact:
            other_checks.append(
                OtherCheck(
                    title="Entity register (Global LEI)",
                    state="FOUND",
                    detail=f"Listed by exact legal name (LEI {exact[0]['id']}), entity status {exact[0]['attributes']['entity']['status']}.",
                )
            )
            claims.add(
                f"The Global LEI register lists {case.legal_name} (LEI {exact[0]['id']}) with entity status "
                f"{exact[0]['attributes']['entity']['status']}.",
                classification="FACT",
                material=False,
                category="ENTITY_REGISTRY",
                relevance="Entity",
                evidence=[ev],
            )
        else:
            gaps.append("The entity was not found by exact legal name in the Global LEI register")
            other_checks.append(
                OtherCheck(
                    title="Entity register (Global LEI)",
                    state="INCOMPLETE",
                    detail="Not found by exact legal name. This is not evidence the entity does not exist.",
                )
            )
    else:
        gaps.append("The Global LEI register was not searched")
        other_checks.append(
            OtherCheck(
                title="Entity register (Global LEI)",
                state="NOT_SEARCHED",
                detail="The Global LEI register was not searched in this run.",
            )
        )

    if "world-bank" in by_source:
        call = by_source["world-bank"]
        wb = json.loads(_read(storage, call.provenance_ref or ""))
        parts = []
        for r in wb["responses"]:
            rows = [x for x in r["body"][1] if x.get("value") is not None]
            if rows:
                parts.append(
                    f"{r['country']} {wb['indicators'][r['indicator']].split(' (')[0].lower()} {rows[0]['value']:.1f}% ({rows[0]['date']})"
                )
        ev, made = _evidence(
            evidence_store,
            sources,
            case,
            principal,
            call,
            evidence_type="MACRO_INDUSTRY",
            title="World Bank macro indicators for the named countries",
            excerpt="; ".join(parts),
        )
        out.evidence_created += int(made)
        other_checks.append(
            OtherCheck(
                title="Country economy (World Bank)",
                state="FOUND",
                detail=("; ".join(parts) or "Indicators retrieved.")
                + ". Country level only, not a sector outlook.",
            )
        )
        claims.add(
            "Macroeconomic backdrop (country level, not a sector outlook): "
            + "; ".join(parts)
            + ".",
            classification="FACT",
            material=False,
            category="COUNTRY_INDUSTRY",
            relevance="Macroeconomic backdrop",
            evidence=[ev],
        )

    adverse_steps = [s for s in steps if s.category.value == "ADVERSE_SEARCH"]
    adverse_complete = bool(adverse_steps) and all(
        s.state.value == "SUCCEEDED" for s in adverse_steps
    )
    for s in adverse_steps:
        if s.state.value != "SUCCEEDED":
            name = str(s.source_snapshot.get("name") or "an adverse-information source")
            gaps.append(
                f"{name} was not searched or did not complete ({s.state.value.replace('_', ' ').lower()})"
            )
    if adverse_steps and adverse_complete:
        other_checks.append(
            OtherCheck(
                title="Adverse-information search",
                state="NOT_ASSESSED",
                detail=f"{len(adverse_steps)} search(es) ran. Their results are leads only and were not analysed here; see the Research tab.",
            )
        )
    elif adverse_steps:
        other_checks.append(
            OtherCheck(
                title="Adverse-information search",
                state="INCOMPLETE",
                detail="At least one search did not complete; see the Research tab.",
            )
        )
    else:
        other_checks.append(
            OtherCheck(
                title="Adverse-information search",
                state="NOT_SEARCHED",
                detail="No adverse-information search was planned or run.",
            )
        )
    other_checks += [
        OtherCheck(
            title="Sector outlook",
            state="NOT_ASSESSED",
            detail="Only country-level economic data is connected, so the sector outlook was not assessed.",
        ),
        OtherCheck(
            title="Court records and other regulators",
            state="NOT_SEARCHED",
            detail="Regulators and courts other than the OFAC list were not searched.",
        ),
        OtherCheck(
            title="Payment behaviour",
            state="NOT_ASSESSED",
            detail="Payment data is outside the scope of this product.",
        ),
    ]
    gaps.append(
        "Sector-level outlook was not assessed (only country-level economic data is connected)"
    )
    gaps.append("Court records and regulators other than the OFAC sanctions list were not searched")
    gaps.append("Receivables aging and allowance for credit losses were not available as figures")
    gaps.extend(fin.gaps)
    for key in rules.CORE:
        section = sections[key]
        if section.level is Level.NOT_ASSESSED:
            gaps.append(f"{section.title} could not be assessed: {section.why}")

    # --- proposal and draft ---------------------------------------------------------------------
    fraction, factors = rules.propose_fraction(
        sections, adverse_search_complete=adverse_complete, sector_outlook_assessed=False
    )
    proposed = (case.exposure_amount * fraction).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    out.proposed, out.factors, out.gaps = proposed, factors, gaps
    out.claims_created = claims.created

    def ref(quote: str) -> EvidenceRef:
        made: EvidenceRef = fin.reference(quote[:300])
        return made

    reasons = [
        Reason(
            text=f"{sec.title}: {FINDING_WORD[sec.level].lower()}. {sec.why}"[:500],
            evidence=[ref(f"{sec.title} for the year ended {fy} ({fin.label})")],
        )
        for sec in out.sections
        if sec.level is not Level.NOT_ASSESSED
    ] or [
        Reason(
            text="No section could be assessed from the data.",
            evidence=[ref(fin.label)],
        )
    ]
    if ofac_note:
        reasons.append(
            Reason(
                text="No match on the OFAC sanctions list (name search only).",
                evidence=[
                    EvidenceRef(
                        kind="web",
                        url="https://sanctionslistservice.ofac.treas.gov/api/publicationpreview/exports/sdn.csv",
                        retrieved_at=by_source["ofac-sdn"].ended_at,
                        quote="OFAC SDN name search, 0 exact and 0 possible matches",
                    )
                ],
            )
        )
    audit_note = next(
        (g for g in fin.gaps if "audited" in g.lower()), "Audit status is not stated."
    )
    ratings = [
        to_rating_out(r) for r in state.rating_store.latest_per_agency(case.id, case.tenant_id)
    ]
    other_checks.append(
        OtherCheck(
            title="Published credit ratings",
            state="FOUND" if ratings else "NOT_SEARCHED",
            detail=(
                "Recorded: "
                + ", ".join(f"{AGENCY_NAMES[r.agency]} {r.grade}" for r in ratings)
                + ". Information only."
                if ratings
                else "No published rating is recorded. The product does not search for ratings by itself; a person or an analyst session records them with their source."
            ),
        )
    )
    analysis_report = build_report(
        sections=sections,
        order=rules.SECTIONS,
        consolidated=(level, why),
        ratio_sets=[c.ratios for c in contexts],
        figure_sets=figures,
        periods=out.periods,
        currency=currency,
        statements_label=fin.label[:600],
        audit_note=audit_note[:600],
        other_checks=other_checks,
        gaps=gaps,
        analyzer_version=rules.ANALYZER_VERSION,
        ratings=ratings,
        as_of=datetime.now(UTC).date(),
    )
    summary = (
        f"Consolidated financial findings: {STATUS_WORD[analysis_report.consolidated_status]}. "
        f"{analysis_report.consolidated_why} By dimension: "
        + "; ".join(
            f"{s.title.lower()} {FINDING_WORD[s.level].lower()}"
            for s in out.sections
            if s.key in rules.CORE
        )
        + f". Proposed amount {money(float(proposed) / 1e6, currency)} of {money(float(case.exposure_amount) / 1e6, currency)} requested "
        "after the reductions listed. The adverse-news search, court records and sector outlook are not complete."
    )[:600]
    body = DraftImport(
        ai_proposed_amount=proposed,
        financial_findings_weak=level is Level.WEAK,
        decline_findings=[],
        factors=[Factor(code=f.code, explanation=f.explanation[:400]) for f in factors],  # type: ignore[arg-type]
        summary=summary,
        reasons=reasons,
        information_gaps=[g[:200] for g in gaps][:20],
        analysis=analysis_report,
        source=SourceInfo(
            kind="analyzer_v1",
            model="rules engine (no AI model)",
            skill_version=f"analyzer v{rules.ANALYZER_VERSION} (analyst-framework dimensions)",
            policy_version=POLICY_VERSION,
        ),
    )
    out.draft = import_draft(request, case.id, body, principal)
    out.status = "DRAFT_PREPARED"
    out.message = "A draft recommendation was prepared for the underwriter. It is not a decision."
    return out


def rules_name(name: str | None) -> str:
    from app.research.public_connectors import normalise_name

    return normalise_name(name or "")
