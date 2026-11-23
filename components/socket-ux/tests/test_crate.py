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


def test_build_crate_funder():
    """edo:hasFunding -> schema.org funder + contextual Organization entity."""
    doc = linked_instance()
    doc["edo:hasFunding"] = {
        "edo:fundingStatus": "granted",
        "edo:funder": {
            "foaf:name": "Helmholtz Metadata Collaboration",
            "edo:identifier": {
                "dcterms:identifier": "https://helmholtz-metadaten.de/about-hmc",
            },
        },
    }
    crate = crate_mod.build_crate(doc, PROJECT_IRI)
    metadata = crate_mod.crate_metadata_json(crate)
    graph = _graph(metadata)

    funder_id = "https://helmholtz-metadaten.de/about-hmc"
    funder = graph[funder_id]
    assert funder["@type"] == "Organization"
    assert funder["name"] == "Helmholtz Metadata Collaboration"
    assert funder["identifier"] == funder_id
    assert funder["description"] == "Funding status: granted."
    assert graph["./"]["funder"]["@id"] == funder_id


def test_build_crate_no_funding():
    """Without edo:hasFunding the root dataset carries no funder property."""
    doc = linked_instance()
    crate = crate_mod.build_crate(doc, PROJECT_IRI)
    metadata = crate_mod.crate_metadata_json(crate)
    assert "funder" not in _graph(metadata)["./"]


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


def test_build_crate_per_dataset_entities():
    """Single-dataset form: the dcat:dataset becomes a Dataset entity with its
    distributions as MediaObject entities (UPL-003, CCA highlight targets)."""
    doc = linked_instance()
    crate = crate_mod.build_crate(doc, PROJECT_IRI)
    metadata = crate_mod.crate_metadata_json(crate)
    graph = _graph(metadata)

    ds = graph[DATASET_ID]
    assert ds["@type"] == "Dataset"
    assert ds["name"] == "Weatherstation Q3-2026"
    assert ds["keywords"] == ["Energy", "Orchestrator"]
    assert ds["edo:personalData"] is False
    assert ds["edo:sensitiveData"] is False
    assert graph["./"]["hasPart"] == [{"@id": DATASET_ID}]

    dists = ds["distribution"]
    assert len(dists) == 2
    storage = graph[dists[0]["@id"]]
    assert storage["@type"] == "MediaObject"
    assert storage["name"] == "Storage during the project"
    assert storage["encodingFormat"] == "http://purl.org/NET/mediatypes/text/csv"
    assert storage["contentUrl"] == "https://gitlab.kit.edu/kit/iai/it4edm/metadb"
    assert storage["edo:dataAccess"] == "open"


def test_build_crate_multiple_datasets():
    """List form (RDMO projects with several datasets): one Dataset entity per
    dcat:dataset, distributions attached, root carries the project title and
    the union of the keywords; the generate action covers all datasets."""
    second = {
        "@id": "edo:dataset:second",
        "@type": "dcat:Dataset",
        "dcterms:title": "Second dataset",
        "dcat:keyword": ["Orchestrator", "Extra"],
        "edo:sensitiveData": True,
        "dcat:distribution": [
            {"@type": "dcat:Distribution", "dcterms:title": "Dist B"},
        ],
    }
    doc = linked_instance()
    doc["dcat:dataset"] = [doc["dcat:dataset"], second]
    crate = crate_mod.build_crate(doc, PROJECT_IRI)
    metadata = crate_mod.crate_metadata_json(crate)
    graph = _graph(metadata)

    root = graph["./"]
    assert root["name"] == "Measurement_02"  # project title wins with >1 dataset
    assert root["keywords"] == ["Energy", "Orchestrator", "Extra"]
    assert root["hasPart"] == [
        {"@id": DATASET_ID},
        {"@id": "edo:dataset:second"},
    ]

    second_ent = graph["edo:dataset:second"]
    assert second_ent["name"] == "Second dataset"
    assert second_ent["edo:sensitiveData"] is True
    assert "edo:personalData" not in second_ent
    dist_b = graph[second_ent["distribution"][0]["@id"]]
    assert dist_b["name"] == "Dist B"

    action = graph["#generate-action"]
    assert action["object"] == [
        {"@id": DATASET_ID},
        {"@id": "edo:dataset:second"},
    ]

    # the sensor of the first dataset is still linked (DMP-SMS link)
    assert root["prov:wasGeneratedBy"]["@id"] == SENSOR_ID
