"""요청 값 파싱 헬퍼. 기존 API의 관대한 입력 처리(문자열 숫자 허용, 범위 클램프)를 유지한다."""

from __future__ import annotations

from typing import Any


def parse_int(value: Any, default: int | None = None) -> int | None:
    """정수로 바꿀 수 없으면 default를 돌려준다. bool은 정수로 취급하지 않는다."""
    if isinstance(value, bool):
        return default
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def parse_float(value: Any, default: float | None = None) -> float | None:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))
