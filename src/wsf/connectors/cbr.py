from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime
from typing import Any

from wsf.connectors.base import ConnectorResult, PullRequest
from wsf.connectors.daily import daily_count_result
from wsf.connectors.http import HttpTransport, post_with_retry
from wsf.time import date_range

CBR_DAILY_INFO_URL = "https://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx"


class CbrConnector:
    """Measures domestic financial conditions: Bank of Russia RUONIA interbank funding spread over policy key rate."""
    source = "cbr"

    def __init__(self, transport: HttpTransport) -> None:
        self.http = transport

    def _fetch_soap(self, action: str, body_xml: str, progress: Any) -> tuple[int, bytes]:
        soap_req = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    {body_xml}
  </soap:Body>
</soap:Envelope>"""
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f"http://web.cbr.ru/{action}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        resp = post_with_retry(
            self.http,
            CBR_DAILY_INFO_URL,
            headers=headers,
            data=soap_req.encode("utf-8"),
            timeout=30,
            attempts=3,
            sleep=1.0,
        )
        return resp.status, resp.body

    def pull(self, request: PullRequest) -> ConnectorResult:
        days = date_range(request.start, request.end)
        retrieved_at = request.retrieved_at or datetime.now(UTC)
        progress = request.log()

        requests_log: list[dict[str, Any]] = []
        ruonia_by_date: dict[date, float] = {}
        key_rate_by_date: dict[date, float] = {}
        source_down_days: set[date] = set()

        ruonia_body = f"""<RuoniaXML xmlns="http://web.cbr.ru/">
      <fromDate>{request.start.isoformat()}</fromDate>
      <ToDate>{request.end.isoformat()}</ToDate>
    </RuoniaXML>"""
        progress.status(f"cbr {request.window_id} RuoniaXML {request.start}..{request.end}")
        try:
            status_r, body_r = self._fetch_soap("RuoniaXML", ruonia_body, progress)
            requests_log.append({
                "url": f"{CBR_DAILY_INFO_URL}#RuoniaXML",
                "status": status_r,
                "bytes": len(body_r),
            })
            if status_r == 200 and body_r:
                root = ET.fromstring(body_r)
                for ro in root.iter("ro"):
                    d_elem = ro.find("D0")
                    r_elem = ro.find("ruo")
                    if d_elem is not None and d_elem.text and r_elem is not None and r_elem.text:
                        try:
                            d_val = date.fromisoformat(d_elem.text[:10])
                            ruonia_by_date[d_val] = float(r_elem.text.replace(",", "."))
                        except (ValueError, TypeError):
                            continue
            else:
                source_down_days.update(d for d in days if d.weekday() < 5)
        except Exception as err:
            requests_log.append({"url": f"{CBR_DAILY_INFO_URL}#RuoniaXML", "error": str(err)})
            source_down_days.update(d for d in days if d.weekday() < 5)

        keyrate_body = f"""<KeyRateXML xmlns="http://web.cbr.ru/">
      <fromDate>{request.start.isoformat()}</fromDate>
      <ToDate>{request.end.isoformat()}</ToDate>
    </KeyRateXML>"""
        progress.status(f"cbr {request.window_id} KeyRateXML {request.start}..{request.end}")
        try:
            status_k, body_k = self._fetch_soap("KeyRateXML", keyrate_body, progress)
            requests_log.append({
                "url": f"{CBR_DAILY_INFO_URL}#KeyRateXML",
                "status": status_k,
                "bytes": len(body_k),
            })
            if status_k == 200 and body_k:
                root = ET.fromstring(body_k)
                kr_records: list[tuple[date, float]] = []
                for kr in root.iter("KR"):
                    d_elem = kr.find("DT")
                    r_elem = kr.find("Rate")
                    if d_elem is not None and d_elem.text and r_elem is not None and r_elem.text:
                        try:
                            d_val = date.fromisoformat(d_elem.text[:10])
                            kr_records.append((d_val, float(r_elem.text.replace(",", "."))))
                        except (ValueError, TypeError):
                            continue
                kr_records.sort(key=lambda x: x[0])
                if kr_records:
                    curr_rate = kr_records[0][1]
                    kr_idx = 0
                    for day in days:
                        while kr_idx < len(kr_records) and kr_records[kr_idx][0] <= day:
                            curr_rate = kr_records[kr_idx][1]
                            kr_idx += 1
                        key_rate_by_date[day] = curr_rate
            else:
                source_down_days.update(d for d in days if d.weekday() < 5)
        except Exception as err:
            requests_log.append({"url": f"{CBR_DAILY_INFO_URL}#KeyRateXML", "error": str(err)})
            source_down_days.update(d for d in days if d.weekday() < 5)

        counts: dict[date, float] = {}
        for day in days:
            if day in ruonia_by_date and day in key_rate_by_date:
                ruonia_rate = ruonia_by_date[day]
                key_rate = key_rate_by_date[day]
                counts[day] = (ruonia_rate - key_rate) * 100.0
            elif day.weekday() < 5 and (day in ruonia_by_date or day in key_rate_by_date):
                source_down_days.add(day)

        progress.line(
            f"cbr {request.window_id} ruonia_days={len(ruonia_by_date)} spread_days={len(counts)} "
            f"down_days={len(source_down_days)}"
        )
        return daily_count_result(
            request,
            days,
            counts,
            retrieved_at=retrieved_at,
            requests=requests_log,
            expected_weekdays_only=True,
            source_down_days=source_down_days,
            notes="Bank of Russia domestic money-market RUONIA spread over policy key rate in bps",
        )
