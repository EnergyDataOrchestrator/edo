"""socket-ux FastAPI application.

The API the vue-frontend talks to:

* ``GET /healthz``                     — liveness (+ internal-DB reachability)
* ``GET /api/v1/projects``             — projects and their key values (Fuseki)
* ``GET /api/v1/projects/{pid}/values`` — full internal-format document
* ``GET /api/v1/projects/{pid}/crate``  — RO-Crate metadata for NovaCrate
  (both answer with an ``ETag``/``X-Revision-Token`` revision token, UPL-001)
* ``GET /api/v1/events``               — SSE stream of databus project events
* ``GET /api/v1/whoami``               — the RBAC role this instance serves under (EDO_ROLE)
* ``GET /api/v1/bus/…``                — databus REST bridge / live tracker (steward+,
                                         POST publish admin) — card UPL-002

``pid`` is the URL-encoded project IRI from the internal database.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Annotated

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from . import crate as crate_mod
from . import fuseki
from . import auth
from .bus import CRATE_TOPIC, SOCKET_ID, BusPublisher, MessageHeader, ORDERED_HEADER_KEYS, ontology_uri_from_path
from .config import get_settings
from .databus import DatabusStore, broker_online, list_topics
from .events import BusEvent, EventBus, subscriber_from_settings
from .internal_format import project_doc
from .occ import TokenStore, canonical_digest

logger = logging.getLogger(__name__)

app = FastAPI(title="socket-ux", version="0.1.0", description=(
    "Ontology-aware socket presenting the API for the EDO front end."
))

_publisher: BusPublisher | None = None
_broker = EventBus()
_subscriber = None  # BusSubscriber | None, started in the lifespan below
_databus = DatabusStore()  # per-topic ring buffers behind the /bus bridge
_token_store: TokenStore | None = None  # OCC revision tokens (UPL-001)


def token_store() -> TokenStore:
    """The OCC token store (file-backed when SOCKET_UX_OCC_STATE_FILE is set)."""
    global _token_store
    if _token_store is None:
        _token_store = TokenStore(get_settings().occ_state_file)
    return _token_store


def broker() -> EventBus:
    """The in-process event broker feeding the SSE endpoint."""
    return _broker


@asynccontextmanager
async def _lifespan(_: FastAPI):
    global _subscriber
    settings = get_settings()
    # Fail fast on a misconfigured EDO_ROLE (UPL-002) instead of serving
    # everything under a silently mis-parsed role.
    auth.instance_role(settings)
    _broker.attach_loop(asyncio.get_running_loop())
    _subscriber = subscriber_from_settings(
        _broker, settings.kafka_bootstrap_servers,
        store=_databus, pattern=settings.kafka_topic_pattern)
    if _subscriber is not None:
        _subscriber.start()
    try:
        yield
    finally:
        if _subscriber is not None:
            _subscriber.stop()
            _subscriber = None


app.router.lifespan_context = _lifespan


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


# -- RBAC (UPL-002, option B): per-instance role + capability enforcement -----


@app.get("/api/v1/whoami")
def whoami() -> dict[str, Any]:
    """The role this instance serves under, for the frontends' role display.

    The UI may only *narrow* its locally chosen role against this value — the
    instance role is the ceiling. Mutating endpoints answer
    ``403 {required_role, ...}`` per the card's server-side-mirror invariant.
    """
    settings = get_settings()
    role = auth.instance_role(settings)
    return {
        "role": role,
        "source": "EDO_ROLE",
        "capabilities": auth.capabilities_for(role),
    }


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


def _etag_response(content: Any, token: str) -> JSONResponse:
    """JSON response carrying the slice's revision token (UPL-001).

    The token travels as ``ETag`` (strong validator, quoted per RFC 7232) and
    as ``X-Revision-Token`` (unquoted, trivial to read in the browser). The
    served bodies stay untouched — NovaCrate and the JSON tree must not see
    transport metadata.
    """
    return JSONResponse(content=content, headers={
        "ETag": f'"{token}"',
        "X-Revision-Token": token,
    })


@app.get("/api/v1/projects/{pid:path}/values")
def project_values(pid: str) -> JSONResponse:
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
    token = token_store().observe(f"adp:values:{pid}", doc)
    return _etag_response(doc, str(token))


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

    _broker.publish(BusEvent(
        topic="local.crate.v1",
        payload={"event": "crate.served", "project": pid},
        headers={"socket_id": SOCKET_ID},
    ))
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
    token = token_store().observe(f"fep:crate:{pid}", metadata)
    return _etag_response(metadata, str(token))


# -- server-sent events (CF1): project changes reach the front end live ------

SSE_KEEPALIVE_S = 15.0


def format_sse(event: BusEvent) -> str:
    """One bus event as an SSE message.

    Project events from regimo-core become ``event: projects-changed`` (the
    front end refetches the list); anything else keeps its action as the
    event name.
    """
    action = event.action or "bus.message"
    data = json.dumps(event.payload, ensure_ascii=False)
    name = "projects-changed" if action.startswith("project.") else action
    return f"event: {name}\ndata: {data}\n\n"


def format_bus_sse(event: BusEvent) -> str:
    """One bus message in full as an SSE message for the live tracker.

    Unlike :func:`format_sse` (which carries only the payload), this ships the
    complete bridge message shape — topic, payload, header, partition, offset,
    broker timestamp — so the Databus view can insert it into the right topic
    view without a round trip.
    """
    data = json.dumps({
        "topic": event.topic,
        "payload": event.payload,
        "header": event.headers,
        "partition": event.partition,
        "offset": event.offset,
        "timestamp": event.timestamp,
    }, ensure_ascii=False)
    return f"event: bus.message\ndata: {data}\n\n"


@app.get("/api/v1/events")
async def events(request: Request) -> StreamingResponse:
    """SSE stream of databus events (``edo.projects.v1`` via regimo-core).

    Emits ``event: projects-changed`` with the event payload as JSON data so
    the front end can refetch the project list; a keep-alive comment keeps
    proxies from closing idle connections.
    """

    async def stream():
        queue = _broker.subscribe()
        try:
            yield "retry: 3000\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=SSE_KEEPALIVE_S)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield format_sse(event)
        finally:
            _broker.unsubscribe(queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# -- live tracker feed (CF1-012): every bus message, in full, as SSE ---------


@app.get("/api/v1/bus/events")
async def bus_events(request: Request) -> StreamingResponse:
    """SSE stream of *every* bus message — the Databus view's live tracker.

    Each message is emitted as ``event: bus.message`` with the complete bridge
    shape (topic, payload, header, partition, offset, broker timestamp), so
    the front end can append it live to the selected topic's view. The same
    keep-alive/retry conventions as ``/api/v1/events`` apply. Diagnostics —
    gated to ``viewDiagnostics`` (steward+) like the bus bridge.
    """
    auth.require_capability("viewDiagnostics", get_settings())

    async def stream():
        queue = _broker.subscribe()
        try:
            yield "retry: 3000\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=SSE_KEEPALIVE_S)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield format_bus_sse(event)
        finally:
            _broker.unsubscribe(queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# -- databus REST bridge (CF1-012): the bus, as plain REST -------------------
#
# The contract of ``frontend/vue-frontend/src/lib/databus.ts``: topics,
# per-topic recent messages (bare JSON array), publishing with the 6-header
# contract, and a status probe for the "bridge online" chip. Without a
# configured/reachable broker the listing endpoints answer 503 so the
# frontend's ``bridgeAvailable()`` falls back to demo mode.


def _broker_servers() -> str:
    return get_settings().kafka_bootstrap_servers


@app.get("/api/v1/bus/topics")
def bus_topics() -> dict[str, Any]:
    """Topics of the broker as ``{"topics": [{name, partitions}]}``."""
    auth.require_capability("viewDiagnostics", get_settings())
    servers = _broker_servers()
    if not servers:
        raise HTTPException(status_code=503, detail="no databus configured (KAFKA_BOOTSTRAP_SERVERS unset)")
    try:
        topics = list_topics(servers)
    except Exception as exc:  # noqa: BLE001 — offline must answer 503, not 500
        raise HTTPException(status_code=503, detail=f"broker unreachable: {exc}") from exc
    return {"topics": topics}


@app.get("/api/v1/bus/topics/{topic}/messages")
def bus_messages(topic: str, limit: int = Query(default=20, ge=1, le=100)) -> list[dict[str, Any]]:
    """The last ``limit`` messages of one topic from the ring buffer.

    Bare JSON array — that is what ``recentMessages()`` in ``databus.ts``
    expects. Headers are shown verbatim per the 6-header contract.
    """
    auth.require_capability("viewDiagnostics", get_settings())
    return [m.as_api() for m in _databus.recent(topic, limit)]


class BusPublishBody(BaseModel):
    """POST body of the publish endpoint: ``{payload, header}``."""

    payload: dict[str, Any]
    header: dict[str, str]


@app.post("/api/v1/bus/topics/{topic}/messages")
def bus_publish(topic: str, body: BusPublishBody) -> dict[str, Any]:
    """Publish a payload with the 6-header contract to one topic.

    Makes the frontend's ``publishMaDmp()`` real. The message is also
    recorded in the ring buffer right away so it shows up in the topic's
    recent messages without waiting for the consumer round trip (the store
    de-duplicates the consumer's own copy).
    """
    auth.require_capability("manageSystem", get_settings())
    missing = [key for key in ORDERED_HEADER_KEYS if key not in body.header]
    if missing:
        raise HTTPException(
            status_code=400,
            detail="header violates the 6-header contract; missing: " + ", ".join(missing))
    header = MessageHeader(
        socket_id=body.header.get("socket_id", ""),
        ontology_uri=body.header.get("ontology_uri", ""),
        project_id=body.header.get("project_id", ""),
        schema_id=body.header.get("schema_id", ""),
        timestamp=body.header.get("timestamp", ""),
        lineage=body.header.get("lineage", ""),
    )
    if not publisher().publish(topic, body.payload, header):
        raise HTTPException(status_code=503, detail="bus publishing unavailable (no producer/broker)")
    # No local record here: the bridge consumer picks the produced message up
    # within ~1 s and records it once (with partition/offset) — recording it
    # locally too would show it twice.
    return {"published": True, "topic": topic}


@app.get("/api/v1/bus/status")
def bus_status() -> dict[str, Any]:
    """Bridge status: broker reachability, subscriber, per-topic buffer fill.

    Diagnostics — gated to ``viewDiagnostics`` (steward+) like the bus bridge.
    """
    auth.require_capability("viewDiagnostics", get_settings())
    servers = _broker_servers()
    return {
        "online": broker_online(servers),
        "subscriber": _subscriber is not None,
        "buffered": _databus.counts(),
    }
