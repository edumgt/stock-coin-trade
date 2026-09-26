"""Scheduled, idempotent OHLCV collection grouped by ticker and calendar year."""
import logging
import os
import threading
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import create_engine, text

from crawl_major_ohlcv import MAJOR_TICKERS, fetch_naver, fetch_yahoo, upsert_ticker
from ohlcv_aggregate import (
    claim_daily_batch,
    create_ohlcv_engine,
    finish_daily_batch,
    refresh_ohlcv_aggregates,
)


log = logging.getLogger(__name__)
_sync_lock = threading.Lock()


def _enabled(name, default=True):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def sync_enabled():
    return _enabled("OHLCV_SYNC_ENABLED", True)


def _database_url():
    return os.environ.get(
        "OHLCV_DATABASE_URL",
        "postgresql+psycopg://admin:admin1234@pg-stock:5432/admin",
    )


def _ensure_status_table(engine):
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ohlcv_sync_status (
                ticker_code varchar(20) NOT NULL,
                data_year smallint NOT NULL,
                provider varchar(20) NOT NULL,
                status varchar(20) NOT NULL,
                requested_from date NOT NULL,
                requested_to date NOT NULL,
                fetched_rows integer NOT NULL DEFAULT 0,
                upserted_rows integer NOT NULL DEFAULT 0,
                last_error varchar(500),
                started_at timestamptz NOT NULL,
                completed_at timestamptz NOT NULL,
                PRIMARY KEY (ticker_code, data_year)
            )
        """))


def _save_status(engine, *, code, year, provider, status, start, end,
                 fetched, upserted, error, started):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO ohlcv_sync_status
                (ticker_code,data_year,provider,status,requested_from,requested_to,
                 fetched_rows,upserted_rows,last_error,started_at,completed_at)
            VALUES
                (:code,:year,:provider,:status,:start,:end,:fetched,:upserted,
                 :error,:started,:completed)
            ON CONFLICT (ticker_code,data_year) DO UPDATE SET
                provider=EXCLUDED.provider, status=EXCLUDED.status,
                requested_from=EXCLUDED.requested_from, requested_to=EXCLUDED.requested_to,
                fetched_rows=EXCLUDED.fetched_rows, upserted_rows=EXCLUDED.upserted_rows,
                last_error=EXCLUDED.last_error, started_at=EXCLUDED.started_at,
                completed_at=EXCLUDED.completed_at
        """), {
            "code": code, "year": year, "provider": provider, "status": status,
            "start": start, "end": end - timedelta(days=1), "fetched": fetched,
            "upserted": upserted, "error": str(error)[:500] if error else None,
            "started": started, "completed": datetime.now(timezone.utc),
        })


def _ticker_universe(engine):
    selection = os.environ.get("OHLCV_SYNC_TICKERS", "major").strip()
    if not selection or selection.lower() == "major":
        return dict(MAJOR_TICKERS)

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT ticker_code,name,market FROM tickers ORDER BY ticker_code")).mappings()
        available = {
            row["ticker_code"]: (row["name"] or row["ticker_code"], row["market"] or "KOSPI")
            for row in rows
        }
    if selection.lower() == "all":
        limit = max(0, int(os.environ.get("OHLCV_SYNC_MAX_TICKERS", "0")))
        items = list(available.items())
        return dict(items[:limit] if limit else items)

    requested = [value.strip().upper() for value in selection.split(",") if value.strip()]
    unknown = [code for code in requested if code not in available and code not in MAJOR_TICKERS]
    if unknown:
        raise ValueError(f"OHLCV_SYNC_TICKERS에 등록되지 않은 종목이 있습니다: {', '.join(unknown)}")
    return {code: available[code] if code in available else MAJOR_TICKERS[code] for code in requested}


def _existing_years(engine, code):
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT extract(year FROM trade_date)::int AS data_year,
                   max(trade_date) AS last_date, count(*) AS row_count
            FROM ohlcv WHERE ticker_code=:code GROUP BY 1
        """), {"code": code}).mappings()
        return {row["data_year"]: {"last_date": row["last_date"], "row_count": row["row_count"]} for row in rows}


def plan_year_ranges(existing, start_year, as_of, reconcile=False, correction_days=7):
    """Return inclusive/exclusive ranges that need collection."""
    ranges = []
    end_exclusive = as_of + timedelta(days=1)
    for year in range(start_year, as_of.year + 1):
        year_start = date(year, 1, 1)
        year_end = min(date(year + 1, 1, 1), end_exclusive)
        state = existing.get(year)
        if reconcile or not state:
            ranges.append((year, year_start, year_end))
        elif year == as_of.year:
            refresh_start = max(year_start, state["last_date"] - timedelta(days=max(0, correction_days)))
            ranges.append((year, refresh_start, year_end))
    return ranges


def _download(provider, code, market, start, end):
    if provider == "naver":
        return fetch_naver(code, start, end)
    if provider == "yahoo":
        return fetch_yahoo(code, market, start, end)
    try:
        rows = fetch_yahoo(code, market, start, end)
    except Exception:
        log.warning("Yahoo OHLCV failed for %s; falling back to Naver", code, exc_info=True)
        rows = []
    return rows or fetch_naver(code, start, end)


def collect_ohlcv(*, reconcile=False, as_of=None, engine=None, downloader=None):
    """Collect missing years and refresh the current year for each configured ticker."""
    if not _sync_lock.acquire(blocking=False):
        return {"status": "already_running", "tickers": 0, "ranges": 0, "failed": []}
    try:
        as_of = as_of or date.today()
        provider = os.environ.get("OHLCV_SYNC_PROVIDER", "naver").strip().lower()
        if provider not in {"naver", "yahoo", "auto"}:
            raise ValueError("OHLCV_SYNC_PROVIDER는 naver, yahoo, auto 중 하나여야 합니다.")
        start_year = int(os.environ.get("OHLCV_SYNC_START_YEAR", "2020"))
        correction_days = int(os.environ.get("OHLCV_SYNC_CORRECTION_DAYS", "7"))
        engine = engine or create_engine(_database_url(), pool_pre_ping=True, pool_size=2, max_overflow=1)
        _ensure_status_table(engine)
        universe = _ticker_universe(engine)
        fetch = downloader or _download
        summary = {"status": "completed", "tickers": len(universe), "ranges": 0,
                   "fetchedRows": 0, "upsertedRows": 0, "failed": []}
        for code, (name, market) in universe.items():
            existing = _existing_years(engine, code)
            ranges = plan_year_ranges(existing, start_year, as_of, reconcile, correction_days)
            for year, start, end in ranges:
                summary["ranges"] += 1
                started = datetime.now(timezone.utc)
                try:
                    rows = fetch(provider, code, market, start, end)
                    upserted = upsert_ticker(engine, code, name, market, rows)
                    status = "success" if rows else "empty"
                    _save_status(engine, code=code, year=year, provider=provider, status=status,
                                 start=start, end=end, fetched=len(rows), upserted=upserted,
                                 error=None, started=started)
                    summary["fetchedRows"] += len(rows)
                    summary["upsertedRows"] += max(0, upserted or 0)
                    log.info("OHLCV %s %s: %s rows (%s..%s)", code, year, len(rows), start, end - timedelta(days=1))
                except Exception as exc:
                    summary["failed"].append({"ticker": code, "year": year, "error": str(exc)[:200]})
                    _save_status(engine, code=code, year=year, provider=provider, status="failed",
                                 start=start, end=end, fetched=0, upserted=0, error=exc, started=started)
                    log.exception("OHLCV collection failed for %s/%s", code, year)
        if summary["failed"]:
            summary["status"] = "partial_failure"
        return summary
    finally:
        _sync_lock.release()


def run_incremental_sync():
    if not sync_enabled():
        return {"status": "disabled"}
    engine = create_ohlcv_engine()
    result = collect_ohlcv(reconcile=False, engine=engine)
    result["aggregate"] = refresh_ohlcv_aggregates(engine)
    log.info("Incremental OHLCV sync finished: %s", result)
    return result


def run_daily_ohlcv_batch(as_of=None):
    """Run collection and persisted aggregation at most once per local date."""
    if not sync_enabled():
        return {"status": "disabled"}
    batch_date = as_of or date.today()
    engine = create_ohlcv_engine()
    if not claim_daily_batch(engine, batch_date):
        result = {"status": "already_executed", "batchDate": batch_date.isoformat()}
        log.info("Daily OHLCV batch skipped: %s", result)
        return result
    try:
        result = collect_ohlcv(reconcile=False, as_of=batch_date, engine=engine)
        aggregate = refresh_ohlcv_aggregates(engine)
        status = result.get("status", "completed")
        finish_daily_batch(
            engine, batch_date, status=status,
            fetched_rows=result.get("fetchedRows", 0),
            upserted_rows=result.get("upsertedRows", 0),
            refreshed_at=aggregate.get("refreshed_at"),
        )
        result.update({"batchDate": batch_date.isoformat(), "aggregate": aggregate})
        log.info("Daily OHLCV batch finished: %s", result)
        return result
    except Exception as exc:
        finish_daily_batch(engine, batch_date, status="failed", error=exc)
        log.exception("Daily OHLCV batch failed")
        raise
