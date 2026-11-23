"""Committed RO-Crate state in Fuseki (UPL-001 step 2b, decision (a)).

The committed crate slice of a project lives in a *named graph*
``urn:edo:crate:<pid>`` in the same Fuseki dataset as the internal-format
project graphs — decision (a) of the UPL-001 write-back question:

* write-back stays in the graph-DB circle (SHACL-validatable later),
* the regimo-core sync engine never touches crate graphs (it upserts only
  ``<project_iri>`` and its sensor closure), so there is no write collision,
* commits are announced on ``edo.crate.v1`` (``crate.committed``).

Transport: the crate metadata (compact JSON-LD) is stored *verbatim* as one
literal triple in the named graph (``edo:crateJson``). An expanded-triples
representation was tried first and rejected: pyld expansion silently drops
every property outside the RO-Crate 1.1 context (``sosa:observes``, and any
custom term a user adds in NovaCrate), and its ``remove_base`` mangles
``urn:uuid:...`` IRIs when compacting against an ``urn:`` base. The verbatim
literal makes the round trip content-exact by construction — what a client
commits is what every later GET serves and what the OCC digest covers.

The committed state is authoritative crate JSON; mirroring it as queryable
triples (for SHACL/SPARQL) is a future step, not a second source of truth.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from .config import Settings
from .fuseki import FusekiError, _auth

CRATE_JSON_PREDICATE = "https://w3id.org/edo/terms/crateJson"
CRATE_METADATA_TYPE = "https://w3id.org/edo/terms/CrateMetadata"


def crate_graph_uri(project_iri: str) -> str:
    """The named graph holding the committed crate of one project."""
    return f"urn:edo:crate:{project_iri}"


def load_committed(
    settings: Settings, project_iri: str, client: httpx.Client,
) -> dict[str, Any] | None:
    """The committed crate metadata of one project, or ``None`` when absent.

    Reads the verbatim ``edo:crateJson`` literal from the named graph.
    """
    graph_uri = crate_graph_uri(project_iri)
    query = (
        f"SELECT ?json WHERE {{ GRAPH <{graph_uri}> {{ "
        f"<{graph_uri}#metadata> <{CRATE_JSON_PREDICATE}> ?json }}}}"
    )
    response = client.post(
        settings.dataset_query_url,
        data={"query": query},
        auth=_auth(settings),
        headers={"Accept": "application/sparql-results+json"},
    )
    if response.status_code != 200:
        raise FusekiError(f"Fuseki crate graph read failed: HTTP {response.status_code}")
    bindings = response.json().get("results", {}).get("bindings", [])
    if not bindings:
        return None
    return json.loads(bindings[0]["json"]["value"])


def save_committed(
    settings: Settings, project_iri: str, metadata: dict[str, Any],
    client: httpx.Client,
) -> None:
    """Persist crate metadata as the project's committed crate (named graph).

    The compact JSON-LD document is stored verbatim as one literal triple;
    HTTP ``PUT /{dataset}/data?graph=<uri>`` *replaces* the named graph's
    content, so repeated commits are idempotent writes. (POST would *add* —
    Jena keeps the old triples, the graph accumulates stale literals and
    ``load_committed`` reads an arbitrary one — regression-tested.)
    """
    document = {
        "@id": f"{crate_graph_uri(project_iri)}#metadata",
        "@type": CRATE_METADATA_TYPE,
        CRATE_JSON_PREDICATE: json.dumps(metadata, ensure_ascii=False),
    }
    response = client.put(
        f"{settings.fuseki_url.rstrip('/')}/{settings.fuseki_dataset}/data",
        params={"graph": crate_graph_uri(project_iri)},
        content=json.dumps(document, ensure_ascii=False),
        auth=_auth(settings),
        headers={"Content-Type": "application/ld+json"},
    )
    # 200 replaces an existing graph, 201 creates a new one — both are writes.
    if response.status_code not in (200, 201):
        raise FusekiError(f"Fuseki crate graph write failed: HTTP {response.status_code}")
