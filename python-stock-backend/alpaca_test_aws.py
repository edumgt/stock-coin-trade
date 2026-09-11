"""Read-only Alpaca Paper Trading checks sourced from AWS SSM Parameter Store.

Parallel track to ``alpaca_test.py``: the same read-only Paper endpoints, but
the API Key/Secret come from AWS Systems Manager Parameter Store instead of
``al.key`` or ``ALPACA_API_KEY``/``ALPACA_SECRET_KEY``. ``alpaca_test.py``
itself is not modified or used by this module.
"""

from __future__ import annotations

from typing import Any

import requests

from aws_secret_store import AwsSecretError, get_credentials


ALPACA_PAPER_BASE = "https://paper-api.alpaca.markets/v2"


def _headers() -> dict[str, str]:
    api_key, secret_key = get_credentials("alpaca", key_name="api_key", secret_name="secret_key")
    return {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key}


def _get(url: str, params: dict[str, Any] | None = None) -> Any:
    response = requests.get(url, headers=_headers(), params=params, timeout=15)
    try:
        body = response.json()
    except ValueError as exc:
        raise AwsSecretError(f"Alpaca 서버가 JSON 응답을 반환하지 않았습니다. (HTTP {response.status_code})") from exc
    if not response.ok:
        message = body.get("message") or body.get("code") or "요청이 거부되었습니다."
        raise AwsSecretError(f"Alpaca API 인증 실패 (HTTP {response.status_code}): {message}")
    return body


def test_paper_account_aws() -> dict[str, Any]:
    """Call the read-only Paper account endpoint and return no account identifier."""
    body = _get(f"{ALPACA_PAPER_BASE}/account")
    return {
        "environment": "Paper Trading (AWS SSM)",
        "connection": "connected",
        "accountStatus": body.get("status"),
        "tradingBlocked": bool(body.get("trading_blocked")),
        "accountBlocked": bool(body.get("account_blocked")),
        "currency": body.get("currency"),
    }


def test_paper_positions_aws() -> dict[str, Any]:
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
    return {"environment": "Paper Trading (AWS SSM)", "positionCount": len(positions), "positions": positions}


def test_paper_clock_aws() -> dict[str, Any]:
    """Read-only market clock check (GET /v2/clock)."""
    body = _get(f"{ALPACA_PAPER_BASE}/clock")
    return {
        "environment": "Paper Trading (AWS SSM)", "isOpen": bool(body.get("is_open")),
        "timestamp": body.get("timestamp"), "nextOpen": body.get("next_open"), "nextClose": body.get("next_close"),
    }


def test_paper_asset_aws(symbol: str) -> dict[str, Any]:
    """Read-only asset metadata check (GET /v2/assets/{symbol})."""
    body = _get(f"{ALPACA_PAPER_BASE}/assets/{symbol}")
    return {
        "environment": "Paper Trading (AWS SSM)", "symbol": body.get("symbol"),
        "name": body.get("name"), "status": body.get("status"), "tradable": bool(body.get("tradable")),
        "fractionable": bool(body.get("fractionable")), "shortable": bool(body.get("shortable")),
    }
