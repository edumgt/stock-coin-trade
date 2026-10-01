"""KIS API 탐색기(/api/kis-explorer/*)."""

from __future__ import annotations

import requests
from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from app.core.deps import OptionalMemberId, csrf_required
from app.core.errors import ApiError
from app.services.authz import can_use_kis_account
from app.services.brokers.common import BrokerApiError
from app.services.brokers.kis_explorer import ACCOUNT_CATEGORIES, BY_ID, CATALOG, call_api

from ..schemas import KisExplorerCallBody

router = APIRouter(prefix="/api/kis-explorer", tags=["kis"])
require_csrf = csrf_required(ok=False, message="요청 검증에 실패했습니다. 화면을 새로고침한 뒤 다시 시도하세요.")


@router.get("/catalog")
def catalog() -> dict:
    return {"ok": True, **CATALOG}


@router.post("/call")
def call(request: Request, member_id: OptionalMemberId, payload: KisExplorerCallBody = Body(default_factory=KisExplorerCallBody)):
    require_csrf(request)
    api = BY_ID.get(str(payload.id or ""))
    if api is None:
        raise ApiError(404, ok=False, message="카탈로그에 없는 API 입니다.")
    if not api["demoSupported"]:
        raise ApiError(400, ok=False, message="이 API 는 모의투자(Testbed)를 지원하지 않아 이 웹앱에서 호출하지 않습니다. 실전 계좌·실전 키가 필요합니다.")
    if api["method"] != "GET":
        raise ApiError(400, ok=False, message="주문·정정·취소 같은 주문성 API 는 탐색기에서 직접 호출하지 않습니다. 로그인 후 '모의 주문 흐름 테스트'에서 보호된 흐름으로만 실행합니다.")
    if api["category"] in ACCOUNT_CATEGORIES and not can_use_kis_account(member_id):
        raise ApiError(401, ok=False, message="계좌 관련 API 는 로그인한 회원만 호출할 수 있습니다.")

    try:
        result = call_api(api, payload.params or {}, payload.variant)
    except BrokerApiError as exc:
        raise ApiError(exc.status_code, ok=False, message=str(exc))
    except requests.RequestException:
        raise ApiError(503, ok=False, message="한국투자증권 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요.")
    return result if result["ok"] else JSONResponse(result, status_code=502)
