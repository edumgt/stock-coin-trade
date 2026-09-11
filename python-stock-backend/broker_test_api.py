import requests

from flask import Blueprint, jsonify, request, session

from broker_test import (
    BrokerApiError,
    check_kb_token,
    get_kb_domestic_quote,
    get_kb_stock_base_info,
    get_kb_stock_chart,
    get_kb_stock_orderbook,
    get_kis_balance,
    get_kis_daily_chart,
    get_kis_index,
    get_kis_orderbook,
    get_kis_quote,
    run_kis_mock_order_flow_test,
)


broker_test_bp = Blueprint("broker_test", __name__, url_prefix="/api/broker-test")


def _symbol() -> str:
    symbol = request.args.get("symbol", "005930").strip()
    if len(symbol) != 6 or not symbol.isdigit():
        raise BrokerApiError("종목코드는 6자리 KRX 숫자 코드여야 합니다.")
    return symbol


def _kis_response(build):
    try:
        return jsonify({"ok": True, **build()})
    except BrokerApiError as exc:
        # A broker-side rejection is an expected test result, not a browser
        # transport failure. Returning 200 prevents an unnecessary console 502.
        return jsonify({"ok": False, "broker": "한국투자증권 Testbed", "message": str(exc)})
    except requests.RequestException:
        return jsonify({"ok": False, "broker": "한국투자증권 Testbed", "message": "한국투자증권 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요."}), 503


@broker_test_bp.get("/kis/quote")
def kis_quote():
    return _kis_response(lambda: {"quote": get_kis_quote(_symbol())})


@broker_test_bp.get("/kis/balance")
def kis_balance():
    return _kis_response(lambda: {"balance": get_kis_balance()})


@broker_test_bp.get("/kis/chart")
def kis_chart():
    return _kis_response(lambda: {"chart": get_kis_daily_chart(_symbol())})


@broker_test_bp.get("/kis/orderbook")
def kis_orderbook():
    return _kis_response(lambda: {"orderbook": get_kis_orderbook(_symbol())})


@broker_test_bp.get("/kis/index")
def kis_index():
    code = request.args.get("code", "0001").strip()
    if code not in ("0001", "1001"):
        return jsonify({"ok": False, "broker": "한국투자증권 Testbed", "message": "code는 0001(코스피) 또는 1001(코스닥)이어야 합니다."})
    return _kis_response(lambda: {"index": get_kis_index(code)})


@broker_test_bp.post("/kis/order-flow-test")
def kis_order_flow_test():
    if not session.get("member_id"):
        return jsonify({"ok": False, "message": "모의 주문 흐름 테스트는 로그인 후 실행할 수 있습니다."}), 401
    return _kis_response(lambda: {"test": run_kis_mock_order_flow_test()})


@broker_test_bp.get("/kb/token")
def kb_token():
    try:
        return jsonify({"ok": True, "check": check_kb_token()})
    except BrokerApiError as exc:
        return jsonify({"ok": False, "broker": "KB증권", "message": str(exc)})
    except requests.RequestException:
        return jsonify({"ok": False, "broker": "KB증권", "message": "KB증권 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요."}), 503


@broker_test_bp.get("/kb/quote")
def kb_quote():
    try:
        return jsonify({"ok": True, "quote": get_kb_domestic_quote(_symbol())})
    except BrokerApiError as exc:
        return jsonify({"ok": False, "broker": "KB증권", "message": str(exc)})
    except requests.RequestException:
        return jsonify({"ok": False, "broker": "KB증권", "message": "KB증권 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요."}), 503


@broker_test_bp.get("/kb/base-info")
def kb_base_info():
    try:
        return jsonify({"ok": True, "result": get_kb_stock_base_info(_symbol())})
    except BrokerApiError as exc:
        return jsonify({"ok": False, "broker": "KB증권", "message": str(exc)})
    except requests.RequestException:
        return jsonify({"ok": False, "broker": "KB증권", "message": "KB증권 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요."}), 503


@broker_test_bp.get("/kb/orderbook")
def kb_orderbook():
    try:
        return jsonify({"ok": True, "result": get_kb_stock_orderbook(_symbol())})
    except BrokerApiError as exc:
        return jsonify({"ok": False, "broker": "KB증권", "message": str(exc)})
    except requests.RequestException:
        return jsonify({"ok": False, "broker": "KB증권", "message": "KB증권 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요."}), 503


@broker_test_bp.get("/kb/chart")
def kb_chart():
    try:
        return jsonify({"ok": True, "result": get_kb_stock_chart(_symbol())})
    except BrokerApiError as exc:
        return jsonify({"ok": False, "broker": "KB증권", "message": str(exc)})
    except requests.RequestException:
        return jsonify({"ok": False, "broker": "KB증권", "message": "KB증권 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요."}), 503
