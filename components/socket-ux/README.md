# socket-ux

Ontology-aware **socket** presenting the API that the EDO vue-frontend talks to
(`components/vue-frontend`). It is the backend counterpart of the frontend's
project drawer and NovaCrate editor:

```
vue-frontend ──HTTP──> socket-ux ──SPARQL──> Fuseki /projects (internal DB)
     │                     │
     │                     └──Kafka (optional, 6-header contract)──> databus
     └──NovaCrate iframe <── RO-Crate metadata JSON (on project click)
```

## What it does

| Endpoint | Purpose |
|---|---|
| `GET /healthz` | Liveness + internal-DB reachability |
| `GET /api/v1/projects` | Projects and their key values (title, description, datasets, contact) for the drawer list |
| `GET /api/v1/projects/{pid}/values` | Full internal-format document (compact JSON-LD) of one project |
| `GET /api/v1/projects/{pid}/crate` | RO-Crate metadata JSON for one project, ready for NovaCrate |
| `GET /api/v1/events` | SSE stream of databus project events (live refresh of the drawer) |

`{pid}` is the URL-encoded project IRI from the internal database, e.g.
`urn%3Auuid%3Ad9e575a1-...`.

### Ontology awareness

- The internal-format project graphs live in the Fuseki TDB2 dataset
  `/projects` as RDF using the EDO vocabulary (`https://w3id.org/edo/terms/`),
  Dublin Core terms, DCAT, FOAF, PROV, SOSA and the SMS controlled
  vocabulary. The socket queries this graph directly (SPARQL) — there is no
  separate "translation" step; the internal format *is* the ontology-aware
  representation (CF2-003/CF2-004).
- Databus events follow the `regimo_core.interfaces.message` 6-header contract
  (`socket_id`, `ontology_uri`, `project_id`, `schema_id`, `timestamp`,
  `lineage`) — see `bus.py`. Publishing is **optional**: when
  `KAFKA_BOOTSTRAP_SERVERS` is unset or the broker is unreachable, events are
  logged and the API keeps working (the user never notices the databus, per
  the frontend design decision — the bus is only visible in Settings).

### Live project events (CF1)

`regimo-core` publishes one semantic event per project change on the
`edo.projects.v1` topic. When `KAFKA_BOOTSTRAP_SERVERS` is set, socket-ux
runs a background consumer (`events.py`) that fans those events out through
`GET /api/v1/events` as **server-sent events**:

```
regimo-core ──Kafka edo.projects.v1──> socket-ux ──SSE──> vue-frontend
```

Project events (`project.created` / `project.updated` / `project.removed`)
are forwarded as `event: projects-changed` with the original payload as JSON
data — the frontend drawer simply refetches the project list on each one.
Other bus events keep their action as the event name. A `: keep-alive`
comment every 15 s keeps idle connections open. Without a configured broker
the endpoint still works (it just never emits project events), keeping the
socket usable before and without the databus.

### RO-Crate on demand

`crate.py` mirrors the essential structure of
`projecting_spaces/EDO/Artefacts/07_Fragments/scripts/fuseki-proto/tool/src/fuseki_proto/ro_crate.py`
(CF2-006) but builds a **metadata-only** crate for interactive display: the
internal-format graph stays in the internal database and is referenced from
the root dataset via `isBasedOn`. The provenance-rich batch generation with
the packaged graph file remains in `fuseki-proto`.

## Configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `FUSEKI_URL` | `http://localhost:3031` | Internal graph database base URL |
| `FUSEKI_DATASET` | `projects` | Dataset with the internal-format project graphs |
| `FUSEKI_USER` / `FUSEKI_PASSWORD` | `admin` / `edo-proto` | Basic auth for the Fuseki data service |
| `KAFKA_BOOTSTRAP_SERVERS` | *(unset)* | Databus for ontology-aware events (optional) |
| `ONTOLOGY_PATH` | *(unset)* | Path to `regimo.ttl`; source of the `ontology_uri` header |

## Run

```sh
uv venv && uv pip install -e ".[test]"   # or: pip install -e .
uvicorn socket_ux.api:app --port 8090 --reload
```

The vue-frontend dev server proxies `/ux` → `http://localhost:8090`
(rewrite: strip `/ux`), so the frontend calls e.g. `/ux/api/v1/projects`.

## Tests

```sh
pytest
```

The tests use an internal-format fixture (the CF2-003/CF2-005 linked
DMP+SMS example) and `httpx.MockTransport` — no running Fuseki or Kafka
needed.
