from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Member(Base):
    __tablename__ = "member"
    __table_args__ = (CheckConstraint("asset >= 0", name="chk_member_asset_nonnegative"),)

    member_id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(255))
    email = Column(String(255))
    password = Column(String(255))
    asset = Column(BigInteger, nullable=False)


class UpbitMarket(Base):
    __tablename__ = "upbit_market"

    upbit_market_id = Column(BigInteger, primary_key=True, autoincrement=True)
    market_code = Column(String(255))
    korean_name = Column(String(255))
    english_name = Column(String(255))


class HoldCrypto(Base):
    __tablename__ = "hold_crypto"

    hold_crypto_id = Column(BigInteger, primary_key=True, autoincrement=True)
    buy_average = Column(Float, nullable=False)
    buy_crypto_count = Column(Float, nullable=False)
    buy_total_krw = Column(BigInteger, nullable=False)
    member_id = Column(BigInteger, ForeignKey("member.member_id"))
    upbit_market_id = Column(BigInteger, ForeignKey("upbit_market.upbit_market_id"))


class CryptoOrder(Base):
    """코인 모의 매수·매도 체결 내역. HoldCrypto(보유)와 별도로 거래내역 화면에 사용된다."""
    __tablename__ = "crypto_order"

    crypto_order_id = Column(BigInteger, primary_key=True, autoincrement=True)
    member_id = Column(BigInteger, ForeignKey("member.member_id"), nullable=False)
    market_code = Column(String(30), nullable=False)
    korean_name = Column(String(255))
    order_type = Column(String(4), nullable=False)  # BUY | SELL
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    amount = Column(BigInteger, nullable=False)
    source = Column(String(20), nullable=False, default="WEB")  # WEB | BOT
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class CryptoRank(Base):
    __tablename__ = "crypto_rank"

    crypto_rank_id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_crypto_id = Column(Integer)
    name = Column(String(255))
    market_cap = Column(Numeric(38, 2))
    percent_change24h = Column(Float, nullable=False)
    percent_change7d = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    symbol = Column(String(255))


class StockPosition(Base):
    __tablename__ = "stock_position"
    __table_args__ = (UniqueConstraint("member_id", "symbol", name="uq_stock_position_member_symbol"),)

    stock_position_id = Column(BigInteger, primary_key=True, autoincrement=True)
    member_id = Column(BigInteger, ForeignKey("member.member_id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    quantity = Column(Integer, nullable=False)
    avg_price = Column(BigInteger, nullable=False)


class StockOrder(Base):
    __tablename__ = "stock_order"

    stock_order_id = Column(BigInteger, primary_key=True, autoincrement=True)
    member_id = Column(BigInteger, ForeignKey("member.member_id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    name = Column(String(100))
    order_type = Column(String(4), nullable=False)  # BUY | SELL
    quantity = Column(Integer, nullable=False)
    price = Column(BigInteger, nullable=False)
    amount = Column(BigInteger, nullable=False)
    source = Column(String(20), nullable=False, default="WEB")  # WEB | OPENAPI
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class HtsWatchMemo(Base):
    """로그인 회원별 HTS 관심종목 메모."""
    __tablename__ = "hts_watch_memo"
    __table_args__ = (UniqueConstraint("member_id", "symbol", name="uq_hts_watch_memo_member_symbol"),)

    hts_watch_memo_id = Column(BigInteger, primary_key=True, autoincrement=True)
    member_id = Column(BigInteger, ForeignKey("member.member_id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    memo = Column(Text, nullable=False)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class AlternativePosition(Base):
    """금속·파생상품·부동산 모의투자 보유 포지션."""
    __tablename__ = "alternative_position"
    __table_args__ = (UniqueConstraint("member_id", "symbol", name="uq_alternative_position_member_symbol"),)

    alternative_position_id = Column(BigInteger, primary_key=True, autoincrement=True)
    member_id = Column(BigInteger, ForeignKey("member.member_id"), nullable=False)
    symbol = Column(String(30), nullable=False)
    category = Column(String(20), nullable=False)
    quantity = Column(Integer, nullable=False)
    avg_price = Column(BigInteger, nullable=False)


class AlternativeOrder(Base):
    __tablename__ = "alternative_order"

    alternative_order_id = Column(BigInteger, primary_key=True, autoincrement=True)
    member_id = Column(BigInteger, ForeignKey("member.member_id"), nullable=False)
    symbol = Column(String(30), nullable=False)
    name = Column(String(100), nullable=False)
    category = Column(String(20), nullable=False)
    order_type = Column(String(4), nullable=False)
    source = Column(String(20), nullable=False, default="WEB")  # WEB | BOT
    quantity = Column(Integer, nullable=False)
    price = Column(BigInteger, nullable=False)
    multiplier = Column(Integer, nullable=False, default=1)
    amount = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class ApiKey(Base):
    __tablename__ = "api_key"

    api_key_id = Column(BigInteger, primary_key=True, autoincrement=True)
    member_id = Column(BigInteger, ForeignKey("member.member_id"), nullable=False)
    label = Column(String(100))
    key_prefix = Column(String(16), nullable=False)
    key_hash = Column(String(64), nullable=False, unique=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    last_used_at = Column(DateTime, nullable=True)
