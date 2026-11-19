"""Tests for the internal-format extraction (internal_format.py)."""

from __future__ import annotations

from pyld import jsonld

from socket_ux.internal_format import project_doc

from conftest import PROJECT_IRI, linked_instance


def _fuseki_output() -> list[dict]:
    """What Fuseki returns for DESCRIBE: full-URI JSON-LD.

    Simulated by expanding the compact example (same triples, full IRIs).
    """
    return jsonld.expand(linked_instance())


def test_project_doc_round_trip():
    doc = project_doc(_fuseki_output(), PROJECT_IRI)
    original = linked_instance()

    # context is compacted and the project node is the document root
    assert doc["@id"] == PROJECT_IRI
    assert doc["dcterms:title"] == original["dcterms:title"]
    assert doc["edo:hasContact"]["foaf:name"] == "A. Koubaa"


def test_project_doc_embeds_nested_nodes():
    doc = project_doc(_fuseki_output(), PROJECT_IRI)

    dataset = doc["dcat:dataset"]
    assert dataset["dcterms:title"] == "Weatherstation Q3-2026"
    assert dataset["dcat:keyword"] == ["Energy", "Orchestrator"]

    sensor = dataset["prov:wasGeneratedBy"]
    assert sensor["@id"] == "https://sms.atmohub.kit.edu/devices/67"
    assert len(sensor["sosa:observes"]) == 5
    assert sensor["sosa:observes"][0]["dcterms:title"] == "Wind speed"


def test_project_doc_keeps_cv_references_as_ids():
    """Controlled-vocabulary URIs without nodes in the graph stay references."""
    doc = project_doc(_fuseki_output(), PROJECT_IRI)

    sensor = doc["dcat:dataset"]["prov:wasGeneratedBy"]
    assert sensor["dcterms:type"] == "smscv:equipmenttypes/54/"
    prop = sensor["sosa:observes"][0]
    assert prop["smscv:measuredQuantity"] == "smscv:measuredquantities/172/"


def test_project_doc_unknown_project():
    import pytest

    with pytest.raises(KeyError):
        project_doc(_fuseki_output(), "urn:uuid:not-there")
