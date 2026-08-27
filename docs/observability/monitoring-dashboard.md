# Monitoring-Dashboard Architecture

| Field | Value |
|---|---|
| **Document ID** | OBS-DASHBOARD |
| **Deliverable** | D7 — Observability & Audit Architecture |
| **Version** | 1.0.0 · **Date** 2026-08-21 · **Author** Aman Singh |
| **Related** | [logging-spec.md](logging-spec.md) · [audit-trail.md](audit-trail.md) · [../escalation/escalation-framework.md](../escalation/escalation-framework.md) · spec §A6.2 |

---

## 1. Purpose

Three dashboard panels, each targeting a distinct stakeholder group (spec §A6.2). All metrics are computed from the [operational and decision log streams](logging-spec.md); none require reading raw sensitive content. Thresholds below are defaults and are configurable.

## 2. Panel 1 — System Health (audience: Operations)

| Metric | Definition | Alert threshold |
|---|---|---|
| **Agent status** | running / degraded / stopped, via heartbeat | Heartbeat interval **30 s** (default); miss ⇒ degraded |
| **Message-queue depth** | pending messages per topic | **WARN at 80%** capacity, **CRITICAL at 95%** |
| **Processing latency** | per-agent **P50 / P95 / P99** | Alert on **SLA-percentile violation** |
| **Resource utilisation** | CPU / memory / network per agent | Capacity-planning projection; alert on trend to exhaustion |
| **Error rate** | errors per agent | **Statistical-process-control** anomaly detection (trend + control limits) |

Heartbeats ride the `heartbeats` topic (Redis Streams — chosen for low-latency liveness, spec §B7). A missed heartbeat degrades the agent and, if sustained, trips the orchestrator's failover per the [resilience topology](../architecture/deployment-topology.md).

## 3. Panel 2 — Compliance Effectiveness (audience: Compliance Leadership)

| Metric | Definition | Notes |
|---|---|---|
| **Detection rate by violation type** | detections per type over daily/weekly/monthly windows | trend analysis |
| **False-positive rate** | by agent and by violation type | tracked vs **baseline**; CS-18-style suppressions feed this |
| **Time-to-detection** | occurrence → detection distribution | how fast violations surface |
| **Time-to-escalation / time-to-resolution** | detection → escalation → close distributions | end-to-end process efficiency vs [SLAs](../escalation/escalation-framework.md) |
| **Regulatory-filing accuracy & timeliness** | filed-correct %, filed-on-time %, **by jurisdiction** | SAR/24 h, GDPR/72 h, etc. |

The false-positive metric closes the feedback loop: confirmed true-negatives (CS-18) and human overrides recalibrate agent confidence, and the dashboard shows whether that calibration is improving against baseline.

## 4. Panel 3 — Operational Intelligence (audience: Senior Management)

| Metric | Definition |
|---|---|
| **Escalation volume & distribution** | by **tier, agent, violation type**, with trend analysis |
| **Human decision patterns** | approval rate, **override frequency**, average response time |
| **Agent conflict frequency & resolution** | conflict-class ([taxonomy](../conflict-resolution/conflict-taxonomy.md)) frequency + resolution pattern, **root-cause categorised** |
| **Regulatory-update impact tracking** | pipeline from RU detection → assessment → **system-update deployment** |
| **Cost-per-detection** | automated cost per detection **vs manual baseline** (the efficiency case, spec §A2) |

## 5. Alerting model

Alerts are severity-tiered (`WARN`/`CRITICAL`) and routed by panel: System-Health alerts page Operations; SLA-violation and filing-timeliness alerts notify Compliance; sustained override/conflict spikes surface to Senior Management. Every alert carries the `correlation_id`/`trace_id` so a click jumps straight to the reconstructable case in the [audit trail](audit-trail.md). Alert thresholds and heartbeat/queue parameters are configuration, versioned in the audit log when changed.

## 6. Data sourcing & integrity

Dashboards read only from logs and pre-aggregated metrics, never mutate them; they are strictly consumers. Historical drill-downs resolve against the audit store within the **≤ 30 s** query-latency target (spec §A6.1). Because metrics derive from the same signed decision stream that feeds audit, the numbers a manager sees are provably consistent with what an examiner would reconstruct.

---
*End of OBS-DASHBOARD v1.0.0*
