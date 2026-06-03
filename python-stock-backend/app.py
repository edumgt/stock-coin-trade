from flask import Flask, jsonify, request
import threading
import time
import yfinance as yf

app = Flask(__name__)
lock = threading.Lock()

STOCKS = {
    # KOSPI
    "005930": {"name": "삼성전자",          "market": "KOSPI",  "ticker": "005930.KS"},
    "000660": {"name": "SK하이닉스",         "market": "KOSPI",  "ticker": "000660.KS"},
    "005380": {"name": "현대차",             "market": "KOSPI",  "ticker": "005380.KS"},
    "035420": {"name": "NAVER",             "market": "KOSPI",  "ticker": "035420.KS"},
    "035720": {"name": "카카오",             "market": "KOSPI",  "ticker": "035720.KS"},
    "068270": {"name": "셀트리온",           "market": "KOSPI",  "ticker": "068270.KS"},
    "207940": {"name": "삼성바이오로직스",    "market": "KOSPI",  "ticker": "207940.KS"},
    "373220": {"name": "LG에너지솔루션",      "market": "KOSPI",  "ticker": "373220.KS"},
    "005490": {"name": "POSCO홀딩스",        "market": "KOSPI",  "ticker": "005490.KS"},
    # KOSDAQ
    "247540": {"name": "에코프로비엠",        "market": "KOSDAQ", "ticker": "247540.KQ"},
    "196170": {"name": "알테오젠",           "market": "KOSDAQ", "ticker": "196170.KQ"},
    "091990": {"name": "셀트리온헬스케어",    "market": "KOSDAQ", "ticker": "091990.KQ"},
    "086520": {"name": "에코프로",           "market": "KOSDAQ", "ticker": "086520.KQ"},
    "263750": {"name": "펄어비스",           "market": "KOSDAQ", "ticker": "263750.KQ"},
}

# Base prices used as fallback when yfinance is unavailable
BASE_PRICES = {
    "005930": 74000,  "000660": 178000, "005380": 215000,
    "035420": 185000, "035720": 37000,  "068270": 178000,
    "207940": 780000, "373220": 320000, "005490": 410000,
    "247540": 92000,  "196170": 230000, "091990": 41000,
    "086520": 72000,  "263750": 28000,
}

_quote_cache = {}
_chart_cache = {}
_index_cache = {}

QUOTE_TTL  = 60
CHART_TTL  = 300
INDEX_TTL  = 60

state = {
    "initial_cash":  10_000_000,
    "cash":          10_000_000,
    "positions":     {},
    "trade_history": [],
}


def _simulated_price(symbol: str) -> int:
    base = BASE_PRICES.get(symbol, 50000)
    wave = int((time.time() // 10) % 20) - 10
    return max(1000, base + wave * (base // 500))


def get_quote_cached(symbol: str) -> dict:
    now = time.time()
    cached = _quote_cache.get(symbol)
    if cached and now - cached["ts"] < QUOTE_TTL:
        return cached["data"]

    info = STOCKS.get(symbol)
    if not info:
        raise ValueError(f"Unknown symbol: {symbol}")

    try:
        ticker = yf.Ticker(info["ticker"])
        hist = ticker.history(period="5d")
        if hist.empty:
            raise ValueError("empty history")
        last = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) >= 2 else last
        price      = int(last["Close"])
        prev_close = int(prev["Close"])
        change     = price - prev_close
        change_rate = round((change / prev_close * 100) if prev_close else 0, 2)
        volume     = int(last["Volume"])
        data = {
            "symbol":     symbol,
            "name":       info["name"],
            "market":     info["market"],
            "price":      price,
            "prevClose":  prev_close,
            "change":     change,
            "changeRate": change_rate,
            "volume":     volume,
        }
    except Exception:
        sim = _simulated_price(symbol)
        base = BASE_PRICES.get(symbol, sim)
        data = {
            "symbol":     symbol,
            "name":       info["name"],
            "market":     info["market"],
            "price":      sim,
            "prevClose":  base,
            "change":     sim - base,
            "changeRate": round(((sim - base) / base * 100) if base else 0, 2),
            "volume":     0,
            "simulated":  True,
        }

    _quote_cache[symbol] = {"data": data, "ts": now}
    return data


def get_chart_cached(symbol: str, period: str) -> list:
    now = time.time()
    key = (symbol, period)
    cached = _chart_cache.get(key)
    if cached and now - cached["ts"] < CHART_TTL:
        return cached["data"]

    info = STOCKS.get(symbol)
    if not info:
        raise ValueError(f"Unknown symbol: {symbol}")

    period_map   = {"1d": "1d",  "1w": "5d",  "1m": "1mo", "3m": "3mo", "1y": "1y"}
    interval_map = {"1d": "5m",  "1w": "60m", "1m": "1d",  "3m": "1d",  "1y": "1wk"}
    yf_period   = period_map.get(period, "1mo")
    yf_interval = interval_map.get(period, "1d")

    ohlcv = []
    try:
        ticker = yf.Ticker(info["ticker"])
        hist = ticker.history(period=yf_period, interval=yf_interval)
        if hist.empty:
            raise ValueError("empty")
        for ts, row in hist.iterrows():
            ts_ms = int(ts.timestamp() * 1000)
            ohlcv.append({
                "x": ts_ms,
                "o": round(float(row["Open"]),  2),
                "h": round(float(row["High"]),  2),
                "l": round(float(row["Low"]),   2),
                "c": round(float(row["Close"]), 2),
                "v": int(row["Volume"]),
            })
    except Exception:
        # Generate simulated OHLCV when yfinance is unavailable
        base  = BASE_PRICES.get(symbol, 50000)
        steps = {"1d": 78, "1w": 40, "1m": 30, "3m": 90, "1y": 52}.get(period, 30)
        step_ms = {"1d": 300_000, "1w": 3_600_000, "1m": 86_400_000,
                   "3m": 86_400_000, "1y": 604_800_000}.get(period, 86_400_000)
        ts_ms = int(now * 1000) - steps * step_ms
        price = float(base)
        import random
        rng = random.Random(symbol)
        for _ in range(steps):
            o = price
            h = o * (1 + rng.uniform(0, 0.015))
            l = o * (1 - rng.uniform(0, 0.015))
            c = rng.uniform(l, h)
            v = rng.randint(500_000, 5_000_000)
            ohlcv.append({"x": ts_ms, "o": round(o), "h": round(h),
                          "l": round(l), "c": round(c), "v": v})
            price = c
            ts_ms += step_ms

    _chart_cache[key] = {"data": ohlcv, "ts": now}
    return ohlcv


def get_index_cached(index_sym: str) -> dict:
    now = time.time()
    cached = _index_cache.get(index_sym)
    if cached and now - cached["ts"] < INDEX_TTL:
        return cached["data"]

    fallbacks = {"^KS11": {"price": 2600.0, "change": 0.0, "changeRate": 0.0},
                 "^KQ11": {"price": 870.0,  "change": 0.0, "changeRate": 0.0}}

    try:
        ticker = yf.Ticker(index_sym)
        hist = ticker.history(period="5d")
        if hist.empty:
            raise ValueError("empty")
        last  = hist.iloc[-1]
        prev  = hist.iloc[-2] if len(hist) >= 2 else last
        price = round(float(last["Close"]), 2)
        pc    = round(float(prev["Close"]), 2)
        ch    = round(price - pc, 2)
        cr    = round((ch / pc * 100) if pc else 0, 2)
        data  = {"price": price, "change": ch, "changeRate": cr}
    except Exception:
        data = fallbacks.get(index_sym, {"price": 0.0, "change": 0.0, "changeRate": 0.0})

    _index_cache[index_sym] = {"data": data, "ts": now}
    return data


def current_price(symbol: str) -> int:
    try:
        return get_quote_cached(symbol)["price"]
    except Exception:
        return _simulated_price(symbol)


def build_position(symbol: str, position: dict) -> dict:
    price = current_price(symbol)
    eval_amount = position["quantity"] * price
    pnl = eval_amount - (position["quantity"] * position["avg_price"])
    name = STOCKS.get(symbol, {}).get("name", symbol)
    return {
        "symbol":      symbol,
        "name":        name,
        "quantity":    position["quantity"],
        "avgPrice":    position["avg_price"],
        "currentPrice": price,
        "evalAmount":  eval_amount,
        "pnl":         pnl,
    }


def account_snapshot() -> dict:
    total_pos = sum(p["quantity"] * current_price(s) for s, p in state["positions"].items())
    total_asset = state["cash"] + total_pos
    initial    = state["initial_cash"]
    pnl_rate   = round(((total_asset - initial) / initial * 100) if initial else 0, 4)
    return {"cash": state["cash"], "totalAsset": total_asset, "totalPnlRate": pnl_rate}


# ── Health ──────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return jsonify({"status": "ok"})


# ── Stock list ───────────────────────────────────────────────────────────────
@app.get("/api/stocks/list")
def stock_list():
    result = [{"symbol": k, "name": v["name"], "market": v["market"]} for k, v in STOCKS.items()]
    return jsonify({"stocks": result})


# ── Market indices ───────────────────────────────────────────────────────────
@app.get("/api/stocks/market")
def market():
    kospi  = get_index_cached("^KS11")
    kosdaq = get_index_cached("^KQ11")
    return jsonify({"KOSPI": kospi, "KOSDAQ": kosdaq})


# ── Quote ────────────────────────────────────────────────────────────────────
@app.get("/api/stocks/quote")
def quote():
    symbol = request.args.get("symbol", "").upper()
    if not symbol:
        return jsonify({"message": "symbol is required"}), 400
    try:
        return jsonify(get_quote_cached(symbol))
    except ValueError as e:
        return jsonify({"message": str(e)}), 404


# ── Chart ────────────────────────────────────────────────────────────────────
@app.get("/api/stocks/chart")
def chart():
    symbol = request.args.get("symbol", "").upper()
    period = request.args.get("period", "1m")
    if not symbol:
        return jsonify({"message": "symbol is required"}), 400
    try:
        ohlcv = get_chart_cached(symbol, period)
        return jsonify({"symbol": symbol, "period": period, "data": ohlcv})
    except ValueError as e:
        return jsonify({"message": str(e)}), 404


# ── Account ──────────────────────────────────────────────────────────────────
@app.get("/api/stocks/account")
def account():
    with lock:
        return jsonify(account_snapshot())


# ── Positions ────────────────────────────────────────────────────────────────
@app.get("/api/stocks/positions")
def positions():
    with lock:
        result = [build_position(s, p) for s, p in state["positions"].items()]
        return jsonify({"positions": result})


# ── Orders ───────────────────────────────────────────────────────────────────
@app.post("/api/stocks/orders/buy")
def buy():
    data     = request.get_json(silent=True) or {}
    symbol   = str(data.get("symbol", "")).upper()
    try:
        quantity = int(data.get("quantity", 0))
    except (TypeError, ValueError):
        return jsonify({"message": "quantity는 정수여야 합니다."}), 400

    if not symbol or quantity <= 0:
        return jsonify({"message": "symbol and quantity(>0) are required"}), 400
    if symbol not in STOCKS:
        return jsonify({"message": f"지원하지 않는 종목입니다: {symbol}"}), 400

    price  = current_price(symbol)
    amount = price * quantity
    with lock:
        if amount > state["cash"]:
            return jsonify({"message": "보유 현금이 부족합니다."}), 400
        state["cash"] -= amount
        pos = state["positions"].get(symbol)
        if pos is None:
            state["positions"][symbol] = {"quantity": quantity, "avg_price": price}
        else:
            total_qty    = pos["quantity"] + quantity
            total_amount = pos["avg_price"] * pos["quantity"] + amount
            pos["quantity"]  = total_qty
            pos["avg_price"] = int(total_amount / total_qty)
        state["trade_history"].append({
            "ts": int(time.time() * 1000),
            "type": "BUY",
            "symbol": symbol,
            "name": STOCKS[symbol]["name"],
            "quantity": quantity,
            "price": price,
            "amount": amount,
        })
        return jsonify({"status": "ok", "symbol": symbol, "quantity": quantity, "price": price})


@app.post("/api/stocks/orders/sell")
def sell():
    data     = request.get_json(silent=True) or {}
    symbol   = str(data.get("symbol", "")).upper()
    try:
        quantity = int(data.get("quantity", 0))
    except (TypeError, ValueError):
        return jsonify({"message": "quantity는 정수여야 합니다."}), 400

    if not symbol or quantity <= 0:
        return jsonify({"message": "symbol and quantity(>0) are required"}), 400

    with lock:
        pos = state["positions"].get(symbol)
        if pos is None or pos["quantity"] < quantity:
            return jsonify({"message": "매도 가능한 수량이 부족합니다."}), 400
        price  = current_price(symbol)
        amount = price * quantity
        pos["quantity"] -= quantity
        state["cash"]   += amount
        if pos["quantity"] == 0:
            del state["positions"][symbol]
        state["trade_history"].append({
            "ts": int(time.time() * 1000),
            "type": "SELL",
            "symbol": symbol,
            "name": STOCKS.get(symbol, {}).get("name", symbol),
            "quantity": quantity,
            "price": price,
            "amount": amount,
        })
        return jsonify({"status": "ok", "symbol": symbol, "quantity": quantity, "price": price})


# ── Trade History ─────────────────────────────────────────────────────────────
@app.get("/api/stocks/orders/history")
def order_history():
    with lock:
        return jsonify({"history": list(reversed(state["trade_history"]))})


# ── Account Reset ──────────────────────────────────────────────────────────────
@app.post("/api/stocks/account/reset")
def reset_account():
    with lock:
        state["cash"]          = state["initial_cash"]
        state["positions"]     = {}
        state["trade_history"] = []
        return jsonify({"status": "ok", "cash": state["initial_cash"]})


# ── Market Movers ─────────────────────────────────────────────────────────────
@app.get("/api/stocks/movers")
def movers():
    quotes = []
    for symbol in STOCKS:
        try:
            q = get_quote_cached(symbol)
            quotes.append({
                "symbol":     q["symbol"],
                "name":       q["name"],
                "price":      q["price"],
                "changeRate": q.get("changeRate", 0),
                "market":     q["market"],
            })
        except Exception:
            pass
    sorted_q = sorted(quotes, key=lambda x: x.get("changeRate", 0), reverse=True)
    gainers  = sorted_q[:3]
    losers   = sorted_q[-3:][::-1]
    return jsonify({"gainers": gainers, "losers": losers})


# ── Batch Prices (실시간 마켓 리스트용) ──────────────────────────────────────
@app.get("/api/stocks/prices")
def batch_prices():
    result = {}
    for symbol in STOCKS:
        try:
            q = get_quote_cached(symbol)
            result[symbol] = {
                "name":       q["name"],
                "market":     q["market"],
                "price":      q["price"],
                "change":     q.get("change", 0),
                "changeRate": q.get("changeRate", 0),
                "volume":     q.get("volume", 0),
            }
        except Exception:
            info = STOCKS[symbol]
            result[symbol] = {
                "name":       info["name"],
                "market":     info["market"],
                "price":      BASE_PRICES.get(symbol, 0),
                "change":     0,
                "changeRate": 0,
                "volume":     0,
            }
    return jsonify({"prices": result})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8200, debug=False)
