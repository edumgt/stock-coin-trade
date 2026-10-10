"""자연어 명령 라우터 평가 (evals/jev_intent).

    PYTHONPATH=src:python-stock-backend python -m deskjev.eval --mode oracle                 # 오프라인, 무료
    PYTHONPATH=src:python-stock-backend TYPESAFE_API_KEY=... python -m deskjev.eval --mode live --max-usd 1

- oracle: 정답을 확률 0.99로 돌려주는 가짜 모델. 채점이 100%가 아니면 채점기나 사례가 틀린 것이다.
- live: 실제 Jev. --max-usd가 없으면 거부하고, 다음 호출이 상한을 넘을 수 있으면 멈춘다.

채점은 코드로만 한다. 화면은 정답 또는 허용 대안(screen_alt)이면 맞고, 화면이 쓰는 인자
(주식·코인·전략, deskjev.intent.USES)는 정답 화면을 맞힌 경우에만 비교한다.
- nav_ok: 잘못 보내지 않았다(화면이 맞고, 실은 인자가 모두 맞다). 확신이 없어 뺀 인자는 틀린 것이 아니다.
- full_ok: 인자까지 모두 채웠다.
임계값 표는 "confidence ≥ t일 때 바로 이동" 규칙의 자동 처리 비율과 그 안의 잘못된 이동(nav_ok 아님) 비율이다.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from deskagent import pricing
from deskjev import intent

EVAL_DIR = Path(__file__).resolve().parents[2] / "evals" / "jev_intent"
THRESHOLDS = (0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.98)


def load_cases(path: Path = EVAL_DIR / "cases.jsonl") -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class OracleClient:
    """정답을 돌려주는 가짜 Jev. 채점기 자체를 검증한다."""

    def __init__(self, cases: list[dict]):
        self.by_text = {case["text"]: case for case in cases}

    def system_one(self, state, questions, *, model):
        case = self.by_text[state["user_command"]]

        def answer(value):
            value = value or intent.NONE
            return SimpleNamespace(choice=value, confidence=0.99, probabilities={value: 0.99, "__other": 0.01})

        answers = {name: answer(case[name]) for name in ("screen", "stock", "coin", "strategy")}
        return SimpleNamespace(answers=answers, usage=SimpleNamespace(input_tokens=0))


def grade(case: dict, got: intent.Intent) -> dict:
    """사례 하나를 채점한다: nav_ok(잘못 보내지 않음)와 full_ok(인자까지 모두 채움)."""
    screen_ok = got.screen in {case["screen"], *case.get("screen_alt", [])}
    names = intent.USES.get(case["screen"], ()) if got.screen == case["screen"] else ()
    wrong = [n for n in names if getattr(got, n) is not None and getattr(got, n) != case[n]]
    missing = [n for n in names if getattr(got, n) is None and case[n] is not None]
    nav_ok = screen_ok and not wrong
    return {"screen_ok": screen_ok, "nav_ok": nav_ok, "full_ok": nav_ok and not missing}


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    if not n:  # --max-usd가 첫 호출 비용보다 작으면 한 건도 돌지 않는다
        return {"cases": 0, "input_tokens": 0}
    thresholds = []
    for t in THRESHOLDS:
        auto = [r for r in rows if r["confidence"] >= t and r["screen"] != intent.NONE]
        wrong = sum(not r["nav_ok"] for r in auto)
        thresholds.append(
            {
                "t": t,
                "auto_share": round(len(auto) / n, 3),
                "errors": wrong,
                "error_rate": round(wrong / len(auto), 3) if auto else 0.0,
            }
        )
    bins = []
    for lo, hi in ((0.0, 0.5), (0.5, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 0.95), (0.95, 1.01)):
        members = [r for r in rows if lo <= r["confidence"] < hi]
        if members:
            bins.append(
                {
                    "range": f"{lo:.2f}-{min(hi, 1):.2f}",
                    "n": len(members),
                    "mean_confidence": round(statistics.mean(r["confidence"] for r in members), 3),
                    "accuracy": round(statistics.mean(r["nav_ok"] for r in members), 3),
                }
            )
    ece = sum(b["n"] / n * abs(b["mean_confidence"] - b["accuracy"]) for b in bins)
    latencies = sorted(r["ms"] for r in rows)
    return {
        "cases": n,
        "screen_accuracy": round(statistics.mean(r["screen_ok"] for r in rows), 3),
        "nav_accuracy": round(statistics.mean(r["nav_ok"] for r in rows), 3),
        "full_accuracy": round(statistics.mean(r["full_ok"] for r in rows), 3),
        "actions": {a: sum(r["action"] == a for r in rows) for a in ("go", "suggest", "help")},
        "go_errors": [r["id"] for r in rows if r["action"] == "go" and not r["nav_ok"]],
        "go_missing_args": [r["id"] for r in rows if r["action"] == "go" and r["nav_ok"] and not r["full_ok"]],
        "thresholds": thresholds,
        "calibration": bins,
        "ece": round(ece, 3),
        # nearest-rank 백분위수: 정렬된 값의 ceil(p·n)번째
        "latency_ms": {"p50": latencies[math.ceil(0.5 * n) - 1], "p95": latencies[math.ceil(0.95 * n) - 1]},
        "input_tokens": sum(r["input_tokens"] for r in rows),
    }


def run(client, cases: list[dict], candidates, max_usd: float | None = None) -> list[dict]:
    rows, spent = [], 0.0
    for case in cases:
        if max_usd is not None and spent + 0.001 > max_usd:  # 호출 1건은 $0.0001 미만이지만 여유를 둔다
            print(f"stopping: next call could exceed --max-usd {max_usd}", file=sys.stderr)
            break
        start = time.perf_counter()
        got = intent.route(client, case["text"], *candidates)
        ms = round((time.perf_counter() - start) * 1000)
        if max_usd is not None:  # 상한이 있을 때만 쌓는다. 단가가 없으면 KeyError로 멈춘다
            spent += pricing.cost_usd(intent.MODEL, pricing.Usage(input_tokens=got.input_tokens))
        rows.append(
            {
                "id": case["id"],
                "text": case["text"],
                "gold": case["screen"],
                "screen": got.screen,
                "stock": got.stock,
                "coin": got.coin,
                "strategy": got.strategy,
                "confidence": got.confidence,
                "action": got.action,
                "ms": ms,
                "input_tokens": got.input_tokens,
                **grade(case, got),
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Jev intent routing eval")
    parser.add_argument("--mode", choices=("oracle", "live"), required=True)
    parser.add_argument("--max-usd", type=float, default=0.0, help="live only: spend cap")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    cases = load_cases()
    from intent import candidates  # python-stock-backend/intent.py: 서비스와 같은 후보

    if args.mode == "live":
        if args.max_usd <= 0:
            parser.error("--mode live needs --max-usd (the spend cap Noah approved)")
        pricing.cost_usd(intent.MODEL, pricing.Usage())  # 단가가 없으면 과금 호출 전에 멈춘다
        from typesafe_sdk import TypeSafeClient

        client = TypeSafeClient()
    else:
        client = OracleClient(cases)
    rows = run(client, cases, candidates(), args.max_usd if args.mode == "live" else None)
    summary = summarize(rows)
    usage = pricing.Usage(input_tokens=summary["input_tokens"])
    cost = pricing.cost_usd_or_none(intent.MODEL, usage)  # 비공개 단가가 없는 환경은 None(미확인)
    summary["cost_usd"] = round(cost, 6) if cost is not None else None
    summary.update(mode=args.mode, model=intent.MODEL, run_at=datetime.now(UTC).isoformat(timespec="seconds"))
    out = args.out or EVAL_DIR / "results" / f"{args.mode}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
