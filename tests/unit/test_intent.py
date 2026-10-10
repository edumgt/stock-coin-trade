"""자연어 명령 라우터(src/deskjev + /api/intent). Jev 응답은 가짜로 만든다: 네트워크 없음."""

from types import SimpleNamespace

import pytest

import intent as intent_api
import jev_usage
from accounts import PRIVACY_VERSION
from deskjev import intent
from settings import Settings, SettingsError


def _choice(probabilities: dict[str, float], choice: str | None = None):
    top = max(probabilities, key=probabilities.get)
    return SimpleNamespace(choice=choice or top, confidence=probabilities[top], probabilities=probabilities)


def _answers(screen: dict, stock: dict | None = None, coin: dict | None = None, strategy: dict | None = None):
    return {
        "screen": _choice(screen),
        "stock": _choice(stock or {"none": 1.0}),
        "coin": _choice(coin or {"none": 1.0}),
        "strategy": _choice(strategy or {"none": 1.0}),
    }


def test_confident_stock_command_goes_straight_to_the_symbol():
    got = intent.decide(_answers({"stock": 0.97, "coin": 0.03}, stock={"000660": 0.95, "none": 0.05}))
    assert (got.action, got.href, got.confidence) == ("go", "/trade/stock.html?symbol=000660", 0.97)


def test_backtest_fills_confident_arguments_and_leaves_out_doubtful_ones():
    got = intent.decide(
        _answers({"quant": 0.99}, stock={"005930": 0.98}, strategy={"rsi": 0.7, "none": 0.3}), input_tokens=750
    )
    # 화면이 확실하면 이동하되, 확률이 ARG_MIN보다 낮은 전략은 싣지 않는다(틀리게 싣는 것보다 낫다).
    assert (got.action, got.href, got.strategy) == ("go", "/quant.html?symbol=005930", None)
    assert got.confidence == 0.99 and got.input_tokens == 750
    sure = intent.decide(_answers({"quant": 0.99}, stock={"005930": 0.98}, strategy={"rsi": 0.9, "none": 0.1}))
    assert sure.href == "/quant.html?symbol=005930&strategy=rsi"


def test_suggestion_for_the_chosen_screen_keeps_its_arguments():
    got = intent.decide(_answers({"arbitrage": 0.6, "coin": 0.4}, coin={"ETH": 0.95}))
    assert got.action == "suggest" and got.alternatives[0]["href"] == "/arbitrage.html?symbol=ETH"
    assert got.alternatives[1]["href"] == "/trade/order.html"


def test_arguments_the_screen_does_not_use_are_ignored():
    # "비트 차트"가 전략 질문에서 무엇을 골랐든 코인 화면은 전략을 쓰지 않는다.
    got = intent.decide(_answers({"coin": 0.99}, coin={"BTC": 0.99}, strategy={"rsi": 0.2, "none": 0.8}))
    assert got.href == "/trade/order.html?market=KRW-BTC" and got.strategy is None and got.action == "go"


def test_unrelated_text_asks_for_help_without_a_link():
    got = intent.decide(_answers({"none": 0.9, "research": 0.1}))
    assert (got.action, got.href) == ("help", None)


def test_uncertain_screen_offers_suggestions_not_navigation():
    got = intent.decide(_answers({"research": 0.55, "stock": 0.35, "none": 0.10}))
    assert got.action == "suggest"
    assert [alt["screen"] for alt in got.alternatives] == ["research", "stock"]


def test_values_outside_the_sent_candidates_are_dropped():
    # 외부 API가 후보에 없는 값을 돌려줘도 URL에 넣지 않는다(쿼리 인젝션 방지).
    allowed = {"stock": {"005930"}, "coin": {"BTC"}, "strategy": {"rsi"}}
    got = intent.decide(_answers({"stock": 0.99}, stock={"005930&x=1": 0.99}), allowed=allowed)
    assert (got.href, got.stock) == ("/trade/stock.html", None)
    assert intent.decide(_answers({"admin": 0.99}), allowed=allowed).action == "help"


def test_suggestions_skip_none_before_taking_the_top_three():
    got = intent.decide(_answers({"dashboard": 0.5, "none": 0.3, "stock": 0.14, "coin": 0.06}))
    assert [alt["screen"] for alt in got.alternatives] == ["dashboard", "stock", "coin"]


def test_quant_keeps_one_symbol_so_link_and_fields_agree():
    got = intent.decide(_answers({"quant": 0.99}, stock={"005930": 0.95}, coin={"BTC": 0.95}))
    assert (got.href, got.stock, got.coin) == ("/quant.html?symbol=005930", "005930", None)


def test_eval_summary_survives_no_rows_and_uses_nearest_rank_p95():
    from deskjev.eval import summarize

    assert summarize([])["cases"] == 0
    rows = [
        {
            "id": str(i),
            "screen": "stock",
            "confidence": 0.9,
            "action": "go",
            "ms": i,
            "input_tokens": 1,
            "screen_ok": True,
            "nav_ok": True,
            "full_ok": True,
        }
        for i in range(1, 21)
    ]
    assert summarize(rows)["latency_ms"] == {"p50": 10, "p95": 19}


def test_the_distribution_wins_over_a_mismatched_choice_label():
    answers = _answers({"stock": 0.9, "coin": 0.1})
    answers["screen"] = _choice({"stock": 0.9, "coin": 0.1}, choice="coin")  # sdk-python#15
    assert intent.decide(answers).screen == "stock"


def test_route_pins_the_model_and_sends_only_the_trimmed_command():
    seen = {}

    class FakeClient:
        def system_one(self, state, questions, *, model):
            seen.update(state=state, questions=set(questions), model=model)
            return SimpleNamespace(answers=_answers({"dashboard": 0.99}), usage=SimpleNamespace(input_tokens=700))

    got = intent.route(FakeClient(), "  홈" + "x" * 500, {"005930": "삼성전자"}, {"BTC": "비트코인"}, {"rsi": "RSI"})
    assert seen["model"] == "jev-1.13.0"
    assert list(seen["state"]) == ["user_command"] and len(seen["state"]["user_command"]) == intent.MAX_TEXT
    assert seen["questions"] == {"screen", "stock", "coin", "strategy"} and got.href == "/index.html"


# ── /api/intent ──────────────────────────────────────────────────────────────


@pytest.fixture
def jev_client(app, monkeypatch):
    app.config.update(JEV_ENABLED=True, JEV_MONTHLY_BUDGET_USD=1.0)
    intent_api._route.cache_clear()
    monkeypatch.setattr(jev_usage, "over_budget", lambda budget: False)
    recorded = []
    monkeypatch.setattr(jev_usage, "record", recorded.append)
    yield app.test_client(), recorded
    intent_api._route.cache_clear()


def test_over_budget_refuses_when_the_model_has_no_price(monkeypatch):
    from deskagent import pricing

    monkeypatch.setattr(pricing, "load", lambda *args: {})
    assert jev_usage.over_budget(10.0) is True


def test_endpoint_is_off_unless_enabled(client):
    assert client.post("/api/intent", json={"text": "홈"}).get_json() == {"enabled": False}


def test_endpoint_routes_and_records_only_uncached_calls(jev_client, monkeypatch):
    http, recorded = jev_client

    class FakeClient:
        def system_one(self, state, questions, *, model):
            return SimpleNamespace(
                answers=_answers({"arbitrage": 0.96}, coin={"ETH": 0.97}), usage=SimpleNamespace(input_tokens=740)
            )

    monkeypatch.setattr(jev_usage, "client", FakeClient)
    for _ in range(2):
        body = http.post("/api/intent", json={"text": "이더  김프", "consent": PRIVACY_VERSION}).get_json()
    assert body["enabled"] and body["action"] == "go" and body["href"] == "/arbitrage.html?symbol=ETH"
    assert recorded == [740]  # 두 번째는 캐시


def test_endpoint_falls_back_when_jev_fails(jev_client, monkeypatch):
    http, recorded = jev_client

    class Down:
        def system_one(self, *args, **kwargs):
            raise TimeoutError("jev timed out")

    monkeypatch.setattr(jev_usage, "client", Down)
    assert http.post("/api/intent", json={"text": "홈", "consent": PRIVACY_VERSION}).get_json() == {
        "enabled": False,
        "reason": "unavailable",
    }
    assert recorded == []


def test_nothing_is_sent_abroad_before_consent(jev_client, monkeypatch):
    # 명령 문장은 미국 TypeSafe로 가므로(개인정보 처리방침 4절), 현재 버전에 동의한 요청만 보낸다.
    http, recorded = jev_client

    def must_not_call():
        raise AssertionError("동의 전에 Jev를 불렀다")

    monkeypatch.setattr(jev_usage, "client", must_not_call)
    for consent in (None, "2020-01-01"):
        body = {"text": "이더 김프"} | ({"consent": consent} if consent else {})
        answer = http.post("/api/intent", json=body).get_json()
        assert answer == {"enabled": True, "consentRequired": True, "consentVersion": PRIVACY_VERSION}
    assert recorded == []


def test_endpoint_rejects_missing_text(jev_client):
    http, _ = jev_client
    assert http.post("/api/intent", json={"text": "  ", "consent": PRIVACY_VERSION}).status_code == 400


def test_jev_needs_a_budget_and_a_key():
    base = {"SECRET_KEY": "x" * 40, "JEV_ENABLED": "true"}
    with pytest.raises(SettingsError, match="JEV_MONTHLY_BUDGET_USD"):
        Settings.from_env(base)
    with pytest.raises(SettingsError, match="TYPESAFE_API_KEY"):
        Settings.from_env({**base, "JEV_MONTHLY_BUDGET_USD": "5"})
    on = Settings.from_env({**base, "JEV_MONTHLY_BUDGET_USD": "5", "TYPESAFE_API_KEY": "ts-test"})
    assert on.jev_enabled and on.flask_config()["JEV_MONTHLY_BUDGET_USD"] == 5.0


# ── evals/jev_intent ─────────────────────────────────────────────────────────


def test_every_gold_answer_is_a_candidate_jev_can_pick():
    from deskjev.eval import load_cases

    stocks, coins, strategies = intent_api.candidates()
    for case in load_cases():
        assert case["screen"] in intent.SCREENS, case["id"]
        assert set(case.get("screen_alt", [])) <= set(intent.SCREENS), case["id"]
        assert case["stock"] is None or case["stock"] in stocks, case["id"]
        assert case["coin"] is None or case["coin"] in coins, case["id"]
        assert case["strategy"] is None or case["strategy"] in strategies, case["id"]


def test_oracle_model_scores_perfectly():
    from deskjev.eval import OracleClient, load_cases, run, summarize

    cases = load_cases()
    summary = summarize(run(OracleClient(cases), cases, intent_api.candidates()))
    assert summary["full_accuracy"] == 1 and summary["go_errors"] == []


def test_disclosure_radar_is_a_screen_that_takes_a_stock():
    # 공시 레이더(S3)는 공개 사이트의 핵심 기능이다. "삼성전자 공시 보여줘"가 주식 화면으로 가면 안 된다.
    assert intent.USES["disclosures"] == ("stock",)
    assert intent._href("disclosures", "005930", None, None) == "/events.html?symbol=005930"
    assert intent._href("disclosures", None, None, None) == "/events.html"
