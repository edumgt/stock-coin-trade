"""pg-stock 샘플 설정.

원본 ``app.core.config.Settings`` 에서 pg-stock 크롤링·API에 필요한 항목만 남겼다.
환경변수 또는 샘플 루트의 ``.env`` 로 읽는다(이미 설정된 환경변수가 우선).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

SAMPLE_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = SAMPLE_ROOT / ".env"

load_dotenv(ENV_FILE, override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore", case_sensitive=False)

    app_name: str = "pg-stock OHLCV API sample"
    debug: bool = False
    scheduler_enabled: bool = True

    # ── pg-stock(PostgreSQL) ────────────────────────────────────────────
    ohlcv_database_url: str = "postgresql+psycopg://admin:admin1234@localhost:55432/admin"

    # ── OHLCV 배치 ──────────────────────────────────────────────────────
    ohlcv_sync_enabled: bool = True
    ohlcv_sync_tickers: str = "major"          # major | all | 005930,000660
    ohlcv_sync_provider: str = "naver"         # naver | yahoo | auto
    ohlcv_sync_start_year: int = 2020
    ohlcv_sync_correction_days: int = 7
    ohlcv_sync_hours: str = "9,12,16"          # Asia/Seoul cron 시(hour) 목록
    ohlcv_sync_hour: int = 16                  # OHLCV_SYNC_HOURS 가 비었을 때만 사용
    ohlcv_sync_interval_hours: int = 24
    ohlcv_sync_minute: int = 50
    ohlcv_sync_max_tickers: int = 0

    # ── Open API 쓰기 엔드포인트(/openapi/v1/ohlcv/ingest) 인증 ─────────
    # 원본은 MariaDB api_key 테이블을 조회하지만, 샘플은 쉼표로 나열한 고정 키를 쓴다.
    ohlcv_api_keys: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
