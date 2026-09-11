"""Read-only aggregate API for the separate docker-class OHLCV database."""
import os
from datetime import date, datetime
from decimal import Decimal

from flask import Blueprint, jsonify, request
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


ohlcv_db_bp = Blueprint("ohlcv_db", __name__, url_prefix="/api/ohlcv-db")
_engine = None


def _url():
    return os.environ.get(
        "OHLCV_DATABASE_URL",
        "postgresql+psycopg://admin:admin1234@host.docker.internal:5433/admin",
    )


def _db():
    global _engine
    if _engine is None:
        _engine = create_engine(_url(), pool_pre_ping=True, pool_size=2, max_overflow=1)
    return _engine


def _value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _rows(result):
    return [{key: _value(value) for key, value in row.items()} for row in result.mappings()]


@ohlcv_db_bp.get("/summary")
def summary():
    try:
        with _db().connect() as conn:
            totals = _rows(conn.execute(text("""
                SELECT count(*) AS ohlcv_rows, count(DISTINCT ticker_code) AS ticker_count,
                       min(trade_date) AS first_date, max(trade_date) AS last_date
                FROM ohlcv
            """)))[0]
            yearly = _rows(conn.execute(text("""
                SELECT extract(year FROM trade_date)::int AS year, count(*) AS row_count,
                       count(DISTINCT ticker_code) AS ticker_count,
                       round(count(*)::numeric / nullif(count(DISTINCT ticker_code), 0), 1) AS average_rows
                FROM ohlcv GROUP BY 1 ORDER BY 1
            """)))
            quality = _rows(conn.execute(text("""
                SELECT count(*) AS quarantined_rows, count(DISTINCT ticker_code) AS affected_tickers
                FROM ohlcv_data_quality_issues
            """)))[0]
            markets = _rows(conn.execute(text("""
                SELECT market, count(*) AS ticker_count FROM tickers GROUP BY market ORDER BY market
            """)))
        return jsonify({"totals": totals, "yearly": yearly, "quality": quality, "markets": markets})
    except SQLAlchemyError:
        return jsonify({"message": "OHLCV DB 집계를 조회할 수 없습니다."}), 503


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
        return jsonify({"message": "종목별 OHLCV 집계를 조회할 수 없습니다."}), 503
