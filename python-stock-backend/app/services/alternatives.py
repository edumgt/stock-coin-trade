"""모의 파생·귀금속·부동산 시장(교육용 기준 시세·주문 체결)."""

from __future__ import annotations

import math
import threading
import time
from datetime import date, timedelta

import yfinance as yf
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models import AlternativeOrder, AlternativePosition, Member
from app.services.volatility import annualized_volatility

CATALOG = {
    "FUT-K200": {"name": "KOSPI 200 선물", "category": "선물", "price": 372_500, "multiplier": 1, "unit": "1계약", "marginRate": 15, "description": "KOSPI 200 지수 선물 축소 모의계약", "pointScale": 1_000, "actualMultiplier": 250_000},
    "FUT-USD": {"name": "미국 달러 선물", "category": "선물", "price": 13_850, "multiplier": 10, "unit": "10 USD", "marginRate": 12, "description": "원/달러 환율 선물 모의계약"},
    "OPT-K200-C": {"name": "KOSPI 200 콜옵션", "category": "옵션", "price": 12_800, "multiplier": 25, "unit": "1계약", "marginRate": 100, "description": "상승 전망을 연습하는 콜옵션"},
    "OPT-K200-P": {"name": "KOSPI 200 풋옵션", "category": "옵션", "price": 10_400, "multiplier": 25, "unit": "1계약", "marginRate": 100, "description": "하락 위험 헤지를 연습하는 풋옵션"},
    "DRV-LEV": {"name": "KOSPI 200 레버리지", "category": "파생상품", "price": 18_450, "multiplier": 1, "unit": "1좌", "marginRate": 100, "description": "지수 수익률 2배 추종형 모의 ETN"},
    "DRV-INV": {"name": "KOSPI 200 인버스", "category": "파생상품", "price": 7_920, "multiplier": 1, "unit": "1좌", "marginRate": 100, "description": "지수 하락 방향 모의 ETN"},
    "MET-GOLD": {"name": "금 (순금 99.99%)", "category": "금", "price": 178_300, "multiplier": 1, "unit": "1g", "marginRate": 100, "description": "국내 금 현물 기준 모의가격"},
    "MET-SILVER": {"name": "은 (99.9%)", "category": "은", "price": 2_480, "multiplier": 1, "unit": "1g", "marginRate": 100, "description": "국내 은 현물 기준 모의가격"},
    "RE-SEOUL": {"name": "서울 강남 아파트 지분", "category": "부동산", "price": 12_850_000, "multiplier": 1, "unit": "1구좌", "marginRate": 100, "description": "전용 84㎡ 대표 단지 시세를 분할한 교육용 지분", "location": {"lat": 37.4979, "lng": 127.0276, "label": "서울 강남구"}},
    "RE-PANGYO": {"name": "판교 아파트 지분", "category": "부동산", "price": 9_720_000, "multiplier": 1, "unit": "1구좌", "marginRate": 100, "description": "전용 84㎡ 대표 단지 시세를 분할한 교육용 지분", "location": {"lat": 37.3947, "lng": 127.1112, "label": "경기 성남시 판교"}},
    "RE-BUSAN": {"name": "부산 해운대 아파트 지분", "category": "부동산", "price": 6_380_000, "multiplier": 1, "unit": "1구좌", "marginRate": 100, "description": "전용 84㎡ 대표 단지 시세를 분할한 교육용 지분", "location": {"lat": 35.1631, "lng": 129.1636, "label": "부산 해운대구"}},
}

# Yahoo Finance는 무료 데이터라 장중에는 지연될 수 있다. 실제 선물 호가를
# 선물 계약으로 오인하지 않도록 KOSPI200은 지수, USD 선물은 환율을 기준으로
# 표시한다. 옵션·부동산은 공개 실시간 원천이 없어 교육용 기준가를 유지한다.
LIVE_FEEDS = {
    "FUT-K200": {"ticker": "^KS200", "scale": 1_000, "label": "KOSPI 200 지수 연동 (Yahoo Finance 지연 시세)"},
    "FUT-USD": {"ticker": "KRW=X", "scale": 10, "label": "원/달러 환율 연동 (Yahoo Finance 지연 시세)"},
    "DRV-LEV": {"ticker": "122630.KS", "scale": 1, "label": "KODEX 레버리지 (Yahoo Finance 지연 시세)"},
    "DRV-INV": {"ticker": "114800.KS", "scale": 1, "label": "KODEX 인버스 (Yahoo Finance 지연 시세)"},
    "MET-GOLD": {"ticker": "GC=F", "scale": 1, "label": "국제 금 선물 참고 (Yahoo Finance 지연 시세)"},
    "MET-SILVER": {"ticker": "SI=F", "scale": 1, "label": "국제 은 선물 참고 (Yahoo Finance 지연 시세)"},
}
LIVE_TTL = 60
LEVERAGED_CATEGORIES = {"선물", "옵션", "파생상품"}
_live_chart_cache: dict[str, dict] = {}
_live_chart_lock = threading.Lock()


def _feed_scale(symbol: str) -> float:
    """원화/g로 표시하는 금속 상품에는 최신 USD/KRW 환율을 적용한다."""
    feed = LIVE_FEEDS[symbol]
    if symbol not in {"MET-GOLD", "MET-SILVER"}:
        return feed["scale"]
    try:
        fx = yf.Ticker("KRW=X").history(period="5d", interval="1d", auto_adjust=False)["Close"].dropna().iloc[-1]
        return float(fx) / 31.1035  # troy oz → g, USD → KRW
    except Exception:
        return 1.0


def _live_chart(symbol: str, days: int = 365) -> list[dict]:
    """실제 일봉을 가져온다. 실패 시 빈 목록으로 돌려 기존 모의 기준가를 사용한다."""
    if symbol not in LIVE_FEEDS:
        return []
    now = time.time()
    cached = _live_chart_cache.get(symbol)
    if cached and now - cached["ts"] < LIVE_TTL:
        return cached["data"][-days:]
    with _live_chart_lock:
        cached = _live_chart_cache.get(symbol)
        if cached and now - cached["ts"] < LIVE_TTL:
            return cached["data"][-days:]
        try:
            rows = yf.Ticker(LIVE_FEEDS[symbol]["ticker"]).history(period="2y", interval="1d", auto_adjust=False)
            scale = _feed_scale(symbol)
            data = []
            for index, row in rows.iterrows():
                values = [float(row[key]) * scale for key in ("Open", "High", "Low", "Close")]
                if not all(math.isfinite(value) and value > 0 for value in values):
                    continue
                data.append({"time": index.date().isoformat(), "open": round(values[0]), "high": round(values[1]),
                             "low": round(values[2]), "close": round(values[3])})
            if len(data) >= 2:
                _live_chart_cache[symbol] = {"ts": now, "data": data}
                return data[-days:]
        except Exception:
            pass
        return cached["data"][-days:] if cached else []


def quote(symbol: str) -> dict:
    item = CATALOG[symbol]
    live_data = _live_chart(symbol, 2)
    if len(live_data) >= 2:
        price = live_data[-1]["close"]
        previous = live_data[-2]["close"]
        rate = round((price - previous) / previous * 100, 2) if previous else 0
        source = LIVE_FEEDS[symbol]["label"]
        updated_at = live_data[-1]["time"]
    else:
        # 공개 실시간 원천이 없는 옵션·부동산, 또는 공급자 장애 시에만 기준가를 쓴다.
        wave = math.sin(date.today().toordinal() * 0.71 + sum(map(ord, symbol)))
        rate = round(wave * (0.018 if item["category"] in {"옵션", "파생상품"} else 0.009), 2)
        price = max(1, round(item["price"] * (1 + rate / 100)))
        source = "교육용 기준 시세"
        updated_at = date.today().isoformat()
    amount_per_unit = price * item["multiplier"]
    margin_per_unit = round(amount_per_unit * item["marginRate"] / 100)
    result = {"symbol": symbol, **item, "price": price, "changeRate": rate,
              "notionalPerUnit": amount_per_unit, "tradeAmountPerUnit": margin_per_unit,
              "updatedAt": updated_at, "source": source}
    if item.get("pointScale"):
        result["actualPoint"] = price / item["pointScale"]
    return result


def get_chart(symbol: str, days: int = 120) -> list[dict]:
    """실제 일봉을 우선 반환하고, 지원하지 않는 상품은 교육용 차트로 대체한다."""
    days = max(30, min(days, 365))
    live_data = _live_chart(symbol, days)
    if len(live_data) >= 2:
        return live_data
    current = quote(symbol)
    raw = []
    for index in range(days):
        day = date.today() - timedelta(days=days - index - 1)
        seed = sum(map(ord, symbol)) + day.toordinal()
        center = 1 + math.sin(seed * .17) * .035 + math.cos(seed * .043) * .018
        opening = center * (1 + math.sin(seed * .31) * .009)
        closing = center * (1 + math.cos(seed * .23) * .011)
        high = max(opening, closing) * (1.006 + abs(math.sin(seed)) * .012)
        low = min(opening, closing) * (1 - .006 - abs(math.cos(seed)) * .01)
        raw.append((day.isoformat(), opening, high, low, closing))
    scale = current["price"] / raw[-1][4]
    return [{"time": row[0], "open": round(row[1] * scale), "high": round(row[2] * scale),
             "low": round(row[3] * scale), "close": round(row[4] * scale)} for row in raw]


def get_positions(db: Session, member_id: int, include_volatility: bool = False) -> list[dict]:
    rows = db.scalars(select(AlternativePosition).where(AlternativePosition.member_id == member_id)).all()
    result = []
    for row in rows:
        current = quote(row.symbol)
        # 선물은 계약 명목금액이 아니라 주문 시 납부한 증거금을 기준으로 손익을 표시한다.
        cost = round(row.avg_price * current["multiplier"] * current["marginRate"] / 100) * row.quantity
        value = current["tradeAmountPerUnit"] * row.quantity
        item = {"symbol": row.symbol, "name": current["name"], "category": row.category,
                "quantity": row.quantity, "avgPrice": row.avg_price, "currentPrice": current["price"],
                "multiplier": current["multiplier"], "unit": current["unit"], "evalAmount": value,
                "pnl": value - cost, "marginRate": current["marginRate"]}
        if include_volatility:
            # 교육용 기준 시세의 최근 30일 종가로 계산한 연환산(252거래일) 변동성(%).
            item["volatility"] = annualized_volatility(
                [candle["close"] for candle in get_chart(row.symbol, 30)], trading_periods=252
            )
        result.append(item)
    return result


def position_value(db: Session, member_id: int) -> int:
    return sum(item["evalAmount"] for item in get_positions(db, member_id))


def get_position(db: Session, member_id: int, symbol: str) -> AlternativePosition | None:
    return db.scalars(
        select(AlternativePosition).where(AlternativePosition.member_id == member_id, AlternativePosition.symbol == symbol)
    ).first()


def order_history(db: Session, member_id: int, limit: int = 100) -> list[dict]:
    rows = db.scalars(
        select(AlternativeOrder)
        .where(AlternativeOrder.member_id == member_id)
        .order_by(AlternativeOrder.created_at.desc())
        .limit(limit)
    ).all()
    return [{"symbol": row.symbol, "name": row.name, "category": row.category,
             "type": row.order_type, "quantity": row.quantity, "price": row.price, "amount": row.amount,
             "source": row.source, "ts": int(row.created_at.timestamp() * 1000)} for row in rows]


def ensure_tables() -> None:
    # 기존 운영 DB에도 재배포만으로 새 기능을 사용할 수 있게 안전한 생성문을 실행한다.
    statements = (
        """CREATE TABLE IF NOT EXISTS alternative_position (
          alternative_position_id BIGINT AUTO_INCREMENT PRIMARY KEY, member_id BIGINT NOT NULL,
          symbol VARCHAR(30) NOT NULL, category VARCHAR(20) NOT NULL, quantity INT NOT NULL,
          avg_price BIGINT NOT NULL, UNIQUE KEY uq_alternative_position_member_symbol (member_id, symbol),
          CONSTRAINT fk_alternative_position_member FOREIGN KEY (member_id) REFERENCES member(member_id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        """CREATE TABLE IF NOT EXISTS alternative_order (
          alternative_order_id BIGINT AUTO_INCREMENT PRIMARY KEY, member_id BIGINT NOT NULL,
          symbol VARCHAR(30) NOT NULL, name VARCHAR(100) NOT NULL, category VARCHAR(20) NOT NULL,
          order_type VARCHAR(4) NOT NULL, quantity INT NOT NULL, price BIGINT NOT NULL,
          multiplier INT NOT NULL DEFAULT 1, amount BIGINT NOT NULL, source VARCHAR(20) NOT NULL DEFAULT 'WEB',
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          KEY idx_alternative_order_member_created (member_id, created_at),
          CONSTRAINT fk_alternative_order_member FOREIGN KEY (member_id) REFERENCES member(member_id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        # 이미 배포된 DB에는 컬럼만 추가한다(MariaDB 10.0.2+ IF NOT EXISTS 지원).
        "ALTER TABLE alternative_order ADD COLUMN IF NOT EXISTS source VARCHAR(20) NOT NULL DEFAULT 'WEB'",
    )
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


def execute_alternative_order(db: Session, member: Member, symbol: str, side: str, quantity: int, source: str = "WEB") -> dict:
    """대체자산 주문 체결. 라우트와 봇 거래 스케줄러가 함께 사용하는 단일 진입점이다."""
    if symbol not in CATALOG or side not in {"BUY", "SELL"} or quantity <= 0:
        raise ValueError("상품, 매수/매도 구분, 1 이상의 수량을 확인해주세요.")
    current = quote(symbol)
    amount = current["tradeAmountPerUnit"] * quantity
    position = get_position(db, member.member_id, symbol)
    if side == "BUY":
        if member.asset < amount:
            raise ValueError("보유 현금이 부족합니다.")
        member.asset -= amount
        if position is None:
            db.add(AlternativePosition(member_id=member.member_id, symbol=symbol, category=current["category"],
                                       quantity=quantity, avg_price=current["price"]))
        else:
            total_qty = position.quantity + quantity
            position.avg_price = round((position.avg_price * position.quantity + current["price"] * quantity) / total_qty)
            position.quantity = total_qty
    else:
        if position is None or position.quantity < quantity:
            raise ValueError("매도 가능한 보유 수량이 부족합니다.")
        position.quantity -= quantity
        member.asset += amount
        if position.quantity == 0:
            db.delete(position)
    db.add(AlternativeOrder(member_id=member.member_id, symbol=symbol, name=current["name"], category=current["category"],
                            order_type=side, quantity=quantity, price=current["price"], multiplier=current["multiplier"],
                            amount=amount, source=source))
    return {"status": "ok", "cash": member.asset, "price": current["price"], "amount": amount}


def preview_order(db: Session, member: Member, symbol: str, side: str, quantity: int) -> dict:
    current = quote(symbol)
    position = get_position(db, member.member_id, symbol)
    held_quantity = position.quantity if position else 0
    amount = current["tradeAmountPerUnit"] * quantity
    executable = amount <= member.asset if side == "BUY" else quantity <= held_quantity
    return {"executable": executable, "symbol": symbol, "name": current["name"], "category": current["category"],
            "side": side, "quantity": quantity, "estimatedPrice": current["price"], "estimatedAmount": amount,
            "marginRate": current["marginRate"], "cashBefore": member.asset, "heldQuantity": held_quantity,
            "reason": None if executable else ("보유 현금이 부족합니다." if side == "BUY" else "매도 가능 수량이 부족합니다."),
            "notice": "미리보기는 교육용 기준 시세를 사용하며 주문·잔고를 변경하지 않습니다."}
