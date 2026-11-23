"""Tests for the FastAPI endpoints (api.py) with mocked Fuseki transport."""

from __future__ import annotations

from fastapi.testclient import TestClient

from socket_ux import api, fuseki
from socket_ux.config import Settings

from conftest import PROJECT_IRI, linked_instance


class FakeSettings(Settings):
    """Settings pointing at nothing real; Fuseki client calls are monkeypatched."""

    def __init__(self) -> None:
        super().__init__(fuseki_url="http://fuseki.test")


def test_healthz(monkeypatch):
    monkeypatch.setattr(api, "get_settings", FakeSettings)

    class Probe:
        def __init__(self, base_url):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, timeout=None):
            class R:
                status_code = 200

            return R()

    monkeypatch.setattr(api, "_client", lambda settings: Probe(settings.fuseki_url))
    client = TestClient(api.app)
    body = client.get("/healthz").json()
    assert body["status"] == "ok"
    assert body["fuseki"] == "up"


def test_projects_endpoint(monkeypatch):
    monkeypatch.setattr(api, "get_settings", FakeSettings)

    def fake_list(settings, client):
        return [{
            "id": PROJECT_IRI,
            "title": "Measurement_02",
            "description": "Weatherstation test",
            "datasets": ["edo:dataset:weatherstation-q3-2026"],
            "contact": "A. Koubaa",
        }]

    monkeypatch.setattr(fuseki, "list_projects", fake_list)
    client = TestClient(api.app)
    body = client.get("/api/v1/projects").json()
    assert body["projects"][0]["title"] == "Measurement_02"


def test_crate_endpoint(monkeypatch):
    """The crate endpoint returns ro-crate-metadata.json for NovaCrate."""
    monkeypatch.setattr(api, "get_settings", FakeSettings)
    from pyld import jsonld

    graph = jsonld.expand(linked_instance())
    monkeypatch.setattr(fuseki, "project_graph_jsonld", lambda s, pid, c: graph)
    monkeypatch.setattr(api.crate_store, "load_committed", lambda s, pid, c: None)

    class _StubPublisher:
        def publish(self, *args, **kwargs):
            return False

    monkeypatch.setattr(api, "_publisher", _StubPublisher())

    client = TestClient(api.app)
    response = client.get(f"/api/v1/projects/{PROJECT_IRI}/crate")
    assert response.status_code == 200
    metadata = response.json()
    assert metadata["@context"] == "https://w3id.org/ro/crate/1.1/context"
    root = next(n for n in metadata["@graph"] if n["@id"] == "./")
    assert root["name"] == "Weatherstation Q3-2026"


def test_values_endpoint_not_found(monkeypatch):
    monkeypatch.setattr(api, "get_settings", FakeSettings)
    from pyld import jsonld

    graph = jsonld.expand(linked_instance())
    monkeypatch.setattr(fuseki, "project_graph_jsonld", lambda s, pid, c: graph)

    client = TestClient(api.app)
    response = client.get("/api/v1/projects/urn:uuid:missing/values")
    assert response.status_code == 404
