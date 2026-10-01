"""계좌 소유자 전용 읽기 전용 KIS 실전투자 계좌 연동(잔고 조회만)."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from typing import Any

import requests

from app.services.api_usage import record_kis_gateway_call

KIS_REAL_BASE_URL = "https://openapi.koreainvestment.com:9443"
KIS_REAL_BALANCE_TR_ID = "TTTC8434R"

_token_lock = threading.Lock()
_token_cache: dict[str, Any] = {"token": None, "expires_at": 0.0, "key_fingerprint": None}


class KisRealError(RuntimeError):
    def __init__(self, message: str, status_code: int = 503, code: str = "KIS_REAL_ERROR"):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def _settings() -> dict[str, str]:
    # 실전 키는 호출 시점에 환경변수에서 읽어 전역 객체에 캐시되지 않게 한다.
    return {
        "app_key": os.environ.get("KIS_REAL_APP_KEY", "").strip(),
        "app_secret": os.environ.get("KIS_REAL_APP_SECRET", "").strip(),
        "account": os.environ.get("KIS_REAL_ACCOUNT_NO", "").strip(),
        "owner_email": os.environ.get("KIS_REAL_OWNER_EMAIL", "").strip().lower(),
    }


EmailGetter = Callable[[], str | None]


def configuration_state(member_email: EmailGetter) -> dict[str, Any]:
    """설정·권한 상태. 소유자 이메일이 설정된 경우에만 ``member_email()``을 호출해 DB 조회를 피한다."""
    settings = _settings()
    flags = {
        "appKey": bool(settings["app_key"]),
        "appSecret": bool(settings["app_secret"]),
        "account": bool(settings["account"]),
        "ownerEmail": bool(settings["owner_email"]),
    }
    account_valid = False
    if settings["account"] and "-" in settings["account"]:
        cano, product = settings["account"].split("-", 1)
        account_valid = cano.isdigit() and len(cano) == 8 and product.isdigit() and len(product) == 2
    ready = all(flags.values()) and account_valid
    owner = bool(settings["owner_email"] and (member_email() or "").strip().lower() == settings["owner_email"])
    return {"settings": settings, "configured": flags, "accountFormatValid": account_valid, "ready": ready, "authorized": ready and owner}


def _require_owner_configuration(member_email: EmailGetter) -> dict[str, str]:
    state = configuration_state(member_email)
    if not state["ready"]:
        raise KisRealError("실전 App Key·Secret·계좌번호·계좌 소유자 이메일 설정이 필요합니다.", 503, "REAL_CONFIG_REQUIRED")
    if not state["authorized"]:
        raise KisRealError("이 실전 계좌의 잔고조회 권한이 없습니다.", 403, "REAL_ACCOUNT_FORBIDDEN")
    return state["settings"]


def _safe_json(response: requests.Response) -> dict[str, Any]:
    try:
        return response.json()
    except ValueError as exc:
        raise KisRealError(f"KIS 운영 서버가 JSON을 반환하지 않았습니다. (HTTP {response.status_code})", 502, "KIS_INVALID_RESPONSE") from exc


def _access_token(settings: dict[str, str]) -> str:
    fingerprint = f"{settings['app_key'][:8]}:{len(settings['app_secret'])}"
    now = time.time()
    with _token_lock:
        if _token_cache["token"] and _token_cache["expires_at"] > now + 60 and _token_cache["key_fingerprint"] == fingerprint:
            return str(_token_cache["token"])
        started = time.perf_counter()
        try:
            response = requests.post(
                f"{KIS_REAL_BASE_URL}/oauth2/tokenP",
                json={"grant_type": "client_credentials", "appkey": settings["app_key"], "appsecret": settings["app_secret"]},
                timeout=20,
            )
            body = _safe_json(response)
        except requests.RequestException as exc:
            record_kis_gateway_call(
                method="POST", path="/oauth2/tokenP", tr_id="OAUTH", label="실전 토큰 발급", attempt=1,
                request_data={}, http_status=503, response_body={}, duration_ms=(time.perf_counter() - started) * 1000,
                success=False, error="KIS 운영 서버 연결 실패",
            )
            raise KisRealError("KIS 운영 서버의 인증 응답을 받지 못했습니다.", 503, "KIS_CONNECTION_ERROR") from exc
        token = body.get("access_token")
        success = bool(response.ok and token)
        record_kis_gateway_call(
            method="POST", path="/oauth2/tokenP", tr_id="OAUTH", label="실전 토큰 발급", attempt=1,
            request_data={}, http_status=response.status_code,
            response_body={"error_code": body.get("error_code"), "error_description": body.get("error_description"), "tokenIssued": bool(token)},
            duration_ms=(time.perf_counter() - started) * 1000, success=success,
            error=None if success else body.get("error_description") or "실전 토큰 발급 실패",
        )
        if not success:
            raise KisRealError(body.get("error_description") or "실전 App Key 인증에 실패했습니다.", 502, body.get("error_code") or "KIS_AUTH_FAILED")
        expires_in = max(300, int(body.get("expires_in") or 86400))
        _token_cache.update({"token": token, "expires_at": now + expires_in, "key_fingerprint": fingerprint})
        return str(token)


def get_real_balance(member_email: EmailGetter) -> dict[str, Any]:
    settings = _require_owner_configuration(member_email)
    cano, product = settings["account"].split("-", 1)
    token = _access_token(settings)
    params = {
        "CANO": cano, "ACNT_PRDT_CD": product, "AFHR_FLPR_YN": "N", "OFL_YN": "",
        "INQR_DVSN": "02", "UNPR_DVSN": "01", "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "01", "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
    }
    started = time.perf_counter()
    try:
        response = requests.get(
            f"{KIS_REAL_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance",
            headers={
                "content-type": "application/json; charset=utf-8", "authorization": f"Bearer {token}",
                "appkey": settings["app_key"], "appsecret": settings["app_secret"],
                "tr_id": KIS_REAL_BALANCE_TR_ID, "custtype": "P",
            },
            params=params,
            timeout=20,
        )
        body = _safe_json(response)
    except requests.RequestException as exc:
        record_kis_gateway_call(
            method="GET", path="/uapi/domestic-stock/v1/trading/inquire-balance", tr_id=KIS_REAL_BALANCE_TR_ID,
            label="실전 잔고 조회", attempt=1, request_data={"CANO": cano}, http_status=503, response_body={},
            duration_ms=(time.perf_counter() - started) * 1000, success=False, error="KIS 운영 서버 연결 실패",
        )
        raise KisRealError("KIS 운영 서버에서 잔고 응답을 받지 못했습니다.", 503, "KIS_CONNECTION_ERROR") from exc
    success = bool(response.ok and str(body.get("rt_cd")) == "0")
    holdings = [
        {
            "symbol": row.get("pdno"), "name": row.get("prdt_name"), "quantity": row.get("hldg_qty"),
            "avgPrice": row.get("pchs_avg_pric"), "currentPrice": row.get("prpr"),
            "evalAmount": row.get("evlu_amt"), "profitLoss": row.get("evlu_pfls_amt"), "profitLossRate": row.get("evlu_pfls_rt"),
        }
        for row in (body.get("output1") or []) if row.get("pdno")
    ]
    record_kis_gateway_call(
        method="GET", path="/uapi/domestic-stock/v1/trading/inquire-balance", tr_id=KIS_REAL_BALANCE_TR_ID,
        label="실전 잔고 조회", attempt=1, request_data={"CANO": cano}, http_status=response.status_code,
        response_body={"rt_cd": body.get("rt_cd"), "msg_cd": body.get("msg_cd"), "msg1": body.get("msg1"), "holdingsCount": len(holdings)},
        duration_ms=(time.perf_counter() - started) * 1000, success=success,
        error=None if success else body.get("msg1") or "실전 잔고 조회 실패",
    )
    if not success:
        raise KisRealError(body.get("msg1") or "실전 잔고조회가 거부되었습니다.", 502, body.get("msg_cd") or "KIS_BALANCE_FAILED")
    summary = (body.get("output2") or [{}])[0]
    return {
        "cashBalance": summary.get("dnca_tot_amt"), "totalEvalAmount": summary.get("tot_evlu_amt"),
        "totalProfitLoss": summary.get("evlu_pfls_smtl_amt"), "holdingsCount": len(holdings), "holdings": holdings,
        "environment": "KIS 실전투자", "readOnly": True,
    }
