"""Read-only public market-data checks for Binance Spot and Korbit."""

from __future__ import annotations

from typing import Any

import requests

from broker_test import BrokerApiError


BINANCE_BASE_URL = "https://api.binance.com/api/v3"
KORBIT_BASE_URL = "https://api.korbit.co.kr/v2"


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
    return {"exchange": "Binance Spot", "symbol": symbol, "lastPrice": body.get("lastPrice"), "priceChangePercent": body.get("priceChangePercent"), "highPrice": body.get("highPrice"), "lowPrice": body.get("lowPrice"), "volume": body.get("volume"), "closeTime": body.get("closeTime")}


def get_binance_orderbook(symbol: str) -> dict[str, Any]:
    body = _json(requests.get(f"{BINANCE_BASE_URL}/depth", params={"symbol": symbol, "limit": 10}, timeout=15), "Binance")
    return {"exchange": "Binance Spot", "symbol": symbol, "lastUpdateId": body.get("lastUpdateId"), "bids": body.get("bids", []), "asks": body.get("asks", [])}


def get_korbit_ticker(symbol: str) -> dict[str, Any]:
    body = _json(requests.get(f"{KORBIT_BASE_URL}/tickers", params={"symbol": symbol}, timeout=15), "Korbit")
    if not body.get("success") or not body.get("data"):
        raise BrokerApiError("Korbit 공개 시세 조회가 빈 응답을 반환했습니다.")
    quote = body["data"][0]
    return {"exchange": "Korbit", "symbol": quote.get("symbol", symbol), "lastPrice": quote.get("close"), "priceChangePercent": quote.get("priceChangePercent"), "highPrice": quote.get("high"), "lowPrice": quote.get("low"), "volume": quote.get("volume"), "closeTime": quote.get("lastTradedAt")}


def get_korbit_orderbook(symbol: str) -> dict[str, Any]:
    body = _json(requests.get(f"{KORBIT_BASE_URL}/orderbook", params={"symbol": symbol}, timeout=15), "Korbit")
    if not body.get("success") or not isinstance(body.get("data"), dict):
        raise BrokerApiError("Korbit 공개 호가 조회가 빈 응답을 반환했습니다.")
    book = body["data"]
    return {"exchange": "Korbit", "symbol": symbol, "timestamp": book.get("timestamp"), "bids": book.get("bids", [])[:10], "asks": book.get("asks", [])[:10]}
