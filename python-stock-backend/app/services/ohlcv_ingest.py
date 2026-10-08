"""종목 하나를 외부 공급자에서 받아 pg-stock OHLCV 저장소에 즉시 채운다.

종목 검색이 OHLCV 저장소에서 빗나갔을 때 호출된다(lumina-invest `/api/stocks/search`
→ `POST /openapi/v1/ohlcv/ingest`). 적재가 끝나면 다음 검색부터는 저장소에서 바로 나온다.

일괄 적재는 `app.jobs.ohlcv_crawler`(CLI)가 담당한다. 받아오기·검증·upsert 로직은
그 모듈에 이미 있으므로 여기서 그대로 재사용한다 — 적재 규칙을 두 곳에 두지 않는다.
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta

from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.jobs.ohlcv_crawler import fetch_naver, fetch_yahoo, upsert_ticker

logger = logging.getLogger(__name__)

TICKER_CODE = re.compile(r"^[0-9A-Z]{6}$")
MARKETS = {"KOSPI", "KOSDAQ", "KOSDAQ GLOBAL"}
DEFAULT_START = date(2020, 1, 1)

# 네이버 일봉에 쓰는 시장 구분은 없다(코드만 받는다). 야후는 접미사가 필요하다.
_YAHOO_SUFFIX = {"KOSPI": "KS", "KOSDAQ": "KQ", "KOSDAQ GLOBAL": "KQ"}

_engine = None


def engine():
    """적재 전용 쓰기 엔진 — 읽기 엔진(ohlcv_store)과 풀을 섞지 않는다."""
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().ohlcv_database_url, pool_pre_ping=True, pool_size=1, max_overflow=1)
    return _engine


def parse_symbol(symbol: str) -> tuple[str, str] | None:
    """`035720.KS` 또는 `035720` 을 (종목코드, 시장)으로 바꾼다. 국내 상장이 아니면 None.

    이 저장소는 국내 일봉 전용이다(`tickers.market` 이 KOSPI/KOSDAQ). 해외 티커는
    담지 않으므로 호출자가 야후 결과를 그대로 쓰게 None 을 돌려준다.
    """
    raw = (symbol or "").strip().upper()
    if not raw:
        return None
    code, _, suffix = raw.partition(".")
    if not TICKER_CODE.fullmatch(code):
        return None
    if suffix in ("KS", ""):
        return code, "KOSPI"
    if suffix == "KQ":
        return code, "KOSDAQ"
    return None


def existing_market(code: str) -> str | None:
    """이미 등록된 종목이면 그 시장 구분을 쓴다(접미사 추측보다 정확하다)."""
    with engine().connect() as conn:
        return conn.execute(text("SELECT market FROM tickers WHERE ticker_code = :code"), {"code": code}).scalar()


def fetch_rows(code: str, market: str, start: date, end: date) -> list[dict]:
    """야후 → 네이버 순으로 시도한다(크롤러 `--provider auto` 와 같은 순서)."""
    try:
        rows = fetch_yahoo(code, market, start, end)
    except Exception as exc:
        logger.info("OHLCV 야후 조회 실패 %s: %s", code, exc)
        rows = []
    if not rows:
        rows = fetch_naver(code, start, end)
    return rows


def ingest(*, symbol: str, name: str = "", start: date | None = None, end: date | None = None) -> dict:
    """종목 하나의 일봉을 받아 upsert 한다.

    Returns: {"status", "tickerCode", "name", "market", "rows", "firstDate", "lastDate"}
      status 는 ingested(새로 채움) · skipped(국내 상장 아님) · empty(공급자에 데이터 없음).
    국내 상장이 아니면 예외 없이 skipped 로 돌려준다 — 검색을 깨뜨리지 않기 위해서다.
    """
    parsed = parse_symbol(symbol)
    if not parsed:
        return {"status": "skipped", "reason": "국내 상장 종목코드가 아닙니다.", "symbol": symbol}
    code, guessed_market = parsed
    market = existing_market(code) or guessed_market
    if market not in MARKETS:
        market = guessed_market

    start = start or DEFAULT_START
    end = end or (date.today() + timedelta(days=1))
    if start >= end:
        raise ValueError("start 는 end 보다 앞이어야 합니다.")

    rows = fetch_rows(code, market, start, end)
    if not rows:
        return {"status": "empty", "tickerCode": code, "name": name, "market": market, "rows": 0}

    # 이름이 비면 코드로 둔다 — tickers.name 이 NULL 이면 이후 이름 검색에서 빠진다.
    upsert_ticker(engine(), code, name.strip() or code, market, rows)
    logger.info("OHLCV 적재 %s(%s) %s행 %s~%s", code, market, len(rows), rows[0]["trade_date"], rows[-1]["trade_date"])
    return {
        "status": "ingested",
        "tickerCode": code,
        "name": name.strip() or code,
        "market": market,
        "rows": len(rows),
        "firstDate": rows[0]["trade_date"].isoformat(),
        "lastDate": rows[-1]["trade_date"].isoformat(),
    }
