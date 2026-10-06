# TODO — KIS 자동매매 연동 (stock-coin-trade 담당분)

> 작성일: 2026-10-02
> 3개 저장소(domain-rag-lab / lumina-invest / stock-coin-trade)를 연결해
> **시그널 → 위험관리 → KIS 실주문 → 체결 확인** 파이프라인을 구축한다.
> 이 파일은 stock-coin-trade 담당분이다. 같은 이름의 todo.md가 다른 두 저장소에도 있다.

---

## 0. 연동 방식과 실행 흐름

### 0-1. 연동 방식: 사이트 통합이 아닌 **저장소별 API 연동**

- 세 저장소는 **각자 독립 배포·독립 DB**를 유지한다. 코드나 화면을 한 저장소로 합치지 않는다.
- 저장소 간 통신은 **HTTP API만** 사용한다 (파일 공유·DB 직접 접근 없음).
  - domain-rag-lab → lumina-invest : 백테스트 결과/전략 스펙 API
  - lumina-invest → stock-coin-trade : 주문·체결조회·잔고 Open API (API Key 인증)
- 각 저장소는 자기 API의 **계약(요청/응답 스키마)과 버전**에 책임을 진다. 상대 저장소 내부 모듈을 import하지 않는다.

### 0-2. 최초 트리거: lumina-invest 웹앱 **종목 선정 화면**

자동매매는 사용자가 lumina-invest 웹앱에서 종목을 고르고 자동매매를 켜는 순간부터 시작된다.

```
[사용자] lumina-invest 웹앱 (public/app.html, public/js/quant.js)
   │  ① 퀀트 화면에서 종목 선정 + 리스크 한도 입력
   │     POST /api/stocks/quant/settings  →  BrokerSettings.quant_selected_symbols, risk_* 저장
   │  ② 자동매매 ON  (quant_mode: paper | live)
   ▼
[lumina-invest] Celery Beat 10분 주기  quant.auto_trade_cycle
   │  ③ _run_quant_cycle()  — selected_symbols 로드 (없으면 AI 상위 N종목)
   │  ④ 시그널 생성: 기술지표 + LightGBM(ml_models.py)  →  매수/매도/관망
   │  ⑤ risk_guard: kill switch → 일손실 한도 → 일 주문 수 → 종목 비중 → 쿨다운
   ▼
[stock-coin-trade] Open API  (HTTP, API Key)
   │  ⑥ POST /openapi/v1/kis/order-approval  →  60초 1회용 승인 토큰
   │  ⑦ POST /openapi/v1/kis/orders  (승인 토큰 + client_order_id)
   │       kis_request(): OAuth 토큰 서버 캐싱, 레이트리밋, 회당 주문 한도, Secrets Manager 키
   ▼
[KIS Testbed / 실전 API]  ──(주문 체결)──►  [stock-coin-trade DB 감사 로그 + 체결 기록]
   │
   │  ⑧ lumina-invest  quant.confirm_fills (1~2분 주기)  GET /openapi/v1/kis/orders/{order_no}
   ▼
[lumina-invest] 체결 반영 → 사이클 로그 → 웹앱 자동매매 현황 화면 / 알림
```

domain-rag-lab은 이 런타임 흐름의 **앞단(사전 검증)**에 위치한다. 종목 선정 화면에서 선택 가능한 전략은
domain-rag-lab LEAN 백테스트를 통과해 export된 전략 스펙만 노출한다.

### 0-3. 5단계 구조와 담당 저장소

| 단계 | 내용 | 담당 |
|------|------|------|
| 1. 신호 생성 & 검증 | LEAN Docker 백테스트 전략 검증 | domain-rag-lab |
|  | LightGBM / 기술지표 매수·매도 시그널 생성 | lumina-invest |
| 2. 스케줄링 & 리스크 제어 | Celery Beat 10분 주기 `quant.auto_trade_cycle` | lumina-invest |
|  | 위험관리 엔진: 중복주문 쿨다운, 일손실 한도, 비상정지(Kill-Switch) | lumina-invest |
| 3. KIS 통합 주문 게이트웨이 | KIS 공통 게이트웨이 `kis_request()` | **stock-coin-trade** (이 저장소) |
|  | 인증 & 보안: OAuth 토큰 서버 캐싱, AWS Secrets Manager 키 관리 | **stock-coin-trade** (이 저장소) |
|  | 안전 장치: 60초 1회용 승인 토큰, 회당 주문 한도 제어 | **stock-coin-trade** (이 저장소) |
| 4. KIS Testbed / 실전 API | 주문 체결 (환경 플래그로 분리) | **stock-coin-trade** (이 저장소) |
| 5. DB 감사 로그 & 체결 기록 | `_audit_kis_call` 감사 로그 + `kis_orders` 체결 기록 | **stock-coin-trade** (이 저장소) (lumina는 사이클 로그에 미러) |

### 0-4. 전체 작업 순서 (3개 저장소 공통)

- [ ] **Phase 0. 계약 정의** — 3개 저장소가 공유할 API 계약을 먼저 고정
  - [x] 전략 스펙 API (domain-rag-lab → lumina-invest) — 계약서 1절, `/backtests/strategies` 구현·연동 완료
  - [ ] 승인 토큰·주문 요청/응답 스키마 (lumina-invest → stock-coin-trade)
  - [ ] 체결 조회·잔고 응답 스키마 (stock-coin-trade → lumina-invest)
- [ ] **Phase 1. 전략 확정** (domain-rag-lab) — 백테스트 통과 전략을 API로 제공
- [ ] **Phase 2. 실주문 경로 구축** (stock-coin-trade) — 모의(Testbed)부터, 실전은 플래그로 분리
- [ ] **Phase 3. 사이클 연결** (lumina-invest) — 종목 선정 화면 → 시그널 → risk_guard → 승인 토큰 → 주문 → 체결 확인
- [ ] **Phase 4. 모의 통합 테스트** — 종목 선정 화면에서 시작해 KIS Testbed 체결까지 end-to-end 1주 이상 운영
- [ ] **Phase 5. 실전 전환** — 소액·소수 종목부터, kill switch 수동 점검 후 개방

---

## 1. 현재 확인된 상태 (2026-10-02)

경로 기준: `python-stock-backend/app/`

- KIS 공통 게이트웨이: `services/brokers/kis.py`
  - `kis_request()` — 토큰 캐시, 프로세스 전역 레이트리밋, 레이트리밋 코드 재시도, `_audit_kis_call()` 감사로그
  - ⚠️ base URL이 `KIS_TESTBED_URL`(모의) **하드코딩**. 실전 URL(`openapi.koreainvestment.com:9443`) 분기 없음
  - `place_kis_paper_order()` — 모의 주문(`VTTC0012U`/`VTTC0011U`), 수량·금액 한도, 예수금/보유수량 사전 검증, 프로세스 락
  - `get_kis_orders_today()` — 당일 체결 조회(`inquire-daily-ccld`, `VTTC8001R`)
  - `get_kis_balance()`, `get_kis_quote()`, `get_kis_orderbook()` 등 조회 함수 보유
- Open API: `api/routes/openapi.py` (API Key 인증 `require_api_key`)
  - ⚠️ `POST /openapi/v1/orders`는 `stock_trading.execute_order(source="OPENAPI")` → **가상 주식 주문**. KIS로 나가지 않음
  - `GET /account`, `/positions`, `/orders`도 가상계좌 기준
- KIS 실전: `api/routes/kis_real.py` — `/status`, `POST /balance` **잔고 조회 전용**(`readOnly: True`), 계좌 소유자 이메일 검증(`KIS_REAL_OWNER_EMAIL`)
- KIS 모의 연습: `api/routes/kis_practice.py` — 세션 로그인 + CSRF 기반, Open API 키 인증 아님
- env: `.env.example` `KIS_ENVIRONMENT`, `KIS_PAPER_*`, `KIS_REAL_*`, `KIS_PAPER_MAX_ORDER_AMOUNT/QUANTITY`
- 60초 1회용 승인 토큰: `api/routes/broker_test.py` `POST /kis/order-approval` → `POST /kis/orders`
  - ⚠️ **브라우저 세션(`request.session`) 기반**. lumina-invest 서버가 API Key로 호출하는 machine-to-machine 경로에서는 그대로 쓸 수 없음 → Open API용 재구현 필요
- 회당 주문 한도: `place_kis_paper_order()`의 `KIS_PAPER_MAX_ORDER_AMOUNT`/`KIS_PAPER_MAX_ORDER_QUANTITY` 검증 (모의 전용)
- AWS Secrets Manager: `services/aws_secret_store.py` `get_secret(service)`, `cli/upload_keys_to_secrets_manager.py` 존재. KIS 키는 현재 env 우선, Secrets Manager 연동 여부는 `brokers/aws.py` 경로 확인 필요
- DB 감사 로그: `_audit_kis_call()` (요청/응답/소요시간/성공여부), `services/api_usage.py` (Open API 사용 로그)

---

## 2. 이 저장소에서 할 일

### 2-1. 계약 합의 (Phase 0)
- [x] 주문 요청 스키마 확정 (lumina-invest와 합의)
  - `symbol`(6자리), `side`(BUY/SELL), `quantity`, `order_type`(MARKET/LIMIT), `price`, `environment`(paper/real), `client_order_id`(멱등키)
- [x] 주문 응답 스키마: `order_no`(ODNO), `order_time`, `environment`, `client_order_id`, `message`
- [x] 체결 조회 응답 스키마: `order_no`, `status`(접수/부분체결/체결/거부/취소), `ordered_qty`, `filled_qty`, `avg_price`, `updated_at`
- [x] 에러 코드 표 정리 (KIS `msg_cd` → HTTP 상태 + 내부 코드 매핑)

### 2-2. 게이트웨이 환경 분리 (Phase 2)
- [x] `kis_request()`에 `environment: Literal["paper","real"]` 인자 추가, URL·토큰 캐시·자격증명을 환경별로 분리
  - 토큰 캐시 `_kis_token_cache`를 환경별 dict로
  - `_kis_credentials()`/`_kis_account()`가 `KIS_PAPER_*` / `KIS_REAL_*` 중 선택
- [x] tr_id 매핑 테이블 신설 (paper ↔ real)
  - 매수 `VTTC0012U` ↔ `TTTC0012U`, 매도 `VTTC0011U` ↔ `TTTC0011U`
  - 체결조회 `VTTC8001R` ↔ `TTTC8001R`, 잔고 `VTTC8434R` ↔ `TTTC8434R`
  - 정정/취소 `VTTC0013U` ↔ `TTTC0013U`
- [x] 레이트리밋이 환경별 별도 토큰이지만 KIS 계정 공통 제한인지 확인 후 `_kis_api_rate_lock` 범위 결정

### 2-3. 실주문 서비스 (Phase 2)
- [x] `place_kis_paper_order()`를 일반화한 `place_kis_order(environment, ...)` 추가 (기존 함수는 wrapper로 유지)
  - 실전 한도 env 추가: `KIS_REAL_MAX_ORDER_AMOUNT`, `KIS_REAL_MAX_ORDER_QUANTITY`, `KIS_REAL_ALLOWED_SYMBOLS`(선택, 화이트리스트)
  - 실전은 `KIS_REAL_ORDER_ENABLED=true` 플래그가 없으면 **무조건 거부** (Phase 5까지 기본 false)
- [x] 멱등성: `client_order_id` 저장 테이블(`kis_orders`) 신설. 동일 키 재요청 시 새 주문 없이 기존 결과 반환
- [x] **승인 토큰 Open API 버전**: 세션 대신 서버 저장소(Redis 또는 DB `order_approvals`)에 `token_digest`, `intent_digest`, `api_key_id`, `expires_at(+60s)`, `used_at` 저장. 1회 사용 후 즉시 소멸, 의도(symbol/side/qty/price) 불일치 시 거부
- [x] 회당 주문 한도를 환경별로 분리하고 API Key 단위 한도도 추가 (`KIS_REAL_MAX_ORDER_AMOUNT`, API Key별 `max_order_amount`)
- [x] KIS 자격증명 로딩 순서 확정: AWS Secrets Manager(`aws_secret_store.get_secret("kis-real")`) → env 폴백. 실전 키는 **env에 두지 않는 것**을 기본으로
- [x] 주문 레코드 저장: 요청 원문, KIS 응답, `order_no`, 환경, 호출 주체(API Key member), 상태
- [x] 정정/취소 함수 `cancel_kis_order(environment, order_no, ...)` 추가 (kill switch 시 lumina가 호출)

### 2-4. 체결 조회 서비스 (Phase 2)
- [x] `get_kis_order_status(environment, order_no)` — `inquire-daily-ccld`에서 해당 주문 찾아 상태 정규화
- [x] `kis_orders` 테이블 상태 갱신 (조회 시 또는 백그라운드 폴링)
- [x] 당일 미체결 목록 `get_kis_open_orders(environment)` (기존 `_kis_open_orders_today()` 공개 함수화)

### 2-5. Open API 엔드포인트 신설 (Phase 2)
`api/routes/openapi.py` 또는 새 라우터 `api/routes/openapi_kis.py` (API Key 인증 유지)
- [x] `POST /openapi/v1/kis/order-approval` — 60초 1회용 승인 토큰 발급 (주문 의도 포함)
- [x] `POST /openapi/v1/kis/orders` — 주문 (승인 토큰 필수. 기존 가상 `/orders`와 **분리**, 혼동 방지)
- [x] `GET  /openapi/v1/kis/orders/{order_no}` — 체결 상태
- [x] `GET  /openapi/v1/kis/orders?date=&status=` — 당일 주문/체결 목록
- [x] `DELETE /openapi/v1/kis/orders/{order_no}` — 취소
- [x] `GET  /openapi/v1/kis/balance` — 잔고 (lumina 실계좌 기준 일손실 계산용)
- [x] API Key에 **권한 스코프** 추가: `kis:paper:order`, `kis:real:order`, `kis:read`. 실전 주문 스코프는 수동 발급만
- [x] 실전 주문은 `KIS_REAL_OWNER_EMAIL` 소유자 검증(`kis_real.py` 로직) 재사용
- [x] 요청/응답 전부 `api_usage` 로그 + `_audit_kis_call` 감사로그 연결 확인

### 2-6. 테스트 (Phase 2·4)
- [x] `kis_request` 환경 분기 단위 테스트 (URL·헤더·tr_id)
- [x] 멱등키 중복 요청 테스트, `rt_cd != "0"` 응답 처리 테스트
- [x] Testbed 실호출 스모크 테스트 (환경변수 있을 때만 실행)
- [x] lumina-invest 게이트웨이 클라이언트와 계약 테스트 (스키마 고정 후)

---

## 3. 다른 저장소와의 인터페이스

- **← lumina-invest**: 위 2-5 엔드포인트 호출 (API Key 헤더, 서버 간 호출). 10분 사이클마다 승인 토큰 → 주문 2단계 호출, 1~2분 체결 확인 폴링
- 최초 트리거는 lumina-invest 웹앱 종목 선정 화면이며, 이 저장소는 **사용자 화면 없이 API만** 제공한다
- **→ lumina-invest**: 주문 결과·체결 상태·잔고 응답

---

## 4. 미결 사항 (결정 필요)

- [x] 체결 상태를 lumina가 폴링할지, stock-coin-trade가 webhook/콜백으로 밀어줄지 (초기엔 폴링 권장)
- [x] 기존 `POST /openapi/v1/orders`(가상) 유지 여부와 문서 표기
- [x] 실전 전환 2인 승인: 코드 대신 운영 절차(6-2 Phase 5 체크리스트)로 결정
- [x] `vscode-kis-mcp/` 통합: 범위 외로 결정(6-4)

---

## 5. 개발 소요 예상 시간

> 기준: 각 저장소 코드를 아는 개발자, 하루 6시간 실작업, 영업일(d) 단위. KIS Testbed 계좌·AWS 계정은 준비되어 있다고 가정.
> 추정이므로 ±30% 여유를 둔다. 미결 사항(각 파일 4절)이 늦게 결정되면 그만큼 밀린다.

| Phase | 저장소 | 주요 작업 | 공수 |
|-------|--------|-----------|------|
| 0. 계약 정의 | 공통 | 전략 스펙·주문·체결 스키마, 에러 코드 표, 미결 사항 결정 | 2~3d |
| 1. 전략 확정 | domain-rag-lab | 스펙 스키마, 스펙→main.py 생성기, 결과 파서·합격 기준, 전략 조회 API+인증, 테스트 | 5~7d |
| 2. 실주문 경로 | stock-coin-trade | kis_request 환경 분리·tr_id 매핑 (2d), 실주문 서비스+멱등+승인 토큰 (3d), 체결 조회 (1~2d), Open API 엔드포인트+스코프 (2d), Secrets Manager 연동 (1d), 테스트 (2d) | 10~12d |
| 3. 사이클 연결 | lumina-invest | 종목 선정 화면 확장 (2~3d), 전략 로더+LightGBM 합산 (2~3d), 게이트웨이 2단계 호출 (2d), 체결 확인 태스크+live_orders (2~3d), 위험관리 보강 (2~3d), 테스트 (2d) | 12~16d |
| 4. 모의 통합 테스트 | 공통 | Testbed로 종목 선정 → 체결까지 end-to-end, 1주 관찰 + 버그 수정 | 5d 운영 관찰 + 3~5d 수정 |
| 5. 실전 전환 | 공통 | 실전 플래그·스코프 발급, 소액 운영 1주 관찰, kill switch 리허설 | 2~3d + 5d 관찰 |

### 합계

| 인원 구성 | 실작업 공수 | 캘린더 기간 |
|-----------|-------------|-------------|
| 1인이 순차 진행 | 약 **40~50 영업일** | 약 **10~12주** (관찰 기간 2주 포함) |
| 3인이 저장소별 병렬 진행 (Phase 1·2·3 동시) | 합산 공수는 동일 | 약 **6~7주** — 크리티컬 패스는 lumina-invest(Phase 3) → Phase 4 → Phase 5 |

### AI 에이전트(Claude Code) 개발 기준

> 기준: AI 에이전트가 코드 작성·테스트·마이그레이션을 수행하고, 사람은 계약 결정·코드 리뷰·자격증명 투입·실행 승인만 담당.
> 에이전트 실작업은 **세션 시간(h)**, 사람 몫은 영업일(d)로 구분. 코딩 시간은 크게 줄지만 **외부 대기와 관찰 기간은 줄지 않는다.**

| Phase | 에이전트 실작업 | 사람 몫 (결정·리뷰·승인) | 줄지 않는 대기 |
|-------|----------------|--------------------------|----------------|
| 0. 계약 정의 | 스키마·에러 코드 표 초안 1~2h | 미결 사항 결정 + 초안 검토 0.5~1d | — |
| 1. 전략 확정 (domain-rag-lab) | 스펙 스키마, main.py 생성기, 결과 파서, 조회 API, 테스트 4~6h | 리뷰 0.5d | LEAN Docker 백테스트 실행 시간 (전략당 수 분~수십 분) |
| 2. 실주문 경로 (stock-coin-trade) | 환경 분리, 실주문·멱등·승인 토큰, 체결 조회, Open API, Secrets Manager, 테스트 8~12h | 리뷰 0.5~1d, KIS/AWS 자격증명 투입 | Testbed 스모크 테스트는 장 운영시간에만 가능 |
| 3. 사이클 연결 (lumina-invest) | 종목 선정 화면 확장, 전략 로더+LightGBM 합산, 게이트웨이, 체결 확인 태스크, 위험관리 보강, 테스트 10~14h | 리뷰 1d, 화면 UX 확인 | — |
| 4. 모의 통합 테스트 | 발견 이슈 수정 누적 3~6h | 매일 사이클 로그 점검 | **Testbed 관찰 5 영업일** (장 운영시간 기준, 단축 비권장) |
| 5. 실전 전환 | 플래그·스코프·리허설 스크립트 2~3h | 실전 전환 승인, kill switch 리허설 참여 | **KIS 실전 API 승인 대기** + **소액 운영 관찰 5 영업일** |

| 구분 | 합계 |
|------|------|
| 에이전트 실작업 | 약 **28~43시간** (세션 기준 5~7 영업일) |
| 사람 몫 | 약 **3~4 영업일** (결정 1d, 리뷰 2~3d) |
| 줄지 않는 대기 | 관찰 10 영업일 + KIS 실전 승인 대기 |
| **캘린더 기간** | 약 **3.5~4.5주** (사람 기준 10~12주 대비 약 1/3) |

에이전트 기준으로 Phase 1·2·3은 **같은 날 병렬 세션**으로 돌릴 수 있어 코딩 구간은 1주 안에 끝난다.
전체 기간은 Phase 0 결정 속도와 Phase 4·5의 관찰 기간이 결정한다. 관찰을 각 3 영업일로 줄이면 약 3주까지 단축되지만, 쿨다운·일손실 한도가 실제로 작동하는 장면을 충분히 보지 못하므로 권장하지 않는다.

에이전트 작업 시 추가로 드는 비용은 사람 리뷰다. 주문·자금이 걸린 코드이므로 Phase 2·3 산출물은 **사람이 반드시 라인 단위로 리뷰**하는 것을 전제로 위 사람 몫을 잡았다.

### 기간을 좌우하는 변수
- Phase 0에서 API 계약을 확정하지 못하면 Phase 1·2·3이 병렬로 진행되지 못한다. **계약 확정이 최우선**
- lumina-invest는 기존 `KISClient` 직접 호출을 버리고 stock-coin-trade 경유로 바꾸는 작업이라, 자체 호출 유지로 결정하면 Phase 3에서 2~3d 줄어든다 (대신 stock-coin-trade의 감사 로그·승인 토큰 이점을 잃음)
- KIS 실전 API 승인(계좌 소유자 인증, 모의→실전 전환 절차)은 외부 대기 시간이라 Phase 5 시작 2주 전에 미리 신청한다
- Phase 4 관찰 중 장 휴장일이 끼면 그만큼 연장된다

---

## 6. 작업 보고 (AI 에이전트 인수인계용)

> 이 섹션은 **작업을 이어받는 AI 에이전트가 가장 먼저 읽는 부분**이다. 작업을 끝낼 때마다 아래 형식으로 항목을 추가한다.
> 규칙: ① 완료 항목은 2절 체크박스를 `[x]`로 바꾸고 여기엔 파일 경로·검증 방법을 적는다 ② 미완료는 "다음 작업"에 우선순위와 시작 지점(파일:함수)을 적는다
> ③ 가정·결정은 "결정 사항"에 이유와 함께 적는다 ④ 커밋은 사용자가 한다(에이전트는 커밋하지 않음) ⑤ 테스트 실행 명령을 그대로 적어 재현 가능하게 한다.

### 6-1. 2026-10-02 1차 작업 (Phase 0 + Phase 2 핵심 완료)

**완료**
| 항목 | 파일 | 비고 |
|------|------|------|
| API 계약 v0.2 | `docs/contracts/kis-autotrade-api.md` | 세 저장소 동일 사본. 변경 시 3곳 동시 갱신 |
| 게이트웨이 환경 분리 | `python-stock-backend/app/services/brokers/kis.py` `kis_request(base_url=, headers_factory=)` | 기존 호출부는 무변경(기본값=Testbed). 실전은 아래 모듈이 주입 |
| 자동매매 주문 서비스 | `python-stock-backend/app/services/brokers/kis_autotrade.py` | `TR_IDS` 매핑, `normalize_intent`, `issue_approval/consume_approval`, `place_order`(멱등·한도·사전 잔고·PENDING 선기록), `sync_order_status`, `list_today_orders`, `cancel_order`, `get_balance`, `require_scope`, `require_real_owner/allowed` |
| 모델·DDL | `app/models.py` `KisOrderApproval`, `KisAutotradeOrder` / `database/db.sql`, `database/SCHEMA.md` | SQLite 테스트용 PK variant 포함. 기동 시 `ensure_kis_autotrade_tables()` (`app/startup.py`) |
| Open API 라우터 | `python-stock-backend/app/api/routes/openapi_kis.py` (`/openapi/v1/kis/*`) | `router.py` 등록. `openapi.py`에 `ApiKeyContext`(api_key_id, member_id) 추가 |
| 요청 스키마 | `app/api/schemas.py` `KisAutotradeOrderBody` | |
| 환경변수 | `.env.example` `KIS_AUTOTRADE_API_KEY_IDS`, `KIS_REAL_ORDER_ENABLED`, `KIS_REAL_MAX_ORDER_*`, `KIS_REAL_ALLOWED_SYMBOLS` | |
| 테스트 14개 | `python-stock-backend/tests/test_kis_autotrade.py` | 스코프 기본 거부, 승인 토큰 1회성·의도 바인딩, 멱등 중복, KIS 거부 기록, 실전 플래그/소유자, 한도, tr_id 매핑, 실전 URL/헤더, 상태 정규화, 체결 조회 갱신 |

| README 안내 | `README.md` 끝 "KIS 자동매매" 절 | todo.md 6절·계약 문서 링크 |

**검증**
```bash
cd /home/ubuntu/stock-coin-trade/python-stock-backend && .venv/bin/python -m pytest -q   # 68 passed
```

**결정 사항 (이유)**
- 스코프는 DB 컬럼 대신 env 화이트리스트 `KIS_AUTOTRADE_API_KEY_IDS` (비우면 전부 거부). 이유: 운영 MariaDB `api_key` 테이블 ALTER 없이 당일 배포 가능. → 다음 작업에서 컬럼으로 승격 가능
- 승인 토큰은 Redis 아닌 **DB 테이블** `kis_order_approval`. 이유: 멱등 주문 기록과 같은 트랜잭션 경계, 다중 프로세스 공유, 감사 추적
- 멱등 중복 요청도 승인 토큰을 소비한다(계약서 2-2). 중복 응답에 `duplicate: true`
- 주문 전 PENDING 행을 **별도 commit** 해 KIS 호출 중 장애에도 흔적을 남긴다. 연결 오류 시 상태 UNKNOWN (KIS 수신 여부 불명) → 호출자가 체결 조회로 확정
- 실전 자격증명: env 우선, `CREDENTIAL_SOURCE=aws` 면 Secrets Manager `kis-real`(app_key/secret) + `kis-real/account` 폴백. 보안 암호 이름은 **운영팀과 확정 필요**
- 기존 `place_kis_paper_order()`/`broker_test.py` 세션 기반 흐름은 그대로 두었다(웹 화면용). 자동매매는 `kis_autotrade` 만 사용

**다음 작업 (우선순위순)**
1. Testbed 스모크: `.env`에 `KIS_PAPER_*` + `KIS_AUTOTRADE_API_KEY_IDS` 설정 → API 키 발급(`POST /api/api-keys`) → 장중에 승인→주문→`GET /orders/{no}` 1사이클 실호출. 시작 지점: `tests/test_kis_autotrade.py` 의 `ORDER` 본문을 curl 로 재현
2. `api_key` 테이블에 `scopes` 컬럼 추가 + `require_scope` 가 컬럼 우선·env 폴백 (`app/services/brokers/kis_autotrade.py:require_scope`)
3. 당일 조회 페이지네이션(`CTX_AREA_FK100/NK100`) 처리 — `list_today_orders` 는 1페이지만 읽음 (주문 50건 초과 시 누락)
4. `sync_order_status` 의 당일 범위 한계: 전일 미체결(익일 취소) 주문은 조회 불가 → `INQR_STRT_DT` 를 생성일 기준으로
5. 실전 전환(Phase 5) 체크리스트: `KIS_REAL_ORDER_ENABLED=true`, `KIS_REAL_ALLOWED_SYMBOLS` 소수 종목, `KIS_REAL_MAX_ORDER_AMOUNT` 소액 → 운영자 승인 후

**알려진 제약**
- 라우트 등록 확인은 TestClient 경로로만 했다(최신 FastAPI `_IncludedRouter` 로 `app.routes` 순회 불가). 서버 기동 후 `/docs`에서 `openapi-kis` 태그 확인 권장
- KIS 레이트리밋은 paper/real 이 **같은 전역 락**을 공유한다(보수적). 계정이 다르면 분리 가능

### 6-2. 2026-10-02 2차 작업 (6-1 "다음 작업" 2·3·4·5 처리)

**완료**
| 6-1 번호 | 항목 | 파일 | 비고 |
|------|------|------|------|
| 2 | `api_key.scopes` 컬럼 + DB 우선 스코프 | `app/models.py` `ApiKey.scopes`, `kis_autotrade.key_scopes/require_scope(api_key_id, db)`, `openapi_kis.py` 전 라우트에 db 전달, `api_keys.py` 직렬화(읽기만), `database/db.sql` | `kis:order` 또는 `kis:*` 가 있으면 허용, 없으면 env `KIS_AUTOTRADE_API_KEY_IDS` 폴백. 기동 시 `ensure_kis_autotrade_tables()` 가 `ALTER TABLE api_key ADD COLUMN IF NOT EXISTS scopes` 실행(MariaDB) |
| 3 | 연속조회 페이지네이션 | `kis_autotrade.list_orders(environment, start, end, ...)` | 응답 헤더 `tr_cont` F/M → 요청 헤더 `tr_cont=N` + `CTX_AREA_FK100/NK100` 반복, 최대 `CCLD_MAX_PAGES=10`. `list_today_orders` 는 래퍼 |
| 4 | 조회 범위 = 주문 생성일~오늘 | `kis_autotrade.sync_order_status` | 기록이 있으면 `created_at` 부터 조회 → 전일 미체결(익일 취소)도 찾음 |
| 5 | 실전 전환 체크리스트 | 아래 "Phase 5 체크리스트" | 문서 |
| — | 테스트 3개 추가 (총 71) | `tests/test_kis_autotrade.py` | scopes 컬럼 우선, 2페이지 연속조회, 생성일 기준 조회 범위 |

**검증**
```bash
cd /home/ubuntu/stock-coin-trade/python-stock-backend && .venv/bin/python -m pytest -q   # 71 passed
```

**결정 사항**
- 스코프 이름은 todo 원안(`kis:paper:order`/`kis:real:order`)이 아닌 **`kis:order` 단일 + 환경 구분은 서버 플래그**로 단순화. 이유: real 허용은 이미 `KIS_REAL_ORDER_ENABLED` + 소유자 이메일로 2중 통제되므로 스코프 분리는 중복
- 스코프 부여 API는 만들지 않음(셀프 발급 차단). 운영자가 DB에서 `UPDATE api_key SET scopes='kis:order' WHERE api_key_id=?`
- 구 운영 DB에서 `scopes` 컬럼이 없을 때 `db.get(ApiKey)` 가 실패하면 빈 집합으로 처리해 env 폴백이 동작한다

**Phase 5 실전 전환 체크리스트 (운영자용)**
1. `.env`: `KIS_REAL_APP_KEY/SECRET/ACCOUNT_NO/OWNER_EMAIL` (또는 Secrets Manager `kis-real`), `KIS_REAL_ORDER_ENABLED=true`, `KIS_REAL_ALLOWED_SYMBOLS=005930`(소수 종목), `KIS_REAL_MAX_ORDER_AMOUNT=300000`, `KIS_REAL_MAX_ORDER_QUANTITY=5`
2. lumina 호출용 API 키의 member 가 `KIS_REAL_OWNER_EMAIL` 회원인지 확인, `scopes='kis:order'` 부여
3. 장 시작 전 `GET /openapi/v1/kis/balance?environment=real` 로 잔고 조회 성공 확인
4. 첫 실전 주문은 1주 지정가(현재가 −5%) → `GET /orders/{no}?environment=real` 로 ACCEPTED 확인 → `DELETE` 로 취소까지 리허설
5. lumina `STOCK_COIN_TRADE_KIS_ENVIRONMENT=real` 전환은 위 1~4 완료 후, 소액 운영 5영업일 관찰

**다음 작업**
1. (6-1의 1) Testbed 스모크 — 자격증명 필요, 미수행
2. `list_orders` 의 `tr_cont` 처리는 KIS 문서 기준 구현이며 실호출 미검증 → 스모크 때 50건 초과 계좌로 확인
3. `_kis_api_rate_lock` 를 환경별로 분리할지 (KIS 계정이 다르면 분리 가능)

### 6-3. 2026-10-02 3차 작업 — 환경 구성 + Testbed 스모크 (6-1 "다음 작업" 1 처리)

**환경 구성(실행함)**
| 항목 | 내용 |
|------|------|
| compose | `docker-compose.yml` `python-backend` 에 외부 네트워크 `shared-net` 추가(lumina `fin-ai-*` 와 동일망) + `KIS_AUTOTRADE_API_KEY_IDS`, `KIS_REAL_ORDER_ENABLED`, `KIS_REAL_MAX_ORDER_*`, `KIS_REAL_ALLOWED_SYMBOLS` 환경변수 전달 |
| API 키 | MariaDB `api_key` 에 member_id=1(jj@jj.com) 소유 `lumina-autotrade` 키 발급 → **api_key_id=2**. 원문은 lumina-invest `.env` `STOCK_COIN_TRADE_API_KEY` 에만 저장(DB는 SHA-256) |
| .env | `KIS_AUTOTRADE_API_KEY_IDS=2`, `KIS_REAL_ORDER_ENABLED=false` 추가 |
| 이미지 | `docker compose build python-backend` → `up -d`. 기동 시 `kis_order_approval`/`kis_autotrade_order` 생성, `api_key.scopes` 컬럼 보정 확인 |
| 스모크 스크립트 | `scripts/kis_autotrade_smoke.py` — lumina 컨테이너에서 `docker exec -i fin-ai-app python - [--order] < scripts/kis_autotrade_smoke.py` |

**스모크 결과 (14:19 KST, 장중, Testbed)**
| 단계 | 결과 |
|------|------|
| `GET /openapi/v1/kis/balance` | 200. 예수금·보유 5종목 정상 |
| `POST /order-approval` | 200. 60초 토큰 |
| `POST /orders` 삼성전자 1주 LIMIT 253,000(현재가 −8%) | 200 ACCEPTED, KIS 주문번호 0000028011, orgNo 00950, msg 40600000 |
| `GET /orders/0000028011` | 200 (기록 기준 ACCEPTED) |
| `DELETE /orders/0000028011` | 200 CANCEL_REQUESTED, msg 40630000 |
| 감사 로그 | `api_usage_log` provider "KIS Gateway" 에 잔고·주문·취소·조회 8건 기록, `kis_order_approval` 3건 중 1건 used |

**발견한 제약 — KIS 모의투자의 일별주문체결조회(VTTC8001R)는 건별 목록(output1)을 비워 돌려준다**
- `rt_cd=0, msg_cd=70070000 "모의투자 조회할 내역(자료)이 없습니다"` 이면서 output2 합계(tot_ord_qty 등)는 채워져 있음. INQR_DVSN 00/01, PDNO 지정, CCLD_DVSN 02, 기간 7일, `EXCG_ID_DVSN_CD` KRX/ALL, ODNO 지정 모두 동일
- 따라서 Testbed 에서는 ccld 기반 체결 확인이 동작하지 않는다. 실전(TTTC8001R)에서는 정상일 것으로 예상하나 **미검증**

**폴백 구현 — 보유수량 변화로 체결 추정**
- `place_order` 가 주문 직전 보유수량·예수금을 `request_json._holding_before/_cash_before` 에 기록
- `sync_order_status` 가 ccld 에서 못 찾으면 `infer_status_from_holdings()`: 같은 환경·종목의 열린 주문이 **이 건 하나일 때만** 잔고 조회로 Δ보유수량 계산 → FILLED / PARTIALLY_FILLED / (취소 접수 40630000 + Δ0 → CANCELLED). 둘 이상이면 `lookup: "ambiguous_open_orders"` 로 추정하지 않음
- 체결가는 LIMIT 주문가로 둔다(지정가 이하 체결 가정). 응답 `lookup: "holdings_inference"`, `inference: {holdingBefore, holdingNow, delta}`
- 형제 주문 정리: 같은 종목에 취소 접수(4063xxxx)된 열린 주문이 남아 있으면, "다음 주문이 기록한 기준 보유수량"과 비교해 변화가 없을 때 먼저 CANCELLED 로 정리한 뒤 추정한다(쿨다운으로 종목당 순차 주문이라는 전제)
- 테스트 4개 추가 (총 75)
- **실호출 검증**: 두 번째 스모크 주문 0000028261(접수→취소)이 재기동 후 `GET /orders/0000028261` 에서 `status=CANCELLED, lookup=holdings_inference, delta=0` 으로 확정됨. 첫 주문 0000028011 은 추정 기능 도입 전 기록(기준 보유수량 없음)이라 DB 에서 수동 CANCELLED 처리

**검증**
```bash
cd /home/ubuntu/stock-coin-trade/python-stock-backend && .venv/bin/python -m pytest -q   # 75 passed
docker exec -i fin-ai-app python - < /home/ubuntu/stock-coin-trade/scripts/kis_autotrade_smoke.py          # 잔고·승인까지
docker exec -i fin-ai-app python - --order < /home/ubuntu/stock-coin-trade/scripts/kis_autotrade_smoke.py  # 접수→조회→취소
```

**다음 작업**
1. 실전 환경에서 `inquire-daily-ccld` output1 이 정상인지 확인(잔고 조회 전용 키로는 불가, Phase 5 에서)
2. 같은 종목에 동시 열린 주문이 있을 때의 체결 귀속 — Testbed 에서는 종목당 1건으로 운용(lumina 쿨다운이 보장)하거나 `_cash_before` 차이로 보조 추정
3. 기존 웹 화면의 `get_kis_orders_today()`(kis.py) 도 같은 제약을 받는다 → 화면에 안내 문구 또는 `kis_autotrade_order` 기록 기반 표시로 전환
4. 컨테이너 로그의 `pg-stock` 연결 오류는 3일 전 종료된 OHLCV DB(`pg-stock` Exited) 때문이며 자동매매와 무관. 필요 시 `pg-stock` 기동

### 6-4. 2026-10-02 4차 작업 — 남은 개발 항목 (6-2·6-3 "다음 작업" 처리)

**완료**
| 항목 | 파일 | 비고 |
|------|------|------|
| 환경별 레이트리밋 | `kis.py` `kis_request(rate_key=)`, `_kis_rate_state()` / `kis_autotrade.request` 가 real 은 `rate_key="real"` | KIS 제한은 App Key 단위 → paper/real 키가 다르므로 상태 분리. 기본값 "paper" 로 기존 호출부 무변경 |
| 웹 당일주문 폴백 | `kis.get_kis_orders_today()` → `kis_autotrade.today_records("paper")` | Testbed 가 건별 목록을 비우면 게이트웨이 기록을 `source: gateway_record` 로 표시 + `note` |
| 계약 필드 고정 | `kis_autotrade.ORDER_RESPONSE_FIELDS` + 테스트 | `serialize_order` 키 집합 = 계약서 2-2 |
| 감사 로그 연결 확인 | (스모크 결과) | `api_usage_log` provider "KIS Gateway" 에 모든 호출 기록됨 |
| 테스트 3개 추가 (총 78) | `tests/test_kis_autotrade.py` | |
| 재배포 | `docker compose build python-backend && up -d` | |

**결정 사항 (4절 미결 정리)**
- 체결 통지는 **폴링**(lumina `quant.confirm_fills` 2분). webhook 은 lumina 가 공개 엔드포인트를 가져야 해 Phase 5 이후 검토
- 기존 `POST /openapi/v1/orders`(가상) 는 **유지**. 계약서·README 에 "가상 주문, KIS 실주문은 /kis/*" 표기 완료
- 실전 전환 2인 승인은 코드 대신 운영 절차(Phase 5 체크리스트)로 둔다
- `vscode-kis-mcp` 통합은 범위 외

**다음 작업**
1. (6-3의 1) 실전 ccld output1 정상 여부 — Phase 5
2. `today_records` 의 `name` 은 None — `kis_autotrade_order` 에 종목명 컬럼 추가 또는 조회 시 quote 로 보완

### 6-5. 2026-10-02 5차 작업 (6-4 "다음 작업" 2)

**완료**
| 항목 | 파일 | 비고 |
|------|------|------|
| 게이트웨이 주문 기록에 종목명 | `kis_autotrade.place_order` 가 잔고 보유 종목명을 `request_json._name` 에 기록, `today_records()` 가 `name` 으로 노출 | 미보유 종목은 빈 값(모의 시세 응답에 종목명 없음). 스키마 변경 없음 |
| pg-stock 기동 | `docker start pg-stock` → healthy | 3일 전 종료돼 있던 OHLCV DB. 컨테이너 로그의 `pg-stock` 해석 오류 해소 예상(다음 동기화 주기에 확인) |
| 테스트 1개 추가 (총 79) | `tests/test_kis_autotrade.py` | |
| 재배포 | python-backend | |

**에이전트가 더 할 수 있는 개발 항목: 없음.** 남은 것은 7절과 Phase 5.

---

## 7. 사용자 의사결정 필요 항목 (에이전트가 대신 정할 수 없는 것)

> 2026-10-02 기준. 결정되면 이 표를 갱신하고 관련 "다음 작업"을 6절에 추가한다.

| # | 결정할 것 | 선택지와 영향 | 에이전트 권고 |
|---|-----------|---------------|---------------|
| S1 | 실전 전환 시점과 범위 | 6-2 Phase 5 체크리스트. 허용 종목·회당 한도·소액 운영 기간 | Testbed 1주 관찰 후, 종목 1개·회당 30만 원·5영업일 |
| S2 | 실전 자격증명 보관 | `.env` vs AWS Secrets Manager(`kis-real`). SM 이면 보안 암호 이름 확정 필요 | Secrets Manager |
| S3 | API 키 권한 방식 확정 | `api_key.scopes` 컬럼(현재 병행) vs env 화이트리스트만 | 컬럼으로 일원화하고 env 는 폐기 |
| S4 | KIS Testbed 체결 목록 미제공에 대한 운영 수용 | 보유수량 추정(현재)으로 Phase 4 진행 vs KIS 문의 후 대기 | 추정으로 진행, 실전에서 ccld 정상 확인 |
| S5 | 같은 종목 동시 주문 허용 여부 | 허용 시 체결 귀속 모호(`ambiguous_open_orders`). lumina 쿨다운으로 1건 유지가 전제 | Testbed 기간엔 종목당 1건 |
| S6 | ~~변경분 커밋~~ **완료**(2026-10-02 푸시, origin/main=e55bfd7, 10-06 기준 미커밋 없음) | — | — |

### 6-6. 2026-10-02 운영 시작 (7절 권고 수용 적용)

| # | 적용 |
|---|------|
| S3 | 권한을 `api_key.scopes` 로 **일원화**: env `KIS_AUTOTRADE_API_KEY_IDS` 를 코드·compose·.env·.env.example·문서에서 제거, `require_scope` 는 컬럼만 확인. lumina 키(api_key_id=2)에 `scopes='kis:order'` 부여. 계약서 v0.5 |
| S4·S5 | 보유수량 추정으로 Phase 4 진행, 종목당 1건(쿨다운 30분) |
| — | 재배포 후 lumina 사이클이 낸 첫 자동 주문 **0000030540 (삼성전자 1주 LIMIT 275,000) ACCEPTED** 가 `kis_autotrade_order` 에 기록됨 |
| — | 테스트 총 79 통과 |

---

## 8. 운영 배포 (2026-10-02)

**대상 서버**
| 도메인 | 저장소 | EC2 | 배포 방식 |
|--------|--------|-----|-----------|
| fd.edumgt.co.kr | lumina-invest | 43.201.229.188 (`/home/ubuntu/lumina-invest`, compose `docker-compose.yml:compose.fd.yml`) | GitHub Actions `deploy.yml`(push main) 또는 수동 rsync+compose |
| pr.edumgt.co.kr | domain-rag-lab | 같은 서버 (`/home/ubuntu/domain-rag-lab`, `deploy/pr-edumgt/compose.yml`, Caddy alias `pr-api`) | 수동 rsync+compose. `cd.yml` 을 이 compose 로 고쳤으나 시크릿(EC2_HOST 등)은 구서버 값 → 갱신 필요 |
| st.edumgt.co.kr | stock-coin-trade | 43.202.161.134 (`/opt/stock-coin-trade`, ssl+pg-stock 오버레이) | GitHub Actions `deploy-ec2.yml`(push main) 만. 에이전트는 이 서버 SSH 키 탐색이 보안 정책으로 차단돼 직접 접속하지 않음 |

**에이전트가 수행한 것**
- fd 서버 `lumina-invest/.env` 에 추가: `STOCK_COIN_TRADE_BASE_URL=https://st.edumgt.co.kr`, `STOCK_COIN_TRADE_API_KEY=`(**비어 있음 — st 서버에서 발급 후 기입**), `STOCK_COIN_TRADE_KIS_ENVIRONMENT=paper`, `..._ORDER_TYPE=LIMIT`, `..._ENFORCE_MARKET_HOURS=true`, `..._CANCEL_OPEN_AFTER_MIN=0`, `DOMAIN_RAG_LAB_BASE_URL=http://pr-api:8000`, `DOMAIN_RAG_LAB_API_KEY=<키>`
- fd 서버 `domain-rag-lab/.env.prod` 에 `STRATEGY_API_KEY=<같은 키>` 추가, `data/strategies`·`data/lean-workflows` 생성
- domain-rag-lab · lumina-invest 를 fd 서버에 rsync 후 compose 재빌드 (결과는 아래 "배포 결과")
- stock-coin-trade: `docker-compose.yml` 에서 shared-net 참여를 로컬 전용 `docker-compose.override.yml` 로 분리해 운영 서버 compose(-f 지정)가 외부 네트워크를 요구하지 않게 함

**에이전트가 할 수 없어 사용자가 수행할 것**
1. **GitHub 푸시** (분류기가 "외부 게시"로 차단). 세 저장소 모두 로컬 main 이 origin 보다 앞서 있음:
   ```bash
   for r in domain-rag-lab lumina-invest stock-coin-trade; do (cd /home/ubuntu/$r && git push origin main); done
   ```
   - 푸시하면 lumina `deploy.yml`(fd 재배포, 이미 수동 배포돼 동일 결과)과 stock-coin-trade `deploy-ec2.yml`(**st 서버 실제 배포**)이 자동 실행된다. `gh run watch -R edumgt/stock-coin-trade` 로 확인
   - domain-rag-lab `cd.yml`/`cd-ecr.yml` 은 시크릿이 구서버 기준이라 실패할 수 있음(무해). 고치려면 `gh secret set EC2_HOST --body 43.201.229.188 -R edumgt/domain-rag-lab`, `EC2_USER=ubuntu`, `EC2_APP_DIR=/home/ubuntu/domain-rag-lab`, `EC2_SSH_PRIVATE_KEY < lumina-invest/fd.edumgt.co.kr.pem`
2. **st 서버에서 lumina 전용 API 키 발급** (deploy-ec2 완료 후, 기동 시 `api_key.scopes` 컬럼·KIS 테이블이 자동 생성됨):
   ```bash
   # st 서버에서 (ssh ubuntu@43.202.161.134)
   cd /opt/stock-coin-trade
   RAW="eduapi_live_$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')"; HASH=$(printf %s "$RAW" | sha256sum | cut -d' ' -f1)
   sudo docker exec crypto-mock-mariadb sh -c "mariadb -u\"\$MARIADB_USER\" -p\"\$MARIADB_PASSWORD\" \"\$MARIADB_DATABASE\" -e \"INSERT INTO api_key (member_id,label,key_prefix,key_hash,is_active,scopes) VALUES (1,'lumina-autotrade','${RAW:0:16}','$HASH',1,'kis:order'); SELECT api_key_id,label,scopes FROM api_key;\""
   echo "$RAW"   # 이 값을 fd 서버 lumina .env 의 STOCK_COIN_TRADE_API_KEY 에 기입
   ```
   - `.env` 에 `KIS_PAPER_APP_KEY/SECRET/ACCOUNT_NO` 가 있어야 하고, `KIS_REAL_ORDER_ENABLED` 는 비워 둔다(false)
   - 확인: `curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $RAW" https://st.edumgt.co.kr/openapi/v1/kis/balance` → 200
3. **fd 서버 lumina `.env` 에 키 기입 후 app·celery 재기동**:
   ```bash
   ssh -i lumina-invest/fd.edumgt.co.kr.pem ubuntu@43.201.229.188 "cd /home/ubuntu/lumina-invest && sed -i 's|^STOCK_COIN_TRADE_API_KEY=.*|STOCK_COIN_TRADE_API_KEY=<RAW>|' .env && sudo env COMPOSE_FILE='docker-compose.yml:compose.fd.yml' docker compose up -d app celery-worker celery-beat"
   ```
   - 키가 비어 있는 동안 fd 의 live 모드는 레거시 직접 호출로 폴백한다(게이트웨이 미사용). 운영 계정은 아직 paper/mock 이므로 실주문은 나가지 않음
4. 운영에서 자동매매를 켤 계정의 종목 선정 화면 설정(live + KIS)은 Testbed 1주 관찰 결정(7절 L1)에 따라 진행

> **2026-10-06 갱신**: 아래 표 작성 이후 상황이 바뀌었다. 푸시·st 배포·API 키 발급은 완료됐고, domain-rag-lab 시크릿도 갱신됐다. 현재 상태는 8-1 절 참고.

**배포 결과 (15:5x KST)**
| 서버 | 결과 |
|------|------|
| fd.edumgt.co.kr (lumina) | rsync + `compose up -d --build` 완료. 컨테이너 내부 `/api/health` 200, **alembic 0009 (head)** 적용, 공개 `https://fd.edumgt.co.kr/api/health` 200. 게이트웨이는 `STOCK_COIN_TRADE_API_KEY` 가 비어 미설정 상태(레거시 폴백) — st 서버 키 발급 후 기입 |
| pr.edumgt.co.kr (domain-rag-lab) | rsync + `deploy/pr-edumgt/compose.yml up --build -d`. 첫 up 에서 api 가 Created 에 머물러(postgres 재생성 대기) `up -d api` 재실행 → healthy. `/health` 200, `/backtests/strategies` 키 없음 401 / 키 있음 200, lumina 컨테이너에서 `pr-api` 조회 성공(전략 0건). 공개 `https://pr.edumgt.co.kr/health` 200 |
| st.edumgt.co.kr (stock-coin-trade) | ~~미배포~~ → **2026-10-02 06:30Z `deploy-ec2.yml` 성공(e55bfd7)**. 이후 lumina 전용 API 키 발급 완료(lumina todo 6-8). 8-1 참고 |


### 8-1. 2026-10-06 현황 갱신

| 항목 | 상태 |
|------|------|
| origin/main | `e55bfd7` (docs(todo): 운영 배포 8절). 10-06 09:50 fetch/pull 결과 로컬=원격, **미커밋 없음** |
| GitHub secret | `EC2_HOST`, `EC2_SSH_KEY`, `EC2_USER`, `STOCK_TRADE_DEPLOY_TOKEN` 존재. 10-06 정비에서 **변경 없음**(배포가 이미 성공 중). 로컬 `pr-test.pem` 은 어느 서버 키인지 문서 근거가 없어 미사용 |
| `deploy-ec2.yml` | 최근 6회 중 5회 성공, 최신 e55bfd7 성공(10-02 06:30Z). 대상 st 43.202.161.134 `/opt/stock-coin-trade`, compose `docker-compose.yml + ssl + pg-stock`, `-p stock-coin-trade` |
| 서버 상태 | `https://st.edumgt.co.kr/health` 200(프런트 HTML), `GET /openapi/v1/kis/balance` 무키 → 401 UNAUTHORIZED(API 기동·인증 정상) |
| lumina 연동 | st MariaDB `api_key` 에 `lumina-autotrade`(member_id=1, scopes `kis:order`) 발급, fd `.env STOCK_COIN_TRADE_API_KEY` 기입 → lumina live 주문이 이 게이트웨이로 들어옴. 첫 주문 0000030540 `kis_autotrade_order` 기록 |
| KIS 키 보관 | st `.env` 에 `KIS_PAPER_*` 없음, Secrets Manager `stock-coin-trade/kis` 사용으로 추정(이름만 확인). S2 결정과 연결 |
| LEAN | `docker/lean/Dockerfile` `FROM quantconnect/lean:latest`(GenericBuyAndHold). 다른 3 저장소도 같은 이미지·latest 태그를 각자 실행 — 공용 서비스 아님 |
| 에이전트 제약 | st 서버 SSH 는 정책상 불가(변경 없음). 서버 측 확인은 사용자 수행 |

**영향 받는 외부 변경(10-06)**: lumina 에 로그인 무관 백그라운드 배치(`KIS_PAPER_BATCH_ENABLED`, 시스템 사용자 `00000000-0000-0000-0000-000000000001`)가 추가됨. 활성화되면 게이트웨이로 들어오는 주문의 `client_order_id`/사용자 식별이 시스템 사용자로 찍힌다. 사용자 계정 행이 함께 켜져 있으면 같은 Testbed 계좌로 **2개 사이클** 주문이 들어올 수 있음(S5 종목당 1건 전제 깨짐) → lumina 쪽에서 tester 행 OFF 권고.

**다음 작업**: 없음(대기). S1·S2 결정 시 6절에 추가.

### 6-7. 2026-10-06 KIS 모의투자 화면 매도 사전 보유수량 점검 (사용자 요청)

| 변경 | 내용 |
|------|------|
| `frontend/js/kis-real-trading-practice.js` | 매도 주문 직전 `precheckSell()`: 잔고를 다시 조회(`/api/broker-test/kis/balance`)해 **보유 0주 → 주문 중단 + 토스트(error 4.5s)**, **수량 > 보유 → 중단 + "매도 가능 N주" 안내**, 전량 매도면 warn 토스트. 매도 탭 전환 시 보유가 없으면 즉시 warn 토스트(비차단). 메시지 박스(`orderMessage`)에도 동일 안내 |
| `frontend/kis-real-trading-practice.html` | 스크립트 캐시 버스터 `v=20261006-sell-precheck` |

**검증**: 백엔드 pytest 79 passed(변경 없음·회귀 확인). 프런트는 괄호·백틱 균형 점검. 배포는 push → `deploy-ec2.yml`.
**참고**: 서버(`/api/broker-test/kis/orders`)도 KIS 응답으로 잔고 부족을 거부하지만, 이 변경으로 KIS 호출 전에 화면에서 먼저 막는다.

### 6-8. 2026-10-06 에러분석(error-analysis.html) 그리드 AG Grid Community 정식 구성 (사용자 요청)

**진단**: 이미 `ag-grid-community@36.0.2`(CDN) 를 쓰고 있었으나 `createGrid(... theme:'legacy')` 로 생성하면서 레거시 CSS(`ag-grid.css`·`ag-theme-*.css`)와 테마 클래스를 싣지 않아 **스타일 없는 그리드**(헤더·테두리·페이지네이션 깨짐)로 렌더됐다. 컨테이너의 `--ag-*` 변수도 레거시 전용이라 무시됨. 다른 페이지(kis-api-history 등)는 Theming API 기본으로 정상.

| 변경 | 내용 |
|------|------|
| `frontend/js/error-analysis.js` | `theme:'legacy'` 제거 → `agGrid.themeQuartz.withParams({...})`(Theming API, Community 포함). 기존 색·폰트·헤더 굵기를 파라미터로 이관. `themeQuartz` 가 없으면 기본 테마로 폴백 |
| `frontend/error-analysis.html` | `.ea-grid` 는 높이·폭만 유지(레거시 변수 제거), 스크립트 캐시 버스터 `v=20261006-theming-api` |

**유지**: 상세/피벗 전환, 플로팅 필터, 페이지네이션(25/50/100/200), 핀 고정 열, 하단 합계 행, CSV 내보내기, 행 클릭 상세 모달 — 모두 Community 기능.
**검증**: 번들에 `themeQuartz` 포함 확인. 배포 후 페이지에서 헤더 배경·행 구분선·페이지네이션 바가 보여야 정상.
