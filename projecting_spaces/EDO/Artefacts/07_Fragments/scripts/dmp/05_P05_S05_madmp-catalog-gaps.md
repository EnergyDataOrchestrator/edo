# maDMP catalog gap register

*Created:* 2026-11-18 · *Scope:* EDO maDMP export (`03_P03_S03_madmp-export.mapping.yaml`, validator `04_P04_S04_validate-export.py`) · *Reference report:* `measurement_02/validation-report.md`

## Purpose

The maDMP (RDA DMP Common Standard) requires information that the **standard RDMO catalog does not ask**. Per decision of 2026-11-18 the standard RDMO catalog is treated as immutable — **no questions may be added to it** to satisfy the maDMP format. This document therefore *carries the absence*: every gap between what maDMP needs and what the standard catalog can provide is recorded here, together with the agreed handling.

Gap classes:

- **CATALOG-ABSENT** — the attribute exists in the RDMO domain (or not even that), but no question in the standard catalog asks for it. Cannot be answered in the project UI at all.
- **CATALOG-INSUFFICIENT** — the catalog asks a related question, but not at the granularity/shape maDMP needs (e.g. yes/no instead of a controlled vocabulary).
- **UNANSWERED** — the catalog *does* ask; the gap is project-specific, not structural. These are tracked in the walkthrough (validation report), **not** in this register — except where a policy decision is recorded.

## Register

| # | maDMP field | RDMO path (attempted) | Class | Impact on export | Handling | Status |
|---|---|---|---|---|---|---|
| 1 | `dmp/contact/identifier` | `project/data_management/identifier` | CATALOG-ABSENT | exported as `None` | leave empty; optional field in maDMP | ACCEPTED-EMPTY |
| 2 | `dmp/contact/identifier_type` | `project/data_management/identifier_type` | CATALOG-ABSENT | exported as `None` | leave empty | ACCEPTED-EMPTY |
| 3 | `dmp/contributor[*]/identifier` | `project/dataset/{preservation,metadata}/responsible_person/identifier` | CATALOG-ABSENT | exported as `None` | leave empty; possible future enrichment from EDO identity layer (ORCID) | ACCEPTED-EMPTY |
| 4 | `dmp/contributor[*]/identifier_type` | `…/responsible_person/identifier_type` | CATALOG-ABSENT | exported as `None` | leave empty | ACCEPTED-EMPTY |
| 5 | `dmp/contributor[metadata]/mbox` | `project/dataset/metadata/responsible_person/email` | CATALOG-ABSENT | contributor without email | leave empty (name is present) | ACCEPTED-EMPTY |
| 6 | `dmp/dmp_id/identifier` | `project/dmp/identifier` | CATALOG-ABSENT | no persistent DMP identifier | **RESOLVED 2026-11-18:** minted at export time by the plugin — deterministic `urn:uuid` via `uuid5(NAMESPACE_URL, "rdmo:project:<pk>")`; stable across exports of the same project | RESOLVED (generated) |
| 7 | `dmp/dmp_id/type` | `project/dmp/identifier_type` | CATALOG-ABSENT | — | **RESOLVED 2026-11-18:** fixed `urn` (the URN is in the maDMP identifier-type vocabulary); follows decision on #6 | RESOLVED (fixed) |
| 8 | `dmp/language` | `project/language` | CATALOG-ABSENT | exported as `None` | default to a fixed language at the EDO layer (`en`) — decision pending | OPEN |
| 9 | `dataset/fields/language` | `project/dataset/language` | CATALOG-ABSENT | exported as `None` | default together with #8 | OPEN |
| 10 | `dataset/fields/dataset_id/identifier` (primary) | `project/dataset/dataset_identifier` | CATALOG-ABSENT | fallback in place: `project/dataset/id` with type `other` (works) | keep fallback | ACCEPTED (fallback) |
| 11 | `dataset/fields/dataset_id/type` (primary) | `project/dataset/dataset_identifier` | CATALOG-ABSENT | — | keep fallback type `other` | ACCEPTED (fallback) |
| 12 | `distribution/after/certified_with` | `project/dataset/preservation/certification` | CATALOG-INSUFFICIENT | catalog offers yes/no only; maDMP wants a certificate type (DIN 31644, CoreTrustSeal, DSA, ISO 16363, …). Answer `0` (no) → empty = correct; answer `1` (yes) would still export nothing. | accept for now; "no certification" is the honest answer for current projects | ACCEPTED-EMPTY (known limitation) |
| 13 | `dmp/cost[*]/value + currency` | `project/costs/**` (18 attributes) | UNANSWERED (catalog does ask) | cost entries exported with value `None` until answered | decide per cost item whether an answer or an explicit "no costs" is exported | tracked in walkthrough (Group 5) |
| 14 | `dataset/fields/type` | `project/dataset/type` | CATALOG-ABSENT | exported as `None` until a source exists | maDMP dataset `type` (e.g. "Dataset"); propose a fixed default at the EDO/export layer — decision pending | OPEN |

## Notes

- **Contact (`dmp/contact/name` / `mbox`)** maps to `project/data_management/{name,mbox}`. Those attributes exist in the RDMO domain, but the standard catalog contains **no question and no page** on them (verified in the database: 0 questions, 0 pages, catalog "RDMO" unlocked). They are therefore per-project UNANSWERED-by-omission: they can never be filled from the UI with the standard catalog. Classified here as #1/#2-adjacent; the name/mbox themselves remain in the walkthrough trace as NOT-ANSWERED until a source is agreed.
- The 13 `PATH-MISSING-IN-CATALOG` rows in the validation report correspond to register items #1–#11 (plus the maDMP-example-catalog-only paths, which are not defects).
- The 44 *answered-but-not-exported* values are the inverse problem (catalog has answers, mapping spec does not use them). They are handled in walkthrough Group 6 (decisions), not in this register.

## Change log

- 2026-11-18 — register created after the decision to keep the standard RDMO catalog unchanged; items #1–#5, #10–#12 accepted, #6–#9 open.
- 2026-11-18 — **items #6/#7 resolved:** `dmp_id` is minted at export time by the exporter plugin (`renderer.generate`, spec kinds `generated: urn_uuid5` + `fixed: urn`, seed `rdmo:project:{project.pk}`). Implementation: `components/socket-rdmo/madmp-exporter` (`renderer.py`), mapping spec `03_P03_S03_madmp-export.mapping.yaml` (synced to the bundled copy), validator `04_P04_S04_validate-export.py` traces generated/fixed rows. Project #4 mints `urn:uuid:d9e575a1-7ae1-588a-be39-b44574958fa0`. Caveat: stability depends on the RDMO project pk; a moved/re-created project would mint a new URN. #8/#9 (languages) remain open.
- 2026-11-18 — **item #14 added:** discovered during walkthrough Group 2 that `project/dataset/type` has no question in any catalog (same structural class as the contact fields, #1/#2-adjacent). The validator's `in catalog` column only reflects domain-attribute existence, so the row had shown `in catalog: True` misleadingly.
