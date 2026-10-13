"""Open API 인증(Bearer API 키)과 메모리 호출 제한.

원본 ``app.services.openapi_auth`` 는 MariaDB ``api_key`` 테이블에서 SHA-256 해시를 조회한다.
샘플은 MariaDB 없이 동작하도록 ``OHLCV_API_KEYS`` 환경변수(쉼표 구분)의 고정 키와 비교한다.
호출 제한 로직은 원본 그대로다.
"""

from __future__ import annotations

import hashlib
import hmac
import threading
import time

from pgstock.config import get_settings

RATE_LIMIT_MAX = 60          # requests
RATE_LIMIT_WINDOW = 60       # seconds
PUBLIC_RATE_MAX = 120        # 키 없는 공개 엔드포인트(OHLCV)의 IP 단위 제한
_rate_buckets: dict[int, list[float]] = {}
_public_buckets: dict[str, list[float]] = {}
_rate_lock = threading.Lock()


def _allow(buckets: dict, key, maximum: int) -> bool:
    now = time.time()
    with _rate_lock:
        bucket = [t for t in buckets.get(key, []) if now - t < RATE_LIMIT_WINDOW]
        if len(bucket) >= maximum:
            buckets[key] = bucket
            return False
        bucket.append(now)
        buckets[key] = bucket
        return True


def check_rate_limit(api_key_id: int) -> bool:
    return _allow(_rate_buckets, api_key_id, RATE_LIMIT_MAX)


def check_public_rate_limit(ip: str) -> bool:
    return _allow(_public_buckets, ip, PUBLIC_RATE_MAX)


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def resolve_api_key(raw_key: str) -> tuple[int, int] | None:
    """유효한 키면 (api_key_id, member_id)를 돌려준다.

    샘플에서는 ``OHLCV_API_KEYS`` 목록의 순번을 api_key_id 로, member_id 는 0 으로 둔다.
    """
    configured = [key.strip() for key in get_settings().ohlcv_api_keys.split(",") if key.strip()]
    for index, key in enumerate(configured, start=1):
        if hmac.compare_digest(hash_key(key), hash_key(raw_key)):
            return index, 0
    return None
