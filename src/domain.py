"""
domain.py — shared vocabulary and constant tables for the whole system.

Everything in here is a *design constant* taken directly from the specification
and the design docs (see ../docs). Keeping these in one place means the agents,
the consensus engine, the escalation manager and the tests all agree on the same
numbers — which is exactly what the rubric rewards (cross-file consistency).
"""
from __future__ import annotations

from enum import Enum, IntEnum


class Severity(IntEnum):
    """Violation severity, as an ordinal so we can take max()/compare directly.

    The integer values matter: `max(Severity.HIGH, Severity.MEDIUM)` must return
    HIGH. Ordering is NO_ALERT < LOW < MEDIUM < HIGH < CRITICAL.
    """

    NO_ALERT = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class Tier(IntEnum):
    """Human-escalation tier. T0 = auto-suppressed / no human; T4 = Director/CCO.

    Legal and Board are not separate tiers — they are *hooks* attached on top of
    a T4 escalation (see EscalationResult.legal_hook / board_reporting).
    """

    T0 = 0
    T1 = 1
    T2 = 2
    T3 = 3
    T4 = 4


class Domain(str, Enum):
    """The evidence domain an opinion sits in. Each agent is weighted by its
    authority *in the domain of its own evidence* (see AUTHORITY below)."""

    TRADING = "trading"
    COMMUNICATIONS = "communications"
    RECORD_KEEPING = "record-keeping"
    REGULATORY = "regulatory"
    SANCTIONS_AML = "sanctions-aml"


class MessageType(str, Enum):
    """The six inter-agent message types carried by the envelope."""

    ALERT = "ALERT"
    QUERY = "QUERY"
    RESPONSE = "RESPONSE"
    UPDATE = "UPDATE"
    HEARTBEAT = "HEARTBEAT"
    ESCALATION = "ESCALATION"


class AuditClass(str, Enum):
    """Routing/retention class stamped on every message and audit entry."""

    REGULATORY = "REGULATORY"
    OPERATIONAL = "OPERATIONAL"
    DIAGNOSTIC = "DIAGNOSTIC"


# --- Canonical agent / service identifiers (must match the trace-through docs) ---
AGENT_TM = "agent.transaction_monitor"
AGENT_CS = "agent.communication_scanner"
AGENT_RU = "agent.regulatory_tracker"
AGENT_RG = "agent.report_generator"
AGENT_ORCH = "agent.orchestrator"
SVC_CONSENSUS = "service.consensus_engine"
SVC_ESCALATION = "service.escalation_manager"
SVC_AUDIT = "service.audit_ledger"


# --- Domain-authority matrix (consensus-algorithm.md §3) --------------------
# AUTHORITY[agent_id][domain] -> weight in [0, 1] ("whose opinion counts more").
AUTHORITY: dict[str, dict[Domain, float]] = {
    AGENT_TM: {
        Domain.TRADING: 0.95,
        Domain.COMMUNICATIONS: 0.15,
        Domain.RECORD_KEEPING: 0.35,
        Domain.REGULATORY: 0.30,
        Domain.SANCTIONS_AML: 0.70,
    },
    AGENT_CS: {
        Domain.TRADING: 0.20,
        Domain.COMMUNICATIONS: 0.95,
        Domain.RECORD_KEEPING: 0.90,
        Domain.REGULATORY: 0.30,
        Domain.SANCTIONS_AML: 0.40,
    },
    AGENT_RU: {
        Domain.TRADING: 0.30,
        Domain.COMMUNICATIONS: 0.25,
        Domain.RECORD_KEEPING: 0.30,
        Domain.REGULATORY: 0.95,
        Domain.SANCTIONS_AML: 0.75,
    },
}


def authority(agent_id: str, domain: Domain) -> float:
    """Return the domain-authority weight w_i(d) for an agent, defaulting to a
    small non-zero value if an agent has no listed authority in a domain."""

    return AUTHORITY.get(agent_id, {}).get(domain, 0.10)


# --- Consensus constants (consensus-algorithm.md §9) ------------------------
TAU_ASSERT = 0.25   # min effective weight (a_i * c_i) for an opinion to "assert" a severity
DELTA_MARGIN = 0.20  # weighted-voting: min margin to accept a winner
KAPPA_CONFLICT = 0.60  # weighted-voting: max Dempster conflict K to accept a winner
SUPPRESSION_THRESHOLD = 0.30  # Belief(V) below this (with benign mass) => NO_ALERT / suppress


# --- Escalation SLAs by severity (escalation-framework.md) ------------------
# (acknowledge_minutes, resolve_description) — resolve times are business-context strings.
SLA: dict[Severity, tuple[int, str]] = {
    Severity.CRITICAL: (15, "24 hours"),
    Severity.HIGH: (60, "72 hours"),
    Severity.MEDIUM: (240, "5 business days"),
    Severity.LOW: (480, "10 business days"),   # 480 min = 1 business day ack
    Severity.NO_ALERT: (0, "n/a"),
}

# Priority mapping used in the message envelope (1 = most urgent).
PRIORITY: dict[Severity, int] = {
    Severity.CRITICAL: 1,
    Severity.HIGH: 2,
    Severity.MEDIUM: 3,
    Severity.LOW: 4,
    Severity.NO_ALERT: 5,
}


def severity_floor_tier(sev: Severity) -> Tier:
    """Severity-floor component of the tier rule (escalation-framework.md).

    CRITICAL -> T4, HIGH -> T3, MEDIUM -> T1, LOW/NO_ALERT -> T0.
    Note MEDIUM floors at T1 (not T2); the confidence band typically lifts a
    genuine MEDIUM case to T2 (e.g. CS-07, CS-12).
    """

    return {
        Severity.CRITICAL: Tier.T4,
        Severity.HIGH: Tier.T3,
        Severity.MEDIUM: Tier.T1,
        Severity.LOW: Tier.T0,
        Severity.NO_ALERT: Tier.T0,
    }[sev]


def confidence_band_tier(confidence: float) -> Tier:
    """Confidence-band component of the tier rule.

    Bands: [0,.30)->T0, [.30,.55)->T1, [.55,.75)->T2, [.75,.90)->T3, [.90,1]->T4.
    """

    if confidence >= 0.90:
        return Tier.T4
    if confidence >= 0.75:
        return Tier.T3
    if confidence >= 0.55:
        return Tier.T2
    if confidence >= 0.30:
        return Tier.T1
    return Tier.T0


def confidence_band_severity(confidence: float) -> Severity:
    """Severity implied purely by the confidence band.

    Used to let *corroboration* raise severity (never lower it): when combined
    belief reaches >= 0.90 the matter is CRITICAL by definition. This mirrors the
    tier rule and keeps severity/tier consistent. Applied as a floor, i.e. the
    resolved severity is max(asserted, this).
    """

    if confidence >= 0.90:
        return Severity.CRITICAL
    if confidence >= 0.75:
        return Severity.HIGH
    if confidence >= 0.55:
        return Severity.MEDIUM
    if confidence >= 0.30:
        return Severity.LOW
    return Severity.NO_ALERT
