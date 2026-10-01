import ast
import html
import random
import re
import threading
import time
from datetime import datetime, timedelta

import requests
import yfinance as yf

STOCKS = {
    # KOSPI
    "005930": {"name": "삼성전자",          "market": "KOSPI",  "ticker": "005930.KS", "sector": "반도체·IT"},
    "000660": {"name": "SK하이닉스",         "market": "KOSPI",  "ticker": "000660.KS", "sector": "반도체·IT"},
    "005380": {"name": "현대차",             "market": "KOSPI",  "ticker": "005380.KS", "sector": "자동차"},
    "035420": {"name": "NAVER",             "market": "KOSPI",  "ticker": "035420.KS", "sector": "인터넷·플랫폼"},
    "035720": {"name": "카카오",             "market": "KOSPI",  "ticker": "035720.KS", "sector": "인터넷·플랫폼"},
    "068270": {"name": "셀트리온",           "market": "KOSPI",  "ticker": "068270.KS", "sector": "바이오·헬스케어"},
    "207940": {"name": "삼성바이오로직스",    "market": "KOSPI",  "ticker": "207940.KS", "sector": "바이오·헬스케어"},
    "373220": {"name": "LG에너지솔루션",      "market": "KOSPI",  "ticker": "373220.KS", "sector": "2차전지"},
    "005490": {"name": "POSCO홀딩스",        "market": "KOSPI",  "ticker": "005490.KS", "sector": "철강·소재"},
    # KOSDAQ
    "247540": {"name": "에코프로비엠",        "market": "KOSDAQ", "ticker": "247540.KQ", "sector": "2차전지"},
    "196170": {"name": "알테오젠",           "market": "KOSDAQ", "ticker": "196170.KQ", "sector": "바이오·헬스케어"},
    "091990": {"name": "셀트리온헬스케어",    "market": "KOSDAQ", "ticker": "091990.KQ", "sector": "바이오·헬스케어"},
    "086520": {"name": "에코프로",           "market": "KOSDAQ", "ticker": "086520.KQ", "sector": "2차전지"},
    "263750": {"name": "펄어비스",           "market": "KOSDAQ", "ticker": "263750.KQ", "sector": "게임"},
}

# Base prices used as fallback when yfinance is unavailable
BASE_PRICES = {
    "005930": 74000,  "000660": 178000, "005380": 215000,
    "035420": 185000, "035720": 37000,  "068270": 178000,
    "207940": 780000, "373220": 320000, "005490": 410000,
    "247540": 92000,  "196170": 230000, "091990": 41000,
    "086520": 72000,  "263750": 28000,
}

# 발행주식수(보통주 기준). 실시간 시세와 곱해 시가총액 순위를 계산한다.
# yfinance를 사용할 수 없는 환경에서도 동일한 순위 화면을 제공하기 위한 기준값이다.
SHARES_OUTSTANDING = {
    "005930": 5_919_638_922, "000660": 728_002_365, "005380": 211_531_506,
    "035420":   64_800_000, "035720": 443_866_000, "068270": 217_000_000,
    "207940":   71_174_000, "373220": 234_000_000, "005490":  84_571_230,
    "247540":   97_000_000, "196170":  53_000_000, "091990":  67_000_000,
    "086520":  136_000_000, "263750":  64_000_000,
}

_quote_cache = {}
_chart_cache = {}
_index_cache = {}
_krx_stock_cache = {"ts": 0.0, "data": []}
_krx_stock_lock = threading.Lock()
_dashboard_quote_cache = {"ts": 0.0, "data": {}}
_dashboard_quote_lock = threading.Lock()

QUOTE_TTL = 60
CHART_TTL = 300
INDEX_TTL = 60
KRX_LIST_TTL = 86_400
KRX_LIST_URL = "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download"
NAVER_STOCK_API = "https://m.stock.naver.com/api/stock"
NAVER_CHART_API = "https://api.finance.naver.com/siseJson.naver"
NAVER_REALTIME_API = "https://polling.finance.naver.com/api/realtime"
DASHBOARD_QUOTE_TTL = 30


def _clean_html(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", value)).split())


def _parse_krx_list(raw: bytes) -> list[dict]:
    """KIND가 제공하는 상장법인 목록 HTML/XLS 응답을 종목 메타데이터로 변환한다."""
    page = raw.decode("euc-kr", errors="replace")
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", page, flags=re.IGNORECASE | re.DOTALL)
    result = []
    market_map = {"유가": "KOSPI", "유가증권": "KOSPI", "코스닥": "KOSDAQ", "코넥스": "KONEX"}
    for row in rows[1:]:
        cells = [_clean_html(cell) for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, flags=re.IGNORECASE | re.DOTALL)]
        if len(cells) < 4 or cells[1] not in market_map or not cells[2]:
            continue
        market = market_map[cells[1]]
        symbol = cells[2].upper()
        result.append({
            "symbol": symbol,
            "name": cells[0],
            "market": market,
            "sector": cells[3] or "기타",
            "ticker": f"{symbol}.{ 'KS' if market == 'KOSPI' else 'KQ' }",
        })
    return result


def get_krx_stocks() -> list[dict]:
    """KRX KIND 공식 상장법인 목록을 가져오고 하루 동안 메모리에 보관한다."""
    now = time.time()
    cached = _krx_stock_cache["data"]
    if cached and now - _krx_stock_cache["ts"] < KRX_LIST_TTL:
        return cached
    with _krx_stock_lock:
        cached = _krx_stock_cache["data"]
        if cached and now - _krx_stock_cache["ts"] < KRX_LIST_TTL:
            return cached
        try:
            response = requests.get(KRX_LIST_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            response.raise_for_status()
            stocks = _parse_krx_list(response.content)
            if not stocks:
                raise ValueError("KRX 상장법인 목록이 비어 있습니다.")
            stocks.sort(key=lambda stock: ({"KOSPI": 0, "KOSDAQ": 1, "KONEX": 2}.get(stock["market"], 9), stock["symbol"]))
            _krx_stock_cache.update({"ts": now, "data": stocks})
            return stocks
        except Exception:
            # 이미 받은 목록이 있으면 네트워크 일시 실패에도 검색 기능을 계속 제공한다.
            if cached:
                return cached
            # KIND 다운로드가 차단된 새 컨테이너도 기본 실습 종목과 모의투자 기능을
            # 계속 제공할 수 있도록, 내장된 기준 종목을 최후의 대체 목록으로 쓴다.
            fallback_stocks = [
                {"symbol": symbol, **info}
                for symbol, info in STOCKS.items()
            ]
            fallback_stocks.sort(key=lambda stock: (
                {"KOSPI": 0, "KOSDAQ": 1, "KONEX": 2}.get(stock["market"], 9),
                stock["symbol"],
            ))
            _krx_stock_cache.update({"ts": now, "data": fallback_stocks})
            return fallback_stocks


def list_krx_stocks(limit: int = 30, market: str = "") -> list[dict]:
    stocks = get_krx_stocks()
    market = market.upper()
    if market in {"KOSPI", "KOSDAQ", "KONEX"}:
        stocks = [stock for stock in stocks if stock["market"] == market]
    return stocks[:max(1, min(limit, 100))]


def search_krx_stocks(query: str, limit: int = 20) -> list[dict]:
    keyword = (query or "").strip().lower()
    stocks = get_krx_stocks()
    if not keyword:
        return stocks[:max(1, min(limit, 50))]

    starts_with = []
    contains = []
    for stock in stocks:
        values = (stock["name"], stock["symbol"], stock["sector"], stock["market"])
        if not any(keyword in value.lower() for value in values):
            continue
        (starts_with if stock["name"].lower().startswith(keyword) or stock["symbol"].lower().startswith(keyword) else contains).append(stock)
    return (starts_with + contains)[:max(1, min(limit, 50))]


def get_stock_info(symbol: str) -> dict | None:
    symbol = (symbol or "").upper()
    # 기존 실습 종목은 오프라인 시뮬레이션을 위해 보존한다.
    if symbol in STOCKS:
        return {"symbol": symbol, **STOCKS[symbol]}
    return next((stock for stock in get_krx_stocks() if stock["symbol"] == symbol), None)


def _to_number(value, default=0):
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return default


def _fetch_naver_quote(symbol: str, info: dict) -> dict:
    """Yahoo Finance가 차단된 환경을 위한 국내 시세 대체 경로."""
    if not re.fullmatch(r"\d{6}", symbol):
        raise ValueError("숫자 6자리 종목코드만 국내 시세 조회를 지원합니다.")
    response = requests.get(
        f"{NAVER_STOCK_API}/{symbol}/basic",
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://m.stock.naver.com/"},
        timeout=8,
    )
    response.raise_for_status()
    row = response.json()
    price = _to_number(row.get("closePrice"))
    if price <= 0:
        raise ValueError("국내 시세 응답에 현재가가 없습니다.")
    change = _to_number(row.get("compareToPreviousClosePrice"))
    rate = float(str(row.get("fluctuationsRatio", 0)).replace(",", "") or 0)
    if rate < 0 and change > 0:
        change = -change
    prev_close = price - change
    return {
        "symbol": symbol,
        "name": info["name"],
        "market": info["market"],
        "price": price,
        "prevClose": prev_close if prev_close > 0 else price,
        "change": change,
        "changeRate": round(rate, 2),
        "volume": _to_number(row.get("accumulatedTradingVolume")),
    }


def get_dashboard_stock_quotes() -> dict[str, dict]:
    """대시보드용 대표 종목 시세를 단일 국내 다종목 요청으로 가져온다."""
    now = time.time()
    cached = _dashboard_quote_cache["data"]
    if cached and now - _dashboard_quote_cache["ts"] < DASHBOARD_QUOTE_TTL:
        return cached
    with _dashboard_quote_lock:
        cached = _dashboard_quote_cache["data"]
        if cached and now - _dashboard_quote_cache["ts"] < DASHBOARD_QUOTE_TTL:
            return cached
        try:
            symbols = list(STOCKS)
            response = requests.get(
                NAVER_REALTIME_API,
                params={"query": f"SERVICE_ITEM:{','.join(symbols)}"},
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com/"},
                timeout=4,
            )
            response.raise_for_status()
            areas = response.json().get("result", {}).get("areas", [])
            rows = [row for area in areas for row in area.get("datas", [])]
            quotes = {}
            for row in rows:
                symbol = str(row.get("cd", "")).upper()
                info = STOCKS.get(symbol)
                if not info:
                    continue
                price = _to_number(row.get("nv"))
                if price <= 0:
                    continue
                quotes[symbol] = {
                    "symbol": symbol,
                    "name": info["name"],
                    "market": info["market"],
                    "price": price,
                    "prevClose": _to_number(row.get("pcv"), price),
                    "change": _to_number(row.get("cv")),
                    "changeRate": round(float(row.get("cr") or 0), 2),
                    "volume": _to_number(row.get("aq")),
                    "tradeAmount": _to_number(row.get("aa")),
                }
            if not quotes:
                raise ValueError("다종목 시세 응답이 비어 있습니다.")
        except Exception:
            # 네트워크가 일시 실패해도 대시보드는 마지막 결과 또는 기준 가격으로 즉시 표시한다.
            quotes = cached or {
                symbol: {
                    "symbol": symbol, "name": info["name"], "market": info["market"],
                    "price": BASE_PRICES[symbol], "prevClose": BASE_PRICES[symbol],
                    "change": 0, "changeRate": 0, "volume": 0, "tradeAmount": 0,
                }
                for symbol, info in STOCKS.items()
            }
        for symbol, quote in quotes.items():
            _quote_cache[symbol] = {"data": quote, "ts": now}
        _dashboard_quote_cache.update({"ts": now, "data": quotes})
        return quotes


def _fetch_naver_chart(symbol: str, period: str, include_ma: bool = False) -> list[dict]:
    if not re.fullmatch(r"\d{6}", symbol):
        raise ValueError("숫자 6자리 종목코드만 국내 차트 조회를 지원합니다.")
    days = (
        {"1d": 180, "1w": 300, "1m": 300, "3m": 340, "1y": 850}.get(period, 300)
        if include_ma else {"1d": 7, "1w": 14, "1m": 45, "3m": 120, "1y": 380}.get(period, 45)
    )
    end = datetime.now()
    start = end - timedelta(days=days)
    response = requests.get(
        NAVER_CHART_API,
        params={
            "symbol": symbol,
            "requestType": 1,
            "startTime": start.strftime("%Y%m%d"),
            "endTime": end.strftime("%Y%m%d"),
            "timeframe": "day",
        },
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com/"},
        timeout=10,
    )
    response.raise_for_status()
    rows = ast.literal_eval(response.text.strip())
    result = []
    for row in rows[1:]:
        if len(row) < 6:
            continue
        timestamp = datetime.strptime(str(row[0]), "%Y%m%d")
        result.append({
            "x": int(timestamp.timestamp() * 1000),
            "o": _to_number(row[1]),
            "h": _to_number(row[2]),
            "l": _to_number(row[3]),
            "c": _to_number(row[4]),
            "v": _to_number(row[5]),
        })
    if not result:
        raise ValueError("국내 차트 응답에 데이터가 없습니다.")
    return result


def _simulated_price(symbol: str) -> int:
    base = BASE_PRICES.get(symbol, 50000)
    wave = int((time.time() // 10) % 20) - 10
    return max(1000, base + wave * (base // 500))


def get_quote_cached(symbol: str) -> dict:
    symbol = (symbol or "").upper()
    now = time.time()
    cached = _quote_cache.get(symbol)
    if cached and now - cached["ts"] < QUOTE_TTL:
        return cached["data"]

    info = get_stock_info(symbol)
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
        try:
            data = _fetch_naver_quote(symbol, info)
        except Exception as naver_error:
            # 기존 수업용 종목만 최후의 오프라인 시뮬레이션 시세를 제공한다.
            # KRX에서 검색한 종목은 가짜 가격으로 주문되지 않게 막는다.
            if symbol not in STOCKS:
                raise RuntimeError("실시간 KRX 시세를 가져오지 못했습니다. 잠시 후 다시 시도해주세요.") from naver_error
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


def get_chart_cached(symbol: str, period: str, include_ma: bool = False) -> tuple[list, int | None]:
    symbol = (symbol or "").upper()
    now = time.time()
    key = (symbol, period, include_ma)
    cached = _chart_cache.get(key)
    if cached and now - cached["ts"] < CHART_TTL:
        return cached["data"], cached.get("visible_from")

    info = get_stock_info(symbol)
    if not info:
        raise ValueError(f"Unknown symbol: {symbol}")

    period_map   = {"1d": "1d",  "1w": "5d",  "1m": "1mo", "3m": "3mo", "1y": "1y"}
    ma_period_map = {"1d": "5d", "1w": "2mo", "1m": "1y", "3m": "1y", "1y": "3y"}
    interval_map = {"1d": "5m",  "1w": "60m", "1m": "1d",  "3m": "1d",  "1y": "1wk"}
    yf_period   = (ma_period_map if include_ma else period_map).get(period, "1mo")
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
        try:
            ohlcv = _fetch_naver_chart(symbol, period, include_ma)
        except Exception as naver_error:
            if symbol not in STOCKS:
                raise RuntimeError("실시간 KRX 차트 데이터를 가져오지 못했습니다. 잠시 후 다시 시도해주세요.") from naver_error
            # Generate simulated OHLCV when both external providers are unavailable.
            base  = BASE_PRICES.get(symbol, 50000)
            steps = ({"1d": 240, "1w": 160, "1m": 150, "3m": 210, "1y": 172}.get(period, 150)
                     if include_ma else {"1d": 78, "1w": 40, "1m": 30, "3m": 90, "1y": 52}.get(period, 30))
            step_ms = {"1d": 300_000, "1w": 3_600_000, "1m": 86_400_000,
                       "3m": 86_400_000, "1y": 604_800_000}.get(period, 86_400_000)
            ts_ms = int(now * 1000) - steps * step_ms
            price = float(base)
            rng = random.Random(symbol)
            for _ in range(steps):
                o = price
                h = o * (1 + rng.uniform(0, 0.015))
                low = o * (1 - rng.uniform(0, 0.015))
                c = rng.uniform(low, h)
                v = rng.randint(500_000, 5_000_000)
                ohlcv.append({"x": ts_ms, "o": round(o), "h": round(h),
                              "l": round(low), "c": round(c), "v": v})
                price = c
                ts_ms += step_ms

    ohlcv.sort(key=lambda candle: candle["x"])
    visible_bars = {"1d": 78, "1w": 40, "1m": 30, "3m": 90, "1y": 52}.get(period, 30)
    visible_from = ohlcv[max(0, len(ohlcv) - visible_bars)]["x"] if include_ma and ohlcv else None
    _chart_cache[key] = {"data": ohlcv, "visible_from": visible_from, "ts": now}
    return ohlcv, visible_from


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
    symbol = (symbol or "").upper()
    try:
        return get_quote_cached(symbol)["price"]
    except Exception:
        if symbol in STOCKS:
            return _simulated_price(symbol)
        raise


def cached_price(symbol: str) -> int | None:
    """네트워크 요청 없이 마지막으로 확인한 시세만 반환한다."""
    cached = _quote_cache.get((symbol or "").upper())
    if not cached:
        return None
    price = cached.get("data", {}).get("price")
    return int(price) if price else None


def get_market_cap_rankings(limit: int = 10) -> list:
    """등록된 국내 주식을 시가총액(현재가 × 발행주식수) 순으로 반환한다."""
    rankings = []
    quotes = get_dashboard_stock_quotes()
    for symbol, info in STOCKS.items():
        quote = quotes.get(symbol)
        if not quote:
            continue
        market_cap = quote["price"] * SHARES_OUTSTANDING.get(symbol, 0)
        rankings.append({
            "rank":       0,
            "symbol":     symbol,
            "name":       info["name"],
            "market":     info["market"],
            "price":      quote["price"],
            "changeRate": quote.get("changeRate", 0),
            "marketCap":  market_cap,
        })

    rankings.sort(key=lambda stock: stock["marketCap"], reverse=True)
    for rank, stock in enumerate(rankings[:limit], start=1):
        stock["rank"] = rank
    return rankings[:limit]
