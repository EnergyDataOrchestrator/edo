"""Kafka REST bridge internals for socket-ux (CF1-012).

Browsers cannot speak the Kafka wire protocol, so socket-ux exposes the bus
as plain REST under ``/api/v1/bus/…`` (the contract
``frontend/vue-frontend/src/lib/databus.ts`` already calls). This module holds
the two building blocks behind those endpoints:

* :class:`DatabusStore` — a bounded per-topic ring buffer of decoded messages
  (Kafka has no native tail-N read; per-request consumer seeks are slow and
  unbounded, while the buffer is filled anyway by the consumer thread).
* :func:`list_topics` / :func:`broker_online` — thin AdminClient wrappers for
  topic listing and reachability probes.

Messages are recorded with the 6-header contract (see :mod:`socket_ux.bus`)
displayed *verbatim* — the bridge never transforms it.
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class StoredMessage:
    """One decoded bus message as served by the bridge endpoints."""

    topic: str
    payload: Any
    header: dict[str, str] = field(default_factory=dict)
    partition: int | None = None
    offset: int | None = None
    timestamp: str | None = None  # ISO-8601 UTC (broker time)

    def as_api(self) -> dict[str, Any]:
        """Shape expected by the frontend ``BusMessage`` interface."""
        doc: dict[str, Any] = {
            "topic": self.topic,
            "payload": self.payload,
            "header": self.header,
        }
        if self.partition is not None:
            doc["partition"] = self.partition
        if self.offset is not None:
            doc["offset"] = self.offset
        return doc


class DatabusStore:
    """Bounded per-topic ring buffers, filled by the Kafka consumer thread.

    Thread-safe: the consumer thread records, the API event loop reads. A
    message already recorded by its ``(topic, partition, offset)`` position
    is skipped, so a locally published message (recorded by the POST endpoint
    for immediacy) is not shown twice when the consumer receives it again.
    """

    def __init__(self, capacity: int = 100) -> None:
        self.capacity = max(1, capacity)
        self._buffers: dict[str, deque[StoredMessage]] = {}
        self._seen: dict[str, set[tuple[int, int]]] = {}
        self._lock = threading.Lock()

    def record(self, message: StoredMessage) -> None:
        with self._lock:
            if message.partition is not None and message.offset is not None:
                seen = self._seen.setdefault(message.topic, set())
                position = (message.partition, message.offset)
                if position in seen:
                    return
                seen.add(position)
                if len(seen) > self.capacity * 10:  # keep the set bounded
                    seen.clear()
                    seen.add(position)
            buffer = self._buffers.setdefault(
                message.topic, deque(maxlen=self.capacity))
            buffer.append(message)

    def recent(self, topic: str, limit: int = 20) -> list[StoredMessage]:
        """The last ``limit`` messages of one topic, oldest first."""
        with self._lock:
            buffer = self._buffers.get(topic)
            items = list(buffer) if buffer else []
        return items[-max(0, limit):]

    def counts(self) -> dict[str, int]:
        """Buffered message count per topic (for the status endpoint)."""
        with self._lock:
            return {topic: len(buffer) for topic, buffer in self._buffers.items()}


def list_topics(bootstrap_servers: str, timeout_s: float = 5.0) -> list[dict[str, Any]]:
    """Topics of the broker as ``[{name, partitions}]``, internals filtered.

    Raises on any broker error (the API endpoint turns that into a 503, the
    frontend falls back to its demo mode).
    """
    from confluent_kafka.admin import AdminClient

    admin = AdminClient({"bootstrap.servers": bootstrap_servers})
    metadata = admin.list_topics(timeout=timeout_s)
    return [
        {"name": name, "partitions": len(meta.partitions)}
        for name, meta in sorted(metadata.topics.items())
        if not name.startswith("__") and not name.startswith("_")
    ]


def broker_online(bootstrap_servers: str, timeout_s: float = 2.0) -> bool:
    """Cheap reachability probe (used by ``GET /api/v1/bus/status``)."""
    if not bootstrap_servers:
        return False
    try:
        list_topics(bootstrap_servers, timeout_s)
        return True
    except Exception as exc:  # noqa: BLE001 — offline must stay non-fatal
        logger.info("bus broker probe failed: %s", exc)
        return False
