# Logging Specification

| Field | Value |
|---|---|
| **Document ID** | OBS-LOGGING |
| **Deliverable** | D7 — Observability & Audit Architecture |
| **Version** | 1.0.0 · **Date** 2026-08-21 · **Author** Aman Singh |
| **Related** | [audit-trail.md](audit-trail.md) · [monitoring-dashboard.md](monitoring-dashboard.md) · [retention-policy.md](retention-policy.md) · [../protocols/message-schema.json](../protocols/message-schema.json) · spec §A6.1 |

---

## 1. Purpose & principle

Regulators treat observability as a compliance requirement in itself: *"it is not sufficient for a system to make correct decisions; the system must also be able to prove it made correct decisions"* (spec §A6). This document specifies **structured logging** — the operational record of everything the system does. It is distinct from the **[audit trail](audit-trail.md)** (the tamper-evident, signed, WORM subset used for regulatory examination): all audit entries are logs, but not all logs are audit entries.

## 2. Log streams (three, by purpose)

| Stream | Contents | Consumers | Backing store |
|---|---|---|---|
| **Operational** | Service lifecycle, latency, queue depth, errors, retries | Ops dashboard, alerting | Hot store (searchable, ~30–90 d) |
| **Decision** | Every detection, consensus computation, escalation, suppression — with full inputs | Compliance dashboard, audit | Feeds the [audit ledger](audit-trail.md) |
| **Diagnostic** | Verbose traces, debug spans, model feature values | Engineers (short-lived) | Sampled, short retention |

The `audit_classification` field on every message envelope (`REGULATORY` / `OPERATIONAL` / `DIAGNOSTIC`) routes each event to the correct stream — this is why it is a first-class envelope field, not an afterthought.

## 3. Canonical log event schema

Every log event is a structured JSON object (never a free-text line):

```json
{
  "log_id": "uuid-v4",
  "timestamp": "2026-08-21T14:07:32.481Z",   // ISO-8601 UTC, ms precision, NTP-synced
  "level": "INFO",                            // TRACE|DEBUG|INFO|WARN|ERROR|FATAL
  "stream": "DECISION",                       // OPERATIONAL|DECISION|DIAGNOSTIC
  "component": "service.consensus_engine",
  "event_type": "consensus.computed",
  "correlation_id": "C01-INS-2026-0842",      // ties all events of one case together
  "trace_id": "9f3c…7a",                       // ties one causal chain across components
  "span_id": "b1…",
  "payload": { "...": "event-specific, structured" },
  "severity_context": "CRITICAL",
  "actor": "service.consensus_engine",        // agent or human principal
  "outcome": "success"                        // success|failure|degraded
}
```

`correlation_id` (per compliance case) and `trace_id` (per causal chain) are **mandatory** on every event — they are what let an examiner reconstruct an entire decision from ingestion to filing.

## 4. What must be logged (completeness)

Spec §A6.1 requires **no gaps** — *"every significant system action must be logged with sufficient context to reconstruct the decision chain."* Mandatory log points:

- **Ingestion**: each transaction / communication / regulatory event received (source, hash, arrival time).
- **Detection**: each agent alert with `{severity, confidence, domain, evidence_refs}`.
- **Consensus**: mechanism selected, all input masses/scores, intermediate values, output (see [consensus-algorithm.md](../conflict-resolution/consensus-algorithm.md)).
- **Escalation**: tier computed, SLA clock started, package contents, recipient tier.
- **Suppression**: NO_ALERT decisions **with reasoning** (CS-18) — suppression is logged, never silent.
- **Human action**: every approval, override, downgrade, dual-control sign-off, with principal identity.
- **Lifecycle & failure**: agent start/stop/degrade, heartbeat miss, retry, dead-letter, circuit-breaker trips.

## 5. Log levels (when to use each)

`TRACE/DEBUG` diagnostic only (sampled, short retention). `INFO` normal significant actions (detections, escalations, state changes). `WARN` degradations that self-heal (retry succeeded, queue at 80%). `ERROR` failed operations needing attention (queue at 95%, agent unreachable, signature verification failure). `FATAL` system-integrity events (audit chain break detected, consensus engine down → fail-safe escalate).

## 6. Temporal integrity (spec §A6.1)

All components synchronise clocks via **NTP against a documented time source**; **clock-skew tolerance < 100 ms**. Every timestamp is UTC, ISO-8601, millisecond precision. On detected skew ≥ 100 ms, the component emits a `WARN` and the audit layer flags affected entries — because ordering (e.g. late-trading CS-14, front-running CS-10) is itself evidence.

## 7. PII & data-boundary handling

Decision/audit logs store **evidence references and hashes**, not raw sensitive content (e.g. `comm:…#hash=sha256:…`, not the message body). Raw content stays in the governed source store with its own retention (see [retention-policy.md](retention-policy.md)); logs point to it. This keeps the searchable log surface minimal while preserving reconstructability, and respects the Communication Scanner's data-retention-boundary constraint.

## 8. Reliability of the log path

Logging is on the critical path for compliance, so the decision stream is written **synchronously and durably** (to Kafka's replayable log) before an action is considered complete; operational/diagnostic streams may be buffered/async. If the audit write fails, the action **fails closed** — the system does not act on a decision it cannot record.

---
*End of OBS-LOGGING v1.0.0*
