"""
run_demo.py — run all 20 scenarios end to end and print what happened.

    python -m src.run_demo

It drives every scenario through a single Orchestrator (so the audit trail forms
one continuous hash chain), prints a results table with a PASS/FAIL check against
the locked expected outcomes, then:
  1. verifies the whole audit chain, and
  2. demonstrates tamper-evidence by mutating one entry and re-verifying.

No third-party dependencies — standard library only.
"""
from __future__ import annotations

from .orchestrator import CaseOutcome, Orchestrator
from .scenarios import SCENARIOS


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


def _row(case_id: str, title: str, outcome: CaseOutcome, ok: bool) -> str:
    cr, er = outcome.consensus, outcome.escalation
    disp = "SUPPRESSED" if cr.suppressed else cr.severity.name
    flag = "OK " if ok else "XX "
    return (f"{flag} {case_id:<6} {disp:<10} c={cr.confidence:<4} {er.tier.name:<3} "
            f"{cr.mechanism:<28} {title[:44]}")


def main() -> int:
    orch = Orchestrator()

    print("=" * 108)
    print("MULTI-AGENT COMPLIANCE MONITORING SYSTEM — reference demo (all 20 scenarios)")
    print("=" * 108)
    print(f"    {'case':<6} {'disposition':<10} {'conf':<6} {'tier':<4} {'mechanism':<28} title")
    print("-" * 108)

    failures = 0
    for scenario in SCENARIOS:
        outcome = orch.process_case(scenario)
        problems = check(outcome, scenario["expected"])
        ok = not problems
        failures += 0 if ok else 1
        print(_row(scenario["case_id"], scenario["title"], outcome, ok))
        if problems:
            print(f"        -> MISMATCH: {'; '.join(problems)}")

    print("-" * 108)
    print(f"scenario results: {len(SCENARIOS) - failures}/{len(SCENARIOS)} matched the locked expected outcomes")

    # ---- Audit chain: verify, then demonstrate tamper-evidence. ----
    print("\n" + "=" * 108)
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
