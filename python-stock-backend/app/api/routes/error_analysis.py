"""시스템 오류 수집(브라우저)과 로그인 회원용 진단 조회."""

from __future__ import annotations

from fastapi import APIRouter, Body, Query, Request
from fastapi.responses import JSONResponse

from app.core.database import DbSession
from app.core.deps import OptionalMemberId
from app.core.errors import ApiError, unauthorized
from app.core.parsing import clamp
from app.models import SystemErrorLog
from app.services import error_analysis

from ..schemas import ClientErrorBody

router = APIRouter(prefix="/api/error-analysis", tags=["diagnostics"])


@router.post("/client")
def collect_client_error(request: Request, member_id: OptionalMemberId, payload: ClientErrorBody = Body(default_factory=ClientErrorBody)):
    message = str(payload.message or "").strip()
    if not message:
        return JSONResponse({"recorded": False}, status_code=400)
    error_analysis.record_error(
        source="CLIENT", message=message, severity="ERROR", error_type=str(payload.type or "JavaScriptError"),
        stack_trace=payload.stack, path=payload.url or request.headers.get("referer"),
        request_meta={"line": payload.line, "column": payload.column, "userAgent": request.headers.get("user-agent", "")},
        member_id=member_id,
    )
    return JSONResponse({"recorded": True}, status_code=202)


def _require_member(db, member_id: int | None) -> None:
    if not error_analysis.is_member(db, member_id):
        raise unauthorized()


@router.get("/logs")
def list_logs(member_id: OptionalMemberId, db: DbSession, limit: int = Query(300), source: str = Query(""), status: str = Query("")) -> dict:
    _require_member(db, member_id)
    return {"logs": error_analysis.list_logs(db, clamp(limit, 1, 1000), source.upper(), status)}


@router.get("/logs/{log_id}")
def get_log(log_id: int, member_id: OptionalMemberId, db: DbSession) -> dict:
    _require_member(db, member_id)
    row = db.get(SystemErrorLog, log_id)
    if not row:
        raise ApiError(404, error="오류 로그를 찾을 수 없습니다.")
    return {"log": error_analysis.serialize_log(row, detailed=True)}
