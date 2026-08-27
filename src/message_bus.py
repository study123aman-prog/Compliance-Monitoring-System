"""
message_bus.py — a minimal in-memory publish/subscribe bus.

In the production design (see ../docs/architecture and ../docs/protocols) the
transport is Apache Kafka (durable, replayable topic log) plus Redis Streams
(low-latency heartbeats). For a single-process reference demo we don't need real
brokers — this class provides the same *semantics* the rest of the code relies
on: named topics, multiple subscribers, and a recorded history of everything
published (which mirrors Kafka's replayable log and is handy for assertions).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Callable

from .envelope import Message

# A subscriber is any callable that takes a Message and returns nothing.
Subscriber = Callable[[Message], None]

# The canonical topics from the protocol design.
TOPICS = (
    "transactions",
    "communications",
    "regulatory-updates",
    "agent-messages",
    "escalations",
    "heartbeats",
)


class MessageBus:
    """Synchronous in-memory pub/sub with a full published-message history.

    Synchronous delivery keeps the demo deterministic and easy to reason about
    (no threads, no ordering surprises) — important for the reproducibility the
    audit requirements demand.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Subscriber]] = defaultdict(list)
        self.history: list[tuple[str, Message]] = []  # (topic, message), in order

    def subscribe(self, topic: str, handler: Subscriber) -> None:
        """Register `handler` to receive every message published to `topic`."""

        self._subscribers[topic].append(handler)

    def publish(self, topic: str, message: Message) -> None:
        """Validate, record, and synchronously deliver a message to subscribers."""

        message.validate()
        self.history.append((topic, message))
        for handler in self._subscribers[topic]:
            handler(message)

    def messages_for(self, correlation_id: str) -> list[Message]:
        """Return all messages for one case, in publication order (a case trail)."""

        return [m for _, m in self.history if m.correlation_id == correlation_id]
