"""Runtime configuration for socket-ux (environment variables)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass
class Settings:
    """socket-ux settings, all overridable via environment variables.

    ``FUSEKI_URL``      — base URL of the internal graph database (Fuseki)
    ``FUSEKI_DATASET``  — dataset holding the internal-format project graphs
    ``FUSEKI_USER``     — basic-auth user for the Fuseki data service
    ``FUSEKI_PASSWORD`` — basic-auth password
    ``KAFKA_BOOTSTRAP_SERVERS`` — databus for ontology-aware events (optional;
                          when unset, events are skipped and only logged)
    ``KAFKA_TOPIC_PATTERN`` — subscription regex of the bridge consumer
                          (default: every ``edo.*`` topic; CF1-012)
    ``BUS_BUFFER_SIZE``   — per-topic ring-buffer capacity of the REST bridge
    ``ONTOLOGY_PATH``   — path to the ontology (regimo.ttl); used for the
                          ``ontology_uri`` message header
    """

    fuseki_url: str = field(default_factory=lambda: _env("FUSEKI_URL", "http://localhost:3031"))
    fuseki_dataset: str = field(default_factory=lambda: _env("FUSEKI_DATASET", "projects"))
    fuseki_user: str = field(default_factory=lambda: _env("FUSEKI_USER", "admin"))
    fuseki_password: str = field(default_factory=lambda: _env("FUSEKI_PASSWORD", "edo-proto"))
    kafka_bootstrap_servers: str = field(default_factory=lambda: _env("KAFKA_BOOTSTRAP_SERVERS"))
    kafka_topic_pattern: str = field(default_factory=lambda: _env("KAFKA_TOPIC_PATTERN", "^edo\\."))
    bus_buffer_size: int = field(default_factory=lambda: int(_env("BUS_BUFFER_SIZE", "100") or 100))
    ontology_path: str = field(default_factory=lambda: _env("ONTOLOGY_PATH"))

    @property
    def dataset_query_url(self) -> str:
        return f"{self.fuseki_url.rstrip('/')}/{self.fuseki_dataset}/query"


def get_settings() -> Settings:
    return Settings()
