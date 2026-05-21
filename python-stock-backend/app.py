from flask import Flask, jsonify, request
import threading
import time

app = Flask(__name__)
lock = threading.Lock()

BASE_PRICES = {
    "AAPL": 260000,
    "MSFT": 540000,
    "NVDA": 170000,
    "TSLA": 250000,
    "AMZN": 260000
}

state = {
    "initial_cash": 10_000_000,
    "cash": 10_000_000,
    "positions": {}
}


def current_price(symbol: str) -> int:
    base = BASE_PRICES.get(symbol.upper(), 100000)
    wave = int((time.time() // 10) % 20) - 10
    return max(1000, base + wave * (base // 500))


def build_position(symbol: str, position: dict) -> dict:
    price = current_price(symbol)
    eval_amount = position["quantity"] * price
    pnl = eval_amount - (position["quantity"] * position["avg_price"])
    return {
        "symbol": symbol,
        "quantity": position["quantity"],
        "avgPrice": position["avg_price"],
        "currentPrice": price,
        "evalAmount": eval_amount,
        "pnl": pnl
    }


def account_snapshot() -> dict:
    total_position_value = 0
    for symbol, position in state["positions"].items():
        total_position_value += position["quantity"] * current_price(symbol)

    total_asset = state["cash"] + total_position_value
    initial_cash = state["initial_cash"]
    pnl_rate = 0
    if initial_cash != 0:
        pnl_rate = ((total_asset - initial_cash) / initial_cash) * 100
    return {
        "cash": state["cash"],
        "totalAsset": total_asset,
        "totalPnlRate": round(pnl_rate, 4)
    }


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/stocks/quote")
def quote():
    symbol = request.args.get("symbol", "").upper()
    if not symbol:
        return jsonify({"message": "symbol is required"}), 400

    price = current_price(symbol)
    base = BASE_PRICES.get(symbol, price)
    change_rate = ((price - base) / base) * 100 if base else 0

    return jsonify({
        "symbol": symbol,
        "price": price,
        "changeRate": round(change_rate, 4)
    })


@app.get("/api/stocks/account")
def account():
    with lock:
        return jsonify(account_snapshot())


@app.get("/api/stocks/positions")
def positions():
    with lock:
        result = [build_position(symbol, position) for symbol, position in state["positions"].items()]
        return jsonify({"positions": result})


@app.post("/api/stocks/orders/buy")
def buy():
    data = request.get_json(silent=True) or {}
    symbol = str(data.get("symbol", "")).upper()
    try:
        quantity = int(data.get("quantity", 0))
    except (TypeError, ValueError):
        return jsonify({"message": "quantity는 정수여야 합니다."}), 400

    if not symbol or quantity <= 0:
        return jsonify({"message": "symbol and quantity(>0) are required"}), 400

    price = current_price(symbol)
    amount = price * quantity

    with lock:
        if amount > state["cash"]:
            return jsonify({"message": "보유 현금이 부족합니다."}), 400

        state["cash"] -= amount
        position = state["positions"].get(symbol)
        if position is None:
            state["positions"][symbol] = {"quantity": quantity, "avg_price": price}
        else:
            total_quantity = position["quantity"] + quantity
            total_buy_amount = (position["avg_price"] * position["quantity"]) + amount
            position["quantity"] = total_quantity
            position["avg_price"] = int(total_buy_amount / total_quantity)

        return jsonify({
            "status": "ok",
            "symbol": symbol,
            "quantity": quantity,
            "price": price
        })


@app.post("/api/stocks/orders/sell")
def sell():
    data = request.get_json(silent=True) or {}
    symbol = str(data.get("symbol", "")).upper()
    try:
        quantity = int(data.get("quantity", 0))
    except (TypeError, ValueError):
        return jsonify({"message": "quantity는 정수여야 합니다."}), 400

    if not symbol or quantity <= 0:
        return jsonify({"message": "symbol and quantity(>0) are required"}), 400

    with lock:
        position = state["positions"].get(symbol)
        if position is None or position["quantity"] < quantity:
            return jsonify({"message": "매도 가능한 수량이 부족합니다."}), 400

        price = current_price(symbol)
        amount = price * quantity
        position["quantity"] -= quantity
        state["cash"] += amount

        if position["quantity"] == 0:
            del state["positions"][symbol]

        return jsonify({
            "status": "ok",
            "symbol": symbol,
            "quantity": quantity,
            "price": price
        })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
