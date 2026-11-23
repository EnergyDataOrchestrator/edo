"""RBAC for socket-ux — the server-side gate (card UPL-002, option B).

Every socket-ux instance serves under exactly one role (``EDO_ROLE``).
Requests exercising a capability above that role are answered ``403`` with the
required role named in the body — the UI capability matrix
(``vue-frontend/src/lib/capabilities.ts``) is UX only and must mirror this
map; here is the real enforcement.

Role transport (staged decision in UPL-002): the role is configured per
instance, not per user. Option A (OIDC/JWT claims) replaces the source later —
the capability checks stay unchanged. Interim default in code is ``guest``
(safe); the dev compose sets ``EDO_ROLE=steward`` to keep today's frictionless
single-user behaviour.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import HTTPException

Role = Literal["guest", "fellow", "steward", "admin"]

ROLES: tuple[str, ...] = ("guest", "fellow", "steward", "admin")

ROLE_RANK: dict[str, int] = {"guest": 0, "fellow": 1, "steward": 2, "admin": 3}

# Minimum role per capability — mirror of the frontend RBAC matrix (SPEC §RBAC,
# UPL-002). Capabilities without a socket-ux endpoint yet are kept here so new
# endpoints reuse the same map instead of inventing their own rules.
MIN_ROLE: dict[str, Role] = {
    "triggerAdpSync": "steward",
    "authorCcaDraft": "fellow",
    "confirmCcaMapping": "steward",
    "runEpeVerification": "fellow",  # fellow = view + test runs; steward = full
    "runShaclValidation": "fellow",
    "editCrate": "fellow",
    "depositPublish": "steward",
    "viewDiagnostics": "steward",  # bus/socket diagnostics, read-only below admin
    "manageSystem": "admin",
}


def parse_role(value: str) -> Role:
    """Validate a configured role; unknown values fail fast with a clear message."""
    role = (value or "").strip().lower()
    if role not in ROLE_RANK:
        raise ValueError(
            f"EDO_ROLE: unknown role {value!r} (valid: {', '.join(ROLES)})")
    return role  # type: ignore[return-value]


def role_meets(role: str, min_role: str) -> bool:
    """True when ``role`` sits at or above ``min_role`` (guest < fellow < steward < admin)."""
    return ROLE_RANK[role] >= ROLE_RANK[min_role]


def capabilities_for(role: str) -> list[str]:
    """The capability keys the given role may exercise (for ``/api/v1/whoami``)."""
    return [cap for cap, min_role in MIN_ROLE.items() if role_meets(role, min_role)]


def instance_role(settings: Any) -> Role:
    """The role this instance serves under (``settings.role`` from ``EDO_ROLE``)."""
    return parse_role(settings.role)


def require_capability(capability: str, settings: Any) -> None:
    """Enforce one capability against the instance role.

    Raises ``403`` with ``{code, required_role, instance_role, capability}``
    when the capability exceeds the instance role — the contract the frontend
    (and later EdoClient) parses to explain the blocked action.
    """
    min_role = MIN_ROLE.get(capability)
    if min_role is None:  # pragma: no cover — developer error, not a runtime path
        raise KeyError(f"unknown capability {capability!r} (valid: {', '.join(MIN_ROLE)})")
    role = instance_role(settings)
    if not role_meets(role, min_role):
        raise HTTPException(status_code=403, detail={
            "code": "insufficient_role",
            "capability": capability,
            "required_role": min_role,
            "instance_role": role,
        })
