"""공시 판정 평가 (evals/jev_disclosures).

    PYTHONPATH=src:python-stock-backend python -m deskjev.eval_disclosures --mode oracle    # 오프라인, 무료
    PYTHONPATH=src:python-stock-backend python -m deskjev.eval_disclosures --mode rules     # 규칙만(Jev 없음)
    PYTHONPATH=src:python-stock-backend TYPESAFE_API_KEY=... python -m deskjev.eval_disclosures --mode live --max-usd 1

- oracle: 정답을 확률 0.99로 돌려주는 가짜 Jev. 100%가 아니면 채점기나 사례가 틀린 것이다.
- rules: Jev를 부르지 않는다. 규칙이 못 정한 유형은 기타, 위험은 낱말로 가른다(서비스의 Jev 장애 폴백과 같다).
- live: 규칙 + 실제 Jev. --max-usd가 없으면 거부하고, 다음 호출이 상한을 넘을 수 있으면 멈춘다.

채점은 코드로만 한다. 유형은 정답 또는 허용 대안(kind_alt)이면 맞다. 위험은 정답(True/False)과 비교한다.
하루 호출 어림은 실측 숫자로 README에 적었다(2026-09-23: 전체 683, 상장사 420, Jev 23).
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
from deskjev import disclosures
from deskjev.eval import load_cases  # 같은 jsonl 읽기

EVAL_DIR = Path(__file__).resolve().parents[2] / "evals" / "jev_disclosures"


class OracleClient:
    """정답을 돌려주는 가짜 Jev. 채점기 자체를 검증한다."""

    def __init__(self, cases: list[dict]):
        self.by_name = {disclosures.normalize(case["report_nm"]): case for case in cases}

    def system_one(self, state, questions, *, model):
        case = self.by_name[state["report_nm"]]
        answers = {
            "kind": SimpleNamespace(
                choice=case["kind"], confidence=0.99, probabilities={case["kind"]: 0.99, "__other": 0.01}
            ),
            "risk": SimpleNamespace(noul=0.99 if case["risk"] else 0.01),
        }
        return SimpleNamespace(answers=answers, usage=SimpleNamespace(input_tokens=0))


def grade(case: dict, got: disclosures.Judgment) -> dict:
    """사례 하나를 채점한다.

    @param case 정답 사례
    @param got 판정 결과
    @returns {"kind_ok", "risk_ok"}
    """
    return {
        "kind_ok": got.kind in {case["kind"], *case.get("kind_alt", [])},
        "risk_ok": got.risk == case["risk"],
    }


def _ece(pairs: list[tuple[float, bool]]) -> float | None:
    """(확률, 맞음) 쌍의 10구간 ECE."""
    if not pairs:
        return None
    total = 0.0
    for i in range(10):
        lo, hi = i / 10, (i + 1) / 10
        members = [(p, y) for p, y in pairs if lo <= p < hi or (i == 9 and p == 1.0)]
        if members:
            conf = statistics.mean(p for p, _ in members)
            acc = statistics.mean(y for _, y in members)
            total += len(members) / len(pairs) * abs(conf - acc)
    return round(total, 3)


def _share(rows: list[dict], key: str) -> float | None:
    return round(statistics.mean(r[key] for r in rows), 3) if rows else None


def summarize(rows: list[dict]) -> dict:
    """사례별 행을 요약한다.

    @param rows run의 결과
    @returns 정확도·재현율·정밀도·ECE·지연
    """
    n = len(rows)
    if not n:  # --max-usd가 첫 호출 비용보다 작으면 한 건도 돌지 않는다
        return {"cases": 0, "input_tokens": 0}
    gold_risk = [r for r in rows if r["gold_risk"]]
    flagged = [r for r in rows if r["risk"]]
    by_jev = [r for r in rows if r["judged_by"] == "jev"]
    jev_kind = [r for r in by_jev if r["kind_prob"] is not None]
    jev_risk = [r for r in by_jev if r["risk_prob"] is not None]
    called = sorted(r["ms"] for r in by_jev)
    strata = ("fixed", "free", "risk_open")
    return {
        "cases": n,
        "kind_accuracy": _share(rows, "kind_ok"),
        "kind_accuracy_by_stratum": {s: _share([r for r in rows if r["stratum"] == s], "kind_ok") for s in strata},
        "risk_recall": round(sum(r["risk"] for r in gold_risk) / len(gold_risk), 3) if gold_risk else None,
        "risk_precision": round(sum(r["gold_risk"] for r in flagged) / len(flagged), 3) if flagged else None,
        "risk_accuracy": _share(rows, "risk_ok"),
        "risk_accuracy_by_stratum": {s: _share([r for r in rows if r["stratum"] == s], "risk_ok") for s in strata},
        "jev": {
            "cases": len(by_jev),
            "kind_decided": len(jev_kind),
            "kind_accuracy": _share(jev_kind, "kind_ok"),
            "kind_ece": _ece([(r["kind_prob"], r["kind_ok"]) for r in jev_kind]),
            "risk_decided": len(jev_risk),
            "risk_accuracy": _share(jev_risk, "risk_ok"),
            # Noul은 '예'의 확률이므로 정답이 '예'인 빈도와 비교한다.
            "risk_ece": _ece([(r["risk_prob"], r["gold_risk"]) for r in jev_risk]),
        },
        "errors": [
            {
                "id": r["id"],
                "report_nm": r["report_nm"],
                "kind": r["kind"],
                "gold_kind": r["gold_kind"],
                "risk": r["risk"],
                "risk_prob": r["risk_prob"],
                "gold_risk": r["gold_risk"],
            }
            for r in rows
            if not (r["kind_ok"] and r["risk_ok"])
        ],
        # nearest-rank 백분위수: 정렬된 값의 ceil(p·n)번째. Jev를 부른 사례만.
        "latency_ms": (
            {"p50": called[math.ceil(0.5 * len(called)) - 1], "p95": called[math.ceil(0.95 * len(called)) - 1]}
            if called
            else None
        ),
        "input_tokens": sum(r["input_tokens"] for r in rows),
    }


def run(client, cases: list[dict], max_usd: float | None = None) -> list[dict]:
    """사례마다 판정한다.

    @param client system_one을 가진 클라이언트. None이면 규칙만 쓴다.
    @param cases 정답 사례
    @param max_usd live 비용 상한(없으면 None)
    @returns 사례별 행
    """
    rows, spent = [], 0.0
    for case in cases:
        needs_jev = client is not None and None in disclosures.by_rules(case["report_nm"])
        if needs_jev and max_usd is not None and spent + 0.001 > max_usd:  # 호출 1건은 $0.0001 미만이지만 여유를 둔다
            print(f"stopping: next call could exceed --max-usd {max_usd}", file=sys.stderr)
            break
        start = time.perf_counter()
        got = disclosures.judge(case["report_nm"], case["rm"], case["corp_cls"], client)
        ms = round((time.perf_counter() - start) * 1000)
        if max_usd is not None:  # 상한이 있을 때만 쌓는다. 단가가 없으면 KeyError로 멈춘다
            spent += pricing.cost_usd(disclosures.MODEL, pricing.Usage(input_tokens=got.input_tokens))
        rows.append(
            {
                "id": case["id"],
                "report_nm": case["report_nm"],
                "stratum": case["stratum"],
                "gold_kind": case["kind"],
                "gold_risk": case["risk"],
                "kind": got.kind,
                "risk": got.risk,
                "kind_prob": got.kind_prob,
                "risk_prob": got.risk_prob,
                "judged_by": got.judged_by,
                "ms": ms,
                "input_tokens": got.input_tokens,
                **grade(case, got),
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Jev DART disclosure eval")
    parser.add_argument("--mode", choices=("oracle", "rules", "live"), required=True)
    parser.add_argument("--max-usd", type=float, default=0.0, help="live only: spend cap")
    parser.add_argument(
        "--cases", type=Path, default=EVAL_DIR / "cases.jsonl", help="heldout.jsonl: 문구를 고친 뒤 재는 따로 둔 사례"
    )
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    cases = load_cases(args.cases)
    if args.mode == "live":
        if args.max_usd <= 0:
            parser.error("--mode live needs --max-usd (the spend cap Noah approved)")
        pricing.cost_usd(disclosures.MODEL, pricing.Usage())  # 단가가 없으면 과금 호출 전에 멈춘다
        from typesafe_sdk import TypeSafeClient

        client = TypeSafeClient()
    else:
        client = OracleClient(cases) if args.mode == "oracle" else None
    rows = run(client, cases, args.max_usd if args.mode == "live" else None)
    summary = summarize(rows)
    usage = pricing.Usage(input_tokens=summary["input_tokens"])
    cost = pricing.cost_usd_or_none(disclosures.MODEL, usage)  # 비공개 단가가 없는 환경은 None(미확인)
    summary["cost_usd"] = round(cost, 6) if cost is not None else None
    summary.update(
        mode=args.mode,
        cases_file=args.cases.name,
        model=disclosures.MODEL,
        run_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    out = args.out or EVAL_DIR / "results" / f"{args.mode}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "errors"}, ensure_ascii=False, indent=1))
    print(f"errors: {len(summary.get('errors', []))}; wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
