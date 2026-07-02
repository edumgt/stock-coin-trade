import time

from models import StockOrder, StockPosition
from stock_market import STOCKS, current_price

INITIAL_CASH = 10_000_000  # matches the seed deposit granted at registration (members.py)

BUY = "BUY"
SELL = "SELL"


def _get_position(db, member_id: int, symbol: str) -> StockPosition | None:
    return (
        db.query(StockPosition)
        .filter(StockPosition.member_id == member_id, StockPosition.symbol == symbol)
        .first()
    )


def get_positions(db, member_id: int) -> list[dict]:
    rows = db.query(StockPosition).filter(StockPosition.member_id == member_id).all()
    result = []
    for pos in rows:
        price = current_price(pos.symbol)
        eval_amount = pos.quantity * price
        pnl = eval_amount - (pos.quantity * pos.avg_price)
        name = STOCKS.get(pos.symbol, {}).get("name", pos.symbol)
        result.append({
            "symbol":       pos.symbol,
            "name":         name,
            "quantity":     pos.quantity,
            "avgPrice":     pos.avg_price,
            "currentPrice": price,
            "evalAmount":   eval_amount,
            "pnl":          pnl,
        })
    return result


def get_account_snapshot(db, member) -> dict:
    positions = get_positions(db, member.member_id)
    total_pos = sum(p["evalAmount"] for p in positions)
    total_asset = member.asset + total_pos
    pnl_rate = round(((total_asset - INITIAL_CASH) / INITIAL_CASH * 100) if INITIAL_CASH else 0, 4)
    return {"cash": member.asset, "totalAsset": total_asset, "totalPnlRate": pnl_rate}


def get_order_history(db, member_id: int, limit: int = 50) -> list[dict]:
    rows = (
        db.query(StockOrder)
        .filter(StockOrder.member_id == member_id)
        .order_by(StockOrder.created_at.desc(), StockOrder.stock_order_id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "ts":       int(o.created_at.timestamp() * 1000) if o.created_at else int(time.time() * 1000),
            "type":     o.order_type,
            "symbol":   o.symbol,
            "name":     o.name,
            "quantity": o.quantity,
            "price":    o.price,
            "amount":   o.amount,
        }
        for o in rows
    ]


def execute_order(db, member, symbol: str, side: str, quantity: int, source: str = "WEB") -> dict:
    """Execute a market BUY/SELL for `member` against their shared cash balance
    (member.asset). Raises ValueError with a user-facing message on failure."""
    symbol = (symbol or "").upper()
    side = (side or "").upper()
    if side not in (BUY, SELL):
        raise ValueError("side는 BUY 또는 SELL이어야 합니다.")
    if symbol not in STOCKS:
        raise ValueError(f"지원하지 않는 종목입니다: {symbol}")
    if not isinstance(quantity, int) or quantity <= 0:
        raise ValueError("quantity는 1 이상의 정수여야 합니다.")

    price = current_price(symbol)
    amount = price * quantity
    position = _get_position(db, member.member_id, symbol)

    if side == BUY:
        if amount > member.asset:
            raise ValueError("보유 현금이 부족합니다.")
        member.asset -= amount
        if position is None:
            position = StockPosition(
                member_id=member.member_id,
                symbol=symbol,
                quantity=quantity,
                avg_price=price,
            )
            db.add(position)
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
        member_id=member.member_id,
        symbol=symbol,
        name=STOCKS[symbol]["name"],
        order_type=side,
        quantity=quantity,
        price=price,
        amount=amount,
        source=source,
    ))

    return {"status": "ok", "symbol": symbol, "side": side, "quantity": quantity, "price": price, "amount": amount}
