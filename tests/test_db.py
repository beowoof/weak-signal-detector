import pytest

from wsf.agent import run_agent
from wsf.db import database_url, desk_health, ping, upsert_heartbeat


def test_database_url_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert database_url() is None
    assert ping() == {"configured": False, "ok": True, "error": None}
    health = desk_health()
    assert health["ok"] is True
    assert health["agent"] is None


def test_database_url_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "  ")
    assert database_url() is None


def test_agent_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="DATABASE_URL"):
        run_agent(interval=0.01)


def test_heartbeat_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="DATABASE_URL"):
        upsert_heartbeat("agent")
