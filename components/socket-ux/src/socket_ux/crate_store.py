"""Committed RO-Crate state in Fuseki (UPL-001 step 2b, decision (a)).

The committed crate slice of a project lives in a *named graph*
``urn:edo:crate:<pid>`` in the same Fuseki dataset as the internal-format
project graphs — decision (a) of the UPL-001 write-back question:

* write-back stays in the graph-DB circle (SHACL-validatable later),
* the regimo-core sync engine never touches crate graphs (it upserts only
  ``<project_iri>`` and its sensor closure), so there is no write collision,
* commits are announced on ``edo.crate.v1`` (``crate.committed``).

Transport: the crate metadata (compact JSON-LD with the RO-Crate 1.1 context
reference) is expanded client-side with pyld and stored as expanded JSON-LD in
the named graph (POST ``/{dataset}/data?graph=<uri>`` replaces the graph).
Reading compacts the graph back against the RO-Crate context.

The RO-Crate 1.1 JSON-LD context is bundled under ``data/`` and installed as a
pyld fallback loader: expansion/compaction also work when w3id.org is not
reachable (air-gapped or offline test runs) and stay byte-stable otherwise.
"""

from __future__ import annotations

import json
import logging
from importlib import resources
from typing import Any

import httpx
import pyld.jsonld

from .config import Settings
from .fuseki import FusekiError, _auth

logger = logging.getLogger(__name__)

RO_CRATE_CONTEXT_URL = "https://w3id.org/ro/crate/1.1/context"
RO_CRATE_CONTEXT_REF = {"@context": RO_CRATE_CONTEXT_URL}

_loader_installed = False


def _bundled_ro_crate_context(url: str) -> dict[str, Any] | None:
    """The bundled RO-Crate 1.1 context document, when ``url`` asks for it."""
    if url.rstrip("/") != RO_CRATE_CONTEXT_URL.rstrip("/"):
        return None
    doc = json.loads(
        resources.files("socket_ux").joinpath("data/ro-crate-1.1-context.json")
        .read_text(encoding="utf-8"))
    return {"document": doc, "documentUrl": url, "contextUrl": None}


def _ensure_loader() -> None:
    """Install a pyld document loader with the bundled-context fallback.

    Applied once per process; the remote loader stays primary (fresh context),
    the bundled copy only answers when the fetch fails — offline runs and CI.
    """
    global _loader_installed
    if _loader_installed:
        return
    remote_loader = pyld.jsonld.get_document_loader()

    def loader(url: str, options: dict[str, Any] | None = None):  # noqa: ANN001, ANN202
        try:
            return remote_loader(url, options or {})
        except Exception:  # noqa: BLE001 — fallback must catch loader failures
            bundled = _bundled_ro_crate_context(url)
            if bundled is not None:
                return bundled
            raise

    pyld.jsonld.set_document_loader(loader)
    _loader_installed = True


def crate_graph_uri(project_iri: str) -> str:
    """The named graph holding the committed crate of one project."""
    return f"urn:edo:crate:{project_iri}"


def crate_base_iri(project_iri: str) -> str:
    """Expansion/compaction base for one project's crate.

    pyld resolves relative crate ids (``./``, ``ro-crate-metadata.json``,
    ``#contact``) against a base IRI — its default is a bogus constant
    (``http://example.org/base/``). Using the crate graph URI + ``/`` keeps
    the round trip through Fuseki symmetric: expand resolves relative ids
    into the graph's IRI space, compact against the same base relativizes
    them back, so the served metadata keeps the literal ``./`` root NovaCrate
    expects.
    """
    return f"{crate_graph_uri(project_iri)}/"


def load_committed(
    settings: Settings, project_iri: str, client: httpx.Client,
) -> dict[str, Any] | None:
    """The committed crate metadata of one project, or ``None`` when absent.

    Reads the named graph, then compacts it back into the RO-Crate shape.
    """
    graph_uri = crate_graph_uri(project_iri)
    query = f"CONSTRUCT {{ ?s ?p ?o }} WHERE {{ GRAPH <{graph_uri}> {{ ?s ?p ?o }} }}"
    response = client.post(
        settings.dataset_query_url,
        data={"query": query},
        auth=_auth(settings),
        headers={"Accept": "application/ld+json"},
    )
    if response.status_code != 200:
        raise FusekiError(f"Fuseki crate graph read failed: HTTP {response.status_code}")
    expanded = response.json()
    if not expanded:
        return None
    _ensure_loader()
    try:
        compacted = pyld.jsonld.compact(
            expanded, RO_CRATE_CONTEXT_REF,
            options={"base": crate_base_iri(project_iri)})
    except Exception as exc:  # noqa: BLE001 — context problems are 502s, not 500s
        raise FusekiError(f"crate compaction failed: {exc}") from exc
    return compacted


def save_committed(
    settings: Settings, project_iri: str, metadata: dict[str, Any],
    client: httpx.Client,
) -> None:
    """Persist crate metadata as the project's committed crate (named graph).

    Expands the compact JSON-LD (resolving the RO-Crate context locally) and
    POSTs it to the Fuseki data endpoint with ``?graph=`` — Fuseki replaces
    the named graph's content, so repeated commits are idempotent writes.
    """
    _ensure_loader()
    try:
        expanded = pyld.jsonld.expand(
            metadata, options={"base": crate_base_iri(project_iri)})
    except Exception as exc:  # noqa: BLE001 — a malformed crate is a 400, not a 500
        raise CrateValidationError(f"crate is not valid JSON-LD: {exc}") from exc
    response = client.post(
        f"{settings.fuseki_url.rstrip('/')}/{settings.fuseki_dataset}/data",
        params={"graph": crate_graph_uri(project_iri)},
        content=json.dumps(expanded, ensure_ascii=False),
        auth=_auth(settings),
        headers={"Content-Type": "application/ld+json"},
    )
    if response.status_code != 200:
        raise FusekiError(f"Fuseki crate graph write failed: HTTP {response.status_code}")


class CrateValidationError(ValueError):
    """The submitted crate metadata is not processable JSON-LD."""
