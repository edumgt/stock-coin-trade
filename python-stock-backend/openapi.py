import hashlib
import threading
import time
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, g, jsonify, request

import stock_trading
from db import session_scope
from models import ApiKey, Member
from stock_market import STOCKS, get_quote_cached

open_api_bp = Blueprint("openapi", __name__, url_prefix="/openapi/v1")

RATE_LIMIT_MAX = 60          # requests
RATE_LIMIT_WINDOW = 60       # seconds
_rate_buckets: dict[int, list] = {}
_rate_lock = threading.Lock()


def _check_rate_limit(api_key_id: int) -> bool:
    now = time.time()
    with _rate_lock:
        bucket = [t for t in _rate_buckets.get(api_key_id, []) if now - t < RATE_LIMIT_WINDOW]
        if len(bucket) >= RATE_LIMIT_MAX:
            _rate_buckets[api_key_id] = bucket
            return False
        bucket.append(now)
        _rate_buckets[api_key_id] = bucket
        return True


def require_api_key(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "UNAUTHORIZED", "message": "Authorization: Bearer <api_key> 헤더가 필요합니다."}), 401
        raw_key = auth[len("Bearer "):].strip()
        if not raw_key:
            return jsonify({"error": "UNAUTHORIZED", "message": "API 키가 비어 있습니다."}), 401

        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        with session_scope() as db:
            api_key = db.query(ApiKey).filter(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True)).first()
            if not api_key:
                return jsonify({"error": "UNAUTHORIZED", "message": "유효하지 않거나 폐기된 API 키입니다."}), 401

            if not _check_rate_limit(api_key.api_key_id):
                return jsonify({"error": "RATE_LIMITED", "message": f"분당 {RATE_LIMIT_MAX}회 호출 제한을 초과했습니다."}), 429

            member = db.get(Member, api_key.member_id)
            api_key.last_used_at = datetime.now(timezone.utc).replace(tzinfo=None)
            g.member_id = member.member_id

        return f(*args, **kwargs)

    return wrapper


@open_api_bp.get("/stocks")
@require_api_key
def list_stocks():
    result = [{"symbol": k, "name": v["name"], "market": v["market"]} for k, v in STOCKS.items()]
    return jsonify({"stocks": result})


@open_api_bp.get("/quote/<symbol>")
@require_api_key
def quote(symbol):
    try:
        return jsonify(get_quote_cached(symbol.upper()))
    except ValueError as e:
        return jsonify({"error": "NOT_FOUND", "message": str(e)}), 404


@open_api_bp.get("/account")
@require_api_key
def account():
    with session_scope() as db:
        member = db.get(Member, g.member_id)
        return jsonify(stock_trading.get_account_snapshot(db, member))


@open_api_bp.get("/positions")
@require_api_key
def positions():
    with session_scope() as db:
        return jsonify({"positions": stock_trading.get_positions(db, g.member_id)})


@open_api_bp.post("/orders")
@require_api_key
def place_order():
    body = request.get_json(silent=True) or {}
    symbol = str(body.get("symbol", ""))
    side = str(body.get("side", ""))
    try:
        quantity = int(body.get("quantity", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "INVALID_REQUEST", "message": "quantity는 정수여야 합니다."}), 400

    with session_scope() as db:
        member = db.get(Member, g.member_id)
        try:
            result = stock_trading.execute_order(db, member, symbol, side, quantity, source="OPENAPI")
        except ValueError as e:
            return jsonify({"error": "INVALID_REQUEST", "message": str(e)}), 400
        return jsonify(result)


@open_api_bp.get("/orders")
@require_api_key
def order_history():
    try:
        limit = max(1, min(int(request.args.get("limit", 50)), 200))
    except (TypeError, ValueError):
        limit = 50
    with session_scope() as db:
        return jsonify({"orders": stock_trading.get_order_history(db, g.member_id, limit=limit)})
