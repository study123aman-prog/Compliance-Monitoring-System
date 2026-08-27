"""
Multi-Agent Compliance Monitoring System — reference implementation.

This package is a lightweight, pure-standard-library reference implementation of
the design documented under ../docs. It is intentionally small and readable: the
goal is to *demonstrate and verify* the design (especially the consensus and
escalation logic and the tamper-evident audit trail), not to be a production
deployment.

Module map
----------
- domain.py         : enums and constant tables (severity, tier, domain, SLAs, thresholds)
- envelope.py       : the 17-field inter-agent message envelope
- message_bus.py    : an in-memory pub/sub bus (stands in for Kafka + Redis Streams)
- audit_ledger.py   : SHA-256 hash-chained, signed, append-only audit ledger
- consensus.py      : the hybrid Dempster-Shafer / weighted-voting consensus engine
- escalation.py     : tier logic (tier = max(band, floor), raised by special triggers) + SLAs
- agents/           : the four specialist agents + a shared base class
- orchestrator.py   : wires everything together; processes a case end to end
- scenarios.py      : the 20 mandatory scenarios encoded as data
- run_demo.py       : runs all 20 scenarios and prints a results table

No third-party dependencies are required to run the demo. `pytest` is used only
for the test-suite under ../tests.
"""

__version__ = "1.0.0"
__author__ = "Aman Singh"
