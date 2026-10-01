"""애플리케이션 설정.

인프라 설정(DB·Redis·세션·CORS·배치 주기 등)은 pydantic-settings ``Settings``로 한 번만 읽는다.
증권사·거래소 자격증명(KIS/KB/Alpaca/KIS 실전)은 의도적으로 ``Settings``에 담지 않고
``app.services.brokers``·``app.services.alpaca``가 호출 시점마다 환경변수에서 읽는다.
값이 프로세스 전역 객체에 캐시되지 않고, 키 교체가 재기동만으로 반영되게 하기 위해서다.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
ENV_FILE = REPO_ROOT / ".env"
RESOURCES_DIR = BACKEND_DIR / "app" / "resources"

# Docker 없이 `uvicorn app.main:app`으로 직접 실행할 때 저장소 루트의 .env를 읽는다.
# 이미 설정된 환경변수(Compose environment 등)가 우선하며, 파일이 없으면 무시된다.
# 증권사 모듈이 os.environ을 직접 읽으므로 Settings 객체뿐 아니라 프로세스 환경에도 올린다.
load_dotenv(ENV_FILE, override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore", case_sensitive=False)

    # ── 앱 ──────────────────────────────────────────────────────────────
    app_name: str = "stock-coin-trade API"
    secret_key: str = "dev-secret-change-me"
    debug: bool = False
    # 기동 시 테이블 보정·시드·스케줄러 실행 여부. 테스트와 일회성 CLI에서는 끈다.
    app_startup_tasks: bool = True
    scheduler_enabled: bool = True
    demo_seed_enabled: bool = True
    # 4xx/5xx 응답과 외부 API 테스트 호출을 DB에 기록(system_error_log, api_usage_log). 테스트에서는 끈다.
    audit_enabled: bool = True
    admin_email: str = "admin@admin.com"

    # ── 회원·모의투자 DB (MariaDB) ──────────────────────────────────────
    # Compose는 DB_*로 넘기고, Docker 없이 직접 실행할 때는 .env의 MARIADB_* 값을 그대로 쓸 수 있다.
    db_host: str = "mariadb"
    db_port: int = 3306
    db_name: str = Field(default="mockinv", validation_alias=AliasChoices("DB_NAME", "MARIADB_DATABASE"))
    db_user: str = Field(default="mockinv", validation_alias=AliasChoices("DB_USER", "MARIADB_USER"))
    db_password: str = Field(default="12345678!!", validation_alias=AliasChoices("DB_PASSWORD", "MARIADB_PASSWORD"))
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_connect_timeout: int = 5

    # ── 세션 (Redis) ────────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"
    redis_session_key_prefix: str = "stock-coin-trade:session:"
    # redis | memory. memory는 Redis 없이 로컬 개발·테스트할 때만 쓴다(프로세스 재시작 시 세션 소멸).
    session_store: str = "redis"
    session_cookie_name: str = "session"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    session_lifetime_days: int = 7

    # ── CORS ────────────────────────────────────────────────────────────
    cors_api_origin_regex: str = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

    # ── 보조 데이터 저장소 ──────────────────────────────────────────────
    quant_database_url: str = "postgresql+psycopg://quant:quant@postgres:5432/quant_research"
    ohlcv_database_url: str = "postgresql+psycopg://admin:admin1234@pg-stock:5432/admin"
    qdrant_url: str = ":memory:"

    # ── OHLCV 배치 ──────────────────────────────────────────────────────
    ohlcv_sync_enabled: bool = True
    ohlcv_sync_tickers: str = "major"
    ohlcv_sync_provider: str = "naver"
    ohlcv_sync_start_year: int = 2020
    ohlcv_sync_correction_days: int = 7
    ohlcv_sync_hour: int = 18
    ohlcv_sync_interval_hours: int = 12
    ohlcv_sync_minute: int = 20
    ohlcv_sync_max_tickers: int = 0

    # ── 외부 서비스 ─────────────────────────────────────────────────────
    cmc_api_key: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"
    aria_demo_key: str = ""
    aws_secrets_manager_prefix: str = "stock-coin-trade"
    aws_region: str | None = Field(default=None, validation_alias=AliasChoices("AWS_REGION", "AWS_DEFAULT_REGION"))

    @property
    def database_url(self) -> URL:
        return URL.create(
            "mysql+pymysql",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            query={"charset": "utf8mb4"},
        )

    @property
    def session_lifetime_seconds(self) -> int:
        return self.session_lifetime_days * 86_400


@lru_cache
def get_settings() -> Settings:
    return Settings()
