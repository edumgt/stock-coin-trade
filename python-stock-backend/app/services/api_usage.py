"""외부 증권사·거래소 API 호출의 안전한 감사 기록."""

from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.context import RequestInfo, request_member_id, request_path
from app.core.database import engine, session_scope
from app.models import ApiUsageLog
from app.services.error_analysis import mask_sensitive

MAX_META = 2000
MAX_RESPONSE = 12000
_SECRET_KEYS = {
    "authorization", "appkey", "app_key", "appsecret", "app_secret", "secret",
    "token", "access_token", "password", "cano", "account", "account_no",
}
_QUERY_SECRET_KEYS = {"token", "key", "secret", "password"}


def _safe_value(value, key=""):
    """자격증명과 전체 계좌번호를 저장 전에 재귀적으로 제거한다."""
    normalized = str(key).lower().replace("-", "_")
    if normalized in _SECRET_KEYS:
        if normalized == "cano" and value:
            raw = str(value)
            return f"{raw[:4]}****"
        return "***"
    if isinstance(value, dict):
        return {str(k): _safe_value(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe_value(item) for item in value]
    return value


def ensure_api_usage_table() -> None:
    statement = """CREATE TABLE IF NOT EXISTS api_usage_log (
      api_usage_log_id BIGINT AUTO_INCREMENT PRIMARY KEY,
      called_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      member_id BIGINT NULL,
      provider VARCHAR(40) NOT NULL,
      operation VARCHAR(100) NOT NULL,
      method VARCHAR(10) NOT NULL,
      path VARCHAR(500) NOT NULL,
      request_meta TEXT NULL,
      http_status INT NOT NULL,
      success BOOLEAN NOT NULL,
      duration_ms INT NULL,
      result_summary VARCHAR(500) NULL,
      response_body TEXT NULL,
      KEY idx_api_usage_member_called (member_id, called_at),
      KEY idx_api_usage_provider_called (provider, called_at),
      KEY idx_api_usage_success_called (success, called_at),
      CONSTRAINT fk_api_usage_member FOREIGN KEY (member_id) REFERENCES member(member_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
    with engine.begin() as conn:
        conn.execute(text(statement))


def provider_for_path(path: str) -> str:
    if "/kis/" in path or "/kis-chart/" in path or "/kis-explorer/" in path or "/kis-real/" in path:
        return "KIS"
    if "/kb/" in path:
        return "KB증권"
    if "alpaca" in path:
        return "Alpaca"
    if "/binance/" in path:
        return "Binance"
    if "/korbit/" in path:
        return "Korbit"
    if "/secrets/" in path or "/ssm/" in path:
        return "AWS Secrets Manager"
    return "외부 API"


def _status_text(status: int) -> str:
    try:
        return f"{status} {HTTPStatus(status).phrase.upper()}"
    except ValueError:
        return str(status)


def record_api_usage(info: RequestInfo, status: int, body: dict[str, Any] | None, duration_ms: int | None,
                     query: dict[str, str]) -> None:
    """자체 API 응답 1건을 기록한다. 기록 실패가 성공한 외부 호출을 실패로 바꾸면 안 된다."""
    try:
        body = body or {}
        safe_body = mask_sensitive(json.dumps(body, ensure_ascii=False, default=str))[:MAX_RESPONSE]
        message = body.get("message") or body.get("error") or ("성공" if body.get("ok") else _status_text(status))
        safe_query = {key: value for key, value in query.items() if key.lower() not in _QUERY_SECRET_KEYS}
        with session_scope() as db:
            db.add(ApiUsageLog(
                member_id=info.member_id, provider=provider_for_path(info.path),
                operation=info.endpoint or info.path.rsplit("/", 1)[-1], method=info.method,
                path=info.path, request_meta=mask_sensitive(json.dumps(safe_query, ensure_ascii=False))[:MAX_META] or None,
                http_status=status, success=bool(status < 400 and body.get("ok") is True),
                duration_ms=max(0, int(duration_ms or 0)),
                result_summary=mask_sensitive(str(message))[:500], response_body=safe_body,
            ))
    except Exception:
        pass


def _gateway_log(*, provider, operation, method, path, meta, http_status, response_body, duration_ms, success, message):
    with session_scope() as db:
        db.add(ApiUsageLog(
            member_id=request_member_id(), provider=provider, operation=str(operation)[:100],
            method=str(method).upper()[:10], path=str(path)[:500],
            request_meta=mask_sensitive(json.dumps(meta, ensure_ascii=False, default=str))[:MAX_META],
            http_status=int(http_status or 503), success=bool(success),
            duration_ms=max(0, int(duration_ms)), result_summary=mask_sensitive(str(message))[:500],
            response_body=mask_sensitive(json.dumps(response_body, ensure_ascii=False, default=str))[:MAX_RESPONSE],
        ))


def record_kis_gateway_call(*, method, path, tr_id, label, attempt, request_data,
                            http_status, response_body, duration_ms, success, error=None) -> None:
    """공통 게이트웨이가 실제로 보낸 KIS 호출 1회를 기록한다(best effort)."""
    try:
        safe_request = _safe_value(request_data or {})
        safe_response = _safe_value(response_body or {})
        meta = {"kind": "kis_outbound", "inboundPath": request_path(), "trId": tr_id, "attempt": attempt, "request": safe_request}
        message = error or safe_response.get("msg1") or safe_response.get("error_description") or ("성공" if success else "KIS 호출 실패")
        _gateway_log(provider="KIS Gateway", operation=f"{label} [{tr_id}]", method=method, path=path, meta=meta,
                     http_status=http_status, response_body=safe_response, duration_ms=duration_ms, success=success, message=message)
        if not success:
            from app.services.error_analysis import record_error

            record_error(
                source="KIS_GATEWAY", severity="WARNING", status=int(http_status or 503),
                method=str(method).upper(), path=str(path), error_type="KisUpstreamError",
                message=str(message), request_meta=meta, member_id=request_member_id(),
            )
    except Exception:
        pass


def record_kb_gateway_call(*, method, path, tr_id, label, request_data,
                           http_status, response_body, duration_ms, success, error=None) -> None:
    """마스킹한 KB Open API 호출 1회를 기록한다."""
    try:
        meta = {"kind": "kb_outbound", "inboundPath": request_path(), "trId": tr_id, "attempt": 1, "request": _safe_value(request_data or {})}
        safe_response = _safe_value(response_body or {})
        message = error or safe_response.get("processMessage") or ("성공" if success else "KB증권 호출 실패")
        _gateway_log(provider="KB Gateway", operation=f"{label} [{tr_id}]", method=method, path=path, meta=meta,
                     http_status=http_status, response_body=safe_response, duration_ms=duration_ms, success=success, message=message)
    except Exception:
        pass


def record_alpaca_gateway_call(*, method, path, label, request_data,
                               http_status, response_body, duration_ms, success, error=None) -> None:
    """마스킹한 Alpaca Paper/Data API 호출 1회를 기록한다."""
    try:
        meta = {"kind": "alpaca_outbound", "inboundPath": request_path(), "attempt": 1, "request": _safe_value(request_data or {})}
        safe_response = _safe_value(response_body or {})
        message = error or safe_response.get("message") or safe_response.get("status") or ("성공" if success else "Alpaca 호출 실패")
        _gateway_log(provider="Alpaca Gateway", operation=label, method=method, path=path, meta=meta,
                     http_status=http_status, response_body=safe_response, duration_ms=duration_ms, success=success, message=message)
    except Exception:
        pass


_LAYERS = {"KIS Gateway": "KIS 외부 호출", "KB Gateway": "KB 외부 호출", "Alpaca Gateway": "Alpaca 외부 호출"}


def serialize_log(row: ApiUsageLog, detail: bool = False) -> dict:
    try:
        meta = json.loads(row.request_meta) if row.request_meta else {}
    except (TypeError, ValueError):
        meta = {}
    data = {
        "id": row.api_usage_log_id, "calledAt": row.called_at.isoformat() if row.called_at else None,
        "provider": row.provider, "operation": row.operation, "method": row.method, "path": row.path,
        "requestMeta": row.request_meta, "status": row.http_status, "success": bool(row.success),
        "durationMs": row.duration_ms, "summary": row.result_summary,
        "layer": _LAYERS.get(row.provider, "내 API"),
        "trId": meta.get("trId"), "attempt": meta.get("attempt"),
        "inboundPath": meta.get("inboundPath"),
    }
    if detail:
        data["responseBody"] = row.response_body
    return data


def member_history(db: Session, member_id: int, limit: int, providers: tuple[str, ...] | None = None) -> list[dict]:
    statement = select(ApiUsageLog).where(ApiUsageLog.member_id == member_id)
    if providers:
        statement = statement.where(ApiUsageLog.provider.in_(providers))
    rows = db.scalars(
        statement.order_by(ApiUsageLog.called_at.desc(), ApiUsageLog.api_usage_log_id.desc()).limit(limit)
    ).all()
    return [serialize_log(row) for row in rows]


def gateway_summary(history: list[dict], layer: str) -> dict:
    completed = [row for row in history if row["layer"] == layer]
    durations = [row["durationMs"] for row in completed if row["durationMs"] is not None]
    return {
        "total": len(history), "outbound": len(completed),
        "success": sum(1 for row in completed if row["success"]),
        "failure": sum(1 for row in completed if not row["success"]),
        "averageMs": round(sum(durations) / len(durations)) if durations else None,
    }
