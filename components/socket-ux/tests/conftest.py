"""Shared fixtures: the internal-format linked DMP+SMS example (CF2-003/CF2-005)."""

from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).parent / "data"

PROJECT_IRI = "urn:uuid:d9e575a1-0671-5f6e-9d2e-3f7e3f2f2a91"
DATASET_ID = "edo:dataset:weatherstation-q3-2026"
SENSOR_ID = "https://sms.atmohub.kit.edu/devices/67"


def linked_instance() -> dict:
    """Compact internal-format document (linked DMP + SMS weather station)."""
    return json.loads((DATA / "linked-instance.example.json").read_text())
