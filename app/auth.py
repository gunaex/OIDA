from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from typing import Optional

from fastapi import HTTPException, Request

from .config import settings
from .db import connect, now, transaction

log = logging.getLogger("oida.security")


@dataclass(frozen=True)
class Actor:
    id: str
    email: str
    display_name: str
    actor_type: str = "HUMAN"


def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        _, salt, expected = encoded.split("$", 2)
    except ValueError:
        return False
    actual = hash_password(password, salt).rsplit("$", 1)[1]
    return hmac.compare_digest(actual, expected)


def bootstrap_user() -> None:
    with transaction() as db:
        row = db.execute("SELECT id FROM users WHERE email=?", (settings.bootstrap_email.lower(),)).fetchone()
        if not row:
            db.execute(
                "INSERT INTO users VALUES (?,?,?,?,?,?)",
                (str(uuid.uuid4()), settings.bootstrap_email.lower(), settings.bootstrap_name,
                 hash_password(settings.bootstrap_password), "HUMAN", now()),
            )


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def issue_session(actor_id: str) -> str:
    payload = _encode(json.dumps({"sub": actor_id, "exp": int(time.time()) + 12 * 3600}, separators=(",", ":")).encode())
    sig = _encode(hmac.new(settings.session_secret.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def _decode_session(token: str) -> Optional[str]:
    try:
        payload, sig = token.split(".", 1)
        expected = _encode(hmac.new(settings.session_secret.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected): return None
        raw = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        data = json.loads(raw)
        return data["sub"] if data["exp"] >= time.time() else None
    except Exception:
        return None


def current_actor(request: Request) -> Actor:
    actor_id = _decode_session(request.cookies.get("oida_session", ""))
    if not actor_id:
        log.warning(json.dumps({"action":"AUTHORIZATION_DENIED","actor_id":"ANONYMOUS","result":"BLOCKED_AUTH"}))
        raise HTTPException(401, "Missing or invalid authorization context")
    with connect() as db:
        row = db.execute("SELECT id,email,display_name,actor_type FROM users WHERE id=?", (actor_id,)).fetchone()
    if not row or row["actor_type"] != "HUMAN":
        raise HTTPException(401, "Authorization context is not an active human identity")
    return Actor(**dict(row))


def require_project(actor: Actor, project_id: str, owner: bool = False):
    with connect() as db:
        row = db.execute(
            "SELECT p.*,m.role FROM projects p JOIN project_memberships m ON m.project_id=p.id "
            "WHERE p.id=? AND m.user_id=?", (project_id, actor.id)
        ).fetchone()
    if not row:
        with transaction() as db:
            db.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?,?,?,?,?)", (
                f"aud_{uuid.uuid4().hex}", None, actor.id, actor.actor_type, "PROJECT_ACCESS_DENIED",
                "PROJECT", project_id, "BLOCKED_AUTH", json.dumps({"owner_required": owner}), now()))
        raise HTTPException(404, "Project not found")
    if owner and row["role"] != "PROJECT_OWNER":
        with transaction() as db:
            db.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?,?,?,?,?)", (
                f"aud_{uuid.uuid4().hex}", project_id, actor.id, actor.actor_type, "AUTHORITY_DENIED",
                "REQUIREMENT_BASELINE", project_id, "BLOCKED_AUTH", json.dumps({"required_role":"PROJECT_OWNER"}), now()))
        raise HTTPException(403, "Project owner authority required")
    return row
