"""KIS Testbed·KB증권 연결 테스트 API(/api/broker-test/*)."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from typing import Any

import requests
from fastapi import APIRouter, Body, Query, Request
from fastapi.responses import JSONResponse

from app.core.deps import OptionalMemberId, csrf_required
from app.core.errors import ApiError
from app.services.authz import can_use_kis_account
from app.services.brokers.common import BrokerApiError
from app.services.brokers.kb import (
    check_kb_token,
    get_kb_configuration_status,
    get_kb_domestic_quote,
    get_kb_stock_base_info,
    get_kb_stock_chart,
    get_kb_stock_orderbook,
)
from app.services.brokers.kis import (
    get_kis_balance,
    get_kis_configuration_status,
    get_kis_daily_chart,
    get_kis_index,
    get_kis_orderbook,
    get_kis_orders_today,
    get_kis_quote,
    place_kis_paper_order,
    run_kis_mock_order_flow_test,
)

from ..schemas import ApprovalTokenBody, KisPaperOrderBody

router = APIRouter(prefix="/api/broker-test", tags=["broker-test"])

KIS_BROKER = "한국투자증권 Testbed"
KB_BROKER = "KB증권"
CSRF_MESSAGE = "요청 검증에 실패했습니다. 화면을 새로고침한 뒤 다시 시도하세요."
require_csrf = csrf_required(ok=False, message=CSRF_MESSAGE)
_ORDER_APPROVAL_KEY = "kis_order_approval"
_PAPER_ORDER_APPROVAL_KEY = "kis_paper_order_approval"


def _symbol(symbol: str) -> str:
    symbol = symbol.strip()
    if len(symbol) != 6 or not symbol.isdigit():
        raise BrokerApiError("종목코드는 6자리 KRX 숫자 코드여야 합니다.", 400)
    return symbol


def _kis_response(build):
    try:
        return {"ok": True, **build()}
    except BrokerApiError as exc:
        # 기계가 읽을 수 있는 HTTP 상태를 유지하면서 안전한 본문을 돌려준다.
        return JSONResponse({"ok": False, "broker": KIS_BROKER, "message": str(exc)}, status_code=exc.status_code)
    except requests.RequestException:
        return JSONResponse({"ok": False, "broker": KIS_BROKER, "message": "한국투자증권 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요."}, status_code=503)


def _kb_response(member_id: int | None, build):
    if not member_id:
        return JSONResponse({"ok": False, "broker": KB_BROKER, "message": "KB API 실습은 로그인 후 이용할 수 있습니다."}, status_code=401)
    try:
        return {"ok": True, **build()}
    except BrokerApiError as exc:
        return JSONResponse({"ok": False, "broker": KB_BROKER, "message": str(exc)}, status_code=exc.status_code)
    except requests.RequestException:
        return JSONResponse({"ok": False, "broker": KB_BROKER, "message": "KB증권 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요."}, status_code=503)


def _require_kis_member(member_id: int | None, message: str) -> int:
    if not member_id or not can_use_kis_account(member_id):
        raise ApiError(401, ok=False, message=message)
    return member_id


@router.get("/kis/quote")
def kis_quote(symbol: str = Query("005930")):
    return _kis_response(lambda: {"quote": get_kis_quote(_symbol(symbol))})


@router.get("/kis/balance")
def kis_balance(member_id: OptionalMemberId):
    if not can_use_kis_account(member_id):
        raise ApiError(401, ok=False, message="KIS 모의계좌 잔고는 로그인 후 조회할 수 있습니다.")
    return _kis_response(lambda: {"balance": get_kis_balance()})


@router.get("/kis/status")
def kis_status() -> dict:
    return {"ok": True, "status": get_kis_configuration_status()}


@router.get("/kis/orders")
def kis_orders(member_id: OptionalMemberId, limit: str = Query("50")):
    if not can_use_kis_account(member_id):
        raise ApiError(401, ok=False, message="KIS 모의계좌 주문내역은 로그인 후 조회할 수 있습니다.")
    try:
        limit_value = int(limit)
    except ValueError:
        raise ApiError(400, ok=False, message="limit은 숫자여야 합니다.")
    return _kis_response(lambda: {"history": get_kis_orders_today(limit_value)})


@router.get("/kis/chart")
def kis_chart(symbol: str = Query("005930"), days: str = Query("30")):
    try:
        days_value = int(days)
    except ValueError:
        raise ApiError(400, ok=False, message="days는 숫자여야 합니다.")
    if not 5 <= days_value <= 365:
        raise ApiError(400, ok=False, message="days는 5~365 사이여야 합니다.")
    return _kis_response(lambda: {"chart": get_kis_daily_chart(_symbol(symbol), days_value)})


@router.get("/kis/orderbook")
def kis_orderbook(symbol: str = Query("005930")):
    return _kis_response(lambda: {"orderbook": get_kis_orderbook(_symbol(symbol))})


@router.get("/kis/index")
def kis_index(code: str = Query("0001")):
    code = code.strip()
    if code not in ("0001", "1001"):
        raise ApiError(400, ok=False, broker=KIS_BROKER, message="code는 0001(코스피) 또는 1001(코스닥)이어야 합니다.")
    return _kis_response(lambda: {"index": get_kis_index(code)})


def _paper_order_intent(payload: KisPaperOrderBody) -> dict[str, Any]:
    symbol = str(payload.symbol or "").strip()
    side = str(payload.side or "").strip().upper()
    order_type = str(payload.orderType or "MARKET").strip().upper()
    quantity = payload.quantity
    price = payload.price if payload.price is not None else 0
    if len(symbol) != 6 or not symbol.isdigit():
        raise BrokerApiError("종목코드는 6자리 KRX 숫자 코드여야 합니다.", 400)
    if side not in {"BUY", "SELL"}:
        raise BrokerApiError("주문 구분은 BUY 또는 SELL이어야 합니다.", 400)
    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
        raise BrokerApiError("주문수량은 1주 이상의 정수여야 합니다.", 400)
    if order_type not in {"MARKET", "LIMIT"}:
        raise BrokerApiError("주문유형은 MARKET 또는 LIMIT만 지원합니다.", 400)
    if order_type == "LIMIT" and (not isinstance(price, int) or isinstance(price, bool) or price < 1):
        raise BrokerApiError("지정가 주문가격은 1원 이상의 정수여야 합니다.", 400)
    return {"symbol": symbol, "side": side, "quantity": quantity, "orderType": order_type, "price": price if order_type == "LIMIT" else 0}


def _intent_digest(intent: dict) -> str:
    return hashlib.sha256(json.dumps(intent, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@router.post("/kis/order-approval")
def kis_paper_order_approval(request: Request, member_id: OptionalMemberId, payload: KisPaperOrderBody = Body(default_factory=KisPaperOrderBody)):
    _require_kis_member(member_id, "KIS 모의주문은 로그인 후 이용할 수 있습니다.")
    require_csrf(request)
    try:
        intent = _paper_order_intent(payload)
    except BrokerApiError as exc:
        raise ApiError(exc.status_code, ok=False, message=str(exc))
    token = secrets.token_urlsafe(32)
    request.session[_PAPER_ORDER_APPROVAL_KEY] = {
        "tokenDigest": hashlib.sha256(token.encode()).hexdigest(),
        "intentDigest": _intent_digest(intent),
        "expiresAt": time.time() + 60,
    }
    return {"ok": True, "approvalToken": token, "expiresIn": 60, "intent": intent}


@router.post("/kis/orders")
def kis_paper_order(request: Request, member_id: OptionalMemberId, payload: KisPaperOrderBody = Body(default_factory=KisPaperOrderBody)):
    _require_kis_member(member_id, "KIS 모의주문은 로그인 후 이용할 수 있습니다.")
    require_csrf(request)
    try:
        intent = _paper_order_intent(payload)
    except BrokerApiError as exc:
        raise ApiError(exc.status_code, ok=False, message=str(exc))
    approval = request.session.pop(_PAPER_ORDER_APPROVAL_KEY, None) or {}
    token_digest = hashlib.sha256(str(payload.approvalToken or "").encode()).hexdigest()
    valid = (
        approval
        and approval.get("expiresAt", 0) >= time.time()
        and hmac.compare_digest(approval.get("tokenDigest", ""), token_digest)
        and hmac.compare_digest(approval.get("intentDigest", ""), _intent_digest(intent))
    )
    if not valid:
        raise ApiError(403, ok=False, message="주문 승인이 만료되었거나 주문 내용이 변경되었습니다. 다시 확인하세요.")
    return _kis_response(lambda: {"order": place_kis_paper_order(
        intent["symbol"], intent["side"], intent["quantity"], intent["orderType"], intent["price"],
    )})


@router.post("/kis/order-flow-approval")
def kis_order_flow_approval(request: Request, member_id: OptionalMemberId):
    if not member_id:
        raise ApiError(401, ok=False, message="로그인이 필요합니다.")
    if not can_use_kis_account(member_id):
        raise ApiError(401, ok=False, message="KIS 모의 주문 테스트는 로그인한 회원만 실행할 수 있습니다.")
    require_csrf(request)
    token = secrets.token_urlsafe(32)
    request.session[_ORDER_APPROVAL_KEY] = {"digest": hashlib.sha256(token.encode()).hexdigest(), "expiresAt": time.time() + 60}
    return {"ok": True, "approvalToken": token, "expiresIn": 60}


@router.post("/kis/order-flow-test")
def kis_order_flow_test(request: Request, member_id: OptionalMemberId, payload: ApprovalTokenBody = Body(default_factory=ApprovalTokenBody)):
    if not member_id:
        raise ApiError(401, ok=False, message="모의 주문 흐름 테스트는 로그인 후 실행할 수 있습니다.")
    if not can_use_kis_account(member_id):
        raise ApiError(401, ok=False, message="KIS 모의 주문 테스트는 로그인한 회원만 실행할 수 있습니다.")
    require_csrf(request)
    approval = request.session.pop(_ORDER_APPROVAL_KEY, None) or {}
    supplied_digest = hashlib.sha256(str(payload.approvalToken or "").encode()).hexdigest()
    if not approval or approval.get("expiresAt", 0) < time.time() or not hmac.compare_digest(approval.get("digest", ""), supplied_digest):
        raise ApiError(403, ok=False, message="주문 실행 승인이 만료되었거나 유효하지 않습니다. 다시 확인 후 실행하세요.")
    return _kis_response(lambda: {"test": run_kis_mock_order_flow_test()})


@router.get("/kb/token")
def kb_token(member_id: OptionalMemberId):
    return _kb_response(member_id, lambda: {"check": check_kb_token()})


@router.get("/kb/status")
def kb_status(member_id: OptionalMemberId):
    return _kb_response(member_id, lambda: {"status": get_kb_configuration_status()})


@router.get("/kb/quote")
def kb_quote(member_id: OptionalMemberId, symbol: str = Query("005930")):
    return _kb_response(member_id, lambda: {"quote": get_kb_domestic_quote(_symbol(symbol))})


@router.get("/kb/base-info")
def kb_base_info(member_id: OptionalMemberId, symbol: str = Query("005930")):
    return _kb_response(member_id, lambda: {"result": get_kb_stock_base_info(_symbol(symbol))})


@router.get("/kb/orderbook")
def kb_orderbook(member_id: OptionalMemberId, symbol: str = Query("005930")):
    return _kb_response(member_id, lambda: {"result": get_kb_stock_orderbook(_symbol(symbol))})


@router.get("/kb/chart")
def kb_chart(member_id: OptionalMemberId, symbol: str = Query("005930"), count: str = Query("60"),
             market: str = Query("0"), period: str = Query("D")):
    try:
        count_value = int(count)
    except ValueError:
        raise ApiError(400, ok=False, broker=KB_BROKER, message="count는 숫자여야 합니다.")
    return _kb_response(member_id, lambda: {"result": get_kb_stock_chart(_symbol(symbol), market.strip(), period.strip().upper(), count_value)})

