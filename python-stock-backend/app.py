import os
from datetime import timedelta

from flask import Flask, jsonify, request
import threading
import time
import requests as _req
from flask_cors import CORS

from admin import admin_bp
from ai import ai_bp
from api_keys import api_key_bp
from crypto import market_bp, trade_bp
from members import member_bp
from openapi import open_api_bp
from scheduler import start_scheduler
from stock_market import BASE_PRICES, STOCKS, get_chart_cached, get_index_cached, get_quote_cached
from stocks import stock_bp

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

CORS(
    app,
    resources={
        r"/api/*": {"origins": ["http://localhost:*", "http://127.0.0.1:*"]},
        r"/openapi/*": {"origins": "*"},
    },
    supports_credentials=True,
)

app.register_blueprint(member_bp)
app.register_blueprint(market_bp)
app.register_blueprint(trade_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(ai_bp)
app.register_blueprint(stock_bp)
app.register_blueprint(api_key_bp)
app.register_blueprint(open_api_bp)

start_scheduler()


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


# ── Qdrant / RAG endpoints ────────────────────────────────────────────────────

@app.post("/api/stocks/ai/qdrant/search")
def ai_qdrant_search():
    data  = request.get_json(silent=True) or {}
    query = str(data.get("query", "")).strip()
    limit = max(1, min(int(data.get("limit", 5)), 10))
    if not query:
        return jsonify({"error": "query is required"}), 400
    try:
        import qdrant_service as qs
        return jsonify({"results": qs.search(query, limit)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 503


@app.get("/api/stocks/ai/qdrant/stats")
def ai_qdrant_stats():
    try:
        import qdrant_service as qs
        return jsonify(qs.stats())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 503


@app.get("/api/stocks/ai/qdrant/list")
def ai_qdrant_list():
    try:
        import qdrant_service as qs
        limit = max(1, min(int(request.args.get("limit", 30)), 100))
        return jsonify({"documents": qs.list_docs(limit)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 503


@app.post("/api/stocks/ai/qdrant/add")
def ai_qdrant_add():
    data     = request.get_json(silent=True) or {}
    text     = str(data.get("text", "")).strip()
    title    = str(data.get("title", "")).strip()
    category = str(data.get("category", "custom")).strip() or "custom"
    if not text:
        return jsonify({"error": "text is required"}), 400
    if len(text) > 2000:
        return jsonify({"error": "text too long (max 2000 chars)"}), 400
    try:
        import qdrant_service as qs
        doc_id = qs.add_doc(text, title, category)
        return jsonify({"id": doc_id, "status": "added"})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 503


# ── KRX 보도자료 뉴스 ────────────────────────────────────────────────────────

_KRX_API     = "https://open.krx.co.kr/contents/OPN/99/OPN99000001.jspx"
_KRX_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type":    "application/x-www-form-urlencoded; charset=UTF-8",
    "Referer":         "https://open.krx.co.kr/contents/OPN/05/05000000/OPN05000000T1.jsp",
    "X-Requested-With": "XMLHttpRequest",
    "Accept":          "application/json, text/javascript, */*; q=0.01",
}
_KRX_FILE_BASE = "https://file.krx.co.kr"
_KRX_PAGE_URL  = "https://open.krx.co.kr/contents/OPN/05/05000000/OPN05000000.jsp"

_news_cache = {"ts": 0.0, "data": None}
_news_lock  = threading.Lock()
_NEWS_TTL   = 300  # 5분


def _krx_pdf_url(noti_no: str) -> str:
    # noti_no = YYYYMMDDNN  →  file = YYYYMMDD0000NN2.pdf
    date   = noti_no[:8]
    serial = noti_no[8:]
    return f"{_KRX_FILE_BASE}/obk/dyn/noti/{date}0000{serial}2.pdf"


@app.get("/api/stocks/news/krx")
def krx_news():
    now = time.time()
    with _news_lock:
        if _news_cache["data"] and now - _news_cache["ts"] < _NEWS_TTL:
            return jsonify(_news_cache["data"])

    try:
        from datetime import datetime, timedelta
        today    = datetime.now().strftime("%Y%m%d")
        one_year = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
        resp = _req.post(_KRX_API, headers=_KRX_HEADERS, data={
            "bld":      "OPN/05/05000000/opn05000000t1_01",
            "pagePath": "/contents/OPN/05/05000000/OPN05000000T1.jsp",
            "pageSize": "20",
            "sch_tp":   "title",
            "sch_word": "",
            "fromdate": one_year,
            "todate":   today,
        }, timeout=10)
        items = resp.json().get("output", [])
    except Exception as e:
        return jsonify({"error": str(e), "news": []}), 503

    news = []
    for a in items:
        noti_no = a.get("noti_no", "")
        news.append({
            "noti_no":  noti_no,
            "title":    a.get("title", ""),
            "date":     a.get("creat_ddtm", ""),
            "view_cnt": a.get("inq_cnt", "0"),
            "pdf_url":  _krx_pdf_url(noti_no) if len(noti_no) == 10 else None,
            "page_url": _KRX_PAGE_URL,
        })

    result = {"news": news, "total": items[0].get("totCnt", "0") if items else "0"}

    with _news_lock:
        _news_cache["ts"]   = time.time()
        _news_cache["data"] = result

    return jsonify(result)



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8200, debug=False)
