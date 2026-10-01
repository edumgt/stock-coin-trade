"""시스템 오류 수집(서버·브라우저)과 진단 조회."""

from __future__ import annotations

import hashlib
import json
import re

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.database import engine, session_scope
from app.models import Member, SystemErrorLog

MAX_MESSAGE = 2000
MAX_STACK = 12000
MAX_META = 5000

SENSITIVE_PATTERN = re.compile(
    r"(?i)((?:app[_ -]?(?:key|secret)|api[_ -]?key|authorization|token|password|passwd|secret)[\"']?\s*(?:[:=]|%3A)\s*[\"']?)([^\s,;\"'}&]+)"
)
BEARER_PATTERN = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+\-/=]+")


def mask_sensitive(value) -> str:
    """접근 토큰·API 키·비밀번호가 진단 데이터에 남지 않게 한다."""
    raw = str(value or "")
    raw = BEARER_PATTERN.sub(r"\1***", raw)
    raw = SENSITIVE_PATTERN.sub(r"\1***", raw)
    return raw


def _cut(value, limit):
    return mask_sensitive(value)[:limit]


def _reason(source, status, error_type, message):
    if source == "CLIENT":
        return "브라우저 JavaScript 실행·리소스 로딩·비동기 처리 중 오류가 보고되었습니다. 스택과 발생 URL을 확인하세요."
    if status == 400:
        return "요청 값 또는 형식이 API 요구사항과 맞지 않습니다. 입력 값과 필수 파라미터를 확인하세요."
    if status == 401:
        return "인증 정보가 없거나 세션이 만료되었습니다. 로그인 상태와 인증 헤더를 확인하세요."
    if status == 403:
        return "현재 계정 또는 API 키에 이 작업을 수행할 권한이 없습니다. 권한과 접근 정책을 확인하세요."
    if status == 404:
        return "요청한 경로 또는 대상 데이터를 찾을 수 없습니다. URL·식별자·배포된 정적 파일을 확인하세요."
    if status == 429:
        return "요청 횟수 제한에 도달했습니다. 재시도 간격과 외부 API의 rate limit을 확인하세요."
    if status and status >= 500:
        return "서버 또는 연동 서비스에서 처리하지 못한 오류입니다. 메시지·스택·외부 API 응답을 확인하세요."
    return "응답 상태가 정상 범위(2xx/3xx)가 아닙니다. 메시지와 요청 정보를 확인하세요."


def record_error(*, source, message, severity="ERROR", status=None, error_type=None,
                 stack_trace=None, method=None, path=None, request_meta=None, member_id=None) -> None:
    """오류 저장은 서비스 중인 요청을 절대 방해하지 않아야 한다(best effort)."""
    try:
        clean_message = _cut(message, MAX_MESSAGE) or "오류 메시지가 제공되지 않았습니다."
        clean_stack = _cut(stack_trace, MAX_STACK) or None
        clean_path = _cut(path, 500) or None
        clean_type = _cut(error_type, 160) or None
        clean_meta = _cut(json.dumps(request_meta, ensure_ascii=False, default=str), MAX_META) if request_meta else None
        fingerprint = hashlib.sha256(f"{source}|{status}|{clean_type}|{clean_message}".encode()).hexdigest()
        with session_scope() as db:
            db.add(SystemErrorLog(
                source=source, severity=severity, http_status=status, method=_cut(method, 10) or None,
                path=clean_path, error_type=clean_type, message=clean_message,
                reason=_reason(source, status, clean_type, clean_message), stack_trace=clean_stack,
                request_meta=clean_meta, fingerprint=fingerprint, member_id=member_id,
            ))
    except Exception:
        # 진단은 의도적으로 best-effort다. 복구 가능한 오류를 장애로 바꾸지 않는다.
        pass


def ensure_error_analysis_table() -> None:
    statement = """CREATE TABLE IF NOT EXISTS system_error_log (
      system_error_log_id BIGINT AUTO_INCREMENT PRIMARY KEY,
      occurred_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      source VARCHAR(20) NOT NULL,
      severity VARCHAR(10) NOT NULL DEFAULT 'ERROR',
      http_status INT NULL,
      method VARCHAR(10) NULL,
      path VARCHAR(500) NULL,
      error_type VARCHAR(160) NULL,
      message TEXT NOT NULL,
      reason TEXT NULL,
      stack_trace TEXT NULL,
      request_meta TEXT NULL,
      fingerprint VARCHAR(64) NULL,
      member_id BIGINT NULL,
      KEY idx_system_error_occurred (occurred_at),
      KEY idx_system_error_source_status (source, http_status),
      KEY idx_system_error_fingerprint (fingerprint),
      CONSTRAINT fk_system_error_member FOREIGN KEY (member_id) REFERENCES member(member_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
    with engine.begin() as conn:
        conn.execute(text(statement))


def is_member(db: Session, member_id: int | None) -> bool:
    return bool(member_id) and db.get(Member, member_id) is not None


def serialize_log(row: SystemErrorLog, detailed: bool = False) -> dict:
    data = {
        "id": row.system_error_log_id, "occurredAt": row.occurred_at.isoformat() if row.occurred_at else None,
        "source": row.source, "severity": row.severity, "status": row.http_status,
        "method": row.method, "path": row.path, "type": row.error_type,
        "message": row.message, "reason": row.reason, "fingerprint": row.fingerprint,
    }
    if detailed:
        data.update({"stackTrace": row.stack_trace, "requestMeta": json.loads(row.request_meta) if row.request_meta else None})
    return data


def list_logs(db: Session, limit: int, source: str, status: str) -> list[dict]:
    statement = select(SystemErrorLog)
    if source in {"SERVER", "CLIENT"}:
        statement = statement.where(SystemErrorLog.source == source)
    if status.isdigit():
        statement = statement.where(SystemErrorLog.http_status == int(status))
    rows = db.scalars(
        statement.order_by(SystemErrorLog.occurred_at.desc(), SystemErrorLog.system_error_log_id.desc()).limit(limit)
    ).all()
    return [serialize_log(row) for row in rows]
