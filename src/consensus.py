"""
consensus.py — the hybrid consensus / conflict-resolution engine.

Implements ../docs/conflict-resolution/consensus-algorithm.md. Given the set of
agent opinions on one case, it produces a single ConsensusResult
(severity, confidence, plus flags) *deterministically* — the same inputs always
yield the same output, which is what makes the decision auditable and
reproducible (SEC 17a-4 reproducibility requirement).

Three mechanisms, selected explicitly:
  A. Dempster-Shafer combination  -> agreeing / corroborating opinions
  B. Weighted voting              -> genuine conflict (severities differ > 1 level)
  (C. Bayesian sequential update  -> streaming re-evaluation; described in the doc,
      not needed to decide the 20 batch scenarios, so not exercised here.)
Plus a passthrough for a single opinion, and a suppression path when an explicit
benign verification is present (the CS-18 false-positive trap).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .domain import (
    Domain,
    Severity,
    authority,
    confidence_band_severity,
    TAU_ASSERT,
    DELTA_MARGIN,
    KAPPA_CONFLICT,
    SUPPRESSION_THRESHOLD,
)


@dataclass
class Opinion:
    """One agent's assessment of a case.

    `benign=True` marks a *verification* opinion that asserts innocence (commits
    mass to B). Ordinary surveillance opinions never assert innocence — their
    remainder goes to ignorance (Theta), not to benign. This asymmetry is the
    crux of correct false-positive suppression (CS-18).
    """

    agent_id: str
    severity: Severity
    confidence: float
    domain: Domain
    benign: bool = False
    evidence_ref: str = ""
    #: explicit weight override (used by a verification opinion whose authority is
    #: the trustworthiness of the exculpatory record, not a domain-matrix value).
    weight: float | None = None
    #: True for a jurisdictional (C5) conflict that must NOT be auto-resolved.
    no_auto_resolve: bool = False

    def effective_weight(self) -> float:
        """a_i — the Dempster-Shafer discounting factor. Uses the explicit weight
        override if provided, else the domain-authority matrix w_i(domain)."""

        return self.weight if self.weight is not None else authority(self.agent_id, self.domain)

    def mass(self) -> dict[str, float]:
        """Convert to a basic probability assignment over frame {V, B, Theta}.

        - normal opinion:  m(V)=a*c,           m(Theta)=1-a*c
        - benign verifier: m(B)=a*record_conf, m(Theta)=1-a*record_conf
        """

        a = self.effective_weight()
        committed = a * self.confidence
        if self.benign:
            return {"V": 0.0, "B": committed, "T": 1.0 - committed}
        return {"V": committed, "B": 0.0, "T": 1.0 - committed}


@dataclass
class ConsensusResult:
    """Output of the engine for one case."""

    severity: Severity
    confidence: float                       # Belief(V), rounded to 2 dp
    mechanism: str                          # which path decided this
    agents: list[str]                       # agents whose opinions were combined
    suppressed: bool = False                # True => NO_ALERT after verification
    unresolved: bool = False                # True => genuine conflict, escalate to human
    detail: dict[str, Any] = field(default_factory=dict)  # intermediate values for audit


# --------------------------------------------------------------------------- #
#  Dempster's rule of combination over the frame {V, B, Theta}
# --------------------------------------------------------------------------- #
def _intersect(x: str, y: str) -> str | None:
    """Set intersection on the frame. Theta ('T') is the whole frame, so it acts
    as identity; V and B are disjoint singletons, so V∩B = empty (None)."""

    if x == "T":
        return y
    if y == "T":
        return x
    if x == y:
        return x
    return None  # V ∩ B = empty  -> contributes to conflict mass K


def combine(m1: dict[str, float], m2: dict[str, float]) -> tuple[dict[str, float], float]:
    """Combine two mass functions with Dempster's rule.

    Returns (combined_mass, K) where K is the conflict mass. The rule is
    commutative and associative, so combining a list pairwise is order-independent.
    """

    raw: dict[str, float] = {"V": 0.0, "B": 0.0, "T": 0.0}
    conflict = 0.0
    for x, mx in m1.items():
        for y, my in m2.items():
            inter = _intersect(x, y)
            prod = mx * my
            if inter is None:
                conflict += prod
            else:
                raw[inter] += prod
    if conflict >= 1.0:  # total conflict — cannot normalise (should never happen here)
        return {"V": 0.0, "B": 0.0, "T": 1.0}, conflict
    norm = 1.0 - conflict
    return {k: v / norm for k, v in raw.items()}, conflict


class ConsensusEngine:
    """Applies the selection rule of consensus-algorithm.md §4 and returns a
    ConsensusResult. Pure and deterministic: no I/O, no randomness."""

    def resolve(self, opinions: list[Opinion]) -> ConsensusResult:
        if not opinions:
            raise ValueError("no opinions to resolve")

        # ---- Jurisdictional (C5) bypass: NEVER auto-resolve. ----
        # A genuine conflict of laws is not a confidence problem — the machine
        # must not pick a side. Return the asserted severity/confidence verbatim
        # (no band elevation) and flag it unresolved so escalation forces T4+Legal.
        no_resolve = [o for o in opinions if o.no_auto_resolve]
        if no_resolve:
            o = no_resolve[0]
            return ConsensusResult(
                severity=o.severity,
                confidence=round(o.confidence, 2),
                mechanism="jurisdictional_bypass",
                agents=[o.agent_id],
                unresolved=True,
                detail={"reason": "C5 conflict of laws — consensus bypassed, human/legal decides",
                        "confidence_meaning": "confidence that the conflict EXISTS"},
            )

        # ---- Suppression path: an explicit benign verification is present ----
        # (One surveillance opinion + one benign verifier => the CS-18 trap.)
        has_benign = any(o.benign for o in opinions)
        if has_benign:
            return self._suppression_path(opinions)

        # ---- Passthrough: a single opinion ----
        if len(opinions) == 1:
            return self._passthrough(opinions[0])

        # ---- Multi-agent: agreement vs genuine conflict ----
        sev_values = [int(o.severity) for o in opinions]
        if max(sev_values) - min(sev_values) <= 1:
            return self._dempster_agreement(opinions)
        return self._weighted_voting(opinions)

    # ------------------------------------------------------------------ #
    def _passthrough(self, o: Opinion) -> ConsensusResult:
        """Single opinion: use the agent's own calibrated confidence directly.

        The domain weight matters only when *combining* opinions; with one agent
        there is nothing to discount against, so consensus confidence = c.
        """

        conf = round(o.confidence, 2)
        sev = max(o.severity, confidence_band_severity(conf))
        return ConsensusResult(
            severity=sev,
            confidence=conf,
            mechanism="passthrough",
            agents=[o.agent_id],
            detail={"calibrated_confidence": o.confidence},
        )

    # ------------------------------------------------------------------ #
    def _dempster_agreement(self, opinions: list[Opinion]) -> ConsensusResult:
        """Corroboration path: combine masses pairwise with Dempster's rule.

        Two independent, moderately-confident signals should combine into higher
        certainty — the intuition that corroboration increases belief.
        """

        combined = opinions[0].mass()
        masses = [(opinions[0].agent_id, dict(combined))]
        total_conflict = 0.0
        for o in opinions[1:]:
            combined, k = combine(combined, o.mass())
            total_conflict += k
            masses.append((o.agent_id, o.mass()))

        belief_v = round(combined["V"], 2)

        # Resolved severity = worst credible asserted severity, floored by the
        # confidence band (so corroboration can raise, never lower, severity).
        credible = [o for o in opinions if o.effective_weight() * o.confidence >= TAU_ASSERT]
        asserted = max((o.severity for o in credible), default=Severity.NO_ALERT)
        sev = max(asserted, confidence_band_severity(belief_v))

        return ConsensusResult(
            severity=sev,
            confidence=belief_v,
            mechanism="dempster_shafer",
            agents=[o.agent_id for o in opinions],
            detail={
                "input_masses": {aid: {k: round(v, 4) for k, v in m.items()} for aid, m in masses},
                "belief_V": round(combined["V"], 4),
                "belief_B": round(combined["B"], 4),
                "ignorance_T": round(combined["T"], 4),
                "conflict_K": round(total_conflict, 4),
                "asserted_severity": asserted.name,
            },
        )

    # ------------------------------------------------------------------ #
    def _weighted_voting(self, opinions: list[Opinion]) -> ConsensusResult:
        """Genuine-conflict path: severities differ by more than one level.

        Weighted votes per severity class; accept the winner only if it wins by a
        clear margin AND the two leading opinions are not too conflicting. Else the
        case is UNRESOLVED and must go to a human at the *higher*-severity tier —
        the legally safe default.
        """

        scores: dict[Severity, float] = {}
        for o in opinions:
            scores[o.severity] = scores.get(o.severity, 0.0) + o.effective_weight() * o.confidence
        total = sum(scores.values()) or 1.0
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        winner, win_score = ranked[0]
        runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = (win_score - runner_up) / total

        # Conflict K between the two leading opinions (highest vs lowest severity).
        hi = max(opinions, key=lambda o: (o.severity, o.confidence))
        lo = min(opinions, key=lambda o: (o.severity, o.confidence))
        _, k = combine(hi.mass(), lo.mass())

        if margin >= DELTA_MARGIN and k <= KAPPA_CONFLICT:
            conf = round(win_score / total, 2)
            return ConsensusResult(
                severity=max(winner, confidence_band_severity(conf)),
                confidence=conf,
                mechanism="weighted_voting",
                agents=[o.agent_id for o in opinions],
                detail={"scores": {s.name: round(v, 4) for s, v in scores.items()},
                        "margin": round(margin, 4), "conflict_K": round(k, 4)},
            )
        # Unresolved: escalate at the higher-severity opinion's level.
        higher = max(o.severity for o in opinions)
        return ConsensusResult(
            severity=higher,
            confidence=round(win_score / total, 2),
            mechanism="weighted_voting_unresolved",
            agents=[o.agent_id for o in opinions],
            unresolved=True,
            detail={"margin": round(margin, 4), "conflict_K": round(k, 4),
                    "reason": "margin<delta or K>kappa -> human decides"},
        )

    # ------------------------------------------------------------------ #
    def _suppression_path(self, opinions: list[Opinion]) -> ConsensusResult:
        """CS-18: combine the surveillance opinion(s) with the benign verifier.

        If authenticated benign mass pulls Belief(V) below the suppression
        threshold, the result is NO_ALERT / suppressed — but the *reasoning*
        (this computation) is returned so it can be written to the audit trail.
        Suppression is never a silent drop.
        """

        combined = opinions[0].mass()
        for o in opinions[1:]:
            combined, _ = combine(combined, o.mass())
        belief_v = combined["V"]

        if belief_v < SUPPRESSION_THRESHOLD:
            return ConsensusResult(
                severity=Severity.NO_ALERT,
                confidence=round(belief_v, 2),
                mechanism="suppressed_after_verification",
                agents=[o.agent_id for o in opinions if not o.benign],
                suppressed=True,
                detail={
                    "belief_V": round(combined["V"], 4),
                    "belief_B": round(combined["B"], 4),
                    "ignorance_T": round(combined["T"], 4),
                    "threshold": SUPPRESSION_THRESHOLD,
                    "note": "authenticated benign verification dominates -> NO_ALERT",
                },
            )
        # Residual suspicion survived verification -> treat as a normal detection.
        surviving = [o for o in opinions if not o.benign]
        result = (self._passthrough(surviving[0]) if len(surviving) == 1
                  else self._dempster_agreement(surviving))
        result.detail["note"] = "verification did not clear residual suspicion"
        return result
