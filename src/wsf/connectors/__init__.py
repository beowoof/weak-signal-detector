from __future__ import annotations

from pathlib import Path
from typing import Any

from wsf.connectors.base import Connector
from wsf.connectors.brent import BrentConnector
from wsf.connectors.cbr import CbrConnector
from wsf.connectors.ctlogs import CtConnector
from wsf.connectors.declared_posture import DeclaredPostureConnector
from wsf.connectors.firms import FirmsConnector
from wsf.connectors.fred import FredConnector
from wsf.connectors.gazette_cadence import GazetteCadenceConnector
from wsf.connectors.gdelt import GdeltConnector
from wsf.connectors.http import HttpTransport, UrllibTransport
from wsf.connectors.icews import IcewsConnector
from wsf.connectors.moex import MoexConnector
from wsf.connectors.navarea import NavareaConnector
from wsf.connectors.notam import NotamConnector
from wsf.connectors.official import OfficialConnector
from wsf.connectors.osm import OsmConnector
from wsf.connectors.ripe import RipeConnector
from wsf.connectors.sar import SarConnector
from wsf.connectors.viirs import ViirsConnector, viirs_extra_available
from wsf.connectors.wiki_edits import WikiEditsConnector
from wsf.connectors.wikipedia import WikipediaConnector

SOURCE_SERIES = {
    "gdelt": "talk.gdelt_cameo",
    "wikipedia": "attn.wiki_pageviews",
    "alfred": "dyad.fx",
    "viirs": "tempo.viirs_aoi",
    "moex": "dyad.moex_usdrub",
    "firms": "tempo.firms_thermal",
    "wiki_edits": "attn.wiki_edits",
    "osm": "attn.osm_changesets",
    "ripe": "net.ripe_prefixes",
    "official": "official.gazette",
    "ct": "official.ct_certs",
    "icews": "talk.icews_cameo",
    "brent": "info.brent",
    "sar": "tempo.s1_backscatter",
    "gazette_cadence": "official.gazette_cadence",
    "navarea": "nav.spatial_warnings",
    "notam": "air.notam_restrictions",
    "cbr": "market.cbr_funding_spread",
    "declared_posture": "posture.travel_risk",
}

AOI_SOURCES = frozenset({"viirs", "firms", "osm", "sar"})


def default_connectors(
    project_root: Path,
    *,
    transport: HttpTransport | None = None,
    viirs_backend: Any | None = None,
) -> dict[str, Connector]:
    http = transport or UrllibTransport()
    raw = project_root / "data" / "raw"
    return {
        "wikipedia": WikipediaConnector(http),
        "alfred": FredConnector(http),
        "gdelt": GdeltConnector(http, cache_dir=raw / "gdelt"),
        "viirs": ViirsConnector(cache_dir=raw / "viirs", backend=viirs_backend),
        "moex": MoexConnector(http),
        "firms": FirmsConnector(http),
        "wiki_edits": WikiEditsConnector(http),
        "osm": OsmConnector(http),
        "ripe": RipeConnector(http, cache_dir=raw / "ripe"),
        "official": OfficialConnector(http),
        "ct": CtConnector(http),
        "icews": IcewsConnector(raw / "icews"),
        "brent": BrentConnector(http),
        "sar": SarConnector(http, cache_dir=raw / "sar"),
        "gazette_cadence": GazetteCadenceConnector(http),
        "navarea": NavareaConnector(http),
        "notam": NotamConnector(http),
        "cbr": CbrConnector(http),
        "declared_posture": DeclaredPostureConnector(http),
    }


def extras_status() -> dict[str, bool]:
    return {"viirs_extra": viirs_extra_available()}
