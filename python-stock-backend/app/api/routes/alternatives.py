"""모의 파생·귀금속·부동산 시장과 주문 API(로그인 필요)."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from app.core.database import DbSession
from app.core.deps import MemberId, require_member_id
from app.core.errors import ApiError
from app.core.parsing import parse_int
from app.models import Member
from app.services import alternatives

from ..schemas import AlternativeOrderBody

router = APIRouter(prefix="/api/alternatives", tags=["alternatives"], dependencies=[Depends(require_member_id)])


@router.get("/markets")
def markets() -> dict:
    return {"markets": [alternatives.quote(symbol) for symbol in alternatives.CATALOG],
            "notice": "교육용 기준 시세이며 실제 투자 권유 또는 실거래 가격이 아닙니다."}


@router.get("/markets/{symbol}/chart")
def chart(symbol: str, days: str = Query("120")) -> dict:
    symbol = symbol.upper()
    if symbol not in alternatives.CATALOG:
        raise ApiError(404, message="지원하지 않는 상품입니다.")
    return {"symbol": symbol, "data": alternatives.get_chart(symbol, parse_int(days, 120) or 120)}


@router.get("/positions")
def positions(member_id: MemberId, db: DbSession, volatility: str = Query("")) -> dict:
    rows = alternatives.get_positions(db, member_id, include_volatility=volatility == "1")
    return {"positions": rows, "totalEvalAmount": sum(row["evalAmount"] for row in rows)}


@router.get("/orders/history")
def history(member_id: MemberId, db: DbSession) -> dict:
    return {"history": alternatives.order_history(db, member_id, 100)}


def _order_fields(payload: AlternativeOrderBody) -> tuple[str, str, int]:
    return str(payload.symbol or "").upper(), str(payload.side or "").upper(), parse_int(payload.quantity, 0) or 0


@router.post("/orders/preview")
def order_preview(member_id: MemberId, db: DbSession, payload: AlternativeOrderBody = Body(default_factory=AlternativeOrderBody)) -> dict:
    symbol, side, quantity = _order_fields(payload)
    if symbol not in alternatives.CATALOG or side not in {"BUY", "SELL"} or quantity <= 0:
        raise ApiError(400, message="상품, BUY/SELL, 1 이상의 수량을 확인해주세요.")
    return alternatives.preview_order(db, db.get(Member, member_id), symbol, side, quantity)


@router.post("/orders")
def order(member_id: MemberId, db: DbSession, payload: AlternativeOrderBody = Body(default_factory=AlternativeOrderBody)) -> dict:
    symbol, side, quantity = _order_fields(payload)
    # 현금 확인과 차감을 하나의 잠금 단위로 묶어 동시 주문으로 인한 음수 잔액을 막는다.
    from app.services.crypto import member_for_update

    member = member_for_update(db, member_id)
    try:
        return alternatives.execute_alternative_order(db, member, symbol, side, quantity)
    except ValueError as exc:
        raise ApiError(400, message=str(exc))
