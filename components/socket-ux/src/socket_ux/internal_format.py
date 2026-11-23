"""Internal-format JSON-LD extraction.

Turns the full-URI JSON-LD graph from Fuseki into the *compact* internal-format
document (``dcterms:title``-style keys, nested nodes) that the LinkML schema
and ``fuseki-proto``'s ``ro_crate.py`` operate on.

The context is the one from the internal-format linked-instance example
(``scripts/internal-format/linked-instance.example.json``), extended by the
``time`` prefix used by the spec.
"""

from __future__ import annotations

from typing import Any

from pyld import jsonld

# Context of the internal-format compact JSON-LD (source of truth:
# projecting_spaces/EDO/Artefacts/07_Fragments/scripts/internal-format/
# linked-instance.example.json; 'time' added for socket-ux compaction).
INTERNAL_CONTEXT: dict[str, Any] = {
    "edo": "https://w3id.org/edo/terms/",
    "dcterms": "http://purl.org/dc/terms/",
    "dcat": "http://www.w3.org/ns/dcat#",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "prov": "http://www.w3.org/ns/prov#",
    "time": "http://www.w3.org/2006/time#",
    "sosa": "http://www.w3.org/ns/sosa/",
    "smscv": "https://sms-cv.helmholtz.cloud/sms/cv/api/v1/",
    # published data-file columns (UPL-004 Stage 2, decision A)
    "csvw": "http://www.w3.org/ns/csvw#",
}


def project_doc(graph_jsonld: list[dict[str, Any]] | dict[str, Any], project_iri: str) -> dict[str, Any]:
    """Extract the project node (with its embedded closure) and compact it.

    ``graph_jsonld`` is a JSON-LD document with full URIs (Fuseki output).
    Nodes referenced by the project that exist in the graph are embedded
    (matching the internal format's nested style); IRIs that are only
    controlled-vocabulary references (no node in the graph) stay as ``@id``
    references.
    """
    expanded = jsonld.expand(graph_jsonld)
    nodes: dict[str, dict[str, Any]] = {}
    for node in _flatten_graph(expanded):
        node_id = node.get("@id")
        if node_id:
            nodes[node_id] = node

    root = nodes.get(project_iri)
    if root is None:
        raise KeyError(f"project {project_iri} not found in graph")

    embedded = _embed(root, nodes, seen=set())
    return jsonld.compact(embedded, INTERNAL_CONTEXT)


def _flatten_graph(expanded: list[Any]) -> list[dict[str, Any]]:
    """Yield every node object, including nodes inside ``@graph`` arrays."""
    out: list[dict[str, Any]] = []
    for item in expanded:
        if not isinstance(item, dict):
            continue
        graph = item.get("@graph")
        if isinstance(graph, list):
            out.extend(n for n in graph if isinstance(n, dict))
        else:
            out.append(item)
    return out


def _embed(node: dict[str, Any], nodes: dict[str, dict[str, Any]], seen: set[str]) -> dict[str, Any]:
    """Recursively replace ``@id`` references with embedded nodes (no cycles)."""
    node_id = node.get("@id")
    if node_id:
        if node_id in seen:
            return {"@id": node_id}
        seen = seen | {node_id}

    result: dict[str, Any] = {}
    for key, value in node.items():
        result[key] = [_embed_value(v, nodes, seen) for v in value] if isinstance(value, list) else value
    return result


def _embed_value(value: Any, nodes: dict[str, dict[str, Any]], seen: set[str]) -> Any:
    if isinstance(value, dict):
        ref = value.get("@id")
        if ref and "@value" not in value and ref in nodes:
            return _embed(nodes[ref], nodes, seen)
        return value
    return value
