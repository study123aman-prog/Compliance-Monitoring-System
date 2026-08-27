# D5.3 — Regulatory Update Tracker (RU) Agent Specification

| Field | Value |
|---|---|
| **Document ID** | AGENT-RU |
| **Deliverable** | D5 — Agent Specifications |
| **Version** | 1.0.0 · **Date** 2026-08-21 · **Author** Aman Singh |
| **AgentID** | `agent.regulatory_tracker` |
| **Related** | [capability-matrix.md](capability-matrix.md) · [../escalation/decision-trees/jurisdictional-conflict-tree.md](../escalation/decision-trees/jurisdictional-conflict-tree.md) · impl `src/agents/regulatory_tracker.py` |

---

## 1. Mandate

Continuous monitoring of the regulatory landscape across all operating jurisdictions — new regulations, amendments, enforcement actions, guidance, no-action letters, consultation papers — and assessment of each change's **impact** on the existing compliance framework, triggering update workflows. RU is the System's authority on *what the rules are* (`w=0.95` for regulatory change/interpretation/cross-jurisdiction).

## 2. Capabilities (from spec §Agent 3)

| Capability | Method | Scope |
|---|---|---|
| Regulatory Feed Monitoring | Continuous ingest of regulator publications, Federal Register, official gazettes | SEC, FINRA, OCC, FCA, ECB, MAS, HKMA, ASIC, JFSA min. |
| Impact Assessment | Automated **preliminary** policy-mapping, procedure gap analysis, system-impact tagging | Policy/procedure/system |
| Timeline Extraction | Extract deadlines, comment periods, phase-in schedules; calendar alerts at **180/90/60/30/14 days** | Calendar integration |
| Cross-Regulation Conflict | Detect conflicts between jurisdictions (the C5 detector) | Multi-jurisdictional conflict matrix |
| Precedent Analysis | Mine 10 years of enforcement/settlements to **calibrate detection thresholds** | Historical enforcement DB |

**Precedent → calibration.** RU's precedent analysis is a primary input to the feedback loop: settlements and enforcement sweeps recalibrate TM/CS thresholds (e.g. an off-channel-comms sweep tightens CS record-keeping sensitivity industry-wide).

## 3. Interface contract

| Direction | Topic | Message | Payload schema |
|---|---|---|---|
| consume | external regulatory feeds (connectors) | publications | `reg.feed.v1` |
| produce | `regulatory-updates` | `UPDATE` (broadcast to all agents) | `update.regulatory.v1` |
| produce | `agent-messages` | `ALERT` (e.g. C5 conflict), `RESPONSE` | `alert.detection.v1` |
| produce | `heartbeats` (Redis) | `HEARTBEAT` | `heartbeat.status.v1` |

An `UPDATE` may recalibrate another agent's thresholds/lexicons; these are **versioned and human-approved** before taking effect in production (no silent auto-mutation — preserves determinism).

## 4. Constraints (spec — binding)

- **Cannot provide legal interpretations** of ambiguous language — impact assessments are **preliminary and require human validation**.
- **Cannot independently modify compliance rules** — proposes; humans approve.
- Coverage **limited to official sources**.
- Detected cross-jurisdiction conflicts (C5) are **never auto-resolved** — routed to T4 + Legal (see the jurisdictional-conflict tree).

## 5. Failure & degradation

RU maintains slowly-changing reference state (the current rule set), which is event-sourced and rebuildable from the `regulatory-updates` log. If RU is offline, detection continues against the **last-known-good** rule set (flagged as potentially stale), and new-regulation detection is marked degraded — the System never blocks surveillance because the rule tracker is down.

## 6. Scenarios RU leads or co-signs

Leads the regulatory-change and cross-jurisdiction scenarios — notably **CS-19** (contradictory cross-border obligations → C5 → Legal) and the integration of enforcement-sweep intelligence into detection thresholds (industry-wide off-channel sweep). Co-signs sanctions/AML cases (shared authority `w=0.75`) and supplies the applicable-regulation citations in every escalation's decision-support package.

---
*End of AGENT-RU v1.0.0*
