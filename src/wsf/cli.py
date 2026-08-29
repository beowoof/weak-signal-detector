from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import typer

from wsf.corpus import collect_corpus, connector_readiness
from wsf.measure import measure_scenario
from wsf.progress import Progress
from wsf.register import validate_configuration
from wsf.review import review_corpus
from wsf.run import ensure_manifest
from wsf.scenario import (
    create_scenario,
    freeze_scenario,
    load_scenario,
    load_status,
    require_collection_ready,
    scenario_hash,
)

app = typer.Typer(no_args_is_help=True, help="Weak-signal detector research CLI.")
scenario_app = typer.Typer(no_args_is_help=True, help="Create and manage scenarios.")
corpus_app = typer.Typer(no_args_is_help=True, help="Collect and review scenario corpora.")
app.add_typer(scenario_app, name="scenario")
app.add_typer(corpus_app, name="corpus")


def _root() -> Path:
    return Path.cwd()


def _echo(value: dict[str, Any]) -> None:
    typer.echo(json.dumps(value, indent=2, sort_keys=True))


@contextmanager
def _operator_errors() -> Iterator[None]:
    try:
        yield
    except (ValueError, OSError, NotImplementedError) as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(code=1) from None


@app.command()
def doctor() -> None:
    """Validate offline configuration contracts without network or model calls."""
    result = validate_configuration(_root() / "config")
    result["connectors"] = connector_readiness(_root())
    _echo(result)


@app.command("init-run")
def init_run(run_id: str = typer.Option(..., help="Unique immutable run id.")) -> None:
    """Create or verify a run manifest."""
    path, manifest = ensure_manifest(_root(), run_id)
    _echo({"manifest": str(path), "protocol_hash": manifest["protocol_hash"]})


@scenario_app.command("create")
def scenario_create(
    name: str = typer.Option(..., help="Lowercase kebab-case scenario name."),
) -> None:
    """Create an incomplete scenario template for the operator to edit."""
    with _operator_errors():
        directory = create_scenario(_root(), name)
    _echo(
        {
            "scenario": name,
            "directory": str(directory),
            "next": (
                f"edit {directory / 'scenario.json'}, then run "
                f"wsd scenario validate --scenario {name}"
            ),
        }
    )


@scenario_app.command("validate")
def scenario_validate(scenario: str = typer.Option(..., help="Scenario identifier.")) -> None:
    """Validate the schema and confirm that collection inputs are complete."""
    with _operator_errors():
        value = load_scenario(_root(), scenario)
        require_collection_ready(value)
    _echo(
        {
            "scenario": scenario,
            "collection_ready": True,
            "scenario_hash": scenario_hash(value),
        }
    )


@scenario_app.command("status")
def scenario_status(scenario: str = typer.Option(..., help="Scenario identifier.")) -> None:
    """Show the current lifecycle state for a scenario."""
    with _operator_errors():
        status = load_status(_root(), scenario)
    _echo(status)


@scenario_app.command("freeze")
def scenario_freeze(
    scenario: str = typer.Option(..., help="Scenario identifier."),
    allow_rehearsal: bool = typer.Option(
        False, help="Permit a mocked GO candidate to freeze a rehearsal only."
    ),
) -> None:
    """Freeze an accepted corpus revision so downstream analysis can begin."""
    with _operator_errors():
        path = freeze_scenario(_root(), scenario, allow_rehearsal=allow_rehearsal)
    _echo({"scenario": scenario, "freeze": str(path), "status": "frozen"})


@corpus_app.command("collect")
def corpus_collect(
    scenario: str = typer.Option(..., help="Scenario identifier."),
    focus: Path | None = typer.Option(  # noqa: B008
        None, help="missing.json from a previous NO-GO review."
    ),
    mock: bool = typer.Option(
        False, help="Create synthetic engineering data; never scientific evidence."
    ),
    only: str | None = typer.Option(
        None,
        help="Comma-separated source ids to collect (wikipedia,gdelt,alfred,viirs).",
    ),
    run_id: str | None = typer.Option(None, help="Explicit collection run id."),
    quiet: bool = typer.Option(False, help="Suppress stderr progress lines."),
    source_workers: int = typer.Option(
        4,
        help="Max sources to harvest at once. Retries stay inside each source.",
    ),
) -> None:
    """Collect a new corpus revision, optionally focused on declared gaps."""
    selected = [item.strip() for item in only.split(",")] if only else None
    with _operator_errors():
        directory, manifest = collect_corpus(
            _root(),
            scenario,
            focus_path=focus,
            mock=mock,
            run_id=run_id,
            only=selected,
            progress=Progress(enabled=not quiet),
            source_workers=source_workers,
        )
    _echo(
        {
            "scenario": scenario,
            "collection_id": manifest["collection_id"],
            "directory": str(directory),
            "mode": manifest["mode"],
        }
    )


@corpus_app.command("review")
def corpus_review(
    scenario: str = typer.Option(..., help="Scenario identifier."),
    mock_model: bool = typer.Option(
        False, help="Create a fake semantic response for rehearsal; does not call Ollama."
    ),
    run_id: str | None = typer.Option(None, help="Explicit review run id."),
    quiet: bool = typer.Option(False, help="Suppress stderr progress lines."),
) -> None:
    """Run deterministic gates and prepare or mock the semantic balance review."""
    with _operator_errors():
        directory, result = review_corpus(
            _root(),
            scenario,
            mock_model=mock_model,
            run_id=run_id,
            progress=Progress(enabled=not quiet),
        )
    _echo(
        {
            "scenario": scenario,
            "review_id": result["review_id"],
            "decision": result["decision"],
            "directory": str(directory),
            "missing": str(directory / "missing.json"),
        }
    )


@app.command()
def measure(
    scenario: str = typer.Option(..., help="Scenario identifier."),
    run_id: str | None = typer.Option(None, help="Explicit measurement run id."),
    quiet: bool = typer.Option(False, help="Suppress stderr progress lines."),
) -> None:
    """Score the active live harvest. Missing nights are unknown, not quiet."""
    with _operator_errors():
        directory, summary = measure_scenario(
            _root(),
            scenario,
            run_id=run_id,
            progress=Progress(enabled=not quiet),
        )
    _echo(
        {
            "scenario": scenario,
            "measure_id": summary["measure_id"],
            "directory": str(directory),
            "protocol_alerts": len(summary["protocol_alerts"]),
            "exploratory_alerts": len(summary["exploratory_alerts"]),
            "verdict_counts": summary["verdict_counts"],
        }
    )


if __name__ == "__main__":
    app()
