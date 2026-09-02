from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any

from wsf.connectors.base import ConnectorResult, PullRequest
from wsf.connectors.daily import daily_count_result, failed_result
from wsf.connectors.http import HttpTransport, get_with_retry, redact_url
from wsf.time import date_range

FEDERAL_REGISTER_FACETS_URL = "https://www.federalregister.gov/api/v1/documents/facets/daily"
OFFENEGESETZE_URL = "https://api.offenegesetze.de/v1/veroeffentlichung/"


class GazetteCadenceConnector:
    """Measures executive and administrative publication cadence (positive bureaucratic residue and tempo)."""
    source = "gazette_cadence"

    def __init__(self, transport: HttpTransport) -> None:
        self.http = transport

    def pull(self, request: PullRequest) -> ConnectorResult:
        days = date_range(request.start, request.end)
        retrieved_at = request.retrieved_at or datetime.now(UTC)
        progress = request.log()

        actor = getattr(request.queries, "cameo_actor", "") or getattr(request.queries, "facility_actor", "USA")
        actor_str = str(actor).upper()

        requests_log: list[dict[str, Any]] = []
        counts: dict[date, float] = {}
        source_down_days: set[date] = set()

        headers = {
            "User-Agent": "WeakSignalFusion/0.1 (https://github.com/beowoof/weak-signal-detector; research poc)",
            "Accept": "application/json",
        }

        if actor_str == "USA":
            url = f"{FEDERAL_REGISTER_FACETS_URL}?conditions[publication_date][gte]={request.start.isoformat()}&conditions[publication_date][lte]={request.end.isoformat()}"
            progress.status(f"gazette_cadence {request.window_id} FederalRegister {request.start}..{request.end}")
            try:
                resp = get_with_retry(self.http, url, headers=headers, timeout=30, attempts=3, sleep=1.0)
                requests_log.append({"url": redact_url(url), "status": resp.status, "bytes": len(resp.body)})
                if resp.status == 200 and resp.body:
                    data = json.loads(resp.body.decode("utf-8"))
                    for date_str, info in data.items():
                        try:
                            d_val = date.fromisoformat(date_str)
                            if request.start <= d_val <= request.end:
                                counts[d_val] = float(info.get("count", 0))
                        except (ValueError, TypeError):
                            continue
                else:
                    source_down_days.update(days)
            except (TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as err:
                requests_log.append({"url": redact_url(url), "error": str(err)})
                source_down_days.update(days)

        elif actor_str == "DEU":
            years = sorted({request.start.year, request.end.year})
            deu_counts: dict[date, float] = {d: 0.0 for d in days}
            had_error = False

            for yr in years:
                url: str | None = f"{OFFENEGESETZE_URL}?year={yr}"
                pages = 0
                while url and pages < 40:
                    pages += 1
                    progress.status(f"gazette_cadence {request.window_id} OffeneGesetze year={yr} p={pages}")
                    try:
                        resp = get_with_retry(self.http, url, headers=headers, timeout=30, attempts=3, sleep=1.0)
                        requests_log.append({"url": redact_url(url), "status": resp.status, "bytes": len(resp.body)})
                        if resp.status != 200 or not resp.body:
                            had_error = True
                            break
                        data = json.loads(resp.body.decode("utf-8"))
                        results = data.get("results", []) if isinstance(data, dict) else data
                        oldest_on_page: date | None = None
                        for item in results:
                            raw_date = item.get("date")
                            if raw_date:
                                try:
                                    d_val = date.fromisoformat(raw_date[:10])
                                    if oldest_on_page is None or d_val < oldest_on_page:
                                        oldest_on_page = d_val
                                    if d_val in deu_counts:
                                        deu_counts[d_val] += 1.0
                                except (ValueError, TypeError):
                                    continue
                        # OffeneGesetze is ordered newest-to-oldest; stop paginating if past window start
                        if oldest_on_page and oldest_on_page < request.start:
                            break
                        url = data.get("next") if isinstance(data, dict) else None
                    except (TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as err:
                        requests_log.append({"url": redact_url(url or ""), "error": str(err)})
                        had_error = True
                        break

                if had_error:
                    # Mark any dates for this year that weren't reached before error as source_down
                    for d in days:
                        if d.year == yr and (oldest_on_page is None or d <= oldest_on_page):
                            source_down_days.add(d)

            counts.update(deu_counts)

        else:
            return failed_result(
                request,
                days,
                f"gazette_cadence is not implemented for actor {actor_str}",
                retrieved_at,
            )

        non_zero = sum(1 for v in counts.values() if v > 0)
        progress.line(
            f"gazette_cadence {request.window_id} days={len(days)} non_zero_days={non_zero} "
            f"total_docs={sum(counts.values()):.0f} down_days={len(source_down_days)}"
        )

        return daily_count_result(
            request,
            days,
            counts,
            retrieved_at=retrieved_at,
            requests=requests_log,
            source_down_days=source_down_days,
            notes=f"Official executive and administrative gazette publication cadence for {actor_str}",
        )
