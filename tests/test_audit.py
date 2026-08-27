"""
test_audit.py — the audit ledger must be tamper-evident and append-only.

Run with:  pytest -q
"""
from __future__ import annotations

from src.audit_ledger import AuditLedger, GENESIS_PREV
from src.domain import AuditClass


def _seed(ledger: AuditLedger, n: int = 5) -> None:
    for i in range(n):
        ledger.append(f"CS-{i:02d}", "agent.transaction_monitor",
                      "detection.alert", {"i": i}, AuditClass.REGULATORY)


def test_empty_head_is_genesis() -> None:
    assert AuditLedger().head_hash == GENESIS_PREV


def test_intact_chain_verifies() -> None:
    ledger = AuditLedger()
    _seed(ledger)
    ok, msg = ledger.verify()
    assert ok, msg
    assert "5 entries" in msg


def test_sequence_is_monotonic_and_gapless() -> None:
    ledger = AuditLedger()
    _seed(ledger, 6)
    assert [e.seq for e in ledger.entries] == [0, 1, 2, 3, 4, 5]


def test_each_entry_links_to_previous_hash() -> None:
    ledger = AuditLedger()
    _seed(ledger, 4)
    entries = ledger.entries
    assert entries[0].prev_hash == GENESIS_PREV
    for prev, cur in zip(entries, entries[1:]):
        assert cur.prev_hash == prev.entry_hash


def test_content_tamper_is_detected() -> None:
    ledger = AuditLedger()
    _seed(ledger)
    ledger._entries[2].details = {"i": 999}          # silently alter a record
    ok, msg = ledger.verify()
    assert not ok
    assert "seq=2" in msg


def test_reorder_tamper_is_detected() -> None:
    ledger = AuditLedger()
    _seed(ledger)
    ledger._entries[1], ledger._entries[2] = ledger._entries[2], ledger._entries[1]
    ok, _ = ledger.verify()
    assert not ok


def test_signature_tamper_is_detected() -> None:
    ledger = AuditLedger()
    _seed(ledger)
    ledger._entries[3].signature = "hmac:deadbeef"
    ok, msg = ledger.verify()
    assert not ok
    assert "seq=3" in msg


def test_entries_property_returns_defensive_copy() -> None:
    """Callers must not be able to mutate the chain via the public accessor."""

    ledger = AuditLedger()
    _seed(ledger, 3)
    ledger.entries.clear()               # mutate the returned copy
    assert len(ledger.entries) == 3      # internal chain is untouched
