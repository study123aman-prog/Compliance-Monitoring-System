"""
base_agent.py — shared behaviour for the specialist agents.
"""
from __future__ import annotations

from typing import Any

from ..consensus import Opinion
from ..domain import AuditClass, MessageType, PRIORITY, Severity
from ..envelope import Message
from ..message_bus import MessageBus


class BaseAgent:
    """Common plumbing: identity, bus access, and the two things every agent does
    — assess a case into opinions, and emit an ALERT envelope for each opinion."""

    #: human-readable list of the compliance domains this agent is authoritative in
    covered_domains: tuple[str, ...] = ()

    def __init__(self, agent_id: str, bus: MessageBus) -> None:
        self.agent_id = agent_id
        self.bus = bus

    # -- detection -------------------------------------------------------- #
    def assess(self, case: dict[str, Any]) -> list[Opinion]:
        """Return this agent's opinion(s) on a case.

        The scenario data maps agent_id -> opinion spec; we surface ours (if any).
        Report Generator overrides this to return nothing (it does not vote).
        """

        specs = case.get("opinions", {})
        spec = specs.get(self.agent_id)
        if spec is None:
            return []
        return [
            Opinion(
                agent_id=self.agent_id,
                severity=spec["severity"],
                confidence=spec["confidence"],
                domain=spec["domain"],
                benign=spec.get("benign", False),
                evidence_ref=spec.get("evidence_ref", ""),
                weight=spec.get("weight"),
                no_auto_resolve=spec.get("no_auto_resolve", False),
            )
        ]

    # -- messaging -------------------------------------------------------- #
    def emit_alert(self, case: dict[str, Any], opinion: Opinion) -> Message:
        """Publish an ALERT envelope describing one opinion, and return it."""

        msg = Message(
            sender_agent_id=self.agent_id,
            recipient_agent_id="agent.orchestrator",
            message_type=MessageType.ALERT,
            payload_schema="alert.detection.v1",
            payload={
                "violation_type": case.get("violation_type", "unspecified"),
                "severity": opinion.severity.name,
                "domain": opinion.domain.value,
                "evidence_refs": [opinion.evidence_ref] if opinion.evidence_ref else [],
                "benign_verification": opinion.benign,
            },
            correlation_id=case["case_id"],
            priority=PRIORITY.get(opinion.severity, 3),
            confidence_score=round(opinion.confidence, 4),
            audit_classification=AuditClass.REGULATORY,
        )
        self.bus.publish("agent-messages", msg)
        return msg
