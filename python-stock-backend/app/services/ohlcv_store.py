"""별도 docker-class OHLCV 저장소(pg-stock) 읽기 전용 조회."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import create_engine, text

from app.core.config import get_settings

_engine = None

ROW_SORT_COLUMNS = {
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


def engine():
    """내부 화면과 인증 Open API 조회가 공유하는 엔진."""
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().ohlcv_database_url, pool_pre_ping=True, pool_size=2, max_overflow=1)
    return _engine


def json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value


def rows_of(result) -> list[dict]:
    return [{key: json_value(value) for key, value in row.items()} for row in result.mappings()]


def summary() -> dict:
    with engine().connect() as conn:
        totals = rows_of(conn.execute(text("""
            SELECT ohlcv_rows, ticker_count, first_date, last_date, refreshed_at
            FROM ohlcv_summary_snapshot WHERE snapshot_id=1
        """)))[0]
        yearly = rows_of(conn.execute(text("""
            SELECT data_year AS year, row_count, ticker_count,
                   round(row_count::numeric / nullif(ticker_count, 0), 1) AS average_rows,
                   first_date, last_date, refreshed_at
            FROM ohlcv_yearly_summary ORDER BY data_year
        """)))
        quality = rows_of(conn.execute(text("""
            SELECT quarantined_rows, affected_tickers
            FROM ohlcv_summary_snapshot WHERE snapshot_id=1
        """)))[0]
        markets = rows_of(conn.execute(text("SELECT market, ticker_count FROM ohlcv_market_summary ORDER BY market")))
        sync = rows_of(conn.execute(text("""
            SELECT tracked_ranges, success_ranges, failed_ranges, last_completed_at
            FROM ohlcv_summary_snapshot WHERE snapshot_id=1
        """)))[0]
    return {"totals": totals, "yearly": yearly, "quality": quality, "markets": markets, "sync": sync}


def ticker_summaries(query: str, limit: int, offset: int) -> dict:
    with engine().connect() as conn:
        total = conn.execute(text("""
            SELECT count(DISTINCT ticker_code) FROM ohlcv
            WHERE ticker_code LIKE :query
        """), {"query": f"%{query}%"}).scalar_one()
        rows = rows_of(conn.execute(text("""
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
    return {"rows": rows, "total": total, "limit": limit, "offset": offset}


def filtered_rows(*, query: str, market: str, date_from: date | None, date_to: date | None,
                  min_close: Decimal | None, max_close: Decimal | None, min_volume: Decimal | None,
                  max_volume: Decimal | None, limit: int, offset: int, sort: str, direction: str) -> dict:
    """AG Grid infinite row model용 필터링된 일별 OHLCV 행."""
    sort_column = ROW_SORT_COLUMNS.get(sort, "o.trade_date")
    sort_direction = "ASC" if direction == "asc" else "DESC"
    clauses = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}

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
    with engine().connect() as conn:
        total = conn.execute(text(f"""
            SELECT count(*) FROM ohlcv o
            JOIN tickers t USING (ticker_code)
            {where}
        """), params).scalar_one()
        result = rows_of(conn.execute(text(f"""
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
    return {"rows": result, "total": total, "limit": limit, "offset": offset}


# ── Open API(공개) 조회 ──────────────────────────────────────────────────────

def public_tickers(*, query: str, market: str, year: int | None, limit: int, offset: int) -> dict:
    params: dict[str, Any] = {"query": f"%{query}%", "market": market, "limit": limit, "offset": offset}
    clauses = ["(:query = '%%' OR o.ticker_code ILIKE :query OR COALESCE(t.name,'') ILIKE :query)",
               "(:market = '' OR t.market = :market)"]
    if year is not None:
        clauses.append("o.trade_date >= :year_start AND o.trade_date < :year_end")
        params.update({"year_start": date(year, 1, 1), "year_end": date(year + 1, 1, 1)})
    where = " AND ".join(clauses)
    with engine().connect() as conn:
        total = conn.execute(text(f"""
            SELECT count(DISTINCT o.ticker_code) FROM ohlcv o
            LEFT JOIN tickers t USING(ticker_code) WHERE {where}
        """), params).scalar_one()
        rows = rows_of(conn.execute(text(f"""
            SELECT o.ticker_code, t.name, t.market, count(*) AS row_count,
                   min(o.trade_date) AS first_date, max(o.trade_date) AS last_date
            FROM ohlcv o LEFT JOIN tickers t USING(ticker_code)
            WHERE {where} GROUP BY o.ticker_code,t.name,t.market
            ORDER BY o.ticker_code LIMIT :limit OFFSET :offset
        """), params))
    return {"tickers": rows, "total": total, "limit": limit, "offset": offset}


def public_history(*, code: str, date_from: date | None, date_to: date | None, order: str, limit: int, offset: int) -> dict | None:
    """종목 하나의 일별 OHLCV를 페이지 단위로 반환한다. 종목이 없으면 None."""
    clauses = ["o.ticker_code=:code"]
    params: dict[str, Any] = {"code": code, "limit": limit, "offset": offset}
    if date_from:
        clauses.append("o.trade_date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        clauses.append("o.trade_date <= :date_to")
        params["date_to"] = date_to
    where = " AND ".join(clauses)
    direction = "ASC" if order == "asc" else "DESC"
    with engine().connect() as conn:
        ticker = conn.execute(text("SELECT ticker_code,name,market FROM tickers WHERE ticker_code=:code"), {"code": code}).mappings().first()
        if not ticker:
            return None
        total = conn.execute(text(f"SELECT count(*) FROM ohlcv o WHERE {where}"), params).scalar_one()
        rows = rows_of(conn.execute(text(f"""
            SELECT o.trade_date,o.open,o.high,o.low,o.close,o.adj_close,o.volume
            FROM ohlcv o WHERE {where}
            ORDER BY o.trade_date {direction} LIMIT :limit OFFSET :offset
        """), params))
    ticker_data = {key: json_value(value) for key, value in ticker.items()}
    next_offset = offset + len(rows) if offset + len(rows) < total else None
    return {"ticker": ticker_data, "rows": rows, "total": total, "limit": limit, "offset": offset, "nextOffset": next_offset}


def search_tickers(*, query: str, limit: int) -> list[dict]:
    """종목코드/종목명 부분일치로 수집된 종목을 찾는다 — 타입어헤드 전용 경량 조회.

    ``public_tickers`` 는 ohlcv 66만 행을 GROUP BY 하느라 1초를 넘긴다. 종목 검색
    자동완성은 코드·이름·시장만 있으면 되므로 2,700행짜리 ``tickers`` 만 훑는다.
    정렬은 ① 코드 완전일치 ② 이름 완전일치 ③ 이름이 검색어로 시작 ④ 짧은 이름 순이다
    (예: "카카오" → 카카오 > 카카오뱅크 > 카카오게임즈).
    """
    q = query.strip()
    if not q:
        return []
    with engine().connect() as conn:
        return rows_of(conn.execute(text("""
            SELECT ticker_code, name, market
            FROM tickers
            WHERE ticker_code ILIKE :like OR COALESCE(name, '') ILIKE :like
            ORDER BY (ticker_code = :exact) DESC,
                     (COALESCE(name, '') = :exact) DESC,
                     (COALESCE(name, '') ILIKE :prefix) DESC,
                     length(COALESCE(name, '')) ASC,
                     ticker_code ASC
            LIMIT :limit
        """), {"like": f"%{q}%", "exact": q, "prefix": f"{q}%", "limit": limit}))
