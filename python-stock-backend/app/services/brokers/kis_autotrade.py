"""KIS 자동매매 주문 게이트웨이 — lumina-invest 같은 외부 스케줄러가 Open API(API Key)로 호출하는 실주문 경로.

계약: docs/contracts/kis-autotrade-api.md (세 저장소 공통).

구성
  - 환경 분리      : environment = "paper"(Testbed) | "real"(실전). URL·tr_id·자격증명·토큰 캐시를 환경별로 나눈다.
                     모든 호출은 kis.kis_request(base_url=..., headers_factory=...)를 거쳐 기존 레이트리밋·감사로그를 공유한다.
  - 승인 토큰      : 60초 1회용. API Key + 주문 의도(intent) 다이제스트에 묶어 DB(kis_order_approval)에 저장한다.
  - 멱등성         : (environment, client_order_id) 유니크. 같은 키 재요청은 새 주문 없이 저장 결과를 돌려준다.
  - 권한          : api_key.scopes 에 kis:order (운영자가 DB에서 부여)
  - 실전 가드      : KIS_REAL_ORDER_ENABLED=true + 계좌 소유자(KIS_REAL_OWNER_EMAIL) 일치 + 허용 종목(KIS_REAL_ALLOWED_SYMBOLS, 선택)
  - 회당 한도      : KIS_{PAPER,REAL}_MAX_ORDER_AMOUNT / _QUANTITY
  - 체결 기록      : kis_autotrade_order 에 요청/응답/상태를 남기고, 체결 조회 시 상태를 갱신한다.

이 모듈은 FastAPI에 의존하지 않는다. 오류는 BrokerApiError(status_code, code) 로 올리고 라우트가 JSON으로 바꾼다.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ApiKey, KisAutotradeOrder, KisOrderApproval
from app.services.brokers import kis as paper_gateway
from app.services.brokers import kis_real
from app.services.brokers.common import BrokerApiError, credential_source

Environment = Literal["paper", "real"]
ENVIRONMENTS: tuple[str, ...] = ("paper", "real")
APPROVAL_TTL_SECONDS = 60
CLIENT_ORDER_ID_MAX = 64

KIS_REAL_BASE_URL = kis_real.KIS_REAL_BASE_URL
KIS_PAPER_BASE_URL = paper_gateway.KIS_TESTBED_URL

# tr_id 매핑: paper ↔ real. (KIS Developers 2024 개편 기준 신 tr_id)
TR_IDS: dict[str, dict[str, str]] = {
    "order_buy":      {"paper": "VTTC0012U", "real": "TTTC0012U"},
    "order_sell":     {"paper": "VTTC0011U", "real": "TTTC0011U"},
    "order_rvsecncl": {"paper": "VTTC0013U", "real": "TTTC0013U"},
    "daily_ccld":     {"paper": "VTTC8001R", "real": "TTTC8001R"},
    "balance":        {"paper": "VTTC8434R", "real": "TTTC8434R"},
    "quote":          {"paper": "FHKST01010100", "real": "FHKST01010100"},
}

_order_locks: dict[str, threading.Lock] = {env: threading.Lock() for env in ENVIRONMENTS}


class AutotradeError(BrokerApiError):
    """계약서의 error 코드를 함께 가진 게이트웨이 오류."""

    def __init__(self, message: str, status_code: int = 400, code: str = "INVALID_REQUEST", **details: Any):
        super().__init__(message, status_code)
        self.code = code
        self.details = details


# ── 환경 ─────────────────────────────────────────────────────────────────────


def normalize_environment(raw: Any) -> str:
    env = str(raw or "paper").strip().lower()
    if env not in ENVIRONMENTS:
        raise AutotradeError("environment는 paper 또는 real 이어야 합니다.", 400, "INVALID_REQUEST")
    return env


def tr_id(operation: str, environment: str) -> str:
    return TR_IDS[operation][environment]


def _real_settings() -> dict[str, str]:
    """실전 자격증명: env 우선, 비어 있고 CREDENTIAL_SOURCE=aws 면 Secrets Manager(kis-real) 폴백."""
    settings = kis_real._settings()
    if (not settings["app_key"] or not settings["app_secret"] or not settings["account"]) and credential_source() == "aws":
        try:
            from app.services.aws_secret_store import get_credentials, get_parameter

            if not settings["app_key"] or not settings["app_secret"]:
                settings["app_key"], settings["app_secret"] = get_credentials("kis-real")
            if not settings["account"]:
                settings["account"] = (get_parameter("kis-real/account", required=False) or "").strip()
        except Exception as exc:  # boto3 미설치·권한 등: env 미설정과 같은 상태로 취급
            raise AutotradeError(f"실전 자격증명을 Secrets Manager에서 읽지 못했습니다: {exc}", 503, "KIS_CONFIG_REQUIRED") from exc
    return settings


def _real_headers_factory(settings: dict[str, str]):
    def _headers(tr: str) -> dict[str, str]:
        try:
            token = kis_real._access_token(settings)
        except kis_real.KisRealError as exc:
            raise AutotradeError(str(exc), exc.status_code, exc.code) from exc
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": settings["app_key"],
            "appsecret": settings["app_secret"],
            "tr_id": tr,
        }

    return _headers


def _account(environment: str) -> tuple[str, str]:
    if environment == "paper":
        return paper_gateway._kis_account()
    settings = _real_settings()
    account = settings["account"]
    if not account or "-" not in account:
        raise AutotradeError("KIS_REAL_ACCOUNT_NO('CANO-상품코드')가 설정되지 않았습니다.", 503, "KIS_CONFIG_REQUIRED")
    cano, _, product = account.partition("-")
    if not (cano.isdigit() and len(cano) == 8 and product.isdigit() and len(product) == 2):
        raise AutotradeError("KIS 실전 계좌번호는 '8자리 CANO-2자리 상품코드' 형식이어야 합니다.", 503, "KIS_CONFIG_REQUIRED")
    return cano, product


def request(environment: str, method: str, path: str, operation: str, *, params=None, payload=None, label: str,
            extra_headers=None, raise_for_api_error: bool = True):
    """환경에 맞는 URL/헤더로 kis_request를 호출한다. 레이트리밋·재시도·감사로그는 kis_request가 담당."""
    tr = tr_id(operation, environment)
    if environment == "paper":
        return paper_gateway.kis_request(method, path, tr, params=params, payload=payload, label=f"[paper] {label}",
                                         extra_headers=extra_headers, raise_for_api_error=raise_for_api_error)
    settings = _real_settings()
    if not settings["app_key"] or not settings["app_secret"]:
        raise AutotradeError("KIS_REAL_APP_KEY / KIS_REAL_APP_SECRET 이 설정되지 않았습니다.", 503, "KIS_CONFIG_REQUIRED")
    return paper_gateway.kis_request(method, path, tr, params=params, payload=payload, label=f"[real] {label}",
                                     extra_headers=extra_headers, raise_for_api_error=raise_for_api_error,
                                     base_url=KIS_REAL_BASE_URL, headers_factory=_real_headers_factory(settings), rate_key="real")


# ── 설정값 ───────────────────────────────────────────────────────────────────


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


SCOPE_ORDER = "kis:order"
SCOPE_ALL = "kis:*"
_SCOPE_SPLIT = re.compile(r"[\s,]+")


def key_scopes(db: Session | None, api_key_id: int) -> set[str]:
    """api_key.scopes 컬럼(공백/쉼표 구분). DB 미제공·컬럼 미존재(구 DB)면 빈 집합."""
    if db is None:
        return set()
    try:
        row = db.get(ApiKey, api_key_id)
    except Exception:  # 구 운영 DB에 scopes 컬럼이 아직 없을 때 등
        return set()
    raw = getattr(row, "scopes", "") or ""
    return {s.strip().lower() for s in _SCOPE_SPLIT.split(raw) if s.strip()}


def require_scope(api_key_id: int, db: Session | None = None) -> None:
    """KIS 자동매매 권한은 **api_key.scopes 컬럼만** 본다(`kis:order` 또는 `kis:*`). env 화이트리스트는 2026-10-02 폐기.

    부여: 운영자가 DB에서 `UPDATE api_key SET scopes='kis:order' WHERE api_key_id=?`. 셀프 서비스 API 없음.
    """
    if {SCOPE_ORDER, SCOPE_ALL} & key_scopes(db, api_key_id):
        return
    raise AutotradeError("이 API 키에는 KIS 자동매매 주문 권한이 없습니다. 운영자가 api_key.scopes 에 kis:order 를 부여해야 합니다.", 403, "SCOPE_FORBIDDEN")


def real_order_enabled() -> bool:
    return _env_flag("KIS_REAL_ORDER_ENABLED")


def real_owner_email() -> str:
    return os.environ.get("KIS_REAL_OWNER_EMAIL", "").strip().lower()


def require_real_owner(member_email) -> None:
    """실전 환경 접근 2중 가드: 서버 플래그 + 계좌 소유자 이메일. 취소·조회·주문 공통.

    ``member_email``은 문자열 또는 지연 호출(callable). 플래그가 꺼져 있으면 DB 조회(이메일) 없이 바로 거부한다.
    """
    if not real_order_enabled():
        raise AutotradeError("실전 주문이 비활성화되어 있습니다 (KIS_REAL_ORDER_ENABLED).", 403, "REAL_ORDER_DISABLED")
    owner = real_owner_email()
    email = member_email() if callable(member_email) else member_email
    if not owner or (email or "").strip().lower() != owner:
        raise AutotradeError("실전 계좌 소유자 API 키로만 실전 주문을 낼 수 있습니다.", 403, "REAL_ORDER_DISABLED")


def require_real_allowed(symbol: str, member_email: str | None) -> None:
    """실전 주문 3중 가드: require_real_owner + (선택) 종목 화이트리스트."""
    require_real_owner(member_email)
    allowed = {s.strip() for s in os.environ.get("KIS_REAL_ALLOWED_SYMBOLS", "").split(",") if s.strip()}
    if allowed and symbol not in allowed:
        raise AutotradeError(f"실전 허용 종목이 아닙니다: {symbol}", 403, "REAL_ORDER_DISABLED")


def limits(environment: str) -> dict[str, int]:
    prefix = "KIS_PAPER" if environment == "paper" else "KIS_REAL"
    default_amount = 10_000_000 if environment == "paper" else 1_000_000
    default_qty = 1000 if environment == "paper" else 100
    return {
        "max_amount": _env_int(f"{prefix}_MAX_ORDER_AMOUNT", default_amount),
        "max_quantity": _env_int(f"{prefix}_MAX_ORDER_QUANTITY", default_qty),
    }


# ── 주문 의도(intent) ─────────────────────────────────────────────────────────


def normalize_intent(payload: dict[str, Any]) -> dict[str, Any]:
    """요청 본문을 검증해 승인·주문·멱등키 계산에 공통으로 쓰는 intent 딕셔너리로 만든다."""
    environment = normalize_environment(payload.get("environment"))
    symbol = str(payload.get("symbol") or "").strip()
    if len(symbol) != 6 or not symbol.isdigit():
        raise AutotradeError("종목코드는 6자리 KRX 숫자 코드여야 합니다.", 400, "INVALID_REQUEST")
    side = str(payload.get("side") or "").strip().upper()
    if side not in {"BUY", "SELL"}:
        raise AutotradeError("side는 BUY 또는 SELL이어야 합니다.", 400, "INVALID_REQUEST")
    order_type = str(payload.get("orderType") or "MARKET").strip().upper()
    if order_type not in {"MARKET", "LIMIT"}:
        raise AutotradeError("orderType은 MARKET 또는 LIMIT만 지원합니다.", 400, "INVALID_REQUEST")
    quantity = payload.get("quantity")
    if isinstance(quantity, str) and quantity.strip().isdigit():
        quantity = int(quantity)
    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
        raise AutotradeError("quantity는 1 이상의 정수여야 합니다.", 400, "INVALID_REQUEST")
    price = payload.get("price") if payload.get("price") is not None else 0
    if isinstance(price, str) and price.strip().isdigit():
        price = int(price)
    if order_type == "LIMIT":
        if not isinstance(price, int) or isinstance(price, bool) or price <= 0:
            raise AutotradeError("LIMIT 주문은 price(1원 이상 정수)가 필요합니다.", 400, "INVALID_REQUEST")
        if paper_gateway._kis_round_down_to_tick(price) != price:
            raise AutotradeError("price가 KRX 호가 단위에 맞지 않습니다.", 400, "INVALID_REQUEST")
    else:
        price = 0
    client_order_id = str(payload.get("clientOrderId") or "").strip()
    if not 1 <= len(client_order_id) <= CLIENT_ORDER_ID_MAX:
        raise AutotradeError(f"clientOrderId는 1~{CLIENT_ORDER_ID_MAX}자여야 합니다.", 400, "INVALID_REQUEST")
    return {
        "environment": environment, "symbol": symbol, "side": side, "orderType": order_type,
        "quantity": quantity, "price": price, "clientOrderId": client_order_id,
    }


def intent_digest(intent: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(intent, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


# ── 승인 토큰 ────────────────────────────────────────────────────────────────


def issue_approval(db: Session, *, api_key_id: int, member_id: int, intent: dict[str, Any]) -> dict[str, Any]:
    token = secrets.token_urlsafe(32)
    row = KisOrderApproval(
        api_key_id=api_key_id, member_id=member_id, token_digest=_digest(token), intent_digest=intent_digest(intent),
        environment=intent["environment"], client_order_id=intent["clientOrderId"],
        expires_at=_now() + timedelta(seconds=APPROVAL_TTL_SECONDS),
    )
    db.add(row)
    db.flush()
    return {"approvalToken": token, "expiresIn": APPROVAL_TTL_SECONDS, "intent": intent}


def consume_approval(db: Session, *, api_key_id: int, token: str, intent: dict[str, Any]) -> None:
    """토큰 1회 소비. 만료·불일치·재사용·다른 API Key 발급분은 모두 403 APPROVAL_INVALID."""
    if not token:
        raise AutotradeError("approvalToken이 필요합니다. 먼저 /order-approval 을 호출하세요.", 403, "APPROVAL_INVALID")
    row = db.scalars(select(KisOrderApproval).where(KisOrderApproval.token_digest == _digest(token))).first()
    now = _now()
    valid = (
        row is not None
        and row.used_at is None
        and row.api_key_id == api_key_id
        and row.expires_at >= now
        and hmac.compare_digest(row.intent_digest, intent_digest(intent))
    )
    if not valid:
        raise AutotradeError("주문 승인이 만료되었거나 주문 내용이 변경되었거나 이미 사용되었습니다.", 403, "APPROVAL_INVALID")
    row.used_at = now
    db.flush()


# ── 시세·잔고 ────────────────────────────────────────────────────────────────


def _int(value: Any) -> int:
    try:
        return int(float(str(value or "0").replace(",", "")))
    except ValueError:
        return 0


def current_price(environment: str, symbol: str) -> int:
    _, body = request(environment, "GET", "/uapi/domestic-stock/v1/quotations/inquire-price", "quote",
                      params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol}, label="현재가 조회")
    return _int((body.get("output") or {}).get("stck_prpr"))


def get_balance(environment: str) -> dict[str, Any]:
    cano, product = _account(environment)
    _, body = request(
        environment, "GET", "/uapi/domestic-stock/v1/trading/inquire-balance", "balance",
        params={
            "CANO": cano, "ACNT_PRDT_CD": product, "AFHR_FLPR_YN": "N", "OFL_YN": "", "INQR_DVSN": "02",
            "UNPR_DVSN": "01", "FUND_STTL_ICLD_YN": "N", "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
        },
        label="잔고 조회", extra_headers={"custtype": "P"},
    )
    summary = (body.get("output2") or [{}])[0]
    holdings = [
        {
            "symbol": row.get("pdno"), "name": row.get("prdt_name"), "quantity": _int(row.get("hldg_qty")),
            "avgPrice": _int(row.get("pchs_avg_pric")), "currentPrice": _int(row.get("prpr")),
            "evalAmount": _int(row.get("evlu_amt")), "profitLoss": _int(row.get("evlu_pfls_amt")),
            "profitLossRate": float(str(row.get("evlu_pfls_rt") or "0").replace(",", "") or 0),
        }
        for row in (body.get("output1") or []) if row.get("pdno")
    ]
    return {
        "environment": environment, "cashBalance": _int(summary.get("dnca_tot_amt")),
        "totalEvalAmount": _int(summary.get("tot_evlu_amt")), "totalProfitLoss": _int(summary.get("evlu_pfls_smtl_amt")),
        "holdings": holdings,
    }


# ── 주문 ─────────────────────────────────────────────────────────────────────


def find_order(db: Session, environment: str, client_order_id: str) -> KisAutotradeOrder | None:
    return db.scalars(select(KisAutotradeOrder).where(
        KisAutotradeOrder.environment == environment, KisAutotradeOrder.client_order_id == client_order_id,
    )).first()


def find_order_by_no(db: Session, environment: str, order_no: str) -> KisAutotradeOrder | None:
    return db.scalars(select(KisAutotradeOrder).where(
        KisAutotradeOrder.environment == environment, KisAutotradeOrder.order_no == order_no,
    ).order_by(KisAutotradeOrder.kis_autotrade_order_id.desc())).first()


# 계약서(docs/contracts/kis-autotrade-api.md 2-2) 주문 응답 필드. lumina-invest 클라이언트 테스트가 같은 집합을 참조한다.
ORDER_RESPONSE_FIELDS = frozenset({
    "clientOrderId", "orderNo", "orgNo", "environment", "symbol", "side", "orderType", "quantity", "price",
    "estimatedAmount", "status", "filledQuantity", "avgFilledPrice", "kisMsgCd", "message", "orderTime", "updatedAt",
})


def today_records(environment: str, limit: int = 100) -> list[dict[str, Any]]:
    """오늘 게이트웨이로 낸 주문 기록(kis_autotrade_order)을 웹 화면의 당일 주문 목록 형식으로 돌려준다."""
    from datetime import date

    from app.core.database import session_scope

    with session_scope() as db:
        rows = db.scalars(select(KisAutotradeOrder).where(
            KisAutotradeOrder.environment == environment, KisAutotradeOrder.created_at >= datetime.combine(date.today(), datetime.min.time()),
        ).order_by(KisAutotradeOrder.kis_autotrade_order_id.desc()).limit(limit)).all()
        def _name(r):
            try:
                return json.loads(r.request_json or "{}").get("_name") or None
            except ValueError:
                return None

        return [{
            "orderNo": r.order_no, "symbol": r.symbol, "name": _name(r), "side": r.side,
            "orderQuantity": str(r.quantity), "filledQuantity": str(r.filled_quantity), "remainingQuantity": str(max(0, r.quantity - r.filled_quantity)),
            "orderPrice": str(r.price), "filledPrice": str(r.avg_filled_price), "orderTime": r.created_at.strftime("%H%M%S") if r.created_at else None,
            "status": r.status, "clientOrderId": r.client_order_id, "source": "gateway_record",
        } for r in rows]


def serialize_order(row: KisAutotradeOrder) -> dict[str, Any]:
    return {
        "clientOrderId": row.client_order_id, "orderNo": row.order_no, "orgNo": row.org_no,
        "environment": row.environment, "symbol": row.symbol, "side": row.side, "orderType": row.order_type,
        "quantity": row.quantity, "price": row.price, "estimatedAmount": row.estimated_amount,
        "status": row.status, "filledQuantity": row.filled_quantity, "avgFilledPrice": row.avg_filled_price,
        "kisMsgCd": row.kis_msg_cd, "message": row.kis_msg,
        "orderTime": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def place_order(db: Session, *, api_key_id: int, member_id: int, intent: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """검증 → 한도 → 사전 잔고 확인 → PENDING 기록 → KIS 주문 → 기록 갱신. (order, duplicate) 반환.

    승인 토큰 소비(consume_approval)와 실전 가드(require_real_allowed)는 호출자(라우트)가 먼저 수행한다.
    """
    environment, symbol, side = intent["environment"], intent["symbol"], intent["side"]
    quantity, order_type, price = intent["quantity"], intent["orderType"], intent["price"]

    existing = find_order(db, environment, intent["clientOrderId"])
    if existing is not None:
        return serialize_order(existing), True

    limit = limits(environment)
    if quantity > limit["max_quantity"]:
        raise AutotradeError(f"회당 주문수량 한도 {limit['max_quantity']:,}주를 초과했습니다.", 422, "LIMIT_EXCEEDED")
    reference_price = price if order_type == "LIMIT" else current_price(environment, symbol)
    if reference_price <= 0:
        raise AutotradeError("현재가를 확인할 수 없어 주문을 중단했습니다.", 502, "KIS_QUOTE_UNAVAILABLE")
    estimated_amount = reference_price * quantity
    if estimated_amount > limit["max_amount"]:
        raise AutotradeError(f"회당 주문금액 한도 {limit['max_amount']:,}원을 초과했습니다.", 422, "LIMIT_EXCEEDED")

    balance = get_balance(environment)
    if side == "BUY" and balance["cashBalance"] < estimated_amount:
        raise AutotradeError("주문 가능 예수금이 부족합니다.", 409, "INSUFFICIENT_BALANCE",
                             availableCash=balance["cashBalance"], requiredAmount=estimated_amount)
    if side == "SELL":
        holding = next((h for h in balance["holdings"] if h["symbol"] == symbol), None)
        if (holding or {}).get("quantity", 0) < quantity:
            raise AutotradeError("보유수량이 부족합니다.", 409, "INSUFFICIENT_HOLDINGS",
                                 heldQuantity=(holding or {}).get("quantity", 0), requestedQuantity=quantity)

    cano, product = _account(environment)
    kis_payload = {
        "CANO": cano, "ACNT_PRDT_CD": product, "PDNO": symbol,
        "ORD_DVSN": "01" if order_type == "MARKET" else "00",
        "ORD_QTY": str(quantity), "ORD_UNPR": str(price), "EXCG_ID_DVSN_CD": "KRX",
    }
    holding_before = int(next((h.get("quantity", 0) for h in balance["holdings"] if h["symbol"] == symbol), 0))
    # 종목명: 보유 중이면 잔고 응답에서, 아니면 기존 모의 시세(get_kis_quote)로는 알 수 없어 빈 값. 웹 당일주문 폴백 표시용.
    symbol_name = str(next((h.get("name") for h in balance["holdings"] if h["symbol"] == symbol), "") or "")
    row = KisAutotradeOrder(
        api_key_id=api_key_id, member_id=member_id, environment=environment, client_order_id=intent["clientOrderId"],
        symbol=symbol, side=side, order_type=order_type, quantity=quantity, price=price,
        estimated_amount=estimated_amount, status="PENDING",
        # _holding_before: Testbed 처럼 체결 목록을 못 받을 때 보유수량 변화로 체결을 추정하기 위한 기준값
        request_json=json.dumps({**kis_payload, "CANO": cano[:4] + "****", "_holding_before": holding_before, "_cash_before": balance["cashBalance"], "_name": symbol_name}, ensure_ascii=False),
    )
    db.add(row)
    db.commit()  # KIS 호출 전에 PENDING을 확정해 호출 중 장애가 나도 흔적을 남긴다.

    lock = _order_locks[environment]
    if not lock.acquire(blocking=False):
        row.status = "REJECTED"
        row.kis_msg = "동일 환경의 다른 주문을 처리 중"
        db.commit()
        raise AutotradeError("다른 KIS 주문을 처리 중입니다. 다음 사이클에 다시 시도하세요.", 409, "ORDER_IN_PROGRESS")
    try:
        _, body = request(
            environment, "POST", "/uapi/domestic-stock/v1/trading/order-cash",
            "order_buy" if side == "BUY" else "order_sell",
            payload=kis_payload, label=f"자동매매 {'매수' if side == 'BUY' else '매도'} 주문",
            extra_headers={"custtype": "P"}, raise_for_api_error=False,
        )
    except Exception as exc:
        row.status = "UNKNOWN"  # KIS가 받았는지 알 수 없다 → 호출자는 체결 조회로 확인해야 한다.
        row.kis_msg = f"KIS 연결 오류: {exc}"[:300]
        db.commit()
        raise AutotradeError("KIS 서버 응답을 받지 못했습니다. 주문 상태를 조회로 확인하세요.", 503, "KIS_CONNECTION_ERROR") from exc
    finally:
        lock.release()

    output = body.get("output") or {}
    row.kis_msg_cd = str(body.get("msg_cd") or "")[:20] or None
    row.kis_msg = str(body.get("msg1") or "")[:300] or None
    row.response_json = json.dumps({"rt_cd": body.get("rt_cd"), "msg_cd": body.get("msg_cd"), "msg1": body.get("msg1"), "output": output}, ensure_ascii=False)
    if str(body.get("rt_cd")) == "0":
        row.status = "ACCEPTED"
        row.order_no = str(output.get("ODNO") or "") or None
        row.org_no = str(output.get("KRX_FWDG_ORD_ORGNO") or "") or None
        db.commit()
        return serialize_order(row), False
    row.status = "REJECTED"
    db.commit()
    raise AutotradeError(row.kis_msg or "KIS가 주문을 거부했습니다.", 502, f"KIS_{row.kis_msg_cd or 'REJECTED'}", order=serialize_order(row))


# ── 체결 조회·취소 ────────────────────────────────────────────────────────────


def _status_from_ccld(ccld: dict[str, Any]) -> str:
    ordered, filled, remaining = _int(ccld.get("ord_qty")), _int(ccld.get("tot_ccld_qty")), _int(ccld.get("rmn_qty"))
    rejected, cancelled = _int(ccld.get("rjct_qty")), _int(ccld.get("cncl_cfrm_qty"))
    if rejected > 0 and filled == 0:
        return "REJECTED"
    if cancelled > 0 and remaining == 0 and filled == 0:
        return "CANCELLED"
    if ordered > 0 and filled >= ordered:
        return "FILLED"
    if filled > 0:
        return "PARTIALLY_FILLED"
    return "ACCEPTED"


def _normalize_ccld(environment: str, ccld: dict[str, Any]) -> dict[str, Any]:
    side_code = str(ccld.get("sll_buy_dvsn_cd") or "")
    side_name = str(ccld.get("sll_buy_dvsn_cd_name") or "")
    return {
        "orderNo": ccld.get("odno"), "orgNo": ccld.get("ord_gno_brno"), "environment": environment,
        "symbol": ccld.get("pdno"), "name": ccld.get("prdt_name"),
        "side": "SELL" if side_code == "01" or "매도" in side_name else "BUY",
        "status": _status_from_ccld(ccld),
        "orderedQuantity": _int(ccld.get("ord_qty")), "filledQuantity": _int(ccld.get("tot_ccld_qty")),
        "remainingQuantity": _int(ccld.get("rmn_qty")), "orderPrice": _int(ccld.get("ord_unpr")),
        "avgFilledPrice": _int(ccld.get("avg_prvs")), "orderTime": ccld.get("ord_tmd"),
        "updatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


CCLD_MAX_PAGES = 10  # 연속 조회 상한 (페이지당 KIS 기본 50건 안팎)


def list_orders(environment: str, start_yyyymmdd: str, end_yyyymmdd: str, *, symbol: str = "", open_only: bool = False) -> list[dict[str, Any]]:
    """기간 주문·체결 조회. KIS 연속조회(tr_cont F/M → 요청 헤더 tr_cont=N + CTX_AREA_FK100/NK100)를 끝까지 따라간다."""
    cano, product = _account(environment)
    fk, nk, tr_cont = "", "", ""
    rows: list[dict[str, Any]] = []
    for _page in range(CCLD_MAX_PAGES):
        response, body = request(
            environment, "GET", "/uapi/domestic-stock/v1/trading/inquire-daily-ccld", "daily_ccld",
            params={
                "CANO": cano, "ACNT_PRDT_CD": product, "INQR_STRT_DT": start_yyyymmdd, "INQR_END_DT": end_yyyymmdd,
                "SLL_BUY_DVSN_CD": "00", "INQR_DVSN": "00", "PDNO": symbol, "CCLD_DVSN": "02" if open_only else "00",
                "ORD_GNO_BRNO": "", "ODNO": "", "INQR_DVSN_3": "00", "INQR_DVSN_1": "",
                "CTX_AREA_FK100": fk, "CTX_AREA_NK100": nk,
            },
            label="주문·체결 조회", extra_headers={"custtype": "P", "tr_cont": tr_cont},
        )
        rows.extend(_normalize_ccld(environment, row) for row in (body.get("output1") or []) if row.get("odno"))
        headers = getattr(response, "headers", None) or {}
        cont = headers.get("tr_cont") if hasattr(headers, "get") else None
        if str(cont or "").upper() not in ("F", "M"):
            break
        fk, nk, tr_cont = str(body.get("ctx_area_fk100") or ""), str(body.get("ctx_area_nk100") or ""), "N"
        if not (fk or nk):
            break
    return rows


def list_today_orders(environment: str, *, symbol: str = "", open_only: bool = False) -> list[dict[str, Any]]:
    today = time.strftime("%Y%m%d", time.localtime())
    return list_orders(environment, today, today, symbol=symbol, open_only=open_only)


def sync_order_status(db: Session, environment: str, order_no: str) -> dict[str, Any]:
    """체결 조회로 상태를 확인하고 kis_autotrade_order 기록이 있으면 함께 갱신한다."""
    row = find_order_by_no(db, environment, order_no)
    today = time.strftime("%Y%m%d", time.localtime())
    # 기록이 있으면 주문 생성일부터 조회해 전일 미체결(익일 취소 포함)도 찾는다.
    start = row.created_at.strftime("%Y%m%d") if row is not None and row.created_at else today
    matches = [o for o in list_orders(environment, min(start, today), today, symbol=row.symbol if row else "")
               if str(o["orderNo"]).lstrip("0") == str(order_no).lstrip("0")]
    if not matches:
        if row is None:
            raise AutotradeError("해당 주문번호를 당일 주문에서 찾을 수 없습니다.", 404, "ORDER_NOT_FOUND")
        inferred = infer_status_from_holdings(db, row)
        if inferred is not None:
            return inferred
        return {**serialize_order(row), "status": row.status if row.status != "PENDING" else "UNKNOWN", "lookup": "not_in_daily_ccld"}
    latest = matches[0]
    if row is not None:
        row.status = latest["status"]
        row.filled_quantity = latest["filledQuantity"]
        row.avg_filled_price = latest["avgFilledPrice"]
        row.org_no = row.org_no or (str(latest.get("orgNo") or "") or None)
        db.commit()
        latest["clientOrderId"] = row.client_order_id
    return latest


OPEN_STATUSES = ("PENDING", "ACCEPTED", "PARTIALLY_FILLED", "CANCEL_REQUESTED", "UNKNOWN")


def infer_status_from_holdings(db: Session, row: KisAutotradeOrder) -> dict[str, Any] | None:
    """체결 목록(inquire-daily-ccld output1)을 못 받을 때(KIS 모의투자 제약) 보유수량 변화로 상태를 추정한다.

    조건: 주문 시점 보유수량(_holding_before)이 기록돼 있고, 같은 환경·종목의 열린 주문이 이 건 하나뿐일 때만.
    둘 이상이면 수량 변화를 어느 주문에 귀속할지 알 수 없어 추정하지 않는다(None).
    결과에는 ``lookup: "holdings_inference"`` 와 추정 근거를 넣는다. 체결가는 LIMIT 주문가(지정가 이하 체결 가정)로 둔다.
    """
    if row.status not in OPEN_STATUSES:
        return None
    try:
        before = json.loads(row.request_json or "{}").get("_holding_before")
    except ValueError:
        before = None
    if before is None:
        return None
    def _open_siblings():
        return db.scalars(select(KisAutotradeOrder).where(
            KisAutotradeOrder.environment == row.environment, KisAutotradeOrder.symbol == row.symbol,
            KisAutotradeOrder.status.in_(OPEN_STATUSES), KisAutotradeOrder.kis_autotrade_order_id != row.kis_autotrade_order_id,
        ).order_by(KisAutotradeOrder.kis_autotrade_order_id)).all()

    siblings = _open_siblings()
    balance = holding = None
    now_qty = 0
    if siblings:
        # 취소가 접수(4063xxxx)된 형제 주문은 자기 기준 보유수량 변화가 없으면 CANCELLED 로 먼저 정리해 막힘을 푼다.
        balance = get_balance(row.environment)
        holding = next((h for h in balance["holdings"] if h["symbol"] == row.symbol), None)
        now_qty = int((holding or {}).get("quantity", 0))
        # 형제의 체결 여부는 "다음 주문이 기록한 기준 보유수량"과 비교한다(다음 주문이 없으면 현재 보유수량).
        # 자동매매는 쿨다운으로 종목당 순차 주문이므로, 다음 주문 시점에 변화가 없었으면 그 형제는 체결 없이 취소된 것이다.
        def _before(o):
            try:
                return json.loads(o.request_json or "{}").get("_holding_before")
            except ValueError:
                return None

        chain = sorted([*siblings, row], key=lambda o: o.kis_autotrade_order_id)
        resolved = False
        for i, sib in enumerate(chain):
            if sib is row or sib.status != "CANCEL_REQUESTED" or not (sib.kis_msg_cd or "").startswith("4063"):
                continue
            sib_before = _before(sib)
            if sib_before is None:
                continue
            nxt = next((_before(o) for o in chain[i + 1:] if _before(o) is not None), None)
            baseline = int(nxt) if nxt is not None else now_qty
            sib_delta = (baseline - int(sib_before)) if sib.side == "BUY" else (int(sib_before) - baseline)
            if sib_delta <= 0:
                sib.status = "CANCELLED"
                resolved = True
        if resolved:
            db.commit()
            siblings = _open_siblings()
    if siblings:
        return {**serialize_order(row), "lookup": "ambiguous_open_orders", "openOrdersSameSymbol": len(siblings) + 1}
    if balance is None:
        balance = get_balance(row.environment)
        holding = next((h for h in balance["holdings"] if h["symbol"] == row.symbol), None)
        now_qty = int((holding or {}).get("quantity", 0))
    delta = (now_qty - int(before)) if row.side == "BUY" else (int(before) - now_qty)
    previous = row.status
    if delta >= row.quantity:
        row.status, row.filled_quantity = "FILLED", row.quantity
        row.avg_filled_price = row.price if row.order_type == "LIMIT" and row.price else int((holding or {}).get("currentPrice", 0))
    elif delta > 0:
        row.status, row.filled_quantity = "PARTIALLY_FILLED", delta
        row.avg_filled_price = row.price if row.order_type == "LIMIT" and row.price else int((holding or {}).get("currentPrice", 0))
    elif previous == "CANCEL_REQUESTED" and (row.kis_msg_cd or "").startswith("4063"):
        row.status = "CANCELLED"   # 취소가 접수(40630000)됐고 보유수량 변화가 없다 → 취소 완료로 본다
    if row.status != previous:
        db.commit()
    return {**serialize_order(row), "lookup": "holdings_inference",
            "inference": {"holdingBefore": int(before), "holdingNow": now_qty, "delta": delta, "basis": "inquire-balance"}}


def cancel_order(db: Session, environment: str, order_no: str) -> dict[str, Any]:
    row = find_order_by_no(db, environment, order_no)
    org_no = row.org_no if row else None
    if not org_no:
        found = [o for o in list_today_orders(environment, open_only=True) if str(o["orderNo"]).lstrip("0") == str(order_no).lstrip("0")]
        org_no = str((found[0].get("orgNo") if found else "") or "")
    if not org_no:
        raise AutotradeError("취소에 필요한 주문 조직번호(orgNo)를 찾을 수 없습니다. 이미 체결·취소된 주문일 수 있습니다.", 404, "ORDER_NOT_FOUND")
    cano, product = _account(environment)
    _, body = request(
        environment, "POST", "/uapi/domestic-stock/v1/trading/order-rvsecncl", "order_rvsecncl",
        payload={
            "CANO": cano, "ACNT_PRDT_CD": product, "KRX_FWDG_ORD_ORGNO": org_no, "ORGN_ODNO": order_no,
            "ORD_DVSN": "00", "RVSE_CNCL_DVSN_CD": "02", "ORD_QTY": "0", "ORD_UNPR": "0",
            "QTY_ALL_ORD_YN": "Y", "EXCG_ID_DVSN_CD": "KRX",
        },
        label="자동매매 주문 취소", extra_headers={"custtype": "P"}, raise_for_api_error=False,
    )
    ok = str(body.get("rt_cd")) == "0"
    if row is not None:
        row.status = "CANCEL_REQUESTED" if ok else row.status
        row.kis_msg_cd = str(body.get("msg_cd") or "")[:20] or row.kis_msg_cd
        row.kis_msg = str(body.get("msg1") or "")[:300] or row.kis_msg
        db.commit()
    if not ok:
        raise AutotradeError(body.get("msg1") or "KIS가 취소를 거부했습니다.", 502, f"KIS_{body.get('msg_cd') or 'CANCEL_REJECTED'}")
    result = serialize_order(row) if row else {"orderNo": order_no, "orgNo": org_no, "environment": environment}
    result["status"] = "CANCEL_REQUESTED"
    result["message"] = body.get("msg1")
    return result


def ensure_kis_autotrade_tables() -> None:
    from app.core.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine, tables=[KisOrderApproval.__table__, KisAutotradeOrder.__table__], checkfirst=True)
    # 기존 운영 DB(MariaDB)의 api_key 에 scopes 컬럼 보정. SQLite 등 미지원 방언은 무시한다.
    try:
        from sqlalchemy import text

        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE api_key ADD COLUMN IF NOT EXISTS scopes VARCHAR(200) NOT NULL DEFAULT ''"))
    except Exception:
        pass
