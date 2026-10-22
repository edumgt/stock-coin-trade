"""One provider taxonomy for held Korean stocks, independent of a truncated stock list."""
from __future__ import annotations

import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timezone

import requests

INDUSTRIES_URL = "https://m.stock.naver.com/api/stocks/industry"
STOCK_URL = "https://m.stock.naver.com/api/stock"
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://m.stock.naver.com/"}
TTL = 86400
RETRY_TTL = 60
_catalog = {"at": 0.0, "names": {}, "checked": ""}
_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()


def normalize_symbol(value: str) -> str:
    value = str(value or "").strip().upper()
    value = re.sub(r"\.(KS|KQ)$", "", value)
    if re.fullmatch(r"A\d{6}", value):
        value = value[1:]
    return value if re.fullmatch(r"[0-9A-Z]{6}", value) else ""


def _unknown() -> dict:
    return {"sector": "분류 미확인", "sectorSource": None, "sectorAsOf": None,
            "sectorStatus": "unavailable", "sectorCode": None}


def _industry_names() -> dict[str, str]:
    with _lock:
        if _catalog["names"] and time.time() - _catalog["at"] < TTL:
            return dict(_catalog["names"])
        # Request all groups: this endpoint also defaults to just 20 rows.
        try:
            response = requests.get(INDUSTRIES_URL, params={"page": 1, "pageSize": 100},
                                    headers=HEADERS, timeout=(2, 4))
            response.raise_for_status()
            body = response.json()
            groups = body.get("groups", [])
            names = {str(row["no"]): str(row["name"]).strip() for row in groups if row.get("name")}
            if not names or len(names) < int(body.get("totalCount", len(names))):
                raise ValueError("Incomplete industry catalog")
            _catalog.update(at=time.time(), names=names,
                            checked=datetime.now(timezone.utc).isoformat())
            return dict(names)
        except Exception:
            # Keep a previously verified catalog rather than inventing new labels.
            return dict(_catalog["names"])


def _lookup(symbol: str, names: dict[str, str]) -> dict:
    try:
        response = requests.get(f"{STOCK_URL}/{symbol}/integration", headers=HEADERS, timeout=(2, 4))
        response.raise_for_status()
        row = response.json()
        if str(row.get("itemCode", "")) != symbol:
            raise ValueError("Stock code mismatch")
        kind = str(row.get("stockEndType", "")).lower()
        code = str(row.get("industryCode") or "")
        # Fund index codes are not equity industry codes. Keep funds separate.
        label = {"etf": "ETF", "etn": "ETN"}.get(kind) or names.get(code)
        if not label or kind not in {"stock", "etf", "etn"}:
            raise ValueError("No verified classification")
        result = {"sector": label, "sectorSource": "네이버 금융 업종" if kind == "stock" else "네이버 금융 상품 유형",
                  "sectorAsOf": datetime.now(timezone.utc).isoformat(), "sectorStatus": "verified",
                  "sectorCode": code if kind == "stock" else kind.upper()}
    except Exception:
        result = _unknown()
    with _lock:
        _cache[symbol] = (time.time(), result)
    return dict(result)


def get_stock_sectors(symbols: list[str]) -> dict[str, dict]:
    codes = list(dict.fromkeys(code for value in symbols if (code := normalize_symbol(value))))
    result, missing = {}, []
    with _lock:
        for code in codes:
            cached = _cache.get(code)
            ttl = TTL if cached and cached[1]["sectorStatus"] == "verified" else RETRY_TTL
            if cached and time.time() - cached[0] < ttl:
                result[code] = dict(cached[1])
            else:
                missing.append(code)
    if not missing:
        return result
    names = _industry_names()
    if not names:
        return {**result, **{code: _unknown() for code in missing}}
    executor = ThreadPoolExecutor(max_workers=6)
    futures = {executor.submit(_lookup, code, names): code for code in missing}
    done, pending = wait(futures, timeout=8)
    for future in done:
        result[futures[future]] = future.result()
    for future in pending:
        future.cancel()
        result[futures[future]] = _unknown()
    executor.shutdown(wait=False, cancel_futures=True)
    return result
