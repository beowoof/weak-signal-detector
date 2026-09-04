from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import typer

from wsf.agent import run_agent
from wsf.brief_pdf import render_existing_packet
from wsf.collect import ALL_KINDS, HARVEST_KINDS, run_collection
from wsf.connectors.viirs import prune_viirs_cache
from wsf.corpus import collect_corpus, connector_readiness
from wsf.measure import measure_scenario
from wsf.notice import (
    apply_notice_action,
    emit_notices_for_measurement,
    list_notices,
    load_notice,
)
from wsf.packet import build_and_save
from wsf.progress import Progress, load_collect_progress
from wsf.register import validate_configuration
from wsf.report import load_report, save_report
from wsf.review import review_allows_cache_prune, review_corpus
from wsf.run import ensure_manifest
from wsf.scenario import (
    create_scenario,
    freeze_scenario,
    load_scenario,
    load_status,
    prepare_scenario_workspace,
    require_collection_ready,
    scenario_hash,
)

app = typer.Typer(no_args_is_help=True, help="Weak-signal detector research CLI.")
scenario_app = typer.Typer(no_args_is_help=True, help="Create and manage scenarios.")
corpus_app = typer.Typer(no_args_is_help=True, help="Collect and review scenario corpora.")
notice_app = typer.Typer(no_args_is_help=True, help="Emit and list collection-cue notices.")
packet_app = typer.Typer(no_args_is_help=True, help="Build cutoff-safe evidence packets.")
agent_app = typer.Typer(no_args_is_help=True, help="Long-running collection/measure worker.")
app.add_typer(scenario_app, name="scenario")
app.add_typer(corpus_app, name="corpus")
app.add_typer(notice_app, name="notice")
app.add_typer(packet_app, name="packet")
app.add_typer(agent_app, name="agent")


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
        prepare_scenario_workspace(_root(), scenario)
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


@corpus_app.command("prune-viirs")
def corpus_prune_viirs(
    scenario: str = typer.Option(..., help="Scenario whose review must have passed."),
    force: bool = typer.Option(
        False, help="Delete even if review has not passed. Do not use during a harvest."
    ),
) -> None:
    """Delete cached VIIRS HDF5 after a passing corpus review. JSONL is unchanged."""
    with _operator_errors():
        root = _root()
        live = load_collect_progress(root).get("active")
        if live and not live.get("stale"):
            raise ValueError(
                "a corpus harvest is running; do not prune VIIRS cache until it finishes"
            )
        ok, reason = review_allows_cache_prune(root, scenario)
        if not ok and not force:
            raise ValueError(
                f"{reason}. Pass `wsd corpus review --scenario {scenario}` first, "
                "or pass --force after you are sure."
            )
        result = prune_viirs_cache(root / "data" / "raw" / "viirs")
    _echo(
        {
            "scenario": scenario,
            "review": reason if ok else f"forced ({reason})",
            "files": result["files"],
            "bytes": result["bytes"],
            "freed": f"{result['bytes'] / 1_000_000_000:.1f}GB",
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
    exploratory: bool = typer.Option(
        False,
        help="Allow measurement before a real corpus GO/freeze; output is non-scientific.",
    ),
    quiet: bool = typer.Option(False, help="Suppress stderr progress lines."),
) -> None:
    """Score the active live harvest, enforcing frozen versus exploratory status."""
    with _operator_errors():
        directory, summary = measure_scenario(
            _root(),
            scenario,
            run_id=run_id,
            exploratory=exploratory,
            progress=Progress(enabled=not quiet),
        )
    _echo(
        {
            "scenario": scenario,
            "measure_id": summary["measure_id"],
            "directory": str(directory),
            "measurement_mode": summary["measurement_mode"],
            "scientific_result": summary["scientific_result"],
            "protocol_alerts": len(summary["protocol_alerts"]),
            "exploratory_alerts": len(summary["exploratory_alerts"]),
            "amber_alerts": summary.get("amber_alerts"),
            "rhythm_alerts": len(summary.get("rhythm_alerts") or []),
            "verdict_counts": summary["verdict_counts"],
            "rhythm_verdict_counts": summary.get("rhythm_verdict_counts"),
            "permutation": summary.get("permutation"),
        }
    )


@notice_app.command("emit")
def notice_emit(
    scenario: str = typer.Option(..., help="Scenario identifier."),
    measure_id: str | None = typer.Option(None, help="Measurement id; default is active."),
    policy: str | None = typer.Option(
        None, help="Notice policy id; default is coupling_k3_z15_p3."
    ),
) -> None:
    """Persist K≥3 coupling episodes as immutable notices. Does not rewrite existing triggers."""
    with _operator_errors():
        notices = emit_notices_for_measurement(
            _root(), scenario, measurement_id=measure_id, policy_id=policy
        )
    _echo(
        {
            "scenario": scenario,
            "n_notices": len(notices),
            "notices": [
                {
                    "notice_id": item.notice_id,
                    "window_id": item.trigger.window_id,
                    "start": item.trigger.start.isoformat(),
                    "end": item.trigger.end.isoformat(),
                    "days_before_window_end": item.trigger.days_before_window_end,
                    "domains": item.trigger.contributing_domains,
                    "posture": item.trigger.recommended_posture.value,
                    "state": item.workflow.state.value,
                }
                for item in notices
            ],
        }
    )


@notice_app.command("list")
def notice_list(scenario: str = typer.Option(..., help="Scenario identifier.")) -> None:
    """List persisted notices for a scenario."""
    with _operator_errors():
        notices = list_notices(_root(), scenario)
    _echo(
        {
            "scenario": scenario,
            "n_notices": len(notices),
            "notices": [
                {
                    "notice_id": item.notice_id,
                    "window_id": item.trigger.window_id,
                    "start": item.trigger.start.isoformat(),
                    "end": item.trigger.end.isoformat(),
                    "state": item.workflow.state.value,
                }
                for item in notices
            ],
        }
    )


@notice_app.command("act")
def notice_act(
    scenario: str = typer.Option(..., help="Scenario identifier."),
    notice: str = typer.Option(..., help="Notice id."),
    action: str = typer.Option(
        ...,
        help="ack | reexamine | request_context | ignore | reject | close",
    ),
    note: str | None = typer.Option(None, help="Optional operator note."),  # noqa: B008
) -> None:
    """Record an operator action on a notice. Does not edit trigger facts."""
    with _operator_errors():
        item = apply_notice_action(_root(), scenario, notice, action, note=note)
    _echo(
        {
            "notice_id": item.notice_id,
            "action": action,
            "state": item.workflow.state.value,
            "selected_posture": (
                item.workflow.selected_posture.value if item.workflow.selected_posture else None
            ),
        }
    )


@packet_app.command("build")
def packet_build(
    scenario: str = typer.Option(..., help="Scenario identifier."),
    notice: str = typer.Option(..., help="Notice id."),
    replay: bool = typer.Option(
        False,
        help="Build as of the episode end. Required for historical notices. Live default is now.",
    ),
    as_of: datetime | None = typer.Option(  # noqa: B008
        None,
        help="Knowledge cutoff (UTC). Implies replay if the date is in the past.",
    ),
) -> None:
    """Assemble evidence.json. Same compiler for a live desk and a historical replay."""
    with _operator_errors():
        packet, path = build_and_save(_root(), scenario, notice, replay=replay, as_of=as_of)
    _echo(
        {
            "scenario": scenario,
            "notice_id": packet.notice_id,
            "packet_id": packet.packet_id,
            "mode": packet.clocks.mode,
            "knowledge_cutoff": packet.clocks.knowledge_cutoff.isoformat(),
            "knowledge_rule": packet.clocks.knowledge_rule,
            "n_evidence": len(packet.collected_evidence),
            "n_hypotheses": len(packet.hypotheses),
            "path": str(path),
        }
    )


@packet_app.command("pdf")
def packet_pdf(
    scenario: str = typer.Option(..., help="Scenario identifier."),
    notice: str = typer.Option(..., help="Notice id."),
) -> None:
    """Write brief.pdf for the notice's current packet."""
    with _operator_errors():
        item = load_notice(_root(), scenario, notice)
        packet_id = item.workflow.packet_id
        if not packet_id:
            raise ValueError("notice has no packet; run wsd packet build first")
        path = render_existing_packet(_root(), scenario, packet_id)
    _echo({"notice_id": notice, "packet_id": packet_id, "path": str(path)})


@packet_app.command("collect")
def packet_collect(
    scenario: str = typer.Option(..., help="Scenario identifier."),
    notice: str = typer.Option(..., help="Notice id."),
    replay: bool = typer.Option(
        False,
        help="Use episode-end cutoff. Required for historical notices.",
    ),
    task: str = typer.Option(
        "harvest",
        help="validate | chronology | refresh_physical | official_pack | harvest | all",
    ),
    request_context: bool = typer.Option(
        False,
        help="Also set the notice to context_requested (focused posture).",
    ),
) -> None:
    """Run packet-scoped collection tasks. Writes into interpretation/<packet>/collection/."""
    if task == "harvest":
        kinds = list(HARVEST_KINDS)
    elif task == "all":
        kinds = list(ALL_KINDS)
    else:
        kinds = [task]
    with _operator_errors():
        payload = run_collection(
            _root(),
            scenario,
            notice,
            kinds=kinds,
            replay=replay,
            request_context=request_context,
        )
    _echo(payload)


@packet_app.command("report")
def packet_report(
    scenario: str = typer.Option(..., help="Scenario identifier."),
    notice: str = typer.Option(..., help="Notice id."),
    notes: str | None = typer.Option(None, help="Save the whole notes document."),
    assessment: str | None = typer.Option(None, help="Dump working assessment text."),
    hypotheses: str | None = typer.Option(None, help="Dump hypothesis notes."),
    collected: str | None = typer.Option(None, help="Dump what you collected."),
    findings: str | None = typer.Option(None, help="Dump findings."),
    decision: str | None = typer.Option(None, help="Dump the decision."),
    change: str | None = typer.Option(None, help="Dump what would change this."),
) -> None:
    """Load or save the analyst working notes. Prefills a template if empty."""
    sections = {
        key: value
        for key, value in {
            "assessment": assessment,
            "hypotheses": hypotheses,
            "collected": collected,
            "findings": findings,
            "decision": decision,
            "change": change,
        }.items()
        if value is not None
    }
    with _operator_errors():
        payload = (
            save_report(_root(), scenario, notice, sections or None, notes=notes)
            if notes is not None or sections
            else load_report(_root(), scenario, notice)
        )
    _echo(
        {
            "notice_id": payload["notice_id"],
            "report_id": payload["report_id"],
            "empty": payload["empty"],
            "updated_at": payload.get("updated_at"),
        }
    )


@agent_app.command("run")
def agent_run(
    interval: float = typer.Option(5.0, help="Heartbeat interval in seconds."),
    agent_id: str = typer.Option("agent", help="Heartbeat row id."),
) -> None:
    """Stay up, heartbeat into Postgres, and wait for collect/measure jobs."""
    with _operator_errors():
        run_agent(interval=interval, agent_id=agent_id)


if __name__ == "__main__":
    app()
