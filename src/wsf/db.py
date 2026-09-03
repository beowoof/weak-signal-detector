"""Desk runtime database. Harvests stay on disk; Postgres holds process state."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import psycopg

_HEARTBEAT_STALE_SECONDS = 30


def database_url() -> str | None:
    raw = os.environ.get("DATABASE_URL", "").strip()
    return raw or None


def ping() -> dict[str, Any]:
    url = database_url()
    if url is None:
        return {"configured": False, "ok": True, "error": None}
    try:
        with psycopg.connect(url, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
    except Exception as exc:
        return {"configured": True, "ok": False, "error": str(exc)}
    return {"configured": True, "ok": True, "error": None}


def upsert_heartbeat(agent_id: str, status: str = "idle") -> None:
    url = database_url()
    if url is None:
        raise ValueError("DATABASE_URL is required")
    with psycopg.connect(url) as conn:
        conn.execute(
            """
            INSERT INTO desk.agent_heartbeat (agent_id, seen_at, status)
            VALUES (%s, now(), %s)
            ON CONFLICT (agent_id)
            DO UPDATE SET seen_at = now(), status = EXCLUDED.status
            """,
            (agent_id, status),
        )
        conn.commit()


def latest_heartbeat() -> dict[str, Any] | None:
    url = database_url()
    if url is None:
        return None
    try:
        with psycopg.connect(url, connect_timeout=3) as conn:
            row = conn.execute(
                """
                SELECT agent_id, seen_at, status
                FROM desk.agent_heartbeat
                ORDER BY seen_at DESC
                LIMIT 1
                """
            ).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    seen_at: datetime = row[1]
    if seen_at.tzinfo is None:
        seen_at = seen_at.replace(tzinfo=UTC)
    age = (datetime.now(UTC) - seen_at).total_seconds()
    return {
        "agent_id": row[0],
        "seen_at": seen_at.isoformat(),
        "status": row[2],
        "stale": age > _HEARTBEAT_STALE_SECONDS,
    }


def desk_health() -> dict[str, Any]:
    db = ping()
    return {"ok": bool(db["ok"]), "db": db, "agent": latest_heartbeat()}
