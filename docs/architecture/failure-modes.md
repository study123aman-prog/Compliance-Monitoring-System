# D1.5 — Failure Mode Analysis

| Field | Value |
|---|---|
| **Document ID** | ARCH-FAILURE |
| **Deliverable** | D1 — Multi-Agent System Architecture |
| **Version** | 1.0.0 |
| **Date** | 2026-08-21 |
| **Author** | Aman Singh |
| **Status** | Baseline |
| **Related** | [system-topology.md](system-topology.md) · [agent-registry.md](agent-registry.md) · [../protocols/routing-logic.md](../protocols/routing-logic.md) · [../observability/monitoring-dashboard.md](../observability/monitoring-dashboard.md) |

---

## 1. Design stance

The System is designed so that **the failure of any single component degrades coverage but never loses a compliance-relevant event and never silently stops monitoring.** This is achieved by three invariants:

1. **Persist-before-process** — every source event is durably written to Kafka before any agent acts, so a crash re-reads rather than loses.
2. **Stateless workers** — detection agents hold no unique state, so a replacement replica is equivalent (see [agent-registry.md](agent-registry.md) §5).
3. **Fail loud** — a degraded or absent capability raises an operational alert and is visible on the System Health panel; the System never presents partial coverage as full coverage (the JPMorgan/Case-Study-5 lesson: silent gaps are the real danger).

## 2. FMEA table

Severity (S), Likelihood (L), Detectability (D) on 1–5; RPN = S×L×D (higher = attend first).

| # | Component | Failure mode | Effect | S | L | D | RPN | Mitigation |
|---|---|---|---|---|---|---|---|---|
| 1 | Transaction Monitor | Crash / OOM mid-day | Trading surveillance gap | 5 | 3 | 1 | 15 | Autoscale replacement; buffered replay; degraded-mode banner (see §3) |
| 2 | Orchestrator leader | Leader dies | Coordination stalls | 5 | 2 | 1 | 10 | Active–passive failover, resume from event log checkpoint |
| 3 | Kafka broker | Broker/partition loss | Backbone impaired | 5 | 2 | 1 | 10 | Replication factor ≥ 3, min-ISR 2; producers block, never drop |
| 4 | Communication Scanner | LLM/model endpoint down | Comms analysis degraded | 4 | 3 | 2 | 24 | Fallback to rules/lexicon-only mode; queue for re-scan; flag reduced confidence |
| 5 | Consensus Engine | Unavailable | Conflicts unresolved | 4 | 2 | 1 | 8 | Default to *safe* action = escalate (never auto-suppress on failure) |
| 6 | Escalation Manager | Down | Cases not routed to humans | 5 | 2 | 1 | 10 | Persistent `escalations` topic; on recovery, replay by priority; SLA clock preserved |
| 7 | Audit Ledger | Write failure | Cannot prove decisions | 5 | 1 | 1 | 5 | **Circuit-breaker: if audit write fails, the action is blocked** — no un-audited compliance decision is allowed to complete |
| 8 | Regulatory feed | Source outage / bad data | Stale rules, missed change | 3 | 3 | 3 | 27 | ≥2 independent sources per jurisdiction; staleness monitor; last-known-good with age flag |
| 9 | Report Generator | Template error / crash | Delayed report | 3 | 2 | 2 | 12 | Versioned templates + rollback; retry; report SLA alert |
| 10 | Downstream (message) | Timeout / no ack | Undelivered inter-agent msg | 3 | 3 | 2 | 18 | Retry w/ exponential backoff → Dead Letter Queue → operator alert (see §4) |

Highest RPNs (reg-feed staleness #8, CS model outage #4, message delivery #10) get the most engineering attention and the tightest monitors.

## 3. Worked case: "TM goes offline mid-trading-day"

This is the specification's litmus-test question. Sequence:

```mermaid
sequenceDiagram
    participant OMS
    participant K as Kafka (transactions)
    participant TM as TM replicas
    participant HM as Health Monitor
    participant OPS as Operations
    OMS->>K: transaction events (continue arriving)
    Note over TM: A TM replica crashes
    TM--xHM: heartbeats stop (3 missed = STOPPED)
    HM->>OPS: CRITICAL: TM capacity degraded
    HM->>TM: autoscaler launches replacement pod
    Note over K,TM: events buffered in Kafka (persist-before-process)
    TM->>K: new replica resumes from committed offset
    Note over TM: back-processes buffered events; no event lost
    TM->>HM: heartbeat RUNNING; consumer lag draining
    HM->>OPS: recovery + max lag / max detection delay reported
```

Key points for the viva: (a) transactions keep landing in Kafka, so **nothing is lost**; (b) the gap is a *latency* gap, not a *coverage* gap, and its exact duration is measured and reported (time-to-detection SLA); (c) if the entire TM pool is down beyond a threshold, the Orchestrator raises a **market-hours coverage-gap incident** and the dashboard shows monitoring as degraded — operators and, if prolonged, compliance leadership are told, because pretending coverage is intact would repeat the JPMorgan failure.

## 4. Retry, circuit-breaker & dead-letter policy

- **Retry:** transient failures retried with **exponential backoff** — base 1s, ×2 each attempt, max 5 attempts, plus 0–500 ms jitter to avoid thundering-herd. (Implemented in the reference code's bus.)
- **Circuit breaker:** after N consecutive failures to a dependency, the breaker opens for a cool-down, the agent switches to its fallback (e.g. CS → rules-only), and the breaker half-opens to test recovery. Prevents a sick dependency from cascading.
- **Dead Letter Queue (DLQ):** a message that cannot be delivered/processed after max retries goes to a DLQ with full context and raises an operator alert; it is **never discarded**. DLQ contents are themselves audit-classified.
- **Audit-write circuit breaker (special):** unlike other dependencies, if the Audit Ledger cannot record an action, the action is **halted**, not completed — the System refuses to make an unprovable compliance decision.

## 5. Graceful degradation matrix

| Failed capability | System behaviour | What is preserved |
|---|---|---|
| TM pool | Latency gap, loud alert | No lost events; exact gap measured |
| CS LLM | Rules/lexicon-only, lower confidence, re-scan queued | Record-keeping + keyword coverage |
| RU feed | Last-known-good rules with age flag; conflict detection paused for that source | Existing rule set still enforced |
| Consensus Engine | Fail-safe: escalate to human | Never auto-suppresses on failure |
| Escalation Manager | Cases persist; SLA clock retained | No case dropped; replay on recovery |

**Fail-safe principle:** wherever a failure creates ambiguity, the System's default is the *conservative* compliance action — escalate to a human — never the permissive one (auto-close). This is the single most important safety property and is asserted by a unit test in the reference implementation.

---
*End of ARCH-FAILURE v1.0.0*
