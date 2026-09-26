#!/usr/bin/env python3
"""한국투자증권 공식 저장소(open-trading-api)의 examples_llm/domestic_stock 예제를 분석해
웹앱 KIS API 탐색기가 쓰는 카탈로그(python-stock-backend/kis_api_catalog.json)를 만든다.

    git clone --depth 1 https://github.com/koreainvestment/open-trading-api.git mcp/open-trading-api
    python3 scripts/build_kis_api_catalog.py

예제 파일마다 다음을 추출한다.
- 분류·이름·API ID  : "# [국내주식] 주문/계좌 > 주식잔고조회[v1_국내주식-006]" 헤더
- URL, 메서드        : API_URL 상수, postFlag=True 여부(주문성 POST)
- tr_id              : 실전/모의 분기. 모의(demo) 분기가 있으면 Testbed 지원으로 본다.
- 요청 파라미터       : params 딕셔너리 + 함수 인자 설명(docstring Args) + Example 기본값
- 응답 필드 한글명     : chk_*.py 의 COLUMN_MAPPING
저장소는 gitignore 대상(/mcp/)이므로 결과 JSON 만 커밋한다.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mcp" / "open-trading-api" / "examples_llm" / "domestic_stock"
OUT = ROOT / "python-stock-backend" / "kis_api_catalog.json"

# 서버가 .env로 채우는 계좌 파라미터. 브라우저에서 받지 않는다.
SERVER_FILLED = {"CANO", "ACNT_PRDT_CD"}
# 연속조회 키는 탐색기에서 항상 공란(최초 조회)으로 보낸다.
ALWAYS_BLANK = {"CTX_AREA_FK100", "CTX_AREA_NK100", "CTX_AREA_FK200", "CTX_AREA_NK200"}
SKIP_ARGS = {"env_dv", "tr_cont", "dataframe", "dataframe1", "dataframe2", "depth", "max_depth", "FK100", "NK100", "FK200", "NK200"}

HEADER_RE = re.compile(r"^# \[국내주식\]\s*(?P<cat>[^>\-]+?)\s*[>\-]\s*(?P<title>.+?)\s*(?:\[(?P<api>[^\]]+)\])?\s*$", re.M)
URL_RE = re.compile(r'^API_URL\s*=\s*"([^"]+)"', re.M)
ARG_DOC_RE = re.compile(r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\((?P<type>[^)]*)\)\s*:\s*(?P<desc>.+?)\s*$", re.M)
TRID_RE = re.compile(r'tr_id\s*=\s*"([A-Z0-9]+)"')


def parse_signature(src: str, fn: str) -> dict[str, dict]:
    """함수 시그니처의 인자와 인라인 주석, 기본값을 읽는다."""
    m = re.search(rf"def {re.escape(fn)}\((?P<args>.*?)\)\s*->", src, re.S)
    if not m:
        return {}
    out: dict[str, dict] = {}
    for line in m.group("args").splitlines():
        line = line.strip().rstrip(",")
        if not line:
            continue
        code, _, comment = line.partition("#")
        code = code.strip().rstrip(",")
        am = re.match(r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?::[^=]+)?(?:=\s*(?P<default>.+))?$", code)
        if not am:
            continue
        name = am.group("name")
        default = am.group("default")
        default_val = None
        if default is not None:
            try:
                default_val = ast.literal_eval(default.strip())
            except Exception:
                default_val = None
        out[name] = {"comment": comment.strip(), "default": default_val, "optional": default is not None}
    return out


def parse_docstring_args(src: str) -> dict[str, str]:
    m = re.search(r"Args:\s*\n(?P<body>.*?)(?:\n\s*Returns:|\n\s*Example)", src, re.S)
    if not m:
        return {}
    return {d.group("name"): d.group("desc").strip() for d in ARG_DOC_RE.finditer(m.group("body"))}


def parse_example_defaults(src: str, arg_order: list[str]) -> dict[str, str]:
    """Example 의 함수 호출에서 kwargs / 위치 인자 기본값을 읽는다."""
    m = re.search(r">>>\s*(?:[\w, ]+=\s*)?\w+\((?P<call>.*?)\)\s*\n\s*(?:>>>|\.\.\.\s*$)", src, re.S)
    if not m:
        m = re.search(r">>>\s*(?:[\w, ]+=\s*)?\w+\((?P<call>.*?)\)", src, re.S)
    if not m:
        return {}
    call = re.sub(r"\n\s*\.\.\.\s*", " ", m.group("call"))
    try:
        node = ast.parse(f"f({call})", mode="eval").body
    except SyntaxError:
        return {}
    defaults: dict[str, str] = {}
    for i, a in enumerate(node.args):
        if i < len(arg_order) and isinstance(a, ast.Constant):
            defaults[arg_order[i]] = str(a.value)
    for kw in node.keywords:
        if isinstance(kw.value, ast.Constant):
            defaults[kw.arg] = str(kw.value.value)
    return defaults


def parse_tr_ids(src: str) -> tuple[list[str], list[str], dict | None]:
    """(실전 tr_id 목록, 모의 tr_id 목록, 분기 선택자)."""
    real_block = re.search(r'if env_dv == "real":(?P<b>.*?)(?=\n\s*elif env_dv == "demo":|\n\s*else:)', src, re.S)
    demo_block = re.search(r'elif env_dv == "demo":(?P<b>.*?)(?=\n\s*else:)', src, re.S)
    both = re.search(r'if env_dv == "real" or env_dv == "demo":\s*\n\s*tr_id = "([A-Z0-9]+)"', src)
    if both:
        return [both.group(1)], [both.group(1)], None
    if real_block:
        real = TRID_RE.findall(real_block.group("b"))
        demo = TRID_RE.findall(demo_block.group("b")) if demo_block else []
        selector = None
        if demo_block and len(demo) > 1:
            branches = re.findall(r'if (?P<arg>[a-z_]+) == "(?P<val>[^"]+)":\s*\n\s*tr_id = "(?P<tr>[A-Z0-9]+)"', demo_block.group("b"))
            if branches:
                selector = {"arg": branches[0][0], "map": {v: t for _, v, t in branches}}
        return real, demo, selector
    return TRID_RE.findall(src)[:1], [], None


def parse_params(src: str) -> list[tuple[str, str | None, str | None]]:
    """params 딕셔너리 -> [(KEY, 변수명 또는 None, 상수값 또는 None)]."""
    m = re.search(r"params\s*=\s*\{(?P<b>.*?)\n\s*\}", src, re.S)
    items: list[tuple[str, str | None, str | None]] = []
    if m:
        for key, val in re.findall(r'"([A-Za-z0-9_]+)"\s*:\s*([^,\n]+)', m.group("b")):
            val = val.split("#", 1)[0].strip()
            if val.startswith(("'", '"')):
                items.append((key, None, val.strip("'\"")))
            else:
                items.append((key, val, None))
    for key, var in re.findall(r'params\["([A-Z0-9_]+)"\]\s*=\s*([a-z_0-9]+)', src):
        if key not in {k for k, _, _ in items}:
            items.append((key, var, None))
    return items


def parse_column_mapping(chk_src: str) -> dict[str, str]:
    m = re.search(r"COLUMN_MAPPING\s*=\s*\{(?P<b>.*?)\n\}", chk_src, re.S)
    if not m:
        return {}
    return dict(re.findall(r"['\"]([A-Za-z0-9_]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]", m.group("b")))


def build_entry(d: Path) -> dict | None:
    fn = d.name
    src_path = d / f"{fn}.py"
    if not src_path.is_file():
        return None
    src = src_path.read_text(encoding="utf-8")
    headers = list(HEADER_RE.finditer(src))
    h = next((m for m in reversed(headers) if m.group("api")), headers[-1] if headers else None)
    url = URL_RE.search(src)
    if not h or not url:
        return None  # 실시간(WebSocket) 예제 등 REST 가 아닌 것
    sig = parse_signature(src, fn)
    docs = parse_docstring_args(src)
    arg_order = [a for a in sig]
    examples = parse_example_defaults(src, arg_order)
    real_ids, demo_ids, selector = parse_tr_ids(src)
    method = "POST" if "postFlag=True" in src else "GET"
    summary = ""
    dm = re.search(r'"""\s*\n\s*(.+?)\n', src[src.index(f"def {fn}("):], re.S)
    if dm:
        summary = dm.group(1).strip()

    params = []
    for key, var, const in parse_params(src):
        p: dict = {"key": key}
        if key in SERVER_FILLED:
            p.update(source="server", label={"CANO": "종합계좌번호"}.get(key, "계좌상품코드"), desc="서버 .env의 KIS_PAPER_ACCOUNT_NO에서 채웁니다.")
        elif key in ALWAYS_BLANK or var in {"FK100", "NK100", "FK200", "NK200"}:
            p.update(source="blank", label="연속조회 키", desc="탐색기는 최초 조회만 수행하므로 공란으로 보냅니다.")
        elif const is not None:
            p.update(source="fixed", value=const, label=key, desc="예제 고정값")
        elif var:
            info = sig.get(var, {})
            desc = docs.get(var) or info.get("comment") or ""
            required = "[필수]" in desc or (not info.get("optional") and "[필수]" in info.get("comment", ""))
            desc = desc.replace("[필수]", "").strip()
            label = desc.split("(ex.")[0].split("(")[0].strip() or var
            example = ""
            em = re.search(r"\(ex\.\s*(.+)\)\s*$", desc)
            if em:
                example = em.group(1).strip()
            default = examples.get(var)
            if default is None and info.get("default") not in (None, ""):
                default = str(info["default"])
            p.update(source="user", arg=var, label=label, desc=desc, example=example, required=required, default=default or "")
        else:
            p.update(source="fixed", value="", label=key, desc="")
        params.append(p)

    chk = d / f"chk_{fn}.py"
    columns = parse_column_mapping(chk.read_text(encoding="utf-8")) if chk.is_file() else {}
    return {
        "id": fn,
        "category": h.group("cat").strip(),
        "title": h.group("title").strip(),
        "apiId": (h.group("api") or "").strip(),
        "url": url.group(1),
        "method": method,
        "trIdReal": real_ids,
        "trIdDemo": demo_ids,
        "trSelector": selector,
        "demoSupported": bool(demo_ids),
        "summary": summary,
        "params": params,
        "columns": columns,
        "source": f"examples_llm/domestic_stock/{fn}/{fn}.py",
    }


def main() -> None:
    if not SRC.is_dir():
        sys.exit(f"공식 저장소가 없습니다: {SRC}\n  git clone --depth 1 https://github.com/koreainvestment/open-trading-api.git mcp/open-trading-api")
    entries = [e for e in (build_entry(d) for d in sorted(SRC.iterdir()) if d.is_dir()) if e]
    cat_order = ["주문/계좌", "기본시세", "시세분석", "종목정보", "순위분석", "업종/기타", "ELW시세", "국내주식"]
    entries.sort(key=lambda e: (cat_order.index(e["category"]) if e["category"] in cat_order else 99, not e["demoSupported"], e["apiId"], e["id"]))
    demo = [e for e in entries if e["demoSupported"]]
    OUT.write_text(json.dumps({
        "generatedFrom": "https://github.com/koreainvestment/open-trading-api (examples_llm/domestic_stock)",
        "testbedUrl": "https://openapivts.koreainvestment.com:29443",
        "count": len(entries), "demoCount": len(demo),
        "apis": entries,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(entries)} REST APIs ({len(demo)} Testbed-capable) -> {OUT.relative_to(ROOT)}")
    for e in demo:
        print(f"  [{e['category']}] {e['title']} {e['method']} tr={e['trIdDemo']} params={len(e['params'])} cols={len(e['columns'])}")


if __name__ == "__main__":
    main()
