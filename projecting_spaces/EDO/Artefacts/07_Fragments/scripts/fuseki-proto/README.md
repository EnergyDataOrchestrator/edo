# fuseki-proto — Apache Jena Fuseki prototype

Prototype for the **Jena / RDF / SHACL path** of the storage decision
(fragment `02_LinkML_Entscheidung` / card `CF2-002`): spin up a triplestore,
load an internal-format instance graph, and validate it against the **project
claim** SHACL shapes.

Choice rationale — this is the "semantically pure" alternative from CF2-002's
*How LinkML Influences the Decision*:
> **Jena (RDF/SPARQL) Path:** If you use Jena, you leverage LinkML's `gen-owl`
> or `gen-shacl` tools … the translation from your schema to RDF is direct,
> and your validation happens via SHACL.

It complements `../trafos/patterns.md` (the SHACL *transformation* patterns)
and the internal-format spec that is its source of truth:
`../internal-format/04_P04_S04_internal-format-spec.md` (§2 entities, §3.2
classes, §3.3 controlled vocabularies) and the LinkML schema from CF1-007
(`../linkml/05_P05_S05_internal-format-schema.yaml`).

## Layout

```
fuseki-proto/
├── docker-compose.yml      # Fuseki 5 (TDB2 + in-memory datasets)
├── config/
│   └── projects-ds.ttl     # dataset assemblers: /projects (TDB2), /shapes (mem)
├── shapes/
│   └── project-claim-shapes.ttl   # SHACL node shapes for a Project claim
└── data/
    └── sample-project.ttl  # spec §4 example translated to Turtle
```

## Run

```bash
docker compose up -d                # http://localhost:3030
```

Two ready-made datasets:
* **`/projects`** — TDB2 (persisted via `fuseki-data` volume); load the sample:
  ```bash
  curl -s -X POST http://admin:edo-proto@localhost:3030/projects/data \
       -H 'Content-Type: text/turtle' \
       --data-binary @data/sample-project.ttl
  ```
* **`/shapes`** — in-memory read side served from `shapes/project-claim-shapes.ttl`.
  Query it: `curl http://localhost:3030/shapes/query?query={...}`.

## Validate the claim

The shapes are self-contained (they do not import external vocabularies), so
the same file drives both the host-side `pyshacl` and the Fuseki `SHACL`
protocol:

```bash
pyshacl -s shapes/project-claim-shapes.ttl \
        -d data/sample-project.ttl \
        -e shapes/project-claim-shapes.ttl
```

Or, against the loaded Fuseki graph, use the Fuseki SHACL validation endpoint:

```bash
curl http://localhost:3030/projects/shacl \
     -H 'Accept: text/turtle' \
     -H 'Content-Type: text/turtle' \
     --data "PREFIX p <http://www.w3.org/ns/shacl#> \
             CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o FILTER(?s = p:ProjectShape) }"
```

## What the claim shapes assert (spec §3.2)

| Shape | Enforces |
|---|---|
| `edo:ProjectShape` | title (req, 1), optional description, `language ∈ {eng,deu}`, one interval w/ dates, exactly-one `dmpId` (typed Identifier), ≥1 contact Person, contributions, costs |
| `time:IntervalShape` | begin (req) + end as `xsd:date` |
| `edo:IdentifierShape` | value (req), type ∈ {doi,handle,ark,urn,url,other} |
| `foaf:PersonShape` | name (req), optional mbox / identifier |
| `edo:ContributionShape` | agent Person (req), role ∈ RDA maDMP contributor-type CV |
| `edo:CostShape` | title (req), optional decimal value + currency |

## Notes / open items

* Shapes cover the **Project claim (top-down)**. Dataset / Distribution /
  Sensor claims remain future work (extend `shapes/` per class when the
  transformation CF2-003 feeds instance data).
* `data/sample-project.ttl` reflects the spec §4 example. The dataset↔sensor
  link is still only in free text (`PIDINST: …`, gap #18); once it becomes a
  typed edge the Dataset/Sensor shapes should assert `prov:wasGeneratedBy`.
* IRIs are placeholders (`urn:` / `edo:`), per spec open item 6 — concrete IRIs
  are fixed by CF1-007 / CF2-004.
