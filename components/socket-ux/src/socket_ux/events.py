"""Databus events for socket-ux (CF1): consume the ``edo.*`` topics.

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
import datetime as _dt
from dataclasses import dataclass, field
from typing import Any, Callable

from .databus import DatabusStore, StoredMessage

logger = logging.getLogger(__name__)

#: topic on which regimo-core announces project created/updated/removed
PROJECTS_TOPIC = "edo.projects.v1"

#: subscription pattern of the bridge consumer (CF1-012): everything the
#: sockets publish lives under the ``edo.`` prefix; Kafka-internal topics
#: (``__consumer_offsets``, ``_schemas``, …) never match it.
TOPIC_PATTERN = "^edo\\."


@dataclass
class BusEvent:
    """One message from the databus, decoded for the SSE bridge."""

    topic: str
    payload: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    # Kafka bookkeeping for the REST bridge's ring buffer (CF1-012); ``None``
    # when the carrier is not a real Kafka message (tests, local events).
    partition: int | None = None
    offset: int | None = None
    timestamp: str | None = None

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
    return BusEvent(
        topic=msg.topic(), payload=payload, headers=headers, **message_meta(msg))


def message_meta(msg: Any) -> dict[str, Any]:
    """Partition/offset/broker-timestamp of a Kafka message, defensively.

    Fake carriers (tests, locally built events) may lack those attributes;
    they then simply stay ``None``.
    """
    meta: dict[str, Any] = {"partition": None, "offset": None, "timestamp": None}
    try:
        meta["partition"] = int(msg.partition())
        meta["offset"] = int(msg.offset())
        ts_type, ts_ms = msg.timestamp()
        if ts_ms and ts_ms > 0:
            meta["timestamp"] = _dt.datetime.fromtimestamp(
                ts_ms / 1000, tz=_dt.timezone.utc).isoformat()
    except Exception:  # not a real Kafka message — keep the Nones
        pass
    return meta


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
                 group_id: str = "socket-ux-events",
                 store: DatabusStore | None = None,
                 pattern: str = "") -> None:
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.broker = broker
        self.group_id = group_id
        self.store = store
        self.pattern = pattern
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
            # "earliest" so the bridge's ring buffer is filled with a topic's
            # recent history on first assignment (no committed offset yet);
            # with committed offsets the consumer resumes where it left off.
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
        })
        # With a pattern the consumer follows every matching topic (the
        # bridge must also see e.g. ``edo.dmp.v1``); without one the classic
        # single-topic subscription is kept.
        subscription = [self.pattern] if self.pattern else [self.topic]
        self._consumer.subscribe(subscription)
        logger.info("bus subscriber listening on %s (%s)",
                    subscription, self.bootstrap_servers)
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
            if self.store is not None:
                self.store.record(StoredMessage(
                    topic=event.topic, payload=event.payload,
                    header=event.headers, partition=event.partition,
                    offset=event.offset, timestamp=event.timestamp,
                ))
            self.broker.publish_threadsafe(event)
            logger.debug("bus event forwarded: %s %s", event.action, event.project)


def subscriber_from_settings(broker: EventBus,
                             bootstrap_servers: str,
                             attach_loop: bool = True,
                             store: DatabusStore | None = None,
                             pattern: str = TOPIC_PATTERN) -> BusSubscriber | None:
    """Build the subscriber when the databus is configured, else ``None``.

    By default it subscribes to every ``edo.*`` topic and feeds both the SSE
    fan-out and the REST bridge's ring buffer (``store``).
    """
    if not bootstrap_servers:
        logger.info("no databus configured — SSE will only carry local events")
        return None
    subscriber = BusSubscriber(bootstrap_servers, PROJECTS_TOPIC, broker,
                               store=store, pattern=pattern)
    if attach_loop:
        try:
            broker.attach_loop(asyncio.get_running_loop())
        except RuntimeError:  # no running loop yet (tests) — attach later
            pass
    return subscriber
