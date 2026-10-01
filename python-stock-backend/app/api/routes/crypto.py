"""코인 시장 조회(공개)와 모의 거래(로그인 필요)."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from app.core.database import DbSession
from app.core.deps import MemberId, OptionalMemberId, require_member_id
from app.core.errors import ApiError
from app.core.parsing import clamp, parse_float, parse_int
from app.models import Member
from app.services import crypto

from ..schemas import CryptoBuyBody, CryptoPreviewBody, CryptoSellBody

market_router = APIRouter(prefix="/api/crypto", tags=["crypto"])
trade_router = APIRouter(prefix="/api/trade", tags=["crypto"], dependencies=[Depends(require_member_id)])


@market_router.get("/rankings")
def rankings(db: DbSession) -> list[dict]:
    return crypto.list_rankings(db)


@market_router.get("/market-list")
def market_list(db: DbSession) -> dict:
    markets = crypto.list_krw_markets(db)
    return {"markets": [crypto.serialize_market(m) for m in markets], "marketCodes": [m.market_code for m in markets]}


@market_router.get("/{code}/domestic-prices")
def domestic_prices(code: str) -> dict:
    return crypto.fetch_domestic_prices(code)


@market_router.get("/{code}")
def crypto_info(code: str, member_id: OptionalMemberId, db: DbSession) -> dict:
    market = crypto.find_market(db, code)
    if not market:
        raise ApiError(404, error=f"존재하지 않는 마켓입니다: {code}")
    buy_crypto_count = 0
    if member_id:
        held = crypto.find_holding(db, member_id, market.upbit_market_id)
        if held:
            buy_crypto_count = held.buy_crypto_count
    return {
        "marketCode": market.market_code,
        "koreanName": market.korean_name,
        "englishName": market.english_name,
        "buyCryptoCount": buy_crypto_count,
    }


# ── Trade (로그인 필요) ──────────────────────────────────────────────────────

@trade_router.get("/hold")
def hold(member_id: MemberId, db: DbSession) -> dict:
    return crypto.hold_summary(db, db.get(Member, member_id))


@trade_router.post("/order/buy")
def order_buy(member_id: MemberId, db: DbSession, payload: CryptoBuyBody = Body(default_factory=CryptoBuyBody)) -> dict:
    if not payload.marketCode or payload.buyKrw is None:
        raise ApiError(400, error="마켓코드와 매수금액을 입력해주세요.")
    buy_krw = parse_int(payload.buyKrw)
    if buy_krw is None:
        raise ApiError(400, error="숫자만 입력해주세요.")
    if buy_krw <= 0:
        raise ApiError(400, error="0보다 큰 수를 입력해주세요.")
    member = crypto.member_for_update(db, member_id)
    try:
        return crypto.execute_crypto_buy(db, member, payload.marketCode, buy_krw)
    except ValueError as exc:
        raise ApiError(400, error=str(exc))
    except Exception:
        raise ApiError(503, error="현재가를 가져오지 못했습니다.")


@trade_router.post("/order/preview")
def order_preview(member_id: MemberId, db: DbSession, payload: CryptoPreviewBody = Body(default_factory=CryptoPreviewBody)) -> dict:
    """코인 시장가 주문의 비변경 예상치를 돌려준다."""
    market_code = str(payload.marketCode or "").upper().strip()
    side = str(payload.side or "").upper().strip()
    if side not in {"BUY", "SELL"}:
        raise ApiError(400, error="side는 BUY 또는 SELL이어야 합니다.")
    member = db.get(Member, member_id)
    market = crypto.find_market(db, market_code)
    if not market:
        raise ApiError(400, error="존재하지 않는 마켓입니다.")
    try:
        price = crypto.upbit_trade_price(market_code)
    except Exception:
        raise ApiError(503, error="현재가를 가져오지 못했습니다.")
    held = crypto.find_holding(db, member_id, market.upbit_market_id)
    held_quantity = held.buy_crypto_count if held else 0.0
    if side == "BUY":
        amount = parse_int(payload.buyKrw)
        if amount is None:
            raise ApiError(400, error="buyKrw는 정수여야 합니다.")
        if amount <= 0:
            raise ApiError(400, error="buyKrw는 0보다 커야 합니다.")
        quantity = round(amount / price, 8)
        executable = amount <= member.asset
    else:
        quantity = parse_float(payload.sellCount)
        if quantity is None:
            raise ApiError(400, error="sellCount는 숫자여야 합니다.")
        if quantity <= 0:
            raise ApiError(400, error="sellCount는 0보다 커야 합니다.")
        amount = round(quantity * price)
        executable = quantity <= held_quantity
    return {"executable": executable, "marketCode": market_code, "koreanName": market.korean_name,
            "side": side, "estimatedPrice": price, "quantity": quantity, "estimatedAmount": amount,
            "cashBefore": member.asset, "heldQuantity": held_quantity,
            "reason": None if executable else ("보유 현금이 부족합니다." if side == "BUY" else "매도 가능 수량이 부족합니다."),
            "notice": "미리보기는 주문·보유자산을 변경하지 않으며 실제 체결 가격과 다를 수 있습니다."}


@trade_router.post("/order/sell")
def order_sell(member_id: MemberId, db: DbSession, payload: CryptoSellBody = Body(default_factory=CryptoSellBody)) -> dict:
    if not payload.marketCode or payload.sellCount is None:
        raise ApiError(400, error="마켓코드와 매도수량을 입력해주세요.")
    sell_count = parse_float(payload.sellCount)
    if sell_count is None:
        raise ApiError(400, error="숫자만 입력해주세요.")
    if sell_count <= 0:
        raise ApiError(400, error="0보다 큰 수를 입력해주세요.")
    member = crypto.member_for_update(db, member_id)
    try:
        return crypto.execute_crypto_sell(db, member, payload.marketCode, sell_count)
    except ValueError as exc:
        raise ApiError(400, error=str(exc))
    except Exception:
        raise ApiError(503, error="현재가를 가져오지 못했습니다.")


@trade_router.get("/order/history")
def order_history(member_id: MemberId, db: DbSession, limit: int = Query(200)) -> dict:
    return {"history": crypto.order_history(db, member_id, clamp(limit, 1, 1000))}
