"""Server-side, read-only Alpaca Paper Trading connection test."""

from __future__ import annotations

import os
import threading
import time
from typing import Any

import requests

from broker_test import BrokerApiError, _read_key_file


ALPACA_PAPER_BASE = "https://paper-api.alpaca.markets/v2"
ALPACA_DATA_BASE = "https://data.alpaca.markets/v2"
_alpaca_order_flow_lock = threading.Lock()
_ALPACA_ORDER_TEST_SYMBOL = "AAPL"
_ALPACA_ORDER_TEST_LIMIT_PRICE = "1.00"


def _credentials() -> tuple[str, str]:
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")
    if api_key and secret_key:
        return api_key, secret_key
    return _read_key_file(
        "al.key",
        ("key", "api_key", "alpaca_api_key", "apca_api_key_id"),
        ("secret", "secret_key", "alpaca_secret_key", "apca_api_secret_key"),
    )


def _headers() -> dict[str, str]:
    api_key, secret_key = _credentials()
    return {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key}


def _get(url: str, params: dict[str, Any] | None = None) -> Any:
    response = requests.get(url, headers=_headers(), params=params, timeout=15)
    try:
        body = response.json()
    except ValueError as exc:
        raise BrokerApiError(f"Alpaca 서버가 JSON 응답을 반환하지 않았습니다. (HTTP {response.status_code})") from exc
    if not response.ok:
        message = body.get("message") or body.get("code") or "요청이 거부되었습니다."
        raise BrokerApiError(f"Alpaca API 인증 실패 (HTTP {response.status_code}): {message}")
    return body


def _request(method: str, url: str, *, json: dict[str, Any] | None = None) -> Any:
    response = requests.request(method, url, headers=_headers(), json=json, timeout=15)
    # Alpaca's successful single-order cancellation may return 204 with no
    # response body. Treat it as a success before attempting JSON parsing.
    if response.status_code == 204:
        return {}
    try:
        body = response.json()
    except ValueError as exc:
        raise BrokerApiError(f"Alpaca 서버가 JSON 응답을 반환하지 않았습니다. (HTTP {response.status_code})") from exc
    if not response.ok:
        message = body.get("message") or body.get("code") or "요청이 거부되었습니다."
        raise BrokerApiError(f"Alpaca Paper API 요청 실패 (HTTP {response.status_code}): {message}")
    return body


def test_paper_account() -> dict[str, Any]:
    """Call the read-only Paper account endpoint and return no account identifier."""
    body = _get(f"{ALPACA_PAPER_BASE}/account")
    return {
        "environment": "Paper Trading",
        "connection": "connected",
        "accountStatus": body.get("status"),
        "tradingBlocked": bool(body.get("trading_blocked")),
        "accountBlocked": bool(body.get("account_blocked")),
        "currency": body.get("currency"),
    }


def test_paper_positions() -> dict[str, Any]:
    """Read-only 보유 포지션 조회 (GET /v2/positions)."""
    body = _get(f"{ALPACA_PAPER_BASE}/positions")
    positions = [
        {
            "symbol": p.get("symbol"), "side": p.get("side"), "quantity": p.get("qty"),
            "avgEntryPrice": p.get("avg_entry_price"), "currentPrice": p.get("current_price"),
            "marketValue": p.get("market_value"), "unrealizedPl": p.get("unrealized_pl"),
            "unrealizedPlpc": p.get("unrealized_plpc"),
        }
        for p in body
    ]
    return {"environment": "Paper Trading", "positionCount": len(positions), "positions": positions}


def test_paper_orders(limit: int = 10) -> dict[str, Any]:
    """Read-only 최근 주문 내역 조회 (GET /v2/orders?status=all)."""
    body = _get(f"{ALPACA_PAPER_BASE}/orders", params={"status": "all", "limit": limit, "direction": "desc"})
    orders = [
        {
            "symbol": o.get("symbol"), "side": o.get("side"), "type": o.get("type"),
            "quantity": o.get("qty"), "status": o.get("status"),
            "filledAvgPrice": o.get("filled_avg_price"), "submittedAt": o.get("submitted_at"),
        }
        for o in body
    ]
    return {"environment": "Paper Trading", "orderCount": len(orders), "orders": orders}


def test_market_clock() -> dict[str, Any]:
    """Read-only 미국 증시 개장 여부 조회 (GET /v2/clock)."""
    body = _get(f"{ALPACA_PAPER_BASE}/clock")
    return {
        "isOpen": bool(body.get("is_open")), "timestamp": body.get("timestamp"),
        "nextOpen": body.get("next_open"), "nextClose": body.get("next_close"),
    }


def test_market_quote(symbol: str) -> dict[str, Any]:
    """Read-only 최근 호가·체결 조회 (Market Data API, /v2/stocks/{symbol}/quotes|trades/latest)."""
    symbol = symbol.upper()
    quote_body = _get(f"{ALPACA_DATA_BASE}/stocks/{symbol}/quotes/latest")
    trade_body = _get(f"{ALPACA_DATA_BASE}/stocks/{symbol}/trades/latest")
    quote = quote_body.get("quote", {})
    trade = trade_body.get("trade", {})
    return {
        "symbol": symbol,
        "bidPrice": quote.get("bp"), "bidSize": quote.get("bs"),
        "askPrice": quote.get("ap"), "askSize": quote.get("as"),
        "lastTradePrice": trade.get("p"), "lastTradeSize": trade.get("s"),
        "lastTradeTime": trade.get("t"),
    }


def run_paper_order_flow_test() -> dict[str, Any]:
    """Submit one deliberately non-marketable Paper limit order, then cancel it.

    This is intentionally not a general order endpoint. The fixed $1 AAPL buy
    limit is only accepted when the live ask is safely above it, and the order
    is cancelled in ``finally`` so a user-triggered test cannot leave an open
    Paper order under normal API operation.
    """
    if not _alpaca_order_flow_lock.acquire(blocking=False):
        raise BrokerApiError("Alpaca Paper 주문 흐름 테스트가 이미 실행 중입니다. 잠시 후 다시 시도하세요.")
    try:
        quote = test_market_quote(_ALPACA_ORDER_TEST_SYMBOL)
        ask = quote.get("askPrice")
        if not isinstance(ask, (int, float)) or ask <= 2:
            raise BrokerApiError("안전 가격을 확인할 수 없어 주문을 보내지 않았습니다. AAPL 매도호가가 $2보다 큰 경우에만 테스트합니다.")

        client_order_id = f"edumgt-paper-{int(time.time() * 1000)}"
        order = _request(
            "POST",
            f"{ALPACA_PAPER_BASE}/orders",
            json={
                "symbol": _ALPACA_ORDER_TEST_SYMBOL,
                "qty": "1",
                "side": "buy",
                "type": "limit",
                "time_in_force": "day",
                "limit_price": _ALPACA_ORDER_TEST_LIMIT_PRICE,
                "client_order_id": client_order_id,
            },
        )
        order_id = order.get("id")
        if not order_id:
            raise BrokerApiError("Paper 주문 응답에 주문 식별자가 없어 취소를 진행하지 않았습니다. 대시보드에서 미체결 주문을 확인하세요.")
        try:
            cancel = _request("DELETE", f"{ALPACA_PAPER_BASE}/orders/{order_id}")
            cancel_status = cancel.get("status") or "accepted"
        except BrokerApiError as exc:
            raise BrokerApiError(f"Paper 주문은 접수됐지만 자동 취소에 실패했습니다. Paper 대시보드에서 미체결 주문을 확인하세요. ({exc})") from exc
        return {
            "environment": "Paper Trading",
            "symbol": _ALPACA_ORDER_TEST_SYMBOL,
            "askPrice": ask,
            "testLimitPrice": _ALPACA_ORDER_TEST_LIMIT_PRICE,
            "quantity": 1,
            "order": "accepted",
            "cancel": cancel_status,
        }
    finally:
        _alpaca_order_flow_lock.release()
