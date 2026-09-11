from flask import Blueprint, jsonify, request, session

import stock_trading
from db import session_scope
from models import AlternativeOrder, AlternativePosition, Member, StockOrder, StockPosition

stock_bp = Blueprint("stocks", __name__, url_prefix="/api/stocks")


@stock_bp.before_request
def require_login():
    if not session.get("member_id"):
        return jsonify({"error": "UNAUTHORIZED", "message": "로그인이 필요합니다."}), 401


@stock_bp.get("/account")
def account():
    member_id = session["member_id"]
    with session_scope() as db:
        member = db.get(Member, member_id)
        return jsonify(stock_trading.get_account_snapshot(db, member))


@stock_bp.get("/positions")
def positions():
    member_id = session["member_id"]
    include_volatility = request.args.get("volatility") == "1"
    with session_scope() as db:
        return jsonify({"positions": stock_trading.get_positions(db, member_id, include_volatility=include_volatility)})


@stock_bp.post("/orders/buy")
def buy():
    return _place_order(stock_trading.BUY)


@stock_bp.post("/orders/sell")
def sell():
    return _place_order(stock_trading.SELL)


@stock_bp.post("/orders/preview")
def order_preview():
    """Validate a stock order and show its cash/position impact without filling it."""
    data = request.get_json(silent=True) or {}
    symbol = str(data.get("symbol", "")).upper().strip()
    side = str(data.get("side", "")).upper().strip()
    try:
        quantity = int(data.get("quantity", 0))
    except (TypeError, ValueError):
        quantity = 0
    if side not in (stock_trading.BUY, stock_trading.SELL) or quantity <= 0:
        return jsonify({"message": "side(BUY/SELL)와 1 이상의 정수 quantity를 입력하세요."}), 400
    info = stock_trading.get_stock_info(symbol)
    if not info:
        return jsonify({"message": "지원하지 않는 KRX 종목입니다."}), 400
    try:
        price = stock_trading.current_price(symbol)
    except Exception:
        return jsonify({"message": "현재 시세를 확인할 수 없습니다."}), 503
    with session_scope() as db:
        member = db.get(Member, session["member_id"])
        position = db.query(StockPosition).filter_by(member_id=member.member_id, symbol=symbol).first()
        held_quantity = position.quantity if position else 0
        amount = price * quantity
        executable = amount <= member.asset if side == stock_trading.BUY else quantity <= held_quantity
        return jsonify({
            "executable": executable, "symbol": symbol, "name": info["name"], "side": side,
            "quantity": quantity, "estimatedPrice": price, "estimatedAmount": amount,
            "cashBefore": member.asset,
            "cashAfter": member.asset - amount if side == stock_trading.BUY else member.asset + amount,
            "positionBefore": held_quantity,
            "positionAfter": held_quantity + quantity if side == stock_trading.BUY else held_quantity - quantity,
            "reason": None if executable else ("보유 현금이 부족합니다." if side == stock_trading.BUY else "매도 가능 수량이 부족합니다."),
            "notice": "주문 미리보기는 체결·잔고를 변경하지 않으며, 실제 주문 시점 가격은 달라질 수 있습니다.",
        })


@stock_bp.post("/orders/pine")
def pine_order():
    """Order endpoint used by the Pine strategy practice screen.

    Strategy parsing and signal generation happen in the browser, but the
    actual simulated fill remains server-authoritative and is labelled in the
    order history so it cannot be confused with a manual web order.
    """
    data = request.get_json(silent=True) or {}
    side = str(data.get("side", "")).upper()
    if side not in (stock_trading.BUY, stock_trading.SELL):
        return jsonify({"message": "side는 BUY 또는 SELL이어야 합니다."}), 400
    return _place_order(side, source="PINE")


def _place_order(side: str, source: str = "WEB"):
    member_id = session["member_id"]
    data = request.get_json(silent=True) or {}
    symbol = str(data.get("symbol", "")).upper()
    try:
        quantity = int(data.get("quantity", 0))
    except (TypeError, ValueError):
        return jsonify({"message": "quantity는 정수여야 합니다."}), 400

    with session_scope() as db:
        member = db.get(Member, member_id)
        try:
            result = stock_trading.execute_order(db, member, symbol, side, quantity, source=source)
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        return jsonify(result)


@stock_bp.get("/orders/history")
def order_history():
    try:
        limit = max(1, min(int(request.args.get("limit", 200)), 1000))
    except (TypeError, ValueError):
        limit = 200
    member_id = session["member_id"]
    with session_scope() as db:
        return jsonify({"history": stock_trading.get_order_history(db, member_id, limit=limit)})


@stock_bp.post("/account/reset")
def reset_account():
    member_id = session["member_id"]
    with session_scope() as db:
        member = db.get(Member, member_id)
        db.query(StockPosition).filter(StockPosition.member_id == member_id).delete()
        db.query(StockOrder).filter(StockOrder.member_id == member_id).delete()
        db.query(AlternativePosition).filter(AlternativePosition.member_id == member_id).delete()
        db.query(AlternativeOrder).filter(AlternativeOrder.member_id == member_id).delete()
        member.asset = stock_trading.INITIAL_CASH
        return jsonify({"status": "ok", "cash": member.asset})
