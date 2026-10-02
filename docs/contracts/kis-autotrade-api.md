# KIS 자동매매 연동 API 계약 (v0.1, 2026-10-02)

> 이 문서는 domain-rag-lab / lumina-invest / stock-coin-trade 세 저장소에 **동일한 내용**으로 복사되어 있다.
> 변경 시 세 저장소를 함께 갱신하고 버전을 올린다. 변경 이력은 문서 끝에 적는다.
> 연동 방식은 **저장소별 독립 배포 + HTTP API**다. 상대 저장소 코드 import·DB 직접 접근은 금지한다.

## 0. 공통 규약

| 항목 | 규칙 |
|------|------|
| 인증 | `Authorization: Bearer <api_key>` (stock-coin-trade Open API), `X-API-Key: <key>` (domain-rag-lab 전략 API) |
| 환경 | `environment`: `"paper"`(KIS 모의 Testbed) 또는 `"real"`(KIS 실전). 생략 시 `paper`. `real`은 서버 플래그 `KIS_REAL_ORDER_ENABLED=true`가 없으면 항상 거부 |
| 종목코드 | KRX 6자리 숫자 문자열 (`"005930"`). lumina 내부 `005930.KS` 표기는 게이트웨이 호출 전 접미사를 제거한다 |
| 방향 | `side`: `"BUY"` / `"SELL"` (대문자). lumina 내부 `buy`/`sell`은 게이트웨이가 변환 |
| 주문유형 | `orderType`: `"MARKET"` / `"LIMIT"`. LIMIT은 `price`(원, 정수, 호가 단위 일치) 필수 |
| 멱등키 | `clientOrderId`: 호출자가 만드는 1~64자 문자열. 같은 키로 재요청하면 **새 주문을 내지 않고** 저장된 결과를 돌려준다 |
| 시간 | ISO 8601, KST(+09:00) 명시 |
| 오류 응답 | `{"ok": false, "error": "<CODE>", "message": "<사람이 읽는 메시지>"}` + HTTP 상태 |
| 재시도 | 주문(POST /orders)은 **재시도 금지**. 승인 토큰 발급·조회·잔고는 재시도 가능 |

## 1. 전략 스펙 API — domain-rag-lab → lumina-invest

Base: `https://<domain-rag-lab>/backtests`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/strategies` | 백테스트 합격 전략 목록 |
| GET | `/strategies/{strategy_id}` | 최신 합격 버전 스펙 |
| GET | `/strategies/{strategy_id}/versions/{version}` | 특정 버전 스펙 |

### StrategySpec (응답 본문)
```json
{
  "strategy_id": "ma_cross_kr_large",
  "version": 3,
  "name": "이동평균 교차 (대형주)",
  "universe": ["005930", "000660"],
  "timeframe": "1d",
  "entry": {"indicator": "ma_cross", "params": {"short_window": 20, "long_window": 60}, "condition": "short_above_long"},
  "exit":  {"indicator": "ma_cross", "params": {"short_window": 20, "long_window": 60}, "condition": "short_below_long"},
  "signal_weights": {"technical": 0.7, "lightgbm": 0.3, "buy_threshold": 0.6, "sell_threshold": -0.6},
  "position_sizing": {"max_position_pct": 30.0, "max_symbols": 5},
  "backtest_result": {
    "period": {"start": "2021-01-01", "end": "2026-09-30"},
    "annualized_return_pct": 12.4, "max_drawdown_pct": -14.2, "sharpe_ratio": 0.91,
    "trade_count": 48, "win_rate_pct": 56.3, "engine": "lean"
  },
  "acceptance": {"passed": true, "criteria": {"max_drawdown_pct_lte": 20, "trade_count_gte": 30, "annualized_return_pct_gt": 0}},
  "created_at": "2026-10-02T12:00:00+09:00"
}
```
목록 응답: `{"strategies": [ {strategy_id, version, name, backtest_result 요약, created_at} ]}`

## 2. 주문 API — lumina-invest → stock-coin-trade

Base: `https://<stock-coin-trade>/openapi/v1/kis`  (기존 `/openapi/v1/orders`는 **가상 주문**이므로 사용하지 않는다)

### 2-1. 승인 토큰 발급 `POST /order-approval`
요청:
```json
{"environment": "paper", "symbol": "005930", "side": "BUY", "orderType": "LIMIT", "quantity": 3, "price": 71000, "clientOrderId": "u1:005930:BUY:20261002:1"}
```
응답 200:
```json
{"ok": true, "approvalToken": "<opaque>", "expiresIn": 60, "intent": {"environment":"paper","symbol":"005930","side":"BUY","orderType":"LIMIT","quantity":3,"price":71000,"clientOrderId":"..."}}
```
- 토큰은 **발급 API Key + 주문 의도(intent) 해시**에 묶인다. 의도의 어떤 필드든 바뀌면 주문 단계에서 거부된다.
- 60초 후 만료, 1회 사용 후 소멸.

### 2-2. 주문 `POST /orders`
요청: 2-1과 동일한 본문 + `"approvalToken": "<opaque>"`
응답 200 (접수):
```json
{"ok": true, "order": {
  "clientOrderId": "u1:005930:BUY:20261002:1", "orderNo": "0000123456", "orgNo": "91252",
  "environment": "paper", "symbol": "005930", "side": "BUY", "orderType": "LIMIT",
  "quantity": 3, "price": 71000, "estimatedAmount": 213000,
  "status": "ACCEPTED", "orderTime": "2026-10-02T10:31:05+09:00", "message": "..."
}, "duplicate": false}
```
- 같은 `clientOrderId` 재요청 → 200 + 저장된 `order` + `"duplicate": true` (승인 토큰 검증은 생략하지 않는다)
- 실패 시 `ok:false`. KIS가 `rt_cd != "0"`을 돌려주면 HTTP 502 + `error: "KIS_<msg_cd>"`

### 2-3. 체결 상태 `GET /orders/{orderNo}?environment=paper`
응답 200:
```json
{"ok": true, "order": {"orderNo": "0000123456", "clientOrderId": "...", "environment": "paper", "symbol": "005930", "side": "BUY",
  "status": "FILLED", "orderedQuantity": 3, "filledQuantity": 3, "remainingQuantity": 0,
  "orderPrice": 71000, "avgFilledPrice": 70900, "updatedAt": "2026-10-02T10:31:40+09:00"}}
```

### 2-4. 당일 주문 목록 `GET /orders?environment=paper&status=OPEN|ALL`
응답: `{"ok": true, "date": "20261002", "orders": [ ...2-3의 order... ]}`

### 2-5. 취소 `DELETE /orders/{orderNo}?environment=paper`
응답: `{"ok": true, "order": {..., "status": "CANCEL_REQUESTED"}}`

### 2-6. 잔고 `GET /balance?environment=paper`
응답:
```json
{"ok": true, "balance": {"environment": "paper", "cashBalance": 9500000, "totalEvalAmount": 10120000, "totalProfitLoss": 120000,
  "holdings": [{"symbol": "005930", "name": "삼성전자", "quantity": 3, "avgPrice": 70900, "currentPrice": 71500, "evalAmount": 214500, "profitLoss": 1800, "profitLossRate": 0.85}]}}
```

### 주문 상태 정규화
| status | 의미 | KIS 근거 |
|--------|------|----------|
| `ACCEPTED` | 접수됨, 미체결 | 주문 응답 rt_cd=0, 체결조회 rmn_qty = ord_qty |
| `PARTIALLY_FILLED` | 일부 체결 | 0 < tot_ccld_qty < ord_qty |
| `FILLED` | 전량 체결 | rmn_qty = 0, tot_ccld_qty = ord_qty |
| `CANCEL_REQUESTED` | 취소 요청 접수 | 취소 응답 rt_cd=0 |
| `CANCELLED` | 취소 완료 | 체결조회에서 취소 확인 |
| `REJECTED` | 거부 | 주문 응답 rt_cd≠0 또는 체결조회 거부 사유 |
| `UNKNOWN` | 조회 실패 | 조회 API 오류. 호출자는 재조회 |

### 오류 코드
| HTTP | error | 상황 |
|------|-------|------|
| 400 | `INVALID_REQUEST` | 필드 검증 실패 (종목코드, 수량, 호가 단위 등) |
| 401 | `UNAUTHORIZED` | API Key 없음/폐기 |
| 403 | `APPROVAL_INVALID` | 승인 토큰 만료·불일치·재사용 |
| 403 | `SCOPE_FORBIDDEN` | 이 API Key에 KIS 주문 권한 없음 (`KIS_AUTOTRADE_API_KEY_IDS` 미포함) |
| 403 | `REAL_ORDER_DISABLED` | `environment=real`인데 서버 플래그 꺼짐 또는 계좌 소유자 아님 |
| 409 | `INSUFFICIENT_BALANCE` / `INSUFFICIENT_HOLDINGS` | 예수금/보유수량 부족 (사전 검증) |
| 409 | `ORDER_IN_PROGRESS` | 동일 환경 주문 락 점유 중 |
| 422 | `LIMIT_EXCEEDED` | 회당 금액/수량 한도 초과 |
| 429 | `RATE_LIMITED` | API Key 분당 호출 제한 |
| 502 | `KIS_<msg_cd>` | KIS가 거부 (메시지는 KIS msg1) |
| 503 | `KIS_CONFIG_REQUIRED` / `KIS_CONNECTION_ERROR` | 자격증명 미설정 / KIS 연결 실패 |

## 3. 변경 이력
- v0.1 (2026-10-02) 최초 작성. 미결: 체결 webhook 여부(현재 폴링), API Key 스코프 컬럼(현재 env 화이트리스트).
