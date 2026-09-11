"""Persist safe audit records for external broker/exchange API test calls."""
import json
import time

from flask import Blueprint, jsonify, request, session
from sqlalchemy import text

from db import engine, session_scope
from error_analysis import mask_sensitive
from models import ApiUsageLog

api_usage_bp = Blueprint("api_usage", __name__, url_prefix="/api/api-usage")
MAX_META = 2000
MAX_RESPONSE = 12000


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
    if "/kis/" in path: return "KIS"
    if "/kb/" in path: return "KB증권"
    if "alpaca" in path: return "Alpaca"
    if "/binance/" in path: return "Binance"
    if "/korbit/" in path: return "Korbit"
    if "/ssm/" in path: return "AWS SSM"
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


def _serialize(row, detail=False):
    data = {
        "id": row.api_usage_log_id, "calledAt": row.called_at.isoformat() if row.called_at else None,
        "provider": row.provider, "operation": row.operation, "method": row.method, "path": row.path,
        "requestMeta": row.request_meta, "status": row.http_status, "success": bool(row.success),
        "durationMs": row.duration_ms, "summary": row.result_summary,
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
