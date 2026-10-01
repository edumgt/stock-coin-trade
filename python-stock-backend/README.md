# python-stock-backend — FastAPI 백엔드

주식·암호화폐 모의투자 및 OpenAPI 학습 플랫폼의 API 서버입니다. Flask 단일 디렉터리 구조에서
**FastAPI + Pydantic v2 + SQLAlchemy 2.0(타입 매핑) + pydantic-settings + uv** 기반의 계층형 패키지로
리팩토링했습니다. 모든 URL 경로와 JSON 응답 형식은 이전 Flask 버전과 동일하게 유지되어 프런트엔드 변경 없이 동작합니다.

| 항목 | 선택 | 비고 |
|---|---|---|
| 웹 프레임워크 | FastAPI (Starlette ASGI) | 라우터·의존성 주입·자동 OpenAPI 문서(`/api/docs`) |
| 검증·설정 | Pydantic v2, pydantic-settings | 요청 본문 스키마, `.env` 기반 `Settings` |
| ORM | SQLAlchemy 2.0 `Mapped[]`/`mapped_column`, `select()` | 레거시 `Query` API 미사용 |
| 세션 | Redis 서버 세션(자체 ASGI 미들웨어) + 서명 쿠키 | Flask-Session과 같은 모델(쿠키에는 서명된 ID만) |
| 서버 | uvicorn (worker 1, 스레드풀) | KIS 호출 제한기가 프로세스 메모리에 있어 단일 worker 유지 |
| 배치 | APScheduler 3 | 코인 랭킹·업비트 마켓·봇 거래·OHLCV 증분 수집 |
| 패키지 관리 | uv + `pyproject.toml` + `uv.lock` | Docker 빌드도 `uv sync --frozen` |
| 품질 | ruff, pytest + httpx TestClient | `uv run ruff check`, `uv run pytest` |

---

## 1. 디렉터리 하이어라키

```text
python-stock-backend/
├── pyproject.toml                 # 의존성·ruff·pytest 설정(uv 프로젝트, package=false)
├── uv.lock                        # 재현 가능한 잠금 파일(Docker 빌드가 그대로 사용)
├── .python-version                # 3.12
├── README.md                      # 이 문서
├── app/                           # 애플리케이션 패키지(배포 단위)
│   ├── __init__.py                # 패키지 구성 요약
│   ├── main.py                    # FastAPI 팩토리 create_app(), lifespan, 미들웨어 스택, `app` 인스턴스
│   ├── startup.py                 # 기동 시 1회 작업(테이블 보정·시드·봇 계정) 오케스트레이션
│   ├── models.py                  # SQLAlchemy 2.0 타입 매핑 모델(MariaDB 회원·모의투자 스키마)
│   │
│   ├── core/                      # 프레임워크 기반 계층(도메인 지식 없음)
│   │   ├── config.py              #   Settings(pydantic-settings) · 저장소 루트 .env 로드 · 경로 상수
│   │   ├── database.py            #   SQLAlchemy 엔진/세션팩토리 · session_scope() · get_db 의존성(DbSession)
│   │   ├── sessions.py            #   서버 세션 미들웨어(Redis/Memory 저장소, 서명 쿠키, regenerate)
│   │   ├── security.py            #   세션 결합 CSRF 토큰 발급·검증
│   │   ├── deps.py                #   공통 의존성: MemberId/OptionalMemberId, login_required(), csrf_required()
│   │   ├── errors.py              #   ApiError(상태코드+JSON 본문) · 예외 핸들러(400 INVALID_REQUEST 등)
│   │   ├── context.py             #   ContextVar 기반 요청 컨텍스트(RequestInfo) — Flask 전역 대체
│   │   ├── middleware.py          #   RequestAuditMiddleware: 4xx/5xx·외부 API 테스트 응답 감사 기록
│   │   └── parsing.py             #   parse_int/parse_float/clamp — 관대한 입력 파싱 유지
│   │
│   ├── api/                       # HTTP 어댑터 계층(얇은 라우터)
│   │   ├── router.py              #   모든 라우터를 api_router 하나로 집계
│   │   ├── schemas.py             #   요청 본문 Pydantic 스키마(LoginBody, StockOrderBody, …)
│   │   └── routes/                #   도메인별 APIRouter — 각 모듈이 자신의 prefix를 소유
│   │       ├── health.py          #     GET /health
│   │       ├── members.py         #     /api/member: me·login·register·logout·hts-memos·portfolio-analysis·랭킹
│   │       ├── api_keys.py        #     /api/member/api-keys: Open API 키 발급·폐기
│   │       ├── market.py          #     /api/stocks(공개): KRX 목록·검색·시세·차트·movers·prices·Qdrant RAG·KRX 뉴스
│   │       ├── stocks.py          #     /api/stocks(로그인): 계좌·포지션·매수/매도/미리보기/Pine·이력·초기화
│   │       ├── crypto.py          #     /api/crypto(공개) · /api/trade(로그인): 코인 시세·보유·매수/매도/미리보기
│   │       ├── alternatives.py    #     /api/alternatives: 파생·귀금속·부동산 모의 시장·주문
│   │       ├── broker_test.py     #     /api/broker-test: KIS Testbed·KB증권 읽기 전용 + 승인 토큰 기반 모의 주문
│   │       ├── broker_test_aws.py #     /api/aws-broker-test: Secrets Manager 자격증명 트랙
│   │       ├── alpaca_test.py     #     /api/alpaca-test: Alpaca Paper 읽기 전용 + 주문→취소 흐름
│   │       ├── alpaca_test_aws.py #     /api/aws-alpaca-test
│   │       ├── crypto_exchange_test.py # /api/crypto-exchange-test: Binance·Korbit 공개 시세
│   │       ├── kis_explorer.py    #     /api/kis-explorer: KIS API 카탈로그·대리 호출(GET·Testbed만)
│   │       ├── kis_chart.py       #     /api/kis-chart: 일/주/월/년봉·분봉 캔들
│   │       ├── kis_practice.py    #     /api/kis-practice: 격리된 연습 원장
│   │       ├── kis_real.py        #     /api/kis-real: 계좌 소유자 전용 실전 잔고(읽기 전용)
│   │       ├── openapi.py         #     /openapi/v1: Bearer API 키 인증·공개 OHLCV 조회·가상 계좌 주문
│   │       ├── ohlcv_db.py        #     /api/ohlcv-db: pg-stock 집계·행 조회(AG Grid)
│   │       ├── quant.py           #     /api/quant: 시계열·시그널·백테스트·팩터 분석
│   │       ├── ai.py              #     /api/ai/analyze: Claude SSE 스트리밍
│   │       ├── ai_sheet.py        #     /api/ai-sheet: URL 표 추출·섹터 시트·퀀트 분석·LEAN 백테스트
│   │       ├── aria.py            #     /api/aria: ARIA 블록암호 데모
│   │       ├── admin.py           #     /api/admin/me
│   │       ├── error_analysis.py  #     /api/error-analysis: 클라이언트 오류 수집·진단 로그 조회
│   │       └── api_usage.py       #     /api/api-usage: 외부 API 사용이력(KIS/KB/Alpaca)
│   │
│   ├── services/                  # 도메인·외부 연동 계층(HTTP를 모름, 라우터와 배치가 공유)
│   │   ├── stock_market.py        #   KRX 종목 목록·시세·차트 캐시(yfinance → 네이버 → 시뮬레이션 폴백)
│   │   ├── stock_trading.py       #   주식 모의 주문 체결·포지션·계좌 스냅샷(행 잠금)
│   │   ├── crypto.py              #   코인 시장 조회·업비트 현재가·매수/매도 체결
│   │   ├── alternatives.py        #   대체자산 카탈로그·교육용 시세·주문 체결·테이블 보정
│   │   ├── members.py             #   비밀번호 해시·HTS 메모·포트폴리오 어드바이저·투자자 랭킹
│   │   ├── authz.py               #   관리자·KIS 계좌 사용 권한
│   │   ├── volatility.py          #   연환산 변동성 유틸
│   │   ├── kis_practice.py        #   KIS 연습 원장(예수금·포지션·체결)
│   │   ├── krx_news.py            #   KRX 보도자료 조회·5분 캐시
│   │   ├── knowledge_base.py      #   Qdrant + fastembed RAG(시드 지식, 검색, 문서 추가)
│   │   ├── ai_sheet.py            #   공개 URL 크롤러(SSRF 방지)·월별 종가·sklearn 회귀·LEAN Docker 실행
│   │   ├── quant.py               #   PostgreSQL quant_research 질의·전략 시그널·백테스트·팩터 회귀
│   │   ├── ohlcv_store.py         #   pg-stock 읽기 전용 질의(내부 화면 + Open API 공용)
│   │   ├── openapi_auth.py        #   Bearer API 키 검증·메모리 호출 제한
│   │   ├── api_usage.py           #   외부 API 사용이력 기록(마스킹)·조회
│   │   ├── error_analysis.py      #   시스템 오류 기록(마스킹)·조회
│   │   ├── audit.py               #   미들웨어가 호출하는 응답 기록기(api_usage + error_analysis 조합)
│   │   ├── aws_secret_store.py    #   AWS Secrets Manager 자격증명 소스(캐시, 값 비노출)
│   │   ├── crypto_exchanges.py    #   Binance·Korbit 공개 시세 조회
│   │   ├── aria_cipher.py         #   순수 파이썬 ARIA(RFC 5794) + CBC/PKCS#7
│   │   ├── demo_seed.py           #   샘플 투자자·시연 계정 시드(멱등)
│   │   ├── brokers/               #   증권사 게이트웨이
│   │   │   ├── common.py          #     BrokerApiError · 자격증명 출처(.env/AWS) · JSON 파싱
│   │   │   ├── kis.py             #     KIS Testbed 공통 게이트웨이 kis_request(제한기·재시도·감사) + 조회·모의 주문
│   │   │   ├── kb.py              #     KB증권 토큰·투자정보 TR·차트 정규화
│   │   │   ├── aws.py             #     Secrets Manager 자격증명으로 KIS/KB 조회(병행 트랙)
│   │   │   ├── kis_chart.py       #     기간별·분봉 캔들 조립·LRU 캐시
│   │   │   ├── kis_explorer.py    #     카탈로그 로드·파라미터 조립(계좌값 서버 주입)·대리 호출
│   │   │   └── kis_real.py        #     실전 계좌 토큰·잔고(소유자 이메일 검증, 지연 조회)
│   │   └── alpaca/
│   │       ├── paper.py           #     Alpaca Paper 읽기 전용 조회·주문→취소 흐름(감사 기록)
│   │       └── aws.py             #     Secrets Manager 자격증명 트랙
│   │
│   ├── jobs/                      # 배치·스케줄 계층
│   │   ├── scheduler.py           #   APScheduler 등록(코인마켓캡·업비트·봇·OHLCV cron)
│   │   ├── market_bots.py         #   system01~20 봇 거래 라운드(실사용자와 같은 체결 함수 호출)
│   │   ├── ohlcv_sync.py          #   종목·연도 단위 멱등 OHLCV 수집(plan_year_ranges)
│   │   ├── ohlcv_aggregate.py     #   대시보드 집계 스냅샷·일일 배치 원장
│   │   └── ohlcv_crawler.py       #   주요 종목 OHLCV 수집기(`python -m app.jobs.ohlcv_crawler`)
│   │
│   ├── cli/                       # 독립 실행 스크립트(`python -m app.cli.<name>`)
│   │   ├── kis_quote_test.py      #   KIS Testbed 현재가 점검
│   │   ├── kb_token_test.py       #   KB 토큰 발급 점검
│   │   └── upload_keys_to_secrets_manager.py  # .env → Secrets Manager 적재(미리보기 기본)
│   │
│   └── resources/
│       └── kis_api_catalog.json   # KIS API 탐색기 카탈로그(scripts/build_kis_api_catalog.py가 생성)
│
└── tests/                         # pytest (httpx TestClient, 메모리 세션 저장소, DB 의존성 오버라이드)
    ├── conftest.py                # app/client/login 픽스처
    ├── test_sessions_and_auth.py  # 세션 쿠키·CSRF·로그인/로그아웃·필드 오류
    ├── test_kis_hardening.py      # KIS 게이트웨이 제한·감사·승인 토큰 단일 사용
    ├── test_kb_lab.py / test_alpaca_lab.py / test_kis_real.py / test_kis_practice.py
    ├── test_aria_cipher.py        # RFC 5794 벡터·OpenSSL 교차 검증·API
    ├── test_crypto_exchange_symbols.py
    └── test_ohlcv_sync.py
```

## 2. 계층 간 의존 규칙

```text
        ┌──────────────────────────────────────────────────────┐
        │  app/main.py  (create_app · lifespan · 미들웨어 스택)  │
        └───────────────┬──────────────────────┬───────────────┘
                        │                      │
                 app/api/routes/*        app/jobs/* (APScheduler)
                 (HTTP 어댑터)            app/startup.py
                        │                      │
                        └──────────┬───────────┘
                                   ▼
                          app/services/**  (도메인 로직)
                                   │
                        ┌──────────┴──────────┐
                        ▼                     ▼
                  app/models.py          app/core/*
              (SQLAlchemy 매핑)   (config · database · context · errors)
```

- **api → services → models/core** 방향으로만 의존합니다. `services`는 `fastapi`를 import하지 않으며, 라우터와 배치(`jobs`)가 같은 서비스 함수를 공유합니다(예: 봇 거래도 `stock_trading.execute_order`를 호출).
- `core`는 도메인을 모릅니다. 유일한 예외는 `core/middleware.py`가 **콜백(recorder)** 으로 `services/audit.py`를 주입받는 구조로, import 방향은 여전히 `main → core`, `main → services`입니다.
- 라우터는 **파싱 → 권한 확인 → 서비스 호출 → 응답 형식 유지**만 담당합니다. 비즈니스 규칙(잔액 검증, 체결 계산, 외부 API 호출)은 서비스에 있습니다.

## 3. 요청 처리 흐름

```text
Browser ──▶ Nginx ──▶ uvicorn
   ServerErrorMiddleware (Starlette 기본)               : 처리되지 않은 예외 → 500
   └─ PathScopedCORSMiddleware (app/main.py)            : /api/* 는 localhost origin + 쿠키, /openapi/* 는 * (쿠키 없음)
      └─ ServerSessionMiddleware (core/sessions.py)      : 쿠키의 서명된 sid → Redis JSON → request.session(dict)
         └─ RequestAuditMiddleware (core/middleware.py) : ContextVar(RequestInfo) 설정, 4xx/5xx·외부 API 테스트 응답 기록
            └─ ExceptionMiddleware (FastAPI)            : ApiError/RequestValidationError → JSON 본문
               └─ APIRouter → 의존성 해결 → 라우트 함수(동기, 스레드풀) → 서비스 → DB/외부 API
```

1. **세션**: `request.session`은 요청 동안 살아 있는 dict(`SessionData`)입니다. 쓰기가 있을 때만 응답 시 Redis에 저장하고 쿠키를 갱신하며, 로그인 직후 `session.regenerate()`로 ID를 교체해 세션 고정을 막습니다. `logout`은 `session.clear()`만 호출하면 키와 쿠키가 함께 삭제됩니다.
2. **인증·CSRF**: 로그인 여부는 `MemberId`(401) / `OptionalMemberId` 의존성으로, 상태 변경 API는 `csrf_required()` 의존성으로 검사합니다. 모듈별 401/403 본문 형식(`{"ok": false, ...}` 등)은 팩토리 인자로 유지합니다.
3. **DB 트랜잭션**: `DbSession = Annotated[Session, Depends(get_db, scope="function")]`. 라우트 함수가 정상 반환하면 **응답을 보내기 전에** commit, `ApiError`를 포함한 예외가 나오면 rollback 합니다(`scope="function"`은 FastAPI 0.118+에서 yield 의존성의 종료 코드를 응답 전송 전에 실행하게 합니다). 배치·시드·감사 기록처럼 요청 밖의 코드는 `session_scope()` 컨텍스트 매니저를 씁니다.
4. **오류 응답**: 모든 실패는 `ApiError(status, **body)`로 던지며 본문이 그대로 JSON이 됩니다. Pydantic 검증 실패는 FastAPI 기본 422 대신 `400 {"error": "INVALID_REQUEST", "message": ...}`로 바꿔 프런트엔드의 `data.error || data.message` 표시 규칙을 지킵니다.
5. **감사 로그**: Flask의 `after_request` 역할을 `RequestAuditMiddleware`가 맡습니다. JSON 응답 중 4xx/5xx와 `/api/broker-test/*`·`/api/kis-*`·`/api/*alpaca*`·`/api/crypto-exchange-test/*` 응답 본문만 메모리에 모아 `system_error_log`·`api_usage_log`에 기록합니다. SSE 스트리밍(`/api/ai/analyze`)은 JSON이 아니므로 버퍼링하지 않습니다. 게이트웨이(`brokers/kis.py` 등)가 외부 호출을 기록할 때 호출자 정보는 `core/context.py`의 ContextVar에서 읽습니다.

## 4. 설정(Settings) 체계

`app/core/config.py`의 `Settings`가 저장소 루트 `.env`와 환경변수를 읽습니다(환경변수 우선). 대표 항목:

| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME`/`MARIADB_DATABASE`, `DB_USER`/`MARIADB_USER`, `DB_PASSWORD`/`MARIADB_PASSWORD` | `mariadb`, 3306, mockinv… | 회원·모의투자 DB. Compose는 `DB_*`로 넘기고, 직접 실행 시 `.env`의 `MARIADB_*`를 그대로 씀 |
| `SECRET_KEY` | dev-secret-change-me | 세션 쿠키 서명 키 |
| `REDIS_URL`, `REDIS_SESSION_KEY_PREFIX` | redis://redis:6379/0 | 서버 세션 저장소 |
| `SESSION_STORE` | redis | `memory`로 두면 Redis 없이 로컬 실행(세션은 프로세스 메모리) |
| `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_SAMESITE`, `SESSION_LIFETIME_DAYS` | false, lax, 7 | 쿠키 속성 |
| `APP_STARTUP_TASKS` | true | 기동 시 테이블 보정·시드·봇 계정 생성 실행 여부 |
| `SCHEDULER_ENABLED` | true | APScheduler 기동 여부 |
| `AUDIT_ENABLED` | true | 4xx/5xx·외부 API 테스트 응답 DB 기록 여부 |
| `DEMO_SEED_ENABLED` | true | 샘플 투자자 30명 시드 |
| `ADMIN_EMAIL` | admin@admin.com | 관리자 판별 |
| `QUANT_DATABASE_URL`, `OHLCV_DATABASE_URL`, `QDRANT_URL` | … | 보조 저장소 |
| `OHLCV_SYNC_*` | … | OHLCV 증분 수집 주기·종목·공급자 |
| `CMC_API_KEY`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `ARIA_DEMO_KEY` | 빈 값 | 외부 서비스 |
| `AWS_REGION`/`AWS_DEFAULT_REGION`, `AWS_SECRETS_MANAGER_PREFIX` | —, stock-coin-trade | Secrets Manager 트랙 |

**자격증명 예외**: `KIS_PAPER_*`, `KIS_REAL_*`, `KB_*`, `ALPACA_*`, `CREDENTIAL_SOURCE`, `KIS_PAPER_MAX_ORDER_*`는 의도적으로 `Settings`에 넣지 않고 `app/services/brokers/*`·`app/services/alpaca/*`가 **호출 시점마다 환경변수에서** 읽습니다. 값이 전역 객체에 캐시되지 않고, 키 교체가 재기동만으로 반영되며, 테스트에서 `patch.dict("os.environ")`로 손쉽게 격리할 수 있습니다.

## 5. 실행·개발

```bash
cd python-stock-backend
uv sync                                     # .venv 생성 + 의존성 설치(dev 포함)

# Docker 없이 로컬 실행(DB는 Compose의 MariaDB 포트 공개를 사용, Redis 없이 메모리 세션)
DB_HOST=127.0.0.1 SESSION_STORE=memory APP_STARTUP_TASKS=false \
  uv run uvicorn app.main:app --reload --port 8200

uv run ruff check app tests                 # 린트
uv run pytest                               # 테스트(DB·Redis 불필요, 약 2초)

# 독립 스크립트
uv run python -m app.cli.kis_quote_test --symbol 005930
uv run python -m app.cli.kb_token_test
uv run python -m app.cli.upload_keys_to_secrets_manager --region ap-northeast-2        # 미리보기
uv run python -m app.jobs.ohlcv_crawler --dry-run                                       # OHLCV 수집기
```

- 자동 문서: `http://localhost:8200/api/docs` (Swagger UI), 스키마 `GET /api/openapi.json`.
- 컨테이너는 `docker/python-backend.Dockerfile`이 `uv sync --frozen --no-dev`로 설치한 뒤 `uvicorn app.main:app --workers 1`로 기동합니다.

## 6. 테스트 전략

- `tests/conftest.py`의 `app` 픽스처는 `create_app(settings, session_store=MemorySessionStore())`로 기동 작업·스케줄러·감사 기록을 끈 앱을 만듭니다.
- `login(member_id, csrf_token)` 헬퍼가 메모리 세션 저장소에 회원 세션을 넣고 서명된 쿠키를 TestClient에 심습니다(Flask의 `session_transaction()` 대체).
- DB가 필요한 라우트는 `app.dependency_overrides[get_db]`로 가짜 세션을 주입하고, 외부 HTTP는 `unittest.mock.patch`로 `requests`를 막습니다.

## 7. Flask 버전과의 차이·운영 참고

- **세션 저장 형식**: Flask-Session의 pickle 대신 JSON으로 저장하므로, 배포 직후 기존 로그인 세션은 1회 무효화되어 재로그인이 필요합니다(키 접두사는 동일).
- **쿠키 이름**은 `session`으로 동일하며 `HttpOnly`·`SameSite=Lax`·7일 TTL(접근 시 연장)을 유지합니다.
- **RAG**: qdrant-client 1.19부터 fastembed 통합 헬퍼(`add`/`query`)가 제거되어 `fastembed.TextEmbedding`으로 직접 임베딩하고 `upsert`/`query_points`를 사용합니다. 벡터 이름·payload 형식은 이전 컬렉션과 호환됩니다.
- **잘못된 입력**: 과거 일부 엔드포인트가 500으로 응답하던 형식 오류(예: 숫자 파라미터에 문자)는 이제 일관되게 `400 INVALID_REQUEST`입니다. 범위를 벗어난 `limit` 등은 이전처럼 조용히 클램프합니다.
- **worker 수**: KIS 호출 제한기·토큰 캐시가 프로세스 메모리에 있으므로 uvicorn worker는 1개를 유지합니다. 수평 확장 시 Redis 기반 제한기로 전환해야 합니다.
