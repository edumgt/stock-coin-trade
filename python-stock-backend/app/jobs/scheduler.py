"""APScheduler 배치: 코인마켓캡 랭킹, 업비트 마켓 목록, 봇 거래, OHLCV 증분 수집."""

from __future__ import annotations

import logging

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.database import session_scope
from app.jobs.market_bots import run_bot_trading_round
from app.jobs.ohlcv_aggregate import bootstrap_ohlcv_aggregates
from app.jobs.ohlcv_sync import run_incremental_sync, sync_enabled
from app.models import CryptoRank, UpbitMarket

log = logging.getLogger(__name__)


def sync_coinmarketcap_rankings() -> None:
    """코인마켓캡 API - 시가총액 top 100 동기화 (1시간 마다 실행)"""
    log.info("sync_coinmarketcap_rankings() -> 코인마켓캡 시가총액 Top100 스케쥴러 실행")
    api_key = get_settings().cmc_api_key
    if not api_key:
        log.warning("CMC_API_KEY가 설정되지 않아 동기화를 건너뜁니다.")
        return

    resp = requests.get(
        "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest",
        headers={"X-CMC_PRO_API_KEY": api_key},
        timeout=15,
    )
    resp.raise_for_status()
    items = resp.json().get("data", [])

    with session_scope() as db:
        db.execute(text("TRUNCATE TABLE crypto_rank"))
        for item in items:
            quote = (item.get("quote") or {}).get("USD") or {}
            db.add(CryptoRank(
                name=item.get("name"),
                symbol=item.get("symbol"),
                api_crypto_id=item.get("id"),
                price=quote.get("price"),
                market_cap=quote.get("market_cap"),
                percent_change24h=quote.get("percent_change_24h"),
                percent_change7d=quote.get("percent_change_7d"),
            ))


def sync_upbit_markets() -> None:
    """업비트 API - 거래가능 market 목록 DB 동기화 (오후 6시 1일 1회)"""
    log.info("sync_upbit_markets() -> 업비트 거래가능 목록 DB 저장 스케쥴러 실행")
    resp = requests.get("https://api.upbit.com/v1/market/all", timeout=10)
    resp.raise_for_status()
    items = resp.json()

    with session_scope() as db:
        existing = set(db.scalars(select(UpbitMarket.market_code)).all())
        for item in items:
            code = item.get("market")
            if not code or "KRW" not in code or code in existing:
                continue
            db.add(UpbitMarket(market_code=code, korean_name=item.get("korean_name"), english_name=item.get("english_name")))


def _ohlcv_schedule_hours() -> str:
    """설정된 간격에 맞는 결정적인 Asia/Seoul cron 시(hour) 목록을 돌려준다."""
    settings = get_settings()
    base_hour = settings.ohlcv_sync_hour
    interval_hours = settings.ohlcv_sync_interval_hours
    if not 0 <= base_hour <= 23:
        raise ValueError("OHLCV_SYNC_HOUR must be between 0 and 23")
    if interval_hours < 1 or 24 % interval_hours:
        raise ValueError("OHLCV_SYNC_INTERVAL_HOURS must be a positive divisor of 24")
    hours = sorted({(base_hour + offset) % 24 for offset in range(0, 24, interval_hours)})
    return ",".join(str(hour) for hour in hours)


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    scheduler.add_job(sync_coinmarketcap_rankings, CronTrigger(minute=0, timezone="Asia/Seoul"))
    scheduler.add_job(sync_upbit_markets, CronTrigger(hour=18, minute=0, timezone="Asia/Seoul"))
    scheduler.add_job(run_bot_trading_round, IntervalTrigger(minutes=10))
    try:
        result = bootstrap_ohlcv_aggregates()
        log.info("OHLCV aggregate bootstrap: %s", result)
    except Exception:
        log.exception("OHLCV aggregate bootstrap failed; scheduled batch will retry aggregation")
    if sync_enabled():
        scheduler.add_job(
            run_incremental_sync,
            CronTrigger(hour=_ohlcv_schedule_hours(), minute=get_settings().ohlcv_sync_minute, timezone="Asia/Seoul"),
            id="ohlcv-incremental-batch",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
        )
    scheduler.start()
    return scheduler
