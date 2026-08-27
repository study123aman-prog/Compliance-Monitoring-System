# Retention & Disposition Policy

| Field | Value |
|---|---|
| **Document ID** | OBS-RETENTION |
| **Deliverable** | D7 — Observability & Audit Architecture |
| **Version** | 1.0.0 · **Date** 2026-08-21 · **Author** Aman Singh |
| **Related** | [audit-trail.md](audit-trail.md) · [logging-spec.md](logging-spec.md) · spec §A6.1 · §A4 (regulatory mapping) · §A7 (India) |

---

## 1. Purpose & principle

Defines **how long** each record class is retained, **on what medium**, and **how it is disposed of**. Retention is bounded on both sides: records must survive at least the regulatory minimum (under **WORM**, immutable for the whole period per SEC 17a-4(f)), and sensitive raw data must **not** be kept beyond its lawful basis (GDPR storage-limitation, the Communication Scanner's data-retention-boundary constraint). Where obligations differ across jurisdictions, the **longest applicable minimum governs** the audit record.

## 2. Retention schedule by record class

| Record class | Store / medium | Minimum retention | Primary basis |
|---|---|---|---|
| **Audit trail** (signed, hash-chained decisions & human actions) | WORM, immutable | **6 years** (first **2 readily accessible**) | SEC Rule 17a-4(f) |
| **Communications records** (regulated business comms) | WORM | **6 years** (US); align to longest applicable | SEC 17a-4, FINRA 3110; MiFID II ≥ 5 y (up to 7) |
| **Transaction/order records** | WORM | **6 years** | SEC 17a-4; CFTC/CEA |
| **SAR & filing packages** | WORM, restricted access | **5 years** from filing | BSA / FinCEN |
| **Regulatory-update assessments** (RU) | Durable | Life of affected rule **+ 6 years** | reproducibility of decisions |
| **Operational logs** (latency, health) | Hot store | **90 days** hot, then aggregate | operational, not 17a-4 |
| **Diagnostic/debug traces** | Sampled | **≤ 30 days** | engineering only; minimise PII surface |
| **Raw sensitive content** (message bodies, PII) | Governed source store | **Lawful-basis minimum only** | GDPR storage-limitation |

Audit and other WORM classes retain **evidence references + hashes** permanently within the chain even when the underlying raw content is disposed of at its shorter GDPR-bound life — the decision remains provable via hash without retaining the raw personal data.

## 3. Jurisdictional overlay (spec §A4, §A7)

The audit trail is written once and must satisfy every regime the record touches, so the **maximum** minimum applies. Notable overlays: **MiFID II** communications (EU) 5–7 years; **GDPR** (EU) imposes an *upper* bound on raw personal data and the right-to-erasure — reconciled by hashing (§2). **India (§A7):** **SEBI** (PIT/LODR) record-keeping typically **5 years**; **RBI** and **PMLA** AML records commonly **5 years** from transaction/relationship end; **DPDP Act** mirrors GDPR storage-limitation. The policy stores the governing basis per record so an examiner sees *why* a period was chosen.

## 4. WORM, legal hold & disposition

**WORM:** audit and regulated records are written to Write-Once-Read-Many media; no modification or deletion is possible during the retention period, and the [hash chain](audit-trail.md) makes any attempt detectable.

**Legal hold:** on litigation/examination notice, affected records are flagged `legal_hold=true`, which **suspends all disposition** regardless of schedule until released. Holds and releases are themselves audited actions.

**Disposition:** at end-of-retention (and absent any hold), records are disposed of under a **documented, audited** process — the disposition event is itself written to the audit trail (what, when, under which schedule, authorised by whom), so even deletion is provable and complete. Raw sensitive content reaching its GDPR-bound limit is purged on schedule while its hash remains in the chain.

## 5. Accessibility tiering

To meet the **≤ 30 s** historical-query target (spec §A6.1) while controlling cost: the **first 2 years** of audit data are kept **readily accessible** (hot/warm, indexed by `correlation_id`, subject, type, time); years **3–6** may move to slower WORM tiers with a documented retrieval SLA. Tier placement never alters the hash chain or signatures — only latency.

---
*End of OBS-RETENTION v1.0.0*
