import time

import requests
from flask import Blueprint, jsonify, request, session
from sqlalchemy import text

from db import engine, session_scope
from models import CryptoOrder, CryptoRank, HoldCrypto, Member, UpbitMarket

market_bp = Blueprint("crypto_market", __name__, url_prefix="/api/crypto")
trade_bp = Blueprint("trade", __name__, url_prefix="/api/trade")


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


def _serialize_market(m: UpbitMarket) -> dict:
    return {
        "id": m.upbit_market_id,
        "market": m.market_code,
        "koreanName": m.korean_name,
        "englishName": m.english_name,
    }


def _serialize_rank(r: CryptoRank) -> dict:
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


@market_bp.get("/rankings")
def rankings():
    with session_scope() as db:
        ranks = db.query(CryptoRank).order_by(CryptoRank.crypto_rank_id).all()
        return jsonify([_serialize_rank(r) for r in ranks])


@market_bp.get("/market-list")
def market_list():
    with session_scope() as db:
        markets = (
            db.query(UpbitMarket)
            .filter(UpbitMarket.market_code.like("KRW%"))
            .order_by(UpbitMarket.upbit_market_id)
            .all()
        )
        return jsonify({
            "markets": [_serialize_market(m) for m in markets],
            "marketCodes": [m.market_code for m in markets],
        })


@market_bp.get("/<code>")
def crypto_info(code):
    with session_scope() as db:
        market = db.query(UpbitMarket).filter(UpbitMarket.market_code == code).first()
        if not market:
            return jsonify({"error": f"존재하지 않는 마켓입니다: {code}"}), 404

        buy_crypto_count = 0
        member_id = session.get("member_id")
        if member_id:
            held = (
                db.query(HoldCrypto)
                .filter(
                    HoldCrypto.member_id == member_id,
                    HoldCrypto.upbit_market_id == market.upbit_market_id,
                )
                .first()
            )
            if held:
                buy_crypto_count = held.buy_crypto_count

        return jsonify({
            "marketCode": market.market_code,
            "koreanName": market.korean_name,
            "englishName": market.english_name,
            "buyCryptoCount": buy_crypto_count,
        })


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


def _fetch_domestic_prices(market_code: str) -> dict:
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


@market_bp.get("/<code>/domestic-prices")
def domestic_prices(code):
    return jsonify(_fetch_domestic_prices(code))


# ── Trade (로그인 필요) ──────────────────────────────────────────────────────

@trade_bp.before_request
def require_login():
    if not session.get("member_id"):
        return jsonify({"error": "UNAUTHORIZED", "message": "로그인이 필요합니다."}), 401


def _upbit_trade_price(market_code: str) -> float:
    resp = requests.get(f"https://api.upbit.com/v1/ticker?markets={market_code}", timeout=5)
    resp.raise_for_status()
    return float(resp.json()[0]["trade_price"])


@trade_bp.get("/hold")
def hold():
    member_id = session["member_id"]
    with session_scope() as db:
        member = db.get(Member, member_id)
        rows = (
            db.query(HoldCrypto, UpbitMarket)
            .join(UpbitMarket, HoldCrypto.upbit_market_id == UpbitMarket.upbit_market_id)
            .filter(HoldCrypto.member_id == member_id)
            .all()
        )

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

        return jsonify({
            "memberAsset": member.asset,
            "totalBuyKrw": total_buy_krw,
            "holdCryptoList": hold_list,
            "marketArrayList": market_codes,
        })


def execute_crypto_buy(db, member: Member, market_code: str, buy_krw: int, source: str = "WEB") -> dict:
    """매수 체결. 라우트와 봇 거래 스케줄러가 함께 사용하는 단일 진입점이다."""
    if buy_krw > member.asset:
        raise ValueError("매수 가능 금액보다 클 수 없습니다.")

    market = db.query(UpbitMarket).filter(UpbitMarket.market_code == market_code).first()
    if not market:
        raise ValueError(f"존재하지 않는 마켓입니다: {market_code}")

    now_price = _upbit_trade_price(market_code)
    buy_crypto_count = round(buy_krw / now_price, 8)

    held = (
        db.query(HoldCrypto)
        .filter(HoldCrypto.member_id == member.member_id, HoldCrypto.upbit_market_id == market.upbit_market_id)
        .first()
    )
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


@trade_bp.post("/order/buy")
def order_buy():
    member_id = session["member_id"]
    body = request.get_json(silent=True) or {}
    market_code = body.get("marketCode")
    buy_krw_raw = body.get("buyKrw")
    if not market_code or buy_krw_raw is None:
        return jsonify({"error": "마켓코드와 매수금액을 입력해주세요."}), 400

    try:
        buy_krw = int(str(buy_krw_raw).replace(",", ""))
    except (TypeError, ValueError):
        return jsonify({"error": "숫자만 입력해주세요."}), 400
    if buy_krw <= 0:
        return jsonify({"error": "0보다 큰 수를 입력해주세요."}), 400

    with session_scope() as db:
        member = db.query(Member).filter(Member.member_id == member_id).with_for_update().one()
        try:
            result = execute_crypto_buy(db, member, market_code, buy_krw)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            return jsonify({"error": "현재가를 가져오지 못했습니다."}), 503
        return jsonify(result)


@trade_bp.post("/order/preview")
def order_preview():
    """Return a non-mutating estimate for a crypto market order."""
    member_id = session["member_id"]
    body = request.get_json(silent=True) or {}
    market_code = str(body.get("marketCode", "")).upper().strip()
    side = str(body.get("side", "")).upper().strip()
    if side not in {"BUY", "SELL"}:
        return jsonify({"error": "side는 BUY 또는 SELL이어야 합니다."}), 400
    with session_scope() as db:
        member = db.get(Member, member_id)
        market = db.query(UpbitMarket).filter(UpbitMarket.market_code == market_code).first()
        if not market:
            return jsonify({"error": "존재하지 않는 마켓입니다."}), 400
        try:
            price = _upbit_trade_price(market_code)
        except Exception:
            return jsonify({"error": "현재가를 가져오지 못했습니다."}), 503
        held = db.query(HoldCrypto).filter_by(member_id=member_id, upbit_market_id=market.upbit_market_id).first()
        held_quantity = held.buy_crypto_count if held else 0.0
        if side == "BUY":
            try:
                amount = int(str(body.get("buyKrw", "")).replace(",", ""))
            except (TypeError, ValueError):
                return jsonify({"error": "buyKrw는 정수여야 합니다."}), 400
            if amount <= 0:
                return jsonify({"error": "buyKrw는 0보다 커야 합니다."}), 400
            quantity = round(amount / price, 8)
            executable = amount <= member.asset
        else:
            try:
                quantity = float(body.get("sellCount", 0))
            except (TypeError, ValueError):
                return jsonify({"error": "sellCount는 숫자여야 합니다."}), 400
            if quantity <= 0:
                return jsonify({"error": "sellCount는 0보다 커야 합니다."}), 400
            amount = round(quantity * price)
            executable = quantity <= held_quantity
        return jsonify({"executable": executable, "marketCode": market_code, "koreanName": market.korean_name,
                        "side": side, "estimatedPrice": price, "quantity": quantity, "estimatedAmount": amount,
                        "cashBefore": member.asset, "heldQuantity": held_quantity,
                        "reason": None if executable else ("보유 현금이 부족합니다." if side == "BUY" else "매도 가능 수량이 부족합니다."),
                        "notice": "미리보기는 주문·보유자산을 변경하지 않으며 실제 체결 가격과 다를 수 있습니다."})


def execute_crypto_sell(db, member: Member, market_code: str, sell_count: float, source: str = "WEB") -> dict:
    """매도 체결. 라우트와 봇 거래 스케줄러가 함께 사용하는 단일 진입점이다."""
    market = db.query(UpbitMarket).filter(UpbitMarket.market_code == market_code).first()
    if not market:
        raise ValueError("암호화폐를 보유중이지 않습니다.")

    held = (
        db.query(HoldCrypto)
        .filter(HoldCrypto.member_id == member.member_id, HoldCrypto.upbit_market_id == market.upbit_market_id)
        .with_for_update()
        .first()
    )
    if held is None:
        raise ValueError("암호화폐를 보유중이지 않습니다.")
    if held.buy_crypto_count < sell_count:
        raise ValueError("매도 가능 개수보다 클 수 없습니다.")

    now_price = _upbit_trade_price(market_code)
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


@trade_bp.post("/order/sell")
def order_sell():
    member_id = session["member_id"]
    body = request.get_json(silent=True) or {}
    market_code = body.get("marketCode")
    sell_count_raw = body.get("sellCount")
    if not market_code or sell_count_raw is None:
        return jsonify({"error": "마켓코드와 매도수량을 입력해주세요."}), 400

    try:
        sell_count = float(sell_count_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "숫자만 입력해주세요."}), 400
    if sell_count <= 0:
        return jsonify({"error": "0보다 큰 수를 입력해주세요."}), 400

    with session_scope() as db:
        # 동일 자산의 동시 매도/매수를 직렬화해 수량 또는 현금이 음수가 되는 것을 막는다.
        member = db.query(Member).filter(Member.member_id == member_id).with_for_update().one()
        try:
            result = execute_crypto_sell(db, member, market_code, sell_count)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            return jsonify({"error": "현재가를 가져오지 못했습니다."}), 503
        return jsonify(result)


@trade_bp.get("/order/history")
def order_history():
    try:
        limit = max(1, min(int(request.args.get("limit", 200)), 1000))
    except (TypeError, ValueError):
        limit = 200
    member_id = session["member_id"]
    with session_scope() as db:
        rows = (
            db.query(CryptoOrder)
            .filter(CryptoOrder.member_id == member_id)
            .order_by(CryptoOrder.created_at.desc())
            .limit(limit)
            .all()
        )
        return jsonify({"history": [{
            "marketCode": row.market_code, "koreanName": row.korean_name, "type": row.order_type,
            "quantity": row.quantity, "price": row.price, "amount": row.amount, "source": row.source,
            "ts": int(row.created_at.timestamp() * 1000),
        } for row in rows]})
