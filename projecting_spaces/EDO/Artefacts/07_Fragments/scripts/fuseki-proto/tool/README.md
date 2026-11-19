# fuseki-proto-tool

Maintenance CLI for the EDO/Regimo Fuseki prototype (see the parent
`../README.md`). Wraps `docker compose` for lifecycle and the Fuseki HTTP
admin/data endpoints for backup/restore/load, with a small stdlib-only
`urllib` HTTP client (the only third-party dependency is `click`).

## Install

```bash
cd tool
python -m venv .venv && . .venv/bin/activate
pip install -e .
```

## Usage

> **Port:** the CLI defaults to `--port 3031`, matching
> `docker-compose.override.yml` (the prototype's non-conflicting host port).
> Host `3030` is left for the system-managed Jena Fuseki that serves the ORKG
> database. Point `fuseki-proto` at that other instance explicitly with
> `--port 3030` / `--dataset orkg` if you ever need to.

```bash
# Lifecycle (via docker compose)
fuseki-proto start          # build the image if needed, bring the container up, wait for ping
fuseki-proto stop           # stop the container gracefully (TDB2 lock!)
fuseki-proto status         # container + live-server/dataset overview

# Data maintenance (Fuseki HTTP)
fuseki-proto ping           # run a trivial query on a dataset (liveness)
fuseki-proto backup         # dump a dataset -> backups/ (now that Fuseki is Full,
                           #   this could use /$/backup instead, but the CONSTRUCT
                           #   dump round-trips fine and needs no code change)
fuseki-proto list-backups   # files in backups/
fuseki-proto restore <file> # empty the dataset then re-upload a backup/ttl dump
fuseki-proto load <file.ttl> [--graph <name>]   # POST a graph into /projects
fuseki-proto wipe [--yes]   # CLEAR ALL over /projects (destructive!)
```

The prototype runs **Fuseki Full**, so the web UI is on `http://localhost:3031/`
and the admin endpoints `/$/ping`, `/$/server`, `/$/backup` are available. The
CLI's `start`/`status`/`ping` probe a data-service `/query` endpoint (which
works under both server-only and Full), and `backup` uses a CONSTRUCT dump — so
the tool works unchanged; the Full admin endpoints are just extra conveniences.

Sensible options are derived from `docker-compose.yml`/`docker-compose.override.yml`
defaults and can be overridden (e.g. `--port`, `--user`, `--password`,
`--service`, `--dataset`, `--compose-dir`, `--backups-dir`). Run
`fuseki-proto --help` / `fuseki-proto <cmd> --help` for details.
