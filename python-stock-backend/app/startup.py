"""기동 시 1회 실행하는 작업: 테이블 보정, 시드 데이터, 봇 계정."""

from __future__ import annotations

import logging

from app.jobs.market_bots import ensure_bot_accounts
from app.services.alternatives import ensure_tables as ensure_alternative_tables
from app.services.api_usage import ensure_api_usage_table
from app.services.crypto import ensure_crypto_tables
from app.services.demo_seed import seed_bababa_dataset, seed_demo_investors, seed_ganada_dataset
from app.services.error_analysis import ensure_error_analysis_table
from app.services.brokers.kis_autotrade import ensure_kis_autotrade_tables
from app.services.kis_practice import ensure_kis_practice_tables
from app.services.members import ensure_member_tables

log = logging.getLogger(__name__)


def run_startup_tasks() -> None:
    """기존 운영 DB에도 재배포만으로 새 기능이 동작하도록 멱등한 보정·시드를 수행한다."""
    ensure_alternative_tables()
    ensure_member_tables()
    ensure_kis_practice_tables()
    ensure_kis_autotrade_tables()
    ensure_crypto_tables()
    seed_demo_investors()
    seed_ganada_dataset()
    seed_bababa_dataset()
    ensure_bot_accounts()
    ensure_error_analysis_table()
    ensure_api_usage_table()
    log.info("Startup tasks completed")
