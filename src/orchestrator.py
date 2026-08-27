"""
orchestrator.py — the supervisor that runs one compliance case end to end.

Flow (hierarchical orchestration, per ../docs/architecture):
    ingest -> collect agent opinions -> consensus -> escalation -> report -> audit

Every step writes a signed, hash-chained entry to the AuditLedger, so the whole
case is reconstructable afterwards from a single correlation_id.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .agents.base_agent import BaseAgent
from .agents.communication_scanner import CommunicationScanner
from .agents.regulatory_tracker import RegulatoryTracker
from .agents.report_generator import ReportGenerator
from .agents.transaction_monitor import TransactionMonitor
from .audit_ledger import AuditLedger
from .consensus import ConsensusEngine, ConsensusResult, Opinion
from .domain import (
    AGENT_ORCH,
    AuditClass,
    Domain,
    Severity,
    SVC_CONSENSUS,
    SVC_ESCALATION,
)
from .escalation import EscalationManager, EscalationResult
from .message_bus import MessageBus


@dataclass
class CaseOutcome:
    """Everything produced for one case — the object the tests assert against."""

    case_id: str
    consensus: ConsensusResult
    escalation: EscalationResult
    opinions: list[Opinion]


class Orchestrator:
    """Owns the bus, the four agents, the consensus engine, the escalation
    manager and the audit ledger, and drives a case through them."""

    def __init__(self) -> None:
        self.bus = MessageBus()
        self.audit = AuditLedger()
        self.consensus = ConsensusEngine()
        self.escalation = EscalationManager()

        # The four specialist agents.
        self.tm = TransactionMonitor(self.bus)
        self.cs = CommunicationScanner(self.bus)
        self.ru = RegulatoryTracker(self.bus)
        self.rg = ReportGenerator(self.bus)
        # Voting agents (RG does not vote); order is deterministic.
        self.voting_agents: list[BaseAgent] = [self.tm, self.cs, self.ru]

    def process_case(self, case: dict[str, Any]) -> CaseOutcome:
        """Run one scenario/case and return its outcome."""

        cid = case["case_id"]
        self.audit.append(cid, AGENT_ORCH, "case.ingested",
                          {"title": case.get("title", "")}, AuditClass.REGULATORY)

        # 1) Collect opinions from the voting agents; emit an ALERT per opinion.
        opinions: list[Opinion] = []
        for agent in self.voting_agents:
            for op in agent.assess(case):
                agent.emit_alert(case, op)
                opinions.append(op)
                self.audit.append(
                    cid, agent.agent_id, "detection.alert",
                    {"severity": op.severity.name, "confidence": op.confidence,
                     "domain": op.domain.value, "benign": op.benign},
                    AuditClass.REGULATORY,
                )

        # 1b) Attach any explicit benign VERIFICATIONS (e.g. an authenticated
        #     approval record). These are not surveillance votes; they commit mass
        #     to "benign" and can suppress a false positive (the CS-18 trap).
        for v in case.get("verifications", []):
            vop = Opinion(
                agent_id=v["agent_id"],
                severity=Severity.NO_ALERT,
                confidence=v["confidence"],
                domain=Domain(v["domain"]),
                benign=True,
                weight=v.get("weight"),
                evidence_ref=v.get("evidence_ref", ""),
            )
            opinions.append(vop)
            self.audit.append(
                cid, v["agent_id"], "verification.recorded",
                {"confidence": vop.confidence, "domain": vop.domain.value,
                 "weight": vop.effective_weight(), "benign": True},
                AuditClass.REGULATORY,
            )

        # 2) Consensus.
        cr = self.consensus.resolve(opinions)
        self.audit.append(cid, SVC_CONSENSUS, "consensus.computed",
                          {"severity": cr.severity.name, "confidence": cr.confidence,
                           "mechanism": cr.mechanism, **cr.detail}, AuditClass.REGULATORY)

        # 3) Escalation (special triggers declared by the scenario).
        er = self.escalation.decide(cr, case.get("triggers", []))
        self.audit.append(cid, SVC_ESCALATION, "escalation.decided",
                          {"tier": er.tier.name, "ack_minutes": er.ack_minutes,
                           "resolve": er.resolve_target, "suppressed": er.suppressed,
                           "transaction_hold": er.transaction_hold, "legal_hook": er.legal_hook,
                           "board_reporting": er.board_reporting, "dual_control": er.dual_control,
                           "unresolved": er.unresolved, "triggers": er.triggers},
                          AuditClass.REGULATORY)

        # 4) Report (RG assembles the package; it does not vote).
        self.rg.build_report(case, cr, er)
        self.audit.append(cid, self.rg.agent_id, "report.generated",
                          {"disposition": "SUPPRESSED" if cr.suppressed else cr.severity.name},
                          AuditClass.REGULATORY)

        return CaseOutcome(case_id=cid, consensus=cr, escalation=er, opinions=opinions)
