# Changelog

All notable changes to the EDO umbrella repository are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/); versioning: SemVer.

## [0.2.0] - 2026-11-23

The observable-bus release (CF1-012 + CF1-013).

### Added
- socket-ux databus REST bridge (`/api/v1/bus/*`: topics, messages, status, SSE events) backed by per-topic ring buffers (CF1-012).
- Cards [[CF1-012]] (observable bus — closed), [[CF1-013]] (no-demo-data UI — closed), [[CF2-008]] (semantic search & grouping over bus messages).

### Verified for this release
- Live chain through the Vite proxy: Kafka messages from a sync round visible in the UI tracker/Bus drawer; `sync.round` heartbeat on `edo.sync.v1` drives the last-sync chip.
- Empty-RDMO behaviour: engine forgets and wipes artifacts when RDMO is empty, aborts untouched when unreachable; UI shows faithful empty states.
- Test suites green: 45 socket-ux bridge tests, 34 core sync tests; `pnpm type-check`/`pnpm lint` clean.

### Component releases
- `regimo-core` v0.2.0, `regimo-infrastructure` v0.2.0, `vue-frontend` v0.2.0 (see their CHANGELOGs); `socket-rdmo` and `ontology` unchanged at v0.1.0.

## [0.1.0] - 2026-11-23

First umbrella release — first verified end-to-end chain.

### Added
- Umbrella repository pinning the component repositories as Git submodules: `schema/ontology`, `core`, `components/socket-rdmo`, `infrastructure`, `frontend/vue-frontend`.
- Root uv workspace and docker-compose orchestration (Kafka broker, semantic layer, Fuseki; restart policies).
- `projecting_spaces/` Obsidian vault: project cards (CF1–CF4, REV), kanban board, artefacts (models, methods, fragments).

### Verified for this release
- RDMO maDMP export (project 11 "Semantico", DOI-based) → regimo-core sync engine → Fuseki `/projects` graph (SHACL-conformant, 0 violations) → Kafka `edo.projects.v1` → RO-Crate with creator and funder.
- Test suites green: 53 exporter mock tests, 32 core tests; sync re-run digest-stable ("no changes").
