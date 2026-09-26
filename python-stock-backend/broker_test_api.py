import hashlib
import hmac
import json
import secrets
import time

import requests

from flask import Blueprint, jsonify, request, session

from broker_test import (
    BrokerApiError,
    check_kb_token,
    get_kb_domestic_quote,
    get_kb_stock_base_info,
    get_kb_stock_chart,
    get_kb_stock_orderbook,
    get_kb_configuration_status,
    get_kis_balance,
    get_kis_configuration_status,
    get_kis_daily_chart,
    get_kis_index,
    get_kis_orders_today,
    get_kis_orderbook,
    get_kis_quote,
    place_kis_paper_order,
    run_kis_mock_order_flow_test,
)
from authz import can_use_kis_account
from security import csrf_is_valid


broker_test_bp = Blueprint("broker_test", __name__, url_prefix="/api/broker-test")


def _symbol() -> str:
    symbol = request.args.get("symbol", "005930").strip()
    if len(symbol) != 6 or not symbol.isdigit():
        raise BrokerApiError("종목코드는 6자리 KRX 숫자 코드여야 합니다.", 400)
    return symbol


def _kis_response(build):
    try:
        return jsonify({"ok": True, **build()})
    except BrokerApiError as exc:
        # Preserve a machine-observable HTTP status while returning a safe body.
        return jsonify({"ok": False, "broker": "한국투자증권 Testbed", "message": str(exc)}), exc.status_code
    except requests.RequestException:
        return jsonify({"ok": False, "broker": "한국투자증권 Testbed", "message": "한국투자증권 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요."}), 503


def _kb_response(build):
    if not session.get("member_id"):
        return jsonify({"ok": False, "broker": "KB증권", "message": "KB API 실습은 로그인 후 이용할 수 있습니다."}), 401
    try:
        return jsonify({"ok": True, **build()})
    except BrokerApiError as exc:
        return jsonify({"ok": False, "broker": "KB증권", "message": str(exc)}), exc.status_code
    except requests.RequestException:
        return jsonify({"ok": False, "broker": "KB증권", "message": "KB증권 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요."}), 503


@broker_test_bp.get("/kis/quote")
def kis_quote():
    return _kis_response(lambda: {"quote": get_kis_quote(_symbol())})


@broker_test_bp.get("/kis/balance")
def kis_balance():
    if not can_use_kis_account(session.get("member_id")):
        return jsonify({"ok": False, "message": "KIS 모의계좌 잔고는 로그인 후 조회할 수 있습니다."}), 401
    return _kis_response(lambda: {"balance": get_kis_balance()})


@broker_test_bp.get("/kis/status")
def kis_status():
    return jsonify({"ok": True, "status": get_kis_configuration_status()})


@broker_test_bp.get("/kis/orders")
def kis_orders():
    if not can_use_kis_account(session.get("member_id")):
        return jsonify({"ok": False, "message": "KIS 모의계좌 주문내역은 로그인 후 조회할 수 있습니다."}), 401
    try:
        limit = int(request.args.get("limit", "50"))
    except ValueError:
        return jsonify({"ok": False, "message": "limit은 숫자여야 합니다."}), 400
    return _kis_response(lambda: {"history": get_kis_orders_today(limit)})


@broker_test_bp.get("/kis/chart")
def kis_chart():
    try:
        days = int(request.args.get("days", "30"))
    except ValueError:
        return jsonify({"ok": False, "message": "days는 숫자여야 합니다."}), 400
    if not 5 <= days <= 365:
        return jsonify({"ok": False, "message": "days는 5~365 사이여야 합니다."}), 400
    return _kis_response(lambda: {"chart": get_kis_daily_chart(_symbol(), days)})


@broker_test_bp.get("/kis/orderbook")
def kis_orderbook():
    return _kis_response(lambda: {"orderbook": get_kis_orderbook(_symbol())})


@broker_test_bp.get("/kis/index")
def kis_index():
    code = request.args.get("code", "0001").strip()
    if code not in ("0001", "1001"):
        return jsonify({"ok": False, "broker": "한국투자증권 Testbed", "message": "code는 0001(코스피) 또는 1001(코스닥)이어야 합니다."}), 400
    return _kis_response(lambda: {"index": get_kis_index(code)})


_ORDER_APPROVAL_KEY = "kis_order_approval"
_PAPER_ORDER_APPROVAL_KEY = "kis_paper_order_approval"


def _paper_order_intent() -> dict:
    payload = request.get_json(silent=True) or {}
    symbol = str(payload.get("symbol", "")).strip()
    side = str(payload.get("side", "")).strip().upper()
    order_type = str(payload.get("orderType", "MARKET")).strip().upper()
    quantity = payload.get("quantity")
    price = payload.get("price", 0)
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


@broker_test_bp.post("/kis/order-approval")
def kis_paper_order_approval():
    member_id = session.get("member_id")
    if not member_id or not can_use_kis_account(member_id):
        return jsonify({"ok": False, "message": "KIS 모의주문은 로그인 후 이용할 수 있습니다."}), 401
    if not csrf_is_valid():
        return jsonify({"ok": False, "message": "요청 검증에 실패했습니다. 화면을 새로고침한 뒤 다시 시도하세요."}), 403
    try:
        intent = _paper_order_intent()
    except BrokerApiError as exc:
        return jsonify({"ok": False, "message": str(exc)}), exc.status_code
    token = secrets.token_urlsafe(32)
    session[_PAPER_ORDER_APPROVAL_KEY] = {
        "tokenDigest": hashlib.sha256(token.encode()).hexdigest(),
        "intentDigest": _intent_digest(intent),
        "expiresAt": time.time() + 60,
    }
    return jsonify({"ok": True, "approvalToken": token, "expiresIn": 60, "intent": intent})


@broker_test_bp.post("/kis/orders")
def kis_paper_order():
    member_id = session.get("member_id")
    if not member_id or not can_use_kis_account(member_id):
        return jsonify({"ok": False, "message": "KIS 모의주문은 로그인 후 이용할 수 있습니다."}), 401
    if not csrf_is_valid():
        return jsonify({"ok": False, "message": "요청 검증에 실패했습니다. 화면을 새로고침한 뒤 다시 시도하세요."}), 403
    try:
        intent = _paper_order_intent()
    except BrokerApiError as exc:
        return jsonify({"ok": False, "message": str(exc)}), exc.status_code
    payload = request.get_json(silent=True) or {}
    approval = session.pop(_PAPER_ORDER_APPROVAL_KEY, None) or {}
    token_digest = hashlib.sha256(str(payload.get("approvalToken", "")).encode()).hexdigest()
    valid = (
        approval
        and approval.get("expiresAt", 0) >= time.time()
        and hmac.compare_digest(approval.get("tokenDigest", ""), token_digest)
        and hmac.compare_digest(approval.get("intentDigest", ""), _intent_digest(intent))
    )
    if not valid:
        return jsonify({"ok": False, "message": "주문 승인이 만료되었거나 주문 내용이 변경되었습니다. 다시 확인하세요."}), 403
    return _kis_response(lambda: {"order": place_kis_paper_order(
        intent["symbol"], intent["side"], intent["quantity"], intent["orderType"], intent["price"],
    )})


@broker_test_bp.post("/kis/order-flow-approval")
def kis_order_flow_approval():
    member_id = session.get("member_id")
    if not member_id:
        return jsonify({"ok": False, "message": "로그인이 필요합니다."}), 401
    if not can_use_kis_account(member_id):
        return jsonify({"ok": False, "message": "KIS 모의 주문 테스트는 로그인한 회원만 실행할 수 있습니다."}), 401
    if not csrf_is_valid():
        return jsonify({"ok": False, "message": "요청 검증에 실패했습니다. 화면을 새로고침한 뒤 다시 시도하세요."}), 403
    token = secrets.token_urlsafe(32)
    session[_ORDER_APPROVAL_KEY] = {
        "digest": hashlib.sha256(token.encode()).hexdigest(),
        "expiresAt": time.time() + 60,
    }
    return jsonify({"ok": True, "approvalToken": token, "expiresIn": 60})


@broker_test_bp.post("/kis/order-flow-test")
def kis_order_flow_test():
    member_id = session.get("member_id")
    if not member_id:
        return jsonify({"ok": False, "message": "모의 주문 흐름 테스트는 로그인 후 실행할 수 있습니다."}), 401
    if not can_use_kis_account(member_id):
        return jsonify({"ok": False, "message": "KIS 모의 주문 테스트는 로그인한 회원만 실행할 수 있습니다."}), 401
    if not csrf_is_valid():
        return jsonify({"ok": False, "message": "요청 검증에 실패했습니다. 화면을 새로고침한 뒤 다시 시도하세요."}), 403
    approval = session.pop(_ORDER_APPROVAL_KEY, None) or {}
    supplied = str((request.get_json(silent=True) or {}).get("approvalToken", ""))
    supplied_digest = hashlib.sha256(supplied.encode()).hexdigest()
    if not approval or approval.get("expiresAt", 0) < time.time() or not hmac.compare_digest(approval.get("digest", ""), supplied_digest):
        return jsonify({"ok": False, "message": "주문 실행 승인이 만료되었거나 유효하지 않습니다. 다시 확인 후 실행하세요."}), 403
    return _kis_response(lambda: {"test": run_kis_mock_order_flow_test()})


@broker_test_bp.get("/kb/token")
def kb_token():
    return _kb_response(lambda: {"check": check_kb_token()})


@broker_test_bp.get("/kb/status")
def kb_status():
    return _kb_response(lambda: {"status": get_kb_configuration_status()})


@broker_test_bp.get("/kb/quote")
def kb_quote():
    return _kb_response(lambda: {"quote": get_kb_domestic_quote(_symbol())})


@broker_test_bp.get("/kb/base-info")
def kb_base_info():
    return _kb_response(lambda: {"result": get_kb_stock_base_info(_symbol())})


@broker_test_bp.get("/kb/orderbook")
def kb_orderbook():
    return _kb_response(lambda: {"result": get_kb_stock_orderbook(_symbol())})


@broker_test_bp.get("/kb/chart")
def kb_chart():
    try:
        count = int(request.args.get("count", "60"))
    except ValueError:
        return jsonify({"ok": False, "broker": "KB증권", "message": "count는 숫자여야 합니다."}), 400
    market = request.args.get("market", "0").strip()
    period = request.args.get("period", "D").strip().upper()
    return _kb_response(lambda: {"result": get_kb_stock_chart(_symbol(), market, period, count)})
