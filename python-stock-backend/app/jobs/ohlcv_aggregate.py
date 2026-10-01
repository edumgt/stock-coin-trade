"""일일 배치만 갱신하는 OHLCV 대시보드 집계 스냅샷."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import create_engine, text

from app.core.config import get_settings


def database_url() -> str:
    return get_settings().ohlcv_database_url


def create_ohlcv_engine():
    return create_engine(database_url(), pool_pre_ping=True, pool_size=2, max_overflow=1)


def ensure_aggregate_tables(engine):
    """스냅샷 테이블과 하루 1회 실행 원장을 만든다."""
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ohlcv_summary_snapshot (
                snapshot_id smallint PRIMARY KEY CHECK (snapshot_id = 1),
                ohlcv_rows bigint NOT NULL DEFAULT 0,
                ticker_count integer NOT NULL DEFAULT 0,
                first_date date,
                last_date date,
                quarantined_rows bigint NOT NULL DEFAULT 0,
                affected_tickers integer NOT NULL DEFAULT 0,
                tracked_ranges integer NOT NULL DEFAULT 0,
                success_ranges integer NOT NULL DEFAULT 0,
                failed_ranges integer NOT NULL DEFAULT 0,
                last_completed_at timestamptz,
                refreshed_at timestamptz NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ohlcv_yearly_summary (
                data_year smallint PRIMARY KEY,
                row_count bigint NOT NULL,
                ticker_count integer NOT NULL,
                first_date date NOT NULL,
                last_date date NOT NULL,
                refreshed_at timestamptz NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ohlcv_market_summary (
                market varchar(40) PRIMARY KEY,
                ticker_count integer NOT NULL,
                refreshed_at timestamptz NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ohlcv_daily_batch_runs (
                batch_date date PRIMARY KEY,
                status varchar(30) NOT NULL,
                started_at timestamptz NOT NULL,
                completed_at timestamptz,
                fetched_rows bigint NOT NULL DEFAULT 0,
                upserted_rows bigint NOT NULL DEFAULT 0,
                aggregate_refreshed_at timestamptz,
                error_message varchar(500)
            )
        """))


def refresh_ohlcv_aggregates(engine=None):
    """집계를 REPEATABLE READ 트랜잭션 하나에서 교체한다."""
    engine = engine or create_ohlcv_engine()
    ensure_aggregate_tables(engine)
    refreshed_at = datetime.now(UTC)
    with engine.begin() as conn:
        conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('ohlcv-aggregate-refresh'))"))
        quality_exists = bool(conn.execute(text("SELECT to_regclass('public.ohlcv_data_quality_issues')")).scalar_one())
        sync_exists = bool(conn.execute(text("SELECT to_regclass('public.ohlcv_sync_status')")).scalar_one())
        quality = {"quarantined_rows": 0, "affected_tickers": 0}
        if quality_exists:
            quality = dict(conn.execute(text("""
                SELECT count(*) AS quarantined_rows,
                       count(DISTINCT ticker_code) AS affected_tickers
                FROM ohlcv_data_quality_issues
            """)).mappings().one())
        sync = {"tracked_ranges": 0, "success_ranges": 0, "failed_ranges": 0, "last_completed_at": None}
        if sync_exists:
            sync = dict(conn.execute(text("""
                SELECT count(*) AS tracked_ranges,
                       count(*) FILTER (WHERE status IN ('success','empty')) AS success_ranges,
                       count(*) FILTER (WHERE status='failed') AS failed_ranges,
                       max(completed_at) AS last_completed_at
                FROM ohlcv_sync_status
            """)).mappings().one())

        conn.execute(text("""
            INSERT INTO ohlcv_summary_snapshot
                (snapshot_id, ohlcv_rows, ticker_count, first_date, last_date,
                 quarantined_rows, affected_tickers, tracked_ranges, success_ranges,
                 failed_ranges, last_completed_at, refreshed_at)
            SELECT 1, count(*), count(DISTINCT ticker_code), min(trade_date), max(trade_date),
                   :quarantined_rows, :affected_tickers, :tracked_ranges, :success_ranges,
                   :failed_ranges, :last_completed_at, :refreshed_at
            FROM ohlcv
            ON CONFLICT (snapshot_id) DO UPDATE SET
                ohlcv_rows=EXCLUDED.ohlcv_rows,
                ticker_count=EXCLUDED.ticker_count,
                first_date=EXCLUDED.first_date,
                last_date=EXCLUDED.last_date,
                quarantined_rows=EXCLUDED.quarantined_rows,
                affected_tickers=EXCLUDED.affected_tickers,
                tracked_ranges=EXCLUDED.tracked_ranges,
                success_ranges=EXCLUDED.success_ranges,
                failed_ranges=EXCLUDED.failed_ranges,
                last_completed_at=EXCLUDED.last_completed_at,
                refreshed_at=EXCLUDED.refreshed_at
        """), {**quality, **sync, "refreshed_at": refreshed_at})
        conn.execute(text("""
            INSERT INTO ohlcv_yearly_summary
                (data_year, row_count, ticker_count, first_date, last_date, refreshed_at)
            SELECT extract(year FROM trade_date)::smallint, count(*),
                   count(DISTINCT ticker_code), min(trade_date), max(trade_date), :refreshed_at
            FROM ohlcv GROUP BY 1
            ON CONFLICT (data_year) DO UPDATE SET
                row_count=EXCLUDED.row_count,
                ticker_count=EXCLUDED.ticker_count,
                first_date=EXCLUDED.first_date,
                last_date=EXCLUDED.last_date,
                refreshed_at=EXCLUDED.refreshed_at
        """), {"refreshed_at": refreshed_at})
        conn.execute(text("""
            DELETE FROM ohlcv_yearly_summary
            WHERE data_year NOT IN (
                SELECT DISTINCT extract(year FROM trade_date)::smallint FROM ohlcv
            )
        """))
        conn.execute(text("""
            INSERT INTO ohlcv_market_summary (market, ticker_count, refreshed_at)
            SELECT COALESCE(NULLIF(market, ''), '미분류'), count(*), :refreshed_at
            FROM tickers GROUP BY 1
            ON CONFLICT (market) DO UPDATE SET
                ticker_count=EXCLUDED.ticker_count,
                refreshed_at=EXCLUDED.refreshed_at
        """), {"refreshed_at": refreshed_at})
        conn.execute(text("""
            DELETE FROM ohlcv_market_summary
            WHERE market NOT IN (
                SELECT DISTINCT COALESCE(NULLIF(market, ''), '미분류') FROM tickers
            )
        """))
        snapshot = dict(conn.execute(text("""
            SELECT ohlcv_rows, ticker_count, first_date, last_date, refreshed_at
            FROM ohlcv_summary_snapshot WHERE snapshot_id=1
        """)).mappings().one())
    return snapshot


def bootstrap_ohlcv_aggregates(engine=None):
    """원본 OHLCV 데이터가 적재된 뒤 스냅샷을 한 번 만든다."""
    engine = engine or create_ohlcv_engine()
    ensure_aggregate_tables(engine)
    with engine.connect() as conn:
        exists = conn.execute(text("SELECT EXISTS (SELECT 1 FROM ohlcv_summary_snapshot WHERE snapshot_id=1)")).scalar_one()
    return {"status": "already_initialized"} if exists else {"status": "initialized", **refresh_ohlcv_aggregates(engine)}


def claim_daily_batch(engine, batch_date=None):
    """하루에 예약 OHLCV 배치 하나만 원자적으로 허용한다."""
    ensure_aggregate_tables(engine)
    batch_date = batch_date or date.today()
    with engine.begin() as conn:
        claimed = conn.execute(text("""
            INSERT INTO ohlcv_daily_batch_runs (batch_date, status, started_at)
            VALUES (:batch_date, 'running', :started_at)
            ON CONFLICT (batch_date) DO NOTHING
            RETURNING batch_date
        """), {"batch_date": batch_date, "started_at": datetime.now(UTC)}).scalar_one_or_none()
    return claimed is not None


def finish_daily_batch(engine, batch_date, *, status, fetched_rows=0, upserted_rows=0, refreshed_at=None, error=None):
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE ohlcv_daily_batch_runs
            SET status=:status, completed_at=:completed_at,
                fetched_rows=:fetched_rows, upserted_rows=:upserted_rows,
                aggregate_refreshed_at=:refreshed_at, error_message=:error
            WHERE batch_date=:batch_date
        """), {
            "batch_date": batch_date, "status": status,
            "completed_at": datetime.now(UTC),
            "fetched_rows": fetched_rows, "upserted_rows": upserted_rows,
            "refreshed_at": refreshed_at,
            "error": str(error)[:500] if error else None,
        })
