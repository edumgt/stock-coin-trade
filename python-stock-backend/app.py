from flask import Flask, jsonify, request
import threading
import time
import yfinance as yf
import requests as _req

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


# ── Admin: Kubernetes 클러스터 현황 ──────────────────────────────────────────

def _cpu_to_m(s: str) -> int:
    """CPU 문자열 → 밀리코어 정수 (n=나노코어, m=밀리코어, 정수=코어)"""
    s = str(s).strip()
    if s.endswith("n"):
        return int(s[:-1]) // 1_000_000   # nanocores → millicores
    if s.endswith("u"):
        return int(s[:-1]) // 1_000       # microcores → millicores
    if s.endswith("m"):
        return int(s[:-1])
    return int(float(s) * 1000)


def _mem_to_mib(s: str) -> int:
    """메모리 문자열 → MiB 정수"""
    s = str(s).strip()
    if s.endswith("Ki"):
        return int(s[:-2]) // 1024
    if s.endswith("Mi"):
        return int(s[:-2])
    if s.endswith("Gi"):
        return int(float(s[:-2]) * 1024)
    if s.endswith("Ti"):
        return int(float(s[:-2]) * 1024 * 1024)
    if s.endswith("K") or s.endswith("k"):
        return int(s[:-1]) // 1000
    return int(s) // (1024 * 1024)


@app.get("/api/admin/k8s/overview")
def admin_k8s_overview():
    try:
        from kubernetes import client, config
        config.load_incluster_config()
    except Exception as e:
        return jsonify({"error": f"k8s config: {e}"}), 503

    v1     = client.CoreV1Api()
    custom = client.CustomObjectsApi()

    # ── 노드 목록 ──────────────────────────────────────────────────────────
    nodes_raw = v1.list_node().items

    # ── 노드 메트릭 ────────────────────────────────────────────────────────
    try:
        nm_items = custom.list_cluster_custom_object("metrics.k8s.io", "v1beta1", "nodes")["items"]
        node_metrics = {m["metadata"]["name"]: m["usage"] for m in nm_items}
    except Exception:
        node_metrics = {}

    # ── 전체 파드 목록 ─────────────────────────────────────────────────────
    pods_raw = v1.list_pod_for_all_namespaces().items

    # ── 파드 메트릭 (네임스페이스별 수집) ──────────────────────────────────
    pod_metrics = {}
    namespaces = list({p.metadata.namespace for p in pods_raw if p.metadata.namespace})
    for ns in namespaces:
        try:
            pm_items = custom.list_namespaced_custom_object(
                "metrics.k8s.io", "v1beta1", ns, "pods")["items"]
            for pm in pm_items:
                name = pm["metadata"]["name"]
                total_cpu = sum(_cpu_to_m(c["usage"]["cpu"])      for c in pm["containers"])
                total_mem = sum(_mem_to_mib(c["usage"]["memory"]) for c in pm["containers"])
                pod_metrics[f"{ns}/{name}"] = {"cpu_m": total_cpu, "mem_mib": total_mem}
        except Exception:
            pass

    # ── 노드별 파드 분류 ───────────────────────────────────────────────────
    pods_by_node: dict[str, list] = {}
    for pod in pods_raw:
        node_name = pod.spec.node_name or "__unscheduled__"
        key = f"{pod.metadata.namespace}/{pod.metadata.name}"
        pm  = pod_metrics.get(key, {})

        # 재시작 횟수 합산
        restarts = 0
        if pod.status.container_statuses:
            for cs in pod.status.container_statuses:
                restarts += cs.restart_count or 0

        # 컨테이너 이미지 (짧게)
        images = []
        for c in (pod.spec.containers or []):
            img = c.image or ""
            images.append(img.split("/")[-1] if "/" in img else img)

        import datetime
        age_min = 0
        if pod.metadata.creation_timestamp:
            delta = datetime.datetime.now(datetime.timezone.utc) - pod.metadata.creation_timestamp
            age_min = int(delta.total_seconds() // 60)

        pod_info = {
            "name":       pod.metadata.name,
            "namespace":  pod.metadata.namespace,
            "status":     pod.status.phase or "Unknown",
            "ip":         pod.status.pod_ip or "",
            "node":       node_name,
            "images":     images,
            "cpu_m":      pm.get("cpu_m", 0),
            "mem_mib":    pm.get("mem_mib", 0),
            "restarts":   restarts,
            "age_min":    age_min,
        }
        pods_by_node.setdefault(node_name, []).append(pod_info)

    # ── 노드 정보 조합 ─────────────────────────────────────────────────────
    nodes = []
    total_cpu_cap = 0
    total_mem_cap = 0
    total_cpu_use = 0
    total_mem_use = 0

    for node in nodes_raw:
        n_name = node.metadata.name
        labels = node.metadata.labels or {}

        cap     = node.status.capacity or {}
        alloc   = node.status.allocatable or {}
        cpu_cap = _cpu_to_m(cap.get("cpu", "0"))
        mem_cap = _mem_to_mib(cap.get("memory", "0"))

        nm      = node_metrics.get(n_name, {})
        cpu_use = _cpu_to_m(nm.get("cpu", "0m"))
        mem_use = _mem_to_mib(nm.get("memory", "0Mi"))

        conditions = {c.type: c.status for c in (node.status.conditions or [])}

        nodes.append({
            "name":          n_name,
            "short_name":    n_name.split(".")[0],
            "status":        "Ready" if conditions.get("Ready") == "True" else "NotReady",
            "instance_type": labels.get("node.kubernetes.io/instance-type", "unknown"),
            "os_image":      (node.status.node_info.os_image if node.status.node_info else ""),
            "kernel":        (node.status.node_info.kernel_version if node.status.node_info else ""),
            "cpu_cap_m":     cpu_cap,
            "mem_cap_mib":   mem_cap,
            "cpu_use_m":     cpu_use,
            "mem_use_mib":   mem_use,
            "cpu_pct":       round(cpu_use / cpu_cap * 100, 1) if cpu_cap else 0,
            "mem_pct":       round(mem_use / mem_cap * 100, 1) if mem_cap else 0,
            "pod_count":     len(pods_by_node.get(n_name, [])),
            "pods":          sorted(pods_by_node.get(n_name, []),
                                    key=lambda p: p["namespace"] + p["name"]),
        })

        total_cpu_cap += cpu_cap
        total_mem_cap += mem_cap
        total_cpu_use += cpu_use
        total_mem_use += mem_use

    import datetime
    return jsonify({
        "nodes":   nodes,
        "cluster": {
            "total_nodes":   len(nodes),
            "total_pods":    sum(len(v) for v in pods_by_node.values()),
            "cpu_cap_m":     total_cpu_cap,
            "mem_cap_mib":   total_mem_cap,
            "cpu_use_m":     total_cpu_use,
            "mem_use_mib":   total_mem_use,
            "cpu_pct":       round(total_cpu_use / total_cpu_cap * 100, 1) if total_cpu_cap else 0,
            "mem_pct":       round(total_mem_use / total_mem_cap * 100, 1) if total_mem_cap else 0,
            "fetched_at":    datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8200, debug=False)
