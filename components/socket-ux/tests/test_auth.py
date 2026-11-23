"""Tests for the RBAC layer (auth.py) and the gated endpoints (UPL-002, option B)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from socket_ux import api, auth
from socket_ux.config import Settings


class RoleSettings(Settings):
    """Settings pointing at nothing real, with an explicit EDO_ROLE."""

    def __init__(self, role: str) -> None:
        super().__init__(fuseki_url="http://fuseki.test", role=role)


def test_parse_role_accepts_the_four_roles():
    for role in auth.ROLES:
        assert auth.parse_role(role) == role
    assert auth.parse_role(" STEWARD ") == "steward"


def test_parse_role_rejects_unknown_values():
    with pytest.raises(ValueError, match="EDO_ROLE"):
        auth.parse_role("superuser")


def test_role_meets_orders_the_lifecycle():
    assert auth.role_meets("guest", "guest")
    assert not auth.role_meets("guest", "fellow")
    assert auth.role_meets("steward", "fellow")
    assert auth.role_meets("admin", "admin")
    assert not auth.role_meets("steward", "admin")


def test_capabilities_for_mirrors_the_matrix():
    assert auth.capabilities_for("guest") == []
    assert "authorCcaDraft" in auth.capabilities_for("fellow")
    assert "depositPublish" not in auth.capabilities_for("fellow")
    assert "depositPublish" in auth.capabilities_for("steward")
    assert "manageSystem" in auth.capabilities_for("admin")
    assert "manageSystem" not in auth.capabilities_for("steward")


def test_unknown_capability_is_a_developer_error():
    with pytest.raises(KeyError):
        auth.require_capability("nonexistent", RoleSettings("admin"))


def test_whoami_reflects_the_configured_role(monkeypatch):
    monkeypatch.setattr(api, "get_settings", lambda: RoleSettings("fellow"))
    client = TestClient(api.app)
    body = client.get("/api/v1/whoami").json()
    assert body["role"] == "fellow"
    assert body["source"] == "EDO_ROLE"
    assert "authorCcaDraft" in body["capabilities"]


def test_bus_diagnostics_require_steward(monkeypatch):
    """fellow < steward: the bus bridge answers 403 naming the required role."""
    monkeypatch.setattr(api, "get_settings", lambda: RoleSettings("fellow"))
    client = TestClient(api.app)

    response = client.get("/api/v1/bus/topics")
    assert response.status_code == 403
    body = response.json()["detail"]
    assert body["code"] == "insufficient_role"
    assert body["required_role"] == "steward"
    assert body["instance_role"] == "fellow"

    assert client.get("/api/v1/bus/status").status_code == 403
    assert client.get("/api/v1/bus/topics/edo.sync.v1/messages").status_code == 403


def test_bus_diagnostics_open_for_steward(monkeypatch):
    monkeypatch.setattr(api, "get_settings", lambda: RoleSettings("steward"))
    client = TestClient(api.app)
    # no broker configured → 503 (offline contract), NOT 403
    assert client.get("/api/v1/bus/topics").status_code == 503
    assert client.get("/api/v1/bus/status").status_code == 200


def test_bus_publish_requires_admin(monkeypatch):
    """steward < admin: publishing to the bus is a system-management action."""
    monkeypatch.setattr(api, "get_settings", lambda: RoleSettings("steward"))
    client = TestClient(api.app)
    body = {"payload": {"event": "test"}, "header": {key: "x" for key in
            ("socket_id", "ontology_uri", "project_id", "schema_id", "timestamp", "lineage")}}
    response = client.post("/api/v1/bus/topics/edo.test.v1/messages", json=body)
    assert response.status_code == 403
    assert response.json()["detail"]["required_role"] == "admin"


def test_bus_publish_open_for_admin(monkeypatch):
    monkeypatch.setattr(api, "get_settings", lambda: RoleSettings("admin"))
    monkeypatch.setattr(api, "_publisher", _StubPublisher())
    client = TestClient(api.app)
    body = {"payload": {"event": "test"}, "header": {key: "x" for key in
            ("socket_id", "ontology_uri", "project_id", "schema_id", "timestamp", "lineage")}}
    response = client.post("/api/v1/bus/topics/edo.test.v1/messages", json=body)
    assert response.status_code == 200
    assert response.json()["published"] is True


def test_read_endpoints_stay_open_for_guest(monkeypatch):
    """Reads are guest-accessible per the matrix — no accidental gating."""
    monkeypatch.setattr(api, "get_settings", lambda: RoleSettings("guest"))
    monkeypatch.setattr(api.fuseki, "list_projects", lambda settings, client: [])
    client = TestClient(api.app)
    assert client.get("/api/v1/projects").status_code == 200
    assert client.get("/api/v1/whoami").status_code == 200


class _StubPublisher:
    def publish(self, *args, **kwargs):
        return True
