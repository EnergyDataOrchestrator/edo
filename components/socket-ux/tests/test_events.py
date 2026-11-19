"""Tests for the databus event bridge (CF1): broker, parsing, SSE endpoint."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from socket_ux.events import (
    PROJECTS_TOPIC,
    BusEvent,
    EventBus,
    parse_kafka_message,
    subscriber_from_settings,
)


# -- message decoding ---------------------------------------------------------

def _kafka_message(value: dict | bytes, headers: list[tuple[str, bytes | str]] | None = None,
                  topic: str = PROJECTS_TOPIC):
    return SimpleNamespace(
        topic=lambda: topic,
        value=lambda: value if isinstance(value, bytes) else json.dumps(value).encode(),
        headers=lambda: headers or [],
    )


def test_parse_kafka_message_decodes_payload_and_headers():
    msg = _kafka_message(
        {"event": "project.created", "project": {"id": 4, "title": "Measurement_02"}},
        [("socket_id", b"regimo-core"), ("project_id", "4")],
    )
    event = parse_kafka_message(msg)
    assert event.topic == PROJECTS_TOPIC
    assert event.action == "project.created"
    assert event.project == {"id": 4, "title": "Measurement_02"}
    assert event.headers == {"socket_id": "regimo-core", "project_id": "4"}


def test_parse_kafka_message_survives_malformed_payload():
    event = parse_kafka_message(_kafka_message(b"not json"))
    assert event.payload == {}
    assert event.action == ""


# -- broker -------------------------------------------------------------------

def test_event_bus_fans_out_to_subscribers():
    broker = EventBus()
    loop = asyncio.new_event_loop()
    try:
        broker.attach_loop(loop)
        first, second = broker.subscribe(), broker.subscribe()
        event = BusEvent(topic=PROJECTS_TOPIC, payload={"event": "project.updated"})
        broker.publish(event)
        assert loop.run_until_complete(first.get()) is event
        assert loop.run_until_complete(second.get()) is event
        broker.unsubscribe(first)
        broker.publish(event)
        assert loop.run_until_complete(second.get()) is event
        assert first.empty()
    finally:
        loop.close()


def test_event_bus_publish_threadsafe_bridges_loop():
    broker = EventBus()
    loop = asyncio.new_event_loop()
    try:
        broker.attach_loop(loop)
        queue = broker.subscribe()
        event = BusEvent(topic=PROJECTS_TOPIC, payload={"event": "project.created"})
        # called from a foreign thread (as the Kafka consumer would)
        broker.publish_threadsafe(event)
        received = loop.run_until_complete(asyncio.wait_for(queue.get(), 2.0))
        assert received is event
    finally:
        loop.close()


def test_event_bus_drops_oldest_when_queue_full():
    broker = EventBus()
    loop = asyncio.new_event_loop()
    try:
        broker.attach_loop(loop)
        queue = broker.subscribe()
        for i in range(70):
            broker.publish(BusEvent(topic=PROJECTS_TOPIC, payload={"n": i}))
        assert queue.qsize() == 64
        assert loop.run_until_complete(queue.get()).payload["n"] == 6
    finally:
        loop.close()


def test_subscriber_from_settings_requires_bootstrap_servers():
    assert subscriber_from_settings(EventBus(), "") is None


def test_subscriber_from_settings_builds_when_configured():
    subscriber = subscriber_from_settings(EventBus(), "localhost:9092",
                                          attach_loop=False)
    assert subscriber is not None
    assert subscriber.topic == PROJECTS_TOPIC


# -- SSE formatting + endpoint ------------------------------------------------


def test_format_sse_maps_project_events_to_projects_changed():
    event = BusEvent(
        topic=PROJECTS_TOPIC,
        payload={"event": "project.created",
                 "project": {"id": 4, "title": "Measurement_02"}},
    )
    assert event.action == "project.created"
    from socket_ux.api import format_sse

    rendered = format_sse(event)
    assert rendered.startswith("event: projects-changed\ndata: ")
    assert "Measurement_02" in rendered
    assert rendered.endswith("\n\n")


def test_format_sse_keeps_other_event_names():
    from socket_ux.api import format_sse

    rendered = format_sse(BusEvent(topic="local.crate.v1",
                                   payload={"event": "crate.served"}))
    assert rendered.startswith("event: crate.served\ndata: ")


def test_sse_endpoint_negotiates_event_stream():
    from fastapi.testclient import TestClient

    from socket_ux.api import app

    with TestClient(app) as client:
        with client.stream("GET", "/api/v1/events") as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            assert response.headers["cache-control"] == "no-cache"
