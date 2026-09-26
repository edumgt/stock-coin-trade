import hashlib
import re
import threading
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from functools import wraps

from flask import Blueprint, g, jsonify, request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

import stock_trading
from db import session_scope
from models import ApiKey, Member
from ohlcv_db import get_ohlcv_engine
from stock_market import get_quote_cached, list_krx_stocks

open_api_bp = Blueprint("openapi", __name__, url_prefix="/openapi/v1")

RATE_LIMIT_MAX = 60          # requests
RATE_LIMIT_WINDOW = 60       # seconds
_rate_buckets: dict[int, list] = {}
_rate_lock = threading.Lock()
_TICKER_CODE = re.compile(r"^[0-9A-Za-z._-]{1,20}$")


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


def _json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _result_rows(result):
    return [{key: _json_value(value) for key, value in row.items()} for row in result.mappings()]


def _bounded_int(name, default, minimum, maximum):
    try:
        return max(minimum, min(int(request.args.get(name, default)), maximum))
    except (TypeError, ValueError):
        raise ValueError(f"{name}은 {minimum}~{maximum} 범위의 정수여야 합니다.")


def _date_arg(name):
    raw = request.args.get(name, "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ValueError(f"{name}은 YYYY-MM-DD 형식이어야 합니다.")


@open_api_bp.get("/stocks")
@require_api_key
def list_stocks():
    try:
        limit = max(1, min(int(request.args.get("limit", 30)), 100))
        return jsonify({"stocks": list_krx_stocks(limit)})
    except Exception as exc:
        return jsonify({"error": "MARKET_DATA_UNAVAILABLE", "message": str(exc)}), 503


@open_api_bp.get("/quote/<symbol>")
@require_api_key
def quote(symbol):
    try:
        return jsonify(get_quote_cached(symbol.upper()))
    except RuntimeError as e:
        return jsonify({"error": "MARKET_DATA_UNAVAILABLE", "message": str(e)}), 503
    except ValueError as e:
        return jsonify({"error": "NOT_FOUND", "message": str(e)}), 404


@open_api_bp.get("/ohlcv/tickers")
@require_api_key
def ohlcv_tickers():
    """Discover tickers that have collected OHLCV data."""
    try:
        query = request.args.get("q", "").strip()
        market = request.args.get("market", "").strip()
        year = request.args.get("year", "").strip()
        limit = _bounded_int("limit", 100, 1, 200)
        offset = _bounded_int("offset", 0, 0, 10_000_000)
        params = {"query": f"%{query}%", "market": market, "limit": limit, "offset": offset}
        clauses = ["(:query = '%%' OR o.ticker_code ILIKE :query OR COALESCE(t.name,'') ILIKE :query)",
                   "(:market = '' OR t.market = :market)"]
        if year:
            year_number = int(year)
            if year_number < 1990 or year_number > date.today().year + 1:
                raise ValueError("year 범위가 올바르지 않습니다.")
            clauses.append("o.trade_date >= :year_start AND o.trade_date < :year_end")
            params.update({"year_start": date(year_number, 1, 1), "year_end": date(year_number + 1, 1, 1)})
        where = " AND ".join(clauses)
        with get_ohlcv_engine().connect() as conn:
            total = conn.execute(text(f"""
                SELECT count(DISTINCT o.ticker_code) FROM ohlcv o
                LEFT JOIN tickers t USING(ticker_code) WHERE {where}
            """), params).scalar_one()
            rows = _result_rows(conn.execute(text(f"""
                SELECT o.ticker_code, t.name, t.market, count(*) AS row_count,
                       min(o.trade_date) AS first_date, max(o.trade_date) AS last_date
                FROM ohlcv o LEFT JOIN tickers t USING(ticker_code)
                WHERE {where} GROUP BY o.ticker_code,t.name,t.market
                ORDER BY o.ticker_code LIMIT :limit OFFSET :offset
            """), params))
        return jsonify({"tickers": rows, "total": total, "limit": limit, "offset": offset})
    except (ValueError, TypeError):
        return jsonify({"error": "INVALID_REQUEST", "message": "year 및 페이지 조건을 확인하세요."}), 400
    except SQLAlchemyError:
        return jsonify({"error": "OHLCV_UNAVAILABLE", "message": "OHLCV 저장소를 조회할 수 없습니다."}), 503


@open_api_bp.get("/ohlcv/<ticker_code>")
@require_api_key
def ohlcv_history(ticker_code):
    """Return paginated daily OHLCV for one ticker and year/date range."""
    code = ticker_code.upper().strip()
    if not _TICKER_CODE.fullmatch(code):
        return jsonify({"error": "INVALID_REQUEST", "message": "ticker_code 형식이 올바르지 않습니다."}), 400
    try:
        limit = _bounded_int("limit", 250, 1, 1000)
        offset = _bounded_int("offset", 0, 0, 10_000_000)
        order = request.args.get("order", "asc").strip().lower()
        if order not in {"asc", "desc"}:
            raise ValueError("order는 asc 또는 desc여야 합니다.")
        date_from = _date_arg("date_from")
        date_to = _date_arg("date_to")
        raw_year = request.args.get("year", "").strip()
        year = int(raw_year) if raw_year else None
        if year is not None:
            if year < 1990 or year > date.today().year + 1:
                raise ValueError("year 범위가 올바르지 않습니다.")
            date_from = max(date_from or date(year, 1, 1), date(year, 1, 1))
            date_to = min(date_to or date(year, 12, 31), date(year, 12, 31))
        elif date_from is None and date_to is None:
            year = date.today().year
            date_from, date_to = date(year, 1, 1), date(year, 12, 31)
        if date_from and date_to and date_from > date_to:
            raise ValueError("date_from은 date_to보다 늦을 수 없습니다.")

        clauses = ["o.ticker_code=:code"]
        params = {"code": code, "limit": limit, "offset": offset}
        if date_from:
            clauses.append("o.trade_date >= :date_from")
            params["date_from"] = date_from
        if date_to:
            clauses.append("o.trade_date <= :date_to")
            params["date_to"] = date_to
        where = " AND ".join(clauses)
        direction = "ASC" if order == "asc" else "DESC"
        with get_ohlcv_engine().connect() as conn:
            ticker = conn.execute(text("SELECT ticker_code,name,market FROM tickers WHERE ticker_code=:code"), {"code": code}).mappings().first()
            if not ticker:
                return jsonify({"error": "NOT_FOUND", "message": "OHLCV 종목을 찾을 수 없습니다."}), 404
            total = conn.execute(text(f"SELECT count(*) FROM ohlcv o WHERE {where}"), params).scalar_one()
            rows = _result_rows(conn.execute(text(f"""
                SELECT o.trade_date,o.open,o.high,o.low,o.close,o.adj_close,o.volume
                FROM ohlcv o WHERE {where}
                ORDER BY o.trade_date {direction} LIMIT :limit OFFSET :offset
            """), params))
        ticker_data = {key: _json_value(value) for key, value in ticker.items()}
        next_offset = offset + len(rows) if offset + len(rows) < total else None
        return jsonify({"ticker": ticker_data, "rows": rows, "total": total,
                        "limit": limit, "offset": offset, "nextOffset": next_offset,
                        "filters": {"year": year,
                                    "dateFrom": date_from.isoformat() if date_from else None,
                                    "dateTo": date_to.isoformat() if date_to else None,
                                    "order": order}})
    except (ValueError, TypeError) as exc:
        return jsonify({"error": "INVALID_REQUEST", "message": str(exc)}), 400
    except SQLAlchemyError:
        return jsonify({"error": "OHLCV_UNAVAILABLE", "message": "OHLCV 저장소를 조회할 수 없습니다."}), 503


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
