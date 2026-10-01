"""KRX 보도자료(open.krx.co.kr) 목록 조회와 5분 캐시."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta

import requests

_KRX_API = "https://open.krx.co.kr/contents/OPN/99/OPN99000001.jspx"
_KRX_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Referer": "https://open.krx.co.kr/contents/OPN/05/05000000/OPN05000000T1.jsp",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}
_KRX_FILE_BASE = "https://file.krx.co.kr"
_KRX_PAGE_URL = "https://open.krx.co.kr/contents/OPN/05/05000000/OPN05000000.jsp"

_news_cache: dict = {"ts": 0.0, "data": None}
_news_lock = threading.Lock()
NEWS_TTL = 300  # 5분


def _krx_pdf_url(noti_no: str) -> str:
    # noti_no = YYYYMMDDNN  →  file = YYYYMMDD0000NN2.pdf
    date = noti_no[:8]
    serial = noti_no[8:]
    return f"{_KRX_FILE_BASE}/obk/dyn/noti/{date}0000{serial}2.pdf"


def cached_news() -> dict | None:
    with _news_lock:
        if _news_cache["data"] and time.time() - _news_cache["ts"] < NEWS_TTL:
            return _news_cache["data"]
    return None


def fetch_news() -> dict:
    """KRX에서 최근 1년 보도자료 20건을 가져와 캐시한다. 네트워크 오류는 호출자가 처리한다."""
    today = datetime.now().strftime("%Y%m%d")
    one_year = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    resp = requests.post(_KRX_API, headers=_KRX_HEADERS, data={
        "bld": "OPN/05/05000000/opn05000000t1_01",
        "pagePath": "/contents/OPN/05/05000000/OPN05000000T1.jsp",
        "pageSize": "20",
        "sch_tp": "title",
        "sch_word": "",
        "fromdate": one_year,
        "todate": today,
    }, timeout=10)
    items = resp.json().get("output", [])

    news = []
    for a in items:
        noti_no = a.get("noti_no", "")
        news.append({
            "noti_no": noti_no,
            "title": a.get("title", ""),
            "date": a.get("creat_ddtm", ""),
            "view_cnt": a.get("inq_cnt", "0"),
            "pdf_url": _krx_pdf_url(noti_no) if len(noti_no) == 10 else None,
            "page_url": _KRX_PAGE_URL,
        })
    result = {"news": news, "total": items[0].get("totCnt", "0") if items else "0"}
    with _news_lock:
        _news_cache.update({"ts": time.time(), "data": result})
    return result
