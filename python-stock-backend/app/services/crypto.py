"""코인 시장 조회와 모의 매수·매도(업비트 현재가 기준)."""

from __future__ import annotations

import time

import requests
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models import CryptoOrder, CryptoRank, HoldCrypto, Member, UpbitMarket


def ensure_crypto_tables() -> None:
    # 기존 운영 DB에도 재배포만으로 코인 거래내역 기능을 사용할 수 있게 한다.
    with engine.begin() as conn:
        conn.execute(text("""CREATE TABLE IF NOT EXISTS crypto_order (
          crypto_order_id BIGINT AUTO_INCREMENT PRIMARY KEY, member_id BIGINT NOT NULL,
          market_code VARCHAR(30) NOT NULL, korean_name VARCHAR(255), order_type VARCHAR(4) NOT NULL,
          quantity DOUBLE NOT NULL, price DOUBLE NOT NULL, amount BIGINT NOT NULL,
          source VARCHAR(20) NOT NULL DEFAULT 'WEB', created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          KEY idx_crypto_order_member_created (member_id, created_at),
          CONSTRAINT fk_crypto_order_member FOREIGN KEY (member_id) REFERENCES member(member_id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""))


def serialize_market(m: UpbitMarket) -> dict:
    return {"id": m.upbit_market_id, "market": m.market_code, "koreanName": m.korean_name, "englishName": m.english_name}


def serialize_rank(r: CryptoRank) -> dict:
    return {
        "id": r.crypto_rank_id,
        "name": r.name,
        "symbol": r.symbol,
        "apiCryptoId": r.api_crypto_id,
        "quote": {
            "usd": {
                "price": r.price,
                "marketCap": float(r.market_cap) if r.market_cap is not None else None,
                "percentChange24h": r.percent_change24h,
                "percentChange7d": r.percent_change7d,
            }
        },
    }


def list_rankings(db: Session) -> list[dict]:
    return [serialize_rank(r) for r in db.scalars(select(CryptoRank).order_by(CryptoRank.crypto_rank_id)).all()]


def list_krw_markets(db: Session) -> list[UpbitMarket]:
    return db.scalars(
        select(UpbitMarket).where(UpbitMarket.market_code.like("KRW%")).order_by(UpbitMarket.upbit_market_id)
    ).all()


def find_market(db: Session, code: str) -> UpbitMarket | None:
    return db.scalars(select(UpbitMarket).where(UpbitMarket.market_code == code)).first()


def find_holding(db: Session, member_id: int, upbit_market_id: int, *, lock: bool = False) -> HoldCrypto | None:
    statement = select(HoldCrypto).where(HoldCrypto.member_id == member_id, HoldCrypto.upbit_market_id == upbit_market_id)
    if lock:
        statement = statement.with_for_update()
    return db.scalars(statement).first()


def member_for_update(db: Session, member_id: int) -> Member:
    """동일 자산의 동시 매도/매수를 직렬화해 수량 또는 현금이 음수가 되는 것을 막는다."""
    return db.execute(select(Member).where(Member.member_id == member_id).with_for_update()).scalar_one()


# ── 시세 ────────────────────────────────────────────────────────────────────

def _extract_symbol(market_code: str) -> str:
    code = (market_code or "BTC").strip().upper()
    parts = code.split("-")
    return parts[1] if len(parts) == 2 and parts[1] else code


def _fetch_price_safely(url, extractor):
    try:
        resp = requests.get(url, timeout=2)
        if not resp.ok:
            return None
        return extractor(resp.json())
    except Exception:
        return None


def fetch_domestic_prices(market_code: str) -> dict:
    symbol = _extract_symbol(market_code)
    normalized = f"KRW-{symbol}"

    upbit_price = _fetch_price_safely(
        f"https://api.upbit.com/v1/ticker?markets={normalized}",
        lambda d: round(d[0]["trade_price"]) if d else None,
    )
    bithumb_price = _fetch_price_safely(
        f"https://api.bithumb.com/public/ticker/{symbol}_KRW",
        lambda d: round(float(d["data"]["closing_price"])),
    )
    coinone_price = _fetch_price_safely(
        f"https://api.coinone.co.kr/public/v2/ticker_new/KRW/{symbol}",
        lambda d: round(float(d["tickers"][0]["last"])) if d.get("tickers") else None,
    )
    korbit_price = _fetch_price_safely(
        f"https://api.korbit.co.kr/v1/ticker/detailed?currency_pair={symbol.lower()}_krw",
        lambda d: round(float(d["last"])),
    )

    prices = [
        {"exchangeCode": "UPBIT", "exchangeName": "업비트", "tradePriceKrw": upbit_price},
        {"exchangeCode": "BITHUMB", "exchangeName": "빗썸", "tradePriceKrw": bithumb_price},
        {"exchangeCode": "COINONE", "exchangeName": "코인원", "tradePriceKrw": coinone_price},
        {"exchangeCode": "KORBIT", "exchangeName": "코빗", "tradePriceKrw": korbit_price},
    ]
    return {"marketCode": normalized, "symbol": symbol, "fetchedAt": int(time.time() * 1000), "prices": prices}


def upbit_trade_price(market_code: str) -> float:
    resp = requests.get(f"https://api.upbit.com/v1/ticker?markets={market_code}", timeout=5)
    resp.raise_for_status()
    return float(resp.json()[0]["trade_price"])


# ── 보유·거래 ───────────────────────────────────────────────────────────────

def hold_summary(db: Session, member: Member) -> dict:
    rows = db.execute(
        select(HoldCrypto, UpbitMarket)
        .join(UpbitMarket, HoldCrypto.upbit_market_id == UpbitMarket.upbit_market_id)
        .where(HoldCrypto.member_id == member.member_id)
    ).all()
    hold_list = []
    total_buy_krw = 0
    market_codes = []
    for held, market in rows:
        symbol = market.market_code.split("-")[1]
        hold_list.append({
            "marketCode": market.market_code,
            "marketCodeOnlySymbol": symbol,
            "koreanName": market.korean_name,
            "holdCount": held.buy_crypto_count,
            "buyAverage": held.buy_average,
            "buyTotalKrw": held.buy_total_krw,
        })
        total_buy_krw += held.buy_total_krw
        market_codes.append(market.market_code)
    return {
        "memberAsset": member.asset,
        "totalBuyKrw": total_buy_krw,
        "holdCryptoList": hold_list,
        "marketArrayList": market_codes,
    }


def execute_crypto_buy(db: Session, member: Member, market_code: str, buy_krw: int, source: str = "WEB") -> dict:
    """매수 체결. 라우트와 봇 거래 스케줄러가 함께 사용하는 단일 진입점이다."""
    if buy_krw > member.asset:
        raise ValueError("매수 가능 금액보다 클 수 없습니다.")

    market = find_market(db, market_code)
    if not market:
        raise ValueError(f"존재하지 않는 마켓입니다: {market_code}")

    now_price = upbit_trade_price(market_code)
    buy_crypto_count = round(buy_krw / now_price, 8)

    held = find_holding(db, member.member_id, market.upbit_market_id)
    if held is None:
        db.add(HoldCrypto(
            member_id=member.member_id, upbit_market_id=market.upbit_market_id,
            buy_crypto_count=buy_crypto_count, buy_average=now_price, buy_total_krw=buy_krw,
        ))
    else:
        before_avg, before_count = held.buy_average, held.buy_crypto_count
        total_buy_krw = held.buy_total_krw + buy_krw
        total_count = round(before_count + buy_crypto_count, 8)
        held.buy_average = round((before_avg * before_count + buy_krw) / total_count, 8)
        held.buy_crypto_count = total_count
        held.buy_total_krw = total_buy_krw

    member.asset -= buy_krw
    db.add(CryptoOrder(member_id=member.member_id, market_code=market_code, korean_name=market.korean_name,
                       order_type="BUY", quantity=buy_crypto_count, price=now_price, amount=buy_krw, source=source))
    return {"success": True, "asset": member.asset}


def execute_crypto_sell(db: Session, member: Member, market_code: str, sell_count: float, source: str = "WEB") -> dict:
    """매도 체결. 라우트와 봇 거래 스케줄러가 함께 사용하는 단일 진입점이다."""
    market = find_market(db, market_code)
    if not market:
        raise ValueError("암호화폐를 보유중이지 않습니다.")

    held = find_holding(db, member.member_id, market.upbit_market_id, lock=True)
    if held is None:
        raise ValueError("암호화폐를 보유중이지 않습니다.")
    if held.buy_crypto_count < sell_count:
        raise ValueError("매도 가능 개수보다 클 수 없습니다.")

    now_price = upbit_trade_price(market_code)
    buy_crypto_count, buy_total_krw = held.buy_crypto_count, held.buy_total_krw

    sell_to_krw = round(buy_total_krw / (buy_crypto_count / sell_count))
    held.buy_total_krw = buy_total_krw - sell_to_krw
    updated_count = round(buy_crypto_count - sell_count, 8)
    held.buy_crypto_count = updated_count

    sell_eval_krw = round(now_price * sell_count)
    member.asset += sell_eval_krw
    if updated_count == 0:
        db.delete(held)

    db.add(CryptoOrder(member_id=member.member_id, market_code=market_code, korean_name=market.korean_name,
                       order_type="SELL", quantity=sell_count, price=now_price, amount=sell_eval_krw, source=source))
    return {"success": True, "asset": member.asset}


def order_history(db: Session, member_id: int, limit: int) -> list[dict]:
    rows = db.scalars(
        select(CryptoOrder).where(CryptoOrder.member_id == member_id).order_by(CryptoOrder.created_at.desc()).limit(limit)
    ).all()
    return [{
        "marketCode": row.market_code, "koreanName": row.korean_name, "type": row.order_type,
        "quantity": row.quantity, "price": row.price, "amount": row.amount, "source": row.source,
        "ts": int(row.created_at.timestamp() * 1000),
    } for row in rows]
