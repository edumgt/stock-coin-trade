"""Binance Spot·Korbit 공개 시세의 읽기 전용 점검."""

from __future__ import annotations

import math
import threading
import time
from typing import Any

import requests

from app.services.brokers.common import BrokerApiError

BINANCE_BASE_URL = "https://data-api.binance.vision/api/v3"
KORBIT_BASE_URL = "https://api.korbit.co.kr/v2"
_binance_symbols_cache: dict[str, Any] = {"expires_at": 0.0, "symbols": []}
_binance_symbols_lock = threading.Lock()
_BINANCE_SYMBOLS_CACHE_SECONDS = 900


def _json(response: requests.Response, exchange: str) -> Any:
    try:
        body = response.json()
    except ValueError as exc:
        raise BrokerApiError(f"{exchange} 서버가 JSON 응답을 반환하지 않았습니다. (HTTP {response.status_code})") from exc
    if not response.ok:
        message = body.get("msg") if isinstance(body, dict) else None
        raise BrokerApiError(f"{exchange} 공개 시세 조회 실패 (HTTP {response.status_code}): {message or '요청이 거부되었습니다.'}")
    return body


def get_binance_ticker(symbol: str) -> dict[str, Any]:
    body = _json(requests.get(f"{BINANCE_BASE_URL}/ticker/24hr", params={"symbol": symbol}, timeout=15), "Binance")
    return {"exchange": "Binance Spot", "symbol": symbol, "lastPrice": body.get("lastPrice"), "priceChangePercent": body.get("priceChangePercent"),
            "highPrice": body.get("highPrice"), "lowPrice": body.get("lowPrice"), "volume": body.get("volume"), "closeTime": body.get("closeTime")}


def get_binance_orderbook(symbol: str) -> dict[str, Any]:
    body = _json(requests.get(f"{BINANCE_BASE_URL}/depth", params={"symbol": symbol, "limit": 10}, timeout=15), "Binance")
    return {"exchange": "Binance Spot", "symbol": symbol, "lastUpdateId": body.get("lastUpdateId"), "bids": body.get("bids", []), "asks": body.get("asks", [])}


def _load_binance_symbols() -> list[dict[str, str]]:
    now = time.monotonic()
    cached = _binance_symbols_cache["symbols"]
    if cached and now < _binance_symbols_cache["expires_at"]:
        return cached
    with _binance_symbols_lock:
        now = time.monotonic()
        cached = _binance_symbols_cache["symbols"]
        if cached and now < _binance_symbols_cache["expires_at"]:
            return cached
        body = _json(
            requests.get(f"{BINANCE_BASE_URL}/exchangeInfo", params={"permissions": "SPOT", "showPermissionSets": "false"}, timeout=15),
            "Binance",
        )
        rows = body.get("symbols", []) if isinstance(body, dict) else []
        symbols = [
            {
                "symbol": str(row.get("symbol", "")),
                "baseAsset": str(row.get("baseAsset", "")),
                "quoteAsset": str(row.get("quoteAsset", "")),
                "status": str(row.get("status", "")),
            }
            for row in rows
            if row.get("status") == "TRADING" and row.get("symbol")
        ]
        symbols.sort(key=lambda row: (row["quoteAsset"], row["baseAsset"], row["symbol"]))
        _binance_symbols_cache.update({"expires_at": time.monotonic() + _BINANCE_SYMBOLS_CACHE_SECONDS, "symbols": symbols})
        return symbols


def get_binance_symbols(query: str = "", quote_asset: str = "", limit: int = 50) -> dict[str, Any]:
    """거래 중인 Binance Spot 심볼을 검색한다(업스트림 전체 응답은 노출하지 않음)."""
    query = query.strip().upper()
    quote_asset = quote_asset.strip().upper()
    rows = _load_binance_symbols()
    matches = [
        row for row in rows
        if (not quote_asset or row["quoteAsset"] == quote_asset)
        and (not query or query in row["symbol"] or query in row["baseAsset"] or query in row["quoteAsset"])
    ]
    matches.sort(
        key=lambda row: (
            0 if row["symbol"] == query else 1 if row["baseAsset"] == query else 2 if row["symbol"].startswith(query) else 3,
            row["symbol"],
        )
    )
    return {
        "exchange": "Binance Spot",
        "query": query,
        "quoteAsset": quote_asset or None,
        "totalMatches": len(matches),
        "symbols": matches[:limit],
        "cacheSeconds": _BINANCE_SYMBOLS_CACHE_SECONDS,
    }


def get_korbit_ticker(symbol: str) -> dict[str, Any]:
    body = _json(requests.get(f"{KORBIT_BASE_URL}/tickers", params={"symbol": symbol}, timeout=15), "Korbit")
    if not body.get("success") or not body.get("data"):
        raise BrokerApiError("Korbit 공개 시세 조회가 빈 응답을 반환했습니다.")
    quote = body["data"][0]
    return {"exchange": "Korbit", "symbol": quote.get("symbol", symbol), "lastPrice": quote.get("close"), "priceChangePercent": quote.get("priceChangePercent"),
            "highPrice": quote.get("high"), "lowPrice": quote.get("low"), "volume": quote.get("volume"), "closeTime": quote.get("lastTradedAt")}


def get_korbit_orderbook(symbol: str) -> dict[str, Any]:
    body = _json(requests.get(f"{KORBIT_BASE_URL}/orderbook", params={"symbol": symbol}, timeout=15), "Korbit")
    if not body.get("success") or not isinstance(body.get("data"), dict):
        raise BrokerApiError("Korbit 공개 호가 조회가 빈 응답을 반환했습니다.")
    book = body["data"]
    return {"exchange": "Korbit", "symbol": symbol, "timestamp": book.get("timestamp"), "bids": book.get("bids", [])[:10], "asks": book.get("asks", [])[:10]}


CANDLE_INTERVALS = {"1m": "1", "5m": "5", "15m": "15", "30m": "30", "1h": "60", "4h": "240", "1d": "1D", "1w": "1W"}


def get_exchange_candles(exchange: str, symbol: str, interval: str = "1h", limit: int = 200) -> dict[str, Any]:
    if exchange not in {"binance", "korbit"} or interval not in CANDLE_INTERVALS or not 1 <= limit <= 200:
        raise BrokerApiError("지원하지 않는 거래소·봉 주기 또는 조회 개수입니다. (최대 200개)")
    if exchange == "binance":
        body = _json(requests.get(f"{BINANCE_BASE_URL}/klines", params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=15), "Binance")
        if not isinstance(body, list):
            raise BrokerApiError("Binance 캔들 응답 형식이 올바르지 않습니다.")
        raw = [dict(zip(("timestamp", "open", "high", "low", "close", "volume"), row[:6])) for row in body if isinstance(row, list)]
        source = f"{BINANCE_BASE_URL}/klines"
    else:
        body = _json(requests.get(f"{KORBIT_BASE_URL}/candles", params={"symbol": symbol, "interval": CANDLE_INTERVALS[interval], "limit": limit}, timeout=15), "Korbit")
        if not isinstance(body, dict) or not body.get("success") or not isinstance(body.get("data"), list):
            raise BrokerApiError("Korbit 캔들 조회가 유효한 응답을 반환하지 않았습니다.")
        raw = body["data"]
        source = f"{KORBIT_BASE_URL}/candles"
    candles = {}
    try:
        for row in raw:
            item = {key: float(row[key]) for key in ("open", "high", "low", "close", "volume")}
            stamp = float(row["timestamp"])
            if not all(math.isfinite(v) for v in [stamp, *item.values()]):
                raise ValueError("non-finite candle")
            item["time"] = int(stamp / 1000)
            if item["time"] <= 0 or item["volume"] < 0 or item["low"] > min(item["open"], item["close"]) or item["high"] < max(item["open"], item["close"]):
                raise ValueError("invalid candle")
            candles[item["time"]] = item
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise BrokerApiError("거래소 캔들 데이터 형식이 올바르지 않습니다.") from exc
    return {"exchange": "Binance Spot" if exchange == "binance" else "Korbit", "symbol": symbol, "interval": interval,
            "source": source, "candles": [candles[t] for t in sorted(candles)][-limit:], "fetchedAt": int(time.time() * 1000)}
