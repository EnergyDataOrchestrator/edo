# Provenance crate: `05_P05_S05_internal-format.schema.json` (F11)

This directory is a RO-Crate 1.1 (`ro-crate-metadata.json`) that documents the
**provenance of one version** of the generated JSON Schema
`05_P05_S05_internal-format.schema.json` — the regeneration performed on
2026-11-19 to close finding **F11** ("the CF2-004 schema edits make the
generated JSON Schema stale; regenerate before the next JSON-Schema consumer",
see `../trafos/README.md`, section 13).

## What the crate contains

**Copies** (the two files that *are* the version):

| File | Role |
|---|---|
| `05_P05_S05_internal-format.schema.json` | The generated JSON Schema (this version). Draft 2019-09, `metamodel_version 1.11.0`. |
| `05_P05_S05_internal-format-schema.yaml` | The LinkML schema — the direct source this version was generated from. |

**References** (files outside the crate, addressed by repository-relative
paths from the crate root; they are *not* copied — they stay where they are
maintained). Each entity in `ro-crate-metadata.json` states *how* the file has
to do with the version:

- `../../internal-format/04_P04_S04_internal-format-spec.md` — specification
  v0.2 (CF1-006) the format is derived from.
- `../05_P05_S05_madmp-schema.yaml`, `../05_P05_S05_sms-schema.yaml` —
  source-side sibling schemas (CF1-007 family); their CV value sets are
  mirrored by the internal-format enums.
- `../trafos/patterns.md`, `../trafos/dmp-to-internal.linkml-map.yaml`,
  `../trafos/sms-to-internal.linkml-map.yaml` — transformation rules and the
  LinkML Maps compiled from them (CF2-004); inputs to the schema
  reconciliation.
- `../fuseki-proto/tool/src/fuseki_proto/trip.py` — hand-coded realisation
  (CF2-003) that is the behavioural reference of the reconciliation.
- `../fuseki-proto/tool/src/fuseki_proto/agnostic_trip.py` — map-driven
  realisation consuming the schema together with the maps.
- `../trafos/README.md` — documentation of the reconciliation (§9) and the
  findings catalogue with F11 (§13).
- `../../../../05_Cards/CF1-006.md`, `CF1-007.md`, `CF2-003.md`,
  `CF2-004.md` — cards in which the format, the schemas, the realisations and
  the finding were decided and logged.

## How the version came about (graph summary)

1. **Specification** (CF1-006) → **LinkML schema** (CF1-007, commit
   `397a789`/`09a25eb`), first generated as JSON Schema with linkml 1.12.0.
2. **CF2-004 schema reconciliation** (`e8b6ee8`): slot mappings/descriptions
   of the LinkML schema were aligned with the CF2-003 realisation
   (`time:hasEnd`, `license_start_date = time:hasBeginning`, IANA media-type
   IRIs per P34, SMS CV mappings S7/S8/S13/S14). This made the previously
   generated JSON Schema stale → F11.
3. **This version**: `.venv/bin/gen-json-schema …internal-format-schema.yaml`
   (linkml **1.11.1**, pinned for linkml-map 0.5.2 per F8) run 2026-11-19
   18:34 +01:00, recorded as `CreateAction` `#gen-json-schema-run-20261119T1834`
   with `instrument`, `object`, `result`, `startTime`/`endTime`.

Version identity for reproducibility:

- predecessor blob: `14c33a8b9064c8d81d413f45c3dbc3baea7f5917`
  (generated with linkml 1.12.0, `metamodel_version 1.12.0`, commit `09a25eb`)
- this version's blob: `d768c94a65ca824260495f6f67c48ae8fd31d2cc`
- differences: the reconciliation descriptions, one generator-behaviour change
  (`data_access`: `anyOf` with `null` → direct `$ref`), and the
  `metamodel_version` downgrade caused by the pinning.

## Conventions and caveats

- Provenance vocabulary: schema.org (`CreateAction`, `object`/`result`/
  `instrument`/`startTime`/`endTime`) plus PROV terms (`wasGeneratedBy`,
  `wasDerivedFrom`) via the additional `prov` context entry.
- External files are referenced with repository-relative paths although
  RO-Crate 1.1 prescribes absolute URLs for external entities — a pragmatic
  deviation kept deliberately so the crate stays resolvable inside the
  repository checkout.
- The copies are snapshots; if the schema changes again, either refresh this
  crate or create a new one per version (one crate per version keeps the
  provenance history explicit).
