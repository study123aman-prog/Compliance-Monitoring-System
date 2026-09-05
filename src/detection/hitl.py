"""
hitl.py — Human-in-the-Loop routing (detection stage 4).

Automation decides; humans stay accountable. This module enforces that: after a
case has been through consensus and escalation, `HITLQueue.route()` decides
whether a human reviewer must see it, and if so, puts it in the right queue at the
right priority with the right SLA.

Routing policy (straight from the brief: "route high-risk OR low-confidence"):

  * HIGH-RISK      — tier T3/T4, or any special obligation attached
                     (transaction hold, dual control, board reporting, legal, or
                     an unresolved conflict). These always get a human.
  * LOW-CONFIDENCE — a non-suppressed case whose confidence sits in the ambiguous
                     FLAGGED band (0.30–0.75), or any agent returned FLAGGED.
                     The machine is unsure, so a human decides.

  * AUTO-CLEARED   — a suppressed false positive (the CS-18 trap) is NOT queued;
                     it was cleared by an authenticated verification and the whole
                     computation is in the audit trail. (Silent-drop is avoided:
                     it is *recorded* as auto-cleared, just not sent to a human.)
  * AUTO-PASS      — genuinely low-risk, high-nothing cases need no human.

The queue is deliberately simple (an in-memory list) — the point is the routing
*logic*, which is the compliance-critical part.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..domain import Severity, Tier
from .evaluator import FLAGGED

# Confidence window (inclusive-exclusive) that counts as "unsure enough for a human".
_LOW_CONF_FLOOR = 0.30
_LOW_CONF_CEIL = 0.75


@dataclass
class ReviewItem:
    """One case queued for human review."""

    case_id: str
    priority: int                 # 1 (highest) .. 5 (lowest)
    tier: str
    severity: str
    confidence: float
    queue: str                    # which human team/role owns it
    reasons: list[str]            # why it was routed
    sla_ack_minutes: int
    sla_resolve: str
    hard: bool = False            # a bright-line guardrail fired somewhere on the case


@dataclass
class HITLQueue:
    """Routes cases to human reviewers and remembers the routing decisions."""

    _items: list[ReviewItem] = field(default_factory=list)
    auto_cleared: list[str] = field(default_factory=list)   # suppressed false positives
    auto_passed: list[str] = field(default_factory=list)    # low-risk, no human needed

    # ------------------------------------------------------------------ #
    def route(self, case_id: str, consensus: Any, escalation: Any,
              opinions: list[Any] | None = None) -> ReviewItem | None:
        """Decide whether `case_id` needs a human; enqueue and return the item if so.

        `consensus` and `escalation` are duck-typed (ConsensusResult /
        EscalationResult) so this module stays decoupled from those classes.
        """

        opinions = opinions or []

        # An authenticated benign verification already cleared this — record but
        # do not send to a human.
        if getattr(consensus, "suppressed", False):
            self.auto_cleared.append(case_id)
            return None

        tier = escalation.tier
        tier_val = int(tier) if isinstance(tier, Tier) else int(getattr(tier, "value", 0))
        tier_name = tier.name if isinstance(tier, Tier) else str(tier)
        conf = float(getattr(consensus, "confidence", 0.0))
        sev = getattr(consensus, "severity", Severity.NO_ALERT)
        sev_name = sev.name if isinstance(sev, Severity) else str(sev)

        reasons: list[str] = []

        # ---- high-risk triggers ----
        if tier_val >= int(Tier.T3):
            reasons.append(f"high-risk tier {tier_name}")
        for flag, label in (
            ("transaction_hold", "transaction hold in force"),
            ("dual_control", "dual-control (SAR) required"),
            ("board_reporting", "board reporting required"),
            ("legal_hook", "legal review required"),
            ("unresolved", "unresolved — machine must not decide"),
        ):
            if getattr(escalation, flag, False):
                reasons.append(label)

        # ---- low-confidence triggers ----
        if _LOW_CONF_FLOOR <= conf < _LOW_CONF_CEIL:
            reasons.append(f"low-confidence ({conf:.2f}) in the ambiguous band")
        flagged = [getattr(o, "agent_id", "?") for o in opinions
                   if getattr(o, "verdict", "") == FLAGGED and not getattr(o, "benign", False)]
        if flagged:
            reasons.append("agent verdict FLAGGED: " + ", ".join(sorted(flagged)))

        if not reasons:
            self.auto_passed.append(case_id)
            return None

        item = ReviewItem(
            case_id=case_id,
            priority=self._priority(tier_val),
            tier=tier_name,
            severity=sev_name,
            confidence=conf,
            queue=self._assign_queue(escalation, sev_name),
            reasons=reasons,
            sla_ack_minutes=int(getattr(escalation, "ack_minutes", 0)),
            sla_resolve=str(getattr(escalation, "resolve_target", "")),
            hard=any(getattr(o, "verdict", "") == FLAGGED or getattr(o, "risk_score", 0) >= 75
                     for o in opinions),
        )
        self._items.append(item)
        return item

    # ------------------------------------------------------------------ #
    @staticmethod
    def _priority(tier_val: int) -> int:
        """T4 -> 1 (most urgent) ... T0 -> 5."""

        return max(1, min(5, 5 - tier_val))

    @staticmethod
    def _assign_queue(escalation: Any, severity_name: str) -> str:
        """Pick the human team based on the obligations and severity."""

        if getattr(escalation, "legal_hook", False) or getattr(escalation, "unresolved", False):
            return "Legal & Compliance Review Board"
        if getattr(escalation, "board_reporting", False):
            return "Board Risk Committee"
        if getattr(escalation, "transaction_hold", False) or severity_name == "CRITICAL":
            return "Senior Compliance Officer (Tier-1)"
        if severity_name == "HIGH":
            return "Compliance Analyst (Tier-2)"
        return "Compliance Analyst (Tier-3)"

    # ------------------------------------------------------------------ #
    def pending(self) -> list[ReviewItem]:
        """Queued items, most urgent first (stable within a priority)."""

        return sorted(self._items, key=lambda it: it.priority)

    def __len__(self) -> int:
        return len(self._items)

    def summary(self) -> str:
        return (f"{len(self._items)} queued for human review, "
                f"{len(self.auto_cleared)} auto-cleared (suppressed), "
                f"{len(self.auto_passed)} auto-passed")
