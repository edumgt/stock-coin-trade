"""외부 연동용 Open API 인증(Bearer API 키)과 메모리 호출 제한."""

from __future__ import annotations

import hashlib
import threading
import time
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.database import session_scope
from app.models import ApiKey

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
    """유효한 키면 (api_key_id, member_id)를 돌려주고 last_used_at을 갱신한다."""
    key_hash = hash_key(raw_key)
    with session_scope() as db:
        api_key = db.scalars(select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))).first()
        if not api_key:
            return None
        api_key.last_used_at = datetime.now(UTC).replace(tzinfo=None)
        return api_key.api_key_id, api_key.member_id
