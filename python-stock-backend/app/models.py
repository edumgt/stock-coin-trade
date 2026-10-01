"""SQLAlchemy 2.0 타입 매핑 모델(회원·모의투자 MariaDB)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
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
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Member(Base):
    __tablename__ = "member"
    __table_args__ = (CheckConstraint("asset >= 0", name="chk_member_asset_nonnegative"),)

    member_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    password: Mapped[str | None] = mapped_column(String(255))
    asset: Mapped[int] = mapped_column(BigInteger, nullable=False)


class UpbitMarket(Base):
    __tablename__ = "upbit_market"

    upbit_market_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    market_code: Mapped[str | None] = mapped_column(String(255))
    korean_name: Mapped[str | None] = mapped_column(String(255))
    english_name: Mapped[str | None] = mapped_column(String(255))


class HoldCrypto(Base):
    __tablename__ = "hold_crypto"

    hold_crypto_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    buy_average: Mapped[float] = mapped_column(Float, nullable=False)
    buy_crypto_count: Mapped[float] = mapped_column(Float, nullable=False)
    buy_total_krw: Mapped[int] = mapped_column(BigInteger, nullable=False)
    member_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("member.member_id"))
    upbit_market_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("upbit_market.upbit_market_id"))


class CryptoOrder(Base):
    """코인 모의 매수·매도 체결 내역. HoldCrypto(보유)와 별도로 거래내역 화면에 사용된다."""

    __tablename__ = "crypto_order"

    crypto_order_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("member.member_id"), nullable=False)
    market_code: Mapped[str] = mapped_column(String(30), nullable=False)
    korean_name: Mapped[str | None] = mapped_column(String(255))
    order_type: Mapped[str] = mapped_column(String(4), nullable=False)  # BUY | SELL
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="WEB")  # WEB | BOT
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class CryptoRank(Base):
    __tablename__ = "crypto_rank"

    crypto_rank_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    api_crypto_id: Mapped[int | None] = mapped_column(Integer)
    name: Mapped[str | None] = mapped_column(String(255))
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(38, 2))
    percent_change24h: Mapped[float] = mapped_column(Float, nullable=False)
    percent_change7d: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(255))


class StockPosition(Base):
    __tablename__ = "stock_position"
    __table_args__ = (UniqueConstraint("member_id", "symbol", name="uq_stock_position_member_symbol"),)

    stock_position_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("member.member_id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_price: Mapped[int] = mapped_column(BigInteger, nullable=False)


class StockOrder(Base):
    __tablename__ = "stock_order"

    stock_order_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("member.member_id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100))
    order_type: Mapped[str] = mapped_column(String(4), nullable=False)  # BUY | SELL
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="WEB")  # WEB | OPENAPI | PINE | BOT
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class KisPracticeAccount(Base):
    """KIS 실거래 연습 전용 가상 예수금. 기존 Member.asset과 분리된다."""

    __tablename__ = "kis_practice_account"
    __table_args__ = (UniqueConstraint("member_id", name="uq_kis_practice_account_member"),)

    kis_practice_account_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("member.member_id"), nullable=False)
    cash: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class KisPracticePosition(Base):
    """KIS 실거래 연습 전용 국내주식 포지션."""

    __tablename__ = "kis_practice_position"
    __table_args__ = (UniqueConstraint("member_id", "symbol", name="uq_kis_practice_position_member_symbol"),)

    kis_practice_position_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("member.member_id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_price: Mapped[int] = mapped_column(BigInteger, nullable=False)


class KisPracticeOrder(Base):
    """KIS 실거래 연습 전용 가상 체결 이력."""

    __tablename__ = "kis_practice_order"

    kis_practice_order_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("member.member_id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    order_type: Mapped[str] = mapped_column(String(4), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class HtsWatchMemo(Base):
    """로그인 회원별 HTS 관심종목 메모."""

    __tablename__ = "hts_watch_memo"
    __table_args__ = (UniqueConstraint("member_id", "symbol", name="uq_hts_watch_memo_member_symbol"),)

    hts_watch_memo_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("member.member_id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    memo: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AlternativePosition(Base):
    """금속·파생상품·부동산 모의투자 보유 포지션."""

    __tablename__ = "alternative_position"
    __table_args__ = (UniqueConstraint("member_id", "symbol", name="uq_alternative_position_member_symbol"),)

    alternative_position_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("member.member_id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_price: Mapped[int] = mapped_column(BigInteger, nullable=False)


class AlternativeOrder(Base):
    __tablename__ = "alternative_order"

    alternative_order_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("member.member_id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    order_type: Mapped[str] = mapped_column(String(4), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="WEB")  # WEB | BOT
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    multiplier: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class ApiKey(Base):
    __tablename__ = "api_key"

    api_key_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("member.member_id"), nullable=False)
    label: Mapped[str | None] = mapped_column(String(100))
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SystemErrorLog(Base):
    """서버 및 브라우저에서 수집한 진단 로그. 민감정보는 저장 전에 마스킹한다."""

    __tablename__ = "system_error_log"

    system_error_log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # SERVER | CLIENT | KIS_GATEWAY
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="ERROR")
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(160), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    stack_trace: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_meta: Mapped[str | None] = mapped_column(Text, nullable=True)
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    member_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("member.member_id"), nullable=True)


class ApiUsageLog(Base):
    """외부 증권사·거래소 API 테스트 호출의 감사 이력. 인증 원문은 저장하지 않는다."""

    __tablename__ = "api_usage_log"

    api_usage_log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    called_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    member_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("member.member_id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    request_meta: Mapped[str | None] = mapped_column(Text, nullable=True)
    http_status: Mapped[int] = mapped_column(Integer, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
