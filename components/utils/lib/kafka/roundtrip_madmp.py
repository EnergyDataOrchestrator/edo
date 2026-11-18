"""CF1-001 round-trip: publish the maDMP first payload onto `edo.dmp.v1`
and consume it back with regimo_core's BusClient.

Verifies the "maDMP round-trip on the bus" acceptance criterion: the JSON
parses, keys are intact, and the ontology-aware headers survive the round trip.

Run from the edo repo root:
    .venv/bin/python components/utils/lib/kafka/roundtrip_madmp.py
Requires the bus to be up:  docker compose up -d zookeeper kafka
"""

import json
import sys
import time
import uuid
from pathlib import Path

from regimo_core.interfaces.message import MessageHeader
from regimo_core.lib.bus import BusClient

BROKER = "localhost:9092"
TOPIC = "edo.dmp.v1"
# First payload: the maDMP rendered/verified in CF1-004.
PAYLOAD_PATH = Path(
    "projecting_spaces/EDO/Artefacts/07_Fragments/scripts/dmp/measurement_02/"
    "Measurement_02.render.json"
)
# Header contract for the publisher (socket provenance / schema pinning).
SOCKET_ID = "socket-rdmo"
ONTOLOGY_URI = "https://github.com/EnergyDataOrchestrator/regimo-ontology"
SCHEMA_ID = "madmp-lightmodel"
PROJECT_ID = "4"


def main() -> int:
    print(f"[1/4] loading payload: {PAYLOAD_PATH}")
    payload = json.loads(PAYLOAD_PATH.read_text(encoding="utf-8"))
    assert "dmp" in payload, "payload must contain a top-level 'dmp' object"
    print(f"      top-level keys: {sorted(payload.keys())}")

    print(f"[2/4] bus client -> {BROKER}, topic '{TOPIC}'")
    # Fresh group per run so 'earliest' reliably reads from the topic start
    # (a previously-committed offset would otherwise be resumed).
    client = BusClient(
        bootstrap_servers=BROKER,
        group_id=f"cf1-001-roundtrip-{uuid.uuid4().hex[:8]}",
    )

    header = MessageHeader.from_time(
        socket_id=SOCKET_ID,
        project_id=PROJECT_ID,
        schema_id=SCHEMA_ID,
        ontology_uri=ONTOLOGY_URI,
        lineage=f"{SOCKET_ID}#{PROJECT_ID} -> madmp-exporter -> {SCHEMA_ID}",
    )

    print("[3/4] publishing maDMP payload")
    client.publish_maDMP(str(PAYLOAD_PATH), header, topic=TOPIC)
    print("      published; waiting for delivery ...")

    # Consume the *newest* message: subscribe only after producing so the
    # group's earliest-offset read starts at the message just written. Give the
    # group time to join and receive a partition assignment.
    client.subscribe([TOPIC], auto_offset_reset="earliest")
    time.sleep(1)

    print("[4/4] consuming back ...")
    msg = None
    matches = 0
    for _ in range(30):
        msg = client.poll()
        if msg is not None:
            matches += 1
            if msg["payload"] == payload:
                break
        time.sleep(0.5)
    print(f"      (topic size {matches} consumed before match)")
    client.close()

    if msg is None:
        print("ERROR: no matching message consumed")
        return 1

    hp = msg["header"].to_dict()
    print("      consumed payload keys:", sorted(msg["payload"].keys()))
    print("      consumed header:")
    for k, v in hp.items():
        print(f"        {k}: {v}")

    # --- assertions -------------------------------------------------------
    ok = True
    if "dmp" not in msg["payload"]:
        ok = False
        print("FAIL: consumed payload lost 'dmp' key")
    if msg["payload"] != payload:
        ok = False
        print("FAIL: consumed payload differs from published payload")

    expected = {
        "socket_id": SOCKET_ID,
        "ontology_uri": ONTOLOGY_URI,
        "schema_id": SCHEMA_ID,
        "project_id": PROJECT_ID,
    }
    for k, v in expected.items():
        if hp.get(k) != v:
            ok = False
            print(f"FAIL: header '{k}' = {hp.get(k)!r}, expected {v!r}")

    print("ROUND-TRIP OK" if ok else "ROUND-TRIP FAILED")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
