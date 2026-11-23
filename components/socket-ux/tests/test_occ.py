"""Tests for OCC revision tokens (UPL-001): occ.py + ETag endpoints."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from pyld import jsonld

from socket_ux import api, fuseki
from socket_ux.occ import TokenStore, canonical_digest, parse_token

from conftest import PROJECT_IRI, linked_instance

from test_api import FakeSettings


def test_token_format_roundtrip():
    assert parse_token("rev:1:sha256:" + "a" * 64) is not None
    assert parse_token("rev:0:sha256:" + "a" * 64) is not None
    assert parse_token("rev:x:sha256:" + "a" * 64) is None
    assert parse_token("rev:1:md5:xyz") is None
    assert parse_token("nope") is None
    assert parse_token("rev:1:sha256:short") is None


def test_canonical_digest_is_order_insensitive():
    assert canonical_digest({"a": 1, "b": [1, 2]}) == canonical_digest({"b": [1, 2], "a": 1})
    assert canonical_digest({"a": 1}) != canonical_digest({"a": 2})


def test_observe_idempotent_then_advances():
    store = TokenStore()
    first = store.observe("s", {"v": 1})
    assert str(first) == f"rev:1:sha256:{canonical_digest({'v': 1})}"
    # Same content -> same token (no seq churn)
    assert store.observe("s", {"v": 1}) == first
    # Content change -> seq+1, new digest
    second = store.observe("s", {"v": 2})
    assert second.seq == 2
    assert second.digest == canonical_digest({"v": 2})
    # Scopes are independent
    assert store.observe("t", {"v": 1}).seq == 1


def test_restart_safety(tmp_path):
    state_file = str(tmp_path / "tokens.json")
    store = TokenStore(state_file)
    token = store.observe("adp:values:p1", {"doc": 1})

    # A fresh store instance (the restart case) resolves the same token and
    # keeps the sequence monotonic across the restart boundary.
    restarted = TokenStore(state_file)
    assert restarted.observe("adp:values:p1", {"doc": 1}) == token
    assert restarted.observe("adp:values:p1", {"doc": 2}).seq == 2


def test_corrupt_state_file_fails_closed(tmp_path):
    state_file = tmp_path / "tokens.json"
    state_file.write_text("{not json")
    store = TokenStore(str(state_file))
    # Starts at seq 1 again — a pre-restart If-Match token now mismatches
    # (fails closed as a 409) instead of being silently accepted.
    assert store.observe("s", {"v": 1}).seq == 1


def test_values_and_crate_carry_etag(monkeypatch):
    monkeypatch.setattr(api, "get_settings", FakeSettings)
    graph = jsonld.expand(linked_instance())
    monkeypatch.setattr(fuseki, "project_graph_jsonld", lambda s, pid, c: graph)
    monkeypatch.setattr(api.crate_store, "load_committed", lambda s, pid, c: None)

    class _StubPublisher:
        def publish(self, *args, **kwargs):
            return False

    monkeypatch.setattr(api, "_publisher", _StubPublisher())
    monkeypatch.setattr(api, "_token_store", None)

    client = TestClient(api.app)

    values = client.get(f"/api/v1/projects/{PROJECT_IRI}/values")
    assert values.status_code == 200
    etag = values.headers["ETag"]
    assert etag.startswith('"rev:1:sha256:')
    assert values.headers["X-Revision-Token"] == etag.strip('"')
    # Second GET with unchanged content: same token, no seq churn
    again = client.get(f"/api/v1/projects/{PROJECT_IRI}/values")
    assert again.headers["ETag"] == etag

    crate = client.get(f"/api/v1/projects/{PROJECT_IRI}/crate")
    assert crate.status_code == 200
    crate_etag = crate.headers["ETag"]
    assert crate_etag.startswith('"rev:1:sha256:')
    # Distinct slices advance independently; the crate digest differs from
    # the values digest (different canonical documents).
    crate_token = parse_token(crate_etag.strip('"'))
    values_token = parse_token(etag.strip('"'))
    assert crate_token is not None and values_token is not None
    assert crate_token.digest != values_token.digest
    # Bodies unchanged: values is still the bare document, crate the bare
    # ro-crate-metadata.json — no transport metadata leaks into the payload.
    assert "revision_token" not in values.json()


def test_etag_changes_when_graph_changes(monkeypatch):
    monkeypatch.setattr(api, "get_settings", FakeSettings)
    graph = jsonld.expand(linked_instance())
    monkeypatch.setattr(fuseki, "project_graph_jsonld", lambda s, pid, c: graph)

    class _StubPublisher:
        def publish(self, *args, **kwargs):
            return False

    monkeypatch.setattr(api, "_publisher", _StubPublisher())
    monkeypatch.setattr(api, "_token_store", None)

    client = TestClient(api.app)
    first = client.get(f"/api/v1/projects/{PROJECT_IRI}/values").headers["ETag"]

    # A sync round mutates the graph -> the next GET observes the new content
    # and advances the sequence (the sync engine is the implicit actor).
    changed = json.loads(json.dumps(graph))
    changed[0]["http://purl.org/dc/terms/title"] = [{"@value": "occ-mutated-title"}]
    monkeypatch.setattr(fuseki, "project_graph_jsonld", lambda s, pid, c: changed)
    second = client.get(f"/api/v1/projects/{PROJECT_IRI}/values").headers["ETag"]
    assert parse_token(second.strip('"')).seq == parse_token(first.strip('"')).seq + 1
