"""Tests for the CCA term-recommendation backend (UPL-004 Stage 3):
ontology.search_terms / recommend_for_columns and the two API endpoints,
with the Fuseki transport monkeypatched."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from socket_ux import api, fuseki, ontology
from socket_ux.config import Settings


def _binding(term: str, label: str, description: str = "", type_iri: str = "") -> dict:
    return {
        "term": {"value": term},
        "label": {"value": label},
        "description": {"value": description} if description else None,
        "type": {"value": type_iri} if type_iri else None,
    }


class _FakeGraph:
    """Minimal labels the fake Fuseki graph carries."""

    ROWS = [
        _binding("https://sms-cv.helmholtz.cloud/sms/cv/api/v1/0001_0___meta__0003",
                 "Air temperature",
                 "Temperature of the ambient air",
                 "sosa:ObservableProperty"),
        _binding("https://sms-cv.helmholtz.cloud/sms/cv/api/v1/0002_0___meta__0007",
                 "Global horizontal irradiance"),
        _binding("https://w3id.org/edo/terms/Dataset",
                 "Dataset",
                 "A collection of data",
                 "rdfs:Class"),
    ]

    @staticmethod
    def run_select(settings, query, client):  # noqa: ANN001
        import re

        assert "CONTAINS" in query
        rows = []
        lowered = query.lower()
        match = re.search(r'contains\(lcase\(str\(\?label\)\), lcase\("([^"]*)"\)\)', lowered)
        needle = match.group(1) if match else ""
        for row in _FakeGraph.ROWS:
            label = row["label"]["value"].lower()
            if needle and needle in label:
                rows.append(row)
        return rows


def test_score_label_ranking():
    tokens = ontology.tokenize("Air temperature")
    assert ontology.score_label("Air temperature", tokens) == 300
    assert ontology.score_label("Air temperature sensor", tokens) == 240
    assert ontology.score_label("Ambient air temperature", tokens) == 240
    assert ontology.score_label("Air", ["air"]) == 300  # single-token exact
    # single-token query fully matched at a word boundary (all-tokens branch)
    assert ontology.score_label("Air humidity", ["air"]) == 240
    assert ontology.score_label("Hairdryer noise", ["air"]) == 60  # substring only
    # single-token query: any boundary hit is already an all-tokens match
    assert ontology.score_label("Air temperature sensor", ["air"]) == 240
    assert ontology.score_label("Global horizontal irradiance", tokens) is None


def test_search_terms_ranks_and_formats(monkeypatch):
    monkeypatch.setattr(fuseki, "_run_select", _FakeGraph.run_select)
    settings = Settings(fuseki_url="http://fuseki.test")
    with __import__("httpx").Client() as client:
        terms = ontology.search_terms(settings, client, "air temperature", 10)
    assert terms[0]["uri"].endswith("0003")
    assert terms[0]["label"] == "Air temperature"
    assert terms[0]["confidence_score"] == 1.0
    assert "sosa:ObservableProperty" in terms[0]["types"]
    # substring fallback also matches ("ambient" not in the graph)
    assert ontology.search_terms(settings, client, "zzz-nothing", 10) == []


def test_recommend_for_columns_merges_strategies(monkeypatch):
    monkeypatch.setattr(fuseki, "_run_select", _FakeGraph.run_select)
    settings = Settings(fuseki_url="http://fuseki.test")
    with __import__("httpx").Client() as client:
        recs = ontology.recommend_for_columns(
            settings, client,
            [{"name": "air_temp", "sample_values": ["12.5"]}],
            limit=5,
        )
    assert len(recs) == 1
    assert recs[0]["name"] == "air_temp"
    uris = [c["uri"] for c in recs[0]["candidates"]]
    assert any(u.endswith("0003") for u in uris)
    # deterministic order: best score first
    scores = [c["confidence_score"] for c in recs[0]["candidates"]]
    assert scores == sorted(scores, reverse=True)


def test_recommend_empty_and_unknown_columns(monkeypatch):
    monkeypatch.setattr(fuseki, "_run_select", _FakeGraph.run_select)
    settings = Settings(fuseki_url="http://fuseki.test")
    with __import__("httpx").Client() as client:
        recs = ontology.recommend_for_columns(
            settings, client,
            [{"name": "totally_unknown_column"}, {"name": ""}],
            limit=5,
        )
    assert [r["name"] for r in recs] == ["totally_unknown_column"]
    assert recs[0]["candidates"] == []


# --- API endpoints -------------------------------------------------------------

@pytest.fixture()
def api_client(monkeypatch):
    monkeypatch.setattr(api, "get_settings", lambda: Settings(fuseki_url="http://fuseki.test"))
    return TestClient(api.app)


def test_ontology_terms_endpoint(api_client, monkeypatch):
    monkeypatch.setattr(fuseki, "_run_select", _FakeGraph.run_select)
    body = api_client.get("/api/v1/ontology/terms", params={"q": "air temperature"}).json()
    assert body["query"] == "air temperature"
    assert body["terms"][0]["label"] == "Air temperature"


def test_ontology_terms_endpoint_requires_q(api_client):
    response = api_client.get("/api/v1/ontology/terms")
    assert response.status_code == 422  # FastAPI validation of the required query


def test_cca_recommendations_endpoint(api_client, monkeypatch):
    monkeypatch.setattr(fuseki, "_run_select", _FakeGraph.run_select)
    response = api_client.post(
        "/api/v1/cca/recommendations",
        json={"columns": [{"name": "air_temp", "sample_values": ["12.5"]}], "limit": 5},
    )
    assert response.status_code == 200
    recs = response.json()["recommendations"]
    assert recs[0]["name"] == "air_temp"
    assert recs[0]["candidates"], "the fake graph carries a matching quantity"


def test_cca_recommendations_endpoint_validates_body(api_client):
    response = api_client.post("/api/v1/cca/recommendations", json={"columns": "nope"})
    assert response.status_code == 400
    response = api_client.post(
        "/api/v1/cca/recommendations", json={"columns": [{"name": "x"}], "limit": 999},
    )
    assert response.status_code == 400
