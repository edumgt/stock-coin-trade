"""system01~system20 시장 활동 봇.

이 프로젝트에는 사용자 간에 체결되는 공유 오더북(matching engine)이 없다.
모든 주문은 서버가 계산한 기준 시세로 각 계정에 대해 즉시 체결되므로, 봇이
실제 사용자의 개별 주문에 상대방으로 "개입"할 방법은 없다. 대신 이 모듈은
system01~system20이라는 20개의 독립된 봇 계정을 만들고, 10분마다 무작위로
일부 봇을 골라 주식·코인·대체자산 중 하나를 매수 또는 매도하게 한다.

봇도 stock_trading.execute_order / crypto의 execute_crypto_buy·sell /
alternatives의 execute_alternative_order를 실제 사용자와 완전히 동일하게
호출하므로, 봇 거래도 실제 거래와 같은 방식으로 각 봇 계정의 보유자산(포지션)과
거래내역(주문 기록)에 남는다.
"""
import logging
import random

import bcrypt

import stock_trading
from alternatives import CATALOG as ALT_CATALOG
from alternatives import _quote as alt_quote
from alternatives import execute_alternative_order
from crypto import execute_crypto_buy, execute_crypto_sell
from db import session_scope
from demo_seed import CRYPTO_MARKETS
from models import AlternativePosition, HoldCrypto, Member, StockPosition, UpbitMarket
from stock_market import STOCKS, current_price

LOGGER = logging.getLogger(__name__)

BOT_COUNT = 20
BOT_EMAIL_DOMAIN = "@system-bot.local"
BOT_PASSWORD = "system-bot-account"  # 로그인용이 아니라 계정 생성 요건을 맞추기 위한 값
BOT_INITIAL_ASSET = 100_000_000
BOTS_PER_ROUND = 6  # 라운드마다 무작위로 골라 거래를 시도하는 봇 수
MIN_BUDGET_RATE, MAX_BUDGET_RATE = 0.01, 0.04  # 보유 현금 대비 1회 주문 비중


def bot_username(index: int) -> str:
    return f"system{index:02d}"


def _bot_email(index: int) -> str:
    return f"{bot_username(index)}{BOT_EMAIL_DOMAIN}"


def ensure_bot_accounts() -> int:
    """system01~system20 봇 계정을 만든다. 이미 있으면 그대로 둔다."""
    try:
        with session_scope() as db:
            password_hash = bcrypt.hashpw(BOT_PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            added = 0
            for index in range(1, BOT_COUNT + 1):
                email = _bot_email(index)
                if db.query(Member).filter(Member.email == email).first():
                    continue
                db.add(Member(username=bot_username(index), email=email, password=password_hash, asset=BOT_INITIAL_ASSET))
                added += 1
        if added:
            LOGGER.info("Created %s market-bot accounts (system01-system%02d).", added, BOT_COUNT)
        return added
    except Exception:
        LOGGER.exception("Unable to ensure market-bot accounts")
        return 0


def _trade_stock(db, member: Member) -> str | None:
    positions = db.query(StockPosition).filter(StockPosition.member_id == member.member_id).all()
    if positions and random.random() < 0.45:
        pos = random.choice(positions)
        quantity = random.randint(1, pos.quantity)
        stock_trading.execute_order(db, member, pos.symbol, stock_trading.SELL, quantity, source="BOT")
        return f"주식 매도 {pos.symbol} {quantity}주"

    symbol = random.choice(list(STOCKS))
    price = current_price(symbol)
    if price <= 0:
        return None
    quantity = int(member.asset * random.uniform(MIN_BUDGET_RATE, MAX_BUDGET_RATE) // price)
    if quantity < 1:
        return None
    stock_trading.execute_order(db, member, symbol, stock_trading.BUY, quantity, source="BOT")
    return f"주식 매수 {symbol} {quantity}주"


def _trade_crypto(db, member: Member) -> str | None:
    holdings = db.query(HoldCrypto).filter(HoldCrypto.member_id == member.member_id).all()
    if holdings and random.random() < 0.45:
        held = random.choice(holdings)
        market = db.get(UpbitMarket, held.upbit_market_id)
        sell_count = round(held.buy_crypto_count * random.uniform(0.2, 1.0), 8)
        if not market or sell_count <= 0:
            return None
        execute_crypto_sell(db, member, market.market_code, sell_count, source="BOT")
        return f"코인 매도 {market.market_code} {sell_count}"

    market_codes = [row[0] for row in db.query(UpbitMarket.market_code)
                     .filter(UpbitMarket.market_code.in_(CRYPTO_MARKETS)).all()]
    if not market_codes:
        return None
    market_code = random.choice(market_codes)
    buy_krw = int(member.asset * random.uniform(MIN_BUDGET_RATE, MAX_BUDGET_RATE))
    if buy_krw < 1_000:
        return None
    execute_crypto_buy(db, member, market_code, buy_krw, source="BOT")
    return f"코인 매수 {market_code} {buy_krw:,}원"


def _trade_alternative(db, member: Member) -> str | None:
    positions = db.query(AlternativePosition).filter(AlternativePosition.member_id == member.member_id).all()
    if positions and random.random() < 0.45:
        pos = random.choice(positions)
        quantity = random.randint(1, pos.quantity)
        execute_alternative_order(db, member, pos.symbol, "SELL", quantity, source="BOT")
        return f"대체자산 매도 {pos.symbol} {quantity}"

    symbol = random.choice(list(ALT_CATALOG))
    unit_cost = alt_quote(symbol)["tradeAmountPerUnit"]
    if unit_cost <= 0:
        return None
    quantity = int(member.asset * random.uniform(MIN_BUDGET_RATE, MAX_BUDGET_RATE) // unit_cost)
    if quantity < 1:
        return None
    execute_alternative_order(db, member, symbol, "BUY", quantity, source="BOT")
    return f"대체자산 매수 {symbol} {quantity}"


def _random_action_for_bot(db, member: Member) -> str | None:
    db.refresh(member, with_for_update=True)
    asset_class = random.choices(("STOCK", "CRYPTO", "ALT"), weights=(3, 3, 2))[0]
    try:
        if asset_class == "STOCK":
            return _trade_stock(db, member)
        if asset_class == "CRYPTO":
            return _trade_crypto(db, member)
        return _trade_alternative(db, member)
    except ValueError:
        # 잔액·보유 수량 부족 등은 조용히 건너뛰고 다음 라운드에 다시 시도한다.
        return None
    except Exception:
        LOGGER.exception("Bot trade attempt failed for %s (%s)", member.username, asset_class)
        return None


def run_bot_trading_round() -> None:
    """스케줄러가 10분마다 호출: 무작위로 고른 봇들이 각각 매수 또는 매도를 한 건씩 시도한다."""
    try:
        with session_scope() as db:
            bots = db.query(Member).filter(Member.email.like(f"%{BOT_EMAIL_DOMAIN}")).all()
            if not bots:
                return
            chosen = random.sample(bots, k=min(BOTS_PER_ROUND, len(bots)))
            log_lines = []
            for member in chosen:
                outcome = _random_action_for_bot(db, member)
                if outcome:
                    log_lines.append(f"{member.username}: {outcome}")
        if log_lines:
            LOGGER.info("Bot trading round: %s", "; ".join(log_lines))
    except Exception:
        LOGGER.exception("Bot trading round failed")
