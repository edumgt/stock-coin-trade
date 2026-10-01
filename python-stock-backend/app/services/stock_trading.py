"""국내주식 모의 주문·포지션·계좌 스냅샷."""

from __future__ import annotations

import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Member, StockOrder, StockPosition
from app.services.stock_market import STOCKS, current_price, get_chart_cached, get_stock_info
from app.services.volatility import annualized_volatility

INITIAL_CASH = 100_000_000  # 회원가입 시 지급하는 초기 예수금(members.INITIAL_ASSET과 동일)

BUY = "BUY"
SELL = "SELL"

__all__ = ["BUY", "SELL", "INITIAL_CASH", "STOCKS", "current_price", "get_stock_info", "execute_order",
           "get_positions", "get_account_snapshot", "get_order_history", "get_position"]


def get_position(db: Session, member_id: int, symbol: str) -> StockPosition | None:
    return db.scalars(
        select(StockPosition).where(StockPosition.member_id == member_id, StockPosition.symbol == symbol)
    ).first()


def _stock_volatility(symbol: str) -> float | None:
    """최근 1개월 일봉 종가로 계산한 연환산(252거래일) 변동성(%)."""
    try:
        ohlcv, _ = get_chart_cached(symbol, "1m")
        return annualized_volatility([candle["c"] for candle in ohlcv], trading_periods=252)
    except Exception:
        return None


def get_positions(db: Session, member_id: int, include_volatility: bool = False) -> list[dict]:
    rows = db.scalars(select(StockPosition).where(StockPosition.member_id == member_id)).all()
    result = []
    for pos in rows:
        price = current_price(pos.symbol)
        eval_amount = pos.quantity * price
        pnl = eval_amount - (pos.quantity * pos.avg_price)
        info = get_stock_info(pos.symbol) or {}
        item = {
            "symbol": pos.symbol,
            "name": info.get("name", pos.symbol),
            "sector": info.get("sector", "기타"),
            "quantity": pos.quantity,
            "avgPrice": pos.avg_price,
            "currentPrice": price,
            "evalAmount": eval_amount,
            "pnl": pnl,
        }
        if include_volatility:
            item["volatility"] = _stock_volatility(pos.symbol)
        result.append(item)
    return result


def get_account_snapshot(db: Session, member: Member) -> dict:
    from app.services.alternatives import position_value

    positions = get_positions(db, member.member_id)
    total_pos = sum(p["evalAmount"] for p in positions) + position_value(db, member.member_id)
    total_asset = member.asset + total_pos
    pnl_rate = round(((total_asset - INITIAL_CASH) / INITIAL_CASH * 100) if INITIAL_CASH else 0, 4)
    return {"cash": member.asset, "totalAsset": total_asset, "totalPnlRate": pnl_rate}


def get_order_history(db: Session, member_id: int, limit: int = 50) -> list[dict]:
    rows = db.scalars(
        select(StockOrder)
        .where(StockOrder.member_id == member_id)
        .order_by(StockOrder.created_at.desc(), StockOrder.stock_order_id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "ts": int(o.created_at.timestamp() * 1000) if o.created_at else int(time.time() * 1000),
            "type": o.order_type,
            "symbol": o.symbol,
            "name": o.name,
            "quantity": o.quantity,
            "price": o.price,
            "amount": o.amount,
            "source": o.source,
        }
        for o in rows
    ]


def execute_order(db: Session, member: Member, symbol: str, side: str, quantity: int, source: str = "WEB") -> dict:
    """시장가 매수·매도를 회원의 공용 현금(member.asset)에 대해 체결한다.

    실패 시 사용자에게 보여줄 메시지를 담은 ValueError를 던진다.
    """
    # 같은 회원이 여러 탭에서 동시에 주문해도 잔액 검증과 차감이 분리되지 않게 행을 잠근다.
    db.refresh(member, with_for_update=True)
    symbol = (symbol or "").upper()
    side = (side or "").upper()
    if side not in (BUY, SELL):
        raise ValueError("side는 BUY 또는 SELL이어야 합니다.")
    info = get_stock_info(symbol)
    if not info:
        raise ValueError(f"지원하지 않는 KRX 종목입니다: {symbol}")
    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
        raise ValueError("quantity는 1 이상의 정수여야 합니다.")

    try:
        price = current_price(symbol)
    except Exception as exc:
        raise ValueError("실시간 시세를 확인할 수 없어 주문할 수 없습니다. 잠시 후 다시 시도해주세요.") from exc
    amount = price * quantity
    position = get_position(db, member.member_id, symbol)

    if side == BUY:
        if amount > member.asset:
            raise ValueError("보유 현금이 부족합니다.")
        member.asset -= amount
        if position is None:
            db.add(StockPosition(member_id=member.member_id, symbol=symbol, quantity=quantity, avg_price=price))
        else:
            total_qty = position.quantity + quantity
            total_amount = position.avg_price * position.quantity + amount
            position.quantity = total_qty
            position.avg_price = int(total_amount / total_qty)
    else:
        if position is None or position.quantity < quantity:
            raise ValueError("매도 가능한 수량이 부족합니다.")
        position.quantity -= quantity
        member.asset += amount
        if position.quantity == 0:
            db.delete(position)

    db.add(StockOrder(
        member_id=member.member_id, symbol=symbol, name=info["name"], order_type=side,
        quantity=quantity, price=price, amount=amount, source=source,
    ))
    return {"status": "ok", "symbol": symbol, "side": side, "quantity": quantity, "price": price, "amount": amount}
