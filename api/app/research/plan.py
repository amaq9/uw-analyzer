"""Research plan (FR-2.3, FR-2.4). A pure function: the same case facts and registry give the same
plan. It decides what WOULD be searched and what cannot be, and it never claims access.

Rules
- One group of steps per research category, for the jurisdictions the person named.
- A registered source that can be reached (ACTUALLY_ACCESSIBLE, or DISCOVERY_ONLY for leads) is
  PLANNED. Discovery-only sources are flagged: they can find leads but cannot verify alone (P-06).
- A relevant source that cannot be used (licence not held, technically unavailable, reported
  DOWN) is listed as NOT_AVAILABLE with the reason (FR-2.4), so the gap is visible, not hidden.
- A category with no registered source for the jurisdictions gets one NOT_AVAILABLE step saying so.
- Sources whose type is unknown to the plan are left out and named in `ignored_sources`.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from app.sources.schemas import AccessCategory, Health, SourceRecord

PLAN_RULES_VERSION = "1"


class Category(StrEnum):
    ENTITY_REGISTRY = "ENTITY_REGISTRY"
    FINANCIALS = "FINANCIALS"
    ADVERSE_SEARCH = "ADVERSE_SEARCH"
    COUNTRY_INDUSTRY = "COUNTRY_INDUSTRY"


class StepState(StrEnum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    SKIPPED = "SKIPPED"


# Registry `source_type` -> the categories it can serve.
TYPE_CATEGORIES: dict[str, tuple[Category, ...]] = {
    "company_registry": (Category.ENTITY_REGISTRY,),
    "financial_filings": (Category.FINANCIALS,),
    "court_records": (Category.ADVERSE_SEARCH,),
    "sanctions_list": (Category.ADVERSE_SEARCH,),
    "regulatory_actions": (Category.ADVERSE_SEARCH,),
    "insolvency_register": (Category.ADVERSE_SEARCH,),
    "news": (Category.ADVERSE_SEARCH, Category.COUNTRY_INDUSTRY),
    "macro_data": (Category.COUNTRY_INDUSTRY,),
    "industry_research": (Category.COUNTRY_INDUSTRY,),
}


@dataclass(frozen=True)
class PlannedStep:
    category: Category
    state: StepState
    reason: str | None
    source_id: str | None
    source_snapshot: dict[str, str | list[str] | None]
    discovery_only: bool = False


@dataclass(frozen=True)
class Plan:
    steps: list[PlannedStep]
    ignored_sources: list[str] = field(default_factory=list)


def _covers(source: SourceRecord, jurisdictions: list[str]) -> bool:
    return "GLOBAL" in source.jurisdictions or bool(set(source.jurisdictions) & set(jurisdictions))


def _snapshot(source: SourceRecord) -> dict[str, str | list[str] | None]:
    return {
        "key": source.key,
        "name": source.name,
        "source_class": source.source_class.value,
        "access_category": source.access_category.value,
        "health": source.health.value,
        "registry_version": str(source.version),
    }


def _unavailable_reason(source: SourceRecord) -> str | None:
    if source.access_category is AccessCategory.RESTRICTED_LICENSED:
        return "A licence or credential is needed and is not held."
    if source.access_category is AccessCategory.TECHNICALLY_UNAVAILABLE:
        return "The source is technically unavailable."
    if source.health is Health.DOWN:
        return "The source is reported as down."
    return None


def build_plan(jurisdictions: list[str], sources: list[SourceRecord]) -> Plan:
    steps: list[PlannedStep] = []
    ignored = sorted(s.key for s in sources if s.source_type not in TYPE_CATEGORIES)
    for category in Category:
        relevant = [
            s
            for s in sources
            if category in TYPE_CATEGORIES.get(s.source_type, ()) and _covers(s, jurisdictions)
        ]
        if not relevant:
            steps.append(
                PlannedStep(
                    category=category,
                    state=StepState.NOT_AVAILABLE,
                    reason="No source is registered for " + ", ".join(jurisdictions) + ".",
                    source_id=None,
                    source_snapshot={"jurisdictions": list(jurisdictions)},
                )
            )
            continue
        for source in relevant:
            reason = _unavailable_reason(source)
            discovery = source.access_category is AccessCategory.DISCOVERY_ONLY
            steps.append(
                PlannedStep(
                    category=category,
                    state=StepState.NOT_AVAILABLE if reason else StepState.PLANNED,
                    reason=reason
                    or (
                        "Discovery only: can find leads but cannot verify a material claim alone."
                        if discovery
                        else None
                    ),
                    source_id=str(source.id),
                    source_snapshot=_snapshot(source),
                    discovery_only=discovery,
                )
            )
    return Plan(steps=steps, ignored_sources=ignored)
