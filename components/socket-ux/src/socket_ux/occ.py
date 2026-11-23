"""Optimistic concurrency control (UPL-001): revision tokens per editable slice.

Token format (``frontend/vue-frontend/docs/uplift/SPEC-bounded-contexts-and-ui.md``
§3): ``rev:<seq>:sha256:<64-hex>`` — ``seq`` is a monotonic per-slice revision
counter, the digest is a SHA-256 over the canonical JSON of the slice content.

Slices observed today (read side; the write path is a later card step):

* ``adp:values:<pid>``  — the internal-format document of one project
* ``fep:crate:<pid>``   — the RO-Crate metadata served to NovaCrate

A token advances whenever the observed content digest changes — whoever changed
the underlying state (the regimo-core sync engine today) is the implicit actor.
Tokens survive restarts when ``SOCKET_UX_OCC_STATE_FILE`` points at a writable
file: the state is loaded on first use and saved atomically on every advance,
so pre-restart ``If-Match`` tokens keep resolving (card acceptance criterion).
Without the setting the store is in-memory only (per-process, test/dev mode).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

TOKEN_PREFIX = "rev:"
STATE_VERSION = 1


@dataclass(frozen=True)
class RevisionToken:
    seq: int
    digest: str

    def __str__(self) -> str:
        return f"{TOKEN_PREFIX}{self.seq}:sha256:{self.digest}"


def canonical_digest(content: Any) -> str:
    """SHA-256 over the canonical JSON encoding of ``content``."""
    canonical = json.dumps(
        content, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def parse_token(token: str) -> RevisionToken | None:
    """Parse ``rev:<seq>:sha256:<64-hex>``; ``None`` when malformed."""
    if not token.startswith(TOKEN_PREFIX):
        return None
    parts = token[len(TOKEN_PREFIX):].split(":")
    if len(parts) != 3 or parts[1] != "sha256":
        return None
    try:
        seq = int(parts[0])
    except ValueError:
        return None
    digest = parts[2].lower()
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        return None
    return RevisionToken(seq=seq, digest=digest)


class TokenStore:
    """Per-slice revision tokens, optional file-backed for restart safety."""

    def __init__(self, state_file: str | None = None) -> None:
        self._state_file = state_file or ""
        self._lock = threading.Lock()
        # scope -> {"seq": int, "digest": hex}
        self._scopes: dict[str, dict[str, Any]] = {}
        self._load()

    # -- persistence -----------------------------------------------------------

    def _load(self) -> None:
        if not self._state_file or not os.path.exists(self._state_file):
            return
        try:
            with open(self._state_file, encoding="utf-8") as fh:
                state = json.load(fh)
            scopes = state.get("scopes")
            if state.get("version") == STATE_VERSION and isinstance(scopes, dict):
                self._scopes = scopes
        except (OSError, ValueError):
            # A corrupt state file must not take the socket down; tokens
            # restart at seq 1 and stale If-Match tokens fail closed (409).
            self._scopes = {}

    def _save(self) -> None:
        if not self._state_file:
            return
        directory = os.path.dirname(self._state_file)
        if directory:
            os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory or ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(
                    {"version": STATE_VERSION, "scopes": self._scopes},
                    fh, sort_keys=True,
                )
            os.replace(tmp, self._state_file)
        except OSError:
            # Best effort: in-memory tokens stay valid even if the disk write
            # fails (read-only volume, full disk). Restart safety degrades.
            with contextlib.suppress(OSError):
                os.unlink(tmp)

    # -- token operations --------------------------------------------------------

    def observe(self, scope: str, content: Any, actor: str | None = None) -> RevisionToken:
        """Token for ``content``; advances the sequence when the digest changed."""
        digest = canonical_digest(content)
        with self._lock:
            current = self._scopes.get(scope)
            if current is not None and current.get("digest") == digest:
                return RevisionToken(seq=current["seq"], digest=digest)
            seq = (current["seq"] + 1) if current else 1
            self._scopes[scope] = self._entry(seq, digest, actor)
            self._save()
            return RevisionToken(seq=seq, digest=digest)

    def commit(
        self, scope: str, content: Any, if_match: str,
        actor: str | None = None,
    ) -> tuple[RevisionToken, dict[str, Any] | None]:
        """Committed write under optimistic concurrency (UPL-001 step 3).

        Validates ``if_match`` against the *current* token of the scope. On
        match the token advances and the new one is returned; on mismatch a
        conflict payload is returned (``(current, conflict)``) for the caller
        to turn into a ``409`` — no write happened.
        """
        digest = canonical_digest(content)
        with self._lock:
            current = self._scopes.get(scope)
            current_token = (
                RevisionToken(seq=current["seq"], digest=current["digest"])
                if current else None
            )
            if current_token is None or str(current_token) != if_match:
                conflict = {
                    "current_revision_token": str(current_token) if current_token else None,
                    "current_digest_sha256": current_token.digest if current_token else None,
                    "updated_at": current.get("updated_at") if current else None,
                    "updated_by": current.get("actor") if current else None,
                }
                return current_token or RevisionToken(seq=0, digest=digest), conflict
            seq = current["seq"] + 1
            self._scopes[scope] = self._entry(seq, digest, actor)
            self._save()
            return RevisionToken(seq=seq, digest=digest), None

    @staticmethod
    def _entry(seq: int, digest: str, actor: str | None) -> dict[str, Any]:
        return {
            "seq": seq,
            "digest": digest,
            "actor": actor,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    def current(self, scope: str) -> RevisionToken | None:
        """The last observed token of a scope, without observing new content."""
        with self._lock:
            current = self._scopes.get(scope)
            if current is None:
                return None
            return RevisionToken(seq=current["seq"], digest=current["digest"])


def diff_documents(mine: Any, theirs: Any) -> list[dict[str, Any]]:
    """Field-level conflict list between a client draft and the server record.

    Pragmatic shallow diff for the 409 payload: top-level keys are compared by
    canonical digest; ``@graph`` is compared node-by-node (keyed by ``@id``).
    Each conflict carries both sides so the UI can offer keep-mine/keep-theirs
    per item; absent sides are ``None``.
    """
    conflicts: list[dict[str, Any]] = []
    if not isinstance(mine, dict) or not isinstance(theirs, dict):
        if canonical_digest(mine) != canonical_digest(theirs):
            return [{"field": "(document)", "mine": mine, "theirs": theirs}]
        return []

    mine_graph = mine.get("@graph") if isinstance(mine.get("@graph"), list) else None
    theirs_graph = theirs.get("@graph") if isinstance(theirs.get("@graph"), list) else None
    if mine_graph is not None or theirs_graph is not None:
        mine_nodes = {n.get("@id", f"#{i}"): n for i, n in enumerate(mine_graph or [])}
        theirs_nodes = {n.get("@id", f"#{i}"): n for i, n in enumerate(theirs_graph or [])}
        for node_id in sorted(set(mine_nodes) | set(theirs_nodes)):
            m = mine_nodes.get(node_id)
            t = theirs_nodes.get(node_id)
            if m is not None and t is not None and canonical_digest(m) == canonical_digest(t):
                continue
            conflicts.append({
                "field": f"@graph/{node_id}", "mine": m, "theirs": t,
            })

    for key in sorted(set(mine) | set(theirs)):
        if key == "@graph":
            continue
        m, t = mine.get(key), theirs.get(key)
        if key not in mine or key not in theirs or canonical_digest(m) != canonical_digest(t):
            conflicts.append({"field": key, "mine": m if key in mine else None,
                              "theirs": t if key in theirs else None})
    return conflicts
