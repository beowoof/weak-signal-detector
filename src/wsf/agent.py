"""Long-running collection/measure worker. Heartbeats now; jobs and websocket fan-out next."""

from __future__ import annotations

import sys
import time

from wsf.db import database_url, ping, upsert_heartbeat


def run_agent(*, interval: float = 5.0, agent_id: str = "agent") -> None:
    if database_url() is None:
        raise ValueError("DATABASE_URL is required for the agent")
    print(f"wsd agent {agent_id} starting (interval={interval}s)", flush=True)
    while True:
        db = ping()
        if not db["ok"]:
            print(f"wsd agent waiting for database: {db['error']}", file=sys.stderr, flush=True)
        else:
            upsert_heartbeat(agent_id, "idle")
        time.sleep(interval)
