"""
audit_ledger.py — tamper-evident, append-only audit trail.

Implements the design in ../docs/observability/audit-trail.md:
  * SHA-256 hash chaining      -> tamper evidence (each entry embeds prev hash)
  * per-actor signature        -> authenticity (who wrote this entry)
  * append-only, monotonic seq -> completeness / gap detection
  * verify() recomputes the whole chain and every signature

NOTE ON CRYPTO (important for the viva): the design specifies ECDSA P-256 for
signatures. To keep this reference demo dependency-free (standard library only,
no `cryptography` package, no key distribution), we stand in an HMAC-SHA256
signature keyed per actor. The *chain* is genuine SHA-256 exactly as specified;
only the signature primitive is simplified. Swapping in real ECDSA is a drop-in
change at sign()/verify() — the surrounding logic is identical. This is called
out honestly rather than pretending HMAC is a public-key signature.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .domain import AuditClass

GENESIS_PREV = "sha256:" + hashlib.sha256(b"GENESIS:compliance-monitor-463548B").hexdigest()

# Demo signing keys per actor (in production these are ECDSA private keys held in
# an HSM/KMS; here they are opaque HMAC secrets used only to demonstrate authenticity).
_DEMO_KEYS: dict[str, bytes] = {}


def _key_for(actor: str) -> bytes:
    """Return (creating if needed) a stable demo signing key for an actor."""

    if actor not in _DEMO_KEYS:
        _DEMO_KEYS[actor] = hashlib.sha256(f"demo-key::{actor}".encode()).digest()
    return _DEMO_KEYS[actor]


def _canonical(obj: Any) -> bytes:
    """Deterministic serialisation so hashing is reproducible across runs/machines."""

    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()


@dataclass
class AuditEntry:
    """One immutable record in the chain."""

    seq: int
    correlation_id: str
    actor: str
    action: str
    details: dict[str, Any]
    audit_classification: AuditClass
    prev_hash: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    )
    entry_hash: str = ""       # filled by the ledger
    signature: str = ""        # filled by the ledger

    def body(self) -> dict[str, Any]:
        """The signed/hashed body — everything except the hash & signature."""

        return {
            "seq": self.seq,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "actor": self.actor,
            "action": self.action,
            "details": self.details,
            "audit_classification": self.audit_classification.value,
            "prev_hash": self.prev_hash,
        }


class AuditLedger:
    """Append-only ledger. `append()` is the only way to add entries; there is no
    update or delete — mirroring WORM storage."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    @property
    def entries(self) -> list[AuditEntry]:
        return list(self._entries)  # a copy: callers cannot mutate the chain

    @property
    def head_hash(self) -> str:
        return self._entries[-1].entry_hash if self._entries else GENESIS_PREV

    def append(
        self,
        correlation_id: str,
        actor: str,
        action: str,
        details: dict[str, Any] | None = None,
        audit_classification: AuditClass = AuditClass.REGULATORY,
    ) -> AuditEntry:
        """Create, hash, sign, and append one entry; returns it."""

        entry = AuditEntry(
            seq=len(self._entries),
            correlation_id=correlation_id,
            actor=actor,
            action=action,
            details=details or {},
            audit_classification=audit_classification,
            prev_hash=self.head_hash,
        )
        # entry_hash = SHA256( canonical(body) || prev_hash )   -- the chain link
        digest = hashlib.sha256(_canonical(entry.body()) + entry.prev_hash.encode()).hexdigest()
        entry.entry_hash = "sha256:" + digest
        # signature over the entry_hash, keyed by the actor (ECDSA stand-in)
        entry.signature = "hmac:" + hmac.new(
            _key_for(actor), entry.entry_hash.encode(), hashlib.sha256
        ).hexdigest()
        self._entries.append(entry)
        return entry

    def verify(self) -> tuple[bool, str]:
        """Recompute the entire chain + every signature.

        Returns (ok, message). If any entry was modified, deleted, or reordered,
        the recomputed hash or the prev_hash link (or a signature) will not match
        and we report the first offending sequence number.
        """

        prev = GENESIS_PREV
        for e in self._entries:
            expect = "sha256:" + hashlib.sha256(
                _canonical(e.body()) + prev.encode()
            ).hexdigest()
            if e.prev_hash != prev:
                return False, f"broken link at seq={e.seq} (prev_hash mismatch)"
            if e.entry_hash != expect:
                return False, f"tampered content at seq={e.seq} (entry_hash mismatch)"
            expect_sig = "hmac:" + hmac.new(
                _key_for(e.actor), e.entry_hash.encode(), hashlib.sha256
            ).hexdigest()
            if e.signature != expect_sig:
                return False, f"bad signature at seq={e.seq}"
            prev = e.entry_hash
        return True, f"chain OK: {len(self._entries)} entries verified"
