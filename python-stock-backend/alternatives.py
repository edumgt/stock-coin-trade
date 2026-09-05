"""모의 파생·귀금속·부동산 시장과 주문 API.

외부 시세 라이선스에 의존하지 않는 교육용 기준 시세다. 가격은 영업일별로
변동하며, 각 상품의 단위·계약승수·증거금 정보를 응답에 함께 제공한다.
"""
import math
from datetime import date, timedelta

from flask import Blueprint, jsonify, request, session
from sqlalchemy import text

from db import engine, session_scope
from models import AlternativeOrder, AlternativePosition, Member

alternative_bp = Blueprint("alternatives", __name__, url_prefix="/api/alternatives")

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


def _quote(symbol: str) -> dict:
    item = CATALOG[symbol]
    # 교육용 기준 시세의 하루 단위 변동. 주문·평가가 같은 기준으로 일관되게 계산된다.
    wave = math.sin(date.today().toordinal() * 0.71 + sum(map(ord, symbol)))
    rate = round(wave * (0.018 if item["category"] in {"옵션", "파생상품"} else 0.009), 2)
    price = max(1, round(item["price"] * (1 + rate / 100)))
    amount_per_unit = price * item["multiplier"]
    margin_per_unit = round(amount_per_unit * item["marginRate"] / 100)
    quote = {"symbol": symbol, **item, "price": price, "changeRate": rate,
            "notionalPerUnit": amount_per_unit, "tradeAmountPerUnit": margin_per_unit,
            "updatedAt": date.today().isoformat(), "source": "교육용 기준 시세"}
    if item.get("pointScale"):
        quote["actualPoint"] = price / item["pointScale"]
    return quote


def get_chart(symbol: str, days: int = 120) -> list[dict]:
    """교육용 기준가에서 파생한 일봉 데이터. 마지막 종가는 현재 주문 기준가와 일치한다."""
    quote = _quote(symbol)
    days = max(30, min(days, 365))
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
    scale = quote["price"] / raw[-1][4]
    return [{"time": row[0], "open": round(row[1] * scale), "high": round(row[2] * scale),
             "low": round(row[3] * scale), "close": round(row[4] * scale)} for row in raw]


def get_positions(db, member_id: int) -> list[dict]:
    rows = db.query(AlternativePosition).filter(AlternativePosition.member_id == member_id).all()
    result = []
    for row in rows:
        quote = _quote(row.symbol)
        # 선물은 계약 명목금액이 아니라 주문 시 납부한 증거금을 기준으로 손익을 표시한다.
        cost = round(row.avg_price * quote["multiplier"] * quote["marginRate"] / 100) * row.quantity
        value = quote["tradeAmountPerUnit"] * row.quantity
        result.append({"symbol": row.symbol, "name": quote["name"], "category": row.category,
                       "quantity": row.quantity, "avgPrice": row.avg_price, "currentPrice": quote["price"],
                       "multiplier": quote["multiplier"], "unit": quote["unit"], "evalAmount": value,
                       "pnl": value - cost, "marginRate": quote["marginRate"]})
    return result


def position_value(db, member_id: int) -> int:
    return sum(item["evalAmount"] for item in get_positions(db, member_id))


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


@alternative_bp.before_request
def require_login():
    if not session.get("member_id"):
        return jsonify({"error": "UNAUTHORIZED", "message": "로그인이 필요합니다."}), 401


@alternative_bp.get("/markets")
def markets():
    return jsonify({"markets": [_quote(symbol) for symbol in CATALOG], "notice": "교육용 기준 시세이며 실제 투자 권유 또는 실거래 가격이 아닙니다."})


@alternative_bp.get("/markets/<symbol>/chart")
def chart(symbol: str):
    symbol = symbol.upper()
    if symbol not in CATALOG:
        return jsonify({"message": "지원하지 않는 상품입니다."}), 404
    try:
        days = int(request.args.get("days", 120))
    except (TypeError, ValueError):
        days = 120
    return jsonify({"symbol": symbol, "data": get_chart(symbol, days)})


@alternative_bp.get("/positions")
def positions():
    with session_scope() as db:
        rows = get_positions(db, session["member_id"])
        return jsonify({"positions": rows, "totalEvalAmount": sum(row["evalAmount"] for row in rows)})


@alternative_bp.get("/orders/history")
def history():
    with session_scope() as db:
        rows = db.query(AlternativeOrder).filter(AlternativeOrder.member_id == session["member_id"]).order_by(AlternativeOrder.created_at.desc()).limit(100).all()
        return jsonify({"history": [{"symbol": row.symbol, "name": row.name, "category": row.category,
          "type": row.order_type, "quantity": row.quantity, "price": row.price, "amount": row.amount,
          "source": row.source, "ts": int(row.created_at.timestamp() * 1000)} for row in rows]})


def execute_alternative_order(db, member: Member, symbol: str, side: str, quantity: int, source: str = "WEB") -> dict:
    """대체자산 주문 체결. 라우트와 봇 거래 스케줄러가 함께 사용하는 단일 진입점이다."""
    if symbol not in CATALOG or side not in {"BUY", "SELL"} or quantity <= 0:
        raise ValueError("상품, 매수/매도 구분, 1 이상의 수량을 확인해주세요.")
    quote = _quote(symbol)
    amount = quote["tradeAmountPerUnit"] * quantity
    position = db.query(AlternativePosition).filter_by(member_id=member.member_id, symbol=symbol).first()
    if side == "BUY":
        if member.asset < amount:
            raise ValueError("보유 현금이 부족합니다.")
        member.asset -= amount
        if position is None:
            position = AlternativePosition(member_id=member.member_id, symbol=symbol, category=quote["category"], quantity=quantity, avg_price=quote["price"])
            db.add(position)
        else:
            total_qty = position.quantity + quantity
            position.avg_price = round((position.avg_price * position.quantity + quote["price"] * quantity) / total_qty)
            position.quantity = total_qty
    else:
        if position is None or position.quantity < quantity:
            raise ValueError("매도 가능한 보유 수량이 부족합니다.")
        position.quantity -= quantity
        member.asset += amount
        if position.quantity == 0:
            db.delete(position)
    db.add(AlternativeOrder(member_id=member.member_id, symbol=symbol, name=quote["name"], category=quote["category"], order_type=side, quantity=quantity, price=quote["price"], multiplier=quote["multiplier"], amount=amount, source=source))
    return {"status": "ok", "cash": member.asset, "price": quote["price"], "amount": amount}


@alternative_bp.post("/orders")
def order():
    data = request.get_json(silent=True) or {}
    symbol, side = str(data.get("symbol", "")).upper(), str(data.get("side", "")).upper()
    try:
        quantity = int(data.get("quantity", 0))
    except (TypeError, ValueError):
        quantity = 0
    with session_scope() as db:
        # 현금 확인과 차감을 하나의 잠금 단위로 묶어 동시 주문으로 인한 음수 잔액을 막는다.
        member = db.query(Member).filter(Member.member_id == session["member_id"]).with_for_update().one()
        try:
            return jsonify(execute_alternative_order(db, member, symbol, side, quantity))
        except ValueError as exc:
            return jsonify({"message": str(exc)}), 400
