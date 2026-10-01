from fastapi import APIRouter

from app.core.deps import OptionalMemberId
from app.core.errors import ApiError
from app.services.authz import is_admin_member

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/me")
def admin_me(member_id: OptionalMemberId) -> dict:
    if not member_id or not is_admin_member(member_id):
        raise ApiError(403, error="관리자만 접근 가능합니다.")
    return {"admin": True, "username": "admin"}
