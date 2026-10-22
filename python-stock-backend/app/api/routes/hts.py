"""HTS 시뮬레이션(/hts.html) 보조 엔드포인트.

/api/hts/recommendations — lumina-invest(fd.edumgt.co.kr) quant-dashboard 의 「대표 강력 매수 시그널」을 그대로 가져온다.
  - 상류: fd `GET /api/stocks/universe/candidates?limit=N` (로그인 불필요, 2026-10-22 실측). fd 에는 CORS 설정이 없어
    브라우저가 직접 부르지 못하므로 이 서버가 대신 읽고, 60초 캐시한다.
  - 선별 규칙은 fd quant.js 와 동일: indicators[symbol].signal.action == "강력 매수" 인 후보만, 상류 순서(점수·거래대금) 유지.
  - 응답에는 상류 URL 을 싣지 않고 종목 식별자·시그널 요약만 돌려준다.
"""
from __future__ import annotations

from threading import Lock
from time import monotonic

import requests
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.core.config import get_settings

router = APIRouter(prefix="/api/hts", tags=["hts"])

SOURCE = "lumina-invest quant-dashboard (fd.edumgt.co.kr)"
_CACHE_SECONDS = 60
_UPSTREAM_TIMEOUT = 10
_cache: dict[str, tuple[float, dict]] = {}
_lock = Lock()


def _code6(symbol: str) -> str:
    """'005930.KS' → '005930'. 6자리 코드가 아니면 빈 문자열."""
    code = str(symbol or "").split(".")[0].strip()
    return code if len(code) == 6 and code.isalnum() else ""


def _shape(payload: dict, limit: int) -> dict:
    indicators = payload.get("indicators") or {}
    picks = []
    for stock in payload.get("stocks") or []:
        symbol = str(stock.get("symbol") or "")
        indicator = indicators.get(symbol) or {}
        signal = indicator.get("signal") or {}
        if signal.get("action") != "강력 매수":
            continue
        code = _code6(symbol) or _code6(stock.get("code") or "")
        if not code:
            continue
        rsi = indicator.get("rsi")
        picks.append({
            "symbol": code,
            "yahooSymbol": symbol if "." in symbol else f"{code}.KS",
            "name": stock.get("name") or code,
            "market": stock.get("market") or "",
            "sector": stock.get("sector") or "",
            "signal": signal.get("action"),
            "score": signal.get("score"),
            "reasons": [str(r) for r in (signal.get("reasons") or [])][:4],
            "rsi": rsi[-1] if isinstance(rsi, list) and rsi else rsi,
            "asOf": indicator.get("as_of"),
            "marketCapEok": stock.get("market_cap_eok"),
            "kisOrderAllowed": stock.get("kis_order_allowed"),
        })
        if len(picks) >= limit:
            break
    policy = payload.get("signal_policy") or {}
    return {
        "ok": True,
        "source": SOURCE,
        "updatedAt": payload.get("updated_at"),
        "strongBuyThreshold": policy.get("strong_buy_threshold", 3),
        "method": policy.get("method"),
        "stocks": picks,
    }


def fetch_recommendations(limit: int) -> dict:
    """상류 호출 + 정형화. 실패 시 requests.RequestException 또는 ValueError."""
    base = get_settings().lumina_invest_base_url.rstrip("/")
    # 강력 매수가 아닌 후보가 섞여 오므로 넉넉히 받아 거른다(상류 최대 200).
    upstream_limit = max(limit * 2, 10)
    response = requests.get(f"{base}/api/stocks/universe/candidates", params={"limit": min(upstream_limit, 200)},
                            timeout=_UPSTREAM_TIMEOUT, headers={"Accept": "application/json"})
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or "stocks" not in payload:
        raise ValueError("상류 응답 형식이 예상과 다릅니다.")
    return _shape(payload, limit)


@router.get("/recommendations")
def recommendations(limit: int = Query(10, ge=1, le=40)):
    key = f"reco:{limit}"
    now = monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
    try:
        data = fetch_recommendations(limit)
    except requests.RequestException:
        return JSONResponse({"ok": False, "source": SOURCE, "message": "fd 강력매수 추천 서버에 연결하지 못했습니다. 잠시 후 다시 시도하세요."},
                            status_code=503)
    except ValueError as exc:
        return JSONResponse({"ok": False, "source": SOURCE, "message": str(exc)}, status_code=502)
    with _lock:
        _cache[key] = (now + _CACHE_SECONDS, data)
    return data
