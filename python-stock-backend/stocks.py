from flask import Blueprint, jsonify, request, session

import stock_trading
from db import session_scope
from models import Member, StockOrder, StockPosition

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
    with session_scope() as db:
        return jsonify({"positions": stock_trading.get_positions(db, member_id)})


@stock_bp.post("/orders/buy")
def buy():
    return _place_order(stock_trading.BUY)


@stock_bp.post("/orders/sell")
def sell():
    return _place_order(stock_trading.SELL)


def _place_order(side: str):
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
            result = stock_trading.execute_order(db, member, symbol, side, quantity, source="WEB")
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        return jsonify(result)


@stock_bp.get("/orders/history")
def order_history():
    member_id = session["member_id"]
    with session_scope() as db:
        return jsonify({"history": stock_trading.get_order_history(db, member_id, limit=200)})


@stock_bp.post("/account/reset")
def reset_account():
    member_id = session["member_id"]
    with session_scope() as db:
        member = db.get(Member, member_id)
        db.query(StockPosition).filter(StockPosition.member_id == member_id).delete()
        db.query(StockOrder).filter(StockOrder.member_id == member_id).delete()
        member.asset = stock_trading.INITIAL_CASH
        return jsonify({"status": "ok", "cash": member.asset})
