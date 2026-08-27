"""regulatory_tracker.py — Agent 3: Regulatory Update Tracker (RU)."""
from __future__ import annotations

from .base_agent import BaseAgent
from ..domain import AGENT_RU
from ..message_bus import MessageBus


class RegulatoryTracker(BaseAgent):
    """Monitors the regulatory landscape; assesses impact of new/changed rules.

    Authoritative in regulatory change/interpretation and cross-jurisdiction
    conflict, and a strong (shared) voice in sanctions/AML. Leads or co-leads
    CS-07,09,11,19,20. Its assessments are *preliminary* and require human
    validation — it cannot interpret ambiguous language or modify rules itself.
    """

    covered_domains = ("regulatory", "sanctions-aml")

    def __init__(self, bus: MessageBus) -> None:
        super().__init__(AGENT_RU, bus)
