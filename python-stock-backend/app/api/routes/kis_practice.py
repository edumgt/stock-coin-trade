"""KIS 스타일 주식 연습 원장 API(로그인 필요)."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from app.core.database import DbSession
from app.core.deps import MemberId, require_csrf, require_member_id
from app.core.errors import ApiError
from app.core.parsing import clamp, parse_int
from app.services import kis_practice
from app.services.kis_practice import PracticeOrderRejected

from ..schemas import KisPracticeOrderBody

router = APIRouter(prefix="/api/kis-practice", tags=["kis"], dependencies=[Depends(require_member_id)])


@router.get("/account")
def account(member_id: MemberId, db: DbSession) -> dict:
    return kis_practice.account_summary(db, member_id)


@router.get("/positions")
def positions(member_id: MemberId, db: DbSession) -> dict:
    return {"positions": kis_practice.serialize_positions(db, member_id), "ledger": "KIS_PRACTICE"}


@router.get("/orders/history")
def history(member_id: MemberId, db: DbSession, limit: int = Query(20)) -> dict:
    return {"history": kis_practice.order_history(db, member_id, clamp(limit, 1, 200)), "ledger": "KIS_PRACTICE"}


@router.post("/orders", dependencies=[Depends(require_csrf)])
def order(member_id: MemberId, db: DbSession, payload: KisPracticeOrderBody = Body(default_factory=KisPracticeOrderBody)):
    quantity = parse_int(payload.quantity, 0) or 0
    try:
        return kis_practice.execute_order(db, member_id, str(payload.symbol or ""), str(payload.side or ""), quantity)
    except PracticeOrderRejected as exc:
        # ApiError로 바꾸면 요청 세션이 롤백되고 기존 응답 형식({error, message, ...details})이 유지된다.
        raise ApiError(exc.status_code, error=exc.code, message=str(exc), **exc.details)
