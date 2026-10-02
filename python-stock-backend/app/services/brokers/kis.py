"""한국투자증권(KIS) 모의투자 Testbed 공통 게이트웨이.

모든 인증 KIS 호출은 ``kis_request``를 거친다. 차트·탐색기·HTS·주문 흐름 모듈이 각자
Testbed의 App Key 공용 호출 제한을 넘기지 않도록 프로세스 전역 제한기를 한 곳에 둔다.
자격증명은 호출 시점에 .env(또는 AWS Secrets Manager)에서 읽고 응답에는 절대 포함하지 않는다.
"""

from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

import requests

from app.services.brokers.common import BrokerApiError, aws_credentials, credential_source
from app.services.brokers.common import json_body as _json

KIS_TESTBED_URL = "https://openapivts.koreainvestment.com:29443"
_kis_token_cache: dict[str, Any] = {"value": None, "expires_at": 0.0}
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
_KIS_INDEX_NAMES = {"0001": "코스피", "1001": "코스닥"}


def _kis_credentials() -> tuple[str, str]:
    if os.environ.get("KIS_ENVIRONMENT", "paper").strip().lower() != "paper":
        raise BrokerApiError("이 서비스는 KIS 모의투자(paper) 환경만 허용합니다.", 503)
    if credential_source() == "aws":
        return aws_credentials("kis")
    paper_key = os.environ.get("KIS_PAPER_APP_KEY")
    paper_secret = os.environ.get("KIS_PAPER_APP_SECRET")
    if paper_key or paper_secret:
        if not paper_key or not paper_secret:
            raise BrokerApiError("KIS_PAPER_APP_KEY와 KIS_PAPER_APP_SECRET을 함께 설정하세요.", 503)
        return paper_key, paper_secret
    raise BrokerApiError(".env에 KIS_PAPER_APP_KEY와 KIS_PAPER_APP_SECRET을 설정하세요.", 503)


def _kis_account() -> tuple[str, str]:
    account_no = os.environ.get("KIS_PAPER_ACCOUNT_NO")
    if not account_no and credential_source() == "aws":
        try:
            from app.services.aws_secret_store import AwsSecretError, get_parameter

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
    """지연 import로 독립 실행 스크립트에서도 시세 헬퍼를 쓸 수 있게 한다."""
    try:
        from app.services.api_usage import record_kis_gateway_call

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
        # KIS 토큰은 보통 하루 유효하다. 보수적인 만료 여유를 두고 Testbed의 분당 1회 토큰 제한을 피한다.
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
    base_url: str | None = None,
    headers_factory: Callable[[str], dict[str, str]] | None = None,
) -> tuple[requests.Response, dict[str, Any]]:
    """인증이 필요한 모든 KIS 호출을 프로세스 전역 제한기 하나로 보낸다.

    기본은 모의투자 Testbed(``KIS_TESTBED_URL`` + ``_kis_headers``)다. 자동매매 게이트웨이
    (``kis_autotrade``)는 ``base_url``/``headers_factory``로 실전 환경을 같은 제한기·감사로그로 보낸다.
    """
    global _kis_last_api_call_at
    target_base_url = base_url or KIS_TESTBED_URL
    make_headers = headers_factory or _kis_headers
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
                f"{target_base_url}{path}",
                headers={**make_headers(tr_id), **(extra_headers or {})},
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
    # Testbed는 초당 제한에서 연타를 거부한다. 짧은 캐시로 더블클릭을 안전하게 하되
    # 오래된 데이터를 장기 시세처럼 보이게 하지는 않는다.
    with _kis_quote_lock:
        _kis_quote_cache[symbol] = {"quote": quote, "expires_at": time.time() + 3}
        _kis_quote_cache.move_to_end(symbol)
        while len(_kis_quote_cache) > _KIS_QUOTE_CACHE_MAX:
            _kis_quote_cache.popitem(last=False)
    return quote


def get_kis_balance() -> dict[str, Any]:
    """읽기 전용 모의투자 계좌 잔고/평가액 조회 (inquire-balance, VTTC8434R)."""
    cano, acnt_prdt_cd = _kis_account()
    _, body = kis_request(
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
    """자격증명·계좌번호를 돌려주지 않고 Testbed 준비 상태만 보고한다."""
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
    """오늘의 KIS Testbed 주문/체결 내역."""
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
    """읽기 전용 일봉 캔들 조회 (inquire-daily-itemchartprice, FHKST03010100)."""
    end = time.strftime("%Y%m%d")
    start = time.strftime("%Y%m%d", time.localtime(time.time() - days * 4 * 86400))
    _, body = kis_request(
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
    """읽기 전용 매도/매수 10단계 호가 조회 (inquire-asking-price-exp-ccn, FHKST01010200)."""
    _, body = kis_request(
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


def get_kis_index(index_code: str = "0001") -> dict[str, Any]:
    """읽기 전용 업종 현재지수 조회 (inquire-index-price, FHPUP02100000). 0001=코스피, 1001=코스닥."""
    _, body = kis_request(
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
    _, body = kis_request("POST", path, tr_id, payload=payload, label=label, extra_headers={"custtype": "P"})
    return body


def place_kis_paper_order(symbol: str, side: str, quantity: int, order_type: str = "MARKET", price: int = 0) -> dict[str, Any]:
    """명시적으로 승인된 주문만 KIS Testbed 계좌에 낸다."""
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
    _, body = kis_request(
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
    open_orders = []
    for row in body.get("output1") or []:
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
    """Testbed 전용 안전한 주문 → 정정 → 취소 검증 1회.

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
