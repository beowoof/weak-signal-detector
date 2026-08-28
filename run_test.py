#!/usr/bin/env python3
"""Run a scenario experiment rehearsal and assign one parent experiment run ID.

Default `--mock` is a synthetic rehearsal. Without `--mock`, collection uses live
connectors. The harness never invokes Ollama.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
if __name__ == "__main__" and Path(sys.prefix).resolve() != (PROJECT_ROOT / ".venv").resolve():
    if not VENV_PYTHON.is_file():
        raise SystemExit("project environment missing; run `uv sync --extra dev`")
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])

from wsf.corpus import collect_corpus  # noqa: E402
from wsf.progress import SILENT, Progress  # noqa: E402
from wsf.review import review_corpus  # noqa: E402
from wsf.run import new_run_id, validate_run_id  # noqa: E402
from wsf.scenario import freeze_scenario  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True, help="Scenario identifier.")
    parser.add_argument(
        "--through",
        choices=("collect", "review", "freeze"),
        default="review",
        help="Last lifecycle stage to run (default: review).",
    )
    parser.add_argument("--run-id", help="Explicit parent experiment run id.")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Synthetic collection and fake semantic review. Never scientific evidence.",
    )
    parser.add_argument(
        "--focus",
        type=Path,
        help="Optional missing.json to drive a focused collection revision.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stderr progress lines.",
    )
    return parser.parse_args()


def run_experiment(
    *,
    scenario_id: str,
    through: str,
    run_id: str,
    mock: bool,
    focus: Path | None = None,
    project_root: Path = PROJECT_ROOT,
    progress: Progress | None = None,
) -> tuple[Path, dict[str, Any]]:
    validate_run_id(run_id)
    run_dir = project_root / "artifacts" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    summary: dict[str, Any] = {
        "run_id": run_id,
        "scenario_id": scenario_id,
        "through": through,
        "mode": "synthetic_rehearsal" if mock else "live_harvest",
        "started_at": datetime.now(UTC).isoformat(),
        "scientific_result": False,
    }
    try:
        collection_dir, collection = collect_corpus(
            project_root,
            scenario_id,
            focus_path=focus,
            mock=mock,
            run_id=f"{run_id}-collection",
            progress=progress or SILENT,
        )
        summary["collection"] = {
            "id": collection["collection_id"],
            "directory": str(collection_dir),
        }
        if through in {"review", "freeze"}:
            review_dir, review = review_corpus(
                project_root,
                scenario_id,
                mock_model=mock,
                run_id=f"{run_id}-review",
                progress=progress or SILENT,
            )
            summary["review"] = {
                "id": review["review_id"],
                "directory": str(review_dir),
                "decision": review["decision"],
            }
        if through == "freeze":
            summary["freeze"] = str(
                freeze_scenario(project_root, scenario_id, allow_rehearsal=mock)
            )
        summary["status"] = "completed"
        return run_dir, summary
    except Exception as error:
        summary["status"] = "failed"
        summary["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        summary["finished_at"] = datetime.now(UTC).isoformat()
        _write_summary(run_dir, summary)


def _write_summary(run_dir: Path, summary: dict[str, Any]) -> None:
    (run_dir / "experiment_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        f"# Experiment {summary['run_id']}",
        "",
        f"- Scenario: `{summary['scenario_id']}`",
        f"- Status: **{summary.get('status', 'unknown')}**",
        f"- Mode: `{summary['mode']}`",
        "- Scientific result: **no**",
    ]
    if "review" in summary:
        lines.append(f"- Corpus decision: `{summary['review']['decision']}`")
    if "error" in summary:
        lines.append(f"- Error: `{summary['error']}`")
    (run_dir / "experiment_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    run_id = args.run_id or new_run_id("experiment")
    try:
        run_dir, summary = run_experiment(
            scenario_id=args.scenario,
            through=args.through,
            run_id=run_id,
            mock=args.mock,
            focus=args.focus,
            progress=SILENT if args.quiet else Progress(enabled=True),
        )
    except Exception as error:
        print(f"run_id={run_id}")
        print(f"status=failed: {error}")
        return 1
    print(f"run_id={run_id}")
    print(f"status={summary['status']}")
    print(f"artifacts={run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
