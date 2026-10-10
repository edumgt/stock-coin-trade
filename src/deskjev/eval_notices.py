"""빗썸 공지 레이더 평가 (evals/jev_notices).

    PYTHONPATH=src:python-stock-backend python -m deskjev.eval_notices --mode rules    # 규칙만, 무료
    PYTHONPATH=src:python-stock-backend python -m deskjev.eval_notices --mode oracle   # 정답을 주는 가짜 Jev, 무료
    PYTHONPATH=src:python-stock-backend TYPESAFE_API_KEY=... python -m deskjev.eval_notices --mode live --max-usd 1

세 정책을 같은 사례로 비교한다. oracle·live는 사례마다 Jev를 한 번만 부르고 그 답을 두 정책이 함께 쓴다.
- rules: 규칙 → 못 정하면 폴백(위험 분류의 공지는 종류 불명 경고)
- jev: 모든 공지를 Jev가 판정(티커는 코드가 제목에서 뽑는다)
- rules+jev: 규칙 → 못 정한 공지만 Jev (서비스가 쓰는 정책)
oracle은 정답을 확률 0.99로 돌려준다. jev 정책이 100%가 아니면 채점기나 라벨이 틀린 것이다.
채점은 코드로만 한다. 위험 재현율·정밀도·오경보율, 맞게 잡은 위험의 종류·대상 코인 정확도,
Jev가 판정한 공지의 위험 확률 보정(ECE), 지연, 비용.
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
from deskjev import notices
from deskjev.eval import load_cases

EVAL_DIR = Path(__file__).resolve().parents[2] / "evals" / "jev_notices"
# 라벨의 기준 시각. "(09/25 재개)"처럼 날짜로 끝나는 중단은 이 시각을 기준으로 끝났는지 본다.
REF_NOW = datetime(2026, 9, 26, 9, 0, tzinfo=notices.KST)
THRESHOLDS = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
POLICIES = ("rules", "jev", "rules+jev")


class OracleClient:
    """정답(kind·coins)을 Jev 답 모양으로 돌려주는 가짜 Jev."""

    def __init__(self, cases: list[dict]):
        self.by_title = {case["title"]: case for case in cases}

    def system_one(self, state, questions, *, model):
        case = self.by_title[state["title"]]
        coins = case["coins"]
        if coins == "ALL":
            scope = "all"
        elif coins == "UNKNOWN":
            scope = "none"
        else:
            scope = "network" if notices._NETWORK.search(case["title"]) else "coins"

        def answer(value):
            return SimpleNamespace(choice=value, confidence=0.99, probabilities={value: 0.99, "__other": 0.01})

        answers = {"kind": answer(case["kind"]), "scope": answer(scope)}
        return SimpleNamespace(answers=answers, usage=SimpleNamespace(input_tokens=0))


def grade(case: dict, verdict: notices.Verdict) -> dict:
    """사례 하나: 위험 판단이 맞았는지, 맞게 잡은 위험이면 종류와 대상 코인까지 맞았는지.

    @param case 라벨이 달린 사례
    @param verdict 정책이 낸 판정
    @returns risk·risk_ok·kind_ok·coins_ok
    """
    caught = case["risk"] and verdict.risk
    return {
        "risk": verdict.risk,
        "risk_ok": verdict.risk == case["risk"],
        "kind_ok": caught and verdict.kind == case["kind"],
        "coins_ok": caught and verdict.coins == case["coins"],
    }


def _pct(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[math.ceil(p * len(ordered)) - 1]  # nearest-rank


def _ece(rows: list[dict]) -> tuple[float | None, list[dict]]:
    """Jev가 판정한 행에서 위험 확률과 실제 위험 비율의 차이(구간 가중 평균)."""
    if not rows:
        return None, []
    bins = []
    for lo, hi in ((0.0, 0.1), (0.1, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.01)):
        members = [r for r in rows if lo <= r["p_risk"] < hi]
        if members:
            bins.append(
                {
                    "range": f"{lo:.1f}-{min(hi, 1):.1f}",
                    "n": len(members),
                    "mean_p_risk": round(statistics.mean(r["p_risk"] for r in members), 3),
                    "risk_rate": round(statistics.mean(r["gold_risk"] for r in members), 3),
                }
            )
    ece = sum(b["n"] / len(rows) * abs(b["mean_p_risk"] - b["risk_rate"]) for b in bins)
    return round(ece, 3), bins


def policy_summary(rows: list[dict], policy: str) -> dict:
    """정책 하나의 지표.

    @param rows run()의 행(정책별 판정은 row["p"][policy])
    @param policy rules | jev | rules+jev
    @returns 재현율·정밀도·오경보율·종류/코인 정확도·ECE·지연 등
    """
    graded = [{**r, **r["p"][policy]} for r in rows]
    positives = [r for r in graded if r["gold_risk"]]
    negatives = [r for r in graded if not r["gold_risk"]]
    alerted = [r for r in graded if r["risk"]]
    caught = [r for r in positives if r["risk"]]
    used_jev = [r for r in graded if r["by"] == "jev"]
    ece, bins = _ece(used_jev)
    latencies = [r["ms"] if r["by"] == "jev" else 0 for r in graded]  # 규칙 판정은 호출이 없다
    return {
        "cases": len(graded),
        "risk_recall": round(len(caught) / len(positives), 3) if positives else None,
        "precision": round(len(caught) / len(alerted), 3) if alerted else None,
        "false_alarm_rate": round(sum(r["risk"] for r in negatives) / len(negatives), 3) if negatives else None,
        "kind_accuracy": round(statistics.mean(r["kind_ok"] for r in caught), 3) if caught else None,
        "coins_accuracy": round(statistics.mean(r["coins_ok"] for r in caught), 3) if caught else None,
        "missed": [r["id"] for r in positives if not r["risk"]],
        "false_alarms": [r["id"] for r in negatives if r["risk"]],
        "jev_share": round(len(used_jev) / len(graded), 3),
        "ece": ece,
        "calibration": bins,
        "latency_ms": {"p50": _pct(latencies, 0.5), "p95": _pct(latencies, 0.95)} if latencies else None,
    }


def threshold_table(rows: list[dict], policy: str) -> list[dict]:
    """RISK_MIN을 바꿨을 때 재현율·오경보율. Jev 답은 그대로 두고, 규칙 판정은 임계값과 무관하다."""
    table = []
    for t in THRESHOLDS:
        flags = [
            (r["p"][policy]["p_risk"] >= t) if r["p"][policy]["by"] == "jev" else r["p"][policy]["risk"] for r in rows
        ]
        pos = [flag for flag, r in zip(flags, rows, strict=True) if r["gold_risk"]]
        neg = [flag for flag, r in zip(flags, rows, strict=True) if not r["gold_risk"]]
        table.append(
            {
                "t": t,
                "risk_recall": round(sum(pos) / len(pos), 3) if pos else None,
                "false_alarm_rate": round(sum(neg) / len(neg), 3) if neg else None,
            }
        )
    return table


def _entry(case: dict, verdict: notices.Verdict) -> dict:
    judged = {"by": verdict.by, "kind": verdict.kind, "coins": verdict.coins, "p_risk": verdict.probability}
    return {**judged, **grade(case, verdict)}


def run(client, cases: list[dict], max_usd: float | None = None) -> list[dict]:
    """사례마다 규칙을 돌리고, client가 있으면 Jev를 한 번 불러 세 정책의 판정을 모두 적는다.

    @param client 가짜 또는 실제 TypeSafe 클라이언트. None이면 규칙만
    @param cases 라벨이 달린 사례
    @param max_usd live 비용 상한. 다음 호출이 넘을 수 있으면 멈춘다
    @returns 사례별 행
    """
    rows, spent = [], 0.0
    for case in cases:
        if client is not None and max_usd is not None and spent + 0.001 > max_usd:
            print(f"stopping: next call could exceed --max-usd {max_usd}", file=sys.stderr)
            break
        rule = notices.rules(case, REF_NOW)
        row = {
            "id": case["id"],
            "source": case["source"],
            "title": case["title"],
            "gold_risk": case["risk"],
            "gold_kind": case["kind"],
            "gold_coins": case["coins"],
            "ms": 0,
            "input_tokens": 0,
            "p": {"rules": _entry(case, rule or notices.fallback(case))},
        }
        if client is not None:
            start = time.perf_counter()
            answers, tokens = notices.ask(client, case)
            row["ms"] = round((time.perf_counter() - start) * 1000)
            row["input_tokens"] = tokens
            if max_usd is not None:  # 상한이 있을 때만 쌓는다. 단가가 없으면 KeyError로 멈춘다
                spent += pricing.cost_usd(notices.MODEL, pricing.Usage(input_tokens=tokens))
            jev = notices.decide(answers, case, tokens)
            row["p"]["jev"] = _entry(case, jev)
            row["p"]["rules+jev"] = _entry(case, rule or jev)
        rows.append(row)
    return rows


def notices_per_day(cases: list[dict]) -> float | None:
    """실제 공지의 게시 간격으로 하루 공지 수를 어림한다(최신 20건뿐이라 대략값)."""
    stamps = sorted(datetime.strptime(c["published_at"], "%Y-%m-%d %H:%M:%S") for c in cases if c["source"] == "real")
    if len(stamps) < 2:
        return None
    days = (stamps[-1] - stamps[0]).total_seconds() / 86400
    return round((len(stamps) - 1) / days, 2) if days > 0 else None


def summarize(rows: list[dict], cases: list[dict]) -> dict:
    """정책별 지표, 실제 공지만의 지표, 임계값 표, 비용 어림을 묶는다.

    @param rows run()의 행
    @param cases 전체 사례(하루 공지 수 어림에 쓴다)
    @returns 요약
    """
    policies = [p for p in POLICIES if rows and p in rows[0]["p"]]
    calls = [r for r in rows if "jev" in r["p"]]
    tokens = sum(r["input_tokens"] for r in calls)
    cost = pricing.cost_usd_or_none(notices.MODEL, pricing.Usage(input_tokens=tokens))  # 단가가 없으면 None(미확인)
    per_call = cost / len(calls) if calls and cost is not None else None
    per_day = notices_per_day(cases)
    real = [r for r in rows if r["source"] == "real"]
    summary = {
        "cases": len(rows),
        "risk_cases": sum(r["gold_risk"] for r in rows),
        "risk_min": notices.RISK_MIN,
        "ref_now": REF_NOW.isoformat(),
        "policies": {p: policy_summary(rows, p) for p in policies},
        "real_only": {p: policy_summary(real, p) for p in policies} if real else {},
        "thresholds": {p: threshold_table(rows, p) for p in policies if p != "rules"},
        "jev_calls": len(calls),
        "input_tokens": tokens,
        "cost_usd": round(cost, 6) if cost is not None else None,
        "cost_per_call_usd": round(per_call, 7) if per_call is not None else None,
        "jev_call_latency_ms": (
            {"p50": _pct([r["ms"] for r in calls], 0.5), "p95": _pct([r["ms"] for r in calls], 0.95)} if calls else None
        ),
        "notices_per_day_estimate": per_day,
    }
    if per_call is not None and per_day:
        # 하루 공지 수 × 30 × Jev에 가는 비율(실제 공지 기준) × 호출당 비용. 같은 제목은 캐시되므로 상한에 가깝다.
        for p in ("jev", "rules+jev"):
            share = (summary["real_only"] or summary["policies"])[p]["jev_share"]
            summary["policies"][p]["monthly_usd_estimate"] = round(per_day * 30 * share * per_call, 5)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bithumb notice radar eval")
    parser.add_argument("--mode", choices=("rules", "oracle", "live"), required=True)
    parser.add_argument("--max-usd", type=float, default=0.0, help="live only: spend cap")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    cases = load_cases(EVAL_DIR / "cases.jsonl")
    client = None
    if args.mode == "live":
        if args.max_usd <= 0:
            parser.error("--mode live needs --max-usd (the spend cap Noah approved)")
        pricing.cost_usd(notices.MODEL, pricing.Usage())  # 단가가 없으면 과금 호출 전에 멈춘다
        from typesafe_sdk import TypeSafeClient

        client = TypeSafeClient()
    elif args.mode == "oracle":
        client = OracleClient(cases)
    rows = run(client, cases, args.max_usd if args.mode == "live" else None)
    summary = summarize(rows, cases)
    summary.update(mode=args.mode, model=notices.MODEL, run_at=datetime.now(UTC).isoformat(timespec="seconds"))
    out = args.out or EVAL_DIR / "results" / f"{args.mode}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    brief = {p: {k: v for k, v in s.items() if k != "calibration"} for p, s in summary["policies"].items()}
    print(json.dumps(brief, ensure_ascii=False, indent=1))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
