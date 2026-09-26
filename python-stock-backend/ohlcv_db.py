"""Read-only aggregate API for the separate docker-class OHLCV database."""
import logging
import os
from datetime import date, datetime
from decimal import Decimal

from flask import Blueprint, jsonify, request
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


ohlcv_db_bp = Blueprint("ohlcv_db", __name__, url_prefix="/api/ohlcv-db")
_engine = None
logger = logging.getLogger(__name__)

_ROW_SORT_COLUMNS = {
    "ticker_code": "o.ticker_code",
    "name": "t.name",
    "market": "t.market",
    "trade_date": "o.trade_date",
    "open": "o.open",
    "high": "o.high",
    "low": "o.low",
    "close": "o.close",
    "adj_close": "o.adj_close",
    "volume": "o.volume",
    "change_rate": "change_rate",
    "traded_value": "traded_value",
}


def _url():
    return os.environ.get(
        "OHLCV_DATABASE_URL",
        "postgresql+psycopg://admin:admin1234@pg-stock:5432/admin",
    )


def _db():
    global _engine
    if _engine is None:
        _engine = create_engine(_url(), pool_pre_ping=True, pool_size=2, max_overflow=1)
    return _engine


def get_ohlcv_engine():
    """Shared engine for internal screens and authenticated Open API reads."""
    return _db()


def _value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _rows(result):
    return [{key: _value(value) for key, value in row.items()} for row in result.mappings()]


def _bounded_int(name, default, minimum, maximum):
    value = int(request.args.get(name, default))
    return max(minimum, min(value, maximum))


def _optional_number(name):
    raw = request.args.get(name, "").strip()
    return Decimal(raw) if raw else None


def _optional_date(name):
    raw = request.args.get(name, "").strip()
    return date.fromisoformat(raw) if raw else None


@ohlcv_db_bp.get("/summary")
def summary():
    try:
        with _db().connect() as conn:
            totals = _rows(conn.execute(text("""
                SELECT ohlcv_rows, ticker_count, first_date, last_date, refreshed_at
                FROM ohlcv_summary_snapshot WHERE snapshot_id=1
            """)))[0]
            yearly = _rows(conn.execute(text("""
                SELECT data_year AS year, row_count, ticker_count,
                       round(row_count::numeric / nullif(ticker_count, 0), 1) AS average_rows,
                       first_date, last_date, refreshed_at
                FROM ohlcv_yearly_summary ORDER BY data_year
            """)))
            quality = _rows(conn.execute(text("""
                SELECT quarantined_rows, affected_tickers
                FROM ohlcv_summary_snapshot WHERE snapshot_id=1
            """)))[0]
            markets = _rows(conn.execute(text("""
                SELECT market, ticker_count FROM ohlcv_market_summary ORDER BY market
            """)))
            sync = _rows(conn.execute(text("""
                SELECT tracked_ranges, success_ranges, failed_ranges, last_completed_at
                FROM ohlcv_summary_snapshot WHERE snapshot_id=1
            """)))[0]
        return jsonify({"totals": totals, "yearly": yearly, "quality": quality, "markets": markets, "sync": sync})
    except (IndexError, SQLAlchemyError):
        logger.exception("Failed to query OHLCV summary")
        return jsonify({"message": "OHLCV 일일 집계가 아직 준비되지 않았습니다."}), 503


@ohlcv_db_bp.get("/tickers")
def tickers():
    query = request.args.get("q", "").strip().upper()
    limit = max(1, min(int(request.args.get("limit", 100)), 200))
    offset = max(0, int(request.args.get("offset", 0)))
    try:
        with _db().connect() as conn:
            total = conn.execute(text("""
                SELECT count(DISTINCT ticker_code) FROM ohlcv
                WHERE ticker_code LIKE :query
            """), {"query": f"%{query}%"}).scalar_one()
            rows = _rows(conn.execute(text("""
                WITH per_year AS (
                    SELECT ticker_code, extract(year FROM trade_date)::int AS year, count(*) AS row_count
                    FROM ohlcv WHERE ticker_code LIKE :query GROUP BY ticker_code, 2
                ), per_ticker AS (
                    SELECT ticker_code, count(*) AS total_rows, min(trade_date) AS first_date, max(trade_date) AS last_date
                    FROM ohlcv WHERE ticker_code LIKE :query GROUP BY ticker_code
                ), yearly_json AS (
                    SELECT ticker_code, jsonb_object_agg(year, row_count ORDER BY year) AS yearly_rows
                    FROM per_year GROUP BY ticker_code
                )
                SELECT per_ticker.ticker_code, t.name, t.market, per_ticker.total_rows,
                       per_ticker.first_date, per_ticker.last_date, yearly_json.yearly_rows
                FROM per_ticker
                JOIN yearly_json USING (ticker_code)
                LEFT JOIN tickers t USING (ticker_code)
                ORDER BY ticker_code LIMIT :limit OFFSET :offset
            """), {"query": f"%{query}%", "limit": limit, "offset": offset}))
        return jsonify({"rows": rows, "total": total, "limit": limit, "offset": offset})
    except (ValueError, SQLAlchemyError):
        logger.exception("Failed to query OHLCV ticker summary")
        return jsonify({"message": "종목별 OHLCV 집계를 조회할 수 없습니다."}), 503


@ohlcv_db_bp.get("/rows")
def rows():
    """Return filtered daily OHLCV rows for the AG Grid infinite row model."""
    try:
        query = request.args.get("q", "").strip()
        market = request.args.get("market", "").strip()
        date_from = _optional_date("date_from")
        date_to = _optional_date("date_to")
        min_close = _optional_number("min_close")
        max_close = _optional_number("max_close")
        min_volume = _optional_number("min_volume")
        max_volume = _optional_number("max_volume")
        limit = _bounded_int("limit", 100, 1, 500)
        offset = _bounded_int("offset", 0, 0, 10_000_000)
        sort = request.args.get("sort", "trade_date").strip()
        direction = request.args.get("order", "desc").strip().lower()
    except (ValueError, ArithmeticError):
        return jsonify({"message": "검색 조건의 숫자 또는 날짜 형식이 올바르지 않습니다."}), 400

    if date_from and date_to and date_from > date_to:
        return jsonify({"message": "시작일은 종료일보다 늦을 수 없습니다."}), 400

    sort_column = _ROW_SORT_COLUMNS.get(sort, "o.trade_date")
    sort_direction = "ASC" if direction == "asc" else "DESC"
    clauses = []
    params = {"limit": limit, "offset": offset}

    if query:
        clauses.append("(o.ticker_code ILIKE :query OR COALESCE(t.name, '') ILIKE :query)")
        params["query"] = f"%{query}%"
    if market:
        clauses.append("t.market = :market")
        params["market"] = market
    for key, column, value, operator in (
        ("date_from", "o.trade_date", date_from, ">="),
        ("date_to", "o.trade_date", date_to, "<="),
        ("min_close", "o.close", min_close, ">="),
        ("max_close", "o.close", max_close, "<="),
        ("min_volume", "o.volume", min_volume, ">="),
        ("max_volume", "o.volume", max_volume, "<="),
    ):
        if value is not None:
            clauses.append(f"{column} {operator} :{key}")
            params[key] = value

    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    try:
        with _db().connect() as conn:
            total = conn.execute(text(f"""
                SELECT count(*) FROM ohlcv o
                JOIN tickers t USING (ticker_code)
                {where}
            """), params).scalar_one()
            result = _rows(conn.execute(text(f"""
                SELECT o.ticker_code, t.name, t.market, o.trade_date,
                       o.open, o.high, o.low, o.close, o.adj_close, o.volume,
                       CASE WHEN o.open > 0
                            THEN round(((o.close - o.open) / o.open * 100)::numeric, 4)
                       END AS change_rate,
                       round((o.close * o.volume)::numeric, 0) AS traded_value
                FROM ohlcv o
                JOIN tickers t USING (ticker_code)
                {where}
                ORDER BY {sort_column} {sort_direction}, o.ticker_code ASC, o.trade_date DESC
                LIMIT :limit OFFSET :offset
            """), params))
        return jsonify({"rows": result, "total": total, "limit": limit, "offset": offset})
    except SQLAlchemyError:
        logger.exception("Failed to query filtered OHLCV rows")
        return jsonify({"message": "OHLCV 상세 데이터를 조회할 수 없습니다."}), 503
