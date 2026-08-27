# How It Works — A Plain-Language Walkthrough (Viva Prep)

> This is your study aid for explaining the project. It is written in plain language and anticipates the questions an examiner is likely to ask. It complements — does not replace — the formal design docs in `docs/`. If you can explain the eight sections below in your own words, you can defend the whole project.

---

## 0. The one-paragraph summary (say this first)

"I built a multi-agent compliance monitoring system for a large bank. Four specialist agents each watch one domain — trades, communications, and regulatory change — and raise opinions when they see something suspicious. Because more than one agent can look at the same event and disagree, a **consensus engine** reconciles their opinions using a mathematically defined rule. The result is passed to a **human-in-the-loop escalation framework** that decides which level of human reviewer sees it and how fast. Every single step is written to a **tamper-evident audit ledger** so a regulator can reconstruct exactly what happened and why. I deliberately made the decision logic **deterministic** — same inputs always give the same output — because compliance decisions have legal consequences and must be explainable and reproducible."

---

## 1. The problem the system solves

Banks generate millions of events a day — trades, emails, chat messages, wire transfers — and a tiny fraction of them are compliance violations (insider trading, market manipulation, money laundering, sanctions breaches). Regulators (SEC, FINRA, FCA, MAS, SEBI, RBI) require firms to *detect* these, *act* within tight deadlines (a SAR filing clock, a 72-hour GDPR breach clock), and *prove* they did so with complete records.

The hard parts, which the design specifically addresses:
- **No single agent sees the whole picture.** Insider trading shows up as both a *trade* pattern (TM) and a *communication* (CS). You need multiple agents and a way to combine them.
- **Agents will disagree.** One may say CRITICAL, another may see nothing. You need a principled way to resolve that — not just "take the average."
- **False positives are expensive too.** Blocking a legitimate $450M trade damages the client relationship. The system must be able to *stand down* when there's good exculpatory evidence — but only with documentation.
- **Everything must be provable years later.** If the record can be quietly altered, it is worthless to a regulator. Hence the tamper-evident ledger.

## 2. The moving parts (architecture)

**Four agents** (the "who is looking"):

| Agent | Watches | Strong in (authority weight) |
|---|---|---|
| **Transaction Monitor (TM)** | Trades: spoofing, wash trading, front-running, late trading, structuring, concentration | Trading `0.95`, Sanctions/AML `0.70` |
| **Communication Scanner (CS)** | Emails/chats/voice: misleading claims, info-barrier breaches, off-channel comms, *and the absence of expected comms* | Communications `0.95`, Record-keeping `0.90` |
| **Regulatory Update Tracker (RU)** | New rules, interpretation, cross-jurisdiction conflicts | Regulatory `0.95`, Sanctions/AML `0.75` |
| **Report Generator (RG)** | Assembles the regulator-facing report | (does not vote) |

**Four coordination components** (the "how it's decided and recorded"):

- **Orchestrator** — the router. Events arrive on topics (`transactions`, `communications`, `reg-updates`); it sends each to the right agent(s), then hands their opinions to consensus. It is a *mediator*, so the whole chain stays reconstructable.
- **Consensus Engine** — reconciles multiple opinions into one result (Section 4). This is the intellectual core.
- **Escalation Manager** — turns the result into a **tier** (T0–T4), an SLA clock, and a decision-support package for a human.
- **Audit Ledger** — a hash-chained, append-only log of every event (Section 6).

> **Naming trap an examiner may test you on:** the agent "CS" (Communication Scanner) is *not* the same as the scenario IDs "CS-01…CS-20", where "CS" is just the assessment's scenario prefix. I documented this explicitly.

## 3. End-to-end flow of one case (walk through CS-01)

CS-01 is insider trading: a portfolio manager accumulates a stock over three weeks; internal emails show he had dinner with the target company's CFO; the stock jumps 35% on an acquisition announcement two days later.

1. **Ingest & route.** The trade pattern arrives on `transactions` → Orchestrator routes to **TM**. The email linkage arrives on `communications` → routed to **CS**. They share a `correlation_id` so the system knows they're about the same case.
2. **Detect.** TM assesses the accumulation-before-announcement pattern → opinion: **HIGH, confidence 0.72**, domain *trading*. CS assesses the dinner email → opinion: **HIGH, confidence 0.80**, domain *communications*.
3. **Consensus.** Two agents, severities agree (both HIGH), so the engine uses **Dempster–Shafer combination** (corroboration). The two independent signals combine into **CRITICAL @ 0.92** (worked math in Section 4).
4. **Escalate.** CRITICAL → severity floor T4; confidence 0.92 → band T4; `tier = max(T4, T4) = T4`. This is an insider-trading/SAR matter, so the SAR trigger also forces T4 and starts the 24-hour clock. A decision-support package (both opinions, the evidence refs, the consensus math) is assembled for a Director-level human.
5. **Report.** RG builds the case report.
6. **Audit.** Every one of those steps — each detection, the consensus computation with all its inputs and intermediate masses, the escalation decision — was written to the ledger as it happened.

The key insight to state: **the path is identical for all 20 scenarios.** Only the inputs differ. That is what makes the behaviour reproducible and the audit trail complete "by construction."

## 4. The consensus engine (the core — expect the most questions here)

When two or more agents assess the same case, the engine picks **one** of five mechanisms by an explicit selection rule. Say it as: *"I don't average opinions — I choose the right mechanism for the situation."*

**(a) One agent only → passthrough.** Use that agent's severity and confidence directly. (Most single-agent scenarios: CS-02, 04, 05, 06, 07, 08, 10, 12, 13, 14, 15.)

**(b) Agents agree (within one severity level) → Dempster–Shafer combination.** This is *corroboration*: two independent, moderately-confident signals should make you **more** sure, not just averagely sure.

Here is the math for CS-01, which you should be able to reproduce on a whiteboard:

- Set up a "frame of discernment" with two possibilities: **V** (violation) and **B** (benign). Each agent puts its belief as *mass*.
- Each agent's mass toward V is `authority × confidence`:
  - TM: `0.95 × 0.72 = 0.684` on V; the rest, `0.316`, is "don't know" (Θ), **not** benign.
  - CS: `0.95 × 0.80 = 0.760` on V; `0.240` on "don't know".
- Neither agent asserted *benign*, so there is **no conflict** (K = 0). Combine:
  - `Belief(V) = m₁(V) + m₂(V) − m₁(V)·m₂(V) = 0.684 + 0.760 − 0.684·0.760 = 0.924`.
- So consensus confidence ≈ **0.92**. Two HIGHs corroborate; the 0.92 lands in the top confidence band, which elevates severity to **CRITICAL** (elevation is *raise-only* — corroboration can raise severity but never lower an asserted one).

Why Dempster–Shafer and not simple probability? Because it has an explicit "don't know" state (Θ). A surveillance agent *raises suspicion*; it does not assert innocence. That distinction is exactly what makes the false-positive case (CS-18) work.

**(c) Agents genuinely disagree (more than one level apart) → weighted voting with a safety test.** Compute a weighted score per severity (`authority × confidence`), pick the winner, then check two things:
- **margin** = how decisively it won, and
- **K** = how much the two leading opinions conflict.

If `margin ≥ 0.20` **and** `K ≤ 0.60`, accept the winner. **Otherwise the case is UNRESOLVED and goes to a human at the *higher*-severity tier** — never the lower one. Say it as: *"When the machine isn't sure, it fails safe toward human review at the more serious level."*

**(d) An authenticated benign verification → suppression (CS-18).** A $450M block trade looks alarming (TM: HIGH @ 0.68). But there's an authenticated record that it was pre-arranged with the block desk and is disclosed portfolio rebalancing. That verification carries **benign** mass. Now V and B conflict, so we use the *full* Dempster's rule with normalisation by (1 − K). The benign evidence outweighs the suspicion, belief in V drops below the **0.30 suppression threshold**, and the alert is suppressed as **NO_ALERT** — *with the reasoning written to the audit ledger.* Incorrectly escalating this scenario is a −25 point penalty in the rubric, so it matters.

**(e) Conflict-of-laws (C5) → jurisdictional bypass (CS-19).** An EU rule says "report thisderivative data within one business day"; a Singapore rule says "you may not send this data across the border." These are genuinely irreconcilable by a machine. The engine **refuses to auto-resolve** and routes straight to Legal (T4, unresolved flag). Say it as: *"Some conflicts shouldn't be automated away — the honest answer is to escalate to a human lawyer."*

**The constants** (know these four): `τ_assert = 0.25` (minimum weighted confidence for an opinion to count as "asserting" a severity), `δ_margin = 0.20` (voting decisiveness threshold), `κ_conflict = 0.60` (max tolerated conflict), `suppression_threshold = 0.30` (belief in V below this, given a benign verification, means suppress). No randomness, no clock dependence — that's what makes it deterministic.

## 5. From result to human action (escalation)

Two ideas, both "raise-only" for safety:

- **Tier = max(confidence-band tier, severity-floor tier).** The *severity floor* guarantees a CRITICAL reaches a Director even if confidence is only moderate — because the cost of missing a real critical violation dominates. Confidence bands: `[0,.30)→T0, [.30,.55)→T1, [.55,.75)→T2, [.75,.90)→T3, [.90,1]→T4`. Severity floors: `CRITICAL→T4, HIGH→T3, MEDIUM→T1, LOW/NO_ALERT→T0`.
- **Special triggers can only raise the tier, never lower it:** SAR/sanctions/GDPR clocks, authorised-control override (C7), a senior person being the *subject* of the alert (conflict-of-interest reroute), and jurisdictional conflict (C5). Each also attaches the right SLA and, where needed, dual-control (two-person sign-off) or a legal/board hook.

Only a case that is low-severity **and** low-confidence **and** trigger-free lands at T0 — and even then it's *auto-closed with written reasoning and an audit entry*, never silently dropped.

## 6. Why the audit trail can't be faked (tamper-evidence)

Each ledger entry stores the previous entry's hash plus its own content, and computes `entry_hash = SHA-256(prev_hash ‖ sequence ‖ payload)`. This chains the entries like a blockchain: if anyone edits a past entry, its hash changes, which breaks the `prev_hash` link of every entry after it — so verification instantly detects *where* the tampering happened. Entries are also signed (I used HMAC-SHA256 as an **honestly-documented stand-in** for ECDSA P-256 — the chaining is real; only the signature primitive is simplified so the demo needs no external libraries). The ledger is **append-only (WORM)**, which satisfies the intent of **SEC Rule 17a-4(f)**.

The demo proves this live: it verifies the 109-entry chain (True), mutates one entry (verification → False, and it names the exact sequence number), then restores it (True again).

## 7. Why I built it this way (technology justification)

The brief recommended frameworks like CrewAI, AutoGen, and LangGraph and asked me to justify my choice. **I chose a lightweight, custom, deterministic architecture in pure Python instead.** The reasons — say these confidently:

1. **Compliance decisions must be deterministic and reproducible.** The brief itself says two independent implementers should get identical behaviour. LLM-driven agent frameworks are stochastic; they can't guarantee that for the *decision* layer.
2. **They must be explainable to a lawyer.** A transparent rule — Dempster–Shafer, weighted voting with an explicit margin/conflict test, fixed thresholds — can be walked through line by line. An opaque model chain cannot.
3. **They must be auditable.** A hash-chained WORM ledger is simple to reason about and prove tamper-evident.
4. **Pure standard library = no dependencies.** It runs anywhere, has no supply-chain risk, and — importantly for this assessment — *every line can be explained in a viva.*

**Where does ML belong, then?** In the **detection layer** — NLP for reading communications, anomaly models for trading patterns. Each agent spec describes those. What stays deterministic is the **coordination layer**: how opinions are combined, escalated, and recorded. Slogan: *"ML proposes; the deterministic layer disposes and documents."*

## 8. The 20 scenarios at a glance

- **8 "standard" (single-agent, passthrough):** CS-02, 04, 07, 08, 12, 13, 14, 15.
- **10 "complex" (multi-agent or elevated):** CS-01, 03, 05, 06, 09, 10, 11, 16, 17, 19.
- **2 special:** CS-18 (false positive → suppressed) and CS-20 (coordinated → all four agents).
- **10 are CRITICAL:** CS-01, 04, 05, 08, 09, 10, 14, 16, 17, 20 (this earns the "Pattern Hunter" badge).

The four you should be ready to walk through in detail: **CS-01** (corroboration → CRITICAL), **CS-18** (suppression), **CS-19** (jurisdictional bypass), **CS-20** (full four-agent coordination with SAR + board reporting).

---

## Likely viva questions (and short answers)

- **"How do you avoid just averaging opinions?"** I don't average — I select a mechanism. Corroborating opinions combine via Dempster–Shafer (confidence goes *up*); genuinely conflicting ones go to weighted voting with a safety test, and if it's close on a serious matter, it escalates to a human.
- **"What stops a low-confidence critical alert from being ignored?"** The severity floor: CRITICAL forces at least tier T4 regardless of confidence.
- **"What if two agents are exactly tied?"** Tie goes to the *higher* severity (conservative). Persistent ties escalate.
- **"How is a false positive different from a miss?"** A false positive (CS-18) is suppressed *only* with an authenticated benign verification and a written audit reason; absence of evidence never suppresses a critical alert.
- **"Prove the log can't be tampered with."** Run the demo — it detects a single mutated entry by breaking the hash chain and reports the exact sequence number.
- **"Why not use an LLM agent framework?"** Determinism, explainability, auditability, and zero dependencies — all legal requirements for surveillance, none guaranteed by a stochastic framework.
- **"Where would real ML go?"** In detection (NLP, anomaly detection), not in the decision/consensus layer.
- **"Did you find errors in the spec?"** Yes — five, documented in the README with corrections and citations (e.g., Section A2.1 says "three" primary topologies but lists four; Part C says "four" case studies but presents five; CS-05 cites the wrong MiFID II article for information barriers).

---
*Study tip: practise reproducing the CS-01 Dempster–Shafer calculation and the tier = max(floor, band) rule on paper. Those two are the heart of the system.*
