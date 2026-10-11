"""Verification and freshness rules (pure). These are the protocol's evidence rules as tests."""

from datetime import date

import pytest

from app.evidence.rules import (
    ClaimFacts,
    Classification,
    EvidenceFacts,
    EvidenceType,
    Freshness,
    VerificationStatus,
    freshness,
    verify,
)

V = VerificationStatus


def ev(
    cls: str = "OFFICIAL", *, discovery: bool = False, primary: bool = False, origin: str = "a.org"
) -> EvidenceFacts:
    return EvidenceFacts(cls, discovery, primary, origin)


def claim(
    *,
    material: bool = True,
    adverse: bool = False,
    classification: Classification = Classification.FACT,
    unavailable: bool = False,
    supporting: tuple[EvidenceFacts, ...] = (),
    contradicting: tuple[EvidenceFacts, ...] = (),
) -> ClaimFacts:
    return ClaimFacts(classification, material, adverse, unavailable, supporting, contradicting)


def test_status_values_are_exactly_the_five() -> None:
    assert {s.value for s in VerificationStatus} == {
        "VERIFIED",
        "PARTIALLY_VERIFIED",
        "UNVERIFIED",
        "SOURCE_UNAVAILABLE",
        "NOT_APPLICABLE",
    }


def test_no_evidence_is_unverified() -> None:
    assert verify(claim()).status is V.UNVERIFIED


def test_no_evidence_but_an_unavailable_source_is_source_unavailable() -> None:
    v = verify(claim(unavailable=True))
    assert v.status is V.SOURCE_UNAVAILABLE and v.needs


@pytest.mark.parametrize("cls", ["OFFICIAL", "COMMERCIAL"])
def test_one_reliable_source_verifies_a_material_claim(cls: str) -> None:
    assert verify(claim(supporting=(ev(cls),))).status is V.VERIFIED


@pytest.mark.parametrize("cls", ["SECONDARY", "WEAK"])
def test_weak_sources_alone_never_verify_a_material_claim(cls: str) -> None:
    v = verify(claim(supporting=(ev(cls), ev(cls, origin="b.org"), ev(cls, origin="c.org"))))
    assert v.status is V.PARTIALLY_VERIFIED
    assert any("P-06" in r for r in v.reasons)


def test_discovery_only_evidence_cannot_verify_even_if_official() -> None:
    v = verify(claim(supporting=(ev("OFFICIAL", discovery=True, primary=True),)))
    assert v.status is V.PARTIALLY_VERIFIED


def test_weak_plus_one_reliable_is_verified_for_a_normal_material_claim() -> None:
    assert (
        verify(claim(supporting=(ev("WEAK"), ev("OFFICIAL", origin="b.org")))).status is V.VERIFIED
    )


def test_material_adverse_needs_a_definitive_primary_or_two_independent_reliable() -> None:
    one = verify(claim(adverse=True, supporting=(ev("COMMERCIAL"),)))
    assert one.status is V.PARTIALLY_VERIFIED and any("FR-3.7" in n for n in one.needs)

    same_origin = verify(
        claim(adverse=True, supporting=(ev("COMMERCIAL"), ev("OFFICIAL", origin="a.org")))
    )
    assert same_origin.status is V.PARTIALLY_VERIFIED  # not independent

    two = verify(claim(adverse=True, supporting=(ev("COMMERCIAL"), ev("OFFICIAL", origin="b.org"))))
    assert two.status is V.VERIFIED

    primary = verify(claim(adverse=True, supporting=(ev("OFFICIAL", primary=True),)))
    assert primary.status is V.VERIFIED


def test_primary_must_be_official_and_not_discovery() -> None:
    commercial_primary = ev("COMMERCIAL", primary=True)
    assert (
        verify(claim(adverse=True, supporting=(commercial_primary,))).status is V.PARTIALLY_VERIFIED
    )


def test_a_reliable_contradiction_blocks_verified_and_flags_a_conflict() -> None:
    v = verify(claim(supporting=(ev(),), contradicting=(ev(origin="b.org"),)))
    assert v.status is V.PARTIALLY_VERIFIED and v.conflict
    assert any("resolve" in n.lower() for n in v.needs)


def test_a_weak_contradiction_does_not_block_but_a_contradiction_alone_is_unverified() -> None:
    assert verify(claim(supporting=(ev(),), contradicting=(ev("WEAK"),))).status is V.VERIFIED
    alone = verify(claim(contradicting=(ev(origin="b.org"),)))
    assert alone.status is V.UNVERIFIED and alone.conflict


def test_non_material_claims_still_need_a_reliable_source() -> None:
    assert verify(claim(material=False, supporting=(ev("WEAK"),))).status is V.PARTIALLY_VERIFIED
    assert verify(claim(material=False, supporting=(ev(),))).status is V.VERIFIED


@pytest.mark.parametrize("cls", [Classification.INTERPRETATION, Classification.INFERENCE])
def test_judgements_are_not_applicable(cls: Classification) -> None:
    assert verify(claim(classification=cls, supporting=(ev(),))).status is V.NOT_APPLICABLE


def test_a_claim_recorded_as_unverified_cannot_be_marked_verified() -> None:
    v = verify(claim(classification=Classification.UNVERIFIED, supporting=(ev(),)))
    assert v.status is V.PARTIALLY_VERIFIED


def test_verify_is_deterministic() -> None:
    c = claim(adverse=True, supporting=(ev("COMMERCIAL"), ev("OFFICIAL", origin="b.org")))
    assert verify(c) == verify(c)


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        (0, Freshness.CURRENT),
        (90, Freshness.CURRENT),
        (91, Freshness.RECENT),
        (365, Freshness.RECENT),
        (366, Freshness.STALE),
        (1095, Freshness.STALE),
        (1096, Freshness.HISTORICAL),
    ],
)
def test_news_freshness_boundaries(days: int, expected: Freshness) -> None:
    today = date(2026, 10, 11)
    assert (
        freshness(EvidenceType.NEWS, date.fromordinal(today.toordinal() - days), today) == expected
    )


def test_freshness_thresholds_differ_by_evidence_type() -> None:
    today = date(2026, 10, 11)
    old = date.fromordinal(today.toordinal() - 300)
    assert freshness(EvidenceType.FINANCIAL, old, today) is Freshness.CURRENT
    assert freshness(EvidenceType.NEWS, old, today) is Freshness.RECENT
