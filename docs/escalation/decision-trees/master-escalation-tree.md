# Master Escalation Decision Tree

| Field | Value |
|---|---|
| **Document ID** | TREE-MASTER |
| **Deliverable** | D4 — Human-in-the-Loop Escalation Framework |
| **Version** | 1.0.0 · **Date** 2026-08-21 · **Author** Aman Singh |
| **Related** | [../escalation-framework.md](../escalation-framework.md) · [../../conflict-resolution/consensus-algorithm.md](../../conflict-resolution/consensus-algorithm.md) |

---

## What this tree decides

Every consensus result enters here. The tree computes the **routing tier** as `tier = max(confidence-band tier, severity-floor tier)`, then applies special triggers that can only *raise* it. Suppression (T0) is itself a logged decision, never a silent drop. This is the deterministic form of §3 of the framework — the reference implementation `src/escalation.py` walks exactly these branches.

```mermaid
flowchart TD
    START([Consensus result:<br/>severity s*, confidence C, domain d]) --> RES{Consensus<br/>resolved?}
    RES -- "UNRESOLVED<br/>(margin&lt;0.20 or K&gt;0.60)" --> ESCH[Route to human at<br/>higher-severity opinion's tier]
    RES -- resolved --> SPEC{Special trigger<br/>present?}

    SPEC -- "Jurisdictional conflict C5" --> T4L[Force T4 + Legal hook]
    SPEC -- "Subject in escalation chain" --> COI[Force T4 +<br/>conflict-of-interest reroute]
    SPEC -- "Authorised-control override C7" --> T4O[Escalate regardless of C]
    SPEC -- "Regulatory clock<br/>SAR/GDPR/sanctions" --> T4C[Force T4 + tight SLA]
    SPEC -- none --> BAND

    BAND{Severity s*?}
    BAND -- "NO_ALERT / LOW" --> FLOOR0[Severity floor = T0]
    BAND -- MEDIUM --> FLOOR1[Severity floor = T1]
    BAND -- HIGH --> FLOOR3[Severity floor = T3]
    BAND -- CRITICAL --> FLOOR4[Severity floor = T4]

    FLOOR0 --> CONF
    FLOOR1 --> CONF
    FLOOR3 --> CONF
    FLOOR4 --> CONF
    CONF{Confidence band C}
    CONF -- "0.00–0.30" --> C0[band = T0]
    CONF -- "0.30–0.55" --> C1[band = T1]
    CONF -- "0.55–0.75" --> C2[band = T2]
    CONF -- "0.75–0.90" --> C3[band = T3]
    CONF -- "0.90–1.00" --> C4[band = T4]

    C0 & C1 & C2 & C3 & C4 --> MAX[tier = max floor, band]
    MAX --> ZERO{tier == T0?}
    ZERO -- yes --> SUPP[T0: auto-close with<br/>documented reasoning + audit]
    ZERO -- no --> ROUTE[Assemble decision-support package<br/>route to tier, start SLA clock]

    T4L --> ROUTE
    COI --> ROUTE
    T4O --> ROUTE
    T4C --> ROUTE
    ESCH --> ROUTE
```

## Reading the outcome

The two "raise-only" rules are the safety core: the **severity floor** guarantees a CRITICAL always reaches a Director even at modest confidence (cost of a miss dominates), and **special triggers** guarantee legal/conduct-sensitive cases (C5, C7, senior-subject, regulatory clock) reach T4 regardless of the arithmetic. Only a case that is both low-severity *and* low-confidence *and* trigger-free lands at T0 — and even then it is closed with written reasoning and an audit entry. After routing, the SLA clock ([../escalation-framework.md](../escalation-framework.md) §6) governs auto-re-escalation.

---
*End of TREE-MASTER v1.0.0*
