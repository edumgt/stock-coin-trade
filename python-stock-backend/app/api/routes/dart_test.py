"""DART(금융감독원 전자공시) 읽기 전용 학습 엔드포인트. 업스트림 URL·인증키는 응답에 싣지 않는다.

OpenDART 규약(lumina-invest app/services/dart.py 2026-10-12 실측):
  - 응답은 HTTP 200 이고 성공·실패는 본문 `status` 로 온다(`000` 정상 · `010/011` 키 오류 · `013` 자료 없음 ·
    `020` 한도 초과 · `800` 점검).
  - 종목코드 → 고유번호(corp_code) 매핑은 `corpCode.xml` 이 ZIP 으로 내려온다. 풀어서 프로세스 메모리에 30일 캐시.
"""
import io
import os
import re
import zipfile
from datetime import datetime, timedelta, timezone
from threading import Lock
from time import monotonic
from xml.etree import ElementTree

import requests
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/dart-test", tags=["dart-test"])
_BASE = "https://opendart.fss.or.kr/api/"
_SOURCE = "금융감독원 전자공시(OpenDART)"
_CACHE_SECONDS = 60
_CORP_TTL = 30 * 24 * 3600
_cache = {}
_corp_cache = {"ts": 0.0, "map": {}, "names": {}}
_lock = Lock()

REPRT_CODES = {"11013": "1분기보고서", "11012": "반기보고서", "11014": "3분기보고서", "11011": "사업보고서"}
_STATUS_MESSAGES = {
    "010": "서버 DART_API_KEY 가 등록되지 않은 키입니다.",
    "011": "서버 DART_API_KEY 가 사용할 수 없는 키입니다. 발급 상태를 확인하세요.",
    "012": "접근할 수 없는 IP 입니다. DART 마이페이지의 IP 설정을 확인하세요.",
    "013": "조회된 자료가 없습니다. 종목코드·사업연도·보고서 구분을 확인하세요.",
    "014": "파일이 존재하지 않습니다.",
    "020": "DART 일일 요청 한도를 초과했습니다. 내일 다시 시도하세요.",
    "021": "조회 가능한 회사 개수를 초과했습니다.",
    "100": "요청 파라미터가 잘못되었습니다.",
    "101": "부적절한 접근입니다.",
    "800": "DART 시스템 점검 중입니다. 잠시 후 다시 시도하세요.",
}


def _api_key() -> str:
    for name in ("DART_API_KEY", "OPEN_DART_API_KEY", "OPENDART_API_KEY"):
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _error(message: str, status_code: int = 502):
    return JSONResponse({"ok": False, "message": message}, status_code=status_code)


def _dart_status_error(status: str, message: str):
    text = _STATUS_MESSAGES.get(status, "DART 응답 오류입니다. 잠시 후 다시 시도하세요.")
    if status in ("010", "011", "012"):
        return _error(text, 503)
    if status in ("013", "100"):
        return _error(text, 404 if status == "013" else 400)
    if status in ("020", "021", "800"):
        return _error(text, 503)
    return _error(text, 502)


def _get(path: str, key: str, **params):
    return requests.get(_BASE + path, params={"crtfc_key": key, **params}, timeout=(5, 20))


def _corp_map(key: str) -> tuple[dict, dict] | JSONResponse:
    """종목코드(6자리) → corp_code, corp_code → 회사명. ZIP 을 풀어 만들고 30일 캐시한다."""
    with _lock:
        if _corp_cache["map"] and monotonic() - _corp_cache["ts"] < _CORP_TTL:
            return _corp_cache["map"], _corp_cache["names"]
    response = _get("corpCode.xml", key)
    head = response.content[:300].decode("utf-8", "replace")
    if "<status>" in head and "<status>000</status>" not in head:
        status = re.search(r"<status>(\d+)</status>", head)
        return _dart_status_error(status.group(1) if status else "900", "")
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        xml = zf.read(zf.namelist()[0])
    mapping, names = {}, {}
    for item in ElementTree.fromstring(xml).iter("list"):
        stock = (item.findtext("stock_code") or "").strip()
        corp = (item.findtext("corp_code") or "").strip()
        if stock and corp and re.fullmatch(r"\d{6}", stock):
            mapping[stock] = corp
            names[corp] = (item.findtext("corp_name") or "").strip()
    if not mapping:
        return _error("DART 고유번호 목록이 비어 있습니다.", 503)
    with _lock:
        _corp_cache.update(ts=monotonic(), map=mapping, names=names)
    return mapping, names


def _resolve(stock_code: str, key: str):
    """우선주(끝자리 0 이 아님)는 보통주 코드로 회사를 찾는다. (corp_code, 조회에 쓴 코드, 우선주 여부, 회사명)."""
    resolved = _corp_map(key)
    if isinstance(resolved, JSONResponse):
        return resolved
    mapping, names = resolved
    code, preferred = stock_code, False
    if code not in mapping and code[-1] != "0" and mapping.get(code[:5] + "0"):
        code, preferred = code[:5] + "0", True
    corp = mapping.get(code)
    if not corp:
        return _error("DART 에 등록되지 않은 종목코드입니다. 상장사 6자리 코드를 확인하세요.", 404)
    return corp, code, preferred, names.get(corp, "")


def _run(kind: str, stock_code: str, builder):
    key = _api_key()
    if not key:
        return _error("서버에 DART_API_KEY가 설정되지 않았습니다.", 503)
    cache_key = (kind, stock_code, builder.__name__)
    with _lock:
        cached = _cache.get(cache_key)
        if cached and monotonic() - cached[0] < _CACHE_SECONDS:
            return cached[1]
    try:
        resolved = _resolve(stock_code, key)
        if isinstance(resolved, JSONResponse):
            return resolved
        corp, code, preferred, corp_name = resolved
        result = {"source": _SOURCE, "stock_code": stock_code, "resolved_stock_code": code, "is_preferred": preferred,
                  "corp_name": corp_name, "fetched_at": datetime.now(timezone.utc).isoformat(), "cached_for_seconds": _CACHE_SECONDS}
        outcome = builder(key, corp, result)
        if isinstance(outcome, JSONResponse):
            return outcome
        payload = {"ok": True, "result": outcome}
        with _lock:
            if len(_cache) >= 128:
                _cache.clear()
            _cache[cache_key] = (monotonic(), payload)
        return payload
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError, zipfile.BadZipFile, ElementTree.ParseError):
        return _error("DART 응답을 가져오지 못했습니다. 잠시 후 다시 시도하세요.", 503)


def _json(path: str, key: str, **params):
    response = _get(path, key, **params)
    if response.status_code != 200:
        return _error("DART 서비스에 연결할 수 없습니다. 잠시 후 다시 시도하세요.", 503 if response.status_code == 429 else 502)
    body = response.json()
    status = str(body.get("status") or "")
    if status != "000":
        return _dart_status_error(status, str(body.get("message") or ""))
    return body


def _company(key, corp, result):
    body = _json("company.json", key, corp_code=corp)
    if isinstance(body, JSONResponse):
        return body
    fields = ("corp_name", "corp_name_eng", "stock_name", "stock_code", "ceo_nm", "corp_cls", "jurir_no", "bizr_no",
              "adres", "hm_url", "ir_url", "phn_no", "fax_no", "induty_code", "est_dt", "acc_mt")
    company = {name: body.get(name) for name in fields}
    company["corp_cls_name"] = {"Y": "유가증권(KOSPI)", "K": "코스닥", "N": "코넥스", "E": "기타"}.get(company.get("corp_cls"), company.get("corp_cls"))
    result.update(company=company, status="complete")
    return result


def _disclosures(key, corp, result, days=90, limit=20):
    today = datetime.now(timezone(timedelta(hours=9)))
    body = _json("list.json", key, corp_code=corp, bgn_de=(today - timedelta(days=days)).strftime("%Y%m%d"),
                 end_de=today.strftime("%Y%m%d"), page_no=1, page_count=limit)
    if isinstance(body, JSONResponse):
        return body
    rows = []
    for row in body.get("list") or []:
        row = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}  # report_nm 은 뒤에 공백이 붙어 온다(실측)
        rows.append({"rcept_no": row.get("rcept_no"), "rcept_dt": row.get("rcept_dt"), "report_nm": row.get("report_nm"),
                     "flr_nm": row.get("flr_nm"), "corp_name": row.get("corp_name"), "rm": row.get("rm"),
                     "viewer_url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + str(row.get("rcept_no") or "")})
    result.update(disclosures=rows, total_count=int(body.get("total_count") or 0), window_days=days,
                  latest=rows[0] if rows else None, status="complete" if rows else "partial")
    return result


def _financials(key, corp, result, year=None, reprt_code="11011"):
    today = datetime.now(timezone(timedelta(hours=9)))
    year = year or today.year - 1
    for fs_div in ("CFS", "OFS"):
        body = _json("fnlttSinglAcnt.json", key, corp_code=corp, bsns_year=str(year), reprt_code=reprt_code)
        if isinstance(body, JSONResponse):
            return body
        rows = [r for r in body.get("list") or [] if r.get("fs_div") == fs_div]
        if rows:
            break
    if not rows:
        return _error("해당 연도·보고서의 재무제표가 없습니다. 사업연도나 보고서 구분을 바꿔 보세요.", 404)
    accounts = []
    for row in rows:
        accounts.append({"sj_div": row.get("sj_div"), "sj_nm": row.get("sj_nm"), "account_nm": row.get("account_nm"),
                         "thstrm_nm": row.get("thstrm_nm"), "thstrm_amount": _amount(row.get("thstrm_amount")),
                         "frmtrm_nm": row.get("frmtrm_nm"), "frmtrm_amount": _amount(row.get("frmtrm_amount")),
                         "currency": row.get("currency")})
    summary = {}
    for name, keys in (("assets", ("자산총계",)), ("liabilities", ("부채총계",)), ("equity", ("자본총계",)),
                       ("revenue", ("매출액", "수익(매출액)", "영업수익")), ("operating_income", ("영업이익", "영업이익(손실)", "영업손실")),
                       ("net_income", ("당기순이익", "당기순이익(손실)", "당기순손실"))):
        for row in accounts:
            if row["account_nm"] and row["account_nm"].replace(" ", "") in keys and (name in ("revenue", "operating_income", "net_income") or row["sj_div"] == "BS"):
                summary[name] = row["thstrm_amount"]
                break
        summary.setdefault(name, None)
    result.update(bsns_year=year, reprt_code=reprt_code, report_name=REPRT_CODES.get(reprt_code, reprt_code),
                  fs_div="연결" if fs_div == "CFS" else "별도", accounts=accounts, summary=summary,
                  status="complete" if all(v is not None for v in summary.values()) else "partial")
    return result


def _amount(value):
    text = str(value or "").replace(",", "").strip()
    if not text or text == "-":
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    try:
        number = int(text)
    except ValueError:
        return None
    return -number if negative else number


_CODE = Query("005930", pattern=r"^\d{6}$")


@router.get("/company")
def company(stock_code: str = _CODE):
    return _run("company", stock_code, _company)


@router.get("/disclosures")
def disclosures(stock_code: str = _CODE, days: int = Query(90, ge=1, le=365), limit: int = Query(20, ge=1, le=100)):
    def builder(key, corp, result):
        return _disclosures(key, corp, result, days, limit)
    builder.__name__ = f"disclosures:{days}:{limit}"
    return _run("disclosures", stock_code, builder)


@router.get("/financials")
def financials(stock_code: str = _CODE, bsns_year: int | None = Query(None, ge=2015, le=2100),
               reprt_code: str = Query("11011", pattern=r"^(11011|11012|11013|11014)$")):
    def builder(key, corp, result):
        return _financials(key, corp, result, bsns_year, reprt_code)
    builder.__name__ = f"financials:{bsns_year}:{reprt_code}"
    return _run("financials", stock_code, builder)
