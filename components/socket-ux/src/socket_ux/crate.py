"""RO-Crate generation for NovaCrate (on request, from the internal format).

This mirrors the essential structure of ``fuseki-proto``'s ``ro_crate.py``
(CF2-006), but builds a *metadata-only* crate for interactive display in the
NovaCrate editor: the internal-format graph stays in the internal database and
is referenced via ``isBasedOn`` on the root dataset. The provenance-rich batch
generation with the packaged graph file remains in ``fuseki-proto``.
"""

from __future__ import annotations


from typing import Any

from rocrate.rocrate import ROCrate

RO_CRATE_VERSION = "1.1"

# namespace prefixes of the internal-format compact JSON-LD (ro_crate.py)
SMSCV = "https://sms-cv.helmholtz.cloud/sms/cv/api/v1/"
SCHEMA_IRI = "https://w3id.org/edo/internal-format/0.1"

_LICENSE_NAMES = {
    "https://creativecommons.org/licenses/by/4.0/": "CC BY 4.0",
    "https://spdx.org/licenses/MIT": "MIT",
}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict) and "@value" in value:
        return _text(value["@value"])
    if isinstance(value, dict) and "@id" in value:
        return _text(value["@id"])
    if isinstance(value, list) and value:
        return _text(value[0])
    return ""


def _val(obj: Any, key: str) -> Any:
    if not isinstance(obj, dict):
        return None
    value = obj.get(key)
    # pyld compaction renders single-valued properties as one-element lists
    if isinstance(value, list) and len(value) == 1:
        return value[0]
    return value


def _first_text(items: Any, *keys: str) -> str:
    for key in keys:
        value = _text(_val(items, key))
        if value:
            return value
    return ""


def _expand_smscv(value: str) -> str:
    if value.startswith("smscv:"):
        return f"{SMSCV}{value.split(':', 1)[1]}"
    return value


def _license_name(uri: str) -> str:
    return _LICENSE_NAMES.get(uri) or uri.rstrip("/").rsplit("/", 1)[-1]


def build_crate(doc: dict[str, Any], project_iri: str) -> ROCrate:
    """Build the RO-Crate from a compact internal-format document.

    Returns the ``rocrate`` object; use ``crate.metadata.generate()`` for the
    ``ro-crate-metadata.json`` content.
    """
    project = _as_dict(doc)
    project_title = _first_text(project, "dcterms:title")

    dataset = _as_dict(_val(project, "dcat:dataset"))
    ds_id = _first_text(dataset, "@id") or project_iri
    ds_title = _first_text(dataset, "dcterms:title") or "Dataset"
    ds_description = _first_text(dataset, "dcterms:description")
    keywords = _val(dataset, "dcat:keyword") or []

    # license (first distribution that carries one); the value may be a plain
    # string, a node object ({"@id": ...}) or nested ("dcterms:license": ...)
    license_uri = None
    for dist in _val(dataset, "dcat:distribution") or []:
        lic = _as_dict(_val(dist, "edo:license"))
        raw = _val(lic, "dcterms:license")
        if isinstance(raw, dict):
            raw = raw.get("@id") or raw.get("@value")
        lu = _text(raw)
        if lu:
            license_uri = lu

    # sensor + measured properties (the DMP-SMS link, CF2-005)
    sensor = _as_dict(_val(dataset, "prov:wasGeneratedBy"))
    sensor_id = _first_text(sensor, "@id")
    sensor_title = _first_text(sensor, "dcterms:title")
    sensor_pid = _first_text(_as_dict(_val(sensor, "edo:identifier")), "dcterms:identifier")
    props = [_as_dict(p) for p in (_val(sensor, "sosa:observes") or [])]

    # contact
    contact = _as_dict(_val(project, "edo:hasContact"))
    contact_name = _first_text(contact, "foaf:name")

    # funding -> funder (schema.org "funder" on the root dataset)
    funding = _as_dict(_val(project, "edo:hasFunding"))
    funder = _as_dict(_val(funding, "edo:funder"))
    funder_name = _first_text(funder, "foaf:name")
    funder_id = _first_text(_as_dict(_val(funder, "edo:identifier")),
                            "dcterms:identifier")
    funding_status = _first_text(funding, "edo:fundingStatus")

    crate = ROCrate(version=RO_CRATE_VERSION)
    root = crate.root_dataset
    # ro-crate-py fabricates "datePublished": iso_now() in RootDataset._empty;
    # nothing has been published here — the crate is derived on every GET and
    # a moving timestamp would churn the OCC revision token (UPL-001).
    del root["datePublished"]
    root["name"] = ds_title
    root["description"] = ds_description or (
        f"RO-Crate of the EDO internal-format instance '{ds_title}' "
        f"(linked DMP + SMS) for the project '{project_title}'."
    )
    root["isBasedOn"] = {"@id": project_iri}
    root["conformsTo"] = {"@id": SCHEMA_IRI}
    if keywords:
        root["keywords"] = [k for k in keywords if isinstance(k, str)]

    if license_uri:
        crate.add_jsonld({
            "@id": license_uri,
            "@type": "CreativeWork",
            "name": _license_name(license_uri),
            "description": f"License of the packaged dataset ({license_uri}).",
        })
        root["license"] = {"@id": license_uri}

    # provenance: generated by socket-ux on request for NovaCrate. No endTime
    # here — the crate is derived on every GET, a fabricated timestamp would
    # make the derivation non-deterministic and churn the OCC revision token
    # (UPL-001). Real dates enter when a crate is committed.
    crate.add_jsonld({
        "@id": "#generate-action",
        "@type": "CreateAction",
        "name": "internal-format -> RO-Crate generation (socket-ux)",
        "description": (
            "Generated on request by the socket-ux API from the project graph "
            "in the internal database (Fuseki /projects)."
        ),
        "object": {"@id": ds_id},
        "result": {"@id": "./"},
    })
    root["prov:wasGeneratedBy"] = {"@id": "#generate-action"}

    # sensor contextual entity + measured properties
    if sensor_id or sensor_title:
        crate.add_jsonld({
            "@id": sensor_id or "#sensor",
            "@type": "sosa:Sensor",
            "name": sensor_title or "Sensor",
            "identifier": sensor_pid or sensor_id,
        })
        root["prov:wasGeneratedBy"] = {"@id": sensor_id or "#sensor"}
        for i, prop in enumerate(props, start=1):
            quantity = _expand_smscv(_text(_val(prop, "smscv:measuredQuantity")))
            name = _first_text(prop, "dcterms:title") or quantity
            prop_id = quantity or f"#measured-property-{i}"
            entity: dict[str, Any] = {
                "@id": prop_id,
                "@type": "sosa:ObservableProperty",
                "name": name,
            }
            if quantity:
                entity["identifier"] = quantity
            crate.add_jsonld(entity)
            root.append_to("observes", {"@id": prop_id})

    if contact_name:
        crate.add_jsonld({"@id": "#contact", "@type": "Person", "name": contact_name})
        root["creator"] = {"@id": "#contact"}

    if funder_name or funder_id:
        funder_ent_id = funder_id or "#funder"
        funder_ent: dict[str, Any] = {
            "@id": funder_ent_id,
            "@type": "Organization",
            "name": funder_name or funder_id,
        }
        if funder_id and funder_id != funder_name:
            funder_ent["identifier"] = funder_id
        if funding_status:
            funder_ent["description"] = f"Funding status: {funding_status}."
        # note: add_jsonld consumes @id/@type from the dict
        crate.add_jsonld(funder_ent)
        root["funder"] = {"@id": funder_ent_id}

    return crate


def crate_metadata_json(crate: ROCrate) -> dict[str, Any]:
    """The ``ro-crate-metadata.json`` content of a crate as a dict."""
    import json

    generated = crate.metadata.generate()
    if isinstance(generated, dict):
        return generated
    return json.loads(generated)
