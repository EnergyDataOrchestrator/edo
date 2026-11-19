# trafos — CF2-003 Realisierung: Transformationen DMP & SMS → internes Format

This directory documents and drives the realisation of card **CF2-003**
("Transformationen von DMP und SMS ins interne Format", fragment
`[[06_Transformationen]]`).

* `patterns.md` — the **transformation catalogue** (scenario 1 deliverable):
  every transformation from the sources into the internal format, tagged with a
  pattern identifier (P1–P42 for DMP, S1–S16 for SMS, N1–N6 for the new R4
  classes).
* `README.md` (this file) — the **realisation documentation**: how the three
  acceptance scenarios of CF2-003 were executed end-to-end on a concrete
  instance, every concrete mapping decision, the verification results and the
  findings/open items that fell out of it.
* The executing code lives in
  `../fuseki-proto/tool/src/fuseki_proto/trip.py` (`fuseki-proto trip …`), the
  storage backend is the Fuseki prototype `../fuseki-proto/` (README there).

Status: **all three scenarios executed 2026-11-19, run
`../fuseki-proto/data/trip/20261119-173927/`** — 41/41 round-trip checks passed,
triple-count equality store↔replay OK, one SHACL violation remains by design
(see *Findings*, F1).

---

## 1. The three scenarios (card CF2-003) and how they map to the run

| # | Scenario (Given/When/Then, condensed) | Stage of `trip.py` |
|---|---|---|
| 1 | **Transformation rules documented** — mapping rules captured; field-level transformations, edge cases, missing-value handling documented | `transform` (applies the `patterns.md` catalogue and writes every rule application, translation decision and loss into the report) |
| 2 | **The transformed project is stored in the Fuseki triplestore** — transformed internal-format graph stored in `/projects`, retrievable via SPARQL, validated against `project-claim-shapes.ttl` | `store` (wipe + upload + SPARQL retrievability check + pyshacl) |
| 3 | **Round-trip via the Fuseki triplestore preserves the data** — dump the store back out, verify the dump carries the same data as the original DMP and SMS | `verify` (dump → replay graph → 41 field-level checks + triple-count equality) |

`fuseki-proto trip run` executes 1 → 2 → 3 in one command.

## 2. Instance under test

| Source | File | Key content |
|---|---|---|
| DMP (maDMP export via RDMO) | `../dmp/measurement_02/Measurement_02-13.json` | `dmp_id` `urn:uuid:d9e575a1-7ae1-588a-be39-b44574958fa0` (type `urn`), project "Measurement_02" 2027-01-01…2027-07-31, 2 contributors ("A. Koubaa"), dataset `bnetza_vorhabenpunkte_bbplg_2` with 2 distributions, 3 quality-assurance items, personal+ sensitive data, no contact, no costs, no language |
| SMS device | `../sms/device-67.json` | "KIT-CN-IAI-Bau445-Weather-Station-Weatherstation", model FS6002, FuehlerSysteme eNET International GmbH, equipment type `smscv:equipmenttypes/54/`, PID `21.11157/9b6cdfb9-a4fb-4269-af04-1ef94588f5a8` |
| SMS device property | `../sms/device-67-property-159-air-temperature.json` | "Air temperature" (`smscv:measuredquantities/4/`), unit `…/units/51/` (°C), SMS range −80…60, accuracy/resolution `null`, sampling media Air, compartment Atmosphere, aggregation Average |

> Only device property 159 is available as a machine-readable file; the device
> references properties 157–161 (see finding F7).

## 3. Running it

```bash
cd ../fuseki-proto/tool
. .venv/bin/activate          # needs click; pyshacl optional (SHACL stage)
fuseki-proto start            # bring the prototype up (port 3031)
fuseki-proto trip run         # transform -> store -> verify
# or the individual stages:
fuseki-proto trip transform   # scenario 1: catalogue -> internal-format graph
fuseki-proto trip store       # scenario 2: load into /projects, SPARQL + SHACL
fuseki-proto trip verify      # scenario 3: dump, replay, field-level checks
```

Sources can be overridden (`--dmp`, `--sms-device`, `--sms-property`, repeatable
for several device properties); connection via `--port/--user/--password/--dataset`.

**Artifacts** per run in `../fuseki-proto/data/trip/<timestamp>/`:

| File | Content |
|---|---|
| `project-graph.ttl` | the transformed internal-format instance graph (Turtle) |
| `roundtrip-dump.ttl` | the Turtle dump Fuseki served back from `/projects` |
| `trip-report.json` | inputs, applied rules, notes/losses, all 41 checks with per-graph results, store/verify summaries, SHACL report |

Exit code: `0` when all round-trip checks pass and the replay triple count
equals the store's; `1` otherwise. The SHACL verdict is recorded in the report
but does **not** fail the run (F1 is an open mapping/shape decision, not a
round-trip failure).

## 4. Concrete mapping decisions (scenario 1)

The catalogue in `patterns.md` names the *rule*; this section records the
*decision taken for this instance* — the exact content of
`data/trip/20261119-173652/trip-report.json` (`stages.transform.applied_rules`,
50 entries). Highlights:

### 4.1 Project (P1–P9)

| Rule | Decision on this instance |
|---|---|
| P1 | `project/title` `"Measurement_02"` → `dcterms:title`. **Note:** spec §4's example carries the *DMP-document* title ("maDMP for Measurement_02") — see finding F3. |
| P2 | `project/description` "Example Measurement, as a child-project of IAI." → `dcterms:description` (1:1). |
| P3 | No `language` in export → **default `eng`** (omit → default). |
| P4 | `start`/`end` 2027-01-01…2027-07-31 → `time:hasInterval` blank node, dates cast to `xsd:date`. (NB: the spec §4 example shows the older 2026-07-01…09-11 window.) |
| P5/P16/P17 | `dmp_id` `urn:uuid:d9e575a1-…` (type `urn`) → `edo:dmpId` Identifier node. |
| P6 | **No `contact` in export → omitted** (faithful mapping). This trips `edo:ProjectShape` (`sh:minCount 1` on `edo:hasContact`) — finding **F1**. |
| P7/P8 | 2 contributors → 2 `edo:Contribution` nodes. Role translation (see 4.4): both "Responsible for preservation" and "Responsible for metadata …" → `Data Curator`; unmapped templates would default to `Other`. The free-text role itself is lost in the CV translation (documented). |
| P10/P11 | Agent name 1:1; mbox cast to `mailto:…` **typed as `xsd:anyURI` literal** — required by `foaf:PersonShape` (`sh:datatype xsd:anyURI`); an IRI has no datatype and violates the shape — finding **F2**. |
| P9 | No `cost[]` → omitted. |

### 4.2 Dataset & distributions (P18–P42)

| Rule | Decision on this instance |
|---|---|
| P18 | `dataset_id` `bnetza_vorhabenpunkte_bbplg_2` (type `other`) → `edo:identifier` Identifier node. Dataset IRI minted as `<dmp_id>/dataset:<id>`. |
| P19/P20 | Title, German description 1:1. |
| P21 | `issued` 2027-01-29 → `xsd:date`. |
| P22 | No dataset `type` in this export → omitted (the RDMO-template default was not materialised). |
| P23–P27 | Keywords ×2, `personal_data: yes → true`, `sensitive_data: yes → true` (maDMP yes/no-CV → boolean), quality assurance split into 3 items, preservation statement 1:1. |
| P28 | `security_and_privacy` ("Access authentication" / "Data is public under GeoNutzV.") → **LOST** — no v0.2 target property. Negative check C19 asserts its absence. |
| P29–P34 | Distribution "Storage during the project": `access_url` → `dcat:accessURL`, `data_access open` → `edo:dataAccess`, format **"CSV and JSON" → `text/csv` + `application/json`** (free text → IANA media types, emitted as `http://purl.org/NET/mediatypes/…` IRIs following `data/sample-project.ttl`). |
| P31–P42 | Distribution "Preservation after the project": `data_access open` (given, not derived), `pid_system "doi"` (NB: maDMP JSON carries a **string**, not a list — normalised, F6), `host.title "Own institution"` → `edo:hostedBy edo:Host`, license CC-BY-4.0 with `start_date` 2027-01-29 → `dcterms:license` + `time:hasBeginning`. |
| P30 | No `PIDINST:` fragment in this dataset's description → **no `prov:wasGeneratedBy` link**; the SMS sensor is emitted as a standalone node. Negative check C25 asserts the absence (gap #18). |

### 4.3 SMS (S1–S16)

| Rule | Decision on this instance |
|---|---|
| S6 | Sensor IRI `https://sms.atmohub.kit.edu/devices/67` (SMS API path + EDO base URL). |
| S1–S4 | `short_name` → `dcterms:title`, model FS6002, manufacturer (trailing whitespace normalised), equipment-type URI passthrough (`device_type_name` "Weather station" label dropped — documented loss). |
| S5 | PID → Identifier node, type `handle`. |
| S7–S9 | `smscv:measuredQuantity` (measuredquantities/4/), title "Air temperature", unit units/51/ — URI passthrough, CV *names* dropped (documented loss). |
| S10 | **Datasheet override**: SMS says −80…60 → graph carries **−40.0…80.0** (datasheet is authoritative per CF1-005 / spec open item 7). Negative check C35 asserts the raw SMS value is *not* in the graph. |
| S11/S12 | accuracy/resolution `null` in SMS → datasheet values "±0.3 K @ 25 °C; ±1.0 K over -40…+80 °C" and 0.1. |
| S13–S15 | sampling media / compartment / aggregation-type URI passthrough (`smscv:samplingMedia`, `smscv:compartment`, `edo:aggregationType`). |
| S16 | Property → `sosa:observes` node (type `sosa:ObservableProperty`). |

### 4.4 Translation tables (implemented in `trip.py`)

| Free text (role_template) | RDA maDMP CV (P8) |
|---|---|
| "Responsible for preservation" | `Data Curator` |
| "Responsible for metadata …" | `Data Curator` |
| anything else | `Other` (documented default) |

| Free text (format) | IANA media type (P34) |
|---|---|
| "CSV" | `text/csv` |
| "JSON" | `application/json` |
| "CSV and JSON" | `text/csv`, `application/json` |
| XLS/Excel, NetCDF, PDF, XML | respective media types |

Datasheet overrides (S10–S12) are keyed by measured-quantity URI and currently
cover `smscv:measuredquantities/4/` (air temperature).

## 5. Verification (scenario 3)

After storing, `/projects` is dumped (CONSTRUCT, Turtle), the dump is
**re-uploaded into the named replay graph `<urn:edo:trip:replay>`**, and every
check is evaluated **twice**: against the replay graph (i.e. the dump — what
scenario 3 asks) and against the default graph (the store). Values are compared
at the SPARQL level against values extracted directly from the original JSON
sources, which sidesteps blank-node relabelling during round-trips.

Result of run `20261119-173927`:

* **41/41 checks passed** on both graphs (C01–C40, one count check per repeatable
  field): project title/description/language-default/interval/dmpId, both
  contributions incl. translated roles and mbox, dataset id/title/description/
  issued/keywords×2/personal/sensitive/quality-assurance×3/preservation
  statement, both distributions incl. formats×2/host/license, sensor
  title/model/manufacturer/type/PID, measured property incl. datasheet override
  (and the rejection of the raw SMS range).
* **Negative checks** confirmed the documented losses: no security predicate
  (P28), no `prov:wasGeneratedBy` (P30/gap #18), no contact (P6), no raw SMS
  range values (S10).
* **Triple-count equality**: default graph 78 triples == replay graph 78 triples.

## 6. Findings & open items

| # | Finding | Status |
|---|---|---|
| F1 | `edo:ProjectShape` demands ≥1 `edo:hasContact` (`sh:minCount 1`), but the maDMP export carries no `contact`; faithful P6 behaviour (omit) → SHACL violation. **Decision needed:** relax the shape (contact optional) vs. guarantee a contact in the RDMO export vs. derive contact from a contributor. | Open — the single remaining SHACL violation |
| F2 | `foaf:PersonShape` types `foaf:mbox` as `xsd:anyURI`; an IRI has no datatype, a plain literal has `xsd:string` — both violate. Correct encoding: `mailto:…` as an `xsd:anyURI` **typed literal** (now in `trip.py`). `data/sample-project.ttl` had the same defect and was corrected on 2026-11-19 (now conforms). | Resolved (sample + trip.py) |
| F3 | Title rule: catalogue P1 maps `project/title`; spec §4's example carries the DMP-document title instead. `trip.py` follows the catalogue; harmonise spec §4 / catalogue wording. | Open (documentation) |
| F4 | Namespace inconsistency: `data/sample-project.ttl` uses `sosa:` = `http://www.w3.org/ns/sosa#`, spec §3.1 and the shapes use `…/sosa/`. `trip.py` follows spec/shapes. | Open (documentation) |
| F5 | `dcat:format` encoding: spec §4 shows plain strings ("text/csv"), `sample-project.ttl` and `trip.py` emit `http://purl.org/NET/mediatypes/…` IRIs. | Open (documentation) |
| F6 | maDMP JSON types `pid_system` as a plain string ("doi"), not a list — `trip.py` normalises both. Also `project/title` ("Measurement_02") vs `dmp/title` ("maDMP for Measurement_02") differ in this export. | Handled in code |
| F7 | Only device property 159 is available as a file; device 67 references properties 157–161. Export the remaining property files to cover the full sensor. | Open (data) |

## 7. Related artefacts

* Card: `../../05_Cards/CF2-003.md` (activity log documents the runs)
* Catalogue: `patterns.md` in this directory
* Internal-format spec: `../internal-format/04_P04_S04_internal-format-spec.md`
* Fuseki prototype: `../fuseki-proto/` (+ `tool/README.md` for the CLI,
  incl. the `trip` command)
* Run artifacts: `../fuseki-proto/data/trip/<timestamp>/`
