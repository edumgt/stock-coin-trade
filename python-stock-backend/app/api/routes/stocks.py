"""국내 주식 모의 주문(로그인 필요)."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import delete

from app.core.database import DbSession
from app.core.deps import MemberId, require_member_id
from app.core.errors import ApiError
from app.core.parsing import clamp, parse_int
from app.models import AlternativeOrder, AlternativePosition, Member, StockOrder, StockPosition
from app.services import stock_trading

from ..schemas import StockOrderBody, StockPreviewBody

router = APIRouter(prefix="/api/stocks", tags=["stocks"], dependencies=[Depends(require_member_id)])


@router.get("/account")
def account(member_id: MemberId, db: DbSession) -> dict:
    member = db.get(Member, member_id)
    return stock_trading.get_account_snapshot(db, member)


@router.get("/positions")
def positions(member_id: MemberId, db: DbSession, volatility: str = Query("")) -> dict:
    return {"positions": stock_trading.get_positions(db, member_id, include_volatility=volatility == "1")}


def _place_order(db, member_id: int, payload: StockOrderBody, side: str, source: str = "WEB") -> dict:
    symbol = str(payload.symbol or "").upper()
    quantity = parse_int(payload.quantity)
    if quantity is None:
        raise ApiError(400, message="quantity는 정수여야 합니다.")
    member = db.get(Member, member_id)
    try:
        return stock_trading.execute_order(db, member, symbol, side, quantity, source=source)
    except ValueError as exc:
        raise ApiError(400, message=str(exc))


@router.post("/orders/buy")
def buy(member_id: MemberId, db: DbSession, payload: StockOrderBody = Body(default_factory=StockOrderBody)) -> dict:
    return _place_order(db, member_id, payload, stock_trading.BUY)


@router.post("/orders/sell")
def sell(member_id: MemberId, db: DbSession, payload: StockOrderBody = Body(default_factory=StockOrderBody)) -> dict:
    return _place_order(db, member_id, payload, stock_trading.SELL)


@router.post("/orders/preview")
def order_preview(member_id: MemberId, db: DbSession, payload: StockPreviewBody = Body(default_factory=StockPreviewBody)) -> dict:
    """주문을 검증하고 체결 없이 현금·보유 수량 변화를 보여준다."""
    symbol = str(payload.symbol or "").upper().strip()
    side = str(payload.side or "").upper().strip()
    quantity = parse_int(payload.quantity, 0) or 0
    if side not in (stock_trading.BUY, stock_trading.SELL) or quantity <= 0:
        raise ApiError(400, message="side(BUY/SELL)와 1 이상의 정수 quantity를 입력하세요.")
    info = stock_trading.get_stock_info(symbol)
    if not info:
        raise ApiError(400, message="지원하지 않는 KRX 종목입니다.")
    try:
        price = stock_trading.current_price(symbol)
    except Exception:
        raise ApiError(503, message="현재 시세를 확인할 수 없습니다.")
    member = db.get(Member, member_id)
    position = stock_trading.get_position(db, member_id, symbol)
    held_quantity = position.quantity if position else 0
    amount = price * quantity
    is_buy = side == stock_trading.BUY
    executable = amount <= member.asset if is_buy else quantity <= held_quantity
    return {
        "executable": executable, "symbol": symbol, "name": info["name"], "side": side,
        "quantity": quantity, "estimatedPrice": price, "estimatedAmount": amount,
        "cashBefore": member.asset,
        "cashAfter": member.asset - amount if is_buy else member.asset + amount,
        "positionBefore": held_quantity,
        "positionAfter": held_quantity + quantity if is_buy else held_quantity - quantity,
        "reason": None if executable else ("보유 현금이 부족합니다." if is_buy else "매도 가능 수량이 부족합니다."),
        "notice": "주문 미리보기는 체결·잔고를 변경하지 않으며, 실제 주문 시점 가격은 달라질 수 있습니다.",
    }


@router.post("/orders/pine")
def pine_order(member_id: MemberId, db: DbSession, payload: StockPreviewBody = Body(default_factory=StockPreviewBody)) -> dict:
    """Pine 전략 연습 화면용 주문. 전략 해석과 시그널은 브라우저에서 만들고 체결은 서버가 결정한다."""
    side = str(payload.side or "").upper()
    if side not in (stock_trading.BUY, stock_trading.SELL):
        raise ApiError(400, message="side는 BUY 또는 SELL이어야 합니다.")
    return _place_order(db, member_id, StockOrderBody(symbol=payload.symbol, quantity=payload.quantity), side, source="PINE")


@router.get("/orders/history")
def order_history(member_id: MemberId, db: DbSession, limit: int = Query(200)) -> dict:
    return {"history": stock_trading.get_order_history(db, member_id, limit=clamp(limit, 1, 1000))}


@router.post("/account/reset")
def reset_account(member_id: MemberId, db: DbSession) -> dict:
    member = db.get(Member, member_id)
    db.execute(delete(StockPosition).where(StockPosition.member_id == member_id))
    db.execute(delete(StockOrder).where(StockOrder.member_id == member_id))
    db.execute(delete(AlternativePosition).where(AlternativePosition.member_id == member_id))
    db.execute(delete(AlternativeOrder).where(AlternativeOrder.member_id == member_id))
    member.asset = stock_trading.INITIAL_CASH
    return {"status": "ok", "cash": member.asset}
