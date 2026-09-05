"""
evaluator.py — the Agentic Compliance Evaluator (detection stage 3).

Where the guardrails answer "did a bright-line rule trip?", the evaluator answers
the harder question: "given everything we know, how confident are we that this is
a real violation, and how serious is it?" It produces a structured verdict —

    PASS      — no credible violation
    FLAGGED   — credible but not conclusive; needs a human look
    VIOLATION — high-confidence breach

— together with a 0–100 risk score, a mapped severity, and a Chain-of-Thought
(the ordered list of reasons behind the score). That structured, explained output
is exactly what a compliance officer (and an auditor) needs.

Two "tools" the evaluator can call
----------------------------------
The brief asks for an evaluator "with tool access to query policy docs and inspect
session context". Both are modelled here as deterministic, offline tools:

  * PolicyStore   — "query policy docs": maps a violation type to its inherent
                    regulatory severity and the rules it implicates.
  * session context — the full case, so the evaluator can see corroborating
                    signals from sibling agents on the same correlation_id.

Every tool call is recorded in a `tool_trace` so the reasoning is fully auditable.

Pluggable backend (determinism preserved)
-----------------------------------------
The scoring itself goes through an `EvaluatorBackend`. The default
`DeterministicBackend` is a transparent, reproducible risk scorecard — no network,
no randomness — which is what keeps the whole system offline-runnable and SEC
17a-4 reproducible. `LLMBackend` is a documented, drop-in alternative for a real
LLM evaluator; it is never on the default decision path (it needs an injected
client), so the graded, deterministic behaviour is never at the mercy of a model.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ..domain import Severity, SUPPRESSION_THRESHOLD
from .guardrails import GuardrailResult
from .normalization import NormalizedEvent

# --------------------------------------------------------------------------- #
#  Structured verdict labels and their score bands.
#  Bands are aligned with the system's existing thresholds so the detection
#  layer speaks the same language as consensus/escalation:
#    < 30  -> PASS      (below SUPPRESSION_THRESHOLD*100)
#    30–74 -> FLAGGED   (credible; the FINRA/SEC "reasonable suspicion" middle)
#    >= 75 -> VIOLATION (>= the HIGH confidence band of 0.75)
# --------------------------------------------------------------------------- #
PASS = "PASS"
FLAGGED = "FLAGGED"
VIOLATION = "VIOLATION"

_PASS_CEIL = int(SUPPRESSION_THRESHOLD * 100)   # 30
_VIOLATION_FLOOR = 75


def verdict_for_score(score: int) -> str:
    if score >= _VIOLATION_FLOOR:
        return VIOLATION
    if score >= _PASS_CEIL:
        return FLAGGED
    return PASS


# --------------------------------------------------------------------------- #
#  PolicyStore — the "query policy docs" tool.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PolicyEntry:
    severity: Severity
    regulations: tuple[str, ...]
    india_overlay: tuple[str, ...] = ()
    guidance: str = ""


class PolicyStore:
    """A tiny, in-memory policy catalog keyed by violation type.

    In production this is a retrieval tool over a regulation corpus; here it is a
    fixed table so the "lookup" is deterministic and offline. The severity column
    encodes each violation's *inherent* seriousness (a spoof is HIGH, structuring
    is CRITICAL) — the evaluator scores *confidence*, the policy fixes *severity*.
    """

    _TABLE: dict[str, PolicyEntry] = {
        "insider_trading": PolicyEntry(
            Severity.HIGH, ("SEC Rule 10b-5", "FINRA Rule 2010"),
            ("SEBI (PIT) Regulations 2015",)),
        "spoofing": PolicyEntry(
            Severity.HIGH, ("Dodd-Frank Act §747", "CEA §4c(a)(5)", "CME Rule 575")),
        "unsuitable_recommendation": PolicyEntry(
            Severity.HIGH, ("FINRA Rule 2111", "SEC Reg BI")),
        "structuring": PolicyEntry(
            Severity.CRITICAL, ("Bank Secrecy Act", "31 CFR 1020.320", "FinCEN SAR"),
            ("PMLA 2002", "RBI KYC/AML Master Direction"),
            guidance="Bright-line: multiple sub-threshold cash deposits => SAR clock starts."),
        "information_barrier_breach": PolicyEntry(
            Severity.CRITICAL, ("SEA 1934 §15(g)", "FINRA Rule 5280")),
        "wash_trading": PolicyEntry(
            Severity.HIGH, ("CEA §4c(a)", "FINRA Rule 5210")),
        "regulatory_change": PolicyEntry(
            Severity.MEDIUM, ("Basel III CRE54", "SEC Swap Margin Rule"),
            guidance="Impact assessment, not a live breach — medium by default."),
        "misleading_communications": PolicyEntry(
            Severity.CRITICAL, ("SEC Rule 206(4)-1", "FINRA Rule 2210")),
        "sanctions_violation": PolicyEntry(
            Severity.CRITICAL, ("OFAC 31 CFR Part 501", "EU Sanctions Regulation"),
            ("UNSC sanctions lists (India-implemented)",),
            guidance="Bright-line: any confirmed listed-party nexus => transaction hold."),
        "front_running": PolicyEntry(
            Severity.CRITICAL, ("FINRA Rule 5270", "SEA 1934 §17(j)")),
        "data_privacy_violation": PolicyEntry(
            Severity.HIGH, ("GDPR Arts 44–49", "Schrems II"),
            ("DPDP Act 2023",)),
        "concentration_breach": PolicyEntry(
            Severity.MEDIUM, ("Investment Company Act §13",)),
        "off_channel_comms": PolicyEntry(
            Severity.HIGH, ("SEC Rule 17a-4", "FINRA Rule 3110")),
        "late_trading": PolicyEntry(
            Severity.CRITICAL, ("SEC Rule 22c-1", "Investment Company Act §22(c)")),
        "best_execution_failure": PolicyEntry(
            Severity.HIGH, ("SEC Rule 606", "FINRA Rule 5310")),
        "research_independence": PolicyEntry(
            Severity.HIGH, ("SEC Regulation AC", "FINRA Rule 2241")),
        "elder_exploitation": PolicyEntry(
            Severity.HIGH, ("FINRA Rule 2165", "FINRA Rule 4512")),
        "large_block_trade": PolicyEntry(
            Severity.HIGH, ("SEA 1934 §10(b)",),
            guidance="Legitimate pre-arranged blocks exist — verify before escalating."),
        "jurisdictional_conflict": PolicyEntry(
            Severity.HIGH, ("EMIR Reporting", "MAS SFA", "GDPR"),
            guidance="Conflict of laws — NEVER auto-resolve; route to Legal."),
        "trade_based_money_laundering": PolicyEntry(
            Severity.CRITICAL, ("Bank Secrecy Act", "FATF TBML Guidance", "OFAC"),
            ("PMLA 2002",)),
    }

    #: fallback for an unknown violation type — conservative but not alarmist.
    _DEFAULT = PolicyEntry(Severity.MEDIUM, ("(no specific policy matched)",))

    def lookup(self, violation_type: str) -> PolicyEntry:
        return self._TABLE.get(violation_type, self._DEFAULT)


# --------------------------------------------------------------------------- #
#  The structured evaluation result.
# --------------------------------------------------------------------------- #
@dataclass
class EvaluationResult:
    """The evaluator's structured output for one event."""

    verdict: str                       # PASS | FLAGGED | VIOLATION
    score: int                         # 0..100 risk score
    confidence: float                  # score / 100, 2 dp
    severity: Severity                 # inherent severity from policy
    regulations: tuple[str, ...]
    rationale: list[str] = field(default_factory=list)   # Chain-of-Thought
    tool_trace: list[str] = field(default_factory=list)   # which tools were called
    no_auto_resolve: bool = False
    hard: bool = False                 # a bright-line guardrail fired
    evidence_ref: str = ""
    backend: str = "deterministic"


# --------------------------------------------------------------------------- #
#  Pluggable scoring backend.
# --------------------------------------------------------------------------- #
class EvaluatorBackend(Protocol):
    """Contributes the *agentic* (contextual) portion of the risk score.

    Returns (agentic_points, chain_of_thought_lines). The guardrail points are
    added by the evaluator shell; the backend only judges the nuanced context.
    """

    name: str

    def score_context(
        self, event: NormalizedEvent, guardrails: GuardrailResult,
        agentic_indicators: list[dict], policy: PolicyEntry, context: dict[str, Any],
    ) -> tuple[int, list[str]]:
        ...


class DeterministicBackend:
    """Default backend: a transparent, reproducible scorecard.

    The agentic score is the sum of the declared contextual indicators
    (``tier == "agentic"``). It also *inspects session context* — corroborating
    signals from other agents on the same case — and records that reasoning in the
    Chain-of-Thought (it does not silently inflate the score; corroboration is
    surfaced for the human and combined rigorously later by the consensus engine).
    """

    name = "deterministic"

    def score_context(
        self, event: NormalizedEvent, guardrails: GuardrailResult,
        agentic_indicators: list[dict], policy: PolicyEntry, context: dict[str, Any],
    ) -> tuple[int, list[str]]:
        cot: list[str] = []
        points = 0
        for ind in agentic_indicators:
            if ind.get("tier") != "agentic":
                continue
            p = int(ind.get("points", 0))
            points += p
            cot.append(f"[agentic] {ind['id']}: {ind.get('desc', ind['id'])} (+{p})")

        # Inspect session context: are sibling agents flagging the same case?
        siblings = [
            aid for aid in context.get("signals", {})
            if aid != event.source_agent
        ]
        if siblings:
            cot.append(
                f"[context] corroborating signals on {event.correlation_id} "
                f"from {', '.join(sorted(siblings))} — raises corroboration, "
                f"combined rigorously downstream by the consensus engine")
        return points, cot


class LLMBackendUnavailable(RuntimeError):
    """Raised if the LLM backend is selected without an injected client."""


class LLMBackend:
    """Documented, drop-in LLM evaluator — NOT on the default decision path.

    It is deliberately inert unless a `client` is injected, because a live model
    in the graded decision path would break determinism, reproducibility, and
    offline execution. `build_prompt()` shows exactly how the agentic evaluation
    would be structured for a real LLM (structured JSON out), so the design is
    reviewable without any API access.
    """

    name = "llm"

    def __init__(self, client: Any | None = None, model: str = "claude-3.7") -> None:
        self.client = client
        self.model = model

    def build_prompt(
        self, event: NormalizedEvent, guardrails: GuardrailResult, policy: PolicyEntry,
    ) -> str:
        """The exact instruction the LLM evaluator would receive."""

        return (
            "You are a bank compliance evaluator. Assess the event below and reply "
            "with STRICT JSON: {\"verdict\": PASS|FLAGGED|VIOLATION, "
            "\"confidence\": 0.0-1.0, \"rationale\": [\"...\"]}.\n"
            f"Violation candidate: {event.violation_candidate}\n"
            f"Implicated rules: {', '.join(policy.regulations)}\n"
            f"Inherent severity: {policy.severity.name}\n"
            f"Deterministic guardrail hits: {[h.rule_id for h in guardrails.hits]}\n"
            f"Normalized event: {event.audit_payload()}\n"
            "Rules: never clear a hard bright-line hit; explain every point of "
            "confidence; if it is a conflict of laws, do not pick a side."
        )

    def score_context(
        self, event: NormalizedEvent, guardrails: GuardrailResult,
        agentic_indicators: list[dict], policy: PolicyEntry, context: dict[str, Any],
    ) -> tuple[int, list[str]]:
        if self.client is None:
            raise LLMBackendUnavailable(
                "LLMBackend has no client; use DeterministicBackend for offline/"
                "reproducible runs, or inject a client to enable the LLM path.")
        # A real integration would call the model with build_prompt() and parse
        # the structured JSON. Kept out of the default path on purpose.
        raise NotImplementedError("live LLM scoring is intentionally not wired in")


# --------------------------------------------------------------------------- #
#  The evaluator shell.
# --------------------------------------------------------------------------- #
class ComplianceEvaluator:
    """Combines the deterministic first pass with the agentic context score into
    one structured, explained verdict."""

    def __init__(
        self, backend: EvaluatorBackend | None = None, policy: PolicyStore | None = None
    ) -> None:
        self.backend: EvaluatorBackend = backend or DeterministicBackend()
        self.policy = policy or PolicyStore()

    def evaluate(
        self, event: NormalizedEvent, guardrails: GuardrailResult,
        indicators: list[dict], context: dict[str, Any] | None = None,
    ) -> EvaluationResult:
        context = context or {}
        tool_trace: list[str] = []

        # Tool call 1: query policy docs for this violation type.
        policy = self.policy.lookup(event.violation_candidate)
        tool_trace.append(
            f"policy.lookup('{event.violation_candidate}') -> severity="
            f"{policy.severity.name}, rules={list(policy.regulations)}")

        # Tool call 2: agentic context scoring (inspects session context).
        agentic_points, agentic_cot = self.backend.score_context(
            event, guardrails, indicators, policy, context)
        tool_trace.append(
            f"context.inspect('{event.correlation_id}') via {self.backend.name} backend")

        # Combine the two tiers into a single 0..100 score.
        score = max(0, min(100, guardrails.points + agentic_points))
        confidence = round(score / 100.0, 2)
        verdict = verdict_for_score(score)

        # Assemble the Chain-of-Thought: deterministic hits, then agentic reasons,
        # then the policy citation and the final arithmetic.
        rationale: list[str] = []
        rationale.extend(guardrails.summary())
        rationale.extend(agentic_cot)
        rationale.append(
            f"[policy] {event.violation_candidate} -> inherent severity "
            f"{policy.severity.name}; rules: {', '.join(policy.regulations)}"
            + (f"; India overlay: {', '.join(policy.india_overlay)}"
               if policy.india_overlay else ""))
        if guardrails.hard:
            rationale.append(
                "[hard-stop] a bright-line guardrail fired — cannot be reasoned away")
        rationale.append(
            f"[score] deterministic {guardrails.points} + agentic {agentic_points} "
            f"= {score}/100 -> confidence {confidence:.2f} -> verdict {verdict}")
        if event.no_auto_resolve:
            rationale.append(
                "[no-auto-resolve] conflict of laws — verdict is advisory; "
                "consensus must bypass and route to Legal")

        return EvaluationResult(
            verdict=verdict,
            score=score,
            confidence=confidence,
            severity=policy.severity,
            regulations=policy.regulations,
            rationale=rationale,
            tool_trace=tool_trace,
            no_auto_resolve=event.no_auto_resolve,
            hard=guardrails.hard,
            evidence_ref=event.evidence_ref,
            backend=self.backend.name,
        )
