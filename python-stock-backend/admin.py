from flask import Blueprint, jsonify, session

import k8s_overview
from db import session_scope
from models import Member

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")

ADMIN_EMAIL = "admin@admin.com"


def _require_admin():
    """관리자 계정이면 username을, 아니면 None을 반환한다."""
    member_id = session.get("member_id")
    if not member_id:
        return None
    with session_scope() as db:
        member = db.get(Member, member_id)
        if member and member.email == ADMIN_EMAIL:
            return member.username
    return None


def _forbidden():
    return jsonify({"error": "관리자만 접근 가능합니다."}), 403


@admin_bp.get("/me")
def admin_me():
    username = _require_admin()
    if not username:
        return _forbidden()
    return jsonify({"admin": True, "username": username})


@admin_bp.get("/k8s/overview")
def admin_k8s_overview():
    if not _require_admin():
        return _forbidden()
    try:
        return jsonify(k8s_overview.build_overview())
    except Exception as e:
        return jsonify({"error": str(e)}), 503
