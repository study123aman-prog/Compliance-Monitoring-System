"""
scenarios.py — the 20 test scenarios (CS-01 .. CS-20) as data.

Each scenario is a plain dict with three input layers and one expected outcome:

  * `signals`      — the RAW evidence each agent observes, keyed by agent_id. This
                     is what the two-tier detection core (src/detection) actually
                     consumes: the agent normalises it, runs the deterministic
                     guardrails, then the agentic evaluator, and COMPUTES its
                     severity/confidence. Each signal lists its risk `indicators`
                     (deterministic bright-line checks + agentic contextual points);
                     by construction the points sum to confidence*100, so the
                     computed opinion reproduces the calibrated value below.
  * `opinions`     — the per-agent opinion the detection core is expected to
                     produce (severity + confidence + domain). Retained as the
                     reproduction target (see tests/test_detection.py) and as a
                     fallback for cases/fixtures that carry no raw signal.
  * `verifications`— explicit authenticated benign records (only CS-18 uses one).
  * `triggers`     — special escalation triggers the scenario declares.
  * `expected`     — the locked consensus/escalation outcome the acceptance tests
                     assert against; the single source of truth shared with
                     ../../tests/scenarios/scenario-summary.md.

Titles, violation types and regulations mirror Section B4 of the source
specification verbatim. Keeping the scenarios as data (rather than 20 bespoke
functions) means the same Orchestrator + detection code path runs all of them —
exactly the reproducibility property the audit requirement asks for.
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
#  Signal helpers — keep each raw signal / indicator readable on a line or two.
# --------------------------------------------------------------------------- #
def _det(rule_id: str, desc: str, points: int, check: str, hard: bool = False, **params) -> dict:
    """A DETERMINISTIC indicator: a bright-line guardrail check + its risk points.

    `check` names a predicate in src/detection/guardrails.GUARDRAIL_CHECKS and
    `params` are its arguments (field / value / pattern / low / high / values).
    """

    return {"id": rule_id, "desc": desc, "points": points, "tier": "deterministic",
            "check": check, "hard": hard, **params}


def _ag(rule_id: str, desc: str, points: int) -> dict:
    """An AGENTIC indicator: a nuanced/contextual judgement and its risk points."""

    return {"id": rule_id, "desc": desc, "points": points, "tier": "agentic"}


def _sig(violation_type: str, domain: Domain, raw: dict, indicators: list[dict], **extra) -> dict:
    """One agent's raw signal block for a case."""

    return {"violation_type": violation_type, "domain": domain,
            "raw": raw, "indicators": indicators, **extra}


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
        "signals": {
            AGENT_TM: _sig("insider_trading", Domain.TRADING,
                raw={"instrument": "ACME", "days_to_announcement": 17,
                     "adv_multiple": 4.1, "notional_usd": 12_500_000},
                indicators=[
                    _det("restricted_list_trade", "Instrument on restricted/watch list",
                         24, "on_restricted_list"),
                    _det("pre_announcement_window", "Buying inside 21-day pre-announcement window",
                         20, "in_range", field="days_to_announcement", low=1, high=21),
                    _ag("accumulation_vs_adv", "Accumulation 4.1x 30-day ADV in three weeks", 28),
                ]),
            AGENT_CS: _sig("insider_trading", Domain.COMMUNICATIONS,
                raw={"text": "heads up before the acquisition goes public — results look strong",
                     "contact_with_issuer_insider": True},
                indicators=[
                    _det("mnpi_keyword", "MNPI keywords in message (acquisition/results/nonpublic)",
                         30, "regex", field="text",
                         pattern=r"acquisition|nonpublic|guidance|results|merger"),
                    _det("issuer_insider_contact", "External contact with an issuer insider",
                         24, "is_true", field="contact_with_issuer_insider"),
                    _ag("timing_proximity", "Message two days before the trade cluster", 26),
                ]),
        },
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
        "signals": {
            AGENT_TM: _sig("spoofing", Domain.TRADING,
                raw={"cancel_ratio": 0.97, "layered_levels": 8, "avg_resting_ms": 180},
                indicators=[
                    _det("cancel_ratio_extreme", "Order cancel ratio 0.97 (>0.90)",
                         30, "gt", field="cancel_ratio", value=0.90),
                    _det("multi_level_layering", "Eight layered price levels (>=5)",
                         25, "ge", field="layered_levels", value=5),
                    _ag("no_fill_intent", "Orders posted and pulled within ~180ms, no fill intent", 30),
                ]),
        },
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
        "signals": {
            AGENT_CS: _sig("unsuitable_recommendation", Domain.COMMUNICATIONS,
                raw={"advice_text": "put your entire retirement savings into this leveraged product",
                     "client_risk_profile": "conservative", "product_risk": "high"},
                indicators=[
                    _det("high_risk_advice_language", "Advice pushes leverage / all-in of savings",
                         25, "regex", field="advice_text",
                         pattern=r"all-in|guaranteed|retirement savings|leverage|double down"),
                    _det("conservative_profile", "Client profile is conservative",
                         20, "equals", field="client_risk_profile", value="conservative"),
                    _ag("suitability_mismatch", "High-risk product vs conservative profile", 25),
                ]),
            AGENT_TM: _sig("unsuitable_recommendation", Domain.TRADING,
                raw={"product_risk": "high", "portfolio_alloc_pct": 85},
                indicators=[
                    _det("high_risk_product", "Executed product is high-risk",
                         20, "equals", field="product_risk", value="high"),
                    _det("over_allocation", "85% of portfolio into one product (>50%)",
                         20, "gt", field="portfolio_alloc_pct", value=50),
                    _ag("concentration_in_unsuitable", "Concentration compounds unsuitability", 22),
                ]),
        },
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
        "signals": {
            AGENT_TM: _sig("structuring", Domain.SANCTIONS_AML,
                raw={"deposits": [9500, 9200, 9800, 9600], "branches": 4, "window_hours": 26},
                indicators=[
                    _det("sub_threshold_deposits", "All cash deposits below $10,000 (structuring)",
                         40, "all_below", hard=True, field="deposits", value=10000),
                    _det("repeated_deposits", "Four deposits in the pattern (>=3)",
                         18, "count_ge", field="deposits", value=3),
                    _ag("multi_branch_same_window", "Spread across 4 branches within 26h", 30),
                ]),
        },
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
        "signals": {
            AGENT_CS: _sig("information_barrier_breach", Domain.COMMUNICATIONS,
                raw={"crosses_information_barrier": True, "from_side": "private", "to_side": "public"},
                indicators=[
                    _det("wall_crossing", "Message crosses the information barrier (private->public)",
                         48, "is_true", hard=True, field="crosses_information_barrier"),
                    _ag("deal_team_to_trading", "MNPI routed from deal team to trading desk", 35),
                ]),
        },
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
        "signals": {
            AGENT_TM: _sig("wash_trading", Domain.TRADING,
                raw={"same_beneficial_owner": True, "matched_trade_pct": 0.93},
                indicators=[
                    _det("same_beneficial_owner", "Both sides share one beneficial owner",
                         30, "is_true", hard=True, field="same_beneficial_owner"),
                    _det("matched_offsetting", "93% of trades matched/offsetting (>0.80)",
                         22, "gt", field="matched_trade_pct", value=0.80),
                    _ag("no_economic_purpose", "Offsetting trades carry no market risk", 30),
                ]),
        },
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
        "signals": {
            AGENT_RU: _sig("regulatory_change", Domain.REGULATORY,
                raw={"rule_effective_within_90d": True, "days_to_effective": 60, "impacted_desks": 5},
                indicators=[
                    _det("effective_soon", "New margin rule effective within 90 days",
                         20, "is_true", field="rule_effective_within_90d"),
                    _det("broad_impact", "Five trading desks impacted (>=3)",
                         20, "ge", field="impacted_desks", value=3),
                    _ag("margin_model_gap", "New requirements exceed current margin model", 30),
                ]),
        },
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
        "signals": {
            AGENT_CS: _sig("misleading_communications", Domain.COMMUNICATIONS,
                raw={"marketing_text": "guaranteed risk-free 20% annual returns",
                     "lacks_required_disclosures": True},
                indicators=[
                    _det("guaranteed_return_language", "Marketing uses guaranteed/risk-free claims",
                         40, "regex", hard=True, field="marketing_text",
                         pattern=r"guaranteed|risk-free|can'?t lose|no risk|assured returns"),
                    _det("missing_disclosures", "Required risk disclosures absent",
                         16, "is_true", field="lacks_required_disclosures"),
                    _ag("cherry_picked_track_record", "Selective/omitted performance context", 30),
                ]),
        },
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
        "signals": {
            AGENT_TM: _sig("sanctions_violation", Domain.SANCTIONS_AML,
                raw={"counterparty": "Orion Petro DMCC"},
                indicators=[
                    _det("sanctions_list_hit", "Counterparty on OFAC sanctions list",
                         45, "on_sanctions_list", hard=True),
                    _ag("indirect_ownership", "Listed party holds >50% (indirect exposure)", 37),
                ]),
            AGENT_RU: _sig("sanctions_violation", Domain.SANCTIONS_AML,
                raw={"ultimate_parent": "sanctioned-counterparty", "ofac_50_percent_rule": True},
                indicators=[
                    _det("parent_sanctions_hit", "Ultimate parent on sanctions list",
                         45, "on_sanctions_list", hard=True, field="ultimate_parent"),
                    _det("ofac_50_percent", "OFAC 50% rule engaged",
                         17, "is_true", field="ofac_50_percent_rule"),
                    _ag("cross_border_layering", "Ownership layered across jurisdictions", 30),
                ]),
        },
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
        "signals": {
            AGENT_TM: _sig("front_running", Domain.TRADING,
                raw={"proprietary_ahead_of_client": True, "seconds_before_client_order": 8},
                indicators=[
                    _det("prop_ahead_of_client", "Proprietary order placed ahead of client order",
                         40, "is_true", hard=True, field="proprietary_ahead_of_client"),
                    _det("tight_timing", "Prop order 8s before client order (1-60s)",
                         17, "in_range", field="seconds_before_client_order", low=1, high=60),
                    _ag("systematic_pattern", "14 similar instances — systematic, not incidental", 30),
                ]),
        },
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
        "signals": {
            AGENT_CS: _sig("data_privacy_violation", Domain.RECORD_KEEPING,
                raw={"pii_transferred": True, "cross_border": True,
                     "destination": "US", "record_count": 42000},
                indicators=[
                    _det("pii_export", "PII records transferred",
                         20, "is_true", field="pii_transferred"),
                    _det("cross_border_flag", "Transfer crosses a border",
                         18, "is_true", field="cross_border"),
                    _ag("no_scc_or_adequacy", "No SCCs / adequacy basis (post-Schrems II)", 30),
                ]),
            AGENT_RU: _sig("data_privacy_violation", Domain.REGULATORY,
                raw={"gdpr_chapter_v_transfer": True, "adequacy_decision": False},
                indicators=[
                    _det("chapter_v_transfer", "GDPR Chapter V transfer without safeguards",
                         22, "is_true", field="gdpr_chapter_v_transfer"),
                    _det("no_adequacy_decision", "Destination lacks an adequacy decision",
                         20, "equals", field="adequacy_decision", value=False),
                    _ag("schrems_ii_exposure", "Direct Schrems II exposure", 30),
                ]),
        },
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
        "signals": {
            AGENT_TM: _sig("concentration_breach", Domain.TRADING,
                raw={"single_issuer_pct": 31, "sector_pct": 48, "breach_days": 12},
                indicators=[
                    _det("single_issuer_over_limit", "Single-issuer exposure 31% (>25%)",
                         22, "gt", field="single_issuer_pct", value=25),
                    _det("sector_over_limit", "Sector exposure 48% (>40%)",
                         20, "gt", field="sector_pct", value=40),
                    _ag("sustained_breach", "Breach persisted 12 days unremediated", 30),
                ]),
        },
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
        "signals": {
            AGENT_CS: _sig("off_channel_comms", Domain.RECORD_KEEPING,
                raw={"channel": "personal_whatsapp", "business_content": True},
                indicators=[
                    _det("personal_channel", "Business comms on a personal channel",
                         45, "channel_is_personal", hard=True),
                    _det("business_substance", "Message carries business substance",
                         15, "is_true", field="business_content"),
                    _ag("recordkeeping_gap", "Comms never captured by surveillance/archive", 24),
                ]),
        },
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
        "signals": {
            AGENT_TM: _sig("late_trading", Domain.TRADING,
                raw={"after_market_close": True, "priced_at_prior_nav": True, "order_time": "16:12"},
                indicators=[
                    _det("post_close_order", "Order entered after 16:00 market close",
                         40, "is_true", hard=True, field="after_market_close"),
                    _det("stale_nav_pricing", "Filled at that day's (prior) NAV",
                         15, "is_true", field="priced_at_prior_nav"),
                    _ag("systematic_late_pattern", "Recurring post-close entries at prior NAV", 30),
                ]),
        },
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
        "signals": {
            AGENT_TM: _sig("best_execution_failure", Domain.TRADING,
                raw={"worse_than_nbbo_bps": 14, "routed_to_affiliate_pct": 0.92},
                indicators=[
                    _det("worse_than_nbbo", "Fills 14bps worse than NBBO (>5bps)",
                         25, "gt", field="worse_than_nbbo_bps", value=5),
                    _det("affiliate_routing_bias", "92% of flow routed to an affiliate (>0.70)",
                         25, "gt", field="routed_to_affiliate_pct", value=0.70),
                    _ag("pfof_bias", "Routing driven by payment-for-order-flow, not price", 30),
                ]),
        },
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
        "signals": {
            AGENT_CS: _sig("research_independence", Domain.COMMUNICATIONS,
                raw={"analyst_comp_tied_to_banking": True,
                     "research_text": "banking client asked us to upgrade the rating"},
                indicators=[
                    _det("comp_conflict", "Analyst comp tied to banking revenue",
                         30, "is_true", field="analyst_comp_tied_to_banking"),
                    _det("pressure_language", "Message shows banking pressure on the rating",
                         20, "regex", field="research_text",
                         pattern=r"pressure|change the rating|banking client|upgrade"),
                    _ag("rating_vs_model", "Published rating inconsistent with the model", 30),
                ]),
            AGENT_TM: _sig("research_independence", Domain.TRADING,
                raw={"trading_ahead_of_research": True, "position_change_pct": 35},
                indicators=[
                    _det("trading_ahead", "Desk traded ahead of research publication",
                         22, "is_true", field="trading_ahead_of_research"),
                    _det("large_position_shift", "35% position change around the call (>20%)",
                         20, "gt", field="position_change_pct", value=20),
                    _ag("research_conflict_pattern", "Pattern links desk P&L to research timing", 30),
                ]),
        },
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
        "signals": {
            AGENT_TM: _sig("elder_exploitation", Domain.TRADING,
                raw={"client_age": 82, "withdrawal_spike_pct": 340},
                indicators=[
                    _det("elderly_client", "Client age 82 (>=75, protected)",
                         25, "ge", field="client_age", value=75),
                    _det("withdrawal_spike", "Withdrawals up 340% vs baseline (>200%)",
                         27, "gt", field="withdrawal_spike_pct", value=200),
                    _ag("new_beneficiary", "Funds redirected to a newly-added third party", 30),
                ]),
            AGENT_CS: _sig("elder_exploitation", Domain.COMMUNICATIONS,
                raw={"client_age": 82,
                     "comms_text": "client seemed confused; urgent wire to a new friend"},
                indicators=[
                    _det("elderly_client", "Client age 82 (>=75, protected)",
                         25, "ge", field="client_age", value=75),
                    _det("coercion_language", "Confusion / urgency / third-party cues in comms",
                         23, "regex", field="comms_text",
                         pattern=r"confused|urgent|don'?t tell|wire the money|new friend"),
                    _ag("coercion_indicators", "Behavioural coercion indicators present", 30),
                ]),
        },
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
        "signals": {
            AGENT_TM: _sig("large_block_trade", Domain.TRADING,
                raw={"block_size_adv_multiple": 7.2, "price_outside_vwap_band": True},
                indicators=[
                    _det("large_block", "Block 7.2x ADV (>5x)",
                         20, "gt", field="block_size_adv_multiple", value=5),
                    _det("price_off_vwap", "Print outside the VWAP band",
                         18, "is_true", field="price_outside_vwap_band"),
                    _ag("unusual_size_timing", "Size/timing look anomalous on first pass", 30),
                ]),
        },
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
        "signals": {
            AGENT_RU: _sig("jurisdictional_conflict", Domain.REGULATORY,
                raw={"conflicting_obligations": True,
                     "jurisdictions": ["EU-EMIR", "SG-MAS", "EU-GDPR"]},
                indicators=[
                    _det("conflicting_obligations", "Mutually incompatible legal obligations",
                         30, "is_true", field="conflicting_obligations"),
                    _det("multi_jurisdiction", "Three jurisdictions in conflict (>=2)",
                         25, "count_ge", field="jurisdictions", value=2),
                    _ag("no_safe_harbor", "Complying with one law breaches another — no safe harbour", 35),
                ],
                no_auto_resolve=True),
        },
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
        "signals": {
            AGENT_TM: _sig("trade_based_money_laundering", Domain.SANCTIONS_AML,
                raw={"counterparty": "Garnet Trading FZCO", "over_invoicing_pct": 60},
                indicators=[
                    _det("sanctions_list_hit", "Counterparty on OFAC sanctions list",
                         45, "on_sanctions_list", hard=True),
                    _ag("trade_layering", "Over-invoicing 60% — value-transfer layering", 35),
                ]),
            AGENT_CS: _sig("trade_based_money_laundering", Domain.RECORD_KEEPING,
                raw={"falsified_trade_docs": True, "invoice_mismatch_pct": 55},
                indicators=[
                    _det("falsified_docs", "Trade documents falsified",
                         30, "is_true", hard=True, field="falsified_trade_docs"),
                    _det("invoice_mismatch", "55% invoice/value mismatch (>25%)",
                         18, "gt", field="invoice_mismatch_pct", value=25),
                    _ag("shell_entity_comms", "Comms consistent with shell-entity coordination", 30),
                ]),
            AGENT_RU: _sig("trade_based_money_laundering", Domain.SANCTIONS_AML,
                raw={"fatf_tbml_typology": True, "linked_entity": "Meridian Shell Holdings"},
                indicators=[
                    _det("fatf_typology", "Matches a FATF TBML typology",
                         25, "is_true", field="fatf_tbml_typology"),
                    _det("linked_sanctioned_entity", "Linked entity on sanctions list",
                         30, "on_sanctions_list", hard=True, field="linked_entity"),
                    _ag("multi_jurisdiction_shells", "Shell network spans multiple jurisdictions", 30),
                ]),
        },
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
