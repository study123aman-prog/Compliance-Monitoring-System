"""
test_scenarios.py — assert every one of the 20 scenarios produces its locked outcome.

Run with:  pytest -q

These are the acceptance tests: they run each scenario through the real
Orchestrator (same code path as the demo) and check severity, confidence, tier,
mechanism, the set of contributing agents, and the escalation flags against the
`expected` block declared alongside each scenario in src/scenarios.py.
"""
from __future__ import annotations

import pytest

from src.orchestrator import Orchestrator
from src.scenarios import SCENARIOS

_ESCALATION_FLAGS = (
    "transaction_hold", "legal_hook", "board_reporting", "dual_control", "unresolved",
)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["case_id"] for s in SCENARIOS])
def test_scenario_matches_locked_outcome(scenario: dict) -> None:
    exp = scenario["expected"]
    outcome = Orchestrator().process_case(scenario)
    cr, er = outcome.consensus, outcome.escalation

    assert cr.severity.name == exp["severity"]
    assert cr.confidence == pytest.approx(exp["confidence"], abs=0.01)
    assert er.tier.name == exp["tier"]
    assert cr.mechanism == exp["mechanism"]
    assert set(cr.agents) == set(exp["agents"])
    assert cr.suppressed == exp.get("suppressed", False)
    for flag in _ESCALATION_FLAGS:
        assert getattr(er, flag) == exp.get(flag, False), f"{scenario['case_id']}: {flag}"


def test_cs18_is_suppressed_no_alert() -> None:
    """The false-positive trap must end in NO_ALERT / T0 / suppressed — the single
    most important negative-path behaviour in the whole system."""

    outcome = Orchestrator().process_case(next(s for s in SCENARIOS if s["case_id"] == "CS-18"))
    assert outcome.consensus.suppressed is True
    assert outcome.consensus.severity.name == "NO_ALERT"
    assert outcome.escalation.tier.name == "T0"
    assert outcome.consensus.confidence < 0.30


def test_cs19_never_auto_resolved() -> None:
    """A jurisdictional conflict must be flagged unresolved and routed to Legal —
    the machine must not pick a side."""

    outcome = Orchestrator().process_case(next(s for s in SCENARIOS if s["case_id"] == "CS-19"))
    assert outcome.consensus.mechanism == "jurisdictional_bypass"
    assert outcome.escalation.unresolved is True
    assert outcome.escalation.legal_hook is True
    assert outcome.escalation.tier.name == "T4"


def test_all_scenarios_present() -> None:
    """Guard against an accidentally-dropped scenario."""

    ids = {s["case_id"] for s in SCENARIOS}
    assert ids == {f"CS-{n:02d}" for n in range(1, 21)}
