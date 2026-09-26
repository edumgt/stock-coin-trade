#!/usr/bin/env python3
"""curriculum/*.md 를 각 증권사 학습(실전연습) HTML 페이지에 삽입한다.

    python3 scripts/embed_curriculum.py          # 삽입/갱신
    python3 scripts/embed_curriculum.py --check  # 변경 없이 대상만 출력

- 외부 패키지 없이 이 저장소의 markdown 부분집합(제목, 표, 목록, 코드 블록,
  인용, 인라인 코드/굵게/링크)만 변환한다.
- 결과는 <!-- curriculum:start --> ... <!-- curriculum:end --> 마커로 감싸며
  다시 실행하면 마커 안만 교체되므로 md 수정 후 재실행하면 된다.
- 삽입용 CSS 는 cur- 접두사 클래스만 사용해 페이지별 기존 스타일과 충돌하지 않는다.
- `../경로` 형태의 저장소 상대 링크는 GitHub blob 링크로 바꾼다.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRICULUM = ROOT / "curriculum"
LEARNING = ROOT / "frontend" / "learning"
GITHUB_BLOB = "https://github.com/edumgt/stock-coin-trade/blob/main/"

# (curriculum 파일, 라벨, 대상 페이지들, 기본으로 접어 둘 ## 절 제목 접두어)
TARGETS = [
    ("01.md", "KIS TESTBED", ["kis-test.html"]),
    ("02.md", "KB OPEN API", ["kb-securities.html"]),
    ("03.md", "ALPACA PAPER", ["alpaca-api.html"]),
    ("04.md", "BINANCE · KORBIT", ["binance-api.html", "korbit-api.html"]),
]
COLLAPSED_PREFIXES = ("준비·설정 상세",)

START = "<!-- curriculum:start -->"
END = "<!-- curriculum:end -->"
STYLE_ID = "curriculum-embed-style"

CSS = """<style id="curriculum-embed-style">
.cur-card{margin-top:18px;padding:24px;border:1px solid var(--border);border-radius:14px;background:var(--surface);box-shadow:var(--shadow-sm)}
.cur-kicker{font-size:12px;font-weight:900;letter-spacing:.09em;color:var(--accent-dark)}
.cur-title{margin:0 0 6px;font-size:23px;font-weight:900;color:var(--fg)}
.cur-desc{margin:0 0 4px;color:var(--fg-2);font-size:14px;line-height:1.75}
.cur-sec{margin-top:14px;border:1px solid var(--border);border-radius:10px;background:var(--surface-2)}
.cur-sec>summary{cursor:pointer;list-style:none;padding:13px 16px;font-size:16px;font-weight:900;color:var(--fg)}
.cur-sec>summary::-webkit-details-marker{display:none}
.cur-sec>summary::before{content:"▸";display:inline-block;width:16px;color:var(--accent)}
.cur-sec[open]>summary::before{content:"▾"}
.cur-body{padding:2px 16px 16px;color:var(--fg-2);font-size:13.5px;line-height:1.75}
.cur-body h4{margin:16px 0 6px;font-size:14.5px;font-weight:900;color:var(--fg)}
.cur-body p{margin:8px 0}
.cur-body ul,.cur-body ol{margin:6px 0 8px 22px;padding:0}
.cur-body ul{list-style:disc}
.cur-body ol{list-style:decimal}
.cur-body li::marker{color:var(--accent-dark)}
.cur-body li{margin:3px 0}
.cur-body code{padding:1px 5px;border-radius:5px;background:rgba(15,23,42,.06);font:12px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:var(--fg)}
.cur-body a{color:var(--accent-dark);text-decoration:underline;text-underline-offset:2px;word-break:break-all}
.cur-code{margin:10px 0;padding:14px 16px;border-radius:10px;overflow:auto;background:#131722;color:#D1D4DC;font:12px/1.65 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;white-space:pre}
.cur-code code{padding:0;background:none;color:inherit;font:inherit}
.cur-quote{margin:10px 0;padding:12px 14px;border-radius:9px;background:#FFF8E8;color:#854D0E;font-size:13px;line-height:1.7}
.cur-quote p{margin:0}
.cur-table-wrap{overflow:auto;margin:10px 0}
.cur-table{width:100%;min-width:640px;border-collapse:collapse;font-size:12.5px;background:var(--surface)}
.cur-table th,.cur-table td{padding:9px 10px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top;line-height:1.55}
.cur-table th{background:var(--surface-2);color:var(--muted);font-size:11px;white-space:nowrap}
.cur-hr{border:0;border-top:1px solid var(--border);margin:14px 0}
.cur-foot{margin-top:12px;font-size:12px;color:var(--muted)}
@media(max-width:700px){.cur-card{padding:16px}.cur-body{padding:2px 12px 12px}}
</style>"""


# ---------------------------------------------------------------- inline


def _link(href: str, text: str) -> str:
    if href.startswith("../"):
        href = GITHUB_BLOB + href[3:]
    ext = href.startswith("http")
    extra = ' target="_blank" rel="noopener noreferrer"' if ext else ""
    return f'<a href="{html.escape(href, quote=True)}"{extra}>{text}</a>'


def inline(text: str) -> str:
    """인라인 markdown -> HTML. 코드 스팬은 먼저 떼어 두고 나머지만 변환한다."""
    codes: list[str] = []

    def stash(m: re.Match) -> str:
        codes.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", stash, text)
    text = html.escape(text, quote=False)
    text = re.sub(r"&lt;(https?://[^&\s]+)&gt;", lambda m: _link(m.group(1), m.group(1)), text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: _link(m.group(2), m.group(1)), text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)
    return text


# ---------------------------------------------------------------- blocks


def _table(rows: list[str]) -> str:
    def cells(line: str) -> list[str]:
        return [c.strip() for c in line.strip().strip("|").split("|")]

    head = cells(rows[0])
    body = [cells(r) for r in rows[2:]]
    out = ['<div class="cur-table-wrap"><table class="cur-table"><thead><tr>']
    out += [f"<th>{inline(c)}</th>" for c in head]
    out.append("</tr></thead><tbody>")
    for r in body:
        out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def _code(lines: list[str]) -> str:
    return f'<pre class="cur-code"><code>{html.escape(chr(10).join(lines))}</code></pre>'


def render_blocks(lines: list[str]) -> str:
    """## 절 내부(### 포함)를 HTML 로 변환한다."""
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        # 코드 블록 (들여쓰기된 펜스 포함)
        m = re.match(r"^(\s*)```", line)
        if m:
            indent = len(m.group(1))
            buf: list[str] = []
            i += 1
            while i < n and not re.match(r"^\s*```", lines[i]):
                buf.append(lines[i][indent:] if lines[i][:indent].strip() == "" else lines[i].strip())
                i += 1
            i += 1
            block = _code(buf)
            # 목록 항목 바로 뒤의 들여쓴 코드 블록은 그 항목 안에 넣는다.
            if indent and out and out[-1].endswith("</li>") and out[-1].startswith("<li"):
                out[-1] = out[-1][:-5] + block + "</li>"
            else:
                out.append(block)
            continue
        if stripped.startswith("### "):
            out.append(f"<h4>{inline(stripped[4:])}</h4>")
            i += 1
            continue
        if stripped == "---":
            out.append('<hr class="cur-hr">')
            i += 1
            continue
        if stripped.startswith("|"):
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(lines[i])
                i += 1
            out.append(_table(rows))
            continue
        if stripped.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            out.append(f'<div class="cur-quote"><p>{inline(" ".join(buf))}</p></div>')
            continue
        m = re.match(r"^(\s*)(?:[-*]|\d+\.)\s+", line)
        if m:
            ordered = bool(re.match(r"^\s*\d+\.", line))
            tag = "ol" if ordered else "ul"
            items: list[str] = []
            while i < n:
                lm = re.match(r"^(\s*)(?:[-*]|\d+\.)\s+(.*)$", lines[i])
                if not lm:
                    break
                items.append(f"<li>{inline(lm.group(2))}</li>")
                i += 1
                # 항목 뒤에 들여쓴 코드 펜스가 오면 항목에 붙인다.
                if i < n and re.match(r"^\s+```", lines[i]):
                    im = re.match(r"^(\s*)```", lines[i])
                    indent = len(im.group(1))
                    buf = []
                    i += 1
                    while i < n and not re.match(r"^\s*```", lines[i]):
                        buf.append(lines[i][indent:] if lines[i][:indent].strip() == "" else lines[i].strip())
                        i += 1
                    i += 1
                    items[-1] = items[-1][:-5] + _code(buf) + "</li>"
            out.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue
        # 문단: 빈 줄 전까지 이어 붙인다.
        buf = []
        while i < n and lines[i].strip() and not re.match(r"^(\s*```|\s*#{1,3} |\s*\||\s*>|\s*(?:[-*]|\d+\.)\s|---$)", lines[i]):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            out.append(f"<p>{inline(' '.join(buf))}</p>")
        else:
            i += 1
    return "".join(out)


# ---------------------------------------------------------------- document


def render_doc(md: str, label: str, source: str) -> str:
    lines = md.splitlines()
    title = ""
    sections: list[tuple[str, list[str]]] = []
    cur_title: str | None = None
    cur_lines: list[str] = []
    in_code = False
    for line in lines:
        if re.match(r"^\s*```", line):
            in_code = not in_code
        if not in_code and line.startswith("# ") and not title:
            title = line[2:].strip()
            continue
        if not in_code and line.startswith("## "):
            if cur_title is not None:
                sections.append((cur_title, cur_lines))
            cur_title, cur_lines = line[3:].strip(), []
            continue
        cur_lines.append(line)
    if cur_title is not None:
        sections.append((cur_title, cur_lines))

    parts = [
        START,
        CSS,
        '<section class="cur-card" id="curriculum">',
        f'<div class="cur-kicker">CURRICULUM · {html.escape(label)} 실전연습 과정표</div>',
        f'<h2 class="cur-title">{inline(title)}</h2>',
        '<p class="cur-desc">아래 과정표는 저장소의 <code>curriculum/</code> 문서와 같은 내용입니다. 절 제목을 누르면 접거나 펼 수 있습니다.</p>',
    ]
    for sec_title, sec_lines in sections:
        opened = "" if sec_title.startswith(COLLAPSED_PREFIXES) else " open"
        parts.append(f'<details class="cur-sec"{opened}><summary>{inline(sec_title)}</summary>')
        parts.append(f'<div class="cur-body">{render_blocks(sec_lines)}</div></details>')
    parts.append(f'<div class="cur-foot">원본: {_link("../" + source, "curriculum/" + source)} · <code>scripts/embed_curriculum.py</code>로 다시 생성합니다.</div>')
    parts.append("</section>")
    parts.append(END)
    return "\n".join(parts)


def embed(page: Path, block: str) -> bool:
    s = page.read_text(encoding="utf-8")
    # 이전 블록은 위치와 무관하게 제거한 뒤 항상 </main> 안쪽 끝에 넣는다.
    # (학습 페이지는 body 가 overflow:hidden 이고 main 만 스크롤되므로 main 밖에
    #  두면 main 높이가 줄어 페이지 전체가 스크롤되지 않는다.)
    if START in s and END in s:
        a, z = s.index(START), s.index(END) + len(END)
        s_wo = s[:a].rstrip(" ") + s[z:].lstrip("\n")
    else:
        s_wo = s
    idx = s_wo.rfind("</main>")
    if idx == -1:
        raise SystemExit(f"{page.name}: </main> 을 찾지 못했습니다.")
    new = s_wo[:idx].rstrip() + "\n" + block + "\n" + s_wo[idx:]
    if new != s:
        page.write_text(new, encoding="utf-8")
        return True
    return False


def main() -> None:
    check = "--check" in sys.argv
    for md_name, label, pages in TARGETS:
        md = (CURRICULUM / md_name).read_text(encoding="utf-8")
        block = render_doc(md, label, md_name)
        for page_name in pages:
            page = LEARNING / page_name
            if check:
                print(f"{md_name} -> {page.relative_to(ROOT)}")
                continue
            changed = embed(page, block)
            print(f"{md_name} -> {page.relative_to(ROOT)}: {'updated' if changed else 'unchanged'} ({len(block):,} chars)")


if __name__ == "__main__":
    main()
