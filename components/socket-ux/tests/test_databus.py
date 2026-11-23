"""Tests for the databus REST bridge (CF1-012): store, parsing, endpoints."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from socket_ux import api
from socket_ux.config import Settings
from socket_ux.databus import DatabusStore, StoredMessage
from socket_ux.events import PROJECTS_TOPIC, parse_kafka_message


# -- ring buffer ---------------------------------------------------------------

def test_store_records_and_returns_recent_oldest_first():
    store = DatabusStore()
    for i in range(3):
        store.record(StoredMessage(topic="edo.dmp.v1", payload={"n": i}, offset=i))
    recent = store.recent("edo.dmp.v1", limit=2)
    assert [m.payload["n"] for m in recent] == [1, 2]


def test_store_evicts_beyond_capacity():
    store = DatabusStore(capacity=3)
    for i in range(5):
        store.record(StoredMessage(topic="t", payload={"n": i}, offset=i))
    assert [m.payload["n"] for m in store.recent("t", limit=100)] == [2, 3, 4]


def test_store_deduplicates_by_topic_partition_offset():
    store = DatabusStore()
    message = StoredMessage(topic="t", payload={"n": 1}, partition=0, offset=7)
    store.record(message)
    store.record(message)  # e.g. consumer round trip of a locally published one
    assert store.counts() == {"t": 1}


def test_store_counts_per_topic():
    store = DatabusStore()
    store.record(StoredMessage(topic="a", payload={}))
    store.record(StoredMessage(topic="b", payload={}))
    store.record(StoredMessage(topic="b", payload={}))
    assert store.counts() == {"a": 1, "b": 2}


# -- message parsing: Kafka bookkeeping -----------------------------------------

def test_parse_kafka_message_extracts_partition_offset_timestamp():
    msg = SimpleNamespace(
        topic=lambda: PROJECTS_TOPIC,
        value=lambda: json.dumps({"event": "project.created"}).encode(),
        headers=lambda: [],
        partition=lambda: 0,
        offset=lambda: 42,
        timestamp=lambda: (1, 1_766_000_000_000),  # broker timestamp, epoch ms
    )
    event = parse_kafka_message(msg)
    assert event.partition == 0
    assert event.offset == 42
    assert event.timestamp is not None and event.timestamp.startswith("2025-")


def test_parse_kafka_message_survives_missing_bookkeeping():
    msg = SimpleNamespace(
        topic=lambda: PROJECTS_TOPIC,
        value=lambda: json.dumps({}).encode(),
        headers=lambda: [],
    )
    event = parse_kafka_message(msg)
    assert (event.partition, event.offset, event.timestamp) == (None, None, None)


# -- API endpoints ---------------------------------------------------------------

class FakeSettings(Settings):
    def __init__(self) -> None:
        # admin: these tests exercise the bus bridge itself, above every gate
        super().__init__(kafka_bootstrap_servers="localhost:9092", role="admin")


def test_bus_topics_endpoint(monkeypatch):
    monkeypatch.setattr(api, "get_settings", FakeSettings)
    monkeypatch.setattr(api, "list_topics", lambda servers, timeout_s=5.0: [
        {"name": "edo.dmp.v1", "partitions": 1},
        {"name": "edo.projects.v1", "partitions": 1},
    ])
    client = TestClient(api.app)
    body = client.get("/api/v1/bus/topics").json()
    assert [t["name"] for t in body["topics"]] == ["edo.dmp.v1", "edo.projects.v1"]
    assert body["topics"][0]["partitions"] == 1


def test_bus_topics_endpoint_offline_answers_503(monkeypatch):
    class NoBusSettings(Settings):
        def __init__(self) -> None:
            super().__init__(kafka_bootstrap_servers="", role="admin")

    monkeypatch.setattr(api, "get_settings", NoBusSettings)
    client = TestClient(api.app)
    response = client.get("/api/v1/bus/topics")
    assert response.status_code == 503


def test_bus_topics_endpoint_unreachable_broker_answers_503(monkeypatch):
    monkeypatch.setattr(api, "get_settings", FakeSettings)

    def boom(servers, timeout_s=5.0):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(api, "list_topics", boom)
    client = TestClient(api.app)
    assert client.get("/api/v1/bus/topics").status_code == 503


def test_bus_messages_endpoint_serves_buffered_messages(monkeypatch):
    monkeypatch.setattr(api, "get_settings", FakeSettings)
    api._databus.record(StoredMessage(
        topic="edo.test.v1",
        payload={"dmp": {"title": "maDMP for Semantico"}},
        header={"socket_id": "socket-rdmo", "project_id": "11"},
        partition=0, offset=5,
    ))
    client = TestClient(api.app)
    body = client.get("/api/v1/bus/topics/edo.test.v1/messages?limit=20").json()
    assert isinstance(body, list)  # bare array, as databus.ts expects
    assert body[0]["topic"] == "edo.test.v1"
    assert body[0]["header"]["socket_id"] == "socket-rdmo"
    assert body[0]["offset"] == 5


def test_bus_publish_endpoint_posts_with_header_contract(monkeypatch):
    monkeypatch.setattr(api, "get_settings", FakeSettings)
    published: list[tuple] = []

    class StubPublisher:
        def publish(self, topic, payload, header, timeout_s=5.0):
            published.append((topic, payload, header))
            return True

    monkeypatch.setattr(api, "_publisher", StubPublisher())
    client = TestClient(api.app)
    body = {
        "payload": {"dmp": {"title": "x"}},
        "header": {
            "socket_id": "edo-frontend", "ontology_uri": "https://w3id.org/edo/terms/",
            "project_id": "11", "schema_id": "maDMP",
            "timestamp": "2026-11-23T00:00:00Z", "lineage": "vue-frontend -> edo.dmp.v1",
        },
    }
    response = client.post("/api/v1/bus/topics/edo.dmp.v1/messages", json=body)
    assert response.status_code == 200
    assert published[0][0] == "edo.dmp.v1"
    # not recorded locally — the consumer records the produced message once,
    # with its partition/offset (avoids duplicates in the recent list)
    assert api._databus.counts().get("edo.dmp.v1") is None


def test_bus_publish_endpoint_rejects_incomplete_header(monkeypatch):
    monkeypatch.setattr(api, "get_settings", FakeSettings)
    client = TestClient(api.app)
    response = client.post("/api/v1/bus/topics/edo.dmp.v1/messages", json={
        "payload": {"dmp": {}},
        "header": {"socket_id": "edo-frontend"},
    })
    assert response.status_code == 400
    assert "lineage" in response.json()["detail"]


def test_bus_publish_endpoint_without_producer_answers_503(monkeypatch):
    monkeypatch.setattr(api, "get_settings", FakeSettings)

    class DeadPublisher:
        def publish(self, *args, **kwargs):
            return False

    monkeypatch.setattr(api, "_publisher", DeadPublisher())
    client = TestClient(api.app)
    response = client.post("/api/v1/bus/topics/edo.dmp.v1/messages", json={
        "payload": {"dmp": {}},
        "header": {key: "x" for key in
                   ("socket_id", "ontology_uri", "project_id", "schema_id",
                    "timestamp", "lineage")},
    })
    assert response.status_code == 503


def test_bus_status_endpoint(monkeypatch):
    monkeypatch.setattr(api, "get_settings", FakeSettings)
    monkeypatch.setattr(api, "broker_online", lambda servers, timeout_s=2.0: True)
    client = TestClient(api.app)
    body = client.get("/api/v1/bus/status").json()
    assert body["online"] is True
    assert "buffered" in body


# -- live tracker feed ----------------------------------------------------------


def test_format_bus_sse_ships_the_full_message_shape():
    from socket_ux.api import format_bus_sse

    event = api.BusEvent(
        topic="edo.sync.v1",
        payload={"event": "sync.round", "stats": {"created": 1}},
        headers={"socket_id": "regimo-core", "schema_id": "edo.sync.v1"},
        partition=1, offset=3, timestamp="2026-11-23T00:00:00+00:00",
    )
    rendered = format_bus_sse(event)
    assert rendered.startswith("event: bus.message\ndata: ")
    assert rendered.endswith("\n\n")
    data = json.loads(rendered.split("\n", 2)[1][len("data: "):])
    assert data["topic"] == "edo.sync.v1"
    assert data["payload"]["stats"] == {"created": 1}
    assert data["header"]["socket_id"] == "regimo-core"
    assert (data["partition"], data["offset"], data["timestamp"]) == (1, 3, "2026-11-23T00:00:00+00:00")


def test_bus_events_endpoint_negotiates_event_stream(monkeypatch):
    monkeypatch.setattr(api, "get_settings", FakeSettings)
    client = TestClient(api.app)
    with client.stream("GET", "/api/v1/bus/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-cache"


# -- live (optional): against the real broker, opted in via EDO_LIVE_BUS --------

requires_live = pytest.mark.skipif(
    not __import__("os").environ.get("EDO_LIVE_BUS"),
    reason="live broker test — set EDO_LIVE_BUS=1 to run")


@requires_live
def test_live_bridge_lists_broker_topics(monkeypatch):
    monkeypatch.setattr(api, "get_settings", FakeSettings)
    client = TestClient(api.app)
    body = client.get("/api/v1/bus/topics").json()
    names = {t["name"] for t in body["topics"]}
    assert "edo.projects.v1" in names
