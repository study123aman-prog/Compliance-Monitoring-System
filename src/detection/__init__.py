"""
detection — the two-tier compliance detection core.

Pipeline (per agent, per case):

    raw signal ─▶ normalize ─▶ deterministic guardrails ─▶ agentic evaluator ─▶ verdict
                  (stage 1)      (stage 2, fast)            (stage 3, nuanced)

    …and, once per case after consensus/escalation, the HITL router (stage 4)
    decides whether a human must review it.

This package turns the specialist agents from "replay a pre-set opinion" into
"compute an opinion from evidence": each agent runs its raw signal through the
pipeline and forms its severity/confidence from what the rules and the evaluator
actually find. The output is designed to reproduce the locked scenario outcomes
exactly (confidence = risk-score / 100), so the existing consensus, escalation and
audit behaviour — and all existing tests — are preserved.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evaluator import (
    ComplianceEvaluator,
    DeterministicBackend,
    EvaluationResult,
    EvaluatorBackend,
    LLMBackend,
    PolicyStore,
    FLAGGED,
    PASS,
    VIOLATION,
)
from .guardrails import GuardrailEngine, GuardrailResult
from .hitl import HITLQueue, ReviewItem
from .normalization import NormalizedEvent, normalize

__all__ = [
    "DetectionPipeline",
    "DetectionOutcome",
    "ComplianceEvaluator",
    "DeterministicBackend",
    "EvaluatorBackend",
    "LLMBackend",
    "EvaluationResult",
    "PolicyStore",
    "GuardrailEngine",
    "GuardrailResult",
    "HITLQueue",
    "ReviewItem",
    "NormalizedEvent",
    "normalize",
    "PASS",
    "FLAGGED",
    "VIOLATION",
]


@dataclass
class DetectionOutcome:
    """Everything the detection core produced for one agent's signal."""

    event: NormalizedEvent
    guardrails: GuardrailResult
    evaluation: EvaluationResult


class DetectionPipeline:
    """Wires the three per-signal stages (normalize → guardrails → evaluate).

    Stateless and deterministic; a single instance can be shared by all agents.
    The evaluator backend is pluggable (deterministic by default).
    """

    def __init__(
        self,
        guardrails: GuardrailEngine | None = None,
        evaluator: ComplianceEvaluator | None = None,
    ) -> None:
        self.guardrails = guardrails or GuardrailEngine()
        self.evaluator = evaluator or ComplianceEvaluator()

    def run(
        self, correlation_id: str, source_agent: str,
        signal: dict[str, Any], context: dict[str, Any] | None = None,
    ) -> DetectionOutcome:
        """Run one raw signal through the detection core."""

        event = normalize(correlation_id, source_agent, signal)
        indicators = signal.get("indicators", [])
        g = self.guardrails.first_pass(event, indicators)
        evaluation = self.evaluator.evaluate(event, g, indicators, context=context)
        return DetectionOutcome(event=event, guardrails=g, evaluation=evaluation)


#: a shared default pipeline (agents fall back to this when none is injected).
DEFAULT_PIPELINE = DetectionPipeline()
