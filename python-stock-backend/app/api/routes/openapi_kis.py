"""KIS 자동매매 Open API (/openapi/v1/kis). Bearer API 키 + 화이트리스트 스코프 + 60초 승인 토큰.

계약: docs/contracts/kis-autotrade-api.md. 호출자는 lumina-invest 의 Celery 사이클(서버 간 호출)이다.
기존 /openapi/v1/orders 는 가상 주문이므로 KIS 실주문은 반드시 이 라우터를 쓴다.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Body, Query

from app.core.database import DbSession
from app.core.errors import ApiError
from app.services.authz import member_email
from app.services.brokers import kis_autotrade
from app.services.brokers.common import BrokerApiError

from ..schemas import KisAutotradeOrderBody
from .openapi import ApiKeyContext

router = APIRouter(prefix="/openapi/v1/kis", tags=["openapi-kis"])


def _raise(exc: BrokerApiError) -> ApiError:
    code = getattr(exc, "code", None) or ("KIS_CONFIG_REQUIRED" if exc.status_code == 503 else "KIS_ERROR")
    details = getattr(exc, "details", None) or {}
    return ApiError(exc.status_code, ok=False, error=code, message=str(exc), **details)


def _intent(payload: KisAutotradeOrderBody) -> dict:
    try:
        return kis_autotrade.normalize_intent(payload.model_dump())
    except BrokerApiError as exc:
        raise _raise(exc)


def _environment(raw: str) -> str:
    try:
        return kis_autotrade.normalize_environment(raw)
    except BrokerApiError as exc:
        raise _raise(exc)


def _scope(ctx: tuple[int, int], db=None) -> tuple[int, int]:
    try:
        kis_autotrade.require_scope(ctx[0], db)
    except BrokerApiError as exc:
        raise _raise(exc)
    return ctx


def _guard_real(environment: str, symbol: str, member_id: int) -> None:
    if environment != "real":
        return
    try:
        kis_autotrade.require_real_allowed(symbol, lambda: member_email(member_id))
    except BrokerApiError as exc:
        raise _raise(exc)


@router.post("/order-approval")
def order_approval(ctx: ApiKeyContext, db: DbSession, payload: KisAutotradeOrderBody = Body(default_factory=KisAutotradeOrderBody)) -> dict:
    api_key_id, member_id = _scope(ctx, db)
    intent = _intent(payload)
    _guard_real(intent["environment"], intent["symbol"], member_id)
    return {"ok": True, **kis_autotrade.issue_approval(db, api_key_id=api_key_id, member_id=member_id, intent=intent)}


@router.post("/orders")
def place_order(ctx: ApiKeyContext, db: DbSession, payload: KisAutotradeOrderBody = Body(default_factory=KisAutotradeOrderBody)) -> dict:
    api_key_id, member_id = _scope(ctx, db)
    intent = _intent(payload)
    _guard_real(intent["environment"], intent["symbol"], member_id)
    try:
        kis_autotrade.consume_approval(db, api_key_id=api_key_id, token=str(payload.approvalToken or ""), intent=intent)
        db.commit()  # 토큰 소비는 주문 성패와 무관하게 확정한다(재사용 방지).
        order, duplicate = kis_autotrade.place_order(db, api_key_id=api_key_id, member_id=member_id, intent=intent)
    except BrokerApiError as exc:
        raise _raise(exc)
    return {"ok": True, "order": order, "duplicate": duplicate}


@router.get("/orders")
def list_orders(ctx: ApiKeyContext, db: DbSession, environment: str = Query("paper"), status: str = Query("ALL")) -> dict:
    _scope(ctx, db)
    env = _environment(environment)
    try:
        orders = kis_autotrade.list_today_orders(env, open_only=status.strip().upper() == "OPEN")
    except BrokerApiError as exc:
        raise _raise(exc)
    return {"ok": True, "environment": env, "date": time.strftime("%Y%m%d", time.localtime()), "orders": orders}


@router.get("/orders/{order_no}")
def order_status(ctx: ApiKeyContext, db: DbSession, order_no: str, environment: str = Query("paper")) -> dict:
    _scope(ctx, db)
    env = _environment(environment)
    try:
        return {"ok": True, "order": kis_autotrade.sync_order_status(db, env, order_no.strip())}
    except BrokerApiError as exc:
        raise _raise(exc)


@router.delete("/orders/{order_no}")
def cancel_order(ctx: ApiKeyContext, db: DbSession, order_no: str, environment: str = Query("paper")) -> dict:
    api_key_id, member_id = _scope(ctx, db)
    env = _environment(environment)
    if env == "real":
        try:
            kis_autotrade.require_real_owner(lambda: member_email(member_id))
        except BrokerApiError as exc:
            raise _raise(exc)
    try:
        return {"ok": True, "order": kis_autotrade.cancel_order(db, env, order_no.strip())}
    except BrokerApiError as exc:
        raise _raise(exc)


@router.get("/balance")
def balance(ctx: ApiKeyContext, db: DbSession, environment: str = Query("paper")) -> dict:
    _scope(ctx, db)
    env = _environment(environment)
    try:
        return {"ok": True, "balance": kis_autotrade.get_balance(env)}
    except BrokerApiError as exc:
        raise _raise(exc)
