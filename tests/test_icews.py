from __future__ import annotations

import io
import zipfile
from datetime import date
from pathlib import Path

from tests.test_connectors import _queries
from wsf.connectors.base import PullRequest
from wsf.connectors.icews import IcewsConnector, icews_root


def _request(**overrides) -> PullRequest:
    payload = {
        "source": "icews",
        "series_id": "talk.icews_cameo",
        "scenario_id": "ukraine2022",
        "window_id": "incident",
        "start": date(2022, 2, 17),
        "end": date(2022, 2, 18),
        "queries": _queries(cameo_actor="RUS", cameo_root_codes=["01", "02", "04", "13"]),
        "max_workers": 1,
    }
    payload.update(overrides)
    return PullRequest(**payload)


HEADER = "Event Date\tSource Country\tCAMEO Code\n"
ROWS = (
    "2022-02-17\tRussian Federation\t14\n"  # stored 14 → 014 → talk 01
    "2022-02-17\tRussian Federation\t51\n"  # praise, not talk
    "2022-02-18\tUkraine\t14\n"
    "2022-02-18\tRussian Federation\t12\n"  # 012 → 01 talk
)


def test_icews_root_pads_two_digit_cameo() -> None:
    assert icews_root("14") == "01"
    assert icews_root("51") == "05"
    assert icews_root("141") == "14"


def test_icews_reads_tab_and_filters_talk(tmp_path: Path, monkeypatch) -> None:
    table = tmp_path / "events.2022.20190301000000.tab"
    table.write_text(HEADER + ROWS, encoding="utf-8")
    monkeypatch.setenv("ICEWS_EVENTS_PATH", str(table))
    result = IcewsConnector(tmp_path).pull(_request())
    assert result.observations[0].value == 1.0
    assert result.observations[1].value == 1.0


def test_icews_reads_dataverse_zip_and_nested_year_zip(tmp_path: Path, monkeypatch) -> None:
    year_zip = io.BytesIO()
    with zipfile.ZipFile(year_zip, "w") as inner:
        inner.writestr("events.2022.20190301000000.tab", HEADER + ROWS)
    archive = tmp_path / "ICEWS-Coded-Event-Data.zip"
    with zipfile.ZipFile(archive, "w") as outer:
        outer.writestr("events.2022.20190301000000.tab.zip", year_zip.getvalue())
        outer.writestr("events.1995.20150313082510.tab", HEADER + "1995-01-01\tRussia\t14\n")
        outer.writestr("ICEWS-codebook.pdf", b"not a table")
    monkeypatch.setenv("ICEWS_EVENTS_PATH", str(archive))
    result = IcewsConnector(tmp_path).pull(_request())
    assert result.observations[0].value == 1.0
    assert result.item["not_applicable"] is not True


def test_icews_directory_of_yearly_tabs(tmp_path: Path, monkeypatch) -> None:
    folder = tmp_path / "icews"
    folder.mkdir()
    (folder / "events.2022.x.tab").write_text(HEADER + ROWS, encoding="utf-8")
    monkeypatch.setenv("ICEWS_EVENTS_PATH", str(folder))
    result = IcewsConnector(folder).pull(_request())
    assert result.observations[0].quality == "ok"
    assert result.observations[0].value == 1.0
