"""Databus events for socket-ux (CF1): consume ``edo.projects.v1``.

``regimo-core`` publishes one semantic event per project change on the
``edo.projects.v1`` topic (6-header contract, see
``regimo_core.sync.events``). socket-ux consumes that topic in a background
thread and distributes the events to in-process subscribers — the SSE
endpoint ``GET /api/v1/events`` — so the front end can refresh the project
list without polling.

Consuming is *optional*: without ``KAFKA_BOOTSTRAP_SERVERS`` no subscriber
is started and the API keeps working (the drawer simply does not get
pushed updates).
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

#: topic on which regimo-core announces project created/updated/removed
PROJECTS_TOPIC = "edo.projects.v1"


@dataclass
class BusEvent:
    """One message from the databus, decoded for the SSE bridge."""

    topic: str
    payload: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def action(self) -> str:
        """``project.created`` / ``project.updated`` / ``project.removed``."""
        return str(self.payload.get("event", ""))

    @property
    def project(self) -> dict[str, Any]:
        project = self.payload.get("project")
        return project if isinstance(project, dict) else {}


def parse_kafka_message(msg: Any) -> BusEvent:
    """Decode a confluent-kafka message into a :class:`BusEvent`."""
    headers: dict[str, str] = {}
    for key, value in msg.headers() or []:
        if isinstance(value, bytes):
            value = value.decode("utf-8", "replace")
        headers[str(key)] = str(value)
    payload: dict[str, Any] = {}
    try:
        decoded = json.loads(msg.value().decode("utf-8"))
        if isinstance(decoded, dict):
            payload = decoded
    except Exception as exc:  # keep the stream alive on malformed messages
        logger.warning("undecodable bus message on %s: %s", msg.topic(), exc)
    return BusEvent(topic=msg.topic(), payload=payload, headers=headers)


class EventBus:
    """In-process broker fanning databus events out to SSE subscribers.

    The Kafka consumer thread calls :meth:`publish_threadsafe`; the asyncio
    side (the SSE generator) holds one :class:`asyncio.Queue` per subscriber.
    """

    def __init__(self) -> None:
        self._queues: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._queues.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._queues.discard(queue)

    def publish(self, event: BusEvent) -> None:
        """Loop-side publish (drop-oldest per subscriber, never blocks)."""
        for queue in list(self._queues):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(event)

    def publish_threadsafe(self, event: BusEvent) -> None:
        """Consumer-thread publish; bridges into the attached event loop."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(self.publish, event)


class BusSubscriber:
    """Background Kafka consumer thread feeding an :class:`EventBus`."""

    def __init__(self, bootstrap_servers: str, topic: str, broker: EventBus,
                 group_id: str = "socket-ux-events") -> None:
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.broker = broker
        self.group_id = group_id
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._consumer: Any = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="socket-ux-bus-subscriber", daemon=True)
        self._thread.start()

    def stop(self, timeout_s: float = 5.0) -> None:
        self._stop.set()
        if self._consumer is not None:
            try:
                self._consumer.close()
            except Exception:  # pragma: no cover — broker already gone
                pass
            self._consumer = None
        if self._thread is not None:
            self._thread.join(timeout=timeout_s)
            self._thread = None

    # -- consumer thread ------------------------------------------------------

    def _run(self) -> None:
        from confluent_kafka import Consumer

        self._consumer = Consumer({
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": self.group_id,
            "auto.offset.reset": "latest",
            "enable.auto.commit": True,
        })
        self._consumer.subscribe([self.topic])
        logger.info("bus subscriber listening on %s (%s)",
                    self.topic, self.bootstrap_servers)
        while not self._stop.is_set():
            try:
                msg = self._consumer.poll(0.5)
            except Exception as exc:
                logger.warning("bus poll failed: %s", exc)
                if self._stop.wait(2.0):
                    break
                continue
            if msg is None or msg.error():
                continue
            event = parse_kafka_message(msg)
            self.broker.publish_threadsafe(event)
            logger.debug("bus event forwarded: %s %s", event.action, event.project)


def subscriber_from_settings(broker: EventBus,
                             bootstrap_servers: str,
                             attach_loop: bool = True) -> BusSubscriber | None:
    """Build the subscriber when the databus is configured, else ``None``."""
    if not bootstrap_servers:
        logger.info("no databus configured — SSE will only carry local events")
        return None
    subscriber = BusSubscriber(bootstrap_servers, PROJECTS_TOPIC, broker)
    if attach_loop:
        try:
            broker.attach_loop(asyncio.get_running_loop())
        except RuntimeError:  # no running loop yet (tests) — attach later
            pass
    return subscriber
