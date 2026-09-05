"""
base_agent.py — shared behaviour for the specialist agents.
"""
from __future__ import annotations

from typing import Any

from ..consensus import Opinion
from ..detection import DetectionPipeline, DEFAULT_PIPELINE
from ..domain import AuditClass, MessageType, PRIORITY, Severity
from ..envelope import Message
from ..message_bus import MessageBus


class BaseAgent:
    """Common plumbing: identity, bus access, and the two things every agent does
    — assess a case into opinions, and emit an ALERT envelope for each opinion."""

    #: human-readable list of the compliance domains this agent is authoritative in
    covered_domains: tuple[str, ...] = ()

    def __init__(self, agent_id: str, bus: MessageBus,
                 pipeline: DetectionPipeline | None = None) -> None:
        self.agent_id = agent_id
        self.bus = bus
        #: the two-tier detection core used to COMPUTE opinions from raw signals.
        self.pipeline = pipeline or DEFAULT_PIPELINE

    # -- detection -------------------------------------------------------- #
    def assess(self, case: dict[str, Any]) -> list[Opinion]:
        """Return this agent's opinion(s) on a case.

        Two paths:
          1. COMPUTED — if the case carries a raw `signals[agent_id]` block, the
             agent runs it through the detection pipeline (normalize -> guardrails
             -> evaluator) and forms its opinion from what it actually finds. This
             is the real detection path.
          2. FALLBACK — if only a pre-set `opinions[agent_id]` spec is present
             (no raw signal), that spec is surfaced verbatim. This keeps older
             cases and unit fixtures working unchanged.

        Report Generator overrides this to return nothing (it does not vote).
        """

        signal = case.get("signals", {}).get(self.agent_id)
        if signal is not None:
            return [self._computed_opinion(case, signal)]
        return self._preset_opinion(case)

    def _computed_opinion(self, case: dict[str, Any], signal: dict[str, Any]) -> Opinion:
        """Run the detection pipeline and turn its verdict into a consensus Opinion."""

        outcome = self.pipeline.run(
            correlation_id=case["case_id"],
            source_agent=self.agent_id,
            signal=signal,
            context=case,
        )
        ev = outcome.evaluation
        return Opinion(
            agent_id=self.agent_id,
            severity=ev.severity,
            confidence=ev.confidence,
            domain=outcome.event.domain,
            evidence_ref=ev.evidence_ref,
            no_auto_resolve=ev.no_auto_resolve,
            verdict=ev.verdict,
            risk_score=ev.score,
            rationale=tuple(ev.rationale),
        )

    def _preset_opinion(self, case: dict[str, Any]) -> list[Opinion]:
        """Legacy path: surface a pre-set opinion spec if one is declared."""

        spec = case.get("opinions", {}).get(self.agent_id)
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
