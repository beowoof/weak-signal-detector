import json
from datetime import UTC, date, datetime

from wsf.connectors.copernicus_catalogue import search_catalogue
from wsf.connectors.http import HttpResponse


class _FakeTransport:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.urls: list[str] = []

    def get(self, url: str, *, headers=None, timeout: float = 60) -> HttpResponse:
        self.urls.append(url)
        body = json.dumps(self.payload).encode()
        return HttpResponse(url=url, status=200, body=body, headers={})

    def post(self, url: str, *, headers=None, timeout: float = 60, data=None) -> HttpResponse:
        raise AssertionError("catalogue search is GET-only")


def test_s1_original_publication_is_knowable_s2_reprocess_uses_latency() -> None:
    payload = {
        "value": [
            {
                "Id": "s1",
                "Name": "S1A_IW_GRDH_1SDV_20220211T040250_20220211T040319.SAFE",
                "ContentDate": {"Start": "2022-02-11T04:02:50Z"},
                "PublicationDate": "2022-02-11T05:12:42Z",
            },
            {
                "Id": "s2",
                "Name": "S2B_MSIL1C_20220211T090009_N0510_R007_T36UVF_20240513T155855.SAFE",
                "ContentDate": {"Start": "2022-02-11T09:00:09Z"},
                "PublicationDate": "2024-11-19T18:05:31Z",
            },
            {
                "Id": "cog",
                "Name": "S1A_IW_GRDH_1SDV_20220211T040250_COG.SAFE",
                "ContentDate": {"Start": "2022-02-11T04:02:50Z"},
                "PublicationDate": "2023-05-19T20:31:37Z",
            },
        ]
    }
    transport = _FakeTransport(payload)
    aois = [{"id": "RUS-yelnya", "name": "Yelnya", "bbox": [32.95, 54.35, 33.42, 54.62]}]
    cutoff = datetime(2022, 2, 12, 23, 59, 59, tzinfo=UTC)
    granules, notes = search_catalogue(
        transport,
        aois,
        start=date(2022, 2, 10),
        end=date(2022, 2, 12),
        cutoff=cutoff,
        sleep=0,
    )
    names = {row["name"] for row in granules}
    assert any("GRDH" in name and "COG" not in name for name in names)
    assert not any("COG" in name for name in names)
    s1 = next(row for row in granules if row["collection"] == "SENTINEL-1")
    s2 = next(row for row in granules if row["collection"] == "SENTINEL-2")
    assert s1["knowable"] is True
    assert s1["reconstructed"] is False
    assert s2["knowable"] is True
    assert s2["reconstructed"] is True
    assert "do not vote" in " ".join(notes).lower() or "not downloaded" in " ".join(notes).lower()
    assert any("SENTINEL-1" in url and "Yelnya" not in url for url in transport.urls)
