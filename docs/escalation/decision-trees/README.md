# Escalation Decision Trees — Index

| Field | Value |
|---|---|
| **Document ID** | ESCALATION-TREES-INDEX |
| **Deliverable** | D4 — Human-in-the-Loop Escalation Framework |
| **Version** | 1.0.0 · **Date** 2026-08-21 · **Author** Aman Singh |

This directory holds the decision-tree diagrams for each distinct escalation path referenced by [../escalation-framework.md](../escalation-framework.md). Each tree is deterministic — the same case inputs always follow the same branch.

| Tree | Path it models | Key scenarios |
|---|---|---|
| [master-escalation-tree.md](master-escalation-tree.md) | The top-level routing every case passes through | all |
| [critical-filing-tree.md](critical-filing-tree.md) | CRITICAL alert → SAR/STR filing with dual sign-off | CS-01, CS-04, CS-09, CS-14, CS-20 |
| [false-positive-suppression-tree.md](false-positive-suppression-tree.md) | Verify-before-escalate; suppress benign | CS-18 |
| [jurisdictional-conflict-tree.md](jurisdictional-conflict-tree.md) | Contradictory regulations → Legal | CS-19 |

**Legend (all trees):** diamonds = decision, rectangles = action/state, rounded = human tier. `C` = consensus confidence; tiers T0–T4 per the framework.
