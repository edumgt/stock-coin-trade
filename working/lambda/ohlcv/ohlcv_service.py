"""pg-stock 읽기 전용 조회. python-stock-backend/app/services/ohlcv_store.py 와 같은 SQL을 사용한다."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import text

SUMMARY_SQL = text("""
  SELECT ohlcv_rows, ticker_count, first_date, last_date, refreshed_at
  FROM ohlcv_summary_snapshot WHERE snapshot_id=1
""")
YEARLY_SQL = text("""
  SELECT data_year AS year, row_count, ticker_count,
         round(row_count::numeric / nullif(ticker_count, 0), 1) AS average_rows,
         first_date, last_date, refreshed_at
  FROM ohlcv_yearly_summary ORDER BY data_year
""")
MARKETS_SQL = text("""
  SELECT market, ticker_count FROM ohlcv_market_summary ORDER BY market
""")
QUALITY_SQL = text("""
  SELECT quarantined_rows, affected_tickers,
         tracked_ranges, success_ranges, failed_ranges, last_completed_at
  FROM ohlcv_summary_snapshot WHERE snapshot_id=1
""")
TICKERS_COUNT_SQL = text("""
  SELECT count(DISTINCT ticker_code) FROM ohlcv WHERE ticker_code LIKE :query
""")
TICKERS_SQL = text("""
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
""")

ROW_SORT_COLUMNS = {
    "ticker_code": "o.ticker_code", "name": "t.name", "market": "t.market",
    "trade_date": "o.trade_date", "open": "o.open", "high": "o.high", "low": "o.low",
    "close": "o.close", "adj_close": "o.adj_close", "volume": "o.volume",
    "change_rate": "change_rate", "traded_value": "traded_value",
}


def _value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _rows(result):
    return [{key: _value(value) for key, value in row.items()} for row in result.mappings()]


def _bounded_int(args, name, default, minimum, maximum):
    value = int(args.get(name, default))
    return max(minimum, min(value, maximum))


def _optional_number(args, name):
    raw = (args.get(name) or "").strip()
    return Decimal(raw) if raw else None


def _optional_date(args, name):
    raw = (args.get(name) or "").strip()
    return date.fromisoformat(raw) if raw else None


def load_summary(engine) -> dict:
    with engine.connect() as conn:
        return _rows(conn.execute(SUMMARY_SQL))[0]


def load_yearly(engine) -> list:
    with engine.connect() as conn:
        return _rows(conn.execute(YEARLY_SQL))


def load_markets(engine) -> list:
    with engine.connect() as conn:
        return _rows(conn.execute(MARKETS_SQL))


def load_quality(engine) -> dict:
    with engine.connect() as conn:
        row = _rows(conn.execute(QUALITY_SQL))[0]
    return {
        "quality": {k: row[k] for k in ("quarantined_rows", "affected_tickers")},
        "sync": {k: row[k] for k in ("tracked_ranges", "success_ranges", "failed_ranges", "last_completed_at")},
    }


def load_tickers(engine, args) -> dict:
    query = (args.get("q") or "").strip().upper()
    limit = _bounded_int(args, "limit", 100, 1, 200)
    offset = _bounded_int(args, "offset", 0, 0, 10_000_000)
    params = {"query": f"%{query}%", "limit": limit, "offset": offset}
    with engine.connect() as conn:
        total = conn.execute(TICKERS_COUNT_SQL, params).scalar_one()
        rows = _rows(conn.execute(TICKERS_SQL, params))
    return {"rows": rows, "total": total, "limit": limit, "offset": offset}


class BadRequest(ValueError):
    """400 으로 응답할 입력 오류."""


def load_rows(engine, args) -> dict:
    try:
        query = (args.get("q") or "").strip()
        market = (args.get("market") or "").strip()
        date_from = _optional_date(args, "date_from")
        date_to = _optional_date(args, "date_to")
        min_close = _optional_number(args, "min_close")
        max_close = _optional_number(args, "max_close")
        min_volume = _optional_number(args, "min_volume")
        max_volume = _optional_number(args, "max_volume")
        limit = _bounded_int(args, "limit", 100, 1, 500)
        offset = _bounded_int(args, "offset", 0, 0, 10_000_000)
        sort = (args.get("sort") or "trade_date").strip()
        direction = (args.get("order") or "desc").strip().lower()
    except (ValueError, ArithmeticError):
        raise BadRequest("검색 조건의 숫자 또는 날짜 형식이 올바르지 않습니다.")
    if date_from and date_to and date_from > date_to:
        raise BadRequest("시작일은 종료일보다 늦을 수 없습니다.")

    sort_column = ROW_SORT_COLUMNS.get(sort, "o.trade_date")
    sort_direction = "ASC" if direction == "asc" else "DESC"
    clauses, params = [], {"limit": limit, "offset": offset}
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

    with engine.connect() as conn:
        total = conn.execute(text(f"""
            SELECT count(*) FROM ohlcv o JOIN tickers t USING (ticker_code) {where}
        """), params).scalar_one()
        rows = _rows(conn.execute(text(f"""
            SELECT o.ticker_code, t.name, t.market, o.trade_date,
                   o.open, o.high, o.low, o.close, o.adj_close, o.volume,
                   CASE WHEN o.open > 0
                        THEN round(((o.close - o.open) / o.open * 100)::numeric, 4)
                   END AS change_rate,
                   round((o.close * o.volume)::numeric, 0) AS traded_value
            FROM ohlcv o JOIN tickers t USING (ticker_code) {where}
            ORDER BY {sort_column} {sort_direction}, o.ticker_code ASC, o.trade_date DESC
            LIMIT :limit OFFSET :offset
        """), params))
    return {"rows": rows, "total": total, "limit": limit, "offset": offset}
