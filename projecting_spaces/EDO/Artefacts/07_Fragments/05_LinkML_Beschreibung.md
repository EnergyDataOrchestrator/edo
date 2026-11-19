# 05 - LinkML Beschreibung

## Ziel

Beispielhafte LinkML-Beschreibungen für den DMP, SMS und das interne Format erstellen (nur grobes Prinzip, sodass man später die Transformation versteht).

## Beschreibung

LinkML (Linked Data Modeling Language) wird verwendet, um die Schemata für alle drei Komponenten formal zu beschreiben:

1. **DMP-Schema** - Struktur des Data Management Plans
2. **SMS-Schema** - Struktur der Sensorbeschreibung
3. **Internes Format Schema** - Struktur des Zwischenformats

## Aufgaben

- [x] LinkML-Schema für DMP erstellen
- [x] LinkML-Schema für SMS erstellen
- [x] LinkML-Schema für internes Format erstellen
- [x] Klassen und Slots definieren
- [x] Datentypen festlegen
- [x] Constraints dokumentieren

## Werkzeuge

- **LinkML** - Linked Data Modeling Language

## Deliverables

- `scripts/linkml/05_P05_S05_madmp-schema.yaml` (10 Klassen, 41 Slots, 4 Enums)
- `scripts/linkml/05_P05_S05_sms-schema.yaml` (2 Klassen, 39 Slots)
- `scripts/linkml/05_P05_S05_internal-format-schema.yaml` (14 Klassen, 57 Slots, 4 Enums)
- `scripts/linkml/05_P05_S05_internal-format.schema.json` (generiertes JSON Schema, 18 `$defs`)
- `scripts/linkml/05_P05_S05_linkml-modelling-decisions.md` (Modellentscheidungen, IRI-Politik, offene Punkte)

## Notizen

- Drei eigenständige Schemas ohne `imports` — die Pivot-Abbildung DMP→intern und SMS→intern passiert in den Transformationen (CF2-003), nicht auf Schema-Ebene.
- IRI-Politik fixiert (lautete aus CF1-006 §6 offen): `edo:` = `https://w3id.org/edo/terms/` Platzhalter; Vokabular-IRIs stehen in `class_uri`/`mappings`. Details siehe Modellentscheidungen-Dokument §2.
- Lektion: LinkML verwirft nicht definierte Top-Level-Slots still (`name`, `mbox`, `url`) — SchemaView läuft durch, erst `jsonschemagen` bricht ab. YAML-Plain-Scalars ohne `: ` schreiben.
- LinkML als Wegwerf-Installation unter `/tmp/linkmllib` (nicht im Projekt-Venv).

---

**Status:** ✅ Erledigt
**Vorheriger Schritt:** [[04_Internes_Format_Beschreibung]]
**Nächster Schritt:** [[06_Transformationen]]
