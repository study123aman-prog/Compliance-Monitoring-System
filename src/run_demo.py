"""
run_demo.py — run all 20 scenarios end to end and print what happened.

    python -m src.run_demo

It drives every scenario through a single Orchestrator (so the audit trail forms
one continuous hash chain), then shows four things:

  1. a results table with a PASS/FAIL check against the locked expected outcomes,
     now including each case's detection verdict and where it was routed;
  2. a worked example of the two-tier detection core on one signal — the
     deterministic first pass, the agentic evaluator's tool calls, the risk score,
     and the full Chain-of-Thought — to make the "compute, don't replay" path
     visible;
  3. the Human-in-the-Loop review queue the run produced; and
  4. audit-chain verification plus a tamper-evidence demonstration.

No third-party dependencies — standard library only.
"""
from __future__ import annotations

from .detection import DetectionPipeline
from .orchestrator import CaseOutcome, Orchestrator
from .scenarios import SCENARIOS, by_id


# Fields in `expected` that map onto the escalation result (default False if absent).
_ESCALATION_FLAGS = (
    "transaction_hold", "legal_hook", "board_reporting", "dual_control", "unresolved",
)


def check(outcome: CaseOutcome, expected: dict) -> list[str]:
    """Return a list of human-readable mismatches (empty list => everything matched)."""

    problems: list[str] = []
    cr, er = outcome.consensus, outcome.escalation

    if cr.severity.name != expected["severity"]:
        problems.append(f"severity {cr.severity.name}!={expected['severity']}")
    if abs(cr.confidence - expected["confidence"]) > 0.01:
        problems.append(f"confidence {cr.confidence}!={expected['confidence']}")
    if er.tier.name != expected["tier"]:
        problems.append(f"tier {er.tier.name}!={expected['tier']}")
    if "mechanism" in expected and cr.mechanism != expected["mechanism"]:
        problems.append(f"mechanism {cr.mechanism}!={expected['mechanism']}")
    if "agents" in expected and set(cr.agents) != set(expected["agents"]):
        problems.append(f"agents {set(cr.agents)}!={set(expected['agents'])}")
    if cr.suppressed != expected.get("suppressed", False):
        problems.append(f"suppressed {cr.suppressed}!={expected.get('suppressed', False)}")
    for flag in _ESCALATION_FLAGS:
        want = expected.get(flag, False)
        got = getattr(er, flag)
        if got != want:
            problems.append(f"{flag} {got}!={want}")
    return problems


def _verdicts(outcome: CaseOutcome) -> str:
    """Compact per-agent detection verdicts (PASS/FLAGGED/VIOLATION) for a case."""

    labels = {"VIOLATION": "V", "FLAGGED": "F", "PASS": "P"}
    tags = [labels.get(o.verdict, "-") for o in outcome.opinions if not o.benign and o.verdict]
    return "".join(tags) or "-"


def _route(outcome: CaseOutcome) -> str:
    """Where the HITL router sent the case (or how it was auto-dispositioned)."""

    if outcome.review is not None:
        return f"P{outcome.review.priority} {outcome.review.queue}"
    return "auto-cleared" if outcome.consensus.suppressed else "auto-passed"


def _row(case_id: str, outcome: CaseOutcome, ok: bool) -> str:
    cr, er = outcome.consensus, outcome.escalation
    disp = "SUPPRESSED" if cr.suppressed else cr.severity.name
    flag = "OK " if ok else "XX "
    return (f"{flag} {case_id:<6} {disp:<10} c={cr.confidence:<4} {er.tier.name:<3} "
            f"{_verdicts(outcome):<4} {_route(outcome)[:46]}")


def _print_detection_example(case_id: str, agent_id: str) -> None:
    """Show the full two-tier detection output for one signal (transparency)."""

    scenario = by_id(case_id)
    signal = scenario["signals"][agent_id]
    outcome = DetectionPipeline().run(
        correlation_id=case_id, source_agent=agent_id, signal=signal, context=scenario)
    ev = outcome.evaluation

    print("=" * 108)
    print(f"DETECTION CORE — worked example: {case_id} / {agent_id}")
    print("=" * 108)
    print(f"  violation candidate : {outcome.event.violation_candidate}")
    print(f"  normalized event id : {outcome.event.event_id}  (schema {outcome.event.schema_version})")
    print(f"  deterministic pass  : {outcome.guardrails.points} pts from "
          f"{len(outcome.guardrails.hits)} bright-line hit(s)"
          f"{' [HARD STOP]' if outcome.guardrails.hard else ''}")
    print(f"  evaluator tools     :")
    for t in ev.tool_trace:
        print(f"      - {t}")
    print(f"  structured verdict  : {ev.verdict}  score={ev.score}/100  "
          f"confidence={ev.confidence:.2f}  severity={ev.severity.name}")
    print("  chain-of-thought    :")
    for line in ev.rationale:
        print(f"      {line}")
    print()


def _print_hitl_queue(orch: Orchestrator) -> None:
    """Print the human-review queue the run produced, most urgent first."""

    print("=" * 108)
    print("HUMAN-IN-THE-LOOP — review queue produced by this run")
    print("=" * 108)
    print(f"  {'case':<6} {'pri':<4} {'tier':<4} {'severity':<9} {'conf':<6} queue / reasons")
    print("-" * 108)
    for it in orch.hitl.pending():
        print(f"  {it.case_id:<6} P{it.priority:<3} {it.tier:<4} {it.severity:<9} "
              f"{it.confidence:<6} {it.queue}")
        print(f"         reasons: {'; '.join(it.reasons)}")
    print("-" * 108)
    print(f"  {orch.hitl.summary()}")
    print()


def main() -> int:
    orch = Orchestrator()

    print("=" * 108)
    print("MULTI-AGENT COMPLIANCE MONITORING SYSTEM — reference demo (all 20 scenarios)")
    print("=" * 108)
    print("  opinions are COMPUTED from raw signals by the two-tier detection core "
          "(normalize -> guardrails -> evaluator);")
    print("  verdict column: V=VIOLATION F=FLAGGED P=PASS per voting agent.")
    print("-" * 108)
    print(f"    {'case':<6} {'disposition':<10} {'conf':<6} {'tier':<4} {'vd':<4} routed to")
    print("-" * 108)

    failures = 0
    for scenario in SCENARIOS:
        outcome = orch.process_case(scenario)
        problems = check(outcome, scenario["expected"])
        ok = not problems
        failures += 0 if ok else 1
        print(_row(scenario["case_id"], outcome, ok))
        if problems:
            print(f"        -> MISMATCH: {'; '.join(problems)}")

    print("-" * 108)
    print(f"scenario results: {len(SCENARIOS) - failures}/{len(SCENARIOS)} matched the locked expected outcomes")
    print()

    # ---- Worked detection example + the HITL queue this run produced. ----
    _print_detection_example("CS-01", "agent.transaction_monitor")
    _print_hitl_queue(orch)

    # ---- Audit chain: verify, then demonstrate tamper-evidence. ----
    print("=" * 108)
    print("AUDIT TRAIL — tamper-evidence demonstration")
    print("=" * 108)
    entries = orch.audit.entries
    print(f"total audit entries written across all cases: {len(entries)}")

    ok, msg = orch.audit.verify()
    print(f"1) verify intact chain      -> {ok}  ({msg})")

    # Tamper: reach into the internal list and silently alter one entry's details.
    victim = len(entries) // 2
    original = orch.audit._entries[victim].details
    orch.audit._entries[victim].details = {**original, "confidence": 0.01}
    ok_bad, msg_bad = orch.audit.verify()
    print(f"2) after altering entry #{victim:<3} -> {ok_bad}  ({msg_bad})")

    # Restore and re-verify to show the check is not a fluke.
    orch.audit._entries[victim].details = original
    ok_fixed, msg_fixed = orch.audit.verify()
    print(f"3) after restoring entry    -> {ok_fixed}  ({msg_fixed})")

    print("\n" + "=" * 108)
    verdict = "ALL CHECKS PASSED" if failures == 0 and ok and not ok_bad and ok_fixed else "CHECK FAILED"
    print(verdict)
    print("=" * 108)
    return 0 if verdict == "ALL CHECKS PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
