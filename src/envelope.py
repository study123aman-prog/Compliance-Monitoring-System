"""
envelope.py — the inter-agent message envelope (protocol v1.0.0).

Every message on the bus is a Message with the 17 fields defined in
../docs/protocols/communication-protocol.md. Keeping this as a dataclass gives
us cheap validation and a clean `to_dict()` for the audit trail.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

from .domain import MessageType, AuditClass


def _now_iso() -> str:
    """ISO-8601 UTC timestamp with millisecond precision (temporal integrity)."""

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + \
        f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"


@dataclass
class Message:
    """The 17-field envelope. `payload` carries the type-specific body."""

    sender_agent_id: str
    recipient_agent_id: str | list[str]
    message_type: MessageType
    payload_schema: str
    payload: dict[str, Any]
    correlation_id: str
    # --- fields with sensible defaults ---
    priority: int = 3
    confidence_score: float | None = None
    audit_classification: AuditClass = AuditClass.OPERATIONAL
    protocol_version: str = "1.0.0"
    ttl_seconds: int = 86400
    retry_count: int = 0
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    timestamp: str = field(default_factory=_now_iso)
    nonce: str = field(default_factory=lambda: "n-" + uuid.uuid4().hex[:12])
    sender_signature: str = "base64(ECDSA-P256:PLACEHOLDER)"

    def to_dict(self) -> dict[str, Any]:
        """Serialise for logging / audit. Enums become their string values."""

        d = asdict(self)
        d["message_type"] = self.message_type.value
        d["audit_classification"] = self.audit_classification.value
        return d

    def validate(self) -> None:
        """Cheap structural validation. Raises ValueError on a malformed envelope.

        This is deliberately minimal — the JSON Schema in
        ../docs/protocols/message-schema.json is the authoritative contract; this
        just catches obvious programming errors early.
        """

        if not self.sender_agent_id:
            raise ValueError("sender_agent_id is required")
        if not self.recipient_agent_id:
            raise ValueError("recipient_agent_id is required")
        if not isinstance(self.message_type, MessageType):
            raise ValueError("message_type must be a MessageType")
        if self.confidence_score is not None and not (0.0 <= self.confidence_score <= 1.0):
            raise ValueError("confidence_score must be in [0, 1]")
        if not (1 <= self.priority <= 5):
            raise ValueError("priority must be in 1..5")
