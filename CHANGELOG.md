# Changelog

All notable changes to the EDO umbrella repository are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/); versioning: SemVer.

## [0.1.0] - 2026-11-23

First umbrella release — first verified end-to-end chain.

### Added
- Umbrella repository pinning the component repositories as Git submodules: `schema/ontology`, `core`, `components/socket-rdmo`, `infrastructure`, `frontend/vue-frontend`.
- Root uv workspace and docker-compose orchestration (Kafka broker, semantic layer, Fuseki; restart policies).
- `projecting_spaces/` Obsidian vault: project cards (CF1–CF4, REV), kanban board, artefacts (models, methods, fragments).

### Verified for this release
- RDMO maDMP export (project 11 "Semantico", DOI-based) → regimo-core sync engine → Fuseki `/projects` graph (SHACL-conformant, 0 violations) → Kafka `edo.projects.v1` → RO-Crate with creator and funder.
- Test suites green: 53 exporter mock tests, 32 core tests; sync re-run digest-stable ("no changes").
