-- Fresh-install schema for the separate Korean-stock OHLCV PostgreSQL database.
-- Existing installations are not changed: docker-entrypoint-initdb.d runs only
-- when the pg-stock-data volume is empty.

CREATE TABLE IF NOT EXISTS tickers (
    ticker_code varchar(20) PRIMARY KEY,
    name varchar(100),
    market varchar(20) DEFAULT 'KOSPI',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ohlcv (
    ticker_code varchar(20) NOT NULL REFERENCES tickers(ticker_code),
    trade_date date NOT NULL,
    open numeric(14, 4),
    high numeric(14, 4),
    low numeric(14, 4),
    close numeric(14, 4),
    adj_close numeric(14, 4),
    volume bigint,
    PRIMARY KEY (ticker_code, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_ohlcv_trade_date ON ohlcv (trade_date);

CREATE TABLE IF NOT EXISTS ohlcv_data_quality_issues (
    ticker_code varchar(20) NOT NULL,
    trade_date date NOT NULL,
    reason text NOT NULL,
    source_file text NOT NULL,
    detected_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ticker_code, trade_date, reason)
);

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
);

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
);

CREATE TABLE IF NOT EXISTS ohlcv_yearly_summary (
    data_year smallint PRIMARY KEY,
    row_count bigint NOT NULL,
    ticker_count integer NOT NULL,
    first_date date NOT NULL,
    last_date date NOT NULL,
    refreshed_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS ohlcv_market_summary (
    market varchar(40) PRIMARY KEY,
    ticker_count integer NOT NULL,
    refreshed_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS ohlcv_daily_batch_runs (
    batch_date date PRIMARY KEY,
    status varchar(30) NOT NULL,
    started_at timestamptz NOT NULL,
    completed_at timestamptz,
    fetched_rows bigint NOT NULL DEFAULT 0,
    upserted_rows bigint NOT NULL DEFAULT 0,
    aggregate_refreshed_at timestamptz,
    error_message varchar(500)
);
