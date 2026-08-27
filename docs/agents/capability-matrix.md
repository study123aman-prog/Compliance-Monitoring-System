# D5.5 — Agent Capability Matrix

| Field | Value |
|---|---|
| **Document ID** | AGENT-CAPABILITY-MATRIX |
| **Deliverable** | D5 — Agent Specifications |
| **Version** | 1.0.0 · **Date** 2026-08-21 · **Author** Aman Singh |
| **Related** | [transaction-monitor.md](transaction-monitor.md) · [communication-scanner.md](communication-scanner.md) · [regulatory-tracker.md](regulatory-tracker.md) · [report-generator.md](report-generator.md) · [../conflict-resolution/consensus-algorithm.md](../conflict-resolution/consensus-algorithm.md) |

---

## 1. Purpose

A single cross-cutting view of *who does what, who defers to whom, and where responsibilities overlap*. This matrix is the reconciliation point for the four agent specs and the [domain-authority matrix](../conflict-resolution/consensus-algorithm.md) used by the consensus engine.

## 2. Capability ownership

**Legend:** ● primary owner · ○ contributor/corroborator · — not in scope.

| Capability domain | TM | CS | RU | RG |
|---|:--:|:--:|:--:|:--:|
| Trading-pattern detection | ● | ○ | — | — |
| Communications content & intent | — | ● | — | — |
| Record-keeping / off-channel (incl. *absence* detection) | ○ | ● | — | — |
| Information-barrier (Chinese-wall) monitoring | — | ● | — | — |
| Regulatory-change detection & impact | — | — | ● | — |
| Cross-jurisdiction conflict (C5) | — | — | ● | — |
| Sanctions / AML (shared) | ○ | ○ | ● | — |
| Threshold calibration from precedent | ○ | ○ | ● | — |
| Evidence compilation & source attribution | ○ | ○ | ○ | ● |
| Multi-audience reporting & regulatory filing | — | — | — | ● |

## 3. Domain-authority weights (whose opinion counts most)

These are the exact `w_i(d)` values the consensus engine applies (mirrors [consensus §3](../conflict-resolution/consensus-algorithm.md) — kept in one place to prevent drift).

| Domain *d* | TM | CS | RU |
|---|:--:|:--:|:--:|
| Trading patterns | **0.95** | 0.20 | 0.30 |
| Communications content/intent | 0.15 | **0.95** | 0.25 |
| Record-keeping / off-channel | 0.35 | **0.90** | 0.30 |
| Regulatory change / cross-jurisdiction | 0.30 | 0.30 | **0.95** |
| Sanctions / AML (shared) | 0.70 | 0.40 | 0.75 |

RG does not carry a detection authority weight — it reports consensus outcomes, it does not vote on them.

## 4. Shared responsibilities & who arbitrates

| Overlap | Agents | Arbitration |
|---|---|---|
| Insider trading (trade + intent) | TM (trade) + CS (comms linkage) | Dempster–Shafer corroboration; TM authority on the trade, CS on the intent |
| Sanctions / AML | TM + RU (+ CS for comms) | Shared weights; if they conflict, weighted voting then escalate |
| Related-party / undisclosed meetings | TM (circular trades) + CS (meeting comms) | Union of findings; RG reports both |
| Off-channel comms during trading spike | TM (spike) + CS (comms gap) | CS leads (record-keeping authority); TM corroborates timing |

When authorities are close and opinions diverge, the [selection rule](../conflict-resolution/consensus-algorithm.md) decides the mechanism, and unresolved close calls escalate at the **higher-severity** tier.

## 5. Constraint summary (spec-binding boundaries)

| Agent | Cannot (autonomy limit) | Must (obligation) |
|---|---|---|
| TM | access raw comms; halt trading | calibrate confidence; sub-second latency |
| CS | decrypt E2E; determine privilege | privacy-preserving analysis; respect retention |
| RU | give legal interpretation; modify rules | human-validated impact; official sources only |
| RG | file without dual sign-off; include privileged w/o clearance | version-controlled templates; source-attributed evidence |

Every "cannot" is a deliberate human-in-the-loop boundary: the agents detect and recommend; humans decide and authorise.

## 6. Coverage vs the 20 scenarios (lead agent)

| Lead | Scenarios (indicative) |
|---|---|
| TM | trading manipulation, spoofing/layering, wash, front-running, late trading, concentration/synthetic exposure |
| CS | off-channel/record-keeping, misleading statements, coercion, info-barrier, absence-of-comms, whistleblower suppression |
| RU | regulatory change, cross-jurisdiction conflict (CS-19), enforcement-sweep integration |
| TM+CS | insider trading (CS-01), related-party meetings |
| all four | coordinated multi-violation case (CS-20) |
| TM→suppressed | false-positive block trade (CS-18) |

Per-scenario end-to-end traces are in [../../tests/scenarios/](../../tests/scenarios/).

---
*End of AGENT-CAPABILITY-MATRIX v1.0.0*
