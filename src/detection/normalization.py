"""
normalization.py — the Ingestion & Normalization pipe (detection stage 1).

Raw compliance signals arrive in three very different shapes:

  * transactions       (trades, transfers, deposits)   — from Transaction Monitor
  * communications     (emails, chats, call notes)      — from Communication Scanner
  * regulatory events  (rule changes, conflicts)        — from Regulatory Tracker

Before any rule or evaluator can reason about them, they must be standardised
into ONE canonical shape. That is this module's only job: take a heterogeneous
raw signal and emit a `NormalizedEvent` — a single, self-describing "unified
audit payload" that every downstream stage (guardrails, evaluator, HITL, audit
ledger) can consume without special-casing the source.

Design notes
------------
* Deterministic: normalisation never invents or randomises values, so the same
  raw signal always yields the same payload — the reproducibility the SEC 17a-4
  audit requirement depends on.
* Non-lossy: the original raw fields are preserved verbatim under `features`, so
  an auditor can always trace a decision back to the exact inputs.
* Pure standard library.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..domain import Domain

#: bumped if the canonical payload shape ever changes (audit records pin to it).
SCHEMA_VERSION = "normalized-event.v1"

#: which raw source each voting agent speaks for (used only as a sensible default
#: when a signal does not declare its own event_type).
_DEFAULT_EVENT_TYPE = {
    "agent.transaction_monitor": "transaction",
    "agent.communication_scanner": "communication",
    "agent.regulatory_tracker": "regulatory_event",
}


@dataclass
class NormalizedEvent:
    """The canonical, source-agnostic representation of one compliance signal.

    This is the "unified audit payload": whether the underlying signal was a
    wire transfer, a Bloomberg chat, or a rule change, it looks the same here.
    """

    correlation_id: str          # the case id — ties every event/decision together
    source_agent: str            # which agent observed the signal
    event_type: str              # transaction | communication | regulatory_event
    domain: Domain               # the compliance domain the evidence sits in
    violation_candidate: str     # what surveillance *thinks* this might be
    features: dict[str, Any]     # the raw, source-specific fields (verbatim)
    evidence_ref: str = ""       # pointer to the underlying record/artifact
    no_auto_resolve: bool = False  # jurisdictional (C5) events must never auto-resolve
    schema_version: str = SCHEMA_VERSION
    observed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    )

    @property
    def event_id(self) -> str:
        """Stable, deterministic id for this event within a case."""

        return f"{self.correlation_id}:{self.source_agent}"

    def feature(self, name: str, default: Any = None) -> Any:
        """Safe accessor for a raw feature (guardrail predicates use this)."""

        return self.features.get(name, default)

    def audit_payload(self) -> dict[str, Any]:
        """The unified payload written to the audit trail / handed downstream.

        Field order is stable so canonical JSON serialisation is reproducible.
        `observed_at` is deliberately excluded from anything that feeds scoring —
        detection results must not depend on wall-clock time.
        """

        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "correlation_id": self.correlation_id,
            "source_agent": self.source_agent,
            "event_type": self.event_type,
            "domain": self.domain.value,
            "violation_candidate": self.violation_candidate,
            "evidence_ref": self.evidence_ref,
            "no_auto_resolve": self.no_auto_resolve,
            "features": dict(self.features),
        }


def normalize(correlation_id: str, source_agent: str, signal: dict[str, Any]) -> NormalizedEvent:
    """Standardise one raw agent `signal` into a `NormalizedEvent`.

    `signal` is the per-agent block declared in a scenario/case under
    `signals[agent_id]`. Expected keys:
        violation_type : str            (what surveillance flagged)
        domain         : Domain          (evidence domain)
        raw            : dict            (source-specific fields)
        event_type     : str  (optional; inferred from the agent if omitted)
        evidence_ref   : str  (optional)
        no_auto_resolve: bool (optional; True only for C5 jurisdictional conflicts)

    Raises ValueError on a structurally invalid signal so bad inputs fail fast
    and loudly rather than silently scoring to zero.
    """

    if "violation_type" not in signal:
        raise ValueError(f"signal for {source_agent} is missing 'violation_type'")
    if "domain" not in signal:
        raise ValueError(f"signal for {source_agent} is missing 'domain'")

    domain = signal["domain"]
    if not isinstance(domain, Domain):
        # accept the string form too, for robustness
        domain = Domain(domain)

    event_type = signal.get("event_type") or _DEFAULT_EVENT_TYPE.get(source_agent, "generic_event")

    return NormalizedEvent(
        correlation_id=correlation_id,
        source_agent=source_agent,
        event_type=event_type,
        domain=domain,
        violation_candidate=signal["violation_type"],
        features=dict(signal.get("raw", {})),
        evidence_ref=signal.get("evidence_ref", ""),
        no_auto_resolve=bool(signal.get("no_auto_resolve", False)),
    )
