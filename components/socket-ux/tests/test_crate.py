"""Tests for the RO-Crate builder (crate.py)."""

from __future__ import annotations

from socket_ux import crate as crate_mod

from conftest import DATASET_ID, PROJECT_IRI, SENSOR_ID, linked_instance


def _graph(metadata: dict) -> dict[str, dict]:
    return {n["@id"]: n for n in metadata["@graph"]}


def test_build_crate_root_dataset():
    doc = linked_instance()
    crate = crate_mod.build_crate(doc, PROJECT_IRI)
    metadata = crate_mod.crate_metadata_json(crate)
    root = _graph(metadata)["./"]

    assert root["@type"] == "Dataset"
    assert root["name"] == "Weatherstation Q3-2026"
    assert "PIDINST" in root["description"]  # dataset description wins over fallback
    assert root["isBasedOn"]["@id"] == PROJECT_IRI
    assert root["conformsTo"]["@id"] == "https://w3id.org/edo/internal-format/0.1"
    assert root["keywords"] == ["Energy", "Orchestrator"]


def test_build_crate_license():
    doc = linked_instance()
    crate = crate_mod.build_crate(doc, PROJECT_IRI)
    metadata = crate_mod.crate_metadata_json(crate)
    graph = _graph(metadata)

    assert graph["./"]["license"]["@id"] == "https://creativecommons.org/licenses/by/4.0/"
    cc = graph["https://creativecommons.org/licenses/by/4.0/"]
    assert cc["@type"] == "CreativeWork"
    assert cc["name"] == "CC BY 4.0"


def test_build_crate_license_from_full_uri_doc():
    """Compact keys may hold node objects (e.g. dcterms:license as @id)."""
    doc = linked_instance()
    doc["dcat:dataset"]["dcat:distribution"][1]["edo:license"] = {
        "dcterms:license": {"@id": "https://creativecommons.org/licenses/by/4.0/"},
        "time:hasBeginning": "2027-01-29",
    }
    crate = crate_mod.build_crate(doc, PROJECT_IRI)
    metadata = crate_mod.crate_metadata_json(crate)
    graph = _graph(metadata)
    assert graph["./"]["license"]["@id"] == "https://creativecommons.org/licenses/by/4.0/"


def test_build_crate_sensor_and_properties():
    doc = linked_instance()
    crate = crate_mod.build_crate(doc, PROJECT_IRI)
    metadata = crate_mod.crate_metadata_json(crate)
    graph = _graph(metadata)

    sensor = graph[SENSOR_ID]
    assert sensor["@type"] == "sosa:Sensor"
    assert sensor["name"] == "KIT-CN-IAI-Bau445-Weather-Station-Weatherstation"
    assert sensor["identifier"] == "21.11157/9b6cdfb9-a4fb-4269-af04-1ef94588f5a8"

    # root dataset observes the measured properties (DMP-SMS link)
    observes = graph["./"]["observes"]
    assert len(observes) == 5
    wind_speed = graph["https://sms-cv.helmholtz.cloud/sms/cv/api/v1/measuredquantities/172/"]
    assert wind_speed["@type"] == "sosa:ObservableProperty"
    assert wind_speed["name"] == "Wind speed"


def test_build_crate_provenance_and_contact():
    doc = linked_instance()
    crate = crate_mod.build_crate(doc, PROJECT_IRI)
    metadata = crate_mod.crate_metadata_json(crate)
    graph = _graph(metadata)

    root = graph["./"]
    action = graph["#generate-action"]
    assert action["@type"] == "CreateAction"
    assert action["object"]["@id"] == DATASET_ID
    assert action["result"]["@id"] == "./"
    assert root["prov:wasGeneratedBy"]["@id"] == SENSOR_ID

    contact = graph["#contact"]
    assert contact["name"] == "A. Koubaa"
    assert root["creator"]["@id"] == "#contact"
