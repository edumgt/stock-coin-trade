"""KB증권 Open API 읽기 전용 게이트웨이(토큰 발급·투자정보 TR)."""

from __future__ import annotations

import os
import socket
import threading
import time
import uuid
from typing import Any

import requests

from app.services.brokers.common import BrokerApiError
from app.services.brokers.common import env_credentials as _credentials
from app.services.brokers.common import json_body as _json

KB_API_BASE_URL = "https://developer.kbsec.com:32484"
_kb_chart_cache: dict[str, dict[str, Any]] = {}
_kb_chart_lock = threading.Lock()
_KB_CHART_CACHE_SECONDS = 30


def get_kb_configuration_status() -> dict[str, Any]:
    """자격증명 값을 돌려주지 않고 KB 준비 상태만 반환한다."""
    env_key = bool(os.environ.get("KB_APP_KEY", "").strip())
    env_secret = bool(os.environ.get("KB_APP_SECRET", "").strip())
    env_complete = env_key and env_secret
    return {
        "configured": env_complete, "source": "environment" if env_complete else "missing",
        "environment": {"appKey": env_key, "appSecret": env_secret, "complete": env_complete},
        "endpoint": KB_API_BASE_URL, "mode": "production", "readOnly": True,
    }


def _audit_kb_call(**kwargs) -> None:
    try:
        from app.services.api_usage import record_kb_gateway_call

        record_kb_gateway_call(**kwargs)
    except Exception:
        pass


def _kb_token_response() -> dict[str, Any]:
    app_key, app_secret = _credentials("KB")
    started = time.perf_counter()
    try:
        response = requests.post(
            f"{KB_API_BASE_URL}/oauth2/token",
            headers={"Content-Type": "application/json"},
            # 공식 샘플 저장소의 B2C 프록시가 쓰는 공통 봉투.
            json={
                "dataHeader": {"ipAddr": "", "macAddr": ""},
                "dataBody": {"appKey": app_key, "appSecret": app_secret, "grantType": "client_credentials"},
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        _audit_kb_call(method="POST", path="/oauth2/token", tr_id="OAUTH", label="토큰 발급", request_data={},
                       http_status=503, response_body={}, duration_ms=(time.perf_counter() - started) * 1000,
                       success=False, error="KB증권 서버 연결 실패")
        raise exc
    body = _json(response, "KB증권")
    token = body.get("access_token") or body.get("dataBody", {}).get("access_token")
    header = body.get("dataHeader", {})
    code = header.get("processCode") or body.get("error") or body.get("code")
    message = header.get("processMessage") or body.get("error_description") or body.get("message")
    _audit_kb_call(
        method="POST", path="/oauth2/token", tr_id="OAUTH", label="토큰 발급", request_data={},
        http_status=response.status_code,
        response_body={"tokenIssued": bool(token), "tokenType": body.get("token_type") or body.get("dataBody", {}).get("token_type"),
                       "processCode": code, "processMessage": message},
        duration_ms=(time.perf_counter() - started) * 1000, success=bool(response.ok and token),
        error=None if token else message or "토큰 발급 실패",
    )
    if token:
        return body
    raise BrokerApiError(f"KB증권 인증 실패 (HTTP {response.status_code}, {code or 'unknown'}): {message or '토큰 발급 실패'}")


def _kb_data_header() -> dict[str, str]:
    """공식 KB 테스트 앱이 보내는 B2C 단말 헤더를 만든다."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        ip_addr = sock.getsockname()[0]
    except OSError:
        ip_addr = "127.0.0.1"
    finally:
        sock.close()
    node = uuid.getnode()
    mac_addr = ":".join(f"{(node >> shift) & 0xFF:02X}" for shift in range(40, -1, -8))
    return {"ipAddr": ip_addr, "macAddr": mac_addr}


def check_kb_token() -> dict[str, Any]:
    """KB Open API OAuth 토큰 발급만 검증한다(시세 API는 포털 승인 API 그룹이 필요)."""
    body = _kb_token_response()
    token_type = body.get("token_type") or body.get("dataBody", {}).get("token_type") or "Bearer"
    expires_in = body.get("expires_in") or body.get("dataBody", {}).get("expires_in") or 0
    return {"broker": "KB증권 Open API", "tokenType": token_type, "expiresIn": int(expires_in)}


def _kb_investment_info(endpoint: str, data_body: dict[str, str]) -> dict[str, Any]:
    """읽기 전용 KB B2C 투자정보 TR을 호출한다."""
    app_key, _ = _credentials("KB")
    token_body = _kb_token_response()
    access_token = token_body.get("access_token") or token_body.get("dataBody", {}).get("access_token")
    started = time.perf_counter()
    try:
        response = requests.post(
            f"{KB_API_BASE_URL}{endpoint}",
            headers={"Content-Type": "application/json", "Authorization": f"bearer {access_token}", "appKey": app_key},
            json={"dataHeader": _kb_data_header(), "dataBody": data_body},
            timeout=20,
        )
    except requests.RequestException as exc:
        _audit_kb_call(method="POST", path=endpoint, tr_id=endpoint.rsplit("/", 1)[-1].upper(), label="운영 조회",
                       request_data=data_body, http_status=503, response_body={},
                       duration_ms=(time.perf_counter() - started) * 1000, success=False, error="KB증권 서버 연결 실패")
        raise exc
    body = _json(response, "KB증권")
    header = body.get("dataHeader", {})
    code = str(header.get("processCode") or "")
    # KB TR은 전부 0인 성공 코드와 0024(정상 조회 완료)를 함께 쓴다.
    business_ok = not code or set(code) == {"0"} or code == "0024"
    success = bool(response.ok and business_ok)
    _audit_kb_call(
        method="POST", path=endpoint, tr_id=endpoint.rsplit("/", 1)[-1].upper(), label="운영 조회",
        request_data=data_body, http_status=response.status_code,
        response_body={"processCode": code or None, "processMessage": header.get("processMessage"),
                       "dataPresent": body.get("dataBody") is not None},
        duration_ms=(time.perf_counter() - started) * 1000, success=success,
        error=None if success else header.get("processMessage") or "KB증권 조회 실패",
    )
    if not success:
        raise BrokerApiError(
            f"KB증권 조회 실패 (HTTP {response.status_code}, {header.get('processCode') or 'unknown'}): "
            f"{header.get('processMessage') or '요청이 거부되었습니다.'}"
        )
    return body.get("dataBody", {})


def get_kb_domestic_quote(symbol: str) -> dict[str, Any]:
    """공식 KB B2C 국내주식 현재가 TR(IVU10140)."""
    return {"broker": "KB증권 Open API", "symbol": symbol, "raw": _kb_investment_info("/api/v1/ivu10140", {"excg_clsf": "1", "shrt_cd": symbol})}


def get_kb_stock_base_info(symbol: str) -> dict[str, Any]:
    return {"broker": "KB증권 Open API", "symbol": symbol, "raw": _kb_investment_info("/api/v1/siqm4900", {"stnd_is_cd": symbol})}


def get_kb_stock_orderbook(symbol: str) -> dict[str, Any]:
    return {"broker": "KB증권 Open API", "symbol": symbol, "raw": _kb_investment_info("/api/v1/ivu10070", {"is_cd": symbol, "ovtm_mkt_clsf": "0"})}


def _kb_number(value: Any, *, integer: bool = False) -> int | float | None:
    raw = str(value or "").strip().replace(",", "")
    if not raw:
        return None
    try:
        number = float(raw)
        return int(number) if integer else number
    except ValueError:
        return None


def get_kb_stock_chart(symbol: str, market: str = "0", period: str = "D", count: int = 60) -> dict[str, Any]:
    """KB IVS11560만을 원천으로 정규화한 OHLCV 캔들을 반환한다."""
    if market not in {"0", "1"}:
        raise BrokerApiError("시장은 KOSPI(0) 또는 KOSDAQ(1)만 선택할 수 있습니다.", 400)
    if period not in {"D", "W", "M", "Y"}:
        raise BrokerApiError("차트 주기는 일·주·월·년만 지원합니다.", 400)
    if not 10 <= count <= 300:
        raise BrokerApiError("캔들 수는 10~300 사이여야 합니다.", 400)
    cache_key = f"{symbol}:{market}:{period}:{count}"
    now = time.monotonic()
    with _kb_chart_lock:
        cached = _kb_chart_cache.get(cache_key)
        if cached and now - cached["savedAt"] < _KB_CHART_CACHE_SECONDS:
            return cached["value"]

    raw = _kb_investment_info(
        "/api/v1/ivs11560",
        {
            "info_ccd": "1", "mkt_clsf": market, "chrt_clsf": period,
            "minute_tck_indx": "", "is_cd": symbol, "inq_clsf": "2",
            "strt_dy": "", "inq_cnt": str(count),
        },
    )
    candles = []
    for row in raw.get("out2", []):
        date_value = str(row.get("dt") or "").strip()
        if len(date_value) != 8 or not date_value.isdigit():
            continue
        candle = {
            "time": f"{date_value[:4]}-{date_value[4:6]}-{date_value[6:]}",
            "open": _kb_number(row.get("opn_prc_p2")),
            "high": _kb_number(row.get("hgh_prc_p2")),
            "low": _kb_number(row.get("lw_prc_p2")),
            "close": _kb_number(row.get("cls_prc_p2")),
            "volume": _kb_number(row.get("vlm"), integer=True),
            "amount": _kb_number(row.get("dl_tw_amt"), integer=True),
        }
        if all(candle[key] is not None for key in ("open", "high", "low", "close")):
            candles.append(candle)
    candles.sort(key=lambda item: item["time"])
    result = {
        "broker": "KB증권 Open API", "source": "IVS11560",
        "symbol": symbol, "market": "KOSPI" if market == "0" else "KOSDAQ",
        "period": period, "count": len(candles), "candles": candles,
    }
    with _kb_chart_lock:
        _kb_chart_cache[cache_key] = {"savedAt": now, "value": result}
    return result
