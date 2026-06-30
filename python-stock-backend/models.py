from sqlalchemy import BigInteger, Column, Float, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Member(Base):
    __tablename__ = "member"

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
