# D5.2 — Communication Scanner (CS) Agent Specification

| Field | Value |
|---|---|
| **Document ID** | AGENT-CS |
| **Deliverable** | D5 — Agent Specifications |
| **Version** | 1.0.0 · **Date** 2026-08-21 · **Author** Aman Singh |
| **AgentID** | `agent.communication_scanner` |
| **Related** | [capability-matrix.md](capability-matrix.md) · [../architecture/security-architecture.md](../architecture/security-architecture.md) · impl `src/agents/communication_scanner.py` |

> **Naming note.** This agent is the *Communication Scanner*. The scenario identifiers `CS-01…CS-20` are unrelated — "CS" there is the assessment's scenario prefix, not this agent. See [../../src/domain.py](../../src/domain.py).

---

## 1. Mandate

Monitors all internal/external communication — email, IM, voice/video transcripts, social posts, client-facing documents — for compliance violations, while balancing surveillance against **privacy (GDPR, CCPA, India DPDP)** and **legal privilege**. CS is the System's authority on *intent and content* (`w=0.95` for communications, `0.90` for record-keeping).

## 2. Capabilities (from spec §Agent 2)

| Capability | Method | Scope |
|---|---|---|
| Keyword & Phrase Detection | Configurable multilingual lexicons + code-word/euphemism models | English, Mandarin, Hindi, Spanish min. |
| Sentiment & Intent Analysis | Classifiers for coercion, misleading statements, unsuitable recommendations, pressure tactics | All customer-facing channels |
| Information-Barrier Monitoring | Cross-departmental graph to detect Chinese-wall breaches | Public ↔ private side |
| Record-Keeping Compliance | Verify regulated comms are captured/retained; **detect absence** of expected comms | SEC 17a-4, MiFID II, FCA SYSC |
| Privilege Detection | Flag attorney-client / work-product for special handling | Privileged material |

**Detecting absence (spec Q, CS-16-style).** Record-keeping compliance includes flagging the *gap* — expected communications that never arrived (a trader who suddenly goes silent on monitored channels while trading spikes), by comparing observed comms volume against an expected baseline conditioned on trading activity.

## 3. Interface contract

| Direction | Topic | Message | Payload schema |
|---|---|---|---|
| consume | `communications` | comm events (already captured/retained) | `comm.event.v1` |
| consume | `agent-messages` | `QUERY` | `query.corroboration.v1` |
| produce | `agent-messages` | `ALERT`, `RESPONSE` | `alert.detection.v1`, `response.corroboration.v1` |
| produce | `heartbeats` (Redis) | `HEARTBEAT` | `heartbeat.status.v1` |

Evidence bundles carry **excerpts and references**, not full message bodies, and are tagged with privacy/privilege classifications so downstream handling respects the constraints below.

## 4. Constraints (spec — binding)

- **Cannot decrypt end-to-end encrypted** communications; voice limited to transcribed text.
- Must respect **data-retention boundaries** and apply **privacy-preserving** analysis to inadvertently-captured personal comms.
- **Cannot independently determine legal privilege** — flags for human/legal review (feeds the C5/Legal path).
- India PII (Aadhaar/eKYC) is **tokenised** before analysis; personal data stays within India (RBI localisation) — see [security-architecture.md](../architecture/security-architecture.md).

## 5. Failure & degradation

Stateless per message; lexicons/models loaded from a versioned config store (a `regulatory-updates` `UPDATE` can push a new lexicon version). On outage, comms-domain coverage is marked degraded and TM-only cases proceed with the missing-corroboration flag set, so consensus knows CS's silence is *absence of evidence*, not *evidence of absence*.

## 6. Scenarios CS leads or co-signs

Leads communications/record-keeping scenarios: off-channel/record-keeping (JPMorgan-style industry sweep), misleading statements, coercion/pressure, information-barrier breaches, undisclosed related-party meetings, whistleblower suppression, and the **absence-of-communication** case. Co-signs CS-01 (supplies the corroborating dinner-email linkage that lifts TM's HIGH to a CRITICAL consensus) and the coordinated CS-20.

---
*End of AGENT-CS v1.0.0*
