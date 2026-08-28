from __future__ import annotations

import json
import re
import secrets
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from wsf.protocol import combined_protocol_hash, scientific_config_hashes

RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")


def new_run_id(prefix: str = "run") -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{stamp}-{secrets.token_hex(3)}"


def validate_run_id(run_id: str) -> str:
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("run id must contain only letters, numbers, dots, underscores, or hyphens")
    return run_id


def _git_commit(project_root: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def build_manifest(project_root: Path, run_id: str) -> dict[str, Any]:
    config_hashes = scientific_config_hashes(project_root / "config")
    return {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "git_commit": _git_commit(project_root),
        "config_hashes": config_hashes,
        "protocol_hash": combined_protocol_hash(config_hashes),
    }


def ensure_manifest(project_root: Path, run_id: str) -> tuple[Path, dict[str, Any]]:
    validate_run_id(run_id)
    run_dir = project_root / "artifacts" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = run_dir / "manifest.json"
    candidate = build_manifest(project_root, run_id)
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("protocol_hash") != candidate["protocol_hash"]:
            raise ValueError(f"{run_id}: scientific configuration changed since manifest creation")
        return manifest_path, existing
    manifest_path.write_text(
        json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest_path, candidate
