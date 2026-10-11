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
from datetime import date
from decimal import ROUND_DOWN, Decimal
from typing import Any

from fastapi import Request

from app.analysis import assess as rules
from app.analysis.assess import Level, Section, money, pct, times
from app.analysis.facts import YearFigures, extract, to_figures
from app.analysis.ratios import compute
from app.auth.models import Principal
from app.cases.schemas import CaseRecord
from app.escalations.store import PostgresEscalationStore
from app.evidence.rules import Relation
from app.evidence.store import PostgresEvidenceStore
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

_REF = re.compile(r"^snapshot://(snapshots/[^#]+)#sha256=([0-9a-f]{64})$")
SEC_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
ORIGINS = {
    "sec-edgar": "sec.gov",
    "gleif": "gleif.org",
    "ofac-sdn": "treasury.gov",
    "world-bank": "worldbank.org",
}


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
    bs, lq, gr = sec["balance_sheet"], sec["liquidity"], sec["gearing"]
    rc, cf = sec["receivables"], sec["cash_flow"]
    if key == "balance_sheet":
        return (
            f"At {fy} the equity was {money(bs['equity'], cur)}, {pct(bs['equity_to_assets'])} of total assets of "
            f"{money(f.get('total_assets'), cur)}; goodwill and intangibles were {money(bs['goodwill_and_intangibles'], cur)}, "
            f"{pct(bs['goodwill_and_intangibles_to_assets'])} of assets."
        )
    if key == "liquidity":
        return (
            f"At {fy} the current ratio was {times(lq['current_ratio'])} (current assets {money(f.get('current_assets'), cur)} "
            f"over current liabilities {money(f.get('current_liabilities'), cur)}) and the quick ratio {times(lq['quick_ratio'])}; "
            f"working capital was {money(lq['working_capital'], cur)}."
        )
    if key == "gearing":
        return (
            f"At {fy} financial debt was {money(gr['financial_debt'], cur)} against cash and short-term investments of "
            f"{money(f.get('cash'), cur)} (net {'cash' if (gr['net_debt_before_leases'] or 0) <= 0 else 'debt'} of "
            f"{money(abs(gr['net_debt_before_leases'] or 0), cur)} before leases); lease liabilities were "
            f"{money(f.get('lease_liabilities'), cur)}; {money(f.get('debt_due_12m'), cur)} of debt falls due within 12 months; "
            f"net debt including leases was {times(gr['net_debt_to_ebitda'])} EBITDA and interest cover {times(gr['interest_cover'])}."
        )
    if key == "receivables":
        return (
            f"At {fy} receivables were {money(rc['receivables'], cur)} (prior year {money(f.get('prior_receivables'), cur)}), "
            f"{rc['dso_days']:.1f} days of revenue; receivables absorbed {money(rc['cash_absorbed_by_receivables'], cur)} of cash. "
            "No aging schedule or allowance is in the structured data."
            if rc["dso_days"] is not None
            else f"At {fy} receivables could not be assessed from the data."
        )
    return (
        f"For the year to {fy} operating cash flow was {money(cf['operating_cash_flow'], cur)}, "
        f"{times(cf['ocf_to_net_income'])} net income; free cash flow was {money(cf['free_cash_flow'], cur)} against "
        f"dividends and buybacks of {money(cf['distributions'], cur)} ({money(cf['fcf_after_distributions'], cur)} after distributions)."
    )


def analyse(
    request: Request, principal: Principal, case: CaseRecord, run_id: uuid.UUID | None
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

    run, calls = _latest_run(research, queue, case, run_id)
    by_source = _by_source(calls)
    steps = research.steps_for_run(run.id)
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

    # --- financial statements -------------------------------------------------------------------
    if "sec-edgar" not in by_source:
        raise AnalysisUnavailable(
            "No financial statements were retrieved from a connected source (SEC EDGAR covers U.S. SEC filers). "
            "Add the statements another way before a draft can be made."
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
    contexts = [rules.YearContext(ratios=compute(f), figures=f) for f in figures]
    sections = rules.assess(contexts, currency)
    level, why = rules.consolidated(sections)
    latest = years[0]
    fy = latest.period_end.isoformat()
    out.periods = [y.period_end.isoformat() for y in years]
    out.sections = [sections[k] for k in rules.SECTIONS]
    out.consolidated = (level, why)

    fin_ev, made = _evidence(
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
    out.evidence_created += int(made)

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
            f"{sec.title}: {sec.level.value.replace('_', ' ').capitalize()} ({sec.trend.lower()}). {sec.why}",
            classification="INTERPRETATION",
            material=True,
            category="FINANCIALS",
            relevance=sec.title,
            basis=[fact.id],
        )
    if fact_claims:
        claims.add(
            f"Consolidated financial findings: {level.value.replace('_', ' ').capitalize()}. {why}",
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
    else:
        gaps.append("The Global LEI register was not searched")

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
    gaps.append(
        "Sector-level outlook was not assessed (only country-level economic data is connected)"
    )
    gaps.append("Court records and regulators other than the OFAC sanctions list were not searched")
    gaps.append("Receivables aging and allowance for credit losses are not in the structured data")
    gaps.append("The printed 10-K text, notes and auditor's report were not read")
    for key, text in latest.derived.items():
        gaps.append(f"Figure derived: {key} is {text}")
    for section in sections.values():
        if section.level is Level.NOT_ASSESSED:
            gaps.append(f"{section.title} could not be assessed: {section.why}")

    # --- proposal and draft ---------------------------------------------------------------------
    fraction, factors = rules.propose_fraction(
        sections, adverse_search_complete=adverse_complete, sector_outlook_assessed=False
    )
    proposed = (case.exposure_amount * fraction).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    out.proposed, out.factors, out.gaps = proposed, factors, gaps
    out.claims_created = claims.created

    retrieved = sec_call.ended_at
    url = SEC_URL.format(cik=manifest["cik"])

    def ref(quote: str) -> EvidenceRef:
        return EvidenceRef(kind="web", url=url, retrieved_at=retrieved, quote=quote[:300])

    reasons = [
        Reason(
            text=f"{sec.title}: {sec.level.value.replace('_', ' ').lower()}. {sec.why}"[:500],
            evidence=[ref(f"{sec.title} for the year ended {fy} (SEC XBRL company facts)")],
        )
        for sec in out.sections
        if sec.level is not Level.NOT_ASSESSED
    ] or [
        Reason(
            text="No section could be assessed from the data.",
            evidence=[ref("SEC XBRL company facts")],
        )
    ]
    if ofac_note:
        reasons.append(
            Reason(
                text="No match on the OFAC sanctions list (name search only).",
                evidence=[ref("OFAC SDN name search, 0 exact and 0 possible matches")],
            )
        )
    summary = (
        f"Consolidated financial findings: {level.value.replace('_', ' ').lower()} ({why}) "
        + "; ".join(
            f"{s.title.lower()} {s.level.value.replace('_', ' ').lower()}" for s in out.sections
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
        source=SourceInfo(
            kind="analyzer_v1",
            model="rules engine (no AI model)",
            skill_version=f"analyzer v{rules.ANALYZER_VERSION} (statement-assessment method)",
            policy_version="1.0",
        ),
    )
    out.draft = import_draft(request, case.id, body, principal)
    out.status = "DRAFT_PREPARED"
    out.message = "A draft recommendation was prepared for the underwriter. It is not a decision."
    return out


def rules_name(name: str | None) -> str:
    from app.research.public_connectors import normalise_name

    return normalise_name(name or "")
