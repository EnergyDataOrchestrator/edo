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


def _nodes(value: Any) -> list[dict[str, Any]]:
    """Property values normalized to a list of node objects — compact JSON-LD
    renders a one-element list as the bare node, and iterating a dict would
    yield its keys, not its values."""
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    return [d for d in items if isinstance(d, dict)]


def _texts(value: Any) -> list[str]:
    """Property values normalized to a list of plain strings."""
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    return [t for t in items if isinstance(t, str)]


def _expand_smscv(value: str) -> str:
    if value.startswith("smscv:"):
        return f"{SMSCV}{value.split(':', 1)[1]}"
    return value


def _license_name(uri: str) -> str:
    return _LICENSE_NAMES.get(uri) or uri.rstrip("/").rsplit("/", 1)[-1]


def _datasets(project: dict[str, Any]) -> list[dict[str, Any]]:
    """The dcat:dataset nodes, normalized to a list — compact JSON-LD renders
    a single dataset as a dict and several datasets as a list."""
    value = _val(project, "dcat:dataset")
    items = value if isinstance(value, list) else [value]
    return [d for d in items if isinstance(d, dict)]


def _boolean(obj: Any, key: str) -> bool | None:
    """edo:personalData / edo:sensitiveData — plain bool or xsd:boolean literal."""
    value = _val(obj, key)
    if isinstance(value, bool):
        return value
    if isinstance(value, dict) and "@value" in value:
        text = _text(value["@value"]).lower()
        if text in ("true", "false"):
            return text == "true"
    return None


def _format_id(value: Any) -> str:
    """dcat:format — plain string, node object or a one-element list."""
    if isinstance(value, list):
        return _format_id(value[0]) if value else ""
    return _text(value)


def build_crate(doc: dict[str, Any], project_iri: str) -> ROCrate:
    """Build the RO-Crate from a compact internal-format document.

    Every ``dcat:dataset`` becomes its own Dataset entity (with its
    distributions as MediaObject entities) so downstream views (CCA) have
    per-dataset highlight targets in the NovaCrate editor (UPL-003). Returns
    the ``rocrate`` object; use ``crate.metadata.generate()`` for the
    ``ro-crate-metadata.json`` content.
    """
    project = _as_dict(doc)
    project_title = _first_text(project, "dcterms:title")

    datasets = _datasets(project)
    first = datasets[0] if datasets else {}
    multi = len(datasets) > 1
    ds_title = _first_text(first, "dcterms:title") or "Dataset"
    ds_description = _first_text(first, "dcterms:description")

    # license (first distribution of any dataset that carries one); the value
    # may be a plain string, a node object ({"@id": ...}) or nested
    # ("dcterms:license": ...)
    license_uri = None
    for ds in datasets:
        for dist in _nodes(_val(ds, "dcat:distribution")):
            lic = _as_dict(_val(dist, "edo:license"))
            raw = _val(lic, "dcterms:license")
            if isinstance(raw, dict):
                raw = raw.get("@id") or raw.get("@value")
            lu = _text(raw)
            if lu:
                license_uri = lu

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
    root["name"] = ds_title if not multi else (project_title or ds_title)
    if multi:
        fallback_description = (
            f"RO-Crate of the EDO internal-format instance for the project "
            f"'{project_title}' (linked DMP + SMS)."
            if project_title
            else "RO-Crate of the EDO internal-format instance (linked DMP + SMS)."
        )
    else:
        fallback_description = (
            f"RO-Crate of the EDO internal-format instance '{ds_title}' "
            f"(linked DMP + SMS) for the project '{project_title}'."
        )
    root["description"] = fallback_description if multi else (ds_description or fallback_description)
    root["isBasedOn"] = {"@id": project_iri}
    root["conformsTo"] = {"@id": SCHEMA_IRI}

    # keywords: union over all datasets, first occurrence order, no duplicates
    keywords: list[str] = []
    for ds in datasets:
        for k in _texts(_val(ds, "dcat:keyword")):
            if k not in keywords:
                keywords.append(k)
    if keywords:
        root["keywords"] = keywords

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
    action_object = (
        [{"@id": _first_text(ds, "@id") or f"#dataset-{i}"}
         for i, ds in enumerate(datasets, start=1)]
        if multi
        else {"@id": _first_text(first, "@id") or project_iri}
    )
    crate.add_jsonld({
        "@id": "#generate-action",
        "@type": "CreateAction",
        "name": "internal-format -> RO-Crate generation (socket-ux)",
        "description": (
            "Generated on request by the socket-ux API from the project graph "
            "in the internal database (Fuseki /projects)."
        ),
        "object": action_object,
        "result": {"@id": "./"},
    })
    root["prov:wasGeneratedBy"] = {"@id": "#generate-action"}

    # per-dataset entities (UPL-003): each dcat:dataset with its title,
    # description, keywords, identifier, personal/sensitive flags and its
    # distributions (MediaObject) — the CCA highlight targets.
    for i, ds in enumerate(datasets, start=1):
        ds_id = _first_text(ds, "@id") or f"#dataset-{i}"
        entity: dict[str, Any] = {
            "@id": ds_id,
            "@type": "Dataset",
            "name": _first_text(ds, "dcterms:title") or f"Dataset {i}",
        }
        description = _first_text(ds, "dcterms:description")
        if description:
            entity["description"] = description
        ds_keywords = _texts(_val(ds, "dcat:keyword"))
        if ds_keywords:
            entity["keywords"] = ds_keywords
        identifier = _first_text(_as_dict(_val(ds, "edo:identifier")), "dcterms:identifier")
        if identifier:
            entity["identifier"] = identifier
        for flag_key in ("edo:personalData", "edo:sensitiveData"):
            flag = _boolean(ds, flag_key)
            if flag is not None:
                entity[flag_key] = flag

        distribution_refs = []
        for j, dist in enumerate(_nodes(_val(ds, "dcat:distribution")), start=1):
            dist_id = _first_text(dist, "@id") or f"#distribution-{i}-{j}"
            dist_ent: dict[str, Any] = {
                "@id": dist_id,
                "@type": "MediaObject",
                "name": _first_text(dist, "dcterms:title") or f"Distribution {j}",
            }
            fmt = _format_id(_val(dist, "dcat:format"))
            if fmt:
                dist_ent["encodingFormat"] = fmt
            access_url = _first_text(dist, "dcat:accessURL")
            if access_url:
                dist_ent["contentUrl"] = access_url
            data_access = _first_text(dist, "edo:dataAccess")
            if data_access:
                dist_ent["edo:dataAccess"] = data_access
            crate.add_jsonld(dist_ent)
            distribution_refs.append({"@id": dist_id})
        if distribution_refs:
            entity["distribution"] = distribution_refs

        crate.add_jsonld(entity)
        root.append_to("hasPart", {"@id": ds_id})

    # sensor contextual entities + measured properties (the DMP-SMS link,
    # CF2-005) — deduplicated across datasets, root observes the union.
    sensor_ids: set[str] = set()
    prop_counter = 0
    for i, ds in enumerate(datasets, start=1):
        sensor = _as_dict(_val(ds, "prov:wasGeneratedBy"))
        sensor_id = _first_text(sensor, "@id")
        sensor_title = _first_text(sensor, "dcterms:title")
        if not sensor_id and not sensor_title:
            continue
        sensor_key = sensor_id
        if not sensor_key:
            sensor_key = "#sensor" if "#sensor" not in sensor_ids else f"#sensor-{i}"
        if sensor_key not in sensor_ids:
            sensor_ids.add(sensor_key)
            sensor_pid = _first_text(_as_dict(_val(sensor, "edo:identifier")),
                                     "dcterms:identifier")
            crate.add_jsonld({
                "@id": sensor_key,
                "@type": "sosa:Sensor",
                "name": sensor_title or "Sensor",
                "identifier": sensor_pid or sensor_key,
            })
            root["prov:wasGeneratedBy"] = {"@id": sensor_key}
        for prop in _nodes(_val(sensor, "sosa:observes")):
            prop_counter += 1
            quantity = _expand_smscv(_text(_val(prop, "smscv:measuredQuantity")))
            name = _first_text(prop, "dcterms:title") or quantity
            prop_id = quantity or f"#measured-property-{prop_counter}"
            prop_entity: dict[str, Any] = {
                "@id": prop_id,
                "@type": "sosa:ObservableProperty",
                "name": name,
            }
            if quantity:
                prop_entity["identifier"] = quantity
            crate.add_jsonld(prop_entity)
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
