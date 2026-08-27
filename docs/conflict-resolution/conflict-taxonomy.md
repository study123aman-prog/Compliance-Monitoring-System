# D3.2 — Conflict Taxonomy

| Field | Value |
|---|---|
| **Document ID** | CONFLICT-TAXONOMY |
| **Deliverable** | D3 — Conflict Resolution and Consensus Algorithm |
| **Version** | 1.0.0 |
| **Date** | 2026-08-21 |
| **Author** | Aman Singh |
| **Status** | Baseline |
| **Related** | [consensus-algorithm.md](consensus-algorithm.md) · [../escalation/escalation-framework.md](../escalation/escalation-framework.md) |

---

## 1. Purpose

Before you can *resolve* a conflict you must *classify* it. This taxonomy names every kind of inter-agent (and agent-vs-system) disagreement the System can encounter, gives a real example of each, and states how the consensus algorithm and escalation framework respond. It is the companion to [consensus-algorithm.md](consensus-algorithm.md).

## 2. Conflict classes

| # | Conflict class | Definition | Example | Default handling |
|---|---|---|---|---|
| C1 | **Severity disagreement** | Agents agree a violation exists but differ on severity | TM: HIGH wash-trading; CS: MEDIUM (weak intent signal) | Weighted voting; if agree within 1 level, DS corroboration |
| C2 | **Existence disagreement** | One agent asserts violation, another asserts benign | TM: CRITICAL concentration; risk-system view: within limits (Archegos) | Weighted voting + conflict test; usually UNRESOLVED → escalate |
| C3 | **Classification disagreement** | Agents agree something is wrong but differ on *what* | CS: unsuitable recommendation; TM: churning | Keep both violation types; escalate the union; RG reports both |
| C4 | **Confidence disagreement** | Same severity, very different confidence | TM 0.85 vs CS 0.35 on the same pattern | DS combination; low-confidence agent's mass is discounted by authority |
| C5 | **Jurisdictional conflict** | Two regulations demand contradictory actions | EU: must report OTC in 1 day; SG: must not share cross-border (CS-19) | RU flags; NOT auto-resolved → legal counsel (Tier 4 + Legal) |
| C6 | **Temporal conflict** | Streaming lane and batch lane disagree after recompute | Streaming flags spoofing; batch says cancels were legitimate | Bayesian update; batch (more complete) evidence weighted higher |
| C7 | **Authority-vs-override conflict** | An agent flags; an authorised human/system overrode a control | RM overrode sanctions screening twice (CS-20) | The **override itself** is a compliance event; escalate regardless |
| C8 | **False-positive suppression conflict** | Detection fired but verification says benign | Legitimate pre-arranged block trade (CS-18) | Verification agent commits `{B}` mass; suppress with documented reasoning |

## 3. Escalation criteria for conflicts

A conflict escalates to a human when **any** of these holds (from the consensus decision rule):

- Weighted-voting margin `< 0.20` (too close to call automatically), **or**
- Dempster conflict `K > 0.60` (agents strongly contradict — the combination is unreliable), **or**
- The conflict is class **C5 (jurisdictional)** or **C7 (override)** — these are *never* auto-resolved because they carry legal/conduct implications, **or**
- Either opinion is CRITICAL severity (any CRITICAL always reaches Tier 4).

The escalation tier follows the **higher-severity** opinion in the conflict (conservative bias). This guarantees the "one catches a violation but another disagrees" situation always defaults toward human review rather than silent suppression.

## 4. Worked mini-examples

**C2 (Archegos-style, existence disagreement).** TM sees synthetic exposure aggregated across prime brokers → CRITICAL concentration (c=0.82, a=0.95 → 0.78). A single-broker risk view says "within limits" → NO_ALERT (c=0.70, a=0.60 → 0.42, benign mass). Weighted vote: V-score 0.78 vs B-score 0.42, margin = (0.78−0.42)/1.20 = 0.30 ≥ 0.20, **but** one opinion is CRITICAL → mandatory Tier-4 escalation regardless of margin. The design lesson from Archegos: a "within limits" signal from a *partial* view must never silence a CRITICAL from a *complete* view.

**C8 (false positive, CS-18).** TM flags a $450M block trade as anomalous volume (c=0.68). A verification step checks the block-desk pre-arrangement record + disclosed rebalancing mandate and returns explicit benign evidence: `m({B}) = 0.9·0.9 = 0.81`, `m({V})` from TM = 0.646. Dempster combination is dominated by the benign mass once the exculpatory record is authenticated → Belief(V) collapses below the suppression threshold → **NO_ALERT**, with the reasoning (which record, which mandate) written to the audit trail. Suppression is a *documented* decision, not a silent drop.

## 5. Conflict audit trail

Every conflict resolution records: the class (C1–C8), all agent opinions with weights, the mechanism used, intermediate values (masses, scores, margin, K), the outcome, and — if escalated — the tier and reason. The Operational Intelligence dashboard aggregates conflict frequency and resolution patterns by class and root cause ([../observability/monitoring-dashboard.md](../observability/monitoring-dashboard.md)), so leadership can see *which* agent boundaries produce the most disagreement and recalibrate.

---
*End of CONFLICT-TAXONOMY v1.0.0*
