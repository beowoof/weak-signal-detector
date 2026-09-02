#!/usr/bin/env python3
"""Serve a read-only dashboard over local Weak Signal Fusion measurements."""

from __future__ import annotations

import argparse
import json
import mimetypes
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_ROOT = Path(__file__).resolve().parent
SCENARIOS_ROOT = PROJECT_ROOT / "scenarios"


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


from wsf.analysis.coupling import evaluate_window_coupling


def compute_coupling_for_windows(scenario_id: str, features: list[dict]) -> dict[str, dict]:
    windows = sorted({r["window_id"] for r in features if r.get("window_id")})
    result: dict[str, dict] = {}
    for w in windows:
        try:
            w_res = evaluate_window_coupling(scenario_id, w, features, threshold_z=1.5, persistence_days=3, run_permutation=False)
            result[w] = {
                "dates": w_res.dates,
                "daily_states": [
                    {
                        "date": st.date,
                        "window_id": st.window_id,
                        "domain_energies": st.domain_energies,
                        "total_energy": st.total_energy,
                        "active_domains_z15": st.active_domains_z15,
                        "active_domains_z20": st.active_domains_z20,
                        "n_domains_z15": st.n_domains_z15,
                        "n_domains_z20": st.n_domains_z20,
                        "costly_status": st.costly_status,
                        "verdict": st.verdict,
                        "sensor_tasking_order": st.sensor_tasking_order,
                        "series_z": st.series_z,
                    }
                    for st in w_res.daily_states
                ],
                "episodes_k3": [
                    {
                        "level": ep.level,
                        "start_date": ep.start_date,
                        "end_date": ep.end_date,
                        "duration_days": ep.duration_days,
                        "contributing_domains": ep.contributing_domains,
                        "contributing_series": ep.contributing_series,
                        "tasking_order_days": ep.tasking_order_days,
                        "mean_energy": ep.mean_energy,
                        "max_energy": ep.max_energy,
                    }
                    for ep in w_res.episodes_k3
                ],
                "episodes_k2": [
                    {
                        "level": ep.level,
                        "start_date": ep.start_date,
                        "end_date": ep.end_date,
                        "duration_days": ep.duration_days,
                        "contributing_domains": ep.contributing_domains,
                        "contributing_series": ep.contributing_series,
                        "tasking_order_days": ep.tasking_order_days,
                        "mean_energy": ep.mean_energy,
                        "max_energy": ep.max_energy,
                    }
                    for ep in w_res.episodes_k2
                ],
                "max_energy": w_res.max_energy,
                "mean_energy": w_res.mean_energy,
                "days_ge3_domains_z15": w_res.days_ge3_domains_z15,
                "days_ge2_domains_z15": w_res.days_ge2_domains_z15,
                "tasking_order_days": w_res.tasking_order_days,
            }
        except Exception:
            pass
    return result


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
    return {
        "key": ref.key,
        "scenario": scenario_metadata(ref.scenario_id, scenarios_root),
        "summary": summary,
        "features": features,
        "days": days,
        "coupling": coupling,
    }


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "WeakSignalDashboard/1.0"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/results":
                self.send_json(result_index())
                return
            if parsed.path == "/api/result":
                key = parse_qs(parsed.query).get("key", [""])[0]
                if not key:
                    self.send_error(HTTPStatus.BAD_REQUEST, "Missing result key")
                    return
                self.send_json(load_result(key))
                return
            self.send_static(parsed.path)
        except KeyError:
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown result set")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    def send_json(self, payload: dict) -> None:
        body = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_static(self, request_path: str) -> None:
        relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        candidate = (DASHBOARD_ROOT / relative).resolve()
        if DASHBOARD_ROOT not in candidate.parents and candidate != DASHBOARD_ROOT:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Weak Signal dashboard: http://{args.host}:{args.port}")
    print("Press Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
