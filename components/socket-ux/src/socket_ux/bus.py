"""Ontology-aware bus events for socket-ux.

Implements the 6-header contract of ``regimo_core.interfaces.message``
(socket_id, ontology_uri, project_id, schema_id, timestamp, lineage) so the
socket is ontology-aware on the databus. Publishing is *optional*: when
``KAFKA_BOOTSTRAP_SERVERS`` is unset — or the broker is unreachable — events
are logged and the API keeps working. This keeps the socket usable before the
databus bridge exists.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

ORDERED_HEADER_KEYS = [
    "socket_id",
    "ontology_uri",
    "project_id",
    "schema_id",
    "timestamp",
    "lineage",
]

SOCKET_ID = "socket-ux"

# topic on which socket-ux announces served RO-Crates (CF3 entry points)
CRATE_TOPIC = "edo.crate.v1"


@dataclass
class MessageHeader:
    """Mirror of ``regimo_core.interfaces.message.MessageHeader``."""

    socket_id: str
    project_id: str
    schema_id: str
    ontology_uri: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    lineage: str = ""

    def to_dict(self) -> dict[str, str]:
        return {key: str(getattr(self, key) or "") for key in ORDERED_HEADER_KEYS}


def ontology_uri_from_path(path: str) -> str:
    """Best-effort ontology URI from the ontology file path (regimo.ttl)."""
    if not path:
        return ""
    stem = Path(path).stem
    return f"https://w3id.org/edo/ontology/{stem}" if stem else ""


class BusPublisher:
    """Optional JSON Kafka producer with the ontology-aware header contract."""

    def __init__(self, bootstrap_servers: str, ontology_uri: str = "") -> None:
        self.ontology_uri = ontology_uri
        self._producer = None
        if bootstrap_servers:
            try:
                from confluent_kafka import Producer

                self._producer = Producer({"bootstrap.servers": bootstrap_servers})
            except Exception as exc:  # broker/library unavailable — stay optional
                logger.warning("bus publishing disabled: %s", exc)

    def publish(self, topic: str, payload: dict, header: MessageHeader, timeout_s: float = 5.0) -> bool:
        if self._producer is None:
            logger.info("bus event (no producer): %s %s %s", topic, header.to_dict(), payload)
            return False
        try:
            self._producer.produce(
                topic,
                value=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers=[(k, v.encode("utf-8")) for k, v in header.to_dict().items()],
            )
            remainder = self._producer.flush(timeout_s)
            if remainder > 0:
                logger.warning("bus flush timed out for %s", topic)
                return False
            return True
        except Exception as exc:
            logger.warning("bus publish failed: %s", exc)
            return False
