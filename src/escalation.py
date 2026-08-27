"""
escalation.py — turns a consensus result into a human-routing decision.

Implements the tier rule from ../docs/escalation/escalation-framework.md:

    tier = max(confidence_band_tier, severity_floor_tier)

then *special triggers* may only RAISE the tier and attach hooks (Legal, Board),
never lower it. Also assigns the SLA (acknowledge / resolve) by severity.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .consensus import ConsensusResult
from .domain import (
    Severity,
    Tier,
    SLA,
    severity_floor_tier,
    confidence_band_tier,
)


@dataclass
class EscalationResult:
    """The routing decision for one case."""

    tier: Tier
    severity: Severity
    ack_minutes: int
    resolve_target: str
    suppressed: bool = False
    transaction_hold: bool = False
    legal_hook: bool = False
    board_reporting: bool = False
    dual_control: bool = False
    unresolved: bool = False
    triggers: list[str] = field(default_factory=list)


# Special triggers that can only raise the response. Each scenario declares any
# that apply (e.g. CS-09 sanctions hold, CS-19 jurisdictional, CS-20 override+SAR).
KNOWN_TRIGGERS = {
    "sanctions_aml",         # -> transaction hold + force >= T4
    "jurisdictional_c5",     # -> force T4 + Legal, and mark unresolved (never auto-resolve)
    "control_override_c7",   # -> conduct investigation, force >= T4
    "sar_filing",            # -> dual control on filing
    "critical_downgrade",    # -> dual control to downgrade a CRITICAL
    "board_level",           # -> board reporting hook above T4
}


class EscalationManager:
    """Deterministic mapping from (consensus result, triggers) to an EscalationResult."""

    def decide(self, cr: ConsensusResult, triggers: list[str] | None = None) -> EscalationResult:
        triggers = list(triggers or [])

        # --- Suppressed cases: T0, no human, done (CS-18). ---
        if cr.suppressed:
            return EscalationResult(
                tier=Tier.T0,
                severity=cr.severity,
                ack_minutes=0,
                resolve_target="n/a (suppressed)",
                suppressed=True,
                triggers=triggers,
            )

        # --- Base tier: the max() rule. ---
        base = max(confidence_band_tier(cr.confidence), severity_floor_tier(cr.severity))
        tier = base

        res = EscalationResult(
            tier=tier,
            severity=cr.severity,
            ack_minutes=SLA[cr.severity][0],
            resolve_target=SLA[cr.severity][1],
            unresolved=cr.unresolved,
            triggers=triggers,
        )

        # --- Apply special triggers (raise-only). ---
        if "sanctions_aml" in triggers:
            res.transaction_hold = True
            tier = max(tier, Tier.T4)
        if "control_override_c7" in triggers:
            tier = max(tier, Tier.T4)
        if "sar_filing" in triggers:
            res.dual_control = True
            tier = max(tier, Tier.T4)
        if "critical_downgrade" in triggers:
            res.dual_control = True
        if "jurisdictional_c5" in triggers:
            # Never auto-resolved: force top tier + Legal, mark unresolved.
            tier = Tier.T4
            res.legal_hook = True
            res.unresolved = True
        if "board_level" in triggers:
            tier = max(tier, Tier.T4)
            res.board_reporting = True

        res.tier = tier
        return res
