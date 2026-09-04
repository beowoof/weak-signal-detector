from __future__ import annotations

import os
from pathlib import Path


def load_project_env(project_root: Path) -> dict[str, bool]:
    """Load `.env` into os.environ without overriding values already set.

    Returns presence flags only; never returns secret values.
    """
    path = project_root / ".env"
    if path.is_file():
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key:
                os.environ.setdefault(key, value)
    return {
        "FRED_API_KEY": bool(os.environ.get("FRED_API_KEY")),
        "EARTHDATA_TOKEN": bool(os.environ.get("EARTHDATA_TOKEN")),
        "FIRMS_MAP_KEY": bool(os.environ.get("FIRMS_MAP_KEY")),
        "COPERNICUS_CLIENT_ID": bool(os.environ.get("COPERNICUS_CLIENT_ID")),
        "COPERNICUS_CLIENT_SECRET": bool(os.environ.get("COPERNICUS_CLIENT_SECRET")),
        "OPENSKY_TRINO_USER": bool(os.environ.get("OPENSKY_TRINO_USER")),
        "OPENSKY_TRINO_PASSWORD": bool(os.environ.get("OPENSKY_TRINO_PASSWORD")),
        "ICEWS_EVENTS_PATH": bool(os.environ.get("ICEWS_EVENTS_PATH")),
        "GOOGLE_CLOUD_PROJECT": bool(os.environ.get("GOOGLE_CLOUD_PROJECT")),
        "GOOGLE_APPLICATION_CREDENTIALS": bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")),
        "OLLAMA_BASE_URL": bool(os.environ.get("OLLAMA_BASE_URL")),
        "OLLAMA_MODEL": bool(os.environ.get("OLLAMA_MODEL")),
        "TAVILY_API_KEY": bool(os.environ.get("TAVILY_API_KEY")),
    }
