"""국내 주식 시세·차트·KRX 뉴스·RAG 지식 검색(공개 API)."""

from __future__ import annotations

import requests
from fastapi import APIRouter, Body, Query

from app.core.errors import ApiError
from app.core.parsing import clamp
from app.services import knowledge_base, krx_news
from app.services.stock_market import (
    BASE_PRICES,
    get_chart_cached,
    get_dashboard_stock_quotes,
    get_index_cached,
    get_market_cap_rankings,
    get_quote_cached,
    get_stock_info,
    list_krx_stocks,
    search_krx_stocks,
)

from ..schemas import QdrantAddBody, QdrantSearchBody

router = APIRouter(prefix="/api/stocks", tags=["market"])


@router.get("/list")
def stock_list(limit: int = Query(30), market: str = Query("")) -> dict:
    try:
        return {"stocks": list_krx_stocks(clamp(limit, 1, 100), market), "source": "KRX"}
    except Exception as exc:
        raise ApiError(503, message=f"KRX 종목 목록을 가져오지 못했습니다: {exc}")


@router.get("/search")
def stock_search(q: str = Query(""), limit: int = Query(20)) -> dict:
    try:
        return {"stocks": search_krx_stocks(q, clamp(limit, 1, 50)), "source": "KRX"}
    except Exception as exc:
        raise ApiError(503, message=f"KRX 종목 검색을 사용할 수 없습니다: {exc}")


@router.get("/market")
def market_indices() -> dict:
    return {"KOSPI": get_index_cached("^KS11"), "KOSDAQ": get_index_cached("^KQ11")}


def _require_symbol(symbol: str) -> str:
    symbol = symbol.upper()
    if not symbol:
        raise ApiError(400, message="symbol is required")
    if not get_stock_info(symbol):
        raise ApiError(404, message=f"지원하지 않는 KRX 종목입니다: {symbol}")
    return symbol


@router.get("/quote")
def quote(symbol: str = Query("")) -> dict:
    symbol = _require_symbol(symbol)
    try:
        return get_quote_cached(symbol)
    except RuntimeError as exc:
        raise ApiError(503, message=str(exc))
    except ValueError as exc:
        raise ApiError(404, message=str(exc))


@router.get("/chart")
def chart(symbol: str = Query(""), period: str = Query("1m"), include_ma: str = Query("")) -> dict:
    symbol = _require_symbol(symbol)
    try:
        ohlcv, visible_from = get_chart_cached(symbol, period, include_ma == "1")
    except RuntimeError as exc:
        raise ApiError(503, message=str(exc))
    except ValueError as exc:
        raise ApiError(404, message=str(exc))
    return {"symbol": symbol, "period": period, "data": ohlcv, "visibleFrom": visible_from}


@router.get("/movers")
def movers() -> dict:
    quotes = [
        {"symbol": q["symbol"], "name": q["name"], "price": q["price"], "changeRate": q.get("changeRate", 0), "market": q["market"]}
        for q in get_dashboard_stock_quotes().values()
    ]
    sorted_q = sorted(quotes, key=lambda x: x.get("changeRate", 0), reverse=True)
    return {"gainers": sorted_q[:3], "losers": sorted_q[-3:][::-1]}


@router.get("/prices")
def batch_prices(symbols: str = Query("")) -> dict:
    """실시간 마켓 리스트용 다종목 시세."""
    requested = [symbol.strip().upper() for symbol in symbols.split(",") if symbol.strip()]
    if not requested:
        return {"prices": get_dashboard_stock_quotes(), "cachedForSeconds": 30}
    result = {}
    for symbol in requested[:50]:
        info = get_stock_info(symbol)
        if not info:
            continue
        try:
            q = get_quote_cached(symbol)
            result[symbol] = {
                "name": q["name"], "market": q["market"], "price": q["price"],
                "change": q.get("change", 0), "changeRate": q.get("changeRate", 0), "volume": q.get("volume", 0),
            }
        except Exception:
            result[symbol] = {
                "name": info["name"], "market": info["market"], "price": BASE_PRICES.get(symbol, 0),
                "change": 0, "changeRate": 0, "volume": 0,
            }
    return {"prices": result}


@router.get("/market-cap-rankings")
def market_cap_rankings() -> dict:
    return {"rankings": get_market_cap_rankings(10)}


# ── Qdrant / RAG ─────────────────────────────────────────────────────────────

@router.post("/ai/qdrant/search")
def qdrant_search(payload: QdrantSearchBody = Body(default_factory=QdrantSearchBody)) -> dict:
    query = str(payload.query or "").strip()
    if not query:
        raise ApiError(400, error="query is required")
    try:
        return {"results": knowledge_base.search(query, clamp(payload.limit, 1, 10))}
    except Exception as exc:
        raise ApiError(503, error=str(exc))


@router.get("/ai/qdrant/stats")
def qdrant_stats() -> dict:
    try:
        return knowledge_base.stats()
    except Exception as exc:
        raise ApiError(503, error=str(exc))


@router.get("/ai/qdrant/list")
def qdrant_list(limit: int = Query(30)) -> dict:
    try:
        return {"documents": knowledge_base.list_docs(clamp(limit, 1, 100))}
    except Exception as exc:
        raise ApiError(503, error=str(exc))


@router.post("/ai/qdrant/add")
def qdrant_add(payload: QdrantAddBody = Body(default_factory=QdrantAddBody)) -> dict:
    text = str(payload.text or "").strip()
    title = str(payload.title or "").strip()
    category = str(payload.category or "custom").strip() or "custom"
    if not text:
        raise ApiError(400, error="text is required")
    if len(text) > 2000:
        raise ApiError(400, error="text too long (max 2000 chars)")
    try:
        return {"id": knowledge_base.add_doc(text, title, category), "status": "added"}
    except Exception as exc:
        raise ApiError(503, error=str(exc))


# ── KRX 보도자료 ─────────────────────────────────────────────────────────────

@router.get("/news/krx")
def news_krx() -> dict:
    cached = krx_news.cached_news()
    if cached:
        return cached
    try:
        return krx_news.fetch_news()
    except (requests.RequestException, ValueError) as exc:
        raise ApiError(503, error=str(exc), news=[])
