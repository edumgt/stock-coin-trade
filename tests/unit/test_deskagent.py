"""deskagent through the real anthropic SDK with a scripted HTTP transport (no network, no cost)."""

import json

import pytest
from agent_script import Script, _client, answer, call_backtest

from deskagent import numbers, pricing
from deskagent.agent import ask
from deskagent.numbers import Ledger, UnreceiptedAnswer, render, stray_numbers
from deskagent.tools import LocalBackend

GOOD = "005930 MA 교차 전략(2023-01-01 ~ 2025-12-31)의 총수익률은 {{n1}}, Sharpe는 {{n2}}, 보유는 {{n3}}입니다."


def test_answer_numbers_come_from_the_backtest_the_agent_ran():
    script = Script(call_backtest, answer(GOOD))
    result = ask(_client(script), LocalBackend(), "삼성전자 MA 전략 성과는?")
    assert result.status == "answered", result.problems
    run = LocalBackend().run_backtest(
        {"symbol": "005930", "strategy": "ma2050", "start": "2023-01-01", "end": "2025-12-31"}
    )
    shown = {n["path"]: n["value"] for n in result.rendered["numbers"]}
    assert shown["metrics.sharpe"] == pytest.approx(run["metrics"]["sharpe"])
    assert numbers.display(run["metrics"]["totalReturn"], "percent") in result.rendered["text"]
    assert result.rendered["receipts"] == [run["receiptId"]]
    assert [c["name"] for c in result.tool_calls] == ["run_backtest"]
    assert result.turns == 2


def test_request_shape_follows_the_sdk_docs():
    script = Script(call_backtest, answer(GOOD))
    ask(_client(script), LocalBackend(), "q")
    first, second = script.requests
    assert first["model"] == "claude-opus-5-5" and first["thinking"] == {"type": "adaptive"}
    # Opus 5.5의 기본 effort는 medium이라 Opus 5와 같은 high를 명시한다.
    assert first["output_config"]["effort"] == "high"
    assert first["output_config"]["format"]["type"] == "json_schema" and first["stream"] is True
    assert {t["name"] for t in first["tools"]} == {"list_sources", "run_backtest", "get_backtest"}
    tool_result = second["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result" and tool_result["tool_use_id"] == "t1"
    assert second["messages"][1]["role"] == "assistant"  # the tool_use turn is echoed back


def test_a_number_typed_by_the_model_triggers_one_repair_then_passes():
    script = Script(call_backtest, answer("수익률은 12.5%이고 Sharpe는 {{n2}}입니다."), answer(GOOD))
    result = ask(_client(script), LocalBackend(), "q")
    assert result.status == "answered"
    repair = script.requests[2]["messages"][-1]["content"]
    assert "12.5%" in repair and "자리표시자" in repair


def test_the_answer_is_withheld_when_the_repair_also_fails():
    bad = answer("Sharpe는 1.23입니다.")
    result = ask(_client(Script(call_backtest, bad, bad)), LocalBackend(), "q")
    assert result.status == "unreceipted" and result.rendered is None
    assert any("1.23" in problem for problem in result.problems)


def test_citing_a_receipt_the_conversation_never_produced_is_rejected():
    fake = "f" * 64
    result = ask(
        _client(Script(call_backtest, answer(GOOD, cited=fake), answer(GOOD, cited=fake))), LocalBackend(), "q"
    )
    assert result.status == "unreceipted"
    assert any("not produced in this conversation" in problem for problem in result.problems)


def test_refusal_stops_without_running_that_turns_tools():
    def refuse(_body):
        return (
            [
                {
                    "type": "tool_use",
                    "id": "t9",
                    "name": "run_backtest",
                    "input": {"symbol": "005930", "strategy": "rsi"},
                }
            ],
            "refusal",
            {"type": "refusal", "category": "cyber"},
        )

    result = ask(_client(Script(refuse)), LocalBackend(), "q")
    assert result.status == "refused" and result.tool_calls == []


def test_truncated_turn_is_not_executed():
    def cut(_body):
        return [{"type": "tool_use", "id": "t2", "name": "run_backtest", "input": {"symbol": "005930"}}], "max_tokens"

    result = ask(_client(Script(cut)), LocalBackend(), "q")
    assert result.status == "truncated" and result.tool_calls == []


def test_tool_errors_go_back_to_the_model_as_error_results():
    def bad_call(_body):
        return [
            {
                "type": "tool_use",
                "id": "t3",
                "name": "run_backtest",
                "input": {"symbol": "005930", "strategy": "martingale"},
            }
        ], "tool_use"

    script = Script(bad_call, call_backtest, answer(GOOD))
    result = ask(_client(script), LocalBackend(), "q")
    error = script.requests[1]["messages"][-1]["content"][0]
    assert error["is_error"] is True and "strategy" in error["content"]
    assert result.status == "answered" and [c["ok"] for c in result.tool_calls] == [False, True]


def test_out_of_scope_questions_are_answered_without_numbers():
    script = Script(
        answer("미래 가격은 예측하지 않습니다. 과거 백테스트는 도와드릴 수 있습니다.", cited="x", out_of_scope=True)
    )
    result = ask(_client(script), LocalBackend(), "내일 삼성전자 오를까?")
    assert result.status == "out_of_scope" and result.tool_calls == []


def test_turn_limit_bounds_the_loop():
    script = Script(*[call_backtest] * 3)
    result = ask(_client(script), LocalBackend(), "q", max_turns=3)
    assert result.status == "turn_limit" and result.turns == 3


def test_cost_adds_up_every_turn_from_the_pricing_file():
    result = ask(_client(Script(call_backtest, answer(GOOD))), LocalBackend(), "q")
    per_turn = pricing.cost_usd("claude-opus-5-5", pricing.Usage(input_tokens=1000, output_tokens=200))
    assert result.cost_usd == pytest.approx(2 * per_turn)
    assert per_turn == pytest.approx((1000 * 4.00 + 200 * 20.00) / 1e6)
    assert result.usage.input_tokens == 2000 and result.usage.output_tokens == 400


# ── numbers.render / stray detection ─────────────────────────────────────────


def _ledger():
    ledger = Ledger()
    ledger.add_run(
        {
            "receiptId": "a" * 64,
            "parameters": {"symbol": "005930", "strategy": "ma2050", "fast": 20},
            "metrics": {"sharpe": 0.53, "totalReturn": 0.1234, "trades": 17, "flag": True},
        }
    )
    return ledger


@pytest.mark.parametrize(
    ("template", "strays"),
    [
        ("005930 `ma2050` 2024-01-02 ~ 2025-12-31", []),
        ("1. 첫째\n2) 둘째\n- 셋째", []),
        (f"영수증 {'a' * 12}", []),
        ("Sharpe 0.53", ["0.53"]),
        ("MA 20/50 교차", ["20/50"]),
        ("수익률 12%", ["12%"]),
        ("3번 거래", ["3번"]),
    ],
)
def test_stray_number_detection(template, strays):
    assert stray_numbers(template, _ledger().identifiers) == strays


def test_render_formats_and_rejects_non_numbers():
    ledger = _ledger()
    ok = render(
        {
            "answer": "{{n1}} / {{n2}} / {{n3}}",
            "out_of_scope": False,
            "numbers": [
                {"id": "n1", "receipt_id": "a" * 64, "path": "metrics.totalReturn", "format": "percent"},
                {"id": "n2", "receipt_id": "a" * 64, "path": "metrics.sharpe", "format": "ratio"},
                {"id": "n3", "receipt_id": "a" * 64, "path": "metrics.trades", "format": "integer"},
            ],
        },
        ledger,
    )
    assert ok["text"] == "+12.34% / 0.53 / 17"
    for path in ("metrics.flag", "metrics.missing", "parameters.symbol"):
        with pytest.raises(UnreceiptedAnswer):
            render(
                {
                    "answer": "{{n1}}",
                    "out_of_scope": False,
                    "numbers": [{"id": "n1", "receipt_id": "a" * 64, "path": path, "format": "ratio"}],
                },
                ledger,
            )


def test_placeholder_without_an_entry_is_rejected():
    with pytest.raises(UnreceiptedAnswer, match="n7"):
        render({"answer": "{{n7}}", "numbers": [], "out_of_scope": False}, _ledger())


def test_pricing_file_names_its_official_source():
    import tomllib

    data = tomllib.loads(pricing.PRICING_FILE.read_text())
    assert data["source"].startswith("https://platform.claude.com/") and data["checked_on"]
    for model in ("claude-opus-5", "claude-opus-5-5"):
        assert set(data["models"][model]) == {"input", "cache_write_5m", "cache_read", "output"}


# ── eval baselines (offline, pinned) ─────────────────────────────────────────


@pytest.mark.parametrize(("mode", "expected"), [("oracle", 1.0), ("null", 0.0), ("sneaky", 0.0), ("forged", 0.0)])
def test_eval_baselines(tmp_path, mode, expected):
    """A perfect model scores 100%; models that type or forge numbers are blocked on every case."""
    from deskagent import eval as agent_eval

    out = tmp_path / f"{mode}.json"
    agent_eval.main(["--mode", mode, "--repeats", "1", "--out", str(out)])
    summary = json.loads(out.read_text())["summary"]
    assert summary["passRate"] == expected and summary["runs"] == 30 and summary["billed"] is False


def test_eval_cases_are_thirty_synthetic_korean_questions():
    from deskagent import eval as agent_eval

    cases = agent_eval.load_cases()
    assert len(cases) == 30 and len({c["id"] for c in cases}) == 30
    assert sum(c["expect"] == "out_of_scope" for c in cases) == 5
    assert all(any("가" <= ch <= "힣" for ch in c["question"]) for c in cases)


def test_live_eval_refuses_to_run_without_a_spend_cap():
    from deskagent import eval as agent_eval

    with pytest.raises(SystemExit):
        agent_eval.main(["--mode", "live"])


def test_every_token_kind_is_priced_at_its_own_rate():
    # claude-opus-5 on the official pricing page: input $5, 5m cache write $6.25, cache hit $0.50, output $25 per MTok.
    usage = pricing.Usage(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_creation_input_tokens=1_000_000,
        cache_read_input_tokens=1_000_000,
    )
    assert pricing.cost_usd("claude-opus-5", usage) == pytest.approx(5.00 + 25.00 + 6.25 + 0.50)
    assert pricing.cost_usd("claude-opus-5", pricing.Usage(cache_read_input_tokens=2_000_000)) == pytest.approx(1.00)
    # claude-opus-5-5: input $4, 5m cache write $5, cache hit $0.20 (0.05x), output $20 per MTok.
    assert pricing.cost_usd("claude-opus-5-5", usage) == pytest.approx(4.00 + 20.00 + 5.00 + 0.20)
    with pytest.raises(KeyError):
        pricing.cost_usd("gpt-4o", usage)


def test_local_pricing_file_overlays_the_public_table(tmp_path):
    row = "input = {0}\ncache_write_5m = 0.0\ncache_read = 0.0\noutput = {0}\n"
    public = tmp_path / "p.toml"
    public.write_text("[models.a]\n" + row.format(1.0), encoding="utf-8")
    assert set(pricing.load(public)) == {"a"}
    local = public.with_suffix(".local.toml")
    local.write_text("[models.b]\n" + row.format(2.0), encoding="utf-8")
    assert set(pricing.load(public)) == {"a", "b"}
    local.write_text("# 주석만 있는 비공개 파일은 공개 가격표를 깨지 않는다\n", encoding="utf-8")
    assert set(pricing.load(public)) == {"a"}


def test_unpriced_model_is_unknown_cost_not_zero(monkeypatch):
    monkeypatch.setattr(pricing, "load", lambda *args: {})
    assert pricing.cost_usd_or_none("private-model", pricing.Usage(input_tokens=5)) is None
    with pytest.raises(KeyError, match="llm_pricing.local.toml"):
        pricing.cost_usd("private-model", pricing.Usage(input_tokens=5))


def test_example_pricing_file_carries_no_price_values():
    import tomllib

    example = pricing.PRICING_FILE.with_name("llm_pricing.example.toml")
    assert tomllib.loads(example.read_text(encoding="utf-8")) == {}
