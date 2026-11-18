# maDMP export validation report — project 4 "Measurement_02"

*Run:* 2026-11-18T15:09:51.349482+00:00 · *plugin:* deployed `rdmo_madmp.exports.MaDMPExport` · *mapping:* `03_P03_S03_madmp-export.mapping.yaml`

Artifacts of this run: `Measurement_02-groundtruth.json` (answers), `Measurement_02.render.json` (plugin render), this report.

## Summary

- mapping-spec rows: 62
- `NOT-ANSWERED`: 31
- `OK`: 17
- `PATH-MISSING-IN-CATALOG`: 13
- `RESOLVED-EMPTY`: 1
- answered-but-not-exported values: 27
- structural checks: 19/20 passed
- UI export `Measurement_02-dmp.json` vs. offline render: IDENTICAL

## Traceability matrix (mapping spec -> RDMO -> maDMP)

| location | rdmo path | in catalog | answered | resolved | in output | status |
|---|---|---|---|---|---|---|
| `dmp/title` | `(project title)` |  |  | `maDMP for Measurement_02` | True | **OK** |
| `dmp/created` | `project.created` |  |  | `2026-03-02T09:54:14.726258+00:00` | True | **OK** |
| `dmp/modified` | `project.updated` |  |  | `2026-11-09T12:24:33.927859+00:00` | True | **OK** |
| `dmp/contact/name` | `project/data_management/name` | True | False | `None` | False | **NOT-ANSWERED** |
| `dmp/contact/mbox` | `project/data_management/mbox` | True | False | `None` | False | **NOT-ANSWERED** |
| `dmp/contact/identifier` | `project/data_management/identifier` | False | False | `None` | False | **PATH-MISSING-IN-CATALOG** |
| `dmp/contact/identifier_type` | `project/data_management/identifier_type` | False | False | `None` | False | **PATH-MISSING-IN-CATALOG** |
| `dmp/contributor[0]/name` | `project/dataset/preservation/responsible_person/name` | True | True | `A. Koubaa` | True | **OK** |
| `dmp/contributor[0]/mbox` | `project/dataset/preservation/responsible_person/email` | True | True | `mohamed-anis.koubaa@kit.edu` | True | **OK** |
| `dmp/contributor[0]/identifier` | `project/dataset/preservation/responsible_person/identifier` | False | False | `None` | False | **PATH-MISSING-IN-CATALOG** |
| `dmp/contributor[0]/identifier_type` | `project/dataset/preservation/responsible_person/identifier_type` | False | False | `None` | False | **PATH-MISSING-IN-CATALOG** |
| `dmp/contributor[1]/name (set: project/dataset/id)` | `project/dataset/metadata/responsible_person/name` | True | True | `A. Koubaa` | True | **OK** |
| `dmp/contributor[1]/mbox (set: project/dataset/id)` | `project/dataset/metadata/responsible_person/email` | False | False | `None` | False | **PATH-MISSING-IN-CATALOG** |
| `dmp/contributor[1]/identifier (set: project/dataset/id)` | `project/dataset/metadata/responsible_person/identifier` | False | False | `None` | False | **PATH-MISSING-IN-CATALOG** |
| `dmp/contributor[1]/identifier_type (set: project/dataset/id)` | `project/dataset/metadata/responsible_person/identifier_type` | False | False | `None` | False | **PATH-MISSING-IN-CATALOG** |
| `dmp/cost[0] "Personal costs for data creation"` | `project/costs/creation/personnel` | True | False | `None` | False | **NOT-ANSWERED** |
| `dmp/cost[1] "Non personal costs for data creation"` | `project/costs/creation/non_personnel` | True | False | `None` | False | **NOT-ANSWERED** |
| `dmp/cost[2] "Personal costs for data usage"` | `project/costs/usage/personnel` | True | False | `None` | False | **NOT-ANSWERED** |
| `dmp/cost[3] "Non personal costs for data usage"` | `project/costs/usage/non_personnel` | True | False | `None` | False | **NOT-ANSWERED** |
| `dmp/cost[4] "Personal costs for data storage"` | `project/costs/storage/personnel` | True | False | `None` | False | **NOT-ANSWERED** |
| `dmp/cost[5] "Non personal costs for data storage"` | `project/costs/storage/non_personnel` | True | False | `None` | False | **NOT-ANSWERED** |
| `dmp/cost[6] "Personal costs for metadata curation"` | `project/costs/metadata/personnel` | True | False | `None` | False | **NOT-ANSWERED** |
| `dmp/cost[7] "Non personal costs for metadata curation"` | `project/costs/metadata/non_personnel` | True | False | `None` | False | **NOT-ANSWERED** |
| `dmp/cost[8] "Personal costs for PID curation"` | `project/costs/pid/personnel` | True | False | `None` | False | **NOT-ANSWERED** |
| `dmp/cost[9] "Non personal costs for PID curation"` | `project/costs/pid/non_personnel` | True | False | `None` | False | **NOT-ANSWERED** |
| `dmp/cost[10] "Personal costs for data anonymization"` | `project/costs/sensitive_data/anonymization/personnel` | True | False | `None` | False | **NOT-ANSWERED** |
| `dmp/cost[11] "Non personal costs for data anonymization"` | `project/costs/sensitive_data/anonymization/non_personnel` | True | False | `None` | False | **NOT-ANSWERED** |
| `dmp/cost[12] "Personal costs for data security"` | `project/costs/sensitive_data/security/personnel` | True | False | `None` | False | **NOT-ANSWERED** |
| `dmp/cost[13] "Non personal costs for data security"` | `project/costs/sensitive_data/security/non_personnel` | True | False | `None` | False | **NOT-ANSWERED** |
| `dmp/cost[14] "Personal costs for intellectual property rights"` | `project/costs/ipr/personnel` | True | False | `None` | False | **NOT-ANSWERED** |
| `dmp/cost[15] "Non personal costs for intellectual property rights"` | `project/costs/ipr/non_personnel` | True | False | `None` | False | **NOT-ANSWERED** |
| `dmp/cost[16] "Personal costs for preservation"` | `project/costs/preservation/personnel` | True | False | `None` | False | **NOT-ANSWERED** |
| `dmp/cost[17] "Non personal costs for preservation"` | `project/costs/preservation/non_personnel` | True | False | `None` | False | **NOT-ANSWERED** |
| `dmp/dmp_id/identifier` | `project/dmp/identifier` | False | False | `None` | False | **PATH-MISSING-IN-CATALOG** |
| `dmp/dmp_id/type` | `project/dmp/identifier_type` | False | False | `None` | False | **PATH-MISSING-IN-CATALOG** |
| `dmp/language` | `project/language` | False | False | `None` | False | **PATH-MISSING-IN-CATALOG** |
| `dmp/project/start` | `project/schedule/project_start` | True | True | `2017-01-01` | True | **OK** |
| `dmp/project/end` | `project/schedule/project_end` | True | True | `2017-07-31` | True | **OK** |
| `dmp/project/title` | `project.title` |  |  | `Measurement_02` | True | **OK** |
| `dmp/project/description` | `project.description` |  |  | `Example Measurement, as a child-project of IAI.` | True | **OK** |
| `dataset/fields/data_quality_assurance` | `project/dataset/quality_assurance` | True | False | `None` | False | **NOT-ANSWERED** |
| `dataset/fields/description` | `project/dataset/description` | True | True | `Der Datensatz enthält die Netzausbauvorhaben des Bundesbedar` | True | **OK** |
| `dataset/fields/issued` | `project/dataset/data_publication_date` | True | False | `None` | False | **NOT-ANSWERED** |
| `dataset/fields/keyword` | `project/research_question/keywords` | True | True | `trumph testing ecosystem` | True | **OK** |
| `dataset/fields/language` | `project/dataset/language` | False | False | `None` | False | **PATH-MISSING-IN-CATALOG** |
| `dataset/fields/personal_data` | `project/dataset/sensitive_data/personal_data_yesno/yesno` | True | True | `0` | True | **OK** |
| `dataset/fields/preservation_statement` | `project/dataset/preservation/purpose` | True | False | `None` | False | **NOT-ANSWERED** |
| `dataset/fields/security_and_privacy[0] "Access authentication"` | `project/dataset/preservation/access_authentication` | True | True | `Data is public under GeoNutzV.` | True | **OK** |
| `dataset/fields/sensitive_data` | `project/dataset/sensitive_data/personal_data/bdsg_3_9` | True | False | `None` | False | **NOT-ANSWERED** |
| `dataset/fields/type` | `project/dataset/type` | True | False | `None` | False | **NOT-ANSWERED** |
| `dataset/fields/title_fallback` | `project/dataset/id` | True | True | `bnetza_vorhabenpunkte_bbplg_2` | True | **OK** |
| `dataset/fields/dataset_id/identifier` | `project/dataset/dataset_identifier` | False | False | `None` | False | **PATH-MISSING-IN-CATALOG** |
| `dataset/fields/dataset_id/type` | `project/dataset/dataset_identifier` | False | False | `None` | False | **PATH-MISSING-IN-CATALOG** |
| `dataset/fields/dataset_id/fallback_identifier` | `project/dataset/id` | True | True | `bnetza_vorhabenpunkte_bbplg_2` | True | **OK** |
| `dataset/fields/distribution/during/access_url` | `project/dataset/storage/uri` | True | False | `None` | False | **NOT-ANSWERED** |
| `dataset/fields/distribution/during/data_access` | `project/dataset/sharing/yesno` | True | False | `None` | False | **NOT-ANSWERED** |
| `dataset/fields/distribution/during/format` | `project/dataset/format` | True | True | `CSV and JSON` | True | **OK** |
| `dataset/fields/distribution/after/certified_with` | `project/dataset/preservation/certification` | True | True | `None` | False | **RESOLVED-EMPTY** |
| `dataset/fields/distribution/after/pid_system` | `project/dataset/pids/system` | True | False | `None` | False | **NOT-ANSWERED** |
| `dataset/fields/distribution/after/host` | `project/dataset/preservation/repository` | True | False | `None` | False | **NOT-ANSWERED** |
| `dataset/fields/distribution/after/license_ref` | `project/dataset/sharing/conditions` | True | False | `None` | False | **NOT-ANSWERED** |
| `dataset/fields/distribution/after/license_start_date` | `project/dataset/data_publication_date` | True | False | `None` | False | **NOT-ANSWERED** |

## Answered but not exported (candidate gaps)

| attribute | set_index | text | note |
|---|---|---|---|
| `project/coordination/name` | 0 | Institute for Automation and Applied Informatics | no mapping spec (not part of the maDMP export) |
| `project/dataset/creation_methods` | 0 | Bundesnetzagentur (BNetzA) BBPlG network expansion variant 2 data extraction pip | no mapping spec (not part of the maDMP export) |
| `project/dataset/data_analysis_start` | 0 | 2017-06-13 | no mapping spec (not part of the maDMP export) |
| `project/dataset/data_cleansing_end` | 0 | 2017-06-13 | no mapping spec (not part of the maDMP export) |
| `project/dataset/data_cleansing_start` | 0 | 2017-06-01 | no mapping spec (not part of the maDMP export) |
| `project/dataset/data_collection_end` | 0 | 2017-03-31 | no mapping spec (not part of the maDMP export) |
| `project/dataset/interoperability` | 0 | Available on Open trumph testing ecosystem Platform | no mapping spec (not part of the maDMP export) | option uri_path not in option map |
| `project/dataset/metadata/standards` | 0 | OEMETADATA Standard | no mapping spec (not part of the maDMP export) | option uri_path not in option map |
| `project/dataset/metadata/standards` | 0 | Open trumph testing ecosystem Ontology | no mapping spec (not part of the maDMP export) | option uri_path not in option map |
| `project/dataset/origin` | 0 | Bundesnetzagentur (BNetzA) | no mapping spec (not part of the maDMP export) | option uri_path not in option map |
| `project/dataset/preservation/embargo_period` | 0 | No. Data is available without embargo. | no mapping spec (not part of the maDMP export) |
| `project/dataset/reproducibility` | 0 | Fully reproducible via official BNetzA sources[cite: 2] and OEMETADATA specifica | no mapping spec (not part of the maDMP export) | option uri_path not in option map |
| `project/dataset/reuse_scenario` | 0 | Data are open to be reused under GeoNutzV[cite: 2]. No PII are published. | no mapping spec (not part of the maDMP export) |
| `project/dataset/reuse_scenario_usage` | 0 | Research and analysis on power grid expansion projects in Germany. | no mapping spec (not part of the maDMP export) |
| `project/dataset/size/volume` | 0 | 2 MBits | no mapping spec (not part of the maDMP export) | option uri_path not in option map |
| `project/dataset/storage/type` | 0 | GitLab. | no mapping spec (not part of the maDMP export) |
| `project/dataset/usage_description` | 0 | BBPlG power line project point dataset and metadata schema (variant 2) for trump | no mapping spec (not part of the maDMP export) |
| `project/dataset/usage_support` | 0 | No | no mapping spec (not part of the maDMP export) | option uri_path not in option map |
| `project/dataset/usage_technology` | 0 | Python pandas and OEMETADATA specification. | no mapping spec (not part of the maDMP export) |
| `project/dataset/versioning_strategy` | 0 | Internal GitLab (KIT) | no mapping spec (not part of the maDMP export) |
| `project/dataset/versioning_tool` | 0 | KIT GitLab | no mapping spec (not part of the maDMP export) | option uri_path not in option map |
| `project/funder/id` | 0 | HMC | no mapping spec (not part of the maDMP export) |
| `project/funder/name` | 0 | Helmholtz Metadata Collaboration | no mapping spec (not part of the maDMP export) |
| `project/funder/rdm_policy` | 0 | German Research Foundation (DFG). | no mapping spec (not part of the maDMP export) |
| `project/preservation/selection_criteria` | 0 | Publication under GeoNutzV standards. | no mapping spec (not part of the maDMP export) |
| `project/research_field/title` | 0 | trumph testing ecosystem Infrastructure | no mapping spec (not part of the maDMP export) | option uri_path not in option map |
| `project/research_question/title` | 0 | Analysis of BNetzA power line project points (variant 2) under BBPlG[cite: 2]. | no mapping spec (not part of the maDMP export) |

## Structural checks (madmp-lightmodel conformance)

| check | ok | detail |
|---|---|---|
| tree root object has "dmp" | ✅ |  |
| dmp/title required and non-empty | ✅ |  |
| dmp/created is ISO-8601 timestamp | ✅ | 2026-03-02T09:54:14.726258+00:00 |
| dmp/modified is ISO-8601 timestamp | ✅ | 2026-11-09T12:24:33.927859+00:00 |
| dmp/contributor is a list (if present) | ✅ |  |
| dmp/contributor[0] has name (str) | ✅ |  |
| dmp/contributor[0].role is list of str | ✅ |  |
| dmp/contributor[1] has name (str) | ✅ |  |
| dmp/contributor[1].role is list of str | ✅ |  |
| dmp/dataset is a list | ✅ |  |
| dmp/dataset[0] has title (str) | ✅ |  |
| dmp/dataset[0].personal_data in ['no', 'unknown', 'yes'] | ✅ | no |
| dmp/dataset[0].sensitive_data in ['no', 'unknown', 'yes'] | ✅ | unknown |
| dmp/dataset[0].dataset_id has identifier (str) | ✅ |  |
| dmp/dataset[0].dataset_id.type present | ✅ | other |
| dmp/dataset[0].distribution is a list | ✅ |  |
| dmp/dataset[0].distribution[0] has title (str) | ✅ |  |
| dmp/dataset[0].distribution[0].data_access in open|shared|closed|external | ❌ | None |
| dmp/dataset[0].distribution[1] has title (str) | ✅ |  |
| dmp/dataset[0].distribution[1].data_access in open|shared|closed|external | ✅ | closed |

Note: the plugin emits the full RDA maDMP shape (contributor, cost, project, …); `madmp-lightmodel.yaml` is the EDO target subset, so unknown top-level keys are expected and not flagged here.