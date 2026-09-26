"""Persist safe audit records for external broker/exchange API test calls."""
import json
import time

from flask import Blueprint, has_request_context, jsonify, request, session
from sqlalchemy import text

from db import engine, session_scope
from error_analysis import mask_sensitive
from models import ApiUsageLog

api_usage_bp = Blueprint("api_usage", __name__, url_prefix="/api/api-usage")
MAX_META = 2000
MAX_RESPONSE = 12000
_SECRET_KEYS = {
    "authorization", "appkey", "app_key", "appsecret", "app_secret", "secret",
    "token", "access_token", "password", "cano", "account", "account_no",
}


def _safe_value(value, key=""):
    """Recursively remove credentials and full account numbers before persistence."""
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


def ensure_api_usage_table():
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


def provider_for_path(path):
    if "/kis/" in path or "/kis-chart/" in path or "/kis-explorer/" in path or "/kis-real/" in path: return "KIS"
    if "/kb/" in path: return "KB증권"
    if "alpaca" in path: return "Alpaca"
    if "/binance/" in path: return "Binance"
    if "/korbit/" in path: return "Korbit"
    if "/secrets/" in path or "/ssm/" in path: return "AWS Secrets Manager"
    return "외부 API"


def record_api_usage(response, started_at):
    """Best effort only: never make a successful external call fail because logging failed."""
    try:
        body = response.get_json(silent=True) or {}
        safe_body = mask_sensitive(json.dumps(body, ensure_ascii=False, default=str))[:MAX_RESPONSE]
        message = body.get("message") or body.get("error") or ("성공" if body.get("ok") else response.status)
        query = {key: value for key, value in request.args.items() if key.lower() not in {"token", "key", "secret", "password"}}
        with session_scope() as db:
            db.add(ApiUsageLog(
                member_id=session.get("member_id"), provider=provider_for_path(request.path),
                operation=request.endpoint or request.path.rsplit("/", 1)[-1], method=request.method,
                path=request.path, request_meta=mask_sensitive(json.dumps(query, ensure_ascii=False))[:MAX_META] or None,
                http_status=response.status_code, success=bool(response.status_code < 400 and body.get("ok") is True),
                duration_ms=max(0, int((time.perf_counter() - started_at) * 1000)),
                result_summary=mask_sensitive(str(message))[:500], response_body=safe_body,
            ))
    except Exception:
        pass


def record_kis_gateway_call(*, method, path, tr_id, label, attempt, request_data,
                            http_status, response_body, duration_ms, success, error=None):
    """Persist one real outbound KIS attempt made by the common gateway.

    This is intentionally best-effort. Audit/database failures must never alter
    the trading API result returned to the caller.
    """
    try:
        member_id = session.get("member_id") if has_request_context() else None
        inbound_path = request.path if has_request_context() else "CLI/background"
        safe_request = _safe_value(request_data or {})
        safe_response = _safe_value(response_body or {})
        meta = {
            "kind": "kis_outbound", "inboundPath": inbound_path,
            "trId": tr_id, "attempt": attempt, "request": safe_request,
        }
        message = error or safe_response.get("msg1") or safe_response.get("error_description") or ("성공" if success else "KIS 호출 실패")
        with session_scope() as db:
            db.add(ApiUsageLog(
                member_id=member_id, provider="KIS Gateway",
                operation=f"{label} [{tr_id}]"[:100], method=str(method).upper()[:10],
                path=str(path)[:500],
                request_meta=mask_sensitive(json.dumps(meta, ensure_ascii=False, default=str))[:MAX_META],
                http_status=int(http_status or 503), success=bool(success),
                duration_ms=max(0, int(duration_ms)), result_summary=mask_sensitive(str(message))[:500],
                response_body=mask_sensitive(json.dumps(safe_response, ensure_ascii=False, default=str))[:MAX_RESPONSE],
            ))
        if not success:
            from error_analysis import record_error
            record_error(
                source="KIS_GATEWAY", severity="WARNING", status=int(http_status or 503),
                method=str(method).upper(), path=str(path), error_type="KisUpstreamError",
                message=str(message), request_meta=meta, member_id=member_id,
            )
    except Exception:
        pass


def record_kb_gateway_call(*, method, path, tr_id, label, request_data,
                           http_status, response_body, duration_ms, success, error=None):
    """Persist a masked KB Open API outbound attempt."""
    try:
        member_id = session.get("member_id") if has_request_context() else None
        inbound_path = request.path if has_request_context() else "CLI/background"
        meta = {
            "kind": "kb_outbound", "inboundPath": inbound_path,
            "trId": tr_id, "attempt": 1, "request": _safe_value(request_data or {}),
        }
        safe_response = _safe_value(response_body or {})
        message = error or safe_response.get("processMessage") or ("성공" if success else "KB증권 호출 실패")
        with session_scope() as db:
            db.add(ApiUsageLog(
                member_id=member_id, provider="KB Gateway", operation=f"{label} [{tr_id}]"[:100],
                method=str(method).upper()[:10], path=str(path)[:500],
                request_meta=mask_sensitive(json.dumps(meta, ensure_ascii=False, default=str))[:MAX_META],
                http_status=int(http_status or 503), success=bool(success),
                duration_ms=max(0, int(duration_ms)), result_summary=mask_sensitive(str(message))[:500],
                response_body=mask_sensitive(json.dumps(safe_response, ensure_ascii=False, default=str))[:MAX_RESPONSE],
            ))
    except Exception:
        pass


def record_alpaca_gateway_call(*, method, path, label, request_data,
                               http_status, response_body, duration_ms, success, error=None):
    """Persist a masked Alpaca Paper/Data API outbound attempt."""
    try:
        member_id = session.get("member_id") if has_request_context() else None
        inbound_path = request.path if has_request_context() else "CLI/background"
        meta = {
            "kind": "alpaca_outbound", "inboundPath": inbound_path,
            "attempt": 1, "request": _safe_value(request_data or {}),
        }
        safe_response = _safe_value(response_body or {})
        message = error or safe_response.get("message") or safe_response.get("status") or ("성공" if success else "Alpaca 호출 실패")
        with session_scope() as db:
            db.add(ApiUsageLog(
                member_id=member_id, provider="Alpaca Gateway", operation=str(label)[:100],
                method=str(method).upper()[:10], path=str(path)[:500],
                request_meta=mask_sensitive(json.dumps(meta, ensure_ascii=False, default=str))[:MAX_META],
                http_status=int(http_status or 503), success=bool(success),
                duration_ms=max(0, int(duration_ms)), result_summary=mask_sensitive(str(message))[:500],
                response_body=mask_sensitive(json.dumps(safe_response, ensure_ascii=False, default=str))[:MAX_RESPONSE],
            ))
    except Exception:
        pass


def _serialize(row, detail=False):
    try:
        meta = json.loads(row.request_meta) if row.request_meta else {}
    except (TypeError, ValueError):
        meta = {}
    data = {
        "id": row.api_usage_log_id, "calledAt": row.called_at.isoformat() if row.called_at else None,
        "provider": row.provider, "operation": row.operation, "method": row.method, "path": row.path,
        "requestMeta": row.request_meta, "status": row.http_status, "success": bool(row.success),
        "durationMs": row.duration_ms, "summary": row.result_summary,
        "layer": "KIS 외부 호출" if row.provider == "KIS Gateway" else "KB 외부 호출" if row.provider == "KB Gateway" else "Alpaca 외부 호출" if row.provider == "Alpaca Gateway" else "내 API",
        "trId": meta.get("trId"), "attempt": meta.get("attempt"),
        "inboundPath": meta.get("inboundPath"),
    }
    if detail: data["responseBody"] = row.response_body
    return data


@api_usage_bp.get("/history")
def list_history():
    member_id = session.get("member_id")
    if not member_id:
        return jsonify({"error": "API 사용이력은 로그인 후 조회할 수 있습니다."}), 401
    limit = max(1, min(int(request.args.get("limit", 500)), 1000))
    with session_scope() as db:
        rows = db.query(ApiUsageLog).filter(ApiUsageLog.member_id == member_id).order_by(
            ApiUsageLog.called_at.desc(), ApiUsageLog.api_usage_log_id.desc()).limit(limit).all()
        return jsonify({"history": [_serialize(row) for row in rows]})


@api_usage_bp.get("/kis-history")
def list_kis_history():
    member_id = session.get("member_id")
    if not member_id:
        return jsonify({"error": "KIS API 이력은 로그인 후 조회할 수 있습니다."}), 401
    try:
        limit = max(1, min(int(request.args.get("limit", 1000)), 2000))
    except ValueError:
        return jsonify({"error": "limit은 숫자여야 합니다."}), 400
    with session_scope() as db:
        rows = db.query(ApiUsageLog).filter(
            ApiUsageLog.member_id == member_id,
            ApiUsageLog.provider.in_(("KIS", "KIS Gateway")),
        ).order_by(ApiUsageLog.called_at.desc(), ApiUsageLog.api_usage_log_id.desc()).limit(limit).all()
        history = [_serialize(row) for row in rows]
        completed = [row for row in history if row["layer"] == "KIS 외부 호출"]
        durations = [row["durationMs"] for row in completed if row["durationMs"] is not None]
        return jsonify({
            "history": history,
            "summary": {
                "total": len(history), "outbound": len(completed),
                "success": sum(1 for row in completed if row["success"]),
                "failure": sum(1 for row in completed if not row["success"]),
                "averageMs": round(sum(durations) / len(durations)) if durations else None,
            },
        })


@api_usage_bp.get("/kb-history")
def list_kb_history():
    member_id = session.get("member_id")
    if not member_id:
        return jsonify({"error": "KB API 이력은 로그인 후 조회할 수 있습니다."}), 401
    try:
        limit = max(1, min(int(request.args.get("limit", 1000)), 2000))
    except ValueError:
        return jsonify({"error": "limit은 숫자여야 합니다."}), 400
    with session_scope() as db:
        rows = db.query(ApiUsageLog).filter(
            ApiUsageLog.member_id == member_id,
            ApiUsageLog.provider.in_(("KB증권", "KB Gateway")),
        ).order_by(ApiUsageLog.called_at.desc(), ApiUsageLog.api_usage_log_id.desc()).limit(limit).all()
        history = [_serialize(row) for row in rows]
        completed = [row for row in history if row["layer"] == "KB 외부 호출"]
        durations = [row["durationMs"] for row in completed if row["durationMs"] is not None]
        return jsonify({"history": history, "summary": {
            "total": len(history), "outbound": len(completed),
            "success": sum(1 for row in completed if row["success"]),
            "failure": sum(1 for row in completed if not row["success"]),
            "averageMs": round(sum(durations) / len(durations)) if durations else None,
        }})


@api_usage_bp.get("/alpaca-history")
def list_alpaca_history():
    member_id = session.get("member_id")
    if not member_id:
        return jsonify({"error": "Alpaca API 이력은 로그인 후 조회할 수 있습니다."}), 401
    try:
        limit = max(1, min(int(request.args.get("limit", 1000)), 2000))
    except ValueError:
        return jsonify({"error": "limit은 숫자여야 합니다."}), 400
    with session_scope() as db:
        rows = db.query(ApiUsageLog).filter(
            ApiUsageLog.member_id == member_id,
            ApiUsageLog.provider.in_(("Alpaca", "Alpaca Gateway")),
        ).order_by(ApiUsageLog.called_at.desc(), ApiUsageLog.api_usage_log_id.desc()).limit(limit).all()
        history = [_serialize(row) for row in rows]
        completed = [row for row in history if row["layer"] == "Alpaca 외부 호출"]
        durations = [row["durationMs"] for row in completed if row["durationMs"] is not None]
        return jsonify({"history": history, "summary": {
            "total": len(history), "outbound": len(completed),
            "success": sum(1 for row in completed if row["success"]),
            "failure": sum(1 for row in completed if not row["success"]),
            "averageMs": round(sum(durations) / len(durations)) if durations else None,
        }})


@api_usage_bp.get("/history/<int:log_id>")
def get_history(log_id):
    member_id = session.get("member_id")
    if not member_id:
        return jsonify({"error": "API 사용이력은 로그인 후 조회할 수 있습니다."}), 401
    with session_scope() as db:
        row = db.query(ApiUsageLog).filter(ApiUsageLog.api_usage_log_id == log_id, ApiUsageLog.member_id == member_id).first()
        if not row:
            return jsonify({"error": "API 사용이력을 찾을 수 없습니다."}), 404
        return jsonify({"log": _serialize(row, detail=True)})
