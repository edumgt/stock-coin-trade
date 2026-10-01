"""KIS API 탐색기.

공식 저장소(open-trading-api) 예제에서 추출한 카탈로그(app/resources/kis_api_catalog.json)를 제공하고,
Testbed(모의투자)를 지원하는 읽기 전용(GET) API만 서버가 대신 호출한다.

- 계좌 파라미터(CANO, ACNT_PRDT_CD)는 브라우저 값을 쓰지 않고 서버의 .env로 채운다.
- 주문성(POST) API는 탐색기에서 호출하지 않는다. 보호된 모의 주문 흐름 테스트로 안내한다.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from app.core.config import RESOURCES_DIR
from app.services.brokers.common import BrokerApiError
from app.services.brokers.kis import _kis_account, kis_request

_CATALOG_PATH = RESOURCES_DIR / "kis_api_catalog.json"
CATALOG: dict[str, Any] = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
BY_ID: dict[str, dict[str, Any]] = {api["id"]: api for api in CATALOG["apis"]}

ACCOUNT_CATEGORIES = {"주문/계좌"}
_VALUE_RE = re.compile(r"^[A-Za-z0-9_.\-:/ ]{0,40}$")


def build_params(api: dict[str, Any], user_params: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    """(KIS로 보낼 파라미터, 화면에 보여 줄 마스킹된 파라미터)."""
    cano, acnt_prdt_cd = (None, None)
    sent: dict[str, str] = {}
    shown: dict[str, str] = {}
    for p in api["params"]:
        key = p["key"]
        source = p["source"]
        if source == "server":
            if cano is None:
                cano, acnt_prdt_cd = _kis_account()
            value = cano if key == "CANO" else acnt_prdt_cd
            sent[key] = value
            shown[key] = (value[:4] + "****") if key == "CANO" else value
            continue
        if source == "blank":
            sent[key] = ""
            shown[key] = ""
            continue
        if source == "fixed":
            sent[key] = str(p.get("value", ""))
            shown[key] = sent[key]
            continue
        raw = user_params.get(key, p.get("default", ""))
        value = str(raw if raw is not None else "").strip()
        if not _VALUE_RE.match(value):
            raise BrokerApiError(f"{key} 값에 허용되지 않는 문자가 있거나 너무 깁니다.", 400)
        if p.get("required") and value == "":
            raise BrokerApiError(f"{p.get('label') or key} 값은 필수입니다.", 400)
        sent[key] = value
        shown[key] = value
    return sent, shown


def select_tr_id(api: dict[str, Any], variant: str | None) -> str:
    selector = api.get("trSelector")
    if selector:
        if variant in selector["map"]:
            return selector["map"][variant]
        return next(iter(selector["map"].values()))
    return api["trIdDemo"][0]


def call_api(api: dict[str, Any], user_params: dict[str, Any], variant: str | None) -> dict[str, Any]:
    """카탈로그 API 하나를 호출해 KIS 원문(rt_cd, msg_cd, msg1, output*)과 메타데이터를 돌려준다."""
    params, shown = build_params(api, user_params)
    tr_id = select_tr_id(api, variant)
    started = time.time()
    response, data = kis_request(
        "GET", api["url"], tr_id, params=params, label=api.get("title") or "API 조회",
        extra_headers={"custtype": "P", "tr_cont": ""}, raise_for_api_error=False,
    )
    return {
        "ok": data.get("rt_cd") == "0",
        "http": response.status_code,
        "rtCd": data.get("rt_cd"),
        "msgCd": data.get("msg_cd"),
        "msg1": (data.get("msg1") or "").strip(),
        "trId": tr_id,
        "url": api["url"],
        "elapsedMs": int((time.time() - started) * 1000),
        "request": shown,
        "body": data,
        "columns": api.get("columns", {}),
    }
