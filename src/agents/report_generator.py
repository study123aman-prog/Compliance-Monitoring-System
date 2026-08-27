"""report_generator.py — Agent 4: Report Generator (RG)."""
from __future__ import annotations

from typing import Any

from .base_agent import BaseAgent
from ..consensus import ConsensusResult, Opinion
from ..domain import AGENT_RG, AuditClass, MessageType
from ..envelope import Message
from ..escalation import EscalationResult
from ..message_bus import MessageBus


class ReportGenerator(BaseAgent):
    """Produces compliance reports, filings and management summaries.

    Crucially, RG does NOT contribute a consensus opinion — it *reports* on the
    outcome. `assess()` therefore always returns an empty list; instead RG exposes
    build_report().
    """

    covered_domains = ()

    def __init__(self, bus: MessageBus) -> None:
        super().__init__(AGENT_RG, bus)

    def assess(self, case: dict[str, Any]) -> list[Opinion]:
        """RG never votes in consensus."""

        return []

    def build_report(
        self, case: dict[str, Any], consensus: ConsensusResult, escalation: EscalationResult
    ) -> Message:
        """Assemble the report artifact for a case and publish it.

        The report bundles the disposition, the tier/SLA, and any special
        obligations (hold, SAR/dual-control, legal, board) so a human sees one
        coherent package.
        """

        report = {
            "case_id": case["case_id"],
            "title": case.get("title", ""),
            "disposition": "SUPPRESSED (NO_ALERT)" if consensus.suppressed
            else consensus.severity.name,
            "consensus_confidence": consensus.confidence,
            "mechanism": consensus.mechanism,
            "tier": escalation.tier.name,
            "sla": {"ack_minutes": escalation.ack_minutes, "resolve": escalation.resolve_target},
            "obligations": {
                "transaction_hold": escalation.transaction_hold,
                "dual_control": escalation.dual_control,
                "legal_hook": escalation.legal_hook,
                "board_reporting": escalation.board_reporting,
            },
            "regulations": case.get("regulations", []),
        }
        msg = Message(
            sender_agent_id=self.agent_id,
            recipient_agent_id="service.audit_ledger",
            message_type=MessageType.RESPONSE,
            payload_schema="report.case.v1",
            payload=report,
            correlation_id=case["case_id"],
            audit_classification=AuditClass.REGULATORY,
        )
        self.bus.publish("agent-messages", msg)
        return msg
