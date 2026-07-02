import hashlib
import secrets

from flask import Blueprint, jsonify, request, session

from db import session_scope
from models import ApiKey

api_key_bp = Blueprint("api_keys", __name__, url_prefix="/api/member/api-keys")

KEY_PREFIX = "eduapi_live_"


@api_key_bp.before_request
def require_login():
    if not session.get("member_id"):
        return jsonify({"error": "UNAUTHORIZED", "message": "로그인이 필요합니다."}), 401


def _serialize(key: ApiKey) -> dict:
    return {
        "id":         key.api_key_id,
        "label":      key.label,
        "keyPrefix":  key.key_prefix,
        "isActive":   key.is_active,
        "createdAt":  key.created_at.isoformat() if key.created_at else None,
        "lastUsedAt": key.last_used_at.isoformat() if key.last_used_at else None,
    }


@api_key_bp.get("")
def list_keys():
    member_id = session["member_id"]
    with session_scope() as db:
        rows = (
            db.query(ApiKey)
            .filter(ApiKey.member_id == member_id)
            .order_by(ApiKey.created_at.desc())
            .all()
        )
        return jsonify({"keys": [_serialize(k) for k in rows]})


@api_key_bp.post("")
def create_key():
    member_id = session["member_id"]
    body = request.get_json(silent=True) or {}
    label = (body.get("label") or "").strip()[:100] or "My API Key"

    raw_key = KEY_PREFIX + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    key_prefix = raw_key[:16]

    with session_scope() as db:
        key = ApiKey(member_id=member_id, label=label, key_prefix=key_prefix, key_hash=key_hash)
        db.add(key)
        db.flush()
        return jsonify({**_serialize(key), "apiKey": raw_key})


@api_key_bp.delete("/<int:key_id>")
def revoke_key(key_id):
    member_id = session["member_id"]
    with session_scope() as db:
        key = db.get(ApiKey, key_id)
        if not key or key.member_id != member_id:
            return jsonify({"error": "NOT_FOUND", "message": "존재하지 않는 키입니다."}), 404
        key.is_active = False
        return jsonify({"status": "ok"})
