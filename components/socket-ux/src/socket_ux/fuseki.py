"""SPARQL client for the internal graph database (Fuseki ``/projects``).

The socket asks the internal database for the projects and their values:
project graphs live in the TDB2 ``/projects`` dataset as internal-format
RDF (see ``infrastructure/fuseki-proto``). All queries use basic auth, mirroring
``fuseki-proto``'s tool (``docker.py``).
"""

from __future__ import annotations

from typing import Any

import httpx

from .config import Settings

# Namespaces of the internal format (same prefixes as the LinkML schema and
# fuseki-proto's ro_crate.py).
EDO = "https://w3id.org/edo/terms/"
DCTERMS = "http://purl.org/dc/terms/"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDF_TYPE = RDF_NS + "type"


class FusekiError(RuntimeError):
    """Raised when the internal database cannot be queried."""


def _auth(settings: Settings) -> tuple[str, str]:
    return (settings.fuseki_user, settings.fuseki_password)


def _run_select(settings: Settings, query: str, client: httpx.Client) -> list[dict[str, Any]]:
    """Run a SPARQL SELECT, returning ``[]`` of var->term bindings."""
    response = client.post(
        f"{settings.dataset_query_url}",
        data={"query": query},
        auth=_auth(settings),
        headers={"Accept": "application/sparql-results+json"},
    )
    if response.status_code != 200:
        raise FusekiError(f"Fuseki query failed: HTTP {response.status_code}: {response.text[:200]}")
    bindings = response.json().get("results", {}).get("bindings", [])
    return bindings


def _term(binding: dict[str, Any], var: str) -> str:
    """String value of a bound variable ('' when unbound); strips lang tags."""
    term = binding.get(var)
    if not term:
        return ""
    return str(term.get("value") or "")


def list_projects(settings: Settings, client: httpx.Client) -> list[dict[str, Any]]:
    """All projects in the internal database with their key values.

    Returns a list of ``{"id", "title", "description", "dataset", "contact"}``.
    """
    query = f"""
    PREFIX edo:    <{EDO}>
    PREFIX dcterms: <{DCTERMS}>
    PREFIX rdf:    <{RDF_NS}>
    PREFIX foaf:   <http://xmlns.com/foaf/0.1/>
    PREFIX dcat:   <http://www.w3.org/ns/dcat#>
    SELECT ?project ?title ?description ?dataset ?contactName WHERE {{
      ?project rdf:type edo:Project ;
               dcterms:title ?title .
      OPTIONAL {{ ?project dcterms:description ?description }}
      OPTIONAL {{ ?project dcat:dataset ?dataset }}
      OPTIONAL {{ ?project edo:hasContact ?contact .
                 ?contact foaf:name ?contactName }}
    }} ORDER BY ?title
    """
    bindings = _run_select(settings, query, client)
    projects: dict[str, dict[str, Any]] = {}
    for row in bindings:
        pid = _term(row, "project")
        entry = projects.setdefault(
            pid,
            {
                "id": pid,
                "title": _term(row, "title"),
                "description": _term(row, "description"),
                "datasets": [],
                "contact": _term(row, "contactName"),
            },
        )
        ds = _term(row, "dataset")
        if ds and ds not in entry["datasets"]:
            entry["datasets"].append(ds)
    return sorted(projects.values(), key=lambda p: p["title"].lower())


def project_graph_jsonld(settings: Settings, project_iri: str, client: httpx.Client) -> dict[str, Any]:
    """The internal-format graph as full-URI JSON-LD (Fuseki output).

    Uses a full-graph ``CONSTRUCT`` rather than ``DESCRIBE``: Jena DESCRIBE
    does not return the complete blank-node closure, so nested nodes (values,
    distributions, ...) were missing. The closure of the project node is
    extracted client-side in ``internal_format.project_doc``.
    """
    query = "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }"
    response = client.post(
        settings.dataset_query_url,
        data={"query": query},
        auth=_auth(settings),
        headers={"Accept": "application/ld+json"},
    )
    if response.status_code != 200:
        raise FusekiError(f"Fuseki CONSTRUCT failed: HTTP {response.status_code}")
    doc = response.json()
    if not doc:
        raise FusekiError(f"no graph found for project {project_iri}")
    return doc
