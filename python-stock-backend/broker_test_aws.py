"""Read-only KIS/KB quote checks sourced from AWS SSM Parameter Store.

Parallel track to ``broker_test.py``: the same read-only calls against the
KIS Testbed and KB증권 Open API, but credentials come from AWS Systems
Manager Parameter Store instead of ``kis.key``/``kb.key`` or
``KIS_*``/``KB_*`` environment variables. ``broker_test.py`` itself is not
modified or used by this module.
"""

from __future__ import annotations

import socket
import threading
import time
import uuid
from typing import Any

import requests

from aws_secret_store import AwsSecretError, full_parameter_name, get_credentials, get_parameter


KB_API_BASE_URL = "https://developer.kbsec.com:32484"
KIS_TESTBED_URL = "https://openapivts.koreainvestment.com:29443"

_kis_token_cache: dict[str, Any] = {"value": None, "expires_at": 0.0}
_kis_token_lock = threading.Lock()


def _json(response: requests.Response, broker: str) -> dict[str, Any]:
    try:
        return response.json()
    except ValueError as exc:
        raise AwsSecretError(f"{broker} 서버가 JSON 응답을 반환하지 않았습니다. (HTTP {response.status_code})") from exc


# ── KB증권 ───────────────────────────────────────────────────────────────

def _kb_token_response() -> dict[str, Any]:
    app_key, app_secret = get_credentials("kb")
    response = requests.post(
        f"{KB_API_BASE_URL}/oauth2/token",
        headers={"Content-Type": "application/json"},
        json={
            "dataHeader": {"ipAddr": "", "macAddr": ""},
            "dataBody": {"appKey": app_key, "appSecret": app_secret, "grantType": "client_credentials"},
        },
        timeout=20,
    )
    body = _json(response, "KB증권")
    token = body.get("access_token") or body.get("dataBody", {}).get("access_token")
    if token:
        return body
    header = body.get("dataHeader", {})
    code = header.get("processCode") or body.get("error") or body.get("code") or "unknown"
    message = header.get("processMessage") or body.get("error_description") or body.get("message") or "토큰 발급 실패"
    raise AwsSecretError(f"KB증권 인증 실패 (HTTP {response.status_code}, {code}): {message}")


def _kb_data_header() -> dict[str, str]:
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


def check_kb_token_aws() -> dict[str, Any]:
    body = _kb_token_response()
    token_type = body.get("token_type") or body.get("dataBody", {}).get("token_type") or "Bearer"
    expires_in = body.get("expires_in") or body.get("dataBody", {}).get("expires_in") or 0
    return {"broker": "KB증권 Open API (AWS SSM)", "tokenType": token_type, "expiresIn": int(expires_in)}


def get_kb_domestic_quote_aws(symbol: str) -> dict[str, Any]:
    app_key, _ = get_credentials("kb")
    token_body = _kb_token_response()
    access_token = token_body.get("access_token") or token_body.get("dataBody", {}).get("access_token")
    response = requests.post(
        f"{KB_API_BASE_URL}/api/v1/ivu10140",
        headers={"Content-Type": "application/json", "Authorization": f"bearer {access_token}", "appKey": app_key},
        json={"dataHeader": _kb_data_header(), "dataBody": {"excg_clsf": "1", "shrt_cd": symbol}},
        timeout=20,
    )
    body = _json(response, "KB증권")
    if not response.ok:
        header = body.get("dataHeader", {})
        raise AwsSecretError(
            f"KB증권 조회 실패 (HTTP {response.status_code}, {header.get('processCode') or 'unknown'}): "
            f"{header.get('processMessage') or '요청이 거부되었습니다.'}"
        )
    return {"broker": "KB증권 Open API (AWS SSM)", "symbol": symbol, "raw": body.get("dataBody", {})}


# ── 한국투자증권(KIS) ─────────────────────────────────────────────────────

def _kis_access_token() -> str:
    app_key, app_secret = get_credentials("kis")
    with _kis_token_lock:
        access_token = _kis_token_cache["value"] if _kis_token_cache["expires_at"] > time.time() else None
        if access_token:
            return access_token
        token_response = requests.post(
            f"{KIS_TESTBED_URL}/oauth2/tokenP",
            headers={"content-type": "application/json; charset=utf-8"},
            json={"grant_type": "client_credentials", "appkey": app_key, "appsecret": app_secret},
            timeout=15,
        )
        token_body = _json(token_response, "한국투자증권")
        access_token = token_body.get("access_token")
        if not access_token:
            message = token_body.get("error_description") or token_body.get("msg1") or "토큰 발급 실패"
            raise AwsSecretError(f"한국투자증권 인증 실패 (HTTP {token_response.status_code}): {message}")
        # KIS tokens are normally valid for a day. Keep a conservative expiry
        # margin and avoid the Testbed's one-token-per-minute limit.
        expires_in = int(token_body.get("expires_in", 86400))
        _kis_token_cache.update(value=access_token, expires_at=time.time() + max(60, expires_in - 60))
        return access_token


def _kis_headers(tr_id: str) -> dict[str, str]:
    app_key, app_secret = get_credentials("kis")
    return {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {_kis_access_token()}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": tr_id,
    }


def get_kis_quote_aws(symbol: str) -> dict[str, Any]:
    response = requests.get(
        f"{KIS_TESTBED_URL}/uapi/domestic-stock/v1/quotations/inquire-price",
        headers=_kis_headers("FHKST01010100"),
        params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol},
        timeout=15,
    )
    body = _json(response, "한국투자증권")
    if body.get("rt_cd") != "0":
        raise AwsSecretError(
            f"한국투자증권 시세 조회 실패 (HTTP {response.status_code}, {body.get('msg_cd')}): {body.get('msg1')}"
        )
    output = body.get("output", {})
    return {
        "broker": "한국투자증권 Testbed (AWS SSM)", "symbol": symbol,
        "price": output.get("stck_prpr"), "change": output.get("prdy_vrss"),
        "changeRate": output.get("prdy_ctrt"), "volume": output.get("acml_vol"),
        "tradeTime": output.get("stck_cntg_hour"),
    }


def get_kis_balance_aws() -> dict[str, Any]:
    account_no = get_parameter("kis/account")
    if not account_no or "-" not in account_no:
        raise AwsSecretError(
            f"모의투자 계좌번호가 설정되지 않았습니다. SSM Parameter Store의 {full_parameter_name('kis/account')}에 "
            "'CANO-계좌상품코드'(예: 12345678-01) 형식으로 값을 생성하세요."
        )
    cano, _, acnt_prdt_cd = account_no.partition("-")
    response = requests.get(
        f"{KIS_TESTBED_URL}/uapi/domestic-stock/v1/trading/inquire-balance",
        headers=_kis_headers("VTTC8434R"),
        params={
            "CANO": cano, "ACNT_PRDT_CD": acnt_prdt_cd,
            "AFHR_FLPR_YN": "N", "OFL_YN": "", "INQR_DVSN": "02", "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N", "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
        },
        timeout=15,
    )
    body = _json(response, "한국투자증권")
    if body.get("rt_cd") != "0":
        raise AwsSecretError(
            f"한국투자증권 잔고 조회 실패 (HTTP {response.status_code}, {body.get('msg_cd')}): {body.get('msg1')}"
        )
    summary = (body.get("output2") or [{}])[0]
    holdings = [
        {
            "symbol": item.get("pdno"), "name": item.get("prdt_name"),
            "quantity": item.get("hldg_qty"), "avgPrice": item.get("pchs_avg_pric"),
            "evalAmount": item.get("evlu_amt"), "profitLoss": item.get("evlu_pfls_amt"),
            "profitLossRate": item.get("evlu_pfls_rt"),
        }
        for item in (body.get("output1") or []) if item.get("pdno")
    ]
    return {
        "broker": "한국투자증권 Testbed (AWS SSM)",
        "cashBalance": summary.get("dnca_tot_amt"),
        "totalEvalAmount": summary.get("tot_evlu_amt"),
        "totalProfitLoss": summary.get("evlu_pfls_smtl_amt"),
        "holdingsCount": len(holdings),
        "holdings": holdings,
    }
