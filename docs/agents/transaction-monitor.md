# D5.1 — Transaction Monitor (TM) Agent Specification

| Field | Value |
|---|---|
| **Document ID** | AGENT-TM |
| **Deliverable** | D5 — Agent Specifications |
| **Version** | 1.0.0 · **Date** 2026-08-21 · **Author** Aman Singh |
| **AgentID** | `agent.transaction_monitor` |
| **Related** | [capability-matrix.md](capability-matrix.md) · [../architecture/agent-registry.md](../architecture/agent-registry.md) · [../conflict-resolution/consensus-algorithm.md](../conflict-resolution/consensus-algorithm.md) · impl `src/agents/transaction_monitor.py` |

---

## 1. Mandate

Continuous surveillance of all trading and financial-transaction activity to detect patterns that may indicate regulatory violations: **insider trading, market manipulation, wash trading, spoofing, layering, front-running, late trading, and excessive position concentration** across all asset classes (equities, fixed income, derivatives, FX, commodities). TM is the System's authority on *what happened in the market* — it holds the highest domain-authority weight for trading patterns (`w=0.95`).

## 2. Capabilities (from spec §Agent 1)

| Capability | Method (how the design realises it) | Scope |
|---|---|---|
| Pattern Detection | Statistical anomaly detection on volume/price/timing/counterparty concentration (z-score vs rolling baselines, order-to-trade ratios, Benford checks) | All asset classes |
| Threshold Monitoring | Rule engine over jurisdiction-specific position limits, large-trader & SAR triggers | SEC, FCA, MAS, HKMA |
| Temporal Analysis | Multi-window correlation over rolling 1h/4h/1d/5d/20d/60d windows vs known market events | Rolling windows |
| Counterparty Analysis | Graph analysis for related-party, circular-trading, concentration | Internal + external counterparty DBs |
| Cross-Market Surveillance | Correlate patterns across venues/instruments for coordinated manipulation | Multi-venue, multi-instrument |

## 3. Interface contract

| Direction | Topic | Message | Payload schema |
|---|---|---|---|
| consume | `transactions` | market/txn events | `txn.event.v1` |
| consume | `agent-messages` | `QUERY` (corroboration requests) | `query.corroboration.v1` |
| consume | `regulatory-updates` | `UPDATE` (threshold recalibration) | `update.regulatory.v1` |
| produce | `agent-messages` | `ALERT`, `RESPONSE` | `alert.detection.v1`, `response.corroboration.v1` |
| produce | `heartbeats` (Redis) | `HEARTBEAT` every 30 s | `heartbeat.status.v1` |

Every `ALERT` carries `severity`, `confidence_score`, `correlation_id`, and an evidence bundle of transaction references (pointers + hashes, never raw PII).

## 4. Detection logic & confidence

For each candidate pattern TM emits `(severity s, confidence c)`. Confidence is **calibrated against the historical false-positive rate** for that pattern type (spec constraint) — a pattern whose historical precision is 0.7 is capped accordingly, so `c` is a *calibrated* probability, not a raw anomaly score. Severity maps to the ordinal in [consensus §2](../conflict-resolution/consensus-algorithm.md). Domain-authority weights TM contributes to consensus: trading **0.95**, record-keeping 0.35, sanctions/AML 0.70, comms 0.15, regulatory 0.30.

## 5. Constraints (spec — binding)

- **Cannot access raw customer communications** — must rely on CS via `QUERY`/`RESPONSE`.
- Detection confidence **must be calibrated** against historical false-positive rates.
- **Cannot issue trading halts autonomously** — recommends; a human authorises (T3/T4 with dual control).
- Must maintain **sub-second latency** for real-time monitoring; operates within fixed compute boundaries.

## 6. Failure & degradation

TM is **stateless** per event (baselines are loaded from the feature store), so a crashed instance is replaced with no state loss and Kafka replays unprocessed transactions (persist-before-process). If TM is offline, its partition lag is the pressure signal; on prolonged outage the Orchestrator marks trading-domain coverage **degraded** and raises an operational alert — the System fails *loud*, never silently blind. See [../architecture/failure-modes.md](../architecture/failure-modes.md).

## 7. Scenarios TM leads or co-signs

Leads/participates in the trading-centric scenarios — e.g. insider trading (CS-01), spoofing/layering, wash trading, front-running, late trading, concentration/synthetic exposure (Archegos-style, CS-14), and the coordinated multi-agent case (CS-20). In CS-18 TM is the *initiating* detector whose alert is later suppressed after verification — TM raises suspicion, it does not assert innocence (see [false-positive tree](../escalation/decision-trees/false-positive-suppression-tree.md)).

---
*End of AGENT-TM v1.0.0*
