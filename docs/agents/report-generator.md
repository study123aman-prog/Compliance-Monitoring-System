# D5.4 — Report Generator (RG) Agent Specification

| Field | Value |
|---|---|
| **Document ID** | AGENT-RG |
| **Deliverable** | D5 — Agent Specifications |
| **Version** | 1.0.0 · **Date** 2026-08-21 · **Author** Aman Singh |
| **AgentID** | `agent.report_generator` |
| **Related** | [capability-matrix.md](capability-matrix.md) · [../observability/audit-trail.md](../observability/audit-trail.md) · [../escalation/decision-trees/critical-filing-tree.md](../escalation/decision-trees/critical-filing-tree.md) · impl `src/agents/report_generator.py` |

---

## 1. Mandate

Compiles, formats, and distributes compliance reports on schedule and on demand, meeting the format/content/timing needs of compliance committees, senior management, board risk committees, external auditors, and regulators. RG is the System's authority on *how findings are communicated and filed* — it turns consensus outcomes into defensible, audience-appropriate artefacts.

## 2. Capabilities (from spec §Agent 4)

| Capability | Method | Scope |
|---|---|---|
| Scheduled Reports | Template-driven daily/weekly/monthly/quarterly/annual production | All reporting obligations |
| Event-Triggered Reporting | **Sub-15-minute** generation for critical events incl. SAR/STR | Critical events |
| Multi-Audience Adaptation | Adjust detail/terminology/format per audience profile | Board, Mgmt, Ops, Regulator |
| Evidence Compilation | Cross-agent evidence synthesis **with source attribution** | Multi-agent |
| Regulatory Filing Preparation | Generate filing **drafts** (XBRL, XML, PDF) | SAR, STR, CTR, 13F, TRACE, CAT |

**Multi-audience adaptation** is one *finding*, many *renderings*: a board summary leads with risk posture and a single recommendation; a regulator filing carries full evidence and citations; an ops report is granular and actionable. The underlying facts and their hashes are identical across renderings — only depth and framing differ.

## 3. Interface contract

| Direction | Topic | Message | Payload schema |
|---|---|---|---|
| consume | `agent-messages` | consensus outcomes, evidence bundles | `alert.detection.v1` + consensus result |
| consume | `escalations` | resolved cases requiring a filing/report | `escalation.case.v1` |
| produce | report artefacts → distribution + WORM archive | signed PDF/XBRL/XML | — |
| produce | `heartbeats` (Redis) | `HEARTBEAT` | `heartbeat.status.v1` |

## 4. Constraints (spec — binding)

- **Cannot file regulatory reports without human authorisation** — **dual sign-off** required (enforced by the critical-filing tree).
- Report **templates are version-controlled**.
- **Cannot include privileged material** without legal clearance.
- **Distribution lists are controlled** (RBAC).

## 5. Integrity safeguards (anti-"accurate-looking but false" — spec Q)

The spec explicitly asks what prevents RG from producing *accurate-looking reports from fabricated data*. Three safeguards: (1) RG may only cite evidence that carries a **valid hash + source attribution** traceable to an audit-ledger entry — it cannot invent figures; (2) every generated report is itself **hash-chained and signed** into the WORM ledger, so a report's inputs are independently re-derivable; (3) reconciliation reports must reconcile against **event-sourced source-of-record** data, not a mutable summary table — a fabricated input would break the hash chain and fail verification.

## 6. Failure & degradation

Stateless generation from durable inputs; a crash mid-report replays from the consensus/escalation event. If RG is unavailable, critical filings **queue with their SLA clock running** and auto-escalate on breach (they are never dropped), while scheduled reports are regenerated on recovery from the immutable log.

## 7. Scenarios RG leads or co-signs

Produces the outputs for every escalated case; specifically leads the **filing-package generation** in CRITICAL scenarios (CS-01 SAR path, CS-20 coordinated case) and the self-reporting package for enforcement-sweep scenarios. Its integrity safeguards are directly exercised by the fabricated-reconciliation scenario.

---
*End of AGENT-RG v1.0.0*
