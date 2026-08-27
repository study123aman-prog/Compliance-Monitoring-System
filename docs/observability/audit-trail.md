# Audit-Trail Architecture

| Field | Value |
|---|---|
| **Document ID** | OBS-AUDIT |
| **Deliverable** | D7 — Observability & Audit Architecture |
| **Version** | 1.0.0 · **Date** 2026-08-21 · **Author** Aman Singh |
| **Related** | [logging-spec.md](logging-spec.md) · [retention-policy.md](retention-policy.md) · [../conflict-resolution/consensus-algorithm.md](../conflict-resolution/consensus-algorithm.md) §9 · [../protocols/communication-protocol.md](../protocols/communication-protocol.md) · spec §A6.1 · impl `src/audit_ledger.py` |

---

## 1. What the audit trail is

The audit trail is the **tamper-evident, cryptographically-signed, immutable** record used to *prove* — to an internal auditor, external auditor, or regulator — that every compliance decision was made correctly and can be reconstructed years later. Its requirements derive from **SEC Rule 17a-4(f)** and equivalents. It is the `REGULATORY`-classified subset of the [decision log stream](logging-spec.md), hardened with hash chaining, digital signatures, and WORM storage.

## 2. The seven integrity requirements → how we satisfy each (spec §A6.1)

| Requirement | Mechanism in this system |
|---|---|
| **Immutability** | **WORM storage** (Write Once, Read Many). Entries cannot be modified/deleted during retention (SEC 17a-4(f)). |
| **Completeness** | Every significant action logged with full context (see [logging-spec §4](logging-spec.md)); gaps are detectable because the hash chain breaks. |
| **Authenticity** | Each entry **ECDSA P-256 signed** by its originating agent/human; signature verifies principal identity. |
| **Temporal integrity** | NTP-synced UTC ms timestamps, **< 100 ms** skew tolerance ([logging-spec §6](logging-spec.md)). |
| **Tamper evidence** | **SHA-256 hash chaining** — each entry embeds the previous entry's hash (blockchain-style). |
| **Reproducibility** | Consensus is **deterministic** (fixed inputs + constants, no randomness — [consensus-algorithm §9](../conflict-resolution/consensus-algorithm.md)); full state captured, so any decision recomputes identically. |
| **Accessibility** | Indexed by `correlation_id`, subject, time, violation type; **historical query latency ≤ 30 s** (spec target). |

## 3. Audit entry schema

```json
{
  "seq": 100427,                              // monotonic, gap-detectable
  "entry_id": "uuid-v4",
  "timestamp": "2026-08-21T14:07:32.902Z",
  "correlation_id": "C01-INS-2026-0842",
  "actor": "service.consensus_engine",
  "action": "consensus.computed",
  "inputs": { "opinions": [ /* agent masses, weights, confidences */ ] },
  "output": { "belief_v": 0.92, "severity": "CRITICAL", "mechanism": "dempster_shafer" },
  "evidence_refs": ["txn:…#hash=sha256:…", "comm:…#hash=sha256:…"],
  "prev_hash": "sha256:2f9a…c1",              // hash of entry seq=100426
  "entry_hash": "sha256:8b41…9d",             // SHA-256 over canonical(entry minus this field)
  "signature": "base64(ECDSA-P256: 3045…)",   // over entry_hash
  "signer_key_id": "kid:ce-2026-03"
}
```

## 4. Hash-chaining construction (tamper evidence)

```
entry_hash[n] = SHA256( canonical_serialize( entry[n] \ {entry_hash, signature} )
                        || prev_hash[n] )
prev_hash[n]  = entry_hash[n-1]           // genesis: prev_hash[0] = SHA256("GENESIS:<system-id>")
```

Because each entry commits to its predecessor, altering entry *k* changes `entry_hash[k]`, which invalidates `prev_hash[k+1]` and every hash after it. A single modified or **deleted** entry is therefore detectable — the chain no longer verifies. Periodic **anchor checkpoints** (the current head hash) are written to an independent WORM location and, optionally, notarized externally, so even a full-store rewrite is caught.

## 5. Signatures (authenticity)

Each entry's `entry_hash` is signed with the actor's **ECDSA P-256** private key (RSA-2048 is the spec-permitted alternative; we choose ECDSA for smaller signatures/faster verify at equal security). Verification uses the actor's public key resolved via `signer_key_id` against a key registry with documented rotation. This binds each entry to a specific agent or human principal — an override at Tier-4 is provably attributable to the individual who approved it.

## 6. Verification procedure (what an examiner runs)

```
1. For n = 1 … head:
     recompute entry_hash[n]; assert == stored entry_hash[n]
     assert prev_hash[n] == entry_hash[n-1]
     assert ECDSA_verify(signature[n], entry_hash[n], pubkey(signer_key_id[n]))
2. assert head hash == latest independent anchor checkpoint
3. To reproduce a decision: replay inputs[] through the deterministic consensus engine;
   assert recomputed output == stored output
```

Any failure localizes to a sequence number. Success proves the trail is complete, unaltered, authentic, and that the decision is reproducible.

## 7. Storage & write path

Audit writes go to an **append-only, WORM-backed** store fronted by Kafka's durable, replayable log (chosen partly for its audit-trail suitability, spec §B7). The write is **synchronous** — an action is not "done" until its signed, chained entry is durably persisted; if the audit write fails, the action **fails closed** (never act on an unrecordable decision). Retention, legal hold, and disposition are governed by [retention-policy.md](retention-policy.md).

## 8. Scope: what is audited

All `REGULATORY`-classified events: ingestion of monitored data, every agent detection, every consensus computation (incl. suppressions like CS-18 with reasoning), every escalation and SLA event, and **every human decision** (approval, override, dual-control filing sign-off, CoI recusal). This is the reconstructable case file referenced by each scenario trace-through (e.g. `correlation_id = C20-TBML` spans all four agents).

---
*End of OBS-AUDIT v1.0.0*
