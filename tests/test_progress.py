import json
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path

from wsf.progress import Progress, format_elapsed, load_collect_progress


def test_progress_writes_snapshot(tmp_path: Path) -> None:
    stream = StringIO()
    log = Progress(enabled=True, stream=stream)
    path = tmp_path / "progress.json"
    log.bind(path)
    log.update(scenario_id="rus2021apr", source="viirs", day_index=126, day_count=141)
    log.status("viirs tile", aoi="RUS-boguchar", tile="h22v03", step="download")
    payload = log.snapshot()
    assert payload["scenario_id"] == "rus2021apr"
    assert payload["day_index"] == 126
    assert "h22v03" in stream.getvalue()
    log.status(
        "download",
        bytes=11_000_000,
        total_bytes=22_000_000,
        step="download",
    )
    assert "[############" in stream.getvalue() or "50%" in stream.getvalue()
    saved = path.read_text(encoding="utf-8")
    assert "RUS-boguchar" in saved
    log.stop_pulse()


def test_load_collect_progress_marks_stale(tmp_path: Path) -> None:
    scenario = tmp_path / "scenarios" / "rus2021apr"
    scenario.mkdir(parents=True)
    stale_at = (datetime.now(UTC) - timedelta(seconds=120)).isoformat()
    (scenario / "collect_progress.json").write_text(
        json.dumps(
            {
                "scenario_id": "rus2021apr",
                "updated_at": stale_at,
                "source": "viirs",
            }
        ),
        encoding="utf-8",
    )
    payload = load_collect_progress(tmp_path)
    assert payload["runs"]
    assert payload["runs"][0]["stale"] is True
    assert payload["active"] is None


def test_format_elapsed() -> None:
    assert format_elapsed(12) == "12s"
    assert format_elapsed(75) == "1m 15s"
    assert format_elapsed(3661) == "1h 01m"
