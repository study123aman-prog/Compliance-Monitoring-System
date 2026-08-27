"""
scenarios.py — the 20 test scenarios (CS-01 .. CS-20) as data.

Each scenario is a plain dict. The `opinions` map is keyed by agent_id so each
agent surfaces its own view during `assess()`. `verifications` carries explicit
benign records (only CS-18 uses one). `triggers` lists any special escalation
triggers the scenario declares. `expected` is the locked outcome the test suite
asserts against — the single source of truth shared with
../../tests/scenarios/scenario-summary.md, where every value is hand-derived.

Titles, violation types and regulations mirror Section B4 of the source
specification verbatim; the per-agent domains and confidences are the calibrated
inputs that reproduce the locked consensus values. Keeping the scenarios as data
(rather than 20 bespoke functions) means the same Orchestrator code path runs all
of them — exactly the reproducibility property the audit requirement asks for.
"""
from __future__ import annotations

from .domain import (
    AGENT_CS,
    AGENT_RU,
    AGENT_TM,
    Domain,
    Severity,
)

# A verification is not an agent vote; it is an authenticated exculpatory record.
SVC_VERIFICATION = "service.verification"


def _op(severity: Severity, confidence: float, domain: Domain, **extra) -> dict:
    """Small helper to keep each opinion spec on one readable line."""

    spec = {"severity": severity, "confidence": confidence, "domain": domain}
    spec.update(extra)
    return spec


# --------------------------------------------------------------------------- #
#  The 20 scenarios (themes and regulations verbatim from spec Section B4).
# --------------------------------------------------------------------------- #
SCENARIOS: list[dict] = [
    # ---- CS-01: insider trading — pre-announcement accumulation (TM + CS) ----
    {
        "case_id": "CS-01",
        "title": "Insider trading — pre-announcement accumulation",
        "violation_type": "insider_trading",
        "regulations": ["SEC Rule 10b-5", "FINRA Rule 2010", "Insider Trading Sanctions Act"],
        "opinions": {
            AGENT_TM: _op(Severity.HIGH, 0.72, Domain.TRADING),
            AGENT_CS: _op(Severity.HIGH, 0.80, Domain.COMMUNICATIONS),
        },
        "expected": {
            "severity": "CRITICAL", "confidence": 0.92, "tier": "T4",
            "agents": {AGENT_TM, AGENT_CS}, "mechanism": "dempster_shafer",
        },
    },
    # ---- CS-02: spoofing / layering in futures (TM only) ----
    {
        "case_id": "CS-02",
        "title": "Market manipulation — spoofing in futures markets",
        "violation_type": "spoofing",
        "regulations": ["Dodd-Frank Act §747", "CEA §4c(a)(5)", "CME Rule 575"],
        "opinions": {
            AGENT_TM: _op(Severity.HIGH, 0.85, Domain.TRADING),
        },
        "expected": {
            "severity": "HIGH", "confidence": 0.85, "tier": "T3",
            "agents": {AGENT_TM}, "mechanism": "passthrough",
        },
    },
    # ---- CS-03: unsuitable investment recommendation (CS leads, TM supports) ----
    {
        "case_id": "CS-03",
        "title": "Unsuitable investment recommendation",
        "violation_type": "unsuitable_recommendation",
        "regulations": ["FINRA Rule 2111", "SEC Regulation Best Interest"],
        "opinions": {
            AGENT_CS: _op(Severity.HIGH, 0.70, Domain.COMMUNICATIONS),
            AGENT_TM: _op(Severity.HIGH, 0.62, Domain.TRADING),
        },
        "expected": {
            "severity": "HIGH", "confidence": 0.86, "tier": "T3",
            "agents": {AGENT_CS, AGENT_TM}, "mechanism": "dempster_shafer",
        },
    },
    # ---- CS-04: AML — structuring of cash deposits (TM, SAR clock) ----
    {
        "case_id": "CS-04",
        "title": "AML — structuring of cash deposits",
        "violation_type": "structuring",
        "regulations": ["Bank Secrecy Act", "31 CFR 1020.320", "FinCEN SAR requirements"],
        "opinions": {
            AGENT_TM: _op(Severity.CRITICAL, 0.88, Domain.SANCTIONS_AML),
        },
        "triggers": ["sar_filing"],
        "expected": {
            "severity": "CRITICAL", "confidence": 0.88, "tier": "T4",
            "agents": {AGENT_TM}, "mechanism": "passthrough",
            "dual_control": True,
        },
    },
    # ---- CS-05: Chinese-wall breach — information leakage (CS only) ----
    {
        "case_id": "CS-05",
        "title": "Chinese-wall breach — information leakage",
        "violation_type": "information_barrier_breach",
        "regulations": ["SEA 1934 §15(g)", "FINRA Rule 5280", "MiFID II Article 33"],
        "opinions": {
            AGENT_CS: _op(Severity.CRITICAL, 0.83, Domain.COMMUNICATIONS),
        },
        "expected": {
            "severity": "CRITICAL", "confidence": 0.83, "tier": "T4",
            "agents": {AGENT_CS}, "mechanism": "passthrough",
        },
    },
    # ---- CS-06: wash trading — cross-account coordination (TM only) ----
    {
        "case_id": "CS-06",
        "title": "Wash trading — cross-account coordination",
        "violation_type": "wash_trading",
        "regulations": ["CEA §4c(a)", "SEC Rule 10b-5", "FINRA Rule 5210"],
        "opinions": {
            AGENT_TM: _op(Severity.HIGH, 0.82, Domain.TRADING),
        },
        "expected": {
            "severity": "HIGH", "confidence": 0.82, "tier": "T3",
            "agents": {AGENT_TM}, "mechanism": "passthrough",
        },
    },
    # ---- CS-07: regulatory change — new margin requirements (RU only) ----
    {
        "case_id": "CS-07",
        "title": "Regulatory change impact — new margin requirements",
        "violation_type": "regulatory_change",
        "regulations": ["SEC Swap Margin Rule", "Basel III CRE54", "EMIR Margin RTS"],
        "opinions": {
            AGENT_RU: _op(Severity.MEDIUM, 0.70, Domain.REGULATORY),
        },
        "expected": {
            "severity": "MEDIUM", "confidence": 0.70, "tier": "T2",
            "agents": {AGENT_RU}, "mechanism": "passthrough",
        },
    },
    # ---- CS-08: misleading performance claims in marketing (CS only) ----
    {
        "case_id": "CS-08",
        "title": "Client communication violation — misleading performance claims",
        "violation_type": "misleading_communications",
        "regulations": ["SEC Rule 206(4)-1", "FINRA Rule 2210", "FCA COBS 4"],
        "opinions": {
            AGENT_CS: _op(Severity.CRITICAL, 0.86, Domain.COMMUNICATIONS),
        },
        "expected": {
            "severity": "CRITICAL", "confidence": 0.86, "tier": "T4",
            "agents": {AGENT_CS}, "mechanism": "passthrough",
        },
    },
    # ---- CS-09: sanctions — indirect counterparty exposure (TM + RU, hold) ----
    {
        "case_id": "CS-09",
        "title": "Sanctions violation — indirect counterparty exposure",
        "violation_type": "sanctions_violation",
        "regulations": ["OFAC Regulations", "31 CFR Part 501", "EU Sanctions Regulation"],
        "opinions": {
            AGENT_TM: _op(Severity.CRITICAL, 0.82, Domain.SANCTIONS_AML),
            AGENT_RU: _op(Severity.CRITICAL, 0.92, Domain.SANCTIONS_AML),
        },
        "triggers": ["sanctions_aml"],
        "expected": {
            "severity": "CRITICAL", "confidence": 0.87, "tier": "T4",
            "agents": {AGENT_TM, AGENT_RU}, "mechanism": "dempster_shafer",
            "transaction_hold": True,
        },
    },
    # ---- CS-10: front-running — client order anticipation (TM only) ----
    {
        "case_id": "CS-10",
        "title": "Front-running — client order anticipation",
        "violation_type": "front_running",
        "regulations": ["SEA 1934 §17(j)", "Investment Company Act §17(j)", "FINRA Rule 5270"],
        "opinions": {
            AGENT_TM: _op(Severity.CRITICAL, 0.87, Domain.TRADING),
        },
        "expected": {
            "severity": "CRITICAL", "confidence": 0.87, "tier": "T4",
            "agents": {AGENT_TM}, "mechanism": "passthrough",
        },
    },
    # ---- CS-11: data-privacy violation — cross-border transfer (CS + RU) ----
    {
        "case_id": "CS-11",
        "title": "Data-privacy violation — cross-border transfer",
        "violation_type": "data_privacy_violation",
        "regulations": ["GDPR Articles 44–49", "Schrems II ruling"],
        "opinions": {
            AGENT_CS: _op(Severity.HIGH, 0.68, Domain.RECORD_KEEPING),
            AGENT_RU: _op(Severity.HIGH, 0.72, Domain.REGULATORY),
        },
        "expected": {
            "severity": "HIGH", "confidence": 0.88, "tier": "T3",
            "agents": {AGENT_CS, AGENT_RU}, "mechanism": "dempster_shafer",
        },
    },
    # ---- CS-12: concentration risk — portfolio limit breach (TM only) ----
    {
        "case_id": "CS-12",
        "title": "Concentration risk — portfolio limit breach",
        "violation_type": "concentration_breach",
        "regulations": ["Investment Company Act §13", "SEC Form N-PORT", "UCITS concentration limits"],
        "opinions": {
            AGENT_TM: _op(Severity.MEDIUM, 0.72, Domain.TRADING),
        },
        "expected": {
            "severity": "MEDIUM", "confidence": 0.72, "tier": "T2",
            "agents": {AGENT_TM}, "mechanism": "passthrough",
        },
    },
    # ---- CS-13: off-channel communication — personal device usage (CS only) ----
    {
        "case_id": "CS-13",
        "title": "Off-channel communication — personal device usage",
        "violation_type": "off_channel_comms",
        "regulations": ["SEC Rule 17a-4", "FINRA Rule 3110"],
        "opinions": {
            AGENT_CS: _op(Severity.HIGH, 0.84, Domain.RECORD_KEEPING),
        },
        "expected": {
            "severity": "HIGH", "confidence": 0.84, "tier": "T3",
            "agents": {AGENT_CS}, "mechanism": "passthrough",
        },
    },
    # ---- CS-14: late trading — mutual fund NAV manipulation (TM only) ----
    {
        "case_id": "CS-14",
        "title": "Late trading — mutual fund NAV manipulation",
        "violation_type": "late_trading",
        "regulations": ["SEC Rule 22c-1", "Investment Company Act §22(c)"],
        "opinions": {
            AGENT_TM: _op(Severity.CRITICAL, 0.85, Domain.TRADING),
        },
        "expected": {
            "severity": "CRITICAL", "confidence": 0.85, "tier": "T4",
            "agents": {AGENT_TM}, "mechanism": "passthrough",
        },
    },
    # ---- CS-15: best-execution failure — systematic order-routing bias (TM only) ----
    {
        "case_id": "CS-15",
        "title": "Best-execution failure — systematic order-routing bias",
        "violation_type": "best_execution_failure",
        "regulations": ["SEC Rule 606", "FINRA Rule 5310", "MiFID II Best Execution"],
        "opinions": {
            AGENT_TM: _op(Severity.HIGH, 0.80, Domain.TRADING),
        },
        "expected": {
            "severity": "HIGH", "confidence": 0.80, "tier": "T3",
            "agents": {AGENT_TM}, "mechanism": "passthrough",
        },
    },
    # ---- CS-16: conflict of interest — research independence (CS + TM) ----
    {
        "case_id": "CS-16",
        "title": "Conflict of interest — research independence",
        "violation_type": "research_independence",
        "regulations": ["SEC Regulation AC", "FINRA Rule 2241", "Global Research Settlement"],
        "opinions": {
            AGENT_CS: _op(Severity.HIGH, 0.80, Domain.COMMUNICATIONS),
            AGENT_TM: _op(Severity.HIGH, 0.72, Domain.TRADING),
        },
        "expected": {
            "severity": "CRITICAL", "confidence": 0.92, "tier": "T4",
            "agents": {AGENT_CS, AGENT_TM}, "mechanism": "dempster_shafer",
        },
    },
    # ---- CS-17: elder financial exploitation (TM + CS) ----
    {
        "case_id": "CS-17",
        "title": "Elder financial exploitation",
        "violation_type": "elder_exploitation",
        "regulations": ["FINRA Rule 2165", "FINRA Rule 4512", "SEC Senior Safe Act"],
        "opinions": {
            AGENT_TM: _op(Severity.HIGH, 0.82, Domain.TRADING),
            AGENT_CS: _op(Severity.HIGH, 0.78, Domain.COMMUNICATIONS),
        },
        "expected": {
            "severity": "CRITICAL", "confidence": 0.94, "tier": "T4",
            "agents": {AGENT_TM, AGENT_CS}, "mechanism": "dempster_shafer",
        },
    },
    # ---- CS-18: FALSE POSITIVE — legitimate block trade (suppressed) ----
    {
        "case_id": "CS-18",
        "title": "FALSE POSITIVE — legitimate pre-arranged block trade",
        "violation_type": "large_block_trade",
        "regulations": ["SEA 1934 §10(b)"],
        "opinions": {
            AGENT_TM: _op(Severity.HIGH, 0.68, Domain.TRADING),
        },
        "verifications": [
            {"agent_id": SVC_VERIFICATION, "confidence": 0.90,
             "domain": "trading", "weight": 0.90,
             "evidence_ref": "approval-record:block-desk-prearrangement+disclosed-rebalancing"},
        ],
        "expected": {
            "severity": "NO_ALERT", "confidence": 0.26, "tier": "T0",
            "agents": {AGENT_TM}, "mechanism": "suppressed_after_verification",
            "suppressed": True,
        },
    },
    # ---- CS-19: multi-jurisdiction regulatory conflict — never auto-resolved ----
    {
        "case_id": "CS-19",
        "title": "Multi-jurisdiction regulatory conflict (never auto-resolved)",
        "violation_type": "jurisdictional_conflict",
        "regulations": ["EMIR Reporting Obligation", "MAS Securities and Futures Act", "GDPR"],
        "opinions": {
            AGENT_RU: _op(Severity.HIGH, 0.90, Domain.REGULATORY, no_auto_resolve=True),
        },
        "triggers": ["jurisdictional_c5"],
        "expected": {
            "severity": "HIGH", "confidence": 0.90, "tier": "T4",
            "agents": {AGENT_RU}, "mechanism": "jurisdictional_bypass",
            "legal_hook": True, "unresolved": True,
        },
    },
    # ---- CS-20: COORDINATED — trade-based money laundering (all four agents) ----
    {
        "case_id": "CS-20",
        "title": "Coordinated scheme — trade-based money laundering",
        "violation_type": "trade_based_money_laundering",
        "regulations": ["Bank Secrecy Act (AML)", "OFAC Regulations",
                        "FATF Trade-Based ML Guidance", "FinCEN SAR requirements"],
        "opinions": {
            AGENT_TM: _op(Severity.CRITICAL, 0.80, Domain.SANCTIONS_AML),
            AGENT_CS: _op(Severity.CRITICAL, 0.78, Domain.RECORD_KEEPING),
            AGENT_RU: _op(Severity.CRITICAL, 0.85, Domain.SANCTIONS_AML),
        },
        "triggers": ["sanctions_aml", "control_override_c7", "sar_filing", "board_level"],
        "expected": {
            "severity": "CRITICAL", "confidence": 0.95, "tier": "T4",
            "agents": {AGENT_TM, AGENT_CS, AGENT_RU}, "mechanism": "dempster_shafer",
            "transaction_hold": True, "dual_control": True, "board_reporting": True,
        },
    },
]


def by_id(case_id: str) -> dict:
    """Look up a scenario dict by its case_id (e.g. 'CS-09')."""

    for s in SCENARIOS:
        if s["case_id"] == case_id:
            return s
    raise KeyError(case_id)
