"""FRED read-only learning endpoints. Never return upstream URLs or credentials."""
import os
import math
from datetime import datetime, timezone
from threading import Lock
from time import monotonic

import requests
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/fred-test", tags=["fred-test"])
_cache = {}
_lock = Lock()


def _fetch(path, series_id, limit=30):
    key = os.getenv("FRED_API_KEY", "").strip()
    if not key:
        return JSONResponse({"ok": False, "message": "서버에 FRED_API_KEY가 설정되지 않았습니다."}, status_code=503)
    cache_key = (path, series_id, limit)
    with _lock:
        cached = _cache.get(cache_key)
        if cached and monotonic() - cached[0] < 60:
            return cached[1]
    params = {"api_key": key, "file_type": "json", "series_id": series_id}
    if path.endswith("observations"):
        params.update(limit=limit, sort_order="desc")
    try:
        response = requests.get("https://api.stlouisfed.org/fred/" + path, params=params, timeout=(5, 15))
        if response.status_code != 200:
            status = response.status_code
            message = "지표 코드 또는 서버 API 키를 확인하세요." if status == 400 else "FRED 요청이 제한되었거나 서비스에 연결할 수 없습니다. 잠시 후 다시 시도하세요."
            return JSONResponse({"ok": False, "message": message}, status_code=502 if status != 429 else 503)
        data = response.json()
        result = {"source": "FRED · Federal Reserve Bank of St. Louis", "series_id": series_id,
                  "fetched_at": datetime.now(timezone.utc).isoformat(), "cached_for_seconds": 60}
        if path.endswith("observations"):
            rows = data["observations"]
            observations = []
            for row in rows:
                value = None if row["value"] == "." else float(row["value"])
                if value is not None and not math.isfinite(value):
                    value = None
                observations.append({"date": row["date"], "value": value})
            latest = next((row for row in observations if row["value"] is not None), None)
            result.update(observations=observations, latest=latest, as_of=latest["date"] if latest else None,
                          status="complete" if observations and all(r["value"] is not None for r in observations) else "partial")
        else:
            series = data["seriess"][0]
            result.update(series={name: series.get(name) for name in ("id", "title", "units", "frequency", "seasonal_adjustment", "last_updated", "observation_start", "observation_end", "notes")}, status="complete")
        payload = {"ok": True, "result": result}
        with _lock:
            if len(_cache) >= 128:
                _cache.clear()
            _cache[cache_key] = (monotonic(), payload)
        return payload
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        return JSONResponse({"ok": False, "message": "FRED 응답을 가져오지 못했습니다. 잠시 후 다시 시도하세요."}, status_code=503)


@router.get("/series")
def series(series_id: str = Query("DGS10", pattern=r"^[A-Za-z0-9_]{1,40}$")):
    return _fetch("series", series_id.upper())


@router.get("/observations")
def observations(series_id: str = Query("DGS10", pattern=r"^[A-Za-z0-9_]{1,40}$"), limit: int = Query(30, ge=1, le=200)):
    return _fetch("series/observations", series_id.upper(), limit)
