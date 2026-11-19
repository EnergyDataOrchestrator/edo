# 04 - Internes Format Beschreibung

## Ziel

Grobe Beschreibung eines möglichen internen Formats.

## Beschreibung

Es wird ein internes Datenformat definiert, das als Zwischenschicht zwischen den verschiedenen Quellen (DMP, SMS) und dem Zielformat (RO Crate) dient. Dieses Format sollte alle relevanten Informationen aufnehmen können.

## Aufgaben

- [x] Anforderungen an das interne Format sammeln
- [x] Datenstruktur entwerfen
- [x] Felder und Typen definieren
- [x] Beziehungen zwischen Entitäten modellieren
- [x] Format-Spezifikation dokumentieren

## Überlegungen

- Welche Informationen aus DMP müssen abgebildet werden?
- Welche Informationen aus SMS müssen abgebildet werden?
- Wie werden Verknüpfungen dargestellt?
- Ist das Format erweiterbar für das High-Level-Beispiel?

## Deliverables

- Spezifikation des internen Formats
	- `scripts/internal-format/04_P04_S04_internal-format-spec.md` (Draft v0.1:
	  Anforderungen, Entitätsmodell, Vokabular mit Klassen/Properties/CVs,
	  Beispiel-Instanz, RDF-star-Ausblick, offene Punkte)
- Beispiel-Instanzen
	- Weatherstation-Szenario (DMP + SMS kombiniert) in der Spezifikation, §4

## Notizen

- Draft v0.1 der Spezifikation liegt in
  `scripts/internal-format/04_P04_S04_internal-format-spec.md`; Anforderungs-
  basis sind das maDMP-Export-Mapping (DMP-Seite), die SMS-Datensätze
  (device 67 + properties, CF1-005) und die Ziele RO-Crate/JSON-LD/RDF-star.
- Vokabular-Prinzip: existierende URIs wiederverwenden (dcterms, dcat, foaf,
  prov, sosa, SMS-CV, RDA-maDMP-CV); neue `edo:`-URIs nur für EDO-spezifische
  Konzepte (MeasurementSeries, SamplingPlan, Contribution, Cost).
- Zwei zentrale Lücken dokumentiert: Sampling-Intervall/Messreihen-Zeitfenster
  und die Dataset↔Sensor-Verknüpfung sind in keiner Quelle maschinell abgelegt.
- Review der Draft-Version steht aus (Entscheidungen: Rolle-CV, Formate als
  Media-Types, Serialisierung, IRI-Policy).
- **2026-11-19 — Entscheidungen des Reviewers eingearbeitet (v0.2):**
  Beiträger-Rollen = RDA-maDMP-contributor-type-CV (DataCite-Typen; Übersetzung
  der `role_template`-Freitexte in CF2-003), Formate = IANA-Media-Types
  (`text/csv`), Serialisierung = JSON-LD-kompatibles JSON, Quelle für
  Sampling-Intervall/Zeitfenster = RDMO-Fragen (katalog-Extension, dadurch
  Register-Einträge #16/#17 in `scripts/dmp/05_P05_S05_madmp-catalog-gaps.md`)
  oder ELN. Weiter offen: Dataset↔Sensor-Verknüpfung (Register-Eintrag?),
  IRI-Policy (CF1-007).
- **2026-11-19 — abgeschlossen:** Per Nutzerentscheidung werden die
  RDMO-Katalog-Lücken zusammengefasst in **CF2-001** (Entwicklung eines neuen
  Katalogs/Fragebogens für RDMO) und **CF2-002** behandelt; die
  Dataset↔Sensor-Verknüpfung wurde dafür als Register-Eintrag #18 aufgenommen
  (interim: SMS-Geräte-PID). Fragment ✅, Card CF1-006 → Done.

---

**Status:** ✅ Abgeschlossen
**Vorheriger Schritt:** [[03_SMS_Beschreibung]]
**Nächster Schritt:** [[05_LinkML_Beschreibung]]
