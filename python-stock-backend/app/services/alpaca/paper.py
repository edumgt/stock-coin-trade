"""서버 측 읽기 전용 Alpaca Paper Trading 연결 테스트."""

from __future__ import annotations

import os
import threading
import time
from typing import Any
from urllib.parse import urlsplit

import requests

from app.services.brokers.common import BrokerApiError, credential_source

ALPACA_PAPER_BASE = "https://paper-api.alpaca.markets/v2"
ALPACA_DATA_BASE = "https://data.alpaca.markets/v2"
_alpaca_order_flow_lock = threading.Lock()
_ALPACA_ORDER_TEST_SYMBOL = "AAPL"
_ALPACA_ORDER_TEST_LIMIT_PRICE = "1.00"


def _aws_alpaca_credentials() -> tuple[str, str]:
    try:
        from app.services.aws_secret_store import AwsSecretError, get_credentials
    except Exception as exc:  # boto3 미설치 등
        raise BrokerApiError("AWS Secrets Manager 연동 모듈을 불러오지 못했습니다.", 503) from exc
    try:
        return get_credentials("alpaca", key_name="api_key", secret_name="secret_key")
    except AwsSecretError as exc:
        raise BrokerApiError(str(exc), 503) from exc


def get_alpaca_configuration_status() -> dict[str, Any]:
    """자격증명 값을 노출하지 않고 Paper 준비 상태만 반환한다."""
    common = {
        "tradingEndpoint": ALPACA_PAPER_BASE,
        "dataEndpoint": ALPACA_DATA_BASE,
        "mode": "paper",
        "liveEnabled": False,
    }
    if credential_source() == "aws":
        secret_name = "stock-coin-trade/alpaca"
        try:
            from app.services.aws_secret_store import full_secret_name

            secret_name = full_secret_name("alpaca")
        except Exception:
            pass
        configured, message = False, None
        try:
            _aws_alpaca_credentials()
            configured = True
        except BrokerApiError as exc:
            message = str(exc)
        result = {"configured": configured, "source": "aws-secrets-manager", "secret": secret_name, **common}
        if message:
            result["message"] = message
        return result
    env_key = bool(os.environ.get("ALPACA_API_KEY", "").strip())
    env_secret = bool(os.environ.get("ALPACA_SECRET_KEY", "").strip())
    env_complete = env_key and env_secret
    return {
        "configured": env_complete,
        "source": "environment" if env_complete else "missing",
        "environment": {"apiKey": env_key, "secretKey": env_secret, "complete": env_complete},
        **common,
    }


def _audit_alpaca_call(**kwargs) -> None:
    try:
        from app.services.api_usage import record_alpaca_gateway_call

        record_alpaca_gateway_call(**kwargs)
    except Exception:
        pass


def _audit_response_summary(body: Any) -> dict[str, Any]:
    """계좌·주문 식별자는 빼고 진단에 유용한 값만 남긴다."""
    if isinstance(body, list):
        return {"itemCount": len(body)}
    if not isinstance(body, dict):
        return {"dataPresent": body is not None}
    summary = {"dataPresent": bool(body)}
    for key in ("message", "code", "status", "symbol", "side", "type", "qty", "filled_qty", "is_open"):
        if body.get(key) is not None:
            summary[key] = body.get(key)
    if isinstance(body.get("quote"), dict):
        summary["quotePresent"] = True
    if isinstance(body.get("trade"), dict):
        summary["tradePresent"] = True
    return summary


def _credentials() -> tuple[str, str]:
    if credential_source() == "aws":
        return _aws_alpaca_credentials()
    api_key = os.environ.get("ALPACA_API_KEY", "").strip()
    secret_key = os.environ.get("ALPACA_SECRET_KEY", "").strip()
    if api_key and secret_key:
        return api_key, secret_key
    raise BrokerApiError(".env에 ALPACA_API_KEY와 ALPACA_SECRET_KEY를 모두 설정하세요.", 503)


def _headers() -> dict[str, str]:
    api_key, secret_key = _credentials()
    return {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key}


def _get(url: str, params: dict[str, Any] | None = None) -> Any:
    started = time.perf_counter()
    path = urlsplit(url).path
    try:
        response = requests.get(url, headers=_headers(), params=params, timeout=15)
    except requests.RequestException:
        _audit_alpaca_call(method="GET", path=path, label="Alpaca 조회", request_data=params,
                           http_status=503, response_body={}, duration_ms=(time.perf_counter() - started) * 1000,
                           success=False, error="Alpaca 서버 연결 실패")
        raise
    try:
        body = response.json()
    except ValueError as exc:
        _audit_alpaca_call(method="GET", path=path, label="Alpaca 조회", request_data=params,
                           http_status=response.status_code, response_body={}, duration_ms=(time.perf_counter() - started) * 1000,
                           success=False, error="JSON 응답 아님")
        raise BrokerApiError(f"Alpaca 서버가 JSON 응답을 반환하지 않았습니다. (HTTP {response.status_code})") from exc
    if not response.ok:
        message = body.get("message") or body.get("code") or "요청이 거부되었습니다."
        _audit_alpaca_call(method="GET", path=path, label="Alpaca 조회", request_data=params,
                           http_status=response.status_code, response_body=_audit_response_summary(body),
                           duration_ms=(time.perf_counter() - started) * 1000, success=False, error=message)
        raise BrokerApiError(f"Alpaca API 인증 실패 (HTTP {response.status_code}): {message}")
    _audit_alpaca_call(method="GET", path=path, label="Alpaca 조회", request_data=params,
                       http_status=response.status_code, response_body=_audit_response_summary(body),
                       duration_ms=(time.perf_counter() - started) * 1000, success=True)
    return body


def _request(method: str, url: str, *, json: dict[str, Any] | None = None) -> Any:
    started = time.perf_counter()
    path = urlsplit(url).path
    if str(method).upper() == "DELETE" and path.startswith("/v2/orders/"):
        path = "/v2/orders/{order_id}"
    safe_request = {key: value for key, value in (json or {}).items() if key != "client_order_id"}
    try:
        response = requests.request(method, url, headers=_headers(), json=json, timeout=15)
    except requests.RequestException:
        _audit_alpaca_call(method=method, path=path, label="Paper 주문 흐름", request_data=safe_request,
                           http_status=503, response_body={}, duration_ms=(time.perf_counter() - started) * 1000,
                           success=False, error="Alpaca 서버 연결 실패")
        raise
    # Alpaca의 단건 주문 취소 성공은 본문 없는 204일 수 있다. JSON 파싱 전에 성공으로 처리한다.
    if response.status_code == 204:
        _audit_alpaca_call(method=method, path=path, label="Paper 주문 흐름", request_data=safe_request,
                           http_status=204, response_body={"status": "accepted"},
                           duration_ms=(time.perf_counter() - started) * 1000, success=True)
        return {}
    try:
        body = response.json()
    except ValueError as exc:
        _audit_alpaca_call(method=method, path=path, label="Paper 주문 흐름", request_data=safe_request,
                           http_status=response.status_code, response_body={}, duration_ms=(time.perf_counter() - started) * 1000,
                           success=False, error="JSON 응답 아님")
        raise BrokerApiError(f"Alpaca 서버가 JSON 응답을 반환하지 않았습니다. (HTTP {response.status_code})") from exc
    if not response.ok:
        message = body.get("message") or body.get("code") or "요청이 거부되었습니다."
        _audit_alpaca_call(method=method, path=path, label="Paper 주문 흐름", request_data=safe_request,
                           http_status=response.status_code, response_body=_audit_response_summary(body),
                           duration_ms=(time.perf_counter() - started) * 1000, success=False, error=message)
        raise BrokerApiError(f"Alpaca Paper API 요청 실패 (HTTP {response.status_code}): {message}")
    _audit_alpaca_call(method=method, path=path, label="Paper 주문 흐름", request_data=safe_request,
                       http_status=response.status_code, response_body=_audit_response_summary(body),
                       duration_ms=(time.perf_counter() - started) * 1000, success=True)
    return body


def test_paper_account() -> dict[str, Any]:
    """읽기 전용 Paper 계좌 엔드포인트를 호출하고 계좌 식별자는 돌려주지 않는다."""
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
    """읽기 전용 보유 포지션 조회 (GET /v2/positions)."""
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
    """읽기 전용 최근 주문 내역 조회 (GET /v2/orders?status=all)."""
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
    """읽기 전용 미국 증시 개장 여부 조회 (GET /v2/clock)."""
    body = _get(f"{ALPACA_PAPER_BASE}/clock")
    return {
        "isOpen": bool(body.get("is_open")), "timestamp": body.get("timestamp"),
        "nextOpen": body.get("next_open"), "nextClose": body.get("next_close"),
    }


def test_market_quote(symbol: str) -> dict[str, Any]:
    """읽기 전용 최근 호가·체결 조회 (Market Data API)."""
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
    """의도적으로 비시장성인 Paper 지정가 주문 1건을 내고 바로 취소한다.

    일반 주문 엔드포인트가 아니다. $1 AAPL 매수 지정가는 실시간 매도호가가 충분히 높을 때만
    보내며, 테스트가 미체결 Paper 주문을 남기지 않도록 취소까지 한 흐름으로 수행한다.
    """
    if not _alpaca_order_flow_lock.acquire(blocking=False):
        raise BrokerApiError("Alpaca Paper 주문 흐름 테스트가 이미 실행 중입니다. 잠시 후 다시 시도하세요.")
    try:
        # 외부 주문 API를 호출하기 전에 미국 증시 개장 여부를 먼저 확인한다.
        clock = test_market_clock()
        if not clock.get("isOpen"):
            next_open = clock.get("nextOpen")
            raise BrokerApiError(
                "미국 증시가 휴장 중입니다. 개장 시간에 다시 실행하세요." + (f" 다음 개장: {next_open}" if next_open else ""),
                code="MARKET_CLOSED",
            )
        quote = test_market_quote(_ALPACA_ORDER_TEST_SYMBOL)
        ask = quote.get("askPrice")
        if not isinstance(ask, int | float) or ask <= 2:
            raise BrokerApiError(
                "실시간 매도호가를 확인할 수 없어 주문을 보내지 않았습니다. 개장 직후에는 잠시 후 다시 시도하세요.",
                code="NO_SAFE_PRICE",
            )

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
