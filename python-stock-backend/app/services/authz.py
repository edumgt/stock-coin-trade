"""서버 소유 증권 계좌·관리자 권한 판별."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.database import session_scope
from app.models import Member


def admin_email() -> str:
    return get_settings().admin_email.strip().lower()


def member_email(member_id: int | None) -> str | None:
    if not member_id:
        return None
    with session_scope() as db:
        member = db.get(Member, member_id)
        return member.email.strip().lower() if member and member.email else None


def is_admin_member(member_id: int | None) -> bool:
    return member_email(member_id) == admin_email()


def can_use_kis_account(member_id: int | None) -> bool:
    """로그인한 모든 유효 회원은 공용 KIS Testbed 계좌를 사용할 수 있다."""
    return member_email(member_id) is not None
