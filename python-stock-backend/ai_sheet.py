"""URL content to editable spreadsheet data, and sector stock-price sheets.

The crawler deliberately accepts only public HTTP(S) endpoints.  It is not a
general purpose proxy: local/private addresses and non-HTML responses are
rejected to keep this endpoint safe to expose to browsers.
"""
import ipaddress
import json
import os
import random
import re
import shutil
import socket
import subprocess
import threading
from datetime import datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests
from flask import Blueprint, jsonify, request

import stock_market

MONTH_LABEL_RE = re.compile(r"^\d{4}-\d{2}$")


ai_sheet_bp = Blueprint("ai_sheet", __name__, url_prefix="/api/ai-sheet")
MAX_BYTES = 2_000_000
MAX_ROWS = 100
MAX_COLUMNS = 20

SECTOR_SHEET_STOCK_LIMIT = 20
SECTOR_SHEET_MONTHS = 24

LEAN_IMAGE_TAG = "stock-coin-trade-lean:latest"
LEAN_BUILD_CONTEXT = "/lean-src"
LEAN_DATA_DIR = "/lean-data"
LEAN_RESULTS_DIR = "/lean-results"
LEAN_DATA_VOLUME = "lean-data"
LEAN_RESULTS_VOLUME = "lean-results"
LEAN_TIMEOUT_SECONDS = 180
_lean_lock = threading.Lock()  # 테스트용 버튼이므로 named volume을 공유하는 실행을 한 번에 하나로 제한한다.


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


def _parse_number(value):
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return number if number == number else None  # filter out NaN


def _fmt_number(value):
    return "" if value is None else f"{round(value):,.0f}"


@ai_sheet_bp.post("/quant-analyze")
def quant_analyze():
    """M-2까지의 월별 종가로 scikit-learn LinearRegression을 학습해 M-1을 예측하고,
    실제 M-1 값과 나란히 보여준다. 교육용 빠른 검증이 목적이며 CPU에서 즉시 끝나는
    가벼운 모델만 사용한다."""
    body = request.get_json(silent=True) or {}
    columns = body.get("columns") or []
    rows = body.get("rows") or []
    if len(columns) < 5 or not MONTH_LABEL_RE.match(str(columns[1])):
        return jsonify({"message": '퀀트분석은 "섹터별 월별 종가" 시트(yyyy-mm 칼럼)에서만 사용할 수 있습니다.'}), 400

    month_columns = columns[1:]
    n = len(month_columns)
    idx_m1, idx_m2 = n - 2, n - 3
    m1_label = month_columns[idx_m1]
    pred_label, actual_label = f"M-1 예측({m1_label})", f"M-1 실제({m1_label})"

    from sklearn.linear_model import LinearRegression

    new_rows = []
    for row in rows:
        name = row[0] if row else ""
        series = [_parse_number(row[1 + i]) if 1 + i < len(row) else None for i in range(n)]
        train_x = [[i] for i in range(idx_m2 + 1) if series[i] is not None]
        train_y = [series[i] for i in range(idx_m2 + 1) if series[i] is not None]

        predicted = None
        if len(train_x) >= 2:
            predicted = float(LinearRegression().fit(train_x, train_y).predict([[idx_m1]])[0])
        elif len(train_x) == 1:
            predicted = train_y[0]

        new_rows.append([name, _fmt_number(predicted), _fmt_number(series[idx_m1]), *[_fmt_number(v) for v in series]])

    return jsonify({
        "columns": [columns[0], pred_label, actual_label, *month_columns],
        "rows": new_rows,
        "notice": f"{m1_label} 기준 M-2까지의 월별 종가로 scikit-learn LinearRegression을 학습해 예측했습니다. "
                  "빠른 테스트용 지표이며 투자 판단에 그대로 사용하지 마세요.",
    })


def _month_series_offset(columns: list) -> int:
    """M-1 예측/실제 등 앞에 끼워 넣은 칼럼을 건너뛰고 yyyy-mm 칼럼이 시작되는 인덱스를 찾는다."""
    for index in range(1, len(columns)):
        if MONTH_LABEL_RE.match(str(columns[index])):
            return index
    return len(columns)


def _run_docker(args: list, timeout: int):
    """docker-py의 images.build()/containers.wait()가 이 환경의 BuildKit 스트림과
    맞지 않아 요청이 무한 대기하는 문제가 있어, 검증된 `docker` CLI를 서브프로세스로
    직접 호출한다(호스트 데몬은 /var/run/docker.sock 마운트로 접근)."""
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)


def _ensure_lean_image():
    check = _run_docker(["image", "inspect", LEAN_IMAGE_TAG], timeout=10)
    if check.returncode == 0:
        return
    build = _run_docker(["build", "-t", LEAN_IMAGE_TAG, LEAN_BUILD_CONTEXT], timeout=120)
    if build.returncode != 0:
        raise RuntimeError(f"LEAN 이미지 빌드 실패: {build.stderr[-800:]}")


@ai_sheet_bp.post("/lean-backtest")
def lean_backtest():
    """AI Sheet의 월별 종가 한 종목을 QuantConnect LEAN(Docker, quantconnect/lean 엔진)의
    매수 후 보유 전략으로 빠르게 백테스트한다. 교육용 테스트 버튼이므로 named volume을
    잠금(threading.Lock)으로 직렬화해 한 번에 한 실행만 허용한다."""
    body = request.get_json(silent=True) or {}
    columns = body.get("columns") or []
    rows = body.get("rows") or []
    row_index = body.get("rowIndex") or 0

    offset = _month_series_offset(columns)
    month_columns = columns[offset:]
    if len(month_columns) < 2 or not MONTH_LABEL_RE.match(str(columns[offset] if offset < len(columns) else "")):
        return jsonify({"message": '퀀트분석과 마찬가지로 "섹터별 월별 종가" 시트(yyyy-mm 칼럼)에서만 사용할 수 있습니다.'}), 400
    if not isinstance(row_index, int) or row_index < 0 or row_index >= len(rows):
        return jsonify({"message": "백테스트할 종목 행을 찾을 수 없습니다."}), 400

    row = rows[row_index]
    name = (row[0] if row else "") or "SHEET"
    points = []
    for i, label in enumerate(month_columns):
        value = _parse_number(row[offset + i]) if offset + i < len(row) else None
        if value is not None and value > 0:
            points.append((f"{label}-01", value))
    if len(points) < 2:
        return jsonify({"message": "백테스트에 사용할 유효한 월별 종가가 2개월 미만입니다."}), 422

    with _lean_lock:
        try:
            for stale_dir in (LEAN_DATA_DIR, LEAN_RESULTS_DIR):
                for entry in os.listdir(stale_dir):
                    path = os.path.join(stale_dir, entry)
                    (os.remove if os.path.isfile(path) else shutil.rmtree)(path)
            with open(os.path.join(LEAN_DATA_DIR, "prices.csv"), "w") as handle:
                handle.write("Date,Open,High,Low,Close,Volume\n")
                for iso_date, price in points:
                    handle.write(f"{iso_date},{price},{price},{price},{price},0\n")

            _ensure_lean_image()
            run = _run_docker([
                "run", "--rm",
                "-e", f"SYMBOL_NAME={name}",
                "-v", f"{LEAN_DATA_VOLUME}:/custom-data",
                "-v", f"{LEAN_RESULTS_VOLUME}:/results",
                LEAN_IMAGE_TAG,
            ], timeout=LEAN_TIMEOUT_SECONDS)

            summary_path = os.path.join(LEAN_RESULTS_DIR, "GenericBuyAndHold-summary.json")
            if not os.path.exists(summary_path):
                return jsonify({"message": "LEAN 백테스트가 요약 결과를 생성하지 못했습니다.",
                                 "log": (run.stdout + run.stderr)[-2000:]}), 502
            with open(summary_path) as handle:
                statistics = (json.load(handle) or {}).get("statistics") or {}
        except subprocess.TimeoutExpired:
            return jsonify({"message": f"LEAN 백테스트가 {LEAN_TIMEOUT_SECONDS}초 안에 끝나지 않았습니다."}), 504
        except Exception as exc:
            return jsonify({"message": f"LEAN 백테스트 실행에 실패했습니다: {exc}"}), 502

    keys = ["Start Equity", "End Equity", "Net Profit", "Compounding Annual Return",
            "Sharpe Ratio", "Drawdown", "Total Orders"]
    return jsonify({
        "stock": name,
        "startDate": points[0][0],
        "endDate": points[-1][0],
        "statistics": {key: statistics[key] for key in keys if key in statistics},
        "notice": f'"{name}" 종목의 월별 종가로 QuantConnect LEAN(Docker) 매수 후 보유 백테스트를 실행했습니다. '
                  "테스트용 결과이며 투자 판단에 사용하지 마세요.",
    })
