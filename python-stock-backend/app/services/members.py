"""회원 인증·HTS 메모·포트폴리오 분석·투자자 랭킹."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta

import bcrypt
import requests
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models import (
    AlternativeOrder,
    CryptoOrder,
    HoldCrypto,
    HtsWatchMemo,
    Member,
    StockOrder,
    StockPosition,
    UpbitMarket,
)
from app.services import stock_trading
from app.services.alternatives import LEVERAGED_CATEGORIES, position_value
from app.services.alternatives import get_positions as get_alternative_positions
from app.services.stock_market import cached_price

INITIAL_ASSET = 100_000_000
RANKING_CACHE_TTL = 30
_ranking_cache: dict = {"ts": 0.0, "data": None}
_ranking_cache_lock = threading.Lock()
_crypto_price_cache: dict = {"ts": 0.0, "prices": {}}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(password: str, hashed: str | None) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), (hashed or "").encode("utf-8"))
    except ValueError:
        return False


def find_by_email(db: Session, email: str) -> Member | None:
    return db.scalars(select(Member).where(Member.email == email)).first()


def authenticate(db: Session, email: str, password: str) -> Member | None:
    member = find_by_email(db, email)
    if not member or not check_password(password, member.password):
        return None
    return member


def register(db: Session, username: str, email: str, password: str) -> Member:
    member = Member(username=username, email=email, password=hash_password(password), asset=INITIAL_ASSET)
    db.add(member)
    db.flush()
    return member


def ensure_member_tables() -> None:
    """기존 DB에도 배포 시 HTS 개인 메모 기능을 안전하게 추가한다."""
    statement = """CREATE TABLE IF NOT EXISTS hts_watch_memo (
      hts_watch_memo_id BIGINT AUTO_INCREMENT PRIMARY KEY,
      member_id BIGINT NOT NULL,
      symbol VARCHAR(20) NOT NULL,
      memo TEXT NOT NULL,
      updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      UNIQUE KEY uq_hts_watch_memo_member_symbol (member_id, symbol),
      CONSTRAINT fk_hts_watch_memo_member FOREIGN KEY (member_id) REFERENCES member(member_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
    with engine.begin() as conn:
        conn.execute(text(statement))


# ── HTS 관심종목 메모 ───────────────────────────────────────────────────────

def _serialize_memo(row: HtsWatchMemo) -> dict:
    return {"symbol": row.symbol, "memo": row.memo, "updatedAt": row.updated_at.isoformat() if row.updated_at else None}


def list_hts_memos(db: Session, member_id: int) -> list[dict]:
    rows = db.scalars(
        select(HtsWatchMemo).where(HtsWatchMemo.member_id == member_id).order_by(HtsWatchMemo.updated_at.desc())
    ).all()
    return [_serialize_memo(row) for row in rows]


def save_hts_memo(db: Session, member_id: int, symbol: str, memo: str) -> dict:
    row = db.scalars(
        select(HtsWatchMemo).where(HtsWatchMemo.member_id == member_id, HtsWatchMemo.symbol == symbol)
    ).first()
    if not memo:
        if row:
            db.delete(row)
        return {"symbol": symbol, "memo": "", "deleted": True}
    if row:
        row.memo = memo
    else:
        row = HtsWatchMemo(member_id=member_id, symbol=symbol, memo=memo)
        db.add(row)
    db.flush()
    return _serialize_memo(row)


# ── 포트폴리오 어드바이저 ──────────────────────────────────────────────────

def _crypto_prices(codes: list[str], timeout: float) -> dict[str, float]:
    response = requests.get("https://api.upbit.com/v1/ticker", params={"markets": ",".join(codes)}, timeout=timeout)
    response.raise_for_status()
    return {row["market"]: float(row["trade_price"]) for row in response.json()}


def portfolio_analysis(db: Session, member: Member) -> dict:
    """여러 분석 기법(자산배분·분산도·레버리지 노출·손익 통계·업종 집중도)을 종합한
    교육용 포트폴리오 어드바이저 리포트. 실제 투자 자문이나 개인별 권유가 아니다."""
    member_id = member.member_id
    stock_positions = stock_trading.get_positions(db, member_id)
    stock_value = sum(p["evalAmount"] for p in stock_positions)

    crypto_rows = db.execute(
        select(HoldCrypto, UpbitMarket)
        .join(UpbitMarket, HoldCrypto.upbit_market_id == UpbitMarket.upbit_market_id)
        .where(HoldCrypto.member_id == member_id)
    ).all()
    codes = sorted({market.market_code for _, market in crypto_rows})
    prices: dict[str, float] = {}
    if codes:
        try:
            prices = _crypto_prices(codes, timeout=1.5)
        except Exception:
            prices = _crypto_price_cache.get("prices", {})
    crypto_positions = []
    for holding, market in crypto_rows:
        price = prices.get(market.market_code, holding.buy_average)
        eval_amount = holding.buy_crypto_count * price
        crypto_positions.append({
            "name": market.korean_name or market.market_code,
            "evalAmount": eval_amount, "pnl": eval_amount - holding.buy_total_krw,
        })
    crypto_value = sum(p["evalAmount"] for p in crypto_positions)

    alternatives = get_alternative_positions(db, member_id)
    alternative_value = sum(row["evalAmount"] for row in alternatives)
    leverage_value = sum(row["evalAmount"] for row in alternatives if row["category"] in LEVERAGED_CATEGORIES)

    cash = round(member.asset)
    values = [
        {"name": "현금", "value": cash, "color": "#64748B"},
        {"name": "주식", "value": round(stock_value), "color": "#2563EB"},
        {"name": "코인", "value": round(crypto_value), "color": "#7C3AED"},
        {"name": "대체자산", "value": round(alternative_value), "color": "#D97706"},
    ]
    total = sum(item["value"] for item in values)
    for item in values:
        item["weight"] = round(item["value"] / total * 100, 1) if total else 0

    # ── 포지션 손익 통계 (주식·코인·대체자산 통합) ──
    all_positions = (
        [{"name": p["name"], "evalAmount": p["evalAmount"], "pnl": p["pnl"]} for p in stock_positions]
        + crypto_positions
        + [{"name": row["name"], "evalAmount": row["evalAmount"], "pnl": row["pnl"]} for row in alternatives]
    )
    for p in all_positions:
        cost = p["evalAmount"] - p["pnl"]
        p["pnlRate"] = round(p["pnl"] / cost * 100, 2) if cost > 0 else 0.0

    position_stats = None
    if all_positions:
        winners = [p for p in all_positions if p["pnl"] > 0]
        best = max(all_positions, key=lambda p: p["pnlRate"])
        worst = min(all_positions, key=lambda p: p["pnlRate"])
        position_stats = {
            "count": len(all_positions),
            "winRate": round(len(winners) / len(all_positions) * 100, 1),
            "avgPnlRate": round(sum(p["pnlRate"] for p in all_positions) / len(all_positions), 2),
            "best": {"name": best["name"], "pnlRate": best["pnlRate"]},
            "worst": {"name": worst["name"], "pnlRate": worst["pnlRate"]},
        }

    # ── 업종 집중도 (주식) ──
    sector_totals: dict[str, float] = {}
    for p in stock_positions:
        sector_totals[p["sector"]] = sector_totals.get(p["sector"], 0) + p["evalAmount"]
    top_sector = None
    if sector_totals and stock_value > 0:
        name, sector_value = max(sector_totals.items(), key=lambda kv: kv[1])
        top_sector = {"name": name, "weight": round(sector_value / stock_value * 100, 1)}

    # ── 분산도 (허핀달-허쉬만 지수 기반 0~100점) ──
    hhi = sum((item["weight"] / 100) ** 2 for item in values)
    min_hhi = 1 / len(values)
    diversification_score = round(max(0, min(100, (1 - hhi) / (1 - min_hhi) * 100))) if total else 0
    diversification_label = "양호" if diversification_score >= 70 else ("보통" if diversification_score >= 40 else "집중됨")

    # ── 레버리지 노출 (선물·옵션·파생상품 vs 현금 버퍼) ──
    leverage_ratio = round(leverage_value / total * 100, 1) if total else 0
    cash_buffer_ratio = round(cash / leverage_value * 100, 1) if leverage_value else None

    # ── 포트폴리오 건강도 점수 (교육용 heuristic: 분산 40% + 레버리지 억제 30% + 현금 버퍼 30%) ──
    leverage_score = max(0, 100 - leverage_ratio * 2)
    buffer_score = 100 if not leverage_value else min(100, cash_buffer_ratio)
    health_score = round(diversification_score * 0.4 + leverage_score * 0.3 + buffer_score * 0.3) if total else 0
    health_label = ("매우 양호" if health_score >= 80 else "양호" if health_score >= 60
                    else "주의" if health_score >= 40 else "위험") if total else "-"

    # ── 체크리스트 (기법별 점검 결과) ──
    weights = {item["name"]: item["weight"] for item in values}
    checks = []
    if not total:
        checks.append({"title": "투자 시작 전", "status": "warn",
                       "message": "아직 투자 자산이 없습니다. 상품별 변동성과 주문 단위를 먼저 살펴본 뒤 소액으로 연습해 보세요."})
    else:
        largest = max(values, key=lambda item: item["weight"])
        checks.append({
            "title": "자산군 분산",
            "status": "good" if diversification_score >= 70 else "warn" if diversification_score >= 40 else "risk",
            "message": f"분산 점수 {diversification_score}점({diversification_label}). " + (
                "자산군이 고르게 나뉘어 있습니다." if diversification_score >= 70
                else f"{largest['name']} 비중이 {largest['weight']}%로 가장 높습니다. 자산군을 나누면 한 시장의 변동 영향이 줄어들 수 있습니다."
            ),
        })
        if leverage_value > 0:
            checks.append({
                "title": "레버리지 노출",
                "status": "risk" if leverage_ratio >= 30 else "warn" if leverage_ratio >= 15 else "good",
                "message": f"선물·옵션·파생상품 비중이 총자산의 {leverage_ratio}%이며, 현금은 이 노출의 {cash_buffer_ratio}% 수준입니다." + (
                    " 증거금 추가 납부나 반대매매 위험에 대비할 현금 여력을 점검하세요." if leverage_ratio >= 15 else ""
                ),
            })
        if top_sector and top_sector["weight"] >= 50:
            checks.append({
                "title": "업종 집중도",
                "status": "risk" if top_sector["weight"] >= 70 else "warn",
                "message": f"주식 포지션 중 {top_sector['name']} 업종이 {top_sector['weight']}%를 차지합니다. 업종 뉴스·실적 이벤트에 대한 민감도가 커질 수 있습니다.",
            })
        if position_stats:
            checks.append({
                "title": "손익 현황",
                "status": "good" if position_stats["winRate"] >= 50 else "warn",
                "message": (f"보유 {position_stats['count']}개 포지션 중 {position_stats['winRate']}%가 수익 구간이며 "
                            f"평균 수익률은 {position_stats['avgPnlRate']:+.2f}%입니다. "
                            f"최고 {position_stats['best']['name']} {position_stats['best']['pnlRate']:+.2f}% · "
                            f"최저 {position_stats['worst']['name']} {position_stats['worst']['pnlRate']:+.2f}%."),
            })
        if weights["현금"] >= 50:
            checks.append({"title": "현금 비중", "status": "good",
                           "message": f"현금 비중이 {weights['현금']}%로 높아 변동성 방어 여력이 큽니다. 투자 목적과 기간에 맞는 분할 진입 계획을 세워볼 수 있습니다."})
        if len(checks) == 1:
            checks.append({"title": "종합", "status": "good",
                           "message": "자산군이 비교적 나뉘어 있습니다. 각 상품의 변동성·유동성·주문 단위를 주기적으로 점검해 비중을 관리하세요."})

    return {
        "totalAsset": round(total), "allocation": values,
        "healthScore": health_score, "healthLabel": health_label,
        "diversification": {"score": diversification_score, "label": diversification_label},
        "leverage": {"value": round(leverage_value), "ratio": leverage_ratio, "cashBufferRatio": cash_buffer_ratio},
        "positionStats": position_stats, "topSector": top_sector, "checks": checks,
        "notice": "자산배분·분산도(HHI)·레버리지 노출·손익 통계 등 여러 기법을 함께 본 모의투자 교육용 리포트이며, 실제 투자 자문이나 개인별 권유가 아닙니다.",
    }


def trading_activity(db: Session, member_id: int, days: int) -> dict:
    """최근 기간의 체결 주문을 자산군별로 합산한 읽기 전용 활동 통계."""
    cutoff = datetime.now() - timedelta(days=days)
    stock = db.scalars(select(StockOrder).where(StockOrder.member_id == member_id, StockOrder.created_at >= cutoff)).all()
    crypto = db.scalars(select(CryptoOrder).where(CryptoOrder.member_id == member_id, CryptoOrder.created_at >= cutoff)).all()
    alternatives = db.scalars(
        select(AlternativeOrder).where(AlternativeOrder.member_id == member_id, AlternativeOrder.created_at >= cutoff)
    ).all()
    orders = (
        [{"assetClass": "STOCK", "side": row.order_type, "amount": row.amount, "source": row.source, "createdAt": row.created_at} for row in stock]
        + [{"assetClass": "CRYPTO", "side": row.order_type, "amount": row.amount, "source": row.source, "createdAt": row.created_at} for row in crypto]
        + [{"assetClass": "ALTERNATIVE", "side": row.order_type, "amount": row.amount, "source": row.source, "createdAt": row.created_at} for row in alternatives]
    )
    totals = {name: {"count": 0, "buyAmount": 0, "sellAmount": 0} for name in ("STOCK", "CRYPTO", "ALTERNATIVE")}
    daily: dict[str, int] = {}
    for order in orders:
        bucket = totals[order["assetClass"]]
        bucket["count"] += 1
        bucket["buyAmount" if order["side"] == "BUY" else "sellAmount"] += int(order["amount"])
        day = order["createdAt"].date().isoformat() if order["createdAt"] else "unknown"
        daily[day] = daily.get(day, 0) + 1
    return {
        "days": days,
        "from": cutoff.date().isoformat(),
        "orderCount": len(orders),
        "turnover": sum(int(order["amount"]) for order in orders),
        "byAssetClass": totals,
        "dailyOrderCounts": [{"date": day, "count": count} for day, count in sorted(daily.items())],
        "notice": "체결 주문을 자산군별로 합산한 모의투자 활동 통계입니다. 미리보기 요청은 포함하지 않습니다.",
    }


def investor_rankings(db: Session) -> dict:
    """현금·주식·코인·대체자산 평가액을 합산한 모의투자 공개 수익 랭킹."""
    now = time.time()
    with _ranking_cache_lock:
        if _ranking_cache["data"] and now - _ranking_cache["ts"] < RANKING_CACHE_TTL:
            return _ranking_cache["data"]

    members = db.scalars(select(Member)).all()
    totals = {member.member_id: float(member.asset) for member in members}

    for position in db.scalars(select(StockPosition)).all():
        # 랭킹 패널은 즉시 보여야 하므로 외부 시세 호출을 기다리지 않는다.
        # 이미 조회한 최신 시세가 없으면 매입단가로 평가한다.
        value = position.quantity * (cached_price(position.symbol) or position.avg_price)
        totals[position.member_id] = totals.get(position.member_id, 0) + value

    crypto_rows = db.execute(
        select(HoldCrypto, UpbitMarket).join(UpbitMarket, HoldCrypto.upbit_market_id == UpbitMarket.upbit_market_id)
    ).all()
    codes = sorted({market.market_code for _, market in crypto_rows})
    prices: dict[str, float] = {}
    if codes and now - _crypto_price_cache["ts"] < RANKING_CACHE_TTL:
        prices = _crypto_price_cache["prices"]
    elif codes:
        try:
            prices = _crypto_prices(codes, timeout=1)
            _crypto_price_cache.update({"ts": now, "prices": prices})
        except Exception:
            pass
    for holding, market in crypto_rows:
        totals[holding.member_id] = totals.get(holding.member_id, 0) + holding.buy_crypto_count * prices.get(market.market_code, holding.buy_average)

    for member in members:
        totals[member.member_id] = totals.get(member.member_id, 0) + position_value(db, member.member_id)

    rankings = []
    for member in members:
        total_asset = round(totals.get(member.member_id, 0))
        profit = total_asset - INITIAL_ASSET
        rankings.append({
            "username": member.username or "익명 투자자",
            "totalAsset": total_asset,
            "profit": profit,
            "profitRate": round(profit / INITIAL_ASSET * 100, 2),
        })
    rankings.sort(key=lambda row: row["profitRate"], reverse=True)
    for rank, row in enumerate(rankings[:10], start=1):
        row["rank"] = rank
    result = {"rankings": rankings[:10], "cachedForSeconds": RANKING_CACHE_TTL}
    with _ranking_cache_lock:
        _ranking_cache.update({"ts": now, "data": result})
    return result
