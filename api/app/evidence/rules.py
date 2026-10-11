"""Verification and freshness rules (FR-3.4 to FR-3.7; P-04, P-05, P-06). Pure functions: the same
facts always give the same answer, and nothing here can be overridden by a user or a model.

Verification status is exactly one of five values. It is computed from the evidence linked to a
claim, never stored from input, so no caller can set it.

    reliable evidence  = an OFFICIAL or COMMERCIAL source that is not discovery-only
    definitive primary = reliable, OFFICIAL, and the originating record (a filing, a judgment)
    independent        = reliable sources with different origins

    non-material claim            VERIFIED with one reliable supporting source
    material claim                VERIFIED with one reliable supporting source
    material adverse claim        VERIFIED only with a definitive primary source, or with two
                                  independent reliable sources (FR-3.7)
    weak or discovery-only evidence alone never verifies a material claim (P-06)
    reliable contradicting evidence prevents VERIFIED and is flagged as a conflict (P-07)
"""

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

RULES_VERSION = "1"


class VerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Freshness(StrEnum):
    CURRENT = "CURRENT"
    RECENT = "RECENT"
    STALE = "STALE"
    HISTORICAL = "HISTORICAL"


class EvidenceType(StrEnum):
    REGISTRY = "REGISTRY"
    FINANCIAL = "FINANCIAL"
    LEGAL_REGULATORY = "LEGAL_REGULATORY"
    NEWS = "NEWS"
    MACRO_INDUSTRY = "MACRO_INDUSTRY"
    OTHER = "OTHER"


class Classification(StrEnum):
    FACT = "FACT"
    INTERPRETATION = "INTERPRETATION"
    INFERENCE = "INFERENCE"
    UNVERIFIED = "UNVERIFIED"


class Relation(StrEnum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"


# Age in days up to which evidence is CURRENT, RECENT, STALE; older is HISTORICAL (FR-3.5).
FRESHNESS_DAYS: dict[EvidenceType, tuple[int, int, int]] = {
    EvidenceType.REGISTRY: (180, 365, 1095),
    EvidenceType.FINANCIAL: (400, 800, 1500),
    EvidenceType.LEGAL_REGULATORY: (180, 730, 1825),
    EvidenceType.NEWS: (90, 365, 1095),
    EvidenceType.MACRO_INDUSTRY: (120, 400, 1000),
    EvidenceType.OTHER: (90, 365, 1095),
}


def freshness(evidence_type: EvidenceType, evidence_date: date, today: date) -> Freshness:
    current, recent, stale = FRESHNESS_DAYS[evidence_type]
    age = (today - evidence_date).days
    if age <= current:
        return Freshness.CURRENT
    if age <= recent:
        return Freshness.RECENT
    if age <= stale:
        return Freshness.STALE
    return Freshness.HISTORICAL


@dataclass(frozen=True)
class EvidenceFacts:
    source_class: str  # OFFICIAL, COMMERCIAL, SECONDARY, WEAK
    discovery_only: bool
    is_primary: bool
    origin: str

    @property
    def reliable(self) -> bool:
        return self.source_class in ("OFFICIAL", "COMMERCIAL") and not self.discovery_only

    @property
    def definitive_primary(self) -> bool:
        return self.reliable and self.source_class == "OFFICIAL" and self.is_primary


@dataclass(frozen=True)
class ClaimFacts:
    classification: Classification
    material: bool
    adverse: bool
    source_unavailable: bool  # an attempted source was recorded as unavailable
    supporting: tuple[EvidenceFacts, ...] = ()
    contradicting: tuple[EvidenceFacts, ...] = ()


@dataclass(frozen=True)
class Verdict:
    status: VerificationStatus
    reasons: list[str] = field(default_factory=list)
    needs: list[str] = field(default_factory=list)
    conflict: bool = False


def verify(claim: ClaimFacts) -> Verdict:
    if claim.classification in (Classification.INTERPRETATION, Classification.INFERENCE):
        return Verdict(
            VerificationStatus.NOT_APPLICABLE,
            ["This is a judgement, not a fact. It is supported by the facts it is based on."],
        )

    reliable = [e for e in claim.supporting if e.reliable]
    weak = [e for e in claim.supporting if not e.reliable]
    origins = {e.origin for e in reliable}
    reliable_against = [e for e in claim.contradicting if e.reliable]
    conflict = bool(reliable_against)
    reasons: list[str] = []
    needs: list[str] = []

    if not claim.supporting:
        reasons.append("No supporting evidence is linked.")
        if conflict:
            reasons.append("Reliable evidence contradicts it.")
        if claim.source_unavailable:
            return Verdict(
                VerificationStatus.SOURCE_UNAVAILABLE,
                ["The source that could support this was not available."],
                ["Reach the source, or record the limitation."],
                conflict,
            )
        return Verdict(
            VerificationStatus.UNVERIFIED, reasons, ["Link a reliable source."], conflict
        )

    if claim.material and claim.adverse:
        enough = any(e.definitive_primary for e in reliable) or len(origins) >= 2
        if not enough:
            needs.append(
                "A material adverse claim needs a definitive primary source or two independent "
                "reliable sources (FR-3.7)."
            )
    else:
        enough = bool(reliable)
        if not enough:
            needs.append(
                "A reliable source (official or commercial, not discovery-only) is needed."
            )

    if weak and not reliable:
        reasons.append(
            "Only weak or discovery-only sources support it; they cannot verify it alone (P-06)."
        )
    if conflict:
        reasons.append("Reliable evidence contradicts it. A person must resolve the conflict.")
        needs.append("Resolve the conflict between the sources.")
    if claim.classification is Classification.UNVERIFIED:
        reasons.append("It was recorded as unverified, so it cannot be marked verified.")
        enough = False

    if enough and not conflict:
        return Verdict(VerificationStatus.VERIFIED, ["Supported by reliable evidence."], [], False)
    return Verdict(VerificationStatus.PARTIALLY_VERIFIED, reasons, needs, conflict)
