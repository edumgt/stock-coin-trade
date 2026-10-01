"""운영 중인 모의투자 서비스에 안전하게 추가할 수 있는 예제 투자자 데이터."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import session_scope
from app.models import (
    AlternativeOrder,
    AlternativePosition,
    CryptoOrder,
    HoldCrypto,
    Member,
    StockOrder,
    StockPosition,
    UpbitMarket,
)
from app.services.members import hash_password
from app.services.stock_market import BASE_PRICES, STOCKS

LOGGER = logging.getLogger(__name__)
DEMO_EMAIL_DOMAIN = "@sample-investor.local"
DEMO_PASSWORD = "123456"
INITIAL_ASSET = 100_000_000

DEMO_NAMES = (
    "김가온", "이도윤", "박서연", "최민준", "정하린", "윤지후", "한예린", "오현우", "서유진", "강시우",
    "임나연", "조태윤", "신채원", "권도현", "문서진", "배지민", "송예준", "남유나", "류건우", "안수빈",
    "노재현", "장다은", "백준서", "허지안", "전민서", "고은찬", "황유진", "차도윤", "양하은", "서건호",
)

CRYPTO_MARKETS = {
    "KRW-BTC": ("비트코인", "Bitcoin", 150_000_000),
    "KRW-ETH": ("이더리움", "Ethereum", 5_000_000),
    "KRW-XRP": ("리플", "XRP", 3_100),
    "KRW-SOL": ("솔라나", "Solana", 240_000),
    "KRW-ADA": ("에이다", "Cardano", 1_150),
    "KRW-DOGE": ("도지코인", "Dogecoin", 260),
    "KRW-AVAX": ("아발란체", "Avalanche", 36_000),
    "KRW-LINK": ("체인링크", "Chainlink", 28_000),
    "KRW-DOT": ("폴카닷", "Polkadot", 7_500),
    "KRW-TRX": ("트론", "TRON", 410),
}

# 운영 화면 시연에 사용할 계정의 포트폴리오다. 주문의 source 값으로 적용 여부를
# 판별하므로, 재기동과 재배포 때 사용자가 만든 주문을 덮어쓰지 않는다.
GANADA_USERNAME = "가나다"
GANADA_DATASET_SOURCE = "GANADA_DATASET"
GANADA_CASH = 44_300_000
GANADA_STOCKS = (
    ("005930", 80, 70_000),
    ("000660", 25, 170_000),
    ("035420", 30, 180_000),
    ("005380", 20, 205_000),
    ("005490", 14, 400_000),
)
GANADA_COINS = (
    ("KRW-BTC", 3_450_000, 138_000_000),
    ("KRW-ETH", 2_400_000, 4_000_000),
    ("KRW-XRP", 1_950_000, 2_600),
    ("KRW-SOL", 1_800_000, 225_000),
    ("KRW-ADA", 1_400_000, 1_000),
)
GANADA_ALTERNATIVES = (
    ("RE-SEOUL", "서울 강남 아파트 지분", "부동산", 1, 12_850_000, 1, 12_850_000),
    ("MET-GOLD", "금 (순금 99.99%)", "금", 12, 175_000, 1, 2_100_000),
    ("MET-SILVER", "은 (99.9%)", "은", 500, 2_480, 1, 1_240_000),
    ("OPT-K200-C", "KOSPI 200 콜옵션", "옵션", 10, 12_800, 25, 3_200_000),
    ("FUT-USD", "미국 달러 선물", "선물", 20, 13_850, 10, 332_400),
)

# 변동성 기능 테스트용 계정. 주식 7종목(전 섹터 분산)·코인 6종·대체자산 6종
# (선물·옵션·파생상품·금·은·부동산 각 1개씩)을 보유해, 보유자산 화면의 자산별
# 수익률 변동성 배지를 자산군마다 다양하게 확인할 수 있게 한다.
BABABA_USERNAME = "바바바"
BABABA_DATASET_SOURCE = "BABABA_DATASET"
BABABA_CASH = 37_275_100
BABABA_STOCKS = (
    ("005930", 60, 74_000),    # 삼성전자 · 반도체·IT
    ("263750", 100, 28_000),   # 펄어비스 · 게임
    ("373220", 15, 320_000),   # LG에너지솔루션 · 2차전지
    ("035420", 25, 185_000),   # NAVER · 인터넷·플랫폼
    ("005490", 10, 410_000),   # POSCO홀딩스 · 철강·소재
    ("068270", 20, 178_000),   # 셀트리온 · 바이오·헬스케어
    ("247540", 60, 92_000),    # 에코프로비엠 · 2차전지
)
BABABA_COINS = (
    ("KRW-BTC", 4_500_000, 150_000_000),
    ("KRW-ETH", 3_600_000, 5_000_000),
    ("KRW-XRP", 2_800_000, 3_100),
    ("KRW-SOL", 2_500_000, 240_000),
    ("KRW-DOGE", 2_000_000, 260),
    ("KRW-TRX", 1_600_000, 410),
)
BABABA_ALTERNATIVES = (
    ("FUT-K200", "KOSPI 200 선물", "선물", 20, 372_500, 1, 1_117_500),
    ("OPT-K200-P", "KOSPI 200 풋옵션", "옵션", 8, 10_400, 25, 2_080_000),
    ("DRV-INV", "KOSPI 200 인버스", "파생상품", 100, 7_920, 1, 792_000),
    ("MET-GOLD", "금 (순금 99.99%)", "금", 8, 178_300, 1, 1_426_400),
    ("MET-SILVER", "은 (99.9%)", "은", 300, 2_480, 1, 744_000),
    ("RE-PANGYO", "판교 아파트 지분", "부동산", 1, 9_720_000, 1, 9_720_000),
)


def _demo_email(index: int) -> str:
    return f"sample-investor-{index:02d}{DEMO_EMAIL_DOMAIN}"


def _get_or_create_market(db: Session, code: str) -> UpbitMarket:
    market = db.scalars(select(UpbitMarket).where(UpbitMarket.market_code == code)).first()
    if market:
        return market
    korean_name, english_name, _ = CRYPTO_MARKETS[code]
    market = UpbitMarket(market_code=code, korean_name=korean_name, english_name=english_name)
    db.add(market)
    db.flush()
    return market


def _portfolio_for(index: int) -> tuple[list[tuple[str, int, int]], list[tuple[str, int, float]]]:
    """각 투자자에게 서로 다른 2개 주식과 2개 코인 포지션을 만든다."""
    symbols = list(STOCKS)
    coin_codes = list(CRYPTO_MARKETS)
    stock_allocations = (1_650_000, 1_250_000)
    crypto_allocations = (900_000, 700_000)
    stocks = []
    coins = []

    for offset, allocation in enumerate(stock_allocations):
        symbol = symbols[(index * 3 + offset * 5) % len(symbols)]
        base = BASE_PRICES[symbol]
        # 투자자마다 평균 매입가가 달라 수익·손실 사례가 함께 나타난다.
        avg_price = int(base * (0.86 + ((index + offset * 2) % 8) * 0.04))
        quantity = max(1, allocation // avg_price)
        stocks.append((symbol, quantity, avg_price))

    for offset, allocation in enumerate(crypto_allocations):
        code = coin_codes[(index * 2 + offset * 3) % len(coin_codes)]
        base_price = CRYPTO_MARKETS[code][2]
        avg_price = base_price * (0.80 + ((index + offset * 3) % 9) * 0.05)
        coins.append((code, allocation, avg_price))
    return stocks, coins


def seed_demo_investors() -> int:
    """30개의 샘플 투자자와 보유 주식·코인을 추가한다.

    같은 이메일이 이미 있으면 해당 계정은 그대로 두므로 재기동·재배포해도
    중복 생성하거나 사용자가 변경한 샘플 포트폴리오를 덮어쓰지 않는다.
    """
    if not get_settings().demo_seed_enabled:
        return 0

    try:
        with session_scope() as db:
            password_hash = hash_password(DEMO_PASSWORD)
            added = 0
            now = datetime.now()
            for index, name in enumerate(DEMO_NAMES, start=1):
                if db.scalars(select(Member).where(Member.email == _demo_email(index))).first():
                    continue

                stocks, coins = _portfolio_for(index - 1)
                stock_cost = sum(quantity * avg_price for _, quantity, avg_price in stocks)
                crypto_cost = sum(amount for _, amount, _ in coins)
                member = Member(
                    username=name,
                    email=_demo_email(index),
                    password=password_hash,
                    asset=max(300_000, INITIAL_ASSET - stock_cost - crypto_cost),
                )
                db.add(member)
                db.flush()

                for order_index, (symbol, quantity, avg_price) in enumerate(stocks):
                    db.add(StockPosition(member_id=member.member_id, symbol=symbol, quantity=quantity, avg_price=avg_price))
                    db.add(StockOrder(
                        member_id=member.member_id, symbol=symbol, name=STOCKS[symbol]["name"],
                        order_type="BUY", quantity=quantity, price=avg_price, amount=quantity * avg_price,
                        source="DEMO_SEED", created_at=now - timedelta(days=8 + index + order_index * 4),
                    ))

                for code, amount, avg_price in coins:
                    market = _get_or_create_market(db, code)
                    db.add(HoldCrypto(
                        member_id=member.member_id, upbit_market_id=market.upbit_market_id,
                        buy_average=avg_price, buy_crypto_count=round(amount / avg_price, 8), buy_total_krw=amount,
                    ))
                added += 1
        if added:
            LOGGER.info("Added %s sample investor portfolios.", added)
        return added
    except Exception:
        # 시드 실패가 서비스 기동 자체를 막지 않도록 하되, 원인은 컨테이너 로그에 남긴다.
        LOGGER.exception("Unable to seed sample investor portfolios")
        return 0


def _seed_dataset(db: Session, member: Member, *, source: str, cash: int, stocks, coins, alternatives,
                  stock_day_base: int, stock_day_step: int, coin_day_base: int, coin_day_step: int,
                  alt_day_base: int, alt_day_step: int) -> None:
    """시연 계정 하나에 분산 포트폴리오를 적용한다. 동일 종목 보유분은 수량과 평균 매입가를 합산해 보존한다."""
    member.asset = cash
    now = datetime.now()
    for index, (symbol, quantity, price) in enumerate(stocks):
        position = db.scalars(select(StockPosition).where(StockPosition.member_id == member.member_id, StockPosition.symbol == symbol)).first()
        if position:
            total_quantity = position.quantity + quantity
            position.avg_price = round((position.avg_price * position.quantity + price * quantity) / total_quantity)
            position.quantity = total_quantity
        else:
            db.add(StockPosition(member_id=member.member_id, symbol=symbol, quantity=quantity, avg_price=price))
        db.add(StockOrder(member_id=member.member_id, symbol=symbol, name=STOCKS[symbol]["name"],
                          order_type="BUY", quantity=quantity, price=price, amount=quantity * price,
                          source=source, created_at=now - timedelta(days=stock_day_base - index * stock_day_step)))

    for index, (code, amount, price) in enumerate(coins):
        market = _get_or_create_market(db, code)
        quantity = round(amount / price, 8)
        holding = db.scalars(select(HoldCrypto).where(HoldCrypto.member_id == member.member_id,
                                                      HoldCrypto.upbit_market_id == market.upbit_market_id)).first()
        if holding:
            total_quantity = holding.buy_crypto_count + quantity
            total_amount = holding.buy_total_krw + amount
            holding.buy_average = round(total_amount / total_quantity, 8)
            holding.buy_crypto_count = total_quantity
            holding.buy_total_krw = total_amount
        else:
            db.add(HoldCrypto(member_id=member.member_id, upbit_market_id=market.upbit_market_id,
                              buy_average=price, buy_crypto_count=quantity, buy_total_krw=amount))
        db.add(CryptoOrder(member_id=member.member_id, market_code=code, korean_name=market.korean_name,
                           order_type="BUY", quantity=quantity, price=price, amount=amount,
                           source=source, created_at=now - timedelta(days=coin_day_base - index * coin_day_step)))

    for index, (symbol, name, category, quantity, price, multiplier, amount) in enumerate(alternatives):
        position = db.scalars(select(AlternativePosition).where(AlternativePosition.member_id == member.member_id,
                                                                AlternativePosition.symbol == symbol)).first()
        if position:
            total_quantity = position.quantity + quantity
            position.avg_price = round((position.avg_price * position.quantity + price * quantity) / total_quantity)
            position.quantity = total_quantity
        else:
            db.add(AlternativePosition(member_id=member.member_id, symbol=symbol, category=category,
                                       quantity=quantity, avg_price=price))
        db.add(AlternativeOrder(member_id=member.member_id, symbol=symbol, name=name, category=category,
                                order_type="BUY", quantity=quantity, price=price, multiplier=multiplier,
                                amount=amount, source=source, created_at=now - timedelta(days=alt_day_base - index * alt_day_step)))


def _seed_named_account(username: str, source: str, **dataset) -> bool:
    try:
        with session_scope() as db:
            member = db.scalars(select(Member).where(Member.username == username).order_by(Member.member_id)).first()
            if member is None:
                LOGGER.info("Portfolio dataset skipped: %s account was not found.", username)
                return False
            already = db.scalars(select(StockOrder).where(StockOrder.member_id == member.member_id, StockOrder.source == source)).first()
            if already:
                return False
            _seed_dataset(db, member, source=source, **dataset)
        LOGGER.info("Added diversified portfolio dataset for %s.", username)
        return True
    except Exception:
        LOGGER.exception("Unable to seed the %s portfolio dataset", username)
        return False


def seed_ganada_dataset() -> bool:
    """`가나다` 계정에 화면 시연용 분산 포트폴리오를 한 번만 준비한다."""
    return _seed_named_account(
        GANADA_USERNAME, GANADA_DATASET_SOURCE, cash=GANADA_CASH,
        stocks=GANADA_STOCKS, coins=GANADA_COINS, alternatives=GANADA_ALTERNATIVES,
        stock_day_base=35, stock_day_step=5, coin_day_base=28, coin_day_step=4, alt_day_base=20, alt_day_step=3,
    )


def seed_bababa_dataset() -> bool:
    """`바바바` 계정에 자산별 수익률 변동성 기능 테스트용 분산 포트폴리오를 한 번만 준비한다."""
    return _seed_named_account(
        BABABA_USERNAME, BABABA_DATASET_SOURCE, cash=BABABA_CASH,
        stocks=BABABA_STOCKS, coins=BABABA_COINS, alternatives=BABABA_ALTERNATIVES,
        stock_day_base=35, stock_day_step=4, coin_day_base=30, coin_day_step=4, alt_day_base=18, alt_day_step=3,
    )
