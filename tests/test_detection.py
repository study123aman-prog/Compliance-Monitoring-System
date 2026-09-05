"""
test_detection.py — tests for the two-tier detection core (src/detection).

Run with:  pytest -q          (or the repo's offline shim runner)

Two kinds of test live here:

  1. REPRODUCTION — the whole point of the detection core is that agents now
     COMPUTE their opinions from raw evidence instead of replaying a pre-set
     value, yet still land on exactly the locked outcomes. So for every agent
     signal in every scenario we run the pipeline and assert the computed
     severity / confidence / domain equal the scenario's recorded opinion. If a
     scenario's indicator points are ever mis-authored, this test fails loudly.

  2. UNIT — each stage (normalize, guardrails, evaluator, HITL) is exercised in
     isolation so the behaviour of the parts is pinned independently of the
     scenarios.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.detection import (
    ComplianceEvaluator,
    DeterministicBackend,
    DetectionPipeline,
    GuardrailEngine,
    HITLQueue,
    LLMBackend,
    PolicyStore,
    normalize,
    FLAGGED,
    PASS,
    VIOLATION,
)
from src.detection.evaluator import LLMBackendUnavailable, verdict_for_score
from src.detection.guardrails import GuardrailResult
from src.domain import AGENT_CS, AGENT_TM, Domain, Severity, Tier
from src.scenarios import SCENARIOS


# --------------------------------------------------------------------------- #
#  1) REPRODUCTION: computed opinion == locked opinion, for every signal.
# --------------------------------------------------------------------------- #
_REPRO = [
    (s["case_id"], aid, sig, s, s["opinions"][aid])
    for s in SCENARIOS
    for aid, sig in s.get("signals", {}).items()
]
_REPRO_IDS = [f"{cid}:{aid.split('.')[-1]}" for cid, aid, _, _, _ in _REPRO]


@pytest.mark.parametrize("case", _REPRO, ids=_REPRO_IDS)
def test_computed_opinion_reproduces_locked_opinion(case) -> None:
    """The pipeline's computed verdict must match the scenario's recorded opinion."""

    case_id, agent_id, signal, scenario, preset = case
    outcome = DetectionPipeline().run(
        correlation_id=case_id, source_agent=agent_id, signal=signal, context=scenario)
    ev = outcome.evaluation

    assert outcome.event.domain == preset["domain"], f"{case_id}/{agent_id} domain"
    assert ev.severity == preset["severity"], f"{case_id}/{agent_id} severity"
    assert ev.confidence == pytest.approx(preset["confidence"], abs=0.005), \
        f"{case_id}/{agent_id} confidence {ev.confidence} != {preset['confidence']}"
    # confidence and the integer score are two views of the same number.
    assert ev.confidence == pytest.approx(ev.score / 100.0, abs=1e-9)
    # verdict must be consistent with the score bands.
    assert ev.verdict == verdict_for_score(ev.score)


def test_all_signals_have_a_matching_locked_opinion() -> None:
    """Guard against a scenario that declares a signal but no reproduction target."""

    for s in SCENARIOS:
        for aid in s.get("signals", {}):
            assert aid in s["opinions"], f"{s['case_id']} signal {aid} has no opinion to match"


def test_no_auto_resolve_signal_propagates_to_opinion() -> None:
    """CS-19's jurisdictional signal must carry no_auto_resolve through to the result."""

    s = next(s for s in SCENARIOS if s["case_id"] == "CS-19")
    outcome = DetectionPipeline().run(
        "CS-19", "agent.regulatory_tracker",
        s["signals"]["agent.regulatory_tracker"], context=s)
    assert outcome.evaluation.no_auto_resolve is True


# --------------------------------------------------------------------------- #
#  2a) UNIT — normalization.
# --------------------------------------------------------------------------- #
def _signal(**over):
    base = {"violation_type": "spoofing", "domain": Domain.TRADING,
            "raw": {"cancel_ratio": 0.97}, "indicators": []}
    base.update(over)
    return base


def test_normalize_builds_a_unified_payload() -> None:
    ev = normalize("CS-XX", AGENT_TM, _signal(evidence_ref="blotter:42"))
    assert ev.correlation_id == "CS-XX"
    assert ev.source_agent == AGENT_TM
    assert ev.domain == Domain.TRADING
    assert ev.violation_candidate == "spoofing"
    assert ev.evidence_ref == "blotter:42"
    assert ev.event_id == "CS-XX:agent.transaction_monitor"
    assert ev.feature("cancel_ratio") == 0.97
    payload = ev.audit_payload()
    assert payload["schema_version"] == ev.schema_version
    assert "observed_at" not in payload           # excluded from anything feeding scoring
    assert payload["features"] == {"cancel_ratio": 0.97}


def test_normalize_infers_event_type_from_agent() -> None:
    assert normalize("C", AGENT_TM, _signal()).event_type == "transaction"
    assert normalize("C", AGENT_CS, _signal(domain=Domain.COMMUNICATIONS)).event_type == "communication"


def test_normalize_requires_violation_type_and_domain() -> None:
    with pytest.raises(ValueError):
        normalize("C", AGENT_TM, {"domain": Domain.TRADING, "raw": {}})
    with pytest.raises(ValueError):
        normalize("C", AGENT_TM, {"violation_type": "spoofing", "raw": {}})


def test_normalize_accepts_string_domain() -> None:
    ev = normalize("C", AGENT_TM, {"violation_type": "spoofing", "domain": "trading", "raw": {}})
    assert ev.domain == Domain.TRADING


# --------------------------------------------------------------------------- #
#  2b) UNIT — deterministic guardrails.
# --------------------------------------------------------------------------- #
def _run_guardrails(raw, indicators):
    ev = normalize("C", AGENT_TM, {"violation_type": "x", "domain": Domain.TRADING, "raw": raw})
    return GuardrailEngine().first_pass(ev, indicators)


def test_guardrail_hard_hit_fires_counts_points_and_flags_hard() -> None:
    res = _run_guardrails(
        {"counterparty": "Garnet Trading FZCO"},
        [{"id": "sanc", "tier": "deterministic", "check": "on_sanctions_list",
          "points": 45, "hard": True}])
    assert res.points == 45
    assert res.hard is True
    assert res.hits[0].rule_id == "sanc"


def test_guardrail_miss_is_recorded_not_scored() -> None:
    res = _run_guardrails(
        {"counterparty": "Clean Counterparty Ltd"},
        [{"id": "sanc", "tier": "deterministic", "check": "on_sanctions_list",
          "points": 45, "hard": True}])
    assert res.points == 0
    assert res.hard is False
    assert "sanc" in res.misses


def test_guardrail_all_below_detects_structuring() -> None:
    res = _run_guardrails(
        {"deposits": [9500, 9200, 9800]},
        [{"id": "struct", "tier": "deterministic", "check": "all_below",
          "field": "deposits", "value": 10000, "points": 40}])
    assert res.points == 40


def test_guardrail_regex_is_case_insensitive() -> None:
    res = _run_guardrails(
        {"text": "GUARANTEED returns"},
        [{"id": "mkt", "tier": "deterministic", "check": "regex",
          "field": "text", "pattern": r"guaranteed", "points": 40}])
    assert res.points == 40


def test_guardrail_ignores_agentic_indicators() -> None:
    res = _run_guardrails({"x": 1}, [{"id": "ag", "tier": "agentic", "points": 30}])
    assert res.hits == [] and res.misses == []


def test_guardrail_unknown_check_raises() -> None:
    with pytest.raises(KeyError):
        _run_guardrails({"x": 1}, [{"id": "bad", "tier": "deterministic",
                                    "check": "no_such_check", "points": 1}])


# --------------------------------------------------------------------------- #
#  2c) UNIT — the agentic evaluator.
# --------------------------------------------------------------------------- #
def test_verdict_bands_are_at_30_and_75() -> None:
    assert verdict_for_score(29) == PASS
    assert verdict_for_score(30) == FLAGGED
    assert verdict_for_score(74) == FLAGGED
    assert verdict_for_score(75) == VIOLATION


def test_score_is_guardrail_plus_agentic_and_confidence_is_over_100() -> None:
    signal = {"violation_type": "spoofing", "domain": Domain.TRADING,
              "raw": {"cancel_ratio": 0.97},
              "indicators": [
                  {"id": "d", "tier": "deterministic", "check": "gt",
                   "field": "cancel_ratio", "value": 0.90, "points": 30},
                  {"id": "a", "tier": "agentic", "points": 30}]}
    ev = DetectionPipeline().run("C", AGENT_TM, signal).evaluation
    assert ev.score == 60
    assert ev.confidence == pytest.approx(0.60)
    assert ev.verdict == FLAGGED
    assert ev.severity == Severity.HIGH           # from the policy table for spoofing


def test_score_is_clamped_to_100() -> None:
    signal = {"violation_type": "structuring", "domain": Domain.SANCTIONS_AML,
              "raw": {}, "indicators": [{"id": "a", "tier": "agentic", "points": 250}]}
    ev = DetectionPipeline().run("C", AGENT_TM, signal).evaluation
    assert ev.score == 100 and ev.confidence == 1.0


def test_policy_lookup_maps_severity() -> None:
    store = PolicyStore()
    assert store.lookup("structuring").severity == Severity.CRITICAL
    assert store.lookup("spoofing").severity == Severity.HIGH
    assert store.lookup("regulatory_change").severity == Severity.MEDIUM
    assert store.lookup("totally_unknown").severity == Severity.MEDIUM   # conservative default


def test_evaluator_records_tool_trace() -> None:
    signal = {"violation_type": "spoofing", "domain": Domain.TRADING,
              "raw": {}, "indicators": []}
    ev = DetectionPipeline().run("C", AGENT_TM, signal).evaluation
    assert any("policy.lookup" in t for t in ev.tool_trace)
    assert any("context.inspect" in t for t in ev.tool_trace)


def test_default_backend_is_deterministic() -> None:
    assert ComplianceEvaluator().backend.name == "deterministic"
    assert isinstance(ComplianceEvaluator().backend, DeterministicBackend)


def test_llm_backend_is_inert_without_a_client() -> None:
    """The LLM path must never run on the default (offline/reproducible) path."""

    backend = LLMBackend()
    ev = normalize("C", AGENT_TM, {"violation_type": "spoofing",
                                   "domain": Domain.TRADING, "raw": {}})
    with pytest.raises(LLMBackendUnavailable):
        backend.score_context(ev, GuardrailResult(), [], PolicyStore().lookup("spoofing"), {})


def test_llm_backend_builds_a_structured_prompt() -> None:
    backend = LLMBackend()
    ev = normalize("C", AGENT_TM, {"violation_type": "spoofing",
                                   "domain": Domain.TRADING, "raw": {}})
    prompt = backend.build_prompt(ev, GuardrailResult(), PolicyStore().lookup("spoofing"))
    assert "STRICT JSON" in prompt and "PASS|FLAGGED|VIOLATION" in prompt


# --------------------------------------------------------------------------- #
#  2d) UNIT — HITL routing.
# --------------------------------------------------------------------------- #
def _consensus(severity=Severity.HIGH, confidence=0.8, suppressed=False):
    return SimpleNamespace(severity=severity, confidence=confidence, suppressed=suppressed)


def _escalation(tier=Tier.T3, **flags):
    base = dict(transaction_hold=False, dual_control=False, board_reporting=False,
                legal_hook=False, unresolved=False, ack_minutes=60, resolve_target="24h")
    base.update(flags)
    return SimpleNamespace(tier=tier, **base)


def test_hitl_suppressed_case_is_auto_cleared_not_queued() -> None:
    q = HITLQueue()
    item = q.route("CS-18", _consensus(Severity.NO_ALERT, 0.26, suppressed=True),
                   _escalation(Tier.T0))
    assert item is None
    assert "CS-18" in q.auto_cleared
    assert len(q) == 0


def test_hitl_high_tier_is_routed_to_a_human() -> None:
    q = HITLQueue()
    item = q.route("CS-10", _consensus(Severity.CRITICAL, 0.87), _escalation(Tier.T4))
    assert item is not None
    assert item.priority == 1                              # T4 -> most urgent
    assert item.queue == "Senior Compliance Officer (Tier-1)"


def test_hitl_low_confidence_is_routed_even_at_low_tier() -> None:
    q = HITLQueue()
    item = q.route("CS-07", _consensus(Severity.MEDIUM, 0.70), _escalation(Tier.T2))
    assert item is not None
    assert any("low-confidence" in r for r in item.reasons)


def test_hitl_low_risk_high_confidence_is_auto_passed() -> None:
    q = HITLQueue()
    # T1, confidence outside the ambiguous band, no obligations, no flagged opinions.
    item = q.route("CS-CLEAN", _consensus(Severity.LOW, 0.99), _escalation(Tier.T1))
    assert item is None
    assert "CS-CLEAN" in q.auto_passed


def test_hitl_legal_hook_routes_to_legal_board() -> None:
    q = HITLQueue()
    item = q.route("CS-19", _consensus(Severity.HIGH, 0.90),
                   _escalation(Tier.T4, legal_hook=True, unresolved=True))
    assert item.queue == "Legal & Compliance Review Board"
    assert any("legal" in r for r in item.reasons)


def test_hitl_board_reporting_routes_to_board_committee() -> None:
    q = HITLQueue()
    item = q.route("CS-20", _consensus(Severity.CRITICAL, 0.95),
                   _escalation(Tier.T4, board_reporting=True))
    assert item.queue == "Board Risk Committee"


def test_hitl_flagged_opinion_forces_review() -> None:
    q = HITLQueue()
    flagged = SimpleNamespace(agent_id=AGENT_TM, verdict=FLAGGED, benign=False, risk_score=60)
    item = q.route("CS-X", _consensus(Severity.HIGH, 0.99), _escalation(Tier.T1),
                   opinions=[flagged])
    assert item is not None
    assert any("FLAGGED" in r for r in item.reasons)


def test_hitl_pending_is_sorted_by_priority() -> None:
    q = HITLQueue()
    q.route("A", _consensus(Severity.HIGH, 0.85), _escalation(Tier.T3))     # priority 2
    q.route("B", _consensus(Severity.CRITICAL, 0.9), _escalation(Tier.T4))  # priority 1
    order = [it.case_id for it in q.pending()]
    assert order == ["B", "A"]
