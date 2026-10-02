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
  - [ ] 전략 스펙 API (domain-rag-lab → lumina-invest)
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
- [ ] 주문 요청 스키마 확정 (lumina-invest와 합의)
  - `symbol`(6자리), `side`(BUY/SELL), `quantity`, `order_type`(MARKET/LIMIT), `price`, `environment`(paper/real), `client_order_id`(멱등키)
- [ ] 주문 응답 스키마: `order_no`(ODNO), `order_time`, `environment`, `client_order_id`, `message`
- [ ] 체결 조회 응답 스키마: `order_no`, `status`(접수/부분체결/체결/거부/취소), `ordered_qty`, `filled_qty`, `avg_price`, `updated_at`
- [ ] 에러 코드 표 정리 (KIS `msg_cd` → HTTP 상태 + 내부 코드 매핑)

### 2-2. 게이트웨이 환경 분리 (Phase 2)
- [ ] `kis_request()`에 `environment: Literal["paper","real"]` 인자 추가, URL·토큰 캐시·자격증명을 환경별로 분리
  - 토큰 캐시 `_kis_token_cache`를 환경별 dict로
  - `_kis_credentials()`/`_kis_account()`가 `KIS_PAPER_*` / `KIS_REAL_*` 중 선택
- [ ] tr_id 매핑 테이블 신설 (paper ↔ real)
  - 매수 `VTTC0012U` ↔ `TTTC0012U`, 매도 `VTTC0011U` ↔ `TTTC0011U`
  - 체결조회 `VTTC8001R` ↔ `TTTC8001R`, 잔고 `VTTC8434R` ↔ `TTTC8434R`
  - 정정/취소 `VTTC0013U` ↔ `TTTC0013U`
- [ ] 레이트리밋이 환경별 별도 토큰이지만 KIS 계정 공통 제한인지 확인 후 `_kis_api_rate_lock` 범위 결정

### 2-3. 실주문 서비스 (Phase 2)
- [ ] `place_kis_paper_order()`를 일반화한 `place_kis_order(environment, ...)` 추가 (기존 함수는 wrapper로 유지)
  - 실전 한도 env 추가: `KIS_REAL_MAX_ORDER_AMOUNT`, `KIS_REAL_MAX_ORDER_QUANTITY`, `KIS_REAL_ALLOWED_SYMBOLS`(선택, 화이트리스트)
  - 실전은 `KIS_REAL_ORDER_ENABLED=true` 플래그가 없으면 **무조건 거부** (Phase 5까지 기본 false)
- [ ] 멱등성: `client_order_id` 저장 테이블(`kis_orders`) 신설. 동일 키 재요청 시 새 주문 없이 기존 결과 반환
- [ ] **승인 토큰 Open API 버전**: 세션 대신 서버 저장소(Redis 또는 DB `order_approvals`)에 `token_digest`, `intent_digest`, `api_key_id`, `expires_at(+60s)`, `used_at` 저장. 1회 사용 후 즉시 소멸, 의도(symbol/side/qty/price) 불일치 시 거부
- [ ] 회당 주문 한도를 환경별로 분리하고 API Key 단위 한도도 추가 (`KIS_REAL_MAX_ORDER_AMOUNT`, API Key별 `max_order_amount`)
- [ ] KIS 자격증명 로딩 순서 확정: AWS Secrets Manager(`aws_secret_store.get_secret("kis-real")`) → env 폴백. 실전 키는 **env에 두지 않는 것**을 기본으로
- [ ] 주문 레코드 저장: 요청 원문, KIS 응답, `order_no`, 환경, 호출 주체(API Key member), 상태
- [ ] 정정/취소 함수 `cancel_kis_order(environment, order_no, ...)` 추가 (kill switch 시 lumina가 호출)

### 2-4. 체결 조회 서비스 (Phase 2)
- [ ] `get_kis_order_status(environment, order_no)` — `inquire-daily-ccld`에서 해당 주문 찾아 상태 정규화
- [ ] `kis_orders` 테이블 상태 갱신 (조회 시 또는 백그라운드 폴링)
- [ ] 당일 미체결 목록 `get_kis_open_orders(environment)` (기존 `_kis_open_orders_today()` 공개 함수화)

### 2-5. Open API 엔드포인트 신설 (Phase 2)
`api/routes/openapi.py` 또는 새 라우터 `api/routes/openapi_kis.py` (API Key 인증 유지)
- [ ] `POST /openapi/v1/kis/order-approval` — 60초 1회용 승인 토큰 발급 (주문 의도 포함)
- [ ] `POST /openapi/v1/kis/orders` — 주문 (승인 토큰 필수. 기존 가상 `/orders`와 **분리**, 혼동 방지)
- [ ] `GET  /openapi/v1/kis/orders/{order_no}` — 체결 상태
- [ ] `GET  /openapi/v1/kis/orders?date=&status=` — 당일 주문/체결 목록
- [ ] `DELETE /openapi/v1/kis/orders/{order_no}` — 취소
- [ ] `GET  /openapi/v1/kis/balance` — 잔고 (lumina 실계좌 기준 일손실 계산용)
- [ ] API Key에 **권한 스코프** 추가: `kis:paper:order`, `kis:real:order`, `kis:read`. 실전 주문 스코프는 수동 발급만
- [ ] 실전 주문은 `KIS_REAL_OWNER_EMAIL` 소유자 검증(`kis_real.py` 로직) 재사용
- [ ] 요청/응답 전부 `api_usage` 로그 + `_audit_kis_call` 감사로그 연결 확인

### 2-6. 테스트 (Phase 2·4)
- [ ] `kis_request` 환경 분기 단위 테스트 (URL·헤더·tr_id)
- [ ] 멱등키 중복 요청 테스트, `rt_cd != "0"` 응답 처리 테스트
- [ ] Testbed 실호출 스모크 테스트 (환경변수 있을 때만 실행)
- [ ] lumina-invest 게이트웨이 클라이언트와 계약 테스트 (스키마 고정 후)

---

## 3. 다른 저장소와의 인터페이스

- **← lumina-invest**: 위 2-5 엔드포인트 호출 (API Key 헤더, 서버 간 호출). 10분 사이클마다 승인 토큰 → 주문 2단계 호출, 1~2분 체결 확인 폴링
- 최초 트리거는 lumina-invest 웹앱 종목 선정 화면이며, 이 저장소는 **사용자 화면 없이 API만** 제공한다
- **→ lumina-invest**: 주문 결과·체결 상태·잔고 응답

---

## 4. 미결 사항 (결정 필요)

- [ ] 체결 상태를 lumina가 폴링할지, stock-coin-trade가 webhook/콜백으로 밀어줄지 (초기엔 폴링 권장)
- [ ] 기존 `POST /openapi/v1/orders`(가상) 유지 여부와 문서 표기
- [ ] 실전 전환 시 운영자 2인 승인 같은 추가 안전장치 둘지
- [ ] `vscode-kis-mcp/`의 KIS 호출과 게이트웨이 통합 여부

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
