"""계좌 소유자 전용 KIS 실전투자 읽기 전용 API(로그인 필요)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.deps import MemberId, csrf_required, login_required
from app.services.authz import member_email
from app.services.brokers.kis_real import KisRealError, configuration_state, get_real_balance

router = APIRouter(
    prefix="/api/kis-real", tags=["kis"],
    dependencies=[Depends(login_required(ok=False, error="UNAUTHORIZED", message="로그인이 필요합니다."))],
)
require_csrf = csrf_required(ok=False, error="CSRF_INVALID", message="요청 검증에 실패했습니다. 화면을 새로고침해주세요.")


@router.get("/status")
def status(member_id: MemberId) -> dict:
    state = configuration_state(lambda: member_email(member_id))
    if not state["ready"]:
        message = "실전 계좌 연동 설정이 필요합니다."
    elif not state["authorized"]:
        message = "설정된 계좌 소유자만 실전 잔고를 조회할 수 있습니다."
    else:
        message = "실전 잔고조회 준비가 완료되었습니다."
    return {
        "ok": True, "ready": state["ready"], "authorized": state["authorized"],
        "configured": state["configured"], "accountFormatValid": state["accountFormatValid"],
        "environment": "KIS 실전투자", "readOnly": True, "message": message,
    }


@router.post("/balance", dependencies=[Depends(require_csrf)])
def balance(member_id: MemberId):
    try:
        return {"ok": True, "balance": get_real_balance(lambda: member_email(member_id))}
    except KisRealError as exc:
        return JSONResponse({"ok": False, "error": exc.code, "message": str(exc)}, status_code=exc.status_code)
