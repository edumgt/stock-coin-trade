"""API 사용이력의 시각 직렬화 — 오프셋 없는 UTC 를 내보내면 브라우저가 로컬로 읽어 9시간 틀어진다.

2026-10-12: kis-api-history.html 그리드가 한국 시간보다 9시간 과거로 표시되던 원인.
`called_at` 은 MariaDB DATETIME(tz 없음) + CURRENT_TIMESTAMP 이고 컨테이너가 UTC 라 값은 UTC 인데,
`isoformat()` 이 오프셋을 빼고 내보내 `new Date()` 가 로컬 시각으로 해석했다.
"""
from datetime import datetime, timezone

from app.services.api_usage import iso_utc


def test_naive_datetime_is_marked_utc():
    """tz 정보가 없는 값은 UTC 로 못 박아 내보낸다."""
    assert iso_utc(datetime(2026, 10, 12, 3, 28, 2)) == "2026-10-12T03:28:02+00:00"


def test_aware_datetime_keeps_its_offset():
    assert iso_utc(datetime(2026, 10, 12, 3, 28, 2, tzinfo=timezone.utc)) == "2026-10-12T03:28:02+00:00"


def test_none_passes_through():
    assert iso_utc(None) is None


def test_offset_is_always_present():
    """오프셋이 빠지면 프런트에서 시간대가 다시 틀어진다 — 회귀 방지."""
    text = iso_utc(datetime(2026, 1, 1, 0, 0, 0))
    assert text.endswith("+00:00"), text
