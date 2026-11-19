# 03 - SMS Beschreibung

## Ziel

Benutzung eines in SMS beschriebenen Sensors.

## Beschreibung

Der im Szenario verwendete Sensor wird mithilfe von SMS (Sensor Metadata Standard oder ähnliches) formal beschrieben. Diese Beschreibung ermöglicht die maschinelle Interpretation der Sensoreigenschaften und Messdaten.

## Aufgaben

- [x] Sensor identifizieren
- [x] SMS-Schema recherchieren
- [x] Sensor-Eigenschaften dokumentieren
- [x] Messparameter definieren
- [x] Einheit und Genauigkeit spezifizieren
- [x] SMS-Beschreibung erstellen

## Werkzeuge

- **SMS** - Helmholtz Sensor Management System, Instanz KIT AtmoHub
  (https://sms.atmohub.kit.edu, API: https://sms.atmohub.kit.edu/backend/api/v1/)
- **SMS Controlled Vocabulary** - https://sms-cv.helmholtz.cloud/sms/cv/api/v1/
- **B2INST (EUDAT)** - Instrumenten-PID: https://hdl.handle.net/21.11157/9b6cdfb9-a4fb-4269-af04-1ef94588f5a8

## Deliverables

- Formale Sensorbeschreibung im SMS-Format
	- `scripts/sms/device-67.json` (vollständiger SMS-API-Datensatz, JSON:API)
	- `scripts/sms/device-67-property-159-air-temperature.json` (Messgröße Lufttemperatur)
- Dokumentation der Sensorparameter
	- `scripts/sms/03_P03_S03_sms-sensor-description.md`
	- Messgröße Lufttemperatur: Einheit °C (CV: measuredquantities/4, units/51),
	  Messbereich gemäß Datenblatt −40 … +80 °C, Genauigkeit ±0.3 K @ 25 °C
	  (±1.0 K über den Gesamtbereich), Auflösung 0.1 K (Quelle: Bedienungsanleitung
	  FS6002, im SMS als Attachment 395 hinterlegt)

## Notizen

- Der Sensor ist im SMS (KIT AtmoHub) bereits als Device 67 registriert —
  die „formale SMS-Beschreibung“ existiert dort maschinenlesbar und wurde
  zusätzlich als JSON-Auszug in `scripts/sms/` konserviert.
- Das Datenblatt (Attachment 395 im SMS) liefert die technische Autorität für
  Messbereich, Genauigkeit und Auflösung; im SMS sind Accuracy/Resolution
  derzeit nicht befüllt (`null`).
- ⚠️ Diskrepanz: Messbereich im SMS-Eintrag (−80 … 60 °C) weicht vom Datenblatt
  (−40 … +80 °C) ab. Datenblatt gilt als Autorität; Korrektur des SMS-Eintrags
  ist empfohlen.

---

**Status:** ✅ Abgeschlossen
**Vorheriger Schritt:** [[02_DMP_Erstellung]]
**Nächster Schritt:** [[04_Internes_Format_Beschreibung]]
