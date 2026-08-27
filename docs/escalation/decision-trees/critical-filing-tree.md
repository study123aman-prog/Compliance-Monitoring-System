# Critical-Filing Decision Tree (SAR/STR path)

| Field | Value |
|---|---|
| **Document ID** | TREE-CRITICAL-FILING |
| **Deliverable** | D4 — Human-in-the-Loop Escalation Framework |
| **Version** | 1.0.0 · **Date** 2026-08-21 · **Author** Aman Singh |
| **Related** | [../escalation-framework.md](../escalation-framework.md) §5 (dual control) · [../../agents/report-generator.md](../../agents/report-generator.md) |
| **Scenarios** | CS-01, CS-04, CS-09, CS-14, CS-20 |

---

## What this tree decides

Once the master tree routes a **CRITICAL** case to **T4**, this path governs the *consequential action* — a regulatory filing (SAR/STR) or a trading hold. Its defining features are **dual control** (a filing needs two T4 sign-offs) and a **regulatory clock** that auto-re-escalates rather than letting a deadline slip. This is the JPMorgan/1MDB lesson encoded: no single actor can either file *or* quietly bury a critical case.

```mermaid
flowchart TD
    IN([CRITICAL case at T4<br/>+ decision-support package]) --> ACK{Acknowledged<br/>within 15 min?}
    ACK -- no --> REESC[Auto-re-escalate to board hook<br/>+ SLA-breach incident]
    ACK -- yes --> REV{T4 reviewer decision}

    REV -- "Confirm violation" --> FILE{Action requires<br/>regulatory filing?}
    REV -- "Downgrade" --> DUAL2[Requires 2nd T4 approver<br/>+ MFA + rationale]
    REV -- "Need more evidence" --> QUERY[Request corroboration<br/>SLA clock keeps running]

    QUERY --> REV
    DUAL2 -- "2nd approver agrees" --> DOWN[Downgrade recorded<br/>route to lower tier]
    DUAL2 -- "2nd approver rejects" --> REV

    FILE -- "yes: SAR/STR" --> SIGN{Dual sign-off<br/>2× T4, both MFA?}
    FILE -- "no: internal remediation" --> REM[Authorise remediation/hold<br/>single T4 + audit]

    SIGN -- "both sign before 24h" --> SUBMIT[RG generates filing package<br/>submit to FIU-IND/SEC<br/>sign + WORM archive]
    SIGN -- "clock &lt; 24h, not yet signed" --> NUDGE[Escalate to CCO + board hook]
    NUDGE --> SIGN
    SUBMIT --> FB[Log outcome → feedback loop]
    REM --> FB
    DOWN --> FB
    REESC --> FB
```

## Reading the outcome

Three guarantees make this path defensible. First, **dual sign-off** on any filing and **dual control** on any downgrade enforce separation of duties — the audit ledger shows two distinct authenticated approvers. Second, the **24-hour SAR clock** never silently expires: as it nears zero without sign-off, the case climbs to the CCO and board hook (`NUDGE`), so a missed deadline becomes an incident, not a gap. Third, every terminal branch feeds the **feedback loop**, so confirmed filings and downgrades both recalibrate agent confidence. The filing package itself is produced by the Report Generator and written to WORM storage with a hash-chained, signed audit entry (SEC 17a-4(f)).

---
*End of TREE-CRITICAL-FILING v1.0.0*
