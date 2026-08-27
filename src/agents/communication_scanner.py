"""communication_scanner.py — Agent 2: Communication Scanner (CS)."""
from __future__ import annotations

from .base_agent import BaseAgent
from ..domain import AGENT_CS
from ..message_bus import MessageBus


class CommunicationScanner(BaseAgent):
    """Monitors internal/external communications for compliance violations.

    Authoritative in communications content/intent (misleading claims, coercion,
    information-barrier breaches) and record-keeping / off-channel comms. Leads or
    co-leads CS-01,03,05,08,11,13,16,17,20.

    (Naming note: the agent is 'CS'; the scenarios are also prefixed 'CS-NN'. They
    are unrelated — one is an agent, the other a scenario id.)
    """

    covered_domains = ("communications", "record-keeping")

    def __init__(self, bus: MessageBus) -> None:
        super().__init__(AGENT_CS, bus)
