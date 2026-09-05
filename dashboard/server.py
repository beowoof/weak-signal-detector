#!/usr/bin/env python3
"""FastAPI desk API over local Weak Signal Fusion measurements."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from wsf.analysis.coupling import evaluate_window_coupling
from wsf.analyst_workflow import export_brief, load_workflow, update_workflow
from wsf.brief_pdf import render_existing_packet
from wsf.briefing_standards import packet_presentation
from wsf.collect import HARVEST_KINDS, load_collection, run_collection
from wsf.db import desk_health
from wsf.draft import run_desk_draft
from wsf.notice import apply_action_at_path, emit_notices_for_measurement, load_notice
from wsf.packet import build_and_save, packet_directory
from wsf.progress import load_collect_progress
from wsf.report import load_report, save_report

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DASHBOARD_ROOT = Path(__file__).resolve().parent
SCENARIOS_ROOT = PROJECT_ROOT / "scenarios"
DIST_ROOT = DASHBOARD_ROOT / "web" / "dist"


@dataclass(frozen=True)
class ResultRef:
    scenario_id: str
    measure_id: str
    directory: Path

    @property
    def key(self) -> str:
        return f"{self.scenario_id}/{self.measure_id}"


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON in {path}:{line_number}: {exc}") from exc
    return rows


def discover_results(scenarios_root: Path = SCENARIOS_ROOT) -> list[ResultRef]:
    results = []
    for summary_path in scenarios_root.glob("*/measurement/*/summary.json"):
        result_dir = summary_path.parent
        if not (result_dir / "features.jsonl").is_file():
            continue
        results.append(
            ResultRef(
                scenario_id=summary_path.parents[2].name,
                measure_id=result_dir.name,
                directory=result_dir,
            )
        )
    return sorted(results, key=lambda item: (item.scenario_id, item.measure_id), reverse=True)


def scenario_metadata(scenario_id: str, scenarios_root: Path = SCENARIOS_ROOT) -> dict:
    path = scenarios_root / scenario_id / "scenario.json"
    if not path.is_file():
        return {"scenario_id": scenario_id}
    return read_json(path)


def result_index(scenarios_root: Path = SCENARIOS_ROOT) -> dict:
    refs = discover_results(scenarios_root)
    scenarios: dict[str, dict] = {}
    items = []
    for ref in refs:
        summary = read_json(ref.directory / "summary.json")
        scenario = scenarios.setdefault(
            ref.scenario_id, scenario_metadata(ref.scenario_id, scenarios_root)
        )
        items.append(
            {
                "key": ref.key,
                "scenario_id": ref.scenario_id,
                "measure_id": ref.measure_id,
                "measurement_mode": summary.get("measurement_mode", "legacy_unspecified"),
                "protocol_id": summary.get("protocol_id"),
                "n_feature_rows": summary.get("n_feature_rows"),
                "active_series": summary.get("active_series", []),
                "purpose": scenario.get("purpose"),
                "incident": scenario.get("incident"),
                "controls": scenario.get("controls", []),
            }
        )
    return {"results": items, "scenarios": scenarios}


def compute_coupling_for_windows(scenario_id: str, features: list[dict]) -> dict[str, dict]:
    windows = sorted({r["window_id"] for r in features if r.get("window_id")})
    result: dict[str, dict] = {}
    for window_id in windows:
        try:
            window = evaluate_window_coupling(
                scenario_id,
                window_id,
                features,
                threshold_z=1.5,
                persistence_days=3,
                run_permutation=False,
            )
        except ValueError:
            continue
        result[window_id] = {
            "dates": window.dates,
            "daily_states": [
                {
                    "date": state.date,
                    "window_id": state.window_id,
                    "domain_energies": state.domain_energies,
                    "total_energy": state.total_energy,
                    "active_domains_z15": state.active_domains_z15,
                    "active_domains_z20": state.active_domains_z20,
                    "n_domains_z15": state.n_domains_z15,
                    "n_domains_z20": state.n_domains_z20,
                    "costly_status": state.costly_status,
                    "verdict": state.verdict,
                    "sensor_tasking_order": state.sensor_tasking_order,
                    "series_z": state.series_z,
                }
                for state in window.daily_states
            ],
            "episodes_k3": [_episode_payload(episode) for episode in window.episodes_k3],
            "episodes_k2": [_episode_payload(episode) for episode in window.episodes_k2],
            "max_energy": window.max_energy,
            "mean_energy": window.mean_energy,
            "days_ge3_domains_z15": window.days_ge3_domains_z15,
            "days_ge2_domains_z15": window.days_ge2_domains_z15,
            "tasking_order_days": window.tasking_order_days,
        }
    return result


def _episode_payload(episode) -> dict:
    return {
        "level": episode.level,
        "start_date": episode.start_date,
        "end_date": episode.end_date,
        "duration_days": episode.duration_days,
        "contributing_domains": episode.contributing_domains,
        "contributing_series": episode.contributing_series,
        "tasking_order_days": episode.tasking_order_days,
        "mean_energy": episode.mean_energy,
        "max_energy": episode.max_energy,
    }


def load_result(key: str, scenarios_root: Path = SCENARIOS_ROOT) -> dict:
    matches = {ref.key: ref for ref in discover_results(scenarios_root)}
    ref = matches.get(key)
    if ref is None:
        raise KeyError(key)
    summary = read_json(ref.directory / "summary.json")
    features = read_jsonl(ref.directory / "features.jsonl")
    days_path = ref.directory / "days.jsonl"
    days = read_jsonl(days_path) if days_path.is_file() else []
    coupling = compute_coupling_for_windows(ref.scenario_id, features)
    notices = _notices_for_measure(ref.scenario_id, ref.measure_id, scenarios_root)
    return {
        "key": ref.key,
        "scenario": scenario_metadata(ref.scenario_id, scenarios_root),
        "summary": summary,
        "features": features,
        "days": days,
        "coupling": coupling,
        "notices": notices,
    }


def list_notices_index(scenarios_root: Path = SCENARIOS_ROOT) -> dict:
    items: list[dict] = []
    for path in sorted(scenarios_root.glob("*/notices/*/notice.json")):
        payload = read_json(path)
        trigger = payload.get("trigger") or {}
        scenario_id = trigger.get("scenario_id") or path.parents[2].name
        measure_id = trigger.get("measurement_id")
        items.append(
            {
                **payload,
                "scenario_id": scenario_id,
                "key": f"{scenario_id}/{measure_id}" if measure_id else None,
            }
        )
    items.sort(
        key=lambda item: (
            (item.get("trigger") or {}).get("start") or "",
            item.get("notice_id") or "",
        )
    )
    return {"notices": items}


def load_notice_payload(
    scenario_id: str, notice_id: str, scenarios_root: Path = SCENARIOS_ROOT
) -> dict:
    path = scenarios_root / scenario_id / "notices" / notice_id / "notice.json"
    if not path.is_file():
        raise KeyError(f"{scenario_id}/{notice_id}")
    payload = read_json(path)
    trigger = payload.get("trigger") or {}
    measure_id = trigger.get("measurement_id")
    payload["scenario_id"] = trigger.get("scenario_id") or scenario_id
    payload["key"] = f"{payload['scenario_id']}/{measure_id}" if measure_id else None
    return payload


def _notices_for_measure(scenario_id: str, measure_id: str, scenarios_root: Path) -> list[dict]:
    root = scenarios_root / scenario_id / "notices"
    if not root.is_dir():
        return []
    items: list[dict] = []
    for path in sorted(root.glob("*/notice.json")):
        payload = read_json(path)
        trigger = payload.get("trigger") or {}
        if trigger.get("measurement_id") != measure_id:
            continue
        items.append(payload)
    items.sort(
        key=lambda item: (
            (item.get("trigger") or {}).get("start") or "",
            item.get("notice_id") or "",
        )
    )
    return items


class NoticeActionBody(BaseModel):
    scenario: str = Field(min_length=1)
    notice_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    note: str | None = None
    replay: bool = False


class PacketCollectBody(BaseModel):
    scenario: str = Field(min_length=1)
    notice_id: str = Field(min_length=1)
    tasks: list[str] | None = None
    replay: bool = False
    request_context: bool = False


class NoticeEmitBody(BaseModel):
    scenario: str = Field(min_length=1)
    measurement_id: str | None = None


class PacketBuildBody(BaseModel):
    scenario: str = Field(min_length=1)
    notice_id: str = Field(min_length=1)
    replay: bool = False


class PacketDraftBody(BaseModel):
    scenario: str = Field(min_length=1)
    notice_id: str = Field(min_length=1)
    replay: bool = False
    search: bool = True
    apply: bool = False


class ReportBody(BaseModel):
    scenario: str = Field(min_length=1)
    notice_id: str = Field(min_length=1)
    notes: str | None = None
    sections: dict[str, str] = Field(default_factory=dict)


class StrictJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return json.dumps(content, allow_nan=False, separators=(",", ":")).encode()


class WorkflowBody(BaseModel):
    scenario: str
    notice_id: str
    revision: int
    action: str
    review_version: str = ""
    proposal_id: str = ""
    status: str = ""
    reason: str = ""
    text: str = ""
    title: str = ""
    version: int = 0
    reviewer: str = ""
    acknowledged: bool = False


def create_app(
    *,
    api_only: bool | None = None,
    scenarios_root: Path | None = None,
    project_root: Path | None = None,
) -> FastAPI:
    if api_only is None:
        api_only = os.environ.get("WSD_API_ONLY", "").lower() in {"1", "true", "yes"}
    proj = Path(project_root) if project_root is not None else PROJECT_ROOT
    root = Path(scenarios_root) if scenarios_root is not None else proj / "scenarios"
    app = FastAPI(title="WSD collection cueing desk", default_response_class=StrictJSONResponse)
    app.state.project_root = proj
    app.state.scenarios_root = root
    from dashboard.draft_stream import draft_events
    from dashboard.scenario_workspace import scenario_router

    app.include_router(scenario_router(root))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "HEAD", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def api_health() -> JSONResponse:
        payload = desk_health()
        status = 200 if payload["ok"] else 503
        return JSONResponse(payload, status_code=status)

    @app.get("/api/collection/progress")
    def api_collection_progress() -> dict:
        return load_collect_progress(app.state.project_root)

    @app.get("/api/notices")
    def api_notices() -> dict:
        return list_notices_index(app.state.scenarios_root)

    @app.get("/api/notice")
    def api_notice(
        scenario: str = Query(..., min_length=1),
        notice_id: str = Query(..., min_length=1),
    ) -> dict:
        try:
            return load_notice_payload(scenario, notice_id, app.state.scenarios_root)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown notice") from exc

    @app.post("/api/notice/action")
    def api_notice_action(body: NoticeActionBody) -> dict:
        path = app.state.scenarios_root / body.scenario / "notices" / body.notice_id / "notice.json"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Unknown notice")
        if body.action == "request_context":
            try:
                collection = run_collection(
                    app.state.project_root,
                    body.scenario,
                    body.notice_id,
                    kinds=list(HARVEST_KINDS),
                    replay=body.replay,
                    request_context=True,
                )
            except (ValueError, OSError, FileNotFoundError, KeyError) as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            payload = load_notice_payload(body.scenario, body.notice_id, app.state.scenarios_root)
            payload["collection"] = collection
            return payload
        try:
            apply_action_at_path(path, body.action, note=body.note)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return load_notice_payload(body.scenario, body.notice_id, app.state.scenarios_root)

    @app.post("/api/notice/emit")
    def api_notice_emit(body: NoticeEmitBody) -> dict:
        try:
            notices = emit_notices_for_measurement(
                app.state.project_root,
                body.scenario,
                measurement_id=body.measurement_id,
            )
        except (ValueError, OSError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "scenario": body.scenario,
            "n_notices": len(notices),
            "notice_ids": [item.notice_id for item in notices],
        }

    @app.post("/api/packet/build")
    def api_packet_build(body: PacketBuildBody) -> dict:
        try:
            packet, path = build_and_save(
                app.state.project_root,
                body.scenario,
                body.notice_id,
                replay=body.replay,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown notice") from exc
        except (ValueError, OSError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "scenario": body.scenario,
            "notice_id": packet.notice_id,
            "packet_id": packet.packet_id,
            "mode": packet.clocks.mode,
            "layers": packet.layers,
            "path": str(path),
        }

    @app.get("/api/packet")
    def api_packet(
        scenario: str = Query(..., min_length=1),
        packet_id: str = Query(..., min_length=1),
    ) -> dict:
        path = app.state.scenarios_root / scenario / "interpretation" / packet_id / "evidence.json"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Unknown packet")
        payload = read_json(path)
        payload["presentation"] = packet_presentation(payload)
        return payload

    @app.get("/api/packet/pdf")
    def api_packet_pdf(
        scenario: str = Query(..., min_length=1),
        packet_id: str = Query(..., min_length=1),
    ) -> FileResponse:
        if "/" in packet_id or ".." in packet_id or "/" in scenario:
            raise HTTPException(status_code=400, detail="Invalid packet id")
        try:
            path = render_existing_packet(app.state.project_root, scenario, packet_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Unknown packet") from exc
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=f"{packet_id}.pdf",
        )

    @app.get("/api/packet/collection")
    def api_packet_collection(
        scenario: str = Query(..., min_length=1),
        packet_id: str = Query(..., min_length=1),
    ) -> dict:
        return load_collection(app.state.project_root, scenario, packet_id)

    @app.post("/api/packet/draft")
    def api_packet_draft(body: PacketDraftBody) -> dict:
        try:
            return run_desk_draft(
                app.state.project_root,
                body.scenario,
                body.notice_id,
                replay=body.replay,
                search=body.search,
                apply=body.apply,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown notice") from exc
        except (ValueError, OSError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/packet/draft/review")
    def api_draft_review(scenario: str, notice_id: str) -> dict:
        try:
            notice = load_notice(app.state.project_root, scenario, notice_id)
            if not notice.workflow.packet_id:
                return {"review": None}
            path = packet_directory(app.state.project_root, scenario, notice.workflow.packet_id)
            path = path / "machine_draft.json"
            if not path.exists():
                return {"review": None}
            record = json.loads(path.read_text())
            return {"review": record.get("review"), "created_at": record.get("created_at")}
        except (KeyError, ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail="Draft review unavailable") from exc

    @app.post("/api/packet/draft/stream")
    def api_packet_draft_stream(body: PacketDraftBody) -> StreamingResponse:
        def run(*, progress):
            return run_desk_draft(
                app.state.project_root,
                body.scenario,
                body.notice_id,
                replay=body.replay,
                search=body.search,
                apply=body.apply,
                progress=progress,
            )

        return StreamingResponse(
            draft_events(run),
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/packet/collect")
    def api_packet_collect(body: PacketCollectBody) -> dict:
        try:
            return run_collection(
                app.state.project_root,
                body.scenario,
                body.notice_id,
                kinds=body.tasks,
                replay=body.replay,
                request_context=body.request_context,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown notice") from exc
        except (ValueError, OSError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/report")
    def api_report_get(
        scenario: str = Query(..., min_length=1),
        notice_id: str = Query(..., min_length=1),
    ) -> dict:
        try:
            return load_report(app.state.project_root, scenario, notice_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown notice") from exc
        except (ValueError, OSError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/report")
    def api_report_save(body: ReportBody) -> dict:
        try:
            return save_report(
                app.state.project_root,
                body.scenario,
                body.notice_id,
                body.sections or None,
                notes=body.notes,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown notice") from exc
        except (ValueError, OSError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/analyst-workflow")
    def api_workflow(scenario: str, notice_id: str) -> dict:
        try:
            return load_workflow(app.state.project_root, scenario, notice_id)
        except (KeyError, ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/analyst-workflow")
    def api_workflow_update(body: WorkflowBody) -> dict:
        try:
            return update_workflow(app.state.project_root, **body.model_dump())
        except (KeyError, ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/analyst-workflow/export")
    def api_workflow_export(scenario: str, notice_id: str, version: int, format: str = "md"):
        try:
            content = export_brief(app.state.project_root, scenario, notice_id, version, format)
            media_type = (
                "application/pdf"
                if format == "pdf"
                else ("text/html" if format == "html" else "text/markdown")
            )
            return Response(
                content,
                media_type=media_type,
                headers={
                    "Content-Disposition": f'attachment; filename="assessment-v{version}.{format}"'
                },
            )
        except (KeyError, ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/results")
    def api_results() -> dict:
        return result_index(app.state.scenarios_root)

    @app.get("/api/result")
    def api_result(key: str = Query(..., min_length=1)) -> dict:
        try:
            return load_result(key, app.state.scenarios_root)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown result set") from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    if api_only:
        return app

    dist_ready = (DIST_ROOT / "index.html").is_file()
    static_root = DIST_ROOT if dist_ready else DASHBOARD_ROOT

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(static_root / "index.html")

    if dist_ready:
        assets = DIST_ROOT / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")
    else:

        @app.get("/app.js")
        def legacy_js() -> FileResponse:
            return FileResponse(DASHBOARD_ROOT / "app.js")

        @app.get("/styles.css")
        def legacy_css() -> FileResponse:
            return FileResponse(DASHBOARD_ROOT / "styles.css")

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("WSD_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--api-only",
        action="store_true",
        help="Serve /api only. Pair with `npm run dev` in dashboard/web.",
    )
    parser.add_argument(
        "--reload",
        dest="reload",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Reload on Python changes (default on). Use --no-reload to disable.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    os.environ["WSD_API_ONLY"] = "1" if args.api_only else "0"
    import uvicorn

    print(f"WSD API: http://{args.host}:{args.port}/api")
    if args.api_only:
        print("UI: cd dashboard/web && npm run dev  →  http://127.0.0.1:5173")
    else:
        print(f"UI: http://{args.host}:{args.port}")
    run_kwargs: dict[str, object] = {
        "app": "dashboard.server:create_app",
        "factory": True,
        "host": args.host,
        "port": args.port,
        "reload": args.reload,
    }
    if args.reload:
        run_kwargs["reload_dirs"] = [str(DASHBOARD_ROOT), str(PROJECT_ROOT / "src")]
        run_kwargs["reload_excludes"] = [
            "web",
            "web/*",
            "**/node_modules/**",
            "**/__pycache__/**",
        ]
    uvicorn.run(**run_kwargs)


if __name__ == "__main__":
    main()
