"""transaction_monitor.py — Agent 1: Transaction Monitor (TM)."""
from __future__ import annotations

from .base_agent import BaseAgent
from ..domain import AGENT_TM
from ..message_bus import MessageBus


class TransactionMonitor(BaseAgent):
    """Continuous surveillance of trading and financial transactions.

    Authoritative in trading patterns (spoofing, wash trading, front-running,
    late trading, concentration) and a strong (shared) voice in sanctions/AML.
    Leads or co-leads CS-01,02,04,06,09,10,12,14,15,17,18,20.
    """

    covered_domains = ("trading", "sanctions-aml")

    def __init__(self, bus: MessageBus) -> None:
        super().__init__(AGENT_TM, bus)
