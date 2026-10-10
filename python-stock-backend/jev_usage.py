"""TypeSafe Jev 공용 원장과 클라이언트.

명령 라우터(intent.py), 거래소 공지 레이더, 공시 레이더가 같은 월 예산을 나눠 쓴다.
- 원장(jev_usage)에는 월별 호출 수·토큰·비용만 적는다. Jev에 보낸 문장은 저장하지 않는다.
- 예산은 호출하는 쪽이 넘긴다. 웹 요청은 Flask 설정에서, 백그라운드 작업(worker.py)은 Settings에서 읽는다.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import text

from db import engine

log = logging.getLogger(__name__)

JEV_TABLE = """CREATE TABLE IF NOT EXISTS jev_usage (
  month CHAR(7) PRIMARY KEY,
  calls INT NOT NULL DEFAULT 0,
  input_tokens BIGINT NOT NULL DEFAULT 0,
  cost_usd DECIMAL(12, 6) NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""


def ensure_jev_tables() -> None:
    """월별 Jev 호출 수·토큰·비용 원장을 만든다."""
    with engine.begin() as conn:
        conn.execute(text(JEV_TABLE))


def _month() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


def over_budget(budget_usd: float) -> bool:
    """이번 달 누적 비용이 예산 이상이면 True.

    @param budget_usd 월 예산(USD). 0 이하면 항상 초과로 본다.
    @returns 예산 초과 여부. 이 머신에 판정 모델 단가(config/llm_pricing.local.toml)가 없으면 비용을 못 재므로 True다
    """
    from deskagent import pricing
    from deskjev import MODEL

    if MODEL not in pricing.load():  # 단가를 모르면 호출하지 않는다(호출 뒤 기록이 실패해 예산이 눈감는 것을 막는다)
        log.warning("jev_usage: no price for %s in config/llm_pricing.local.toml; Jev calls refused", MODEL)
        return True
    with engine.connect() as conn:
        spent = conn.execute(text("SELECT cost_usd FROM jev_usage WHERE month = :m"), {"m": _month()}).scalar()
    return float(spent or 0) >= budget_usd


def record(input_tokens: int) -> None:
    """실제로 과금된 호출 한 건을 원장에 더한다(캐시 적중은 기록하지 않는다).

    @param input_tokens 응답의 usage.input_tokens
    """
    from deskagent import pricing
    from deskjev import MODEL

    cost = pricing.cost_usd(MODEL, pricing.Usage(input_tokens=input_tokens))
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO jev_usage (month, calls, input_tokens, cost_usd) VALUES (:m, 1, :t, :c) "
                "ON DUPLICATE KEY UPDATE calls = calls + 1, input_tokens = input_tokens + :t, cost_usd = cost_usd + :c"
            ),
            {"m": _month(), "t": input_tokens, "c": cost},
        )


def client(timeout: float = 3.0, max_retries: int = 1):
    """TypeSafe 클라이언트. 키는 SDK가 TYPESAFE_API_KEY에서 읽는다. 테스트는 이 함수를 바꿔 끼운다.

    @param timeout 요청 한 번의 제한 시간(초). 사람이 기다리는 화면은 짧게, 백그라운드 작업은 길게 준다.
    @param max_retries 429·5xx 재시도 횟수
    @returns typesafe_sdk.TypeSafeClient
    """
    from typesafe_sdk import RetryPolicy, TypeSafeClient

    return TypeSafeClient(retry=RetryPolicy(max_retries=max_retries, backoff_max=0.3, timeout=timeout))
