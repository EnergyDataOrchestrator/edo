"""Tests for the Fuseki SPARQL client (fuseki.py), using httpx.MockTransport."""

from __future__ import annotations

import json
import urllib.parse

import httpx
import pytest

from socket_ux import fuseki
from socket_ux.config import Settings

from conftest import PROJECT_IRI

SETTINGS = Settings(fuseki_url="http://fuseki.test", fuseki_dataset="projects")


def _select_response(request: httpx.Request) -> httpx.Response:
    assert request.url.path == "/projects/query"
    assert request.headers.get("Authorization", "").startswith("Basic ")
    import urllib.parse

    query = urllib.parse.parse_qs(request.read().decode())["query"][0]
    if "SELECT" in query and "edo:Project" in query:
        body = {
            "results": {"bindings": [
                {
                    "project": {"type": "uri", "value": PROJECT_IRI},
                    "title": {"type": "literal", "value": "Measurement_02"},
                    "description": {"type": "literal", "value": "Weatherstation test"},
                    "dataset": {"type": "uri", "value": "edo:dataset:weatherstation-q3-2026"},
                    "contactName": {"type": "literal", "value": "A. Koubaa"},
                },
                {
                    "project": {"type": "uri", "value": PROJECT_IRI},
                    "title": {"type": "literal", "value": "Measurement_02"},
                    "description": {"type": "literal", "value": "Weatherstation test"},
                    "dataset": {"type": "uri", "value": "edo:dataset:pv-2026"},
                    "contactName": {"type": "literal", "value": "A. Koubaa"},
                },
            ]}
        }
        return httpx.Response(200, json=body)
    return httpx.Response(400, text="bad query")


def _construct_response(request: httpx.Request) -> httpx.Response:
    assert "CONSTRUCT" in urllib.parse.parse_qs(request.read().decode())["query"][0]
    return httpx.Response(200, json={"@graph": [
        {"@id": PROJECT_IRI, "http://purl.org/dc/terms/title": [{"@value": "Measurement_02"}]},
        {"@id": "urn:uuid:other-project", "http://purl.org/dc/terms/title": [{"@value": "Other"}]},
    ]})


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_list_projects_dedups_datasets():
    found = fuseki.list_projects(SETTINGS, _client(_select_response))
    assert len(found) == 1
    entry = found[0]
    assert entry["id"] == PROJECT_IRI
    assert entry["title"] == "Measurement_02"
    assert entry["datasets"] == ["edo:dataset:weatherstation-q3-2026", "edo:dataset:pv-2026"]
    assert entry["contact"] == "A. Koubaa"


def test_list_projects_error():
    with pytest.raises(fuseki.FusekiError):
        fuseki.list_projects(SETTINGS, _client(lambda req: httpx.Response(500, text="boom")))


def test_project_graph_jsonld():
    doc = fuseki.project_graph_jsonld(SETTINGS, PROJECT_IRI, _client(_construct_response))
    assert {n["@id"] for n in doc["@graph"]} >= {PROJECT_IRI}


def test_project_graph_jsonld_empty():
    client = _client(lambda req: httpx.Response(200, json={}))
    with pytest.raises(fuseki.FusekiError):
        fuseki.project_graph_jsonld(SETTINGS, PROJECT_IRI, client)
