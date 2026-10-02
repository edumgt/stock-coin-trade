"""회원별 Open API 키 발급·폐기(로그인 필요)."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Body, Depends
from sqlalchemy import select

from app.core.database import DbSession
from app.core.deps import MemberId, require_member_id
from app.core.errors import ApiError
from app.models import ApiKey
from app.services.openapi_auth import hash_key

from ..schemas import ApiKeyCreateBody

router = APIRouter(prefix="/api/member/api-keys", tags=["api-keys"], dependencies=[Depends(require_member_id)])

KEY_PREFIX = "eduapi_live_"


def _serialize(key: ApiKey) -> dict:
    return {
        "id": key.api_key_id,
        "label": key.label,
        "keyPrefix": key.key_prefix,
        "isActive": key.is_active,
        "scopes": getattr(key, "scopes", "") or "",   # 운영자가 DB에서 부여. 셀프 서비스 변경 불가
        "createdAt": key.created_at.isoformat() if key.created_at else None,
        "lastUsedAt": key.last_used_at.isoformat() if key.last_used_at else None,
    }


@router.get("")
def list_keys(member_id: MemberId, db: DbSession) -> dict:
    rows = db.scalars(select(ApiKey).where(ApiKey.member_id == member_id).order_by(ApiKey.created_at.desc())).all()
    return {"keys": [_serialize(k) for k in rows]}


@router.post("")
def create_key(member_id: MemberId, db: DbSession, payload: ApiKeyCreateBody = Body(default_factory=ApiKeyCreateBody)) -> dict:
    label = str(payload.label or "").strip()[:100] or "My API Key"
    raw_key = KEY_PREFIX + secrets.token_urlsafe(32)
    key = ApiKey(member_id=member_id, label=label, key_prefix=raw_key[:16], key_hash=hash_key(raw_key))
    db.add(key)
    db.flush()
    return {**_serialize(key), "apiKey": raw_key}


@router.delete("/{key_id}")
def revoke_key(key_id: int, member_id: MemberId, db: DbSession) -> dict:
    key = db.get(ApiKey, key_id)
    if not key or key.member_id != member_id:
        raise ApiError(404, error="NOT_FOUND", message="존재하지 않는 키입니다.")
    key.is_active = False
    return {"status": "ok"}
