# 01 - Definition low level Beispiel

## Ziel

Entwicklung eines kleinen, überschaubaren Beispiel-Szenarios für eine Messreihe.

## Beschreibung

Im ersten Schritt wird ein konkretes, einfaches Szenario definiert, das als Testfall für den gesamten Workflow dient. Dieses Szenario sollte:

- Klein und überschaubar sein
- Eine typische Messreihe repräsentieren
- Alle notwendigen Komponenten abdecken
- Realistisch, aber nicht zu komplex sein

## Aufgaben

- [x] Szenario auswählen (z.B. Temperaturmessung, Umweltdaten, etc.)
- [x] Messparameter definieren
- [x] Zeitrahmen festlegen
- [x] Beteiligte Systeme identifizieren
- [x] Erwartete Outputs dokumentieren

## Erwartete Outputs

1. **Messreihen-CSV** — Air-Temperature-Messreihe der Weatherstation Q3-2026
   (Sensor PIDINST 21.11157/9b6cdfb9-a4fb-4269-af04-1ef94588f5a8), Zeitraum
   2026-07-01 bis 2026-09-30, kontinuierliche Aufzeichnung mit einem
   Sampling-Intervall von 15 Minuten, Ablage im KIT GitLab.
2. **maDMP-Export** — maschinenlesbares maDMP-JSON aus RDMO
   (http://localhost:8484/projects/6/) via madmp-exporter.
3. **Internes EDO-Format** — aus dem maDMP transformierte projektinterne Repräsentation.
4. **RO-Crate** — Verpackung der CSV + Metadaten als Research Object Crate.
5. **OEP-Beschreibung** — OEMetadata-konforme Beschreibung der Messreihe
   für die Veröffentlichung auf der Open Energy Platform.

## Notizen

- Szenario ist in [IAI / **Measurement_02**](http://localhost:8484/projects/6/) definiert.
- Sensor ist: https://hdl.handle.net/21.11157/9b6cdfb9-a4fb-4269-af04-1ef94588f5a8
- Air temperature - Air Temperature (°C) ist der Messparameter
- Der Output ist eine CSV mit ihrem OEP-BEschreibung

---

**Status:** ✅ Abgeschlossen
**Nächster Schritt:** [[02_DMP_Erstellung]]
