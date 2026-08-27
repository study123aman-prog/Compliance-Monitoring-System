# D6 — Scenario Trace-Through Summary & Locked Reference

| Field | Value |
|---|---|
| **Document ID** | SCENARIO-SUMMARY |
| **Deliverable** | D6 — Scenario Trace-Throughs |
| **Version** | 1.0.0 · **Date** 2026-08-21 · **Author** Aman Singh |
| **Related** | [../../docs/conflict-resolution/consensus-algorithm.md](../../docs/conflict-resolution/consensus-algorithm.md) · [../../docs/escalation/escalation-framework.md](../../docs/escalation/escalation-framework.md) · impl `tests/test_scenarios.py` |

---

## 1. Purpose

Index for the 20 mandatory scenario trace-throughs and the **locked reference values** every trace-through and the pytest suite must agree on. All values below are derived from the [consensus algorithm](../../docs/conflict-resolution/consensus-algorithm.md) and [escalation framework](../../docs/escalation/escalation-framework.md); they are the single source of truth that prevents drift.

## 2. Master table

| ID | Violation | Lead agent(s) | Complexity | Expected severity | Consensus conf. | Tier | Key regulations |
|---|---|---|---|:--:|:--:|:--:|---|
| [CS-01](CS-01.md) | Insider trading (pre-announcement) | TM+CS | High | CRITICAL | 0.92 | T4 | SEC 10b-5, FINRA 2010, ITSA |
| [CS-02](CS-02.md) | Spoofing in futures | TM | Medium | HIGH | 0.85 | T3 | Dodd-Frank §747, CEA §4c(a)(5), CME 575 |
| [CS-03](CS-03.md) | Unsuitable recommendation | CS+TM | High | HIGH | 0.86 | T3 | FINRA 2111, SEC Reg BI |
| [CS-04](CS-04.md) | AML structuring | TM | Medium | CRITICAL | 0.88 | T4 | BSA, 31 CFR 1020.320, FinCEN SAR |
| [CS-05](CS-05.md) | Chinese-wall breach | CS | High | CRITICAL | 0.83 | T4 | SEC §15(g), FINRA 5280, MiFID II Art 33 |
| [CS-06](CS-06.md) | Wash trading (cross-account) | TM | High | HIGH | 0.82 | T3 | CEA §4c(a), SEC 10b-5, FINRA 5210 |
| [CS-07](CS-07.md) | Regulatory change (margin) | RU | Medium | MEDIUM | 0.70 | T2 | SEC Swap Margin Rule, Basel III CRE54, EMIR |
| [CS-08](CS-08.md) | Misleading marketing | CS | Low-Med | CRITICAL | 0.86 | T4 | SEC 206(4)-1, FINRA 2210, FCA COBS 4 |
| [CS-09](CS-09.md) | Sanctions (indirect counterparty) | TM+RU | High | CRITICAL | 0.87 | T4 | OFAC, 31 CFR Part 501, EU Sanctions Reg |
| [CS-10](CS-10.md) | Front-running | TM | Medium | CRITICAL | 0.87 | T4 | SEC §17(j), ICA §17(j), FINRA 5270 |
| [CS-11](CS-11.md) | Data-privacy cross-border | CS+RU | Medium | HIGH | 0.88 | T3 | GDPR Art 44–49, Schrems II |
| [CS-12](CS-12.md) | Concentration limit breach | TM | Low | MEDIUM | 0.72 | T2 | ICA §13, Form N-PORT, UCITS |
| [CS-13](CS-13.md) | Off-channel comms | CS | Medium | HIGH | 0.84 | T3 | SEC 17a-4, FINRA 3110 |
| [CS-14](CS-14.md) | Late trading (NAV) | TM | Medium | CRITICAL | 0.85 | T4 | SEC 22c-1, ICA §22(c) |
| [CS-15](CS-15.md) | Best-execution failure | TM | Medium | HIGH | 0.80 | T3 | SEC 606, FINRA 5310, MiFID II |
| [CS-16](CS-16.md) | Research independence | CS+TM | High | CRITICAL | 0.92 | T4 | SEC Reg AC, FINRA 2241, Global Research Settlement |
| [CS-17](CS-17.md) | Elder exploitation | TM+CS | High | CRITICAL | 0.94 | T4 | FINRA 2165/4512, Senior Safe Act |
| [CS-18](CS-18.md) | **FALSE POSITIVE** block trade | TM→suppressed | Medium | **NO_ALERT** | <thr | T0 | (suppression; −25 pts if escalated) |
| [CS-19](CS-19.md) | Multi-jurisdiction conflict | RU | High | HIGH | 0.90* | T4+Legal | EMIR, MAS SFA, GDPR |
| [CS-20](CS-20.md) | **COORDINATED** TBML | ALL FOUR | Very High | CRITICAL | 0.95 | T4+Board | BSA/AML, OFAC, TBML, FATF |

\* CS-19: RU is highly confident the *conflict exists*; the case is **not auto-resolved** — forced to T4 + Legal by the C5 special trigger regardless of confidence.

## 3. Locked consensus computations (multi-agent scenarios)

Combination rule (no benign mass, K=0): `Belief(V) = m₁(V) + m₂(V) − m₁(V)·m₂(V)`, where `mᵢ(V) = wᵢ(domain)·cᵢ`. Authority weights from the [domain-authority matrix](../../docs/conflict-resolution/consensus-algorithm.md#3-domain-authority-matrix).

| ID | Agent (domain, w) × c → m(V) | Belief(V) | Severity |
|---|---|:--:|:--:|
| CS-01 | TM(trading .95)·.72=.684 ; CS(comms .95)·.80=.760 | **0.92** | CRITICAL |
| CS-03 | CS(comms .95)·.70=.665 ; TM(trading .95)·.62=.589 | **0.86** | HIGH |
| CS-09 | TM(sanctions .70)·.82=.574 ; RU(sanctions .75)·.92=.690 | **0.87** | CRITICAL |
| CS-11 | CS(rec-keeping .90)·.68=.612 ; RU(regulatory .95)·.72=.684 | **0.88** | HIGH |
| CS-16 | CS(comms .95)·.80=.760 ; TM(trading .95)·.72=.684 | **0.92** | CRITICAL |
| CS-17 | TM(trading .95)·.82=.779 ; CS(comms .95)·.78=.741 | **0.94** | CRITICAL |
| CS-20 | TM(AML .70)·.80=.560 ; CS(rec .90)·.78=.702 ; RU(AML .75)·.85=.638 → pairwise | **0.95** | CRITICAL |

CS-20 pairwise: TM+CS = .560+.702−.560·.702 = 0.869; then +RU = .869+.638−.869·.638 = **0.953 ≈ 0.95**. (RG reports; it does not vote.)

## 4. Single-agent scenarios (agent's own calibrated confidence)

CS-02 0.85 (HIGH/T3) · CS-04 0.88 (CRITICAL/T4, SAR clock) · CS-05 0.83 (CRITICAL/T4) · CS-06 0.82 (HIGH/T3) · CS-07 0.70 (MEDIUM/T2) · CS-08 0.86 (CRITICAL/T4) · CS-10 0.87 (CRITICAL/T4) · CS-12 0.72 (MEDIUM/T2) · CS-13 0.84 (HIGH/T3) · CS-14 0.85 (CRITICAL/T4) · CS-15 0.80 (HIGH/T3).

## 5. Special scenarios

**CS-18 (false positive).** TM fires `c=0.68` on an 8%-of-ADV block trade. Verification authenticates the block-desk pre-arrangement + disclosed rebalancing mandate → commits benign mass `m({B}) = 0.9·0.9 = 0.81`; TM `m({V}) = 0.95·0.68 = 0.646`. Dempster combination is dominated by benign mass → `Belief(V)` falls below the suppression threshold → **NO_ALERT / T0** with documented reasoning. Escalating this incurs **−25 points** ([false-positive tree](../../docs/escalation/decision-trees/false-positive-suppression-tree.md)).

**CS-19 (jurisdictional conflict).** RU detects EMIR (must report OTC in 1 day) vs MAS (must not share cross-border) — conflict class **C5**. **Never auto-resolved**: consensus engine bypassed, forced to **T4 + Legal hook** with both obligations + citations ([jurisdictional-conflict tree](../../docs/escalation/decision-trees/jurisdictional-conflict-tree.md)).

**CS-20 (coordinated).** All four agents: TM (300% LC mispricing + 5-hop wires), CS (RM overrode screening twice — override C7), RU (beneficiary country added to EDD list 2 weeks ago), RG (SAR + board package). Consensus 0.95 CRITICAL; multiple special triggers (sanctions, override, SAR) → **T4 + board reporting**.

## 6. Tier logic recap (applied uniformly)

`tier = max(confidence-band tier, severity-floor tier)`, then special triggers may only raise it. Bands: 0–.30→T0, .30–.55→T1, .55–.75→T2, .75–.90→T3, .90–1.00→T4. Floors: CRITICAL→T4, HIGH→T3, MEDIUM→T1, LOW/NO_ALERT→T0. See [master-escalation tree](../../docs/escalation/decision-trees/master-escalation-tree.md).

---
*End of SCENARIO-SUMMARY v1.0.0*
