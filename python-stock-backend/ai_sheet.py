"""URL content to editable spreadsheet data, and sector stock-price sheets.

The crawler deliberately accepts only public HTTP(S) endpoints.  It is not a
general purpose proxy: local/private addresses and non-HTML responses are
rejected to keep this endpoint safe to expose to browsers.
"""
import ipaddress
import random
import socket
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests
from flask import Blueprint, jsonify, request

import stock_market


ai_sheet_bp = Blueprint("ai_sheet", __name__, url_prefix="/api/ai-sheet")
MAX_BYTES = 2_000_000
MAX_ROWS = 100
MAX_COLUMNS = 20

SECTOR_SHEET_STOCK_LIMIT = 20
SECTOR_SHEET_MONTHS = 24


def _is_public_url(value):
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    try:
        port = parsed.port
    except ValueError:
        return False
    if parsed.username or parsed.password or (port is not None and port not in (80, 443)):
        return False
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, None)}
        return bool(addresses) and all(ipaddress.ip_address(address).is_global for address in addresses)
    except (socket.gaierror, ValueError):
        return False


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self._table, self._row = [], None, None
        self._cell, self._cell_tag = None, None
        self.title, self._in_title = "", False
        self.paragraphs, self._paragraph = [], None

    def handle_starttag(self, tag, attrs):
        if tag == "title": self._in_title = True
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("th", "td") and self._row is not None:
            self._cell, self._cell_tag = [], tag
        elif tag == "p":
            self._paragraph = []

    def handle_data(self, data):
        if self._in_title: self.title += data
        if self._cell is not None: self._cell.append(data)
        if self._paragraph is not None: self._paragraph.append(data)

    def handle_endtag(self, tag):
        if tag == "title": self._in_title = False
        elif tag in ("th", "td") and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split())[:500])
            self._cell, self._cell_tag = None, None
        elif tag == "tr" and self._row is not None:
            if any(self._row): self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            if self._table: self.tables.append(self._table)
            self._table = None
        elif tag == "p" and self._paragraph is not None:
            text = " ".join("".join(self._paragraph).split())
            if len(text) >= 20: self.paragraphs.append(text[:1000])
            self._paragraph = None


def _to_sheet(parser):
    # Prefer the table with the most populated cells.  A header row becomes
    # spreadsheet columns; otherwise A, B, C ... are generated.
    table = max(parser.tables, key=lambda rows: sum(len(row) for row in rows), default=[])
    if table:
        width = min(MAX_COLUMNS, max(len(row) for row in table))
        first_row = table[0]
        headers = [(first_row[index] if index < len(first_row) and first_row[index] else f"열 {index + 1}")
                   for index in range(width)]
        rows = [[row[index] if index < len(row) else "" for index in range(width)]
                for row in table[1:MAX_ROWS + 1]]
        return headers, rows, "표"
    headers = ["순번", "본문"]
    rows = [[str(index + 1), paragraph] for index, paragraph in enumerate(parser.paragraphs[:MAX_ROWS])]
    return headers, rows, "본문"


@ai_sheet_bp.post("/crawl")
def crawl_to_sheet():
    body = request.get_json(silent=True) or {}
    url = (body.get("url") or "").strip()
    if not _is_public_url(url):
        return jsonify({"message": "공개 HTTP(S) 주소만 입력할 수 있습니다."}), 400
    try:
        with requests.get(url, headers={"User-Agent": "EDUMGT-AISheet/1.0 (+educational)"},
                          timeout=(4, 12), allow_redirects=True, stream=True) as response:
            if not _is_public_url(response.url):
                return jsonify({"message": "안전하지 않은 리디렉션 주소입니다."}), 400
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").lower()
            if "html" not in content_type:
                return jsonify({"message": "HTML 웹페이지만 시트로 가져올 수 있습니다."}), 415
            response.raw.decode_content = True
            payload = response.raw.read(MAX_BYTES + 1)
            if len(payload) > MAX_BYTES:
                return jsonify({"message": "페이지가 너무 큽니다. 2MB 이하의 페이지를 사용해주세요."}), 413
            parser = _TableParser()
            parser.feed(payload.decode(response.encoding or "utf-8", errors="replace"))
            columns, rows, source_type = _to_sheet(parser)
            if not rows:
                return jsonify({"message": "가져올 표 또는 본문을 찾지 못했습니다."}), 422
            return jsonify({"title": " ".join(parser.title.split()) or urlparse(response.url).hostname,
                            "sourceUrl": response.url, "sourceType": source_type,
                            "columns": columns, "rows": rows,
                            "notice": "공개 페이지에서 추출한 결과입니다. 숫자와 원문은 저장 전 확인하세요."})
    except requests.RequestException as exc:
        return jsonify({"message": f"페이지를 가져오지 못했습니다: {exc}"}), 502


def _month_labels(months: int) -> list[str]:
    """가장 오래된 달부터 이번 달까지 'yyyy-mm' 라벨을 만든다."""
    anchor = datetime.utcnow()
    labels = []
    for offset in range(months - 1, -1, -1):
        year, month = anchor.year, anchor.month - offset
        while month <= 0:
            month += 12
            year -= 1
        labels.append(f"{year:04d}-{month:02d}")
    return labels


def _monthly_closes_from_yfinance(ticker: str) -> dict[str, float]:
    import yfinance as yf

    hist = yf.Ticker(ticker).history(period="2y", interval="1mo")
    if hist.empty:
        raise ValueError("empty monthly history")
    return {timestamp.strftime("%Y-%m"): round(float(row["Close"]), 2) for timestamp, row in hist.iterrows()}


def _monthly_closes_simulated(symbol: str, labels: list[str]) -> dict[str, float]:
    """외부 시세를 가져오지 못할 때 종목별로 결정적인(deterministic) 모의 월별 종가를 만든다."""
    base = stock_market.BASE_PRICES.get(symbol, 10_000 + (abs(hash(symbol)) % 490_000))
    rng = random.Random(symbol)
    price = float(base)
    closes = {}
    for label in labels:
        price = max(500.0, price * (1 + rng.uniform(-0.08, 0.09)))
        closes[label] = round(price, 2)
    return closes


@ai_sheet_bp.get("/sectors")
def list_sectors():
    counts: dict[str, int] = {}
    for stock in stock_market.get_krx_stocks():
        sector = stock.get("sector") or "기타"
        if sector == "기타":
            continue
        counts[sector] = counts.get(sector, 0) + 1
    sectors = sorted(
        ({"sector": sector, "count": count} for sector, count in counts.items()),
        key=lambda item: (-item["count"], item["sector"]),
    )
    return jsonify({"sectors": sectors})


@ai_sheet_bp.post("/sector-sheet")
def build_sector_sheet():
    body = request.get_json(silent=True) or {}
    sector = (body.get("sector") or "").strip()
    if not sector:
        return jsonify({"message": "섹터를 선택해주세요."}), 400

    stocks = [stock for stock in stock_market.get_krx_stocks() if stock.get("sector") == sector]
    if not stocks:
        return jsonify({"message": "해당 섹터에 종목이 없습니다."}), 404
    stocks = stocks[:SECTOR_SHEET_STOCK_LIMIT]

    labels = _month_labels(SECTOR_SHEET_MONTHS)
    rows = []
    simulated_count = 0
    for stock in stocks:
        try:
            closes = _monthly_closes_from_yfinance(stock["ticker"])
            if len(closes) < SECTOR_SHEET_MONTHS // 2:
                raise ValueError("insufficient monthly history")
        except Exception:
            closes = _monthly_closes_simulated(stock["symbol"], labels)
            simulated_count += 1
        rows.append([stock["name"]] + [
            (f"{closes[label]:,.0f}" if label in closes else "") for label in labels
        ])

    notice = f"{sector} 섹터 {len(stocks)}개 종목의 최근 {SECTOR_SHEET_MONTHS}개월 월별 종가입니다."
    if simulated_count:
        notice += f" 이 중 {simulated_count}개 종목은 실시간 데이터를 가져오지 못해 모의 값으로 표시했습니다."
    return jsonify({
        "title": f"{sector} 섹터 · 월별 종가",
        "sourceType": "섹터 시세",
        "columns": ["종목명"] + labels,
        "rows": rows,
        "notice": notice,
    })
