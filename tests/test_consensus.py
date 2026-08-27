"""
test_consensus.py — unit tests on the consensus math itself.

Run with:  pytest -q

These test the Dempster-Shafer combination rule, the corroboration (agreement)
path, the false-positive suppression path, and the genuine-conflict path in
isolation from the orchestrator, so the numbers in
../docs/conflict-resolution/consensus-algorithm.md are pinned by code.
"""
from __future__ import annotations

import pytest

from src.consensus import ConsensusEngine, Opinion, combine
from src.domain import AGENT_CS, AGENT_RU, AGENT_TM, Domain, Severity


# --------------------------------------------------------------------------- #
#  The combination rule.
# --------------------------------------------------------------------------- #
def test_combine_agreement_uses_or_formula() -> None:
    """Two agreeing V-masses with no benign mass => K=0 and
    Belief(V) = m1 + m2 - m1*m2 (probabilistic OR)."""

    m1 = {"V": 0.684, "B": 0.0, "T": 0.316}   # TM: 0.95 * 0.72
    m2 = {"V": 0.760, "B": 0.0, "T": 0.240}   # CS: 0.95 * 0.80
    combined, k = combine(m1, m2)
    assert k == pytest.approx(0.0, abs=1e-9)
    assert combined["V"] == pytest.approx(0.684 + 0.760 - 0.684 * 0.760, abs=1e-6)
    assert combined["V"] == pytest.approx(0.924, abs=0.005)


def test_combine_masses_sum_to_one() -> None:
    m1 = {"V": 0.5, "B": 0.0, "T": 0.5}
    m2 = {"V": 0.0, "B": 0.4, "T": 0.6}
    combined, _ = combine(m1, m2)
    assert sum(combined.values()) == pytest.approx(1.0, abs=1e-9)


def test_combine_conflict_when_v_meets_b() -> None:
    """V and B are disjoint, so their product is conflict mass K."""

    m1 = {"V": 0.646, "B": 0.0, "T": 0.354}   # TM in CS-18
    m2 = {"V": 0.0, "B": 0.810, "T": 0.190}   # authenticated benign verifier
    combined, k = combine(m1, m2)
    assert k == pytest.approx(0.646 * 0.810, abs=1e-6)     # 0.52326
    assert combined["V"] == pytest.approx(0.2575, abs=0.005)
    assert combined["B"] > combined["V"]                   # benign dominates


def test_combine_is_commutative() -> None:
    m1 = {"V": 0.6, "B": 0.0, "T": 0.4}
    m2 = {"V": 0.0, "B": 0.3, "T": 0.7}
    a, _ = combine(m1, m2)
    b, _ = combine(m2, m1)
    assert a == pytest.approx(b)


# --------------------------------------------------------------------------- #
#  Engine paths.
# --------------------------------------------------------------------------- #
def test_single_opinion_passthrough_keeps_confidence() -> None:
    eng = ConsensusEngine()
    res = eng.resolve([Opinion(AGENT_TM, Severity.HIGH, 0.85, Domain.TRADING)])
    assert res.mechanism == "passthrough"
    assert res.confidence == 0.85
    assert res.severity == Severity.HIGH


def test_corroboration_raises_confidence_and_can_elevate_severity() -> None:
    """Two HIGH opinions corroborating to >=0.90 elevate the case to CRITICAL."""

    eng = ConsensusEngine()
    res = eng.resolve([
        Opinion(AGENT_TM, Severity.HIGH, 0.72, Domain.TRADING),
        Opinion(AGENT_CS, Severity.HIGH, 0.80, Domain.COMMUNICATIONS),
    ])
    assert res.mechanism == "dempster_shafer"
    assert res.confidence == pytest.approx(0.92, abs=0.01)
    assert res.severity == Severity.CRITICAL          # band elevation, raise-only


def test_corroboration_never_lowers_asserted_severity() -> None:
    """A CRITICAL assertion stays CRITICAL even if belief lands in a lower band."""

    eng = ConsensusEngine()
    res = eng.resolve([
        Opinion(AGENT_TM, Severity.CRITICAL, 0.82, Domain.SANCTIONS_AML),
        Opinion(AGENT_RU, Severity.CRITICAL, 0.92, Domain.SANCTIONS_AML),
    ])
    assert res.severity == Severity.CRITICAL
    assert res.confidence == pytest.approx(0.87, abs=0.01)


def test_suppression_when_benign_dominates() -> None:
    eng = ConsensusEngine()
    res = eng.resolve([
        Opinion(AGENT_TM, Severity.HIGH, 0.68, Domain.TRADING),
        Opinion("service.verification", Severity.NO_ALERT, 0.90,
                Domain.TRADING, benign=True, weight=0.90),
    ])
    assert res.suppressed is True
    assert res.severity == Severity.NO_ALERT
    assert res.confidence < 0.30


def test_weak_benign_does_not_suppress_strong_signal() -> None:
    """A low-confidence benign claim must NOT clear a strong violation signal."""

    eng = ConsensusEngine()
    res = eng.resolve([
        Opinion(AGENT_TM, Severity.CRITICAL, 0.95, Domain.TRADING),
        Opinion("service.verification", Severity.NO_ALERT, 0.20,
                Domain.TRADING, benign=True, weight=0.20),
    ])
    assert res.suppressed is False


def test_jurisdictional_bypass_is_unresolved_and_not_elevated() -> None:
    """no_auto_resolve => asserted severity/confidence returned verbatim, unresolved."""

    eng = ConsensusEngine()
    res = eng.resolve([
        Opinion(AGENT_RU, Severity.HIGH, 0.90, Domain.REGULATORY, no_auto_resolve=True),
    ])
    assert res.mechanism == "jurisdictional_bypass"
    assert res.unresolved is True
    assert res.severity == Severity.HIGH          # NOT elevated to CRITICAL by the 0.90 band
    assert res.confidence == 0.90


def test_genuine_conflict_is_flagged_unresolved_at_higher_tier() -> None:
    """Severities differing by >1 level with no clear winner => unresolved, and the
    safe default is the HIGHER severity."""

    eng = ConsensusEngine()
    res = eng.resolve([
        Opinion(AGENT_TM, Severity.CRITICAL, 0.55, Domain.TRADING),
        Opinion(AGENT_CS, Severity.LOW, 0.55, Domain.COMMUNICATIONS),
    ])
    assert res.unresolved is True
    assert res.severity == Severity.CRITICAL


def test_empty_opinions_raises() -> None:
    with pytest.raises(ValueError):
        ConsensusEngine().resolve([])
