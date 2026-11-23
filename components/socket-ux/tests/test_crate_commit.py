"""Tests for the crate commit path: PUT under If-Match, 409 contract, committed GET (UPL-001 steps 2b/3)."""

from __future__ import annotations

import copy
import json
import re

from fastapi.testclient import TestClient
from pyld import jsonld

from socket_ux import api, crate_store, fuseki
from socket_ux.config import Settings
from socket_ux.occ import parse_token

from conftest import PROJECT_IRI, linked_instance


class FakeAdminSettings(Settings):
    """Settings serving under admin (the dev compose profile) for PUT tests."""

    def __init__(self) -> None:
        super().__init__(fuseki_url="http://fuseki.test", role="admin")


def _setup(monkeypatch, role_settings=FakeAdminSettings):
    """Common fixture wiring: mocked Fuseki reads, stub publisher, fresh tokens."""
    monkeypatch.setattr(api, "get_settings", role_settings)
    graph = jsonld.expand(linked_instance())
    monkeypatch.setattr(fuseki, "project_graph_jsonld", lambda s, pid, c: graph)

    saved = {}

    def fake_save(settings, pid, metadata, client):
        saved["pid"] = pid
        saved["metadata"] = metadata

    monkeypatch.setattr(crate_store, "save_committed", fake_save)
    monkeypatch.setattr(crate_store, "load_committed", lambda s, pid, c: saved.get("metadata"))

    published = []

    class _StubPublisher:
        def publish(self, *args, **kwargs):
            published.append((args, kwargs))
            return True

    monkeypatch.setattr(api, "_publisher", _StubPublisher())
    monkeypatch.setattr(api, "_token_store", None)
    return saved, published


def _derived_crate(client):
    response = client.get(f"/api/v1/projects/{PROJECT_IRI}/crate")
    assert response.status_code == 200
    assert response.headers["X-Crate-Source"] == "derived"
    return response.json(), response.headers["X-Revision-Token"]


def test_put_requires_if_match(monkeypatch):
    _setup(monkeypatch)
    crate, _ = _derived_crate(TestClient(api.app))

    client = TestClient(api.app)
    response = client.put(f"/api/v1/projects/{PROJECT_IRI}/crate", json=crate)
    assert response.status_code == 428
    assert response.json()["detail"]["code"] == "precondition_required"


def test_put_rejects_non_crate_body(monkeypatch):
    _setup(monkeypatch)
    TestClient(api.app).get(f"/api/v1/projects/{PROJECT_IRI}/crate")
    client = TestClient(api.app)
    response = client.put(
        f"/api/v1/projects/{PROJECT_IRI}/crate",
        json={"not": "a crate"},
        headers={"If-Match": "rev:1:sha256:" + "0" * 64},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_crate"


def test_put_conflict_returns_full_contract(monkeypatch):
    _setup(monkeypatch)
    client = TestClient(api.app)
    crate, token = _derived_crate(client)

    stale_token = token.replace("rev:1:", "rev:0:")
    edited = copy.deepcopy(crate)
    edited["@graph"][0]["name"] = "Renamed by A"

    response = client.put(
        f"/api/v1/projects/{PROJECT_IRI}/crate", json=edited,
        headers={"If-Match": stale_token},
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "revision_conflict"
    assert detail["current_revision_token"] == token
    assert len(detail["current_digest_sha256"]) == 64
    assert detail["server_record"] == crate
    # The rename collides with the server's root node; the field list says so.
    fields = [c["field"] for c in detail["field_conflicts"]]
    assert any(f.startswith("@graph/") for f in fields)


def test_put_commit_advances_token_and_persists(monkeypatch):
    saved, published = _setup(monkeypatch)
    client = TestClient(api.app)
    crate, token = _derived_crate(client)

    edited = copy.deepcopy(crate)
    edited["@graph"][0]["name"] = "Renamed by A"

    response = client.put(
        f"/api/v1/projects/{PROJECT_IRI}/crate", json=edited,
        headers={"If-Match": token, "X-Socket-Id": "vue-frontend-test"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["committed"] is True
    new_token = parse_token(body["revision_token"])
    assert new_token is not None and new_token.seq == 2
    assert response.headers["ETag"] == f'"{body["revision_token"]}"'

    # The body was persisted as the committed crate of this project ...
    assert saved["pid"] == PROJECT_IRI
    assert saved["metadata"] == edited
    # ... announced on edo.crate.v1 with the new token, ...
    topics = [call[0][0] for call in published]
    assert "edo.crate.v1" in topics
    commit_calls = [call[0][1] for call in published if call[0][0] == "edo.crate.v1"]
    assert commit_calls[-1]["event"] == "crate.committed"
    assert commit_calls[-1]["revision_token"] == body["revision_token"]
    assert commit_calls[-1]["updated_by"] == "vue-frontend-test"

    # ... and the next GET serves the committed crate with the new token.
    served = client.get(f"/api/v1/projects/{PROJECT_IRI}/crate")
    assert served.headers["X-Crate-Source"] == "committed"
    assert served.json() == edited
    assert served.headers["X-Revision-Token"] == body["revision_token"]


def test_put_forbidden_below_fellow(monkeypatch):
    _setup(monkeypatch)

    class FakeGuestSettings(Settings):
        def __init__(self) -> None:
            super().__init__(fuseki_url="http://fuseki.test", role="guest")

    monkeypatch.setattr(api, "get_settings", FakeGuestSettings)
    client = TestClient(api.app)
    response = client.put(
        f"/api/v1/projects/{PROJECT_IRI}/crate", json={"@graph": []},
        headers={"If-Match": "rev:1:sha256:" + "0" * 64},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["capability"] == "editCrate"


class FakeFusekiClient:
    """Minimal httpx.Client double: records crate writes, answers the SELECT."""

    def __init__(self, settings):
        self.settings = settings
        self.literals = {}

    def post(self, url, data=None, params=None, content=None, auth=None, headers=None):
        if url == self.settings.dataset_query_url:
            match = re.search(r"GRAPH <([^>]+)>", (data or {}).get("query", ""))
            literal = self.literals.get(match.group(1)) if match else None
            bindings = [] if literal is None else [{"json": {"value": literal}}]
            return _FakeResponse(200, {"results": {"bindings": bindings}})
        document = json.loads(content)
        self.literals[params["graph"]] = document[crate_store.CRATE_JSON_PREDICATE]
        return _FakeResponse(201, {})


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_crate_store_verbatim_roundtrip():
    """save -> load preserves the crate document exactly — custom terms too.

    The committed crate is stored verbatim (one ``edo:crateJson`` literal):
    expansion-based storage was rejected because pyld drops every property
    outside the RO-Crate context (``observes``, arbitrary NovaCrate edits).
    """
    settings = FakeAdminSettings()
    client = FakeFusekiClient(settings)
    metadata = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {"@id": "./", "@type": "Dataset", "name": "x",
             "observes": {"@id": "urn:uuid:some-property"},
             "customProp": "kept verbatim"},
        ],
    }

    assert crate_store.load_committed(settings, PROJECT_IRI, client) is None
    crate_store.save_committed(settings, PROJECT_IRI, metadata, client)
    assert crate_store.load_committed(settings, PROJECT_IRI, client) == metadata
