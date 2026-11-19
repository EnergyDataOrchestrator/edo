"""socket-ux FastAPI application.

The API the vue-frontend talks to:

* ``GET /healthz``                     — liveness (+ internal-DB reachability)
* ``GET /api/v1/projects``             — projects and their key values (Fuseki)
* ``GET /api/v1/projects/{pid}/values`` — full internal-format document
* ``GET /api/v1/projects/{pid}/crate``  — RO-Crate metadata for NovaCrate

``pid`` is the URL-encoded project IRI from the internal database.
"""

from __future__ import annotations

import logging
from typing import Any, Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from . import crate as crate_mod
from . import fuseki
from .bus import CRATE_TOPIC, SOCKET_ID, BusPublisher, MessageHeader, ontology_uri_from_path
from .config import get_settings
from .internal_format import project_doc

logger = logging.getLogger(__name__)

app = FastAPI(title="socket-ux", version="0.1.0", description=(
    "Ontology-aware socket presenting the API for the EDO front end."
))

_publisher: BusPublisher | None = None


def publisher() -> BusPublisher:
    global _publisher
    if _publisher is None:
        settings = get_settings()
        _publisher = BusPublisher(
            settings.kafka_bootstrap_servers,
            ontology_uri_from_path(settings.ontology_path),
        )
    return _publisher


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    settings = get_settings()
    try:
        with _client(settings) as client:
            client.get(settings.fuseki_url, timeout=3.0)
        fuseki_ok = True
    except Exception:
        fuseki_ok = False
    return {"status": "ok", "fuseki": "up" if fuseki_ok else "unreachable"}


def _client(settings) -> "httpx.Client":  # noqa: F821 — typing kept lean
    import httpx

    return httpx.Client(base_url=settings.fuseki_url)


@app.get("/api/v1/projects")
def projects() -> dict[str, Any]:
    """Projects and their values from the internal database."""
    import httpx

    settings = get_settings()
    try:
        with httpx.Client(timeout=10.0) as client:
            found = fuseki.list_projects(settings, client)
    except fuseki.FusekiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"projects": found}


@app.get("/api/v1/projects/{pid:path}/values")
def project_values(pid: str) -> dict[str, Any]:
    """Full internal-format document (compact JSON-LD) of one project."""
    import httpx

    settings = get_settings()
    try:
        with httpx.Client(timeout=15.0) as client:
            graph = fuseki.project_graph_jsonld(settings, pid, client)
            doc = project_doc(graph, pid)
    except fuseki.FusekiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return doc


@app.get("/api/v1/projects/{pid:path}/crate")
def project_crate(pid: str) -> JSONResponse:
    """RO-Crate metadata JSON for one project, ready for NovaCrate."""
    import httpx

    settings = get_settings()
    try:
        with httpx.Client(timeout=15.0) as client:
            graph = fuseki.project_graph_jsonld(settings, pid, client)
            doc = project_doc(graph, pid)
    except fuseki.FusekiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    crate = crate_mod.build_crate(doc, pid)
    metadata = crate_mod.crate_metadata_json(crate)

    publisher().publish(
        CRATE_TOPIC,
        {"project": pid, "crate_root": metadata.get("@graph", [{}])[0].get("@id", "./")},
        MessageHeader(
            socket_id=SOCKET_ID,
            project_id=pid,
            schema_id="ro-crate-1.1",
            ontology_uri=ontology_uri_from_path(settings.ontology_path),
            lineage=f"fuseki/{settings.fuseki_dataset} -> socket-ux -> nova-crate",
        ),
    )
    return JSONResponse(content=metadata)
