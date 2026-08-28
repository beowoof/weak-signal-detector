#!/usr/bin/env python3
"""Create a run id and execute the project's engineering-test profile.

The default profile is offline and excludes all live-source and model tests.
Expensive model execution is opt-in and must be run by the project owner, not Codex.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def new_test_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"unit-{stamp}-{secrets.token_hex(3)}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", help="Use an explicit run id instead of assigning one.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Include tests marked live. These may access remote source APIs.",
    )
    parser.add_argument(
        "--with-model",
        action="store_true",
        help="Include tests marked model. This may invoke local Ollama and is never used by Codex.",
    )
    return parser.parse_args()


def marker_expression(*, live: bool, with_model: bool) -> str | None:
    excluded = []
    if not live:
        excluded.append("live")
    if not with_model:
        excluded.append("model")
    return " and ".join(f"not {marker}" for marker in excluded) or None


def main() -> int:
    args = parse_args()
    run_id = args.run_id or new_test_run_id()
    run_dir = PROJECT_ROOT / "artifacts" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    expression = marker_expression(live=args.live, with_model=args.with_model)
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if venv_python.is_file():
        command = [str(venv_python), "-m", "pytest"]
    else:
        uv = shutil.which("uv")
        if uv is None:
            raise SystemExit("uv is required for the first run; run `uv sync --extra dev`")
        command = [uv, "run", "--extra", "dev", "pytest"]
    if expression:
        command.extend(["-m", expression])

    started_at = datetime.now(UTC)
    env = os.environ.copy()
    env["WSD_RUN_ID"] = run_id
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    sys.stdout.write(result.stdout)
    (run_dir / "pytest.log").write_text(result.stdout, encoding="utf-8")

    summary = {
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "profile": {
            "live": args.live,
            "with_model": args.with_model,
            "marker_expression": expression,
        },
        "command": command,
        "exit_code": result.returncode,
    }
    (run_dir / "test_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"run_id={run_id}")
    print(f"artifacts={run_dir}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
