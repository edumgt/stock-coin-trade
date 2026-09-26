"""Fetch major Korean stocks from 2020 onward and upsert them into pg-stock.

Run inside the backend container:
    docker compose exec python-backend python crawl_major_ohlcv.py

The operation is idempotent because ``ohlcv`` uses (ticker_code, trade_date)
as its primary key. Re-running it also applies provider corrections.
"""
import argparse
import ast
import os
from datetime import date, timedelta

import pandas as pd
import requests
import yfinance as yf
from sqlalchemy import create_engine, text


DATABASE_URL = os.getenv(
    "OHLCV_DATABASE_URL",
    "postgresql+psycopg://admin:admin1234@pg-stock:5432/admin",
)

# Liquid KOSPI/KOSDAQ leaders across semiconductors, autos, platforms,
# batteries, bio, finance and telecom. Add a row here to expand the universe.
MAJOR_TICKERS = {
    "005930": ("삼성전자", "KOSPI"),
    "000660": ("SK하이닉스", "KOSPI"),
    "005380": ("현대차", "KOSPI"),
    "000270": ("기아", "KOSPI"),
    "012330": ("현대모비스", "KOSPI"),
    "035420": ("NAVER", "KOSPI"),
    "035720": ("카카오", "KOSPI"),
    "051910": ("LG화학", "KOSPI"),
    "373220": ("LG에너지솔루션", "KOSPI"),
    "006400": ("삼성SDI", "KOSPI"),
    "207940": ("삼성바이오로직스", "KOSPI"),
    "068270": ("셀트리온", "KOSPI"),
    "105560": ("KB금융", "KOSPI"),
    "055550": ("신한지주", "KOSPI"),
    "086790": ("하나금융지주", "KOSPI"),
    "316140": ("우리금융지주", "KOSPI"),
    "066570": ("LG전자", "KOSPI"),
    "017670": ("SK텔레콤", "KOSPI"),
    "028260": ("삼성물산", "KOSPI"),
    "247540": ("에코프로비엠", "KOSDAQ"),
    "086520": ("에코프로", "KOSDAQ"),
    "196170": ("알테오젠", "KOSDAQ"),
    "091990": ("셀트리온헬스케어", "KOSDAQ"),
    "263750": ("펄어비스", "KOSDAQ"),
}


def yahoo_symbol(code, market):
    return f"{code}.KS" if market == "KOSPI" else f"{code}.KQ"


def normalize_download(frame):
    if frame.empty:
        return []
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    frame = frame.rename(columns={"Adj Close": "adj_close"})
    if "adj_close" not in frame.columns:
        frame["adj_close"] = frame["Close"]
    frame = frame.reset_index().rename(columns={
        "Date": "trade_date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    })
    required = ["trade_date", "open", "high", "low", "close", "adj_close", "volume"]
    frame = frame[required].dropna()
    frame = frame[
        (frame[["open", "high", "low", "close", "adj_close"]] > 0).all(axis=1)
        & (frame["volume"] >= 0)
        & (frame["high"] >= frame[["open", "low", "close"]].max(axis=1))
        & (frame["low"] <= frame[["open", "high", "close"]].min(axis=1))
    ]
    return [
        {
            "trade_date": row.trade_date.date(),
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "adj_close": float(row.adj_close),
            "volume": int(row.volume),
        }
        for row in frame.itertuples(index=False)
    ]


def fetch_naver(code, start, end):
    """Fetch Korean daily candles without an API key (end is exclusive)."""
    response = requests.get(
        "https://api.finance.naver.com/siseJson.naver",
        params={
            "symbol": code,
            "requestType": 1,
            "startTime": start.strftime("%Y%m%d"),
            "endTime": (end - timedelta(days=1)).strftime("%Y%m%d"),
            "timeframe": "day",
        },
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com/"},
        timeout=30,
    )
    response.raise_for_status()
    raw_rows = ast.literal_eval(response.text.strip())
    rows = []
    for raw in raw_rows[1:]:
        if len(raw) < 6 or not raw[0]:
            continue
        trade_date = date.fromisoformat(f"{raw[0][:4]}-{raw[0][4:6]}-{raw[0][6:8]}")
        open_price, high, low, close, volume = raw[1:6]
        if not all(value is not None for value in (open_price, high, low, close, volume)):
            continue
        if min(open_price, high, low, close) <= 0 or volume < 0:
            continue
        if high < max(open_price, low, close) or low > min(open_price, high, close):
            continue
        rows.append({
            "trade_date": trade_date,
            "open": float(open_price),
            "high": float(high),
            "low": float(low),
            "close": float(close),
            # Naver does not expose adjusted close in this endpoint.
            "adj_close": float(close),
            "volume": int(volume),
        })
    return rows


def fetch_yahoo(code, market, start, end):
    frame = yf.download(
        yahoo_symbol(code, market),
        start=start.isoformat(),
        end=end.isoformat(),
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    return normalize_download(frame)


def upsert_ticker(engine, code, name, market, rows):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO tickers (ticker_code, name, market)
            VALUES (:code, :name, :market)
            ON CONFLICT (ticker_code) DO UPDATE
            SET name = EXCLUDED.name, market = EXCLUDED.market
        """), {"code": code, "name": name, "market": market})
        if rows:
            result = conn.execute(text("""
                INSERT INTO ohlcv
                    (ticker_code, trade_date, open, high, low, close, adj_close, volume)
                VALUES
                    (:ticker_code, :trade_date, :open, :high, :low, :close, :adj_close, :volume)
                ON CONFLICT (ticker_code, trade_date) DO UPDATE
                SET open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    adj_close = EXCLUDED.adj_close,
                    volume = EXCLUDED.volume
                WHERE (ohlcv.open, ohlcv.high, ohlcv.low, ohlcv.close, ohlcv.adj_close, ohlcv.volume)
                      IS DISTINCT FROM
                      (EXCLUDED.open, EXCLUDED.high, EXCLUDED.low, EXCLUDED.close,
                       EXCLUDED.adj_close, EXCLUDED.volume)
            """), [{"ticker_code": code, **row} for row in rows])
            return result.rowcount
    return 0


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2020-01-01", help="inclusive date (YYYY-MM-DD)")
    parser.add_argument(
        "--end",
        default=(date.today() + timedelta(days=1)).isoformat(),
        help="exclusive date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--ticker",
        action="append",
        dest="tickers",
        help="six-character code; may be repeated (default: all curated major tickers)",
    )
    parser.add_argument(
        "--provider",
        choices=("naver", "yahoo", "auto"),
        default="naver",
        help="market data provider (auto falls back from Yahoo to Naver)",
    )
    parser.add_argument("--dry-run", action="store_true", help="download and validate without DB writes")
    return parser.parse_args()


def main():
    args = parse_args()
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if start >= end:
        raise SystemExit("--start must be before --end")

    selected = args.tickers or list(MAJOR_TICKERS)
    unknown = [code for code in selected if code not in MAJOR_TICKERS]
    if unknown:
        raise SystemExit(f"unknown ticker(s): {', '.join(unknown)}")

    engine = None if args.dry_run else create_engine(DATABASE_URL, pool_pre_ping=True)
    total_rows = 0
    failed = []
    for code in selected:
        name, market = MAJOR_TICKERS[code]
        try:
            if args.provider == "naver":
                rows = fetch_naver(code, start, end)
            elif args.provider == "yahoo":
                rows = fetch_yahoo(code, market, start, end)
            else:
                try:
                    rows = fetch_yahoo(code, market, start, end)
                except Exception:
                    rows = []
                if not rows:
                    rows = fetch_naver(code, start, end)
            if not rows:
                raise RuntimeError("no valid rows returned")
            if engine is not None:
                upsert_ticker(engine, code, name, market, rows)
            total_rows += len(rows)
            print(f"{code} {name}: {len(rows):,} rows ({rows[0]['trade_date']} ~ {rows[-1]['trade_date']})")
        except Exception as exc:
            failed.append(code)
            print(f"ERROR {code} {name}: {exc}")

    print(f"completed: {len(selected) - len(failed)}/{len(selected)} tickers, {total_rows:,} rows")
    if failed:
        raise SystemExit(f"failed tickers: {', '.join(failed)}")


if __name__ == "__main__":
    main()
