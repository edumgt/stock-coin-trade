"""Read-only broker OpenAPI quote checks used by the local test web page.

Credentials stay in server environment variables loaded from ``.env``. They
are never returned or logged; the browser only receives normalized data.
"""

from __future__ import annotations

import os
import socket
import threading
import time
import uuid
from collections import OrderedDict
from typing import Any

import requests


KB_API_BASE_URL = "https://developer.kbsec.com:32484"
KIS_TESTBED_URL = "https://openapivts.koreainvestment.com:29443"
_kis_token_cache: dict[str, Any] = {"value": None, "expires_at": 0.0}
_kb_chart_cache: dict[str, dict[str, Any]] = {}
_kb_chart_lock = threading.Lock()
_KB_CHART_CACHE_SECONDS = 30
_kis_token_lock = threading.Lock()
_kis_quote_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
_kis_quote_lock = threading.Lock()
_kis_order_flow_lock = threading.Lock()
_kis_paper_order_lock = threading.Lock()
_kis_api_rate_lock = threading.Lock()
_kis_last_api_call_at = 0.0
_KIS_API_CALL_GAP_SECONDS = 1.05
_KIS_RATE_LIMIT_CODE = "EGW00201"
_KIS_QUOTE_CACHE_MAX = 256
_KIS_ORDER_TEST_SYMBOL = "005930"
# 지정가는 현재가의 90%(호가 단위 내림)로 계산해 비시장성 매수 주문만 낸다. 고정
# 가격을 쓰면 주가 구간이 바뀔 때 하한가(-30%) 밖이 되거나 체결 위험이 생긴다.
_KIS_ORDER_TEST_PRICE_RATIO = 0.90
_KIS_ORDER_TEST_MAX_PRICE_RATIO = 0.95  # 이 비율 이상이면 체결 위험으로 보고 주문하지 않는다.


class BrokerApiError(RuntimeError):
    """A user-safe error that never includes credentials or access tokens."""

    def __init__(self, message: str, status_code: int = 502, code: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def _credential_source() -> str:
    """자격증명 출처. 서버(EC2)는 .env의 ``CREDENTIAL_SOURCE=aws``로 AWS Secrets
    Manager를 쓰고, 로컬은 값을 비워 .env 환경변수를 쓴다."""
    raw = os.environ.get("CREDENTIAL_SOURCE", "").strip().lower()
    if raw in ("aws", "sm", "secrets-manager", "secretsmanager", "secrets_manager"):
        return "aws"
    return "env"


def _aws_credentials(service: str) -> tuple[str, str]:
    try:
        from aws_secret_store import AwsSecretError, get_credentials
    except Exception as exc:  # boto3 미설치 등
        raise BrokerApiError("AWS Secrets Manager 연동 모듈을 불러오지 못했습니다.", 503) from exc
    try:
        return get_credentials(service)
    except AwsSecretError as exc:
        raise BrokerApiError(str(exc), 503) from exc


def _credentials(prefix: str) -> tuple[str, str]:
    if _credential_source() == "aws":
        return _aws_credentials(prefix.lower())
    app_key = os.environ.get(f"{prefix}_APP_KEY", "").strip()
    app_secret = os.environ.get(f"{prefix}_APP_SECRET", "").strip()
    if not app_key or not app_secret:
        raise BrokerApiError(f".env에 {prefix}_APP_KEY와 {prefix}_APP_SECRET을 모두 설정하세요.", 503)
    return app_key, app_secret


def get_kb_configuration_status() -> dict[str, Any]:
    """Return KB credential readiness without returning any credential value."""
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
        from api_usage import record_kb_gateway_call
        record_kb_gateway_call(**kwargs)
    except Exception:
        pass


def _json(response: requests.Response, broker: str) -> dict[str, Any]:
    try:
        return response.json()
    except ValueError as exc:
        raise BrokerApiError(f"{broker} 서버가 JSON 응답을 반환하지 않았습니다. (HTTP {response.status_code})") from exc


def _kb_token_response() -> dict[str, Any]:
    app_key, app_secret = _credentials("KB")
    started = time.perf_counter()
    try:
        response = requests.post(
            f"{KB_API_BASE_URL}/oauth2/token",
            headers={"Content-Type": "application/json"},
            # The official sample repository's B2C proxy uses this common envelope.
            json={
                "dataHeader": {"ipAddr": "", "macAddr": ""},
                "dataBody": {
                    "appKey": app_key,
                    "appSecret": app_secret,
                    "grantType": "client_credentials",
                },
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
    """Build the B2C device header the official KB test app supplies."""
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
    """Verify KB Open API OAuth token issuance only.

    KB's quote API requires a portal-approved API group that this project does
    not currently have, so the connection test is limited to confirming that
    AppKey/AppSecret correctly issue an access token — mirroring kb_token_test.py.
    """
    body = _kb_token_response()
    token_type = body.get("token_type") or body.get("dataBody", {}).get("token_type") or "Bearer"
    expires_in = body.get("expires_in") or body.get("dataBody", {}).get("expires_in") or 0
    return {"broker": "KB증권 Open API", "tokenType": token_type, "expiresIn": int(expires_in)}


def _kb_investment_info(endpoint: str, data_body: dict[str, str]) -> dict[str, Any]:
    """Call a read-only KB B2C investment-information TR."""
    app_key, _ = _credentials("KB")
    token_body = _kb_token_response()
    access_token = token_body.get("access_token") or token_body.get("dataBody", {}).get("access_token")
    started = time.perf_counter()
    try:
        response = requests.post(
            f"{KB_API_BASE_URL}{endpoint}",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"bearer {access_token}",
                "appKey": app_key,
            },
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
    # KB TRs use both all-zero success codes and 0024 (normal query complete).
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
    """Call the official KB B2C domestic-stock current-price TR (IVU10140)."""
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
    """Return normalized OHLCV candles sourced only from KB IVS11560."""
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


def _kis_credentials() -> tuple[str, str]:
    if os.environ.get("KIS_ENVIRONMENT", "paper").strip().lower() != "paper":
        raise BrokerApiError("이 서비스는 KIS 모의투자(paper) 환경만 허용합니다.", 503)
    if _credential_source() == "aws":
        return _aws_credentials("kis")
    paper_key = os.environ.get("KIS_PAPER_APP_KEY")
    paper_secret = os.environ.get("KIS_PAPER_APP_SECRET")
    if paper_key or paper_secret:
        if not paper_key or not paper_secret:
            raise BrokerApiError("KIS_PAPER_APP_KEY와 KIS_PAPER_APP_SECRET을 함께 설정하세요.", 503)
        return paper_key, paper_secret
    raise BrokerApiError(".env에 KIS_PAPER_APP_KEY와 KIS_PAPER_APP_SECRET을 설정하세요.", 503)


def _kis_account() -> tuple[str, str]:
    account_no = os.environ.get("KIS_PAPER_ACCOUNT_NO")
    if not account_no and _credential_source() == "aws":
        try:
            from aws_secret_store import AwsSecretError, get_parameter
            account_no = get_parameter("kis/account")
        except AwsSecretError as exc:
            raise BrokerApiError(str(exc), 503) from exc
    if not account_no or "-" not in account_no:
        raise BrokerApiError(
            "모의투자 계좌번호가 설정되지 않았습니다. .env의 KIS_PAPER_ACCOUNT_NO에 "
            "'CANO-계좌상품코드'(예: 12345678-01) 형식으로 설정하세요.",
            503,
        )
    cano, _, acnt_prdt_cd = account_no.partition("-")
    if not (cano.isdigit() and len(cano) == 8 and acnt_prdt_cd.isdigit() and len(acnt_prdt_cd) == 2):
        raise BrokerApiError("KIS 계좌번호는 '8자리 CANO-2자리 상품코드' 형식이어야 합니다.", 503)
    return cano, acnt_prdt_cd


def _audit_kis_call(**kwargs) -> None:
    """Lazy import keeps standalone quote helpers usable without a Flask app."""
    try:
        from api_usage import record_kis_gateway_call
        record_kis_gateway_call(**kwargs)
    except Exception:
        pass


def _kis_access_token() -> str:
    app_key, app_secret = _kis_credentials()
    with _kis_token_lock:
        access_token = _kis_token_cache["value"] if _kis_token_cache["expires_at"] > time.time() else None
        if access_token:
            return access_token
        token_payload = {"grant_type": "client_credentials", "appkey": app_key, "appsecret": app_secret}
        started = time.perf_counter()
        try:
            token_response = requests.post(
                f"{KIS_TESTBED_URL}/oauth2/tokenP",
                headers={"content-type": "application/json; charset=utf-8"},
                json=token_payload,
                timeout=15,
            )
            token_body = _json(token_response, "한국투자증권")
        except (requests.RequestException, BrokerApiError) as exc:
            _audit_kis_call(
                method="POST", path="/oauth2/tokenP", tr_id="OAUTH", label="접근 토큰 발급",
                attempt=1, request_data={"json": token_payload}, http_status=503,
                response_body={}, duration_ms=(time.perf_counter() - started) * 1000,
                success=False, error=str(exc),
            )
            raise
        access_token = token_body.get("access_token")
        token_success = bool(access_token)
        _audit_kis_call(
            method="POST", path="/oauth2/tokenP", tr_id="OAUTH", label="접근 토큰 발급",
            attempt=1, request_data={"json": token_payload}, http_status=token_response.status_code,
            response_body=token_body, duration_ms=(time.perf_counter() - started) * 1000,
            success=token_success,
            error=None if token_success else (token_body.get("error_description") or token_body.get("msg1")),
        )
        if not access_token:
            message = token_body.get("error_description") or token_body.get("msg1") or "토큰 발급 실패"
            raise BrokerApiError(f"한국투자증권 인증 실패 (HTTP {token_response.status_code}): {message}")
        # KIS tokens are normally valid for a day. Keep a conservative
        # expiry margin and avoid the Testbed's one-token-per-minute limit.
        expires_in = int(token_body.get("expires_in", 86400))
        _kis_token_cache.update(value=access_token, expires_at=time.time() + max(60, expires_in - 60))
        return access_token


def _kis_headers(tr_id: str) -> dict[str, str]:
    app_key, app_secret = _kis_credentials()
    return {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {_kis_access_token()}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": tr_id,
    }


def kis_request(
    method: str,
    path: str,
    tr_id: str,
    *,
    params: dict[str, str] | None = None,
    payload: dict[str, str] | None = None,
    label: str,
    extra_headers: dict[str, str] | None = None,
    retries: int = 2,
    raise_for_api_error: bool = True,
) -> tuple[requests.Response, dict[str, Any]]:
    """Send every authenticated KIS call through one process-wide limiter.

    Keeping the limiter here prevents the chart, explorer, HTS and order-flow
    modules from independently exceeding the Testbed's shared App Key limit.
    """
    global _kis_last_api_call_at
    response = None
    body: dict[str, Any] = {}
    for attempt in range(retries + 1):
        with _kis_api_rate_lock:
            wait = _KIS_API_CALL_GAP_SECONDS - (time.monotonic() - _kis_last_api_call_at)
            if wait > 0:
                time.sleep(wait)
            _kis_last_api_call_at = time.monotonic()
        if attempt:
            time.sleep(0.8 * attempt)
        started = time.perf_counter()
        request_data = {"params": params or {}, "json": payload or {}}
        try:
            response = requests.request(
                method,
                f"{KIS_TESTBED_URL}{path}",
                headers={**_kis_headers(tr_id), **(extra_headers or {})},
                params=params,
                json=payload,
                timeout=15,
            )
            body = _json(response, "한국투자증권")
        except (requests.RequestException, BrokerApiError) as exc:
            _audit_kis_call(
                method=method, path=path, tr_id=tr_id, label=label, attempt=attempt + 1,
                request_data=request_data, http_status=503, response_body={},
                duration_ms=(time.perf_counter() - started) * 1000,
                success=False, error=str(exc),
            )
            raise
        success = body.get("rt_cd") == "0"
        _audit_kis_call(
            method=method, path=path, tr_id=tr_id, label=label, attempt=attempt + 1,
            request_data=request_data, http_status=response.status_code, response_body=body,
            duration_ms=(time.perf_counter() - started) * 1000, success=success,
            error=None if success else (body.get("msg1") or body.get("msg_cd")),
        )
        if body.get("msg_cd") != _KIS_RATE_LIMIT_CODE:
            break
    if raise_for_api_error and body.get("rt_cd") != "0":
        raise BrokerApiError(
            f"한국투자증권 {label} 실패 (HTTP {response.status_code}, {body.get('msg_cd')}): {body.get('msg1')}"
        )
    return response, body


def get_kis_quote(symbol: str) -> dict[str, Any]:
    with _kis_quote_lock:
        cached_quote = _kis_quote_cache.get(symbol)
        if cached_quote and cached_quote["expires_at"] > time.time():
            _kis_quote_cache.move_to_end(symbol)
            return cached_quote["quote"]
        if cached_quote:
            _kis_quote_cache.pop(symbol, None)

    _, body = kis_request(
        "GET", "/uapi/domestic-stock/v1/quotations/inquire-price", "FHKST01010100",
        params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol},
        label="시세 조회",
    )
    output = body.get("output", {})
    quote = {
        "broker": "한국투자증권 Testbed", "symbol": symbol,
        "price": output.get("stck_prpr"), "change": output.get("prdy_vrss"),
        "changeRate": output.get("prdy_ctrt"), "volume": output.get("acml_vol"),
        "tradeTime": output.get("stck_cntg_hour"),
    }
    # Testbed rejects bursts at the per-second limit. A short cache makes a
    # double click safe without presenting stale data as a long-lived quote.
    with _kis_quote_lock:
        _kis_quote_cache[symbol] = {"quote": quote, "expires_at": time.time() + 3}
        _kis_quote_cache.move_to_end(symbol)
        while len(_kis_quote_cache) > _KIS_QUOTE_CACHE_MAX:
            _kis_quote_cache.popitem(last=False)
    return quote


def get_kis_balance() -> dict[str, Any]:
    """Read-only 모의투자 계좌 잔고/평가액 조회 (inquire-balance, VTTC8434R)."""
    cano, acnt_prdt_cd = _kis_account()
    response, body = kis_request(
        "GET", "/uapi/domestic-stock/v1/trading/inquire-balance", "VTTC8434R",
        params={
            "CANO": cano, "ACNT_PRDT_CD": acnt_prdt_cd,
            "AFHR_FLPR_YN": "N", "OFL_YN": "", "INQR_DVSN": "02", "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N", "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
        },
        label="잔고 조회",
    )
    summary = (body.get("output2") or [{}])[0]
    holdings = [
        {
            "symbol": item.get("pdno"), "name": item.get("prdt_name"),
            "quantity": item.get("hldg_qty"), "avgPrice": item.get("pchs_avg_pric"),
            "currentPrice": item.get("prpr"),
            "evalAmount": item.get("evlu_amt"), "profitLoss": item.get("evlu_pfls_amt"),
            "profitLossRate": item.get("evlu_pfls_rt"),
        }
        for item in (body.get("output1") or []) if item.get("pdno")
    ]
    return {
        "broker": "한국투자증권 Testbed",
        "cashBalance": summary.get("dnca_tot_amt"),
        "totalEvalAmount": summary.get("tot_evlu_amt"),
        "totalProfitLoss": summary.get("evlu_pfls_smtl_amt"),
        "holdingsCount": len(holdings),
        "holdings": holdings,
    }


def get_kis_configuration_status() -> dict[str, Any]:
    """Report Testbed readiness without returning credentials or account numbers."""
    status = {
        "environment": os.environ.get("KIS_ENVIRONMENT", "paper").strip().lower(),
        "testbedUrl": KIS_TESTBED_URL,
        "credentials": False,
        "account": False,
        "ready": False,
    }
    messages = []
    try:
        _kis_credentials()
        status["credentials"] = True
    except BrokerApiError as exc:
        messages.append(str(exc))
    try:
        _kis_account()
        status["account"] = True
    except BrokerApiError as exc:
        messages.append(str(exc))
    status["ready"] = status["environment"] == "paper" and status["credentials"] and status["account"]
    status["message"] = "KIS Testbed 모의주문 준비가 완료되었습니다." if status["ready"] else " ".join(messages)
    return status


def get_kis_orders_today(limit: int = 50) -> dict[str, Any]:
    """Return today's KIS Testbed order/execution history."""
    if not 1 <= limit <= 100:
        raise BrokerApiError("주문내역 limit은 1~100 사이여야 합니다.", 400)
    cano, acnt_prdt_cd = _kis_account()
    today = time.strftime("%Y%m%d", time.localtime())
    _, body = kis_request(
        "GET", "/uapi/domestic-stock/v1/trading/inquire-daily-ccld", "VTTC8001R",
        params={
            "CANO": cano, "ACNT_PRDT_CD": acnt_prdt_cd,
            "INQR_STRT_DT": today, "INQR_END_DT": today,
            "SLL_BUY_DVSN_CD": "00", "INQR_DVSN": "00", "PDNO": "",
            "CCLD_DVSN": "00", "ORD_GNO_BRNO": "", "ODNO": "",
            "INQR_DVSN_3": "00", "INQR_DVSN_1": "",
            "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
        },
        label="당일 주문내역 조회",
    )
    orders = []
    for row in (body.get("output1") or [])[:limit]:
        side_code = str(row.get("sll_buy_dvsn_cd") or row.get("sll_buy_dvsn_cd_name") or "")
        side_name = str(row.get("sll_buy_dvsn_cd_name") or "")
        side = "SELL" if side_code in {"01", "매도"} or "매도" in side_name else "BUY"
        orders.append({
            "orderNo": row.get("odno"), "symbol": row.get("pdno"),
            "name": row.get("prdt_name"), "side": side,
            "orderQuantity": row.get("ord_qty"), "filledQuantity": row.get("tot_ccld_qty"),
            "remainingQuantity": row.get("rmn_qty"), "orderPrice": row.get("ord_unpr"),
            "filledPrice": row.get("avg_prvs"), "orderTime": row.get("ord_tmd"),
            "status": row.get("ord_dvsn_name") or ("체결" if str(row.get("rmn_qty") or "0") == "0" else "미체결"),
        })
    return {"broker": "한국투자증권 Testbed", "date": today, "orders": orders}


def get_kis_daily_chart(symbol: str, days: int = 20) -> dict[str, Any]:
    """Read-only 일봉 캔들 조회 (inquire-daily-itemchartprice, FHKST03010100)."""
    end = time.strftime("%Y%m%d")
    start = time.strftime("%Y%m%d", time.localtime(time.time() - days * 4 * 86400))
    response, body = kis_request(
        "GET", "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice", "FHKST03010100",
        params={
            "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol,
            "FID_INPUT_DATE_1": start, "FID_INPUT_DATE_2": end,
            "FID_PERIOD_DIV_CODE": "D", "FID_ORG_ADJ_PRC": "1",
        },
        label="일봉 조회",
    )
    candles = [
        {
            "date": row.get("stck_bsop_date"), "open": row.get("stck_oprc"),
            "high": row.get("stck_hgpr"), "low": row.get("stck_lwpr"),
            "close": row.get("stck_clpr"), "volume": row.get("acml_vol"),
        }
        for row in (body.get("output2") or [])[:days]
    ]
    return {"broker": "한국투자증권 Testbed", "symbol": symbol, "candles": candles}


def get_kis_orderbook(symbol: str) -> dict[str, Any]:
    """Read-only 매도/매수 10단계 호가 조회 (inquire-asking-price-exp-ccn, FHKST01010200)."""
    response, body = kis_request(
        "GET", "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn", "FHKST01010200",
        params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol},
        label="호가 조회",
    )
    output1 = body.get("output1") or {}
    levels = [
        {
            "level": n,
            "askPrice": output1.get(f"askp{n}"), "askQty": output1.get(f"askp_rsqn{n}"),
            "bidPrice": output1.get(f"bidp{n}"), "bidQty": output1.get(f"bidp_rsqn{n}"),
        }
        for n in range(1, 11)
    ]
    return {
        "broker": "한국투자증권 Testbed", "symbol": symbol, "levels": levels,
        "totalAskQty": output1.get("total_askp_rsqn"), "totalBidQty": output1.get("total_bidp_rsqn"),
    }


_KIS_INDEX_NAMES = {"0001": "코스피", "1001": "코스닥"}


def get_kis_index(index_code: str = "0001") -> dict[str, Any]:
    """Read-only 업종 현재지수 조회 (inquire-index-price, FHPUP02100000). 0001=코스피, 1001=코스닥."""
    response, body = kis_request(
        "GET", "/uapi/domestic-stock/v1/quotations/inquire-index-price", "FHPUP02100000",
        params={"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": index_code},
        label="지수 조회",
    )
    output = body.get("output", {})
    return {
        "broker": "한국투자증권 Testbed", "index": _KIS_INDEX_NAMES.get(index_code, index_code),
        "price": output.get("bstp_nmix_prpr"), "change": output.get("bstp_nmix_prdy_vrss"),
        "changeRate": output.get("bstp_nmix_prdy_ctrt"), "volume": output.get("acml_vol"),
    }


def _kis_order_post(path: str, tr_id: str, payload: dict[str, str], label: str) -> dict[str, Any]:
    _, body = kis_request(
        "POST", path, tr_id,
        payload=payload,
        label=label,
        extra_headers={"custtype": "P"},
    )
    return body


def place_kis_paper_order(
    symbol: str,
    side: str,
    quantity: int,
    order_type: str = "MARKET",
    price: int = 0,
) -> dict[str, Any]:
    """Place an explicitly approved order against the KIS Testbed account only."""
    symbol = str(symbol).strip()
    side = str(side).strip().upper()
    order_type = str(order_type).strip().upper()
    if len(symbol) != 6 or not symbol.isdigit():
        raise BrokerApiError("종목코드는 6자리 KRX 숫자 코드여야 합니다.", 400)
    if side not in {"BUY", "SELL"}:
        raise BrokerApiError("주문 구분은 BUY 또는 SELL이어야 합니다.", 400)
    max_quantity = int(os.environ.get("KIS_PAPER_MAX_ORDER_QUANTITY", "1000"))
    if not isinstance(quantity, int) or isinstance(quantity, bool) or not 1 <= quantity <= max_quantity:
        raise BrokerApiError(f"주문수량은 1~{max_quantity}주 사이의 정수여야 합니다.", 400)
    if order_type not in {"MARKET", "LIMIT"}:
        raise BrokerApiError("주문유형은 MARKET 또는 LIMIT만 지원합니다.", 400)
    if order_type == "LIMIT":
        if not isinstance(price, int) or isinstance(price, bool) or price <= 0:
            raise BrokerApiError("지정가 주문가격은 1원 이상의 정수여야 합니다.", 400)
        if _kis_round_down_to_tick(price) != price:
            raise BrokerApiError("지정가가 KRX 호가 단위에 맞지 않습니다.", 400)
    else:
        price = 0

    quote = get_kis_quote(symbol)
    try:
        current_price = int(str(quote.get("price") or "0").replace(",", ""))
    except ValueError as exc:
        raise BrokerApiError("현재가를 확인할 수 없어 주문을 중단했습니다.") from exc
    reference_price = price if order_type == "LIMIT" else current_price
    if reference_price <= 0:
        raise BrokerApiError("현재가가 0원으로 조회되어 주문을 중단했습니다.")
    max_amount = int(os.environ.get("KIS_PAPER_MAX_ORDER_AMOUNT", "10000000"))
    estimated_amount = reference_price * quantity
    if estimated_amount > max_amount:
        raise BrokerApiError(f"1회 모의주문 한도 {max_amount:,}원을 초과했습니다.", 400)

    balance = get_kis_balance()
    if side == "BUY" and int(float(balance.get("cashBalance") or 0)) < estimated_amount:
        raise BrokerApiError("KIS 모의계좌 주문 가능 예수금이 부족합니다.", 409)
    if side == "SELL":
        holding = next((item for item in balance.get("holdings", []) if item.get("symbol") == symbol), None)
        if int(float((holding or {}).get("quantity") or 0)) < quantity:
            raise BrokerApiError("KIS 모의계좌 보유수량이 부족합니다.", 409)

    if not _kis_paper_order_lock.acquire(blocking=False):
        raise BrokerApiError("다른 KIS 모의주문을 처리 중입니다. 잠시 후 다시 시도하세요.", 409)
    try:
        cano, acnt_prdt_cd = _kis_account()
        body = _kis_order_post(
            "/uapi/domestic-stock/v1/trading/order-cash",
            "VTTC0012U" if side == "BUY" else "VTTC0011U",
            {
                "CANO": cano, "ACNT_PRDT_CD": acnt_prdt_cd, "PDNO": symbol,
                "ORD_DVSN": "01" if order_type == "MARKET" else "00",
                "ORD_QTY": str(quantity), "ORD_UNPR": str(price),
                "EXCG_ID_DVSN_CD": "KRX",
            },
            f"모의 {('매수' if side == 'BUY' else '매도')} 주문",
        )
    finally:
        _kis_paper_order_lock.release()
    output = body.get("output") or {}
    return {
        "broker": "한국투자증권 Testbed", "environment": "paper",
        "symbol": symbol, "side": side, "quantity": quantity,
        "orderType": order_type, "price": price,
        "estimatedAmount": estimated_amount,
        "orderNo": output.get("ODNO"), "orderTime": output.get("ORD_TMD"),
        "message": body.get("msg1") or "KIS Testbed 모의주문이 접수되었습니다.",
    }


def _kis_tick_size(price: int) -> int:
    """KRX 호가 단위(2023-01-25 개편 기준, 전 시장 공통)."""
    if price < 2_000:
        return 1
    if price < 5_000:
        return 5
    if price < 20_000:
        return 10
    if price < 50_000:
        return 50
    if price < 200_000:
        return 100
    if price < 500_000:
        return 500
    return 1_000


def _kis_round_down_to_tick(price: int) -> int:
    tick = _kis_tick_size(price)
    return (price // tick) * tick


def _kis_order_test_prices(current_price: int) -> tuple[int, int]:
    """(주문가, 정정가). 둘 다 현재가보다 충분히 낮은 비시장성 가격이어야 한다."""
    test_price = _kis_round_down_to_tick(int(current_price * _KIS_ORDER_TEST_PRICE_RATIO))
    amended_price = test_price - _kis_tick_size(test_price)
    if test_price <= 0 or amended_price <= 0 or test_price >= current_price * _KIS_ORDER_TEST_MAX_PRICE_RATIO:
        raise BrokerApiError("안전을 위해 현재가 대비 충분히 낮은 지정가를 계산할 수 없어 주문 테스트를 실행하지 않습니다.")
    return test_price, amended_price


def _kis_open_orders_today(cano: str, acnt_prdt_cd: str, symbol: str) -> list[dict[str, Any]]:
    """오늘 미체결 주문 조회 (inquire-daily-ccld, 모의 VTTC8001R). 보정 단계에서만 사용한다."""
    today = time.strftime("%Y%m%d", time.localtime())
    response, body = kis_request(
        "GET", "/uapi/domestic-stock/v1/trading/inquire-daily-ccld", "VTTC8001R",
        params={
            "CANO": cano, "ACNT_PRDT_CD": acnt_prdt_cd,
            "INQR_STRT_DT": today, "INQR_END_DT": today,
            "SLL_BUY_DVSN_CD": "00", "INQR_DVSN": "00", "PDNO": symbol,
            "CCLD_DVSN": "02", "ORD_GNO_BRNO": "", "ODNO": "",
            "INQR_DVSN_3": "00", "INQR_DVSN_1": "",
            "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
        },
        label="미체결 조회",
    )
    rows = body.get("output1") or []
    open_orders = []
    for row in rows:
        try:
            remaining = int(str(row.get("rmn_qty") or "0").replace(",", ""))
        except ValueError:
            remaining = 0
        if row.get("pdno") == symbol and remaining > 0 and row.get("odno"):
            open_orders.append(row)
    return open_orders


def _kis_cancel_order(cano: str, acnt_prdt_cd: str, org_no: str, order_no: str) -> dict[str, Any]:
    return _kis_order_post(
        "/uapi/domestic-stock/v1/trading/order-rvsecncl",
        "VTTC0013U",
        {
            "CANO": cano, "ACNT_PRDT_CD": acnt_prdt_cd,
            "KRX_FWDG_ORD_ORGNO": org_no, "ORGN_ODNO": order_no,
            # 잔량 전부 취소: KIS 스펙상 QTY_ALL_ORD_YN=Y 이면 ORD_QTY 는 "0".
            "ORD_DVSN": "00", "RVSE_CNCL_DVSN_CD": "02", "ORD_QTY": "0", "ORD_UNPR": "0",
            "QTY_ALL_ORD_YN": "Y", "EXCG_ID_DVSN_CD": "KRX",
        },
        "모의 주문 취소",
    )


def _kis_error_text(exc: Exception) -> str:
    if isinstance(exc, BrokerApiError):
        return str(exc)
    return "한국투자증권 서버 응답을 받지 못했습니다(시간 초과 또는 연결 오류)."


def run_kis_mock_order_flow_test() -> dict[str, Any]:
    """Run one safe Testbed-only order → amend → cancel verification.

    순서: 안전 조건 확인 → 매수 지정가 1주 → 정정(한 호가 아래) → 잔량 취소.
    정정이나 취소가 실패하면 오늘 미체결 조회로 남은 주문을 찾아 모두 취소하는
    보정 단계를 거친다. 정정·취소 결과와 사유는 응답 필드로 그대로 전달한다.
    """
    if not _kis_order_flow_lock.acquire(blocking=False):
        raise BrokerApiError("모의 주문 흐름 테스트가 이미 실행 중입니다. 완료된 뒤 다시 시도하세요.")
    try:
        quote = get_kis_quote(_KIS_ORDER_TEST_SYMBOL)
        try:
            current_price = int(str(quote.get("price") or "").replace(",", ""))
        except ValueError as exc:
            raise BrokerApiError("한국투자증권 현재가를 숫자로 확인할 수 없어 주문 테스트를 중단했습니다.") from exc
        if current_price <= 0:
            raise BrokerApiError("한국투자증권 현재가가 0원으로 조회되어 주문 테스트를 중단했습니다.")
        test_price, amended_price = _kis_order_test_prices(current_price)
        cano, acnt_prdt_cd = _kis_account()
        order = _kis_order_post(
            "/uapi/domestic-stock/v1/trading/order-cash",
            "VTTC0012U",
            {
                "CANO": cano, "ACNT_PRDT_CD": acnt_prdt_cd, "PDNO": _KIS_ORDER_TEST_SYMBOL,
                "ORD_DVSN": "00", "ORD_QTY": "1", "ORD_UNPR": str(test_price),
                "EXCG_ID_DVSN_CD": "KRX",
            },
            "모의 매수 주문",
        )
        output = order.get("output") or {}
        org_no = output.get("KRX_FWDG_ORD_ORGNO")
        order_no = output.get("ODNO")
        if not org_no or not order_no:
            raise BrokerApiError("모의 주문은 접수됐지만 정정·취소에 필요한 참조값을 받지 못했습니다. 모의투자 화면에서 주문 상태를 확인하세요.")

        # ── 정정: 실패해도 예외를 삼키고 사유만 기록한 뒤 취소로 진행한다.
        amend_error: Exception | None = None
        try:
            amended = _kis_order_post(
                "/uapi/domestic-stock/v1/trading/order-rvsecncl",
                "VTTC0013U",
                {
                    "CANO": cano, "ACNT_PRDT_CD": acnt_prdt_cd,
                    "KRX_FWDG_ORD_ORGNO": org_no, "ORGN_ODNO": order_no,
                    "ORD_DVSN": "00", "RVSE_CNCL_DVSN_CD": "01", "ORD_QTY": "0",
                    "ORD_UNPR": str(amended_price), "QTY_ALL_ORD_YN": "Y",
                    "EXCG_ID_DVSN_CD": "KRX",
                },
                "모의 주문 정정",
            )
            amended_output = amended.get("output") or {}
            org_no = amended_output.get("KRX_FWDG_ORD_ORGNO") or org_no
            order_no = amended_output.get("ODNO") or order_no
        except (BrokerApiError, requests.RequestException) as exc:
            amend_error = exc

        # ── 취소: 정정 성공 시 새 주문번호, 실패 시 원주문 번호로 시도한다.
        cancel_error: Exception | None = None
        try:
            _kis_cancel_order(cano, acnt_prdt_cd, org_no, order_no)
        except (BrokerApiError, requests.RequestException) as exc:
            cancel_error = exc

        # ── 보정: 취소가 실패했거나, 정정 결과가 불확실(시간 초과)하면 미체결을 조회해 정리한다.
        amend_uncertain = isinstance(amend_error, requests.RequestException)
        reconcile_note: str | None = None
        leftover: int | None = None
        if cancel_error is not None or amend_uncertain:
            try:
                open_orders = _kis_open_orders_today(cano, acnt_prdt_cd, _KIS_ORDER_TEST_SYMBOL)
                failed = 0
                for row in open_orders:
                    try:
                        _kis_cancel_order(cano, acnt_prdt_cd, row.get("ord_gno_brno") or org_no, row["odno"])
                    except (BrokerApiError, requests.RequestException):
                        failed += 1
                leftover = failed
                if open_orders and failed == 0:
                    reconcile_note = f"미체결 {len(open_orders)}건을 조회해 모두 취소했습니다."
                    cancel_error = None
                elif not open_orders:
                    reconcile_note = "미체결 조회 결과 남은 주문이 없습니다."
                    cancel_error = None
                else:
                    reconcile_note = f"미체결 {len(open_orders)}건 중 {failed}건을 취소하지 못했습니다."
            except (BrokerApiError, requests.RequestException) as exc:
                reconcile_note = f"미체결 조회에 실패해 남은 주문을 확인하지 못했습니다: {_kis_error_text(exc)}"

        if cancel_error is not None or (leftover or 0) > 0:
            parts = ["모의 주문 취소를 완료하지 못했습니다."]
            if amend_error is not None:
                parts.append(f"정정: {_kis_error_text(amend_error)}")
            if cancel_error is not None:
                parts.append(f"취소: {_kis_error_text(cancel_error)}")
            if reconcile_note:
                parts.append(reconcile_note)
            parts.append("모의투자 화면에서 미체결 주문을 직접 확인·취소하세요.")
            raise BrokerApiError(" ".join(parts))

        return {
            "environment": "KIS Testbed 모의투자",
            "symbol": _KIS_ORDER_TEST_SYMBOL,
            "currentPrice": current_price,
            "order": "success",
            "amend": "failed" if amend_error is not None else "success",
            "amendMessage": _kis_error_text(amend_error) if amend_error is not None else None,
            "cancel": "success",
            "cancelMessage": reconcile_note,
            "testPrice": test_price,
            "amendedPrice": amended_price,
        }
    finally:
        _kis_order_flow_lock.release()
