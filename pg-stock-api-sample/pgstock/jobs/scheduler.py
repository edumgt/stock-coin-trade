"""APScheduler 배치: pg-stock OHLCV 증분 수집.

원본 ``app.jobs.scheduler`` 에서 코인마켓캡·업비트·봇 거래 작업을 제외하고 OHLCV 부분만 남겼다.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from pgstock.config import get_settings
from pgstock.jobs.ohlcv_aggregate import bootstrap_ohlcv_aggregates
from pgstock.jobs.ohlcv_sync import run_incremental_sync, sync_enabled

log = logging.getLogger(__name__)


def _ohlcv_schedule_hours() -> str:
    """설정된 간격에 맞는 결정적인 Asia/Seoul cron 시(hour) 목록을 돌려준다."""
    settings = get_settings()
    if settings.ohlcv_sync_hours.strip():
        hours = sorted({int(value.strip()) for value in settings.ohlcv_sync_hours.split(",")})
        if any(hour < 0 or hour > 23 for hour in hours):
            raise ValueError("OHLCV_SYNC_HOURS must contain hours between 0 and 23")
        return ",".join(str(hour) for hour in hours)
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
