"""외부 API 사용이력 조회(로그인 필요)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.core.database import DbSession
from app.core.deps import MemberId, login_required
from app.core.errors import ApiError
from app.core.parsing import clamp
from app.models import ApiUsageLog
from app.services import api_usage

router = APIRouter(prefix="/api/api-usage", tags=["diagnostics"])
_LOGIN = "API 사용이력은 로그인 후 조회할 수 있습니다."


def _gateway_history(db, member_id: int, limit: int, providers: tuple[str, ...], layer: str) -> dict:
    history = api_usage.member_history(db, member_id, clamp(limit, 1, 2000), providers)
    return {"history": history, "summary": api_usage.gateway_summary(history, layer)}


@router.get("/history", dependencies=[Depends(login_required(error=_LOGIN))])
def list_history(member_id: MemberId, db: DbSession, limit: int = Query(500)) -> dict:
    return {"history": api_usage.member_history(db, member_id, clamp(limit, 1, 1000))}


@router.get("/kis-history", dependencies=[Depends(login_required(error="KIS API 이력은 로그인 후 조회할 수 있습니다."))])
def list_kis_history(member_id: MemberId, db: DbSession, limit: int = Query(1000)) -> dict:
    return _gateway_history(db, member_id, limit, ("KIS", "KIS Gateway"), "KIS 외부 호출")


@router.get("/kb-history", dependencies=[Depends(login_required(error="KB API 이력은 로그인 후 조회할 수 있습니다."))])
def list_kb_history(member_id: MemberId, db: DbSession, limit: int = Query(1000)) -> dict:
    return _gateway_history(db, member_id, limit, ("KB증권", "KB Gateway"), "KB 외부 호출")


@router.get("/alpaca-history", dependencies=[Depends(login_required(error="Alpaca API 이력은 로그인 후 조회할 수 있습니다."))])
def list_alpaca_history(member_id: MemberId, db: DbSession, limit: int = Query(1000)) -> dict:
    return _gateway_history(db, member_id, limit, ("Alpaca", "Alpaca Gateway"), "Alpaca 외부 호출")


@router.get("/history/{log_id}", dependencies=[Depends(login_required(error=_LOGIN))])
def get_history(log_id: int, member_id: MemberId, db: DbSession) -> dict:
    row = db.scalars(select(ApiUsageLog).where(ApiUsageLog.api_usage_log_id == log_id, ApiUsageLog.member_id == member_id)).first()
    if not row:
        raise ApiError(404, error="API 사용이력을 찾을 수 없습니다.")
    return {"log": api_usage.serialize_log(row, detail=True)}
