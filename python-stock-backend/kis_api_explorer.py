"""KIS API 탐색기 백엔드.

공식 저장소(open-trading-api) 예제에서 추출한 카탈로그(kis_api_catalog.json)를 제공하고,
Testbed(모의투자)를 지원하는 읽기 전용(GET) API 만 서버가 대신 호출한다.

- 계좌 파라미터(CANO, ACNT_PRDT_CD)는 브라우저 값을 쓰지 않고 서버의 .env로 채운다.
- 주문성(POST) API 는 탐색기에서 호출하지 않는다. 보호된 모의 주문 흐름 테스트로 안내한다.
- 응답은 KIS 원문(rt_cd, msg_cd, msg1, output*)을 그대로 돌려주고, 한글 필드명 매핑을 함께 준다.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import requests
from flask import Blueprint, jsonify, request, session

from authz import can_use_kis_account
from broker_test import BrokerApiError, _kis_account, kis_request
from security import csrf_is_valid

kis_explorer_bp = Blueprint("kis_explorer", __name__, url_prefix="/api/kis-explorer")

_CATALOG_PATH = Path(__file__).with_name("kis_api_catalog.json")
_CATALOG: dict[str, Any] = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
_BY_ID: dict[str, dict[str, Any]] = {api["id"]: api for api in _CATALOG["apis"]}

_ACCOUNT_CATEGORIES = {"주문/계좌"}
_VALUE_RE = re.compile(r"^[A-Za-z0-9_.\-:/ ]{0,40}$")


@kis_explorer_bp.get("/catalog")
def catalog():
    return jsonify({"ok": True, **_CATALOG})


def _build_params(api: dict[str, Any], user_params: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    """(KIS 로 보낼 파라미터, 화면에 보여 줄 마스킹된 파라미터)."""
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


def _select_tr_id(api: dict[str, Any], variant: str | None) -> str:
    selector = api.get("trSelector")
    if selector:
        if variant in selector["map"]:
            return selector["map"][variant]
        return next(iter(selector["map"].values()))
    return api["trIdDemo"][0]


@kis_explorer_bp.post("/call")
def call():
    if not csrf_is_valid():
        return jsonify({"ok": False, "message": "요청 검증에 실패했습니다. 화면을 새로고침한 뒤 다시 시도하세요."}), 403
    body = request.get_json(silent=True) or {}
    api = _BY_ID.get(str(body.get("id", "")))
    if api is None:
        return jsonify({"ok": False, "message": "카탈로그에 없는 API 입니다."}), 404
    if not api["demoSupported"]:
        return jsonify({"ok": False, "message": "이 API 는 모의투자(Testbed)를 지원하지 않아 이 웹앱에서 호출하지 않습니다. 실전 계좌·실전 키가 필요합니다."}), 400
    if api["method"] != "GET":
        return jsonify({"ok": False, "message": "주문·정정·취소 같은 주문성 API 는 탐색기에서 직접 호출하지 않습니다. 로그인 후 '모의 주문 흐름 테스트'에서 보호된 흐름으로만 실행합니다."}), 400
    if api["category"] in _ACCOUNT_CATEGORIES and not can_use_kis_account(session.get("member_id")):
        return jsonify({"ok": False, "message": "계좌 관련 API 는 로그인한 회원만 호출할 수 있습니다."}), 401

    try:
        params, shown = _build_params(api, body.get("params") or {})
        tr_id = _select_tr_id(api, body.get("variant"))
        started = time.time()
        response, data = kis_request(
            "GET", api["url"], tr_id, params=params, label=api.get("title") or "API 조회",
            extra_headers={"custtype": "P", "tr_cont": ""}, raise_for_api_error=False,
        )
        elapsed_ms = int((time.time() - started) * 1000)
    except BrokerApiError as exc:
        return jsonify({"ok": False, "message": str(exc)}), exc.status_code
    except requests.RequestException:
        return jsonify({"ok": False, "message": "한국투자증권 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요."}), 503

    result = jsonify({
        "ok": data.get("rt_cd") == "0",
        "http": response.status_code,
        "rtCd": data.get("rt_cd"),
        "msgCd": data.get("msg_cd"),
        "msg1": (data.get("msg1") or "").strip(),
        "trId": tr_id,
        "url": api["url"],
        "elapsedMs": elapsed_ms,
        "request": shown,
        "body": data,
        "columns": api.get("columns", {}),
    })
    return result if data.get("rt_cd") == "0" else (result, 502)
