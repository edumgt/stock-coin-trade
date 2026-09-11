# 모의투자 · OpenAPI 실습 플랫폼

<p align="center">
  <img src="./archi.png" alt="시스템 아키텍처 다이어그램" width="900">
</p>

## AWS 에 Lambda 구성, API GW 구성, 해당 repo FE EC2 구성
## 개인별 ML/DL 대체 AI resource 연동

Flask REST API와 Vanilla JavaScript로 만든 주식·암호화폐 모의투자 및 OpenAPI 학습 플랫폼입니다. 국내 주식·코인 모의 주문, 대체자산 실습, 외부 연동용 Open API, 증권사·Alpaca Paper API의 읽기 전용 연결 테스트를 제공합니다.

> 교육·연습용 프로젝트입니다. 증권사 및 Alpaca 연결 테스트는 키 검증과 읽기 전용 조회만 다루며, 실제 주문 자동화 기능을 제공하지 않습니다.

## 주요 기능

- 회원가입·로그인 기반 모의 주식·코인 거래와 보유자산·거래이력 조회
- KRX 주식 시세·차트·검색, 코인 시세·국내 거래소 가격 비교
- 대체자산(선물·옵션·금속·부동산 지분) 모의 주문
- AI Sheet: 공개 웹페이지 표 가져오기, 섹터별 상위 20개 종목의 최근 24개월 월별 종가 시트(yyyy-mm × 종목명) 생성
  - 퀀트분석: M-2까지의 월별 종가로 scikit-learn LinearRegression을 학습해 M-1을 예측하고 실제 값과 비교(종목명과 함께 고정 표시)
  - LEAN: 선택한 종목의 월별 종가로 QuantConnect LEAN(Docker) 매수 후 보유 백테스트를 실행하는 테스트 버튼 — 자세한 내용은 아래 "운영 시 유의사항" 참고
- 투자 분석 학습, Qdrant 기반 지식 검색 및 AI 분석 기능
- 외부 시스템용 Open API 키 발급 및 가상 주식계좌 연동 API
- 실전연습 학습 페이지
  - TradingView(Pine)
  - KB증권 Open API
  - 한국투자증권(KIS) API
  - Alpaca Paper Trading 및 Trading CLI
- 분석·도구의 읽기 전용 연결 테스트
  - `증권사 시세 테스트`: KIS Testbed 현재가, KB증권 인증 상태
  - `Alpaca Test`: Alpaca Paper 계정 상태
- (선택) VS Code용 한투 공식 KIS MCP 서버 연동 — 자세한 내용은 아래 "KIS MCP" 절 참고

## 4일 Open API 실습 커리큘럼

외부 플랫폼 가입·키 발급은 오전에, 이 웹앱의 안전한 조회·모의 실습은 오후에 진행하는 4일 과정입니다. Key·Secret·계좌번호는 제출물에 포함하지 않습니다.

| 일차 | 오전 | 오후 | 문서 |
|---|---|---|---|
| 1일차 | KIS 모의투자·API 신청 | Testbed 조회와 모의 주문→정정→취소 | [01.md](curriculum/01.md) |
| 2일차 | KB Open API 신청·키 발급 | 운영 시세·호가·차트 읽기 전용 조회 | [02.md](curriculum/02.md) |
| 3일차 | Alpaca Paper 계정·키 발급 | Paper 계정·시세와 주문→취소 흐름 | [03.md](curriculum/03.md) |
| 4일차 | Binance·Korbit 공개/개인 API 권한 구분 | 공개 시세·호가와 통합 보안 점검 | [04.md](curriculum/04.md) |

## 아키텍처

```text
Browser
  │
  ▼
Nginx Frontend (:3000)
  ├─ 정적 HTML / JavaScript / CSS
  ├─ /api/*      → Flask Backend
  └─ /openapi/*  → Flask Backend
                     │
                     ├─ MariaDB (회원·모의 주문)
                     ├─ PostgreSQL (퀀트 OHLCV·전략·체결·성과)
                     ├─ 국내·해외 시세 제공처
                     └─ KIS / KB증권 / Alpaca Paper API (선택, 읽기 전용 테스트)
```

| 영역 | 구성 | 역할 |
|---|---|---|
| Frontend | Nginx, HTML, Vanilla JS, Tailwind CDN | 화면·오프캔버스 메뉴·API 호출 |
| Backend | Flask, SQLAlchemy, Requests | 회원·모의 주문·시세·Open API·외부 API 테스트 |
| Data | MariaDB, PostgreSQL, Qdrant(선택) | 사용자·주문, 퀀트 시계열/백테스트, AI 지식 검색 |
| 운영 | Docker Compose | frontend, python-backend, mariadb(local profile) |

## 빠른 시작

### 요구사항

- Docker Engine 및 Docker Compose v2
- 외부 시세·AI 기능은 인터넷 연결 및 해당 서비스 키가 필요할 수 있습니다.

### 1. 환경 파일 준비

```bash
cp .env.example .env
```

`.env`에는 DB 비밀번호, 세션 키, 선택적 API 키만 설정합니다. 실제 값은 Git에 커밋하지 않습니다.

### 2. 선택적 증권사 테스트 키 파일 준비

Docker Compose는 키 파일을 이미지에 복사하지 않고 `/run/secrets`에 읽기 전용으로 마운트합니다. 해당 테스트를 사용하려면 저장소 루트에 파일을 둡니다. 파일은 `*.key` 규칙으로 Git에서 제외됩니다.

```text
al.key   # Alpaca: Key=..., Secret=...
kb.key   # KB증권: AppKey=..., Secret=...
kis.key  # KIS: App-KEY=..., Secret=...
```

테스트를 사용하지 않더라도 Compose 실행을 위해 빈 파일을 만들 수 있습니다. 빈 파일에서는 해당 테스트가 설정 오류를 반환하며 주문은 실행되지 않습니다.

```bash
touch al.key kb.key kis.key
```

### 3. 실행

```bash
docker compose up -d --build
docker compose ps
```

`.env`의 `COMPOSE_PROFILES=local-db` 설정을 사용하면 로컬 MariaDB 프로필이 함께 기동됩니다.

### 4. 접속

| 주소 | 설명 |
|---|---|
| <http://localhost:3000> | 웹 애플리케이션 |
| <http://localhost:3000/broker-api-test.html> | 증권사 시세 테스트 |
| <http://localhost:3000/alpaca-test.html> | Alpaca Paper API 테스트 |
| <http://localhost:3000/openapi.html> | 외부 연동 Open API 명세 |
| <http://localhost:3000/quant.html> | PostgreSQL 퀀트 랩 |

Nginx는 `/api/*`, `/openapi/*`를 Flask로 프록시합니다. 브라우저에서는 API 호출을 같은 origin으로 처리합니다.

### 5. 종료

```bash
docker compose down
```

로컬 DB 볼륨까지 제거하려면 다음 명령을 사용합니다. 데이터가 삭제되므로 주의하세요.

```bash
docker compose down -v
```

## 공개 멀티자산 데모 계정과 메뉴

<https://st.edumgt.co.kr>에서 바로 로그인해 확인할 수 있도록, 주식·암호화폐·대체자산 포지션을 각각 포함한 공개 데모 계정 5개를 준비했습니다. 아래 계정은 교육·기능 테스트 전용이며, 실제 개인정보·실계좌·외부 API 키를 연결하지 않습니다. 공개된 계정이므로 비밀번호 변경, 개인 정보 입력, 실제 서비스 용도의 사용은 금지합니다.

| 투자 유형 | ID(이메일) | 비밀번호 | 사전 구성 포지션 |
|---|---|---|---|
| 보수형 | `multiasset-demo-01@edumgt.test` | `DemoMultiAsset2601` | 삼성전자 · 비트코인 · 금 |
| 균형형 | `multiasset-demo-02@edumgt.test` | `DemoMultiAsset2602` | SK하이닉스 · 이더리움 · 판교 아파트 지분 |
| 성장형 | `multiasset-demo-03@edumgt.test` | `DemoMultiAsset2603` | NAVER · 리플 · 미국 달러 선물 |
| 실물형 | `multiasset-demo-04@edumgt.test` | `DemoMultiAsset2604` | 현대차 · 솔라나 · KOSPI 200 콜옵션 |
| 파생형 | `multiasset-demo-05@edumgt.test` | `DemoMultiAsset2605` | POSCO홀딩스 · 에이다 · KOSPI 200 레버리지 |

각 계정은 초기 가상 현금도 보유합니다. 여러 사용자가 같은 공개 계정을 함께 사용하므로 주문·매도·초기화에 따라 포트폴리오 상태는 변경될 수 있습니다.

좌측 공통 offcanvas 메뉴는 모든 페이지가 같은 `frontend/js/common.js`를 사용합니다.

| 메뉴 | 주요 화면 |
|---|---|
| 거래 | 코인, 주식, 대체자산 |
| 자산관리 | 보유자산, 거래이력, 물타기 계산기 |
| 실전연습 | TradingView(Pine), KB증권, 한국투자증권 API, Alpaca API |
| 분석 · 도구 | AI Sheet, Open API, 증권사 시세 테스트, Alpaca Test |

## API 요약

### 모의투자 주문·분석 API

모든 주문 API는 로그인 세션이 필요합니다. `preview` API는 현재 시세와 보유 현금·수량을 기준으로 실행 가능 여부만 계산하며, 주문·잔고·거래 이력을 변경하지 않습니다.

| Method | Path | 설명 |
|---|---|---|
| `POST` | `/api/stocks/orders/preview` | 주식 시장가 주문의 예상 체결 금액·현금·보유수량 변화 확인 |
| `POST` | `/api/trade/order/preview` | 코인 시장가 매수/매도의 예상 수량·금액 확인 |
| `POST` | `/api/alternatives/orders/preview` | 선물·옵션·금속·부동산 모의 주문의 증거금/현금 영향 확인 |
| `GET` | `/api/member/trading-activity?days=30` | 주식·코인·대체자산 체결을 합산한 기간별 거래 횟수·회전금액 통계 |
| `GET` | `/api/member/portfolio-analysis` | 자산배분, HHI 분산도, 레버리지 노출, 손익·업종 집중도 분석 |

### PostgreSQL 퀀트 API

로컬 `local-db` 프로필은 PostgreSQL도 함께 실행하며, 첫 기동 시 `database/quant-postgres.sql`이 월별 시계열 분석용 스키마와 명시적인 샘플 OHLCV를 준비합니다. 운영 환경에서는 `QUANT_DATABASE_URL`로 별도의 PostgreSQL을 지정합니다.

| Method | Path | 설명 |
|---|---|---|
| `GET` | `/api/quant/overview` | 적재 건수·사용 가능 심볼 |
| `GET` | `/api/quant/market-data?symbol=005930` | 파티션된 OHLCV 조회 |
| `GET` | `/api/quant/signals?symbol=005930&fast=20&slow=50` | 윈도우 함수 기반 MA 시그널 |
| `POST` | `/api/quant/backtests` | 전략·체결 로그·성과 지표 저장 |
| `GET` | `/api/quant/results` | 저장된 전략과 거래 로그 |

웹 화면은 임의 SQL을 실행하지 않고, 파라미터 바인딩된 읽기 전용 SQL 템플릿만 보여주고 실행합니다. 이는 데이터 조회 편의성과 운영 DB 보호를 함께 고려한 방식입니다.

### PostgreSQL Quant on AWS VM

퀀트 기능은 기존 회원·모의 주문 MariaDB와 분리된 PostgreSQL 16을 사용합니다. 웹 브라우저는 PostgreSQL에 직접 접근하지 않으며, Nginx → Flask API → PostgreSQL 순서로 내부 Docker 네트워크에서만 통신합니다.

| 계층 | 기술 | 역할 |
|---|---|---|
| Web | Nginx, Vanilla JS | `/quant.html` 제공 및 `/api/quant/*` 프록시 |
| API | Python 3.11, Flask, SQLAlchemy, psycopg | 백테스트·팩터 회귀·파라미터 바인딩 |
| Quant DB | PostgreSQL 16 Alpine | OHLCV 파티션, BRIN, JSONB, 체결·성과·팩터 데이터 |
| Runtime | Docker Compose v2, EC2/VM | 내부 네트워크, 볼륨, 헬스체크, 재기동 |

#### VM 기동

AWS EC2 또는 다른 Linux VM에는 Docker Engine과 Docker Compose v2를 설치한 뒤, 저장소에서 다음을 실행합니다.

```bash
cp .env.example .env
docker compose --profile local-db up -d --build
docker compose ps
```

`postgres` 컨테이너는 `internal` Docker 네트워크에만 연결되며 호스트 포트 `5432`를 공개하지 않습니다. Flask 컨테이너는 기본적으로 다음 연결 문자열을 사용합니다.

```text
postgresql+psycopg://<QUANT_DB_USER>:<QUANT_DB_PASSWORD>@postgres:5432/<QUANT_DB_NAME>
```

운영 VM의 `.env`에는 최소한 아래 값을 실제 비밀번호로 변경합니다. `QUANT_DATABASE_URL`을 설정하면 외부 관리형 PostgreSQL(RDS 등)도 사용할 수 있습니다.

```text
QUANT_DB_NAME=quant_research
QUANT_DB_USER=quant
QUANT_DB_PASSWORD=<long-random-password>
SECRET_KEY=<long-random-secret>
```

#### 운영 확인·백업

```bash
# PostgreSQL 준비 상태
docker compose --profile local-db exec postgres pg_isready -U quant -d quant_research

# 퀀트 스키마 확인
docker compose --profile local-db exec postgres psql -U quant -d quant_research -c '\dt'

# 백업: VM의 backups 디렉터리를 먼저 만들고 실행
mkdir -p backups
docker compose --profile local-db exec -T postgres pg_dump -U quant -d quant_research > backups/quant_research.sql

# 복구: 대상 DB가 비어 있는지 확인한 뒤 실행
docker compose --profile local-db exec -T postgres psql -U quant -d quant_research < backups/quant_research.sql
```

AWS 보안 그룹에는 PostgreSQL `5432` 인바운드 규칙을 추가하지 않습니다. 운영자 접속이 필요하면 VM의 Docker 명령, SSM Session Manager 또는 VPN/사설망을 사용합니다. Docker 볼륨 `postgres-quant-data`는 `docker compose down`으로 유지되지만 `down -v`에서는 삭제되므로, 실행 전 백업 여부를 확인하세요.

### 세션 API

| 영역 | 대표 경로 | 인증 |
|---|---|---|
| 회원 | `POST /api/member/login`, `POST /api/member/register`, `POST /api/member/logout`, `GET /api/member/me` | 일부 불필요 |
| 국내 주식 시세 | `GET /api/stocks/list`, `/quote?symbol=`, `/chart?symbol=`, `/market` | 불필요 |
| 주식 모의 주문 | `GET /api/stocks/account`, `/positions`, `POST /api/stocks/orders/buy`, `/sell` | 로그인 필요 |
| 코인 | `GET /api/crypto/rankings`, `/market-list`, `/{code}`, `/{code}/domestic-prices` | 불필요 |
| 코인 모의 주문 | `GET /api/trade/hold`, `POST /api/trade/order/buy`, `/sell` | 로그인 필요 |
| 대체자산 | `GET /api/alternatives/markets`, `/positions`, `POST /api/alternatives/orders` | 로그인 필요 |
| AI | `POST /api/ai/analyze`, `POST /api/ai-sheet/crawl` | 기능별 설정 필요 |

### 외부 연동 Open API

`/openapi/v1/*`는 이 플랫폼의 가상 주식계좌를 외부 모듈에서 조회·주문할 때 사용합니다. 웹에서 발급한 API 키를 `Authorization: Bearer <api_key>` 헤더에 넣습니다.

| Method | Path | 설명 |
|---|---|---|
| `GET` | `/openapi/v1/stocks` | 지원 종목 목록 |
| `GET` | `/openapi/v1/quote/{symbol}` | 종목 시세 |
| `GET` | `/openapi/v1/account` | 가상 계좌 요약 |
| `GET` | `/openapi/v1/positions` | 보유 포지션 |
| `GET` | `/openapi/v1/orders` | 주문 이력 |
| `POST` | `/openapi/v1/orders` | 가상 주식 주문 |

API 키당 분당 60회 제한이 적용됩니다. 키 원문은 발급 시 한 번만 표시되고 서버에는 SHA-256 해시만 저장됩니다.

## 증권사·Alpaca 연결 테스트

테스트 화면은 서버에서만 키를 읽습니다. 브라우저 응답·로그에 API Key, Secret, 접근 토큰, 계좌번호를 포함하지 않습니다.

| 화면 | 경로 | 호출 범위 |
|---|---|---|
| 증권사 시세 테스트 | `/broker-api-test.html` | KIS Testbed 현재가, KB증권 토큰 인증·시세 설정 점검 |
| Alpaca Test | `/alpaca-test.html` | Alpaca Paper `GET /v2/account` 상태 조회 |

백엔드 엔드포인트는 다음과 같습니다.

```text
GET /api/broker-test/kis/quote?symbol=005930
GET /api/broker-test/kb/quote?symbol=005930
GET /api/alpaca-test/paper/account
```

KIS Testbed에는 호출 제한이 있으므로 토큰과 짧은 시세 결과를 서버에서 캐시합니다. KB증권 키가 인증 단계에서 거부되면 검증되지 않은 시세 URI를 추측해 호출하지 않습니다. Alpaca Test는 Paper 환경만 사용하고 주문·잔고·계좌번호를 반환하지 않습니다.

## 외부 플랫폼·증권사·거래소 API 사전 가입 및 이용 절차

이 저장소가 호출하는 모든 외부 API를 **가입·키 발급이 필요한 것**과 **가입 없이 바로 쓰는 공개 API**로 나눠 정리합니다. 실제 신청 화면·약관·요건은 각 서비스가 수시로 바꿀 수 있으므로, 신청 직전에는 항상 공식 사이트에서 최신 절차를 다시 확인하세요.

### 한눈에 보기

| 플랫폼 | 가입 필요 | API Key 발급 | 이 저장소의 저장 위치 | 이 프로젝트에서의 사용 범위 |
|---|---|---|---|---|
| 한국투자증권(KIS) | 계좌 개설 + 모의투자 별도 신청 | 필요 (모의 App Key·Secret) | `kis.key` 또는 `KIS_*` 환경변수 | 모의(Testbed) 시세·잔고 조회, 보호된 모의 주문 흐름 테스트 |
| KB증권 | 계좌 개설(M-able) + Open API 신청 | 필요 (App Key·Secret) | `kb.key` 또는 `KB_APP_KEY`/`KB_APP_SECRET` | 토큰 인증, 시세·호가·차트 읽기 전용 조회 |
| Alpaca Markets | 이메일 가입 | 필요 (Paper Key·Secret) | `al.key` 또는 `ALPACA_API_KEY`/`ALPACA_SECRET_KEY` | Paper 계정 조회, 보호된 Paper 주문 흐름 테스트 |
| Binance | 공개 시세는 불필요 | 공개 시세는 불필요(인증 API·Testnet만 필요) | 해당 없음(미구현) | 공개 24hr 시세·호가만 조회 |
| Korbit | 공개 시세는 불필요 | 공개 시세는 불필요(개인 자산 API만 필요) | 해당 없음(미구현) | 공개 현재가·호가 조회, 국내가 비교 |
| 업비트·빗썸·코인원 | 불필요 | 불필요 | 해당 없음 | 코인 현재가·국내 거래소 가격 비교(공개 API) |
| CoinMarketCap | 가입 필요 | 필요 (`CMC_API_KEY`) | `.env`의 `CMC_API_KEY` | 코인 랭킹 정기 동기화(매시 정각), 미설정 시 건너뜀 |
| Anthropic (Claude API) | 가입 필요 | 필요 (`ANTHROPIC_API_KEY`) | `.env`의 `ANTHROPIC_API_KEY` | AI Sheet/투자 분석 기능, 미설정 시 경고만 표시하고 비활성 |
| TradingView | 무료 계정 가입 | 불필요 | 해당 없음 | Pine Script 실전연습(웹 위젯·Pine Editor) |
| 이 플랫폼 자체 Open API | 이 웹앱 회원가입 | 필요 (웹에서 발급) | 발급 시 1회 표시, 서버는 SHA-256 해시만 저장 | 가상 주식계좌 조회·주문 — 절차는 위 "외부 연동 Open API" 참고 |

### 1. 한국투자증권(KIS) Open API

1. 한국투자증권 계좌가 없다면 공식 앱/웹에서 비대면 계좌개설을 먼저 진행합니다. ([한국투자증권 로그인·가입](https://securities.koreainvestment.com/main/member/login/login.jsp))
2. [모의투자 안내](https://www.truefriend.com/main/research/virtual/_static/TF07da010000.jsp)에서 한국투자증권 고객 ID로 로그인해 **모의투자 참가 신청**을 하고, 완료 후 **나의계좌 → 계좌정보**에서 모의투자 전용 계좌번호(`CANO-상품코드`)를 확인합니다.
3. [KIS Developers](https://apiportal.koreainvestment.com)에 로그인해 **API 신청**에서 방금 만든 모의투자 계좌를 선택해 서비스를 신청합니다. 신청현황에서 모의투자용 **App Key·App Secret**이 발급됩니다. 실전 계좌 행의 키는 이 프로젝트에서 사용하지 않습니다.
4. 발급받은 값을 저장소 루트의 `kis.key`(`app_key=`, `secret=`, `account=CANO-상품코드`) 또는 `.env`의 `KIS_MODE=mock`/`KIS_APP_KEY`/`KIS_APP_SECRET`/`KIS_ACCOUNT_NO`/`KIS_ACCOUNT_PRODUCT_CODE`에 저장합니다(환경변수가 설정되면 우선 적용). 계좌(`account`)는 잔고 조회에만 필요하고 시세 조회에는 필요 없습니다.
5. 모의(Testbed) 도메인은 `https://openapivts.koreainvestment.com:29443`이며, 실전 도메인(`https://openapi.koreainvestment.com:9443`)은 사용하지 않습니다. 모의투자 토큰 발급은 **1분당 1회** 제한이 있으므로 짧은 간격으로 재시도하지 마세요.
6. 자세한 절차·스크린샷은 [`/learning/kis-developers.html`](frontend/learning/kis-developers.html)과 [`/learning/kis-module-guide.html`](frontend/learning/kis-module-guide.html)에, VS Code에서 자연어로 쓰는 공식 MCP 연동은 아래 "KIS MCP" 절에 정리되어 있습니다.

### 2. KB증권 Open API

1. KB M-able 앱을 설치하고 비대면 계좌개설을 진행합니다(본인 명의 휴대폰·신분증 필요).
2. 앱에서 KB증권 ID를 등록한 뒤, PC 웹사이트에서 **클라우드 인증서 로그인** 등 본인 인증 수단으로 로그인합니다.
3. 로그인 후 **Open API → Open API 신청/조회** 메뉴에서 신청할 계좌를 선택하고 비밀번호를 입력해 조회한 뒤, 표시되는 API 그룹·이용기간·약관에 동의해 신청을 제출합니다.
4. 신청현황에서 **App Key·App Secret**을 확인해 저장소 루트의 `kb.key`(`AppKey=`, `Secret=`) 또는 `.env`의 `KB_APP_KEY`/`KB_APP_SECRET`에 저장합니다.
5. **클라우드 인증서 발급, ID 등록, 계좌 이용 등록은 심사 상황에 따라 개인별로 수시간이 걸릴 수 있으므로** 테스트 직전이 아니라 미리 신청해 두세요.
6. 개발 문서·API 명세는 [KB증권 Open API 포털](https://openapi.kbsec.com/intro)에서, 이 프로젝트의 실제 호출 대상은 `https://developer.kbsec.com:32484`(운영 환경)입니다. 주문·잔고 조회는 이 학습 도구에 포함되어 있지 않고 토큰 인증과 시세·호가·차트 읽기 전용 조회만 제공합니다. 절차 전체는 [`/learning/kb-securities.html`](frontend/learning/kb-securities.html) 참고.

### 3. Alpaca Markets (Paper Trading)

1. [Alpaca 가입/대시보드](https://app.alpaca.markets/signup)에서 이메일로 계정을 만들고 요구되는 이메일 확인 절차를 완료합니다.
2. 대시보드 좌측 상단 계정 선택기에서 **Paper Trading** 계정을 선택하거나 새로 생성합니다.
3. **Home** 대시보드의 **API Keys** 패널에서 Paper 계정용 Key·Secret을 생성합니다. Secret은 최초 표시 이후 다시 확인되지 않을 수 있으므로 즉시 저장합니다.
4. 발급받은 값을 저장소 루트의 `al.key`(`Key=`, `Secret=`) 또는 `.env`의 `ALPACA_API_KEY`/`ALPACA_SECRET_KEY`/`ALPACA_PAPER=true`에 저장합니다. Paper 엔드포인트는 `https://paper-api.alpaca.markets`/`https://data.alpaca.markets`이며, Live는 키와 도메인이 모두 다르므로 이 프로젝트에서는 전환하지 않습니다.
5. 거주 국가에 따라 Live 계정 승인 여부·상품·세금 요건이 달라질 수 있지만, Paper 전용 계정은 별도 심사 없이 만들 수 있습니다.
6. 자세한 SDK(`alpaca-py`)·Trading CLI 사용법은 아래 "Alpaca Paper Trading" 절과 [`/learning/alpaca-api.html`](frontend/learning/alpaca-api.html) 참고.

### 4. Binance Spot

- **공개 시세·호가(`/binance-api-test.html`, `crypto_exchange_test.py`)는 가입·API Key 없이 바로 호출됩니다.** `GET https://api.binance.com/api/v3/ticker/24hr`, `.../depth` 등은 Key 없이 공개 데이터를 반환합니다.
- 인증이 필요한 계정·주문 API를 직접 붙이려면 [Binance](https://www.binance.com) 가입 후 API Key·Secret을 발급받아야 하며, 서명(HMAC SHA-256)과 IP 화이트리스트 설정이 필요합니다. 이 프로젝트는 해당 기능을 구현하지 않았습니다.
- 실습·검증용으로는 운영 키 대신 [Binance Spot Testnet](https://testnet.binance.vision)에서 별도 계정과 키를 발급받아 `https://testnet.binance.vision`을 사용하세요. 출금 권한은 어떤 경우에도 API 키에 부여하지 않는 것을 원칙으로 합니다.
- 절차·엔드포인트는 [`/learning/binance-api.html`](frontend/learning/binance-api.html) 참고.

### 5. Korbit(코빗)

- **공개 시세·호가(`/korbit-api-test.html`)는 가입·API Key 없이 바로 호출됩니다.** `GET https://api.korbit.co.kr/v2/tickers`, `.../orderbook` 등이 여기 해당합니다. `crypto.py`의 국내 거래소 가격 비교도 같은 공개 엔드포인트(`v1/ticker/detailed`)를 사용합니다.
- 개인 자산 조회·주문·입출금 API를 사용하려면 [Korbit](https://www.korbit.co.kr) 가입과 본인 인증 후 API Key를 발급받아야 하며, 키 발급 시 **자산 조회 / 주문 조회 / 주문 신청 / 입출금 조회·신청** 권한을 개별적으로 선택합니다. 이 프로젝트는 해당 기능을 구현하지 않았으며, 구현하더라도 출금 권한은 부여하지 않는 것을 권장합니다.
- 공식 API 문서: [docs.korbit.co.kr](https://docs.korbit.co.kr/). 절차는 [`/learning/korbit-api.html`](frontend/learning/korbit-api.html) 참고.

### 6. 업비트·빗썸·코인원 (국내 코인 시세 비교)

코인 상세 화면의 "국내 거래소 가격 비교"는 업비트(`api.upbit.com`), 빗썸(`api.bithumb.com`), 코인원(`api.coinone.co.kr`)의 **공개 시세 API**만 호출합니다. 세 거래소 모두 가입·로그인·API Key 없이 바로 조회할 수 있으며, 이 프로젝트는 매매를 하지 않으므로 계정 개설이 필요하지 않습니다.

### 7. CoinMarketCap (코인 랭킹 동기화)

1. [CoinMarketCap API](https://coinmarketcap.com/api/) 사이트에서 가입한 뒤 무료(Basic) 플랜 API Key를 발급받습니다.
2. 발급받은 값을 `.env`의 `CMC_API_KEY`에 저장합니다. `scheduler.py`가 매시 정각(Asia/Seoul) `https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest`를 호출해 코인 랭킹을 동기화합니다.
3. 키를 설정하지 않아도 앱은 정상 동작하며, 동기화 작업만 로그 경고와 함께 건너뜁니다.

### 8. Anthropic Claude API (AI Sheet · 투자 분석)

1. [console.anthropic.com](https://console.anthropic.com)에서 가입하고 결제 수단을 등록한 뒤 API Key를 발급받습니다.
2. 발급받은 값을 `.env`의 `ANTHROPIC_API_KEY`에 저장합니다. `ai.py`가 `https://api.anthropic.com/v1/messages`를 호출해 AI Sheet 크롤링 결과 분석·투자 분석 기능을 제공합니다.
3. 키를 설정하지 않으면 AI 분석 기능은 화면에 "ANTHROPIC_API_KEY가 설정되지 않았습니다" 안내만 표시하고 비활성 상태로 유지됩니다.

### 9. TradingView (Pine Script 실전연습)

[TradingView 가입·로그인](https://www.tradingview.com/accounts/signin/)에서 무료 계정을 만들면 차트 열람·Pine Editor 사용이 가능합니다. API Key 발급 절차는 없으며, 이 프로젝트는 TradingView의 공식 차트/Pine Script 학습 자료로 연결만 합니다. Pine Script를 저장하거나 전략 백테스트(Strategy Report)를 실행하려면 로그인이 필요합니다. 자세한 내용은 [`/learning/tradingview-pine.html`](frontend/learning/tradingview-pine.html) 참고.

### 10. 이 플랫폼 자체 Open API

위 외부 서비스와 달리, 이 웹앱이 자체 발급하는 `/openapi/v1/*` 키는 이 사이트에 회원가입 후 **회원 메뉴에서 직접 발급**합니다. 발급·인증·호출 제한 절차는 위 "외부 연동 Open API" 절을 참고하세요.

## AWS SSM Parameter Store 연동 트랙 (선택)

`kis.key`/`kb.key`/`al.key`처럼 브로커 키를 파일로 저장소 루트나 EC2 디스크에 두는 대신, **AWS Systems Manager Parameter Store**(SecureString)에서 키를 읽어오는 **완전히 별도의 백엔드 모듈·테스트 웹앱**입니다. 기존 `broker_test.py`, `broker_test_api.py`, `alpaca_test.py`, `alpaca_test_api.py`, `kb_token_test.py`와 `/broker-api-test.html`, `/alpaca-test.html`은 이 트랙과 무관하게 **지금까지의 키 파일 방식 그대로** 동작합니다 — 두 트랙은 서로 다른 URL·다른 Python 모듈을 사용하므로 한쪽을 설정하지 않아도 다른 쪽에 영향이 없습니다.

### 구성

| 구분 | 기존 키 파일 트랙 | 신규 AWS SSM 트랙 |
|---|---|---|
| 자격 증명 소스 | `kis.key`/`kb.key`/`al.key` 또는 `KIS_*`/`KB_*`/`ALPACA_*` 환경변수 | AWS SSM Parameter Store(SecureString) |
| 공용 헬퍼 | `broker_test.py`의 `_read_key_file`/`_credentials` | `aws_secret_store.py`의 `get_parameter`/`get_credentials` |
| KIS·KB 로직 | `broker_test.py` → `broker_test_api.py` (`/api/broker-test/*`) | `broker_test_aws.py` → `broker_test_aws_api.py` (`/api/aws-broker-test/*`) |
| Alpaca 로직 | `alpaca_test.py` → `alpaca_test_api.py` (`/api/alpaca-test/*`) | `alpaca_test_aws.py` → `alpaca_test_aws_api.py` (`/api/aws-alpaca-test/*`) |
| 테스트 웹앱 | `/broker-api-test.html`, `/alpaca-test.html` | `/aws-broker-api-test.html`, `/aws-alpaca-test.html` |

AWS SSM 트랙은 조회 범위를 의도적으로 좁혀 운영합니다. 먼저 SecureString 원문을 복호화하지 않는 준비 상태 점검(리전·IAM·파라미터 존재/타입)을 실행하고, KIS는 현재가·잔고, KB는 토큰 발급 점검·현재가, Alpaca는 계정·포지션·미국 시장 시계·종목 거래 가능 여부를 읽기 전용으로 확인합니다. 주문·정정·취소 API는 이 트랙에서 호출하지 않습니다.

### 1. IAM 정책 준비

EC2에 인스턴스 프로파일(권장) 또는 최소 권한 IAM 사용자를 만들고, 아래 파라미터 경로에만 `ssm:GetParameter`를 허용합니다. SecureString은 KMS 복호화 권한(`kms:Decrypt`)도 함께 필요합니다(기본 AWS 관리형 키 `alias/aws/ssm`를 쓰면 별도 키 생성 없이도 충분합니다).

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["ssm:GetParameter"],
      "Resource": "arn:aws:ssm:<region>:<account-id>:parameter/stock-coin-trade/*"
    },
    {
      "Effect": "Allow",
      "Action": ["kms:Decrypt"],
      "Resource": "arn:aws:kms:<region>:<account-id>:key/*",
      "Condition": { "StringEquals": { "kms:ViaService": "ssm.<region>.amazonaws.com" } }
    }
  ]
}
```

### 2. 파라미터 생성

이름 규칙은 `/stock-coin-trade/<서비스>/<항목>`입니다(접두사는 `.env`의 `AWS_SSM_PARAMETER_PREFIX`로 바꿀 수 있습니다). AWS CLI로 한 번만 생성하면 되고, 값은 이 저장소·터미널 기록에 남기지 않습니다.

| 파라미터 | 값 |
|---|---|
| `/stock-coin-trade/kis/app_key` | KIS 모의투자 App Key |
| `/stock-coin-trade/kis/secret` | KIS 모의투자 App Secret |
| `/stock-coin-trade/kis/account` | 모의투자 계좌 `CANO-상품코드` (잔고 조회 시에만 필요) |
| `/stock-coin-trade/kb/app_key` | KB증권 App Key |
| `/stock-coin-trade/kb/secret` | KB증권 App Secret |
| `/stock-coin-trade/alpaca/api_key` | Alpaca Paper API Key |
| `/stock-coin-trade/alpaca/secret_key` | Alpaca Paper API Secret |

```bash
aws ssm put-parameter --name "/stock-coin-trade/kis/app_key" --type SecureString --value "<모의투자 App Key>"
aws ssm put-parameter --name "/stock-coin-trade/kis/secret"   --type SecureString --value "<모의투자 App Secret>"
aws ssm put-parameter --name "/stock-coin-trade/kis/account"  --type SecureString --value "12345678-01"
aws ssm put-parameter --name "/stock-coin-trade/kb/app_key"   --type SecureString --value "<KB App Key>"
aws ssm put-parameter --name "/stock-coin-trade/kb/secret"    --type SecureString --value "<KB App Secret>"
aws ssm put-parameter --name "/stock-coin-trade/alpaca/api_key"    --type SecureString --value "<Alpaca Paper Key>"
aws ssm put-parameter --name "/stock-coin-trade/alpaca/secret_key" --type SecureString --value "<Alpaca Paper Secret>"
```

### 3. 앱에서 접근하는 방법

- **EC2 배포**: 위 IAM 정책이 붙은 인스턴스 프로파일만 있으면 됩니다. `docker-compose.yml`의 `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_SESSION_TOKEN`은 비워 두세요 — `boto3`가 EC2 메타데이터에서 자동으로 자격 증명을 가져옵니다.
- **로컬 개발**: EC2가 아니므로 `.env`에 `AWS_REGION`과 함께 임시 자격 증명(`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_SESSION_TOKEN`, 예: `aws sso login` 또는 `aws configure`로 발급)을 채운 뒤 `docker compose up -d --build`로 재기동합니다.
- 두 경우 모두 `boto3`의 표준 자격 증명 탐색 순서를 그대로 사용하므로, 이 프로젝트 코드에는 AWS 액세스 키를 하드코딩하지 않습니다.

### 4. 접속·동작 확인

| 주소 | 설명 |
|---|---|
| `/aws-broker-api-test.html` | KIS 현재가·잔고, KB 토큰 발급·현재가 (AWS SSM) |
| `/aws-alpaca-test.html` | Alpaca Paper 계정·포지션·시장 시계·종목 정보 (AWS SSM) |
| `/learning/aws-ssm-key-management.html` | Parameter Store·KMS·IAM 최소권한·테스트 흐름 가이드 |

파라미터가 없거나 IAM 권한이 부족하면 화면에 "SSM Parameter Store에 …이(가) 없습니다" 같은 안전한 오류 메시지만 표시되고, AWS 자격 증명이나 파라미터 값은 응답·로그에 노출되지 않습니다.

## KIS MCP — VS Code에서 자연어로 KIS API 사용하기

`/broker-api-test.html`의 증권사 연결 테스트와는 별개로, 한국투자증권은 AI 도구로 **MCP(Model Context Protocol)** 를 제공합니다. MCP는 생성형 AI가 외부 도구와 데이터에 표준 방식으로 연결되도록 하는 규약입니다. 이 프로젝트는 MCP 서버를 자체 구현하거나 `broker_test.py`를 MCP로 감싼 것이 아니라, 아래의 한투 공식 MCP를 별도로 사용합니다.

| 구분 | 용도 | 공식 안내 |
|---|---|---|
| KIS Code Assistant MCP (코딩도우미) | 자연어로 필요한 Open API를 찾고, 파라미터·응답 구조를 포함한 호출 예제 코드를 생성 | [코딩도우미 MCP](https://apiportal.koreainvestment.com/tools-sample) |
| KIS Trading MCP (트레이딩) | 국내·해외주식, 선물·옵션, 채권, ETF/ETN·인증 등의 Open API를 MCP 도구로 호출 | [트레이딩 MCP](https://apiportal.koreainvestment.com/tools-trading) |

두 도구의 차이와 API 신청 → MCP 클라이언트 연결 → 보안인증키 발급 → 샘플 실행 절차는 [한국투자증권 MCP 소개](https://apiportal.koreainvestment.com/tools-mcp)에서 최신 내용을 확인하세요. 코딩도우미는 API 탐색·예제 생성용이고, 트레이딩 MCP는 API를 실제 호출할 수 있으므로 이 저장소에서는 **모의투자 키만** 연결하는 것을 기본으로 합니다.

아래 설정은 한투 공식 저장소 [koreainvestment/open-trading-api](https://github.com/koreainvestment/open-trading-api)의 `MCP/Kis Trading MCP` 서버를 VS Code(GitHub Copilot Chat 에이전트 모드)·Claude Desktop·Cursor 등에 연결하는 예시입니다.

### 설치

```bash
# 1. 공식 MCP 서버 저장소를 로컬에 clone (이 repo의 git 이력에는 포함되지 않음)
mkdir -p mcp
git clone --depth 1 https://github.com/koreainvestment/open-trading-api.git mcp/open-trading-api

# 2. 의존성 설치 (요구사항: Python 3.11+, uv)
cd "mcp/open-trading-api/MCP/Kis Trading MCP"
uv sync
```

### 모의투자 키 재사용

이미 갖고 있는 `kis.key`(모의투자 App Key·Secret)를 그대로 재사용합니다. 실전 키는 설정하지 않아 실전 거래 도구는 비활성 상태로 유지됩니다.

```bash
# mcp/kis-trade-mcp.env — gitignore 처리됨(/mcp/), Git에 절대 커밋하지 않습니다
KIS_PAPER_APP_KEY=<kis.key의 App-KEY 값>
KIS_PAPER_APP_SECRET=<kis.key의 Secret 값>
```

### VS Code 연결 (`.vscode/mcp.json`)

`.vscode/`는 이미 `.gitignore`에 포함되어 있어 별도 조치 없이 커밋되지 않습니다. 모의투자 계좌번호는 이 저장소 어디에도 저장하지 않고, VS Code가 서버를 처음 실행할 때 안전한 입력창으로 물어보도록 `inputs`를 사용합니다.

```json
{
  "inputs": [
    { "type": "promptString", "id": "kis-paper-account", "description": "KIS 모의투자 계좌번호 앞 8자리" },
    { "type": "promptString", "id": "kis-hts-id", "description": "한국투자증권 HTS ID (선택)" }
  ],
  "servers": {
    "kis-trade-mcp": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "${workspaceFolder}/mcp/open-trading-api/MCP/Kis Trading MCP", "run", "python", "server.py"],
      "envFile": "${workspaceFolder}/mcp/kis-trade-mcp.env",
      "env": {
        "ENV": "live",
        "MCP_TYPE": "stdio",
        "KIS_PAPER_STOCK": "${input:kis-paper-account}",
        "KIS_PROD_TYPE": "01",
        "KIS_HTS_ID": "${input:kis-hts-id}"
      }
    }
  }
}
```

`ENV=live`는 실전 거래를 뜻하지 않습니다 — MCP 서버가 로드할 전송 설정 파일(`.env.live`) 이름일 뿐이며, 실전·모의 구분은 `KIS_APP_KEY`(실전, 비워둠) 대 `KIS_PAPER_APP_KEY`(모의, 설정함)로 결정됩니다.

### 사용

VS Code에서 이 워크스페이스를 열고 Copilot Chat을 에이전트 모드로 전환하면 계좌번호 입력 프롬프트가 표시됩니다. 이후 채팅에서 자연어로 질문합니다.

- "삼성전자 현재가 조회해줘"
- "모의투자 계좌 잔고 보여줘"

전체 도구 목록과 Docker+SSE 실행 방식 등 상세 내용은 [공식 MCP README](https://github.com/koreainvestment/open-trading-api/blob/main/MCP/README.MD)를 참조하세요. 프론트엔드 학습 페이지(`/learning/kis-developers.html`)에도 동일한 안내가 있습니다.

> ⚠️ 실전 거래용 `KIS_APP_KEY`/`KIS_APP_SECRET`는 설정하지 마세요. 설정하면 MCP 도구가 실제 자금으로 주문을 실행할 수 있습니다.

## Alpaca Paper Trading

`실전연습 → Alpaca API`에는 계정 생성, Paper API Key 발급 위치, `alpaca-py`, Trading CLI, WebSocket 및 주의사항을 정리했습니다.

- Paper와 Live는 키와 도메인이 다릅니다.
- Paper 키는 `al.key` 또는 `ALPACA_API_KEY`/`ALPACA_SECRET_KEY` 환경변수로만 관리합니다.
- Trading CLI는 Alpha Preview 상태이므로 명령과 출력 형식이 바뀔 수 있습니다.
- 이 프로젝트에서 “Alpaca”는 금융 API 플랫폼인 **Alpaca Markets**를 의미합니다. Stanford Alpaca, Alpacon/AlpacaX와는 별도 프로젝트입니다.

공식 자료: [Paper Trading](https://docs.alpaca.markets/us/docs/paper-trading) · [Trading CLI](https://docs.alpaca.markets/us/docs/alpacas-cli) · [alpaca-py](https://alpaca.markets/sdks/python/trading.html)

## 환경 변수

전체 예시는 [.env.example](.env.example)를 참조합니다.

| 변수 | 용도 |
|---|---|
| `MARIADB_DATABASE`, `MARIADB_USER`, `MARIADB_PASSWORD` | 로컬 MariaDB 설정 |
| `SECRET_KEY` | Flask 세션 서명 키 |
| `CMC_API_KEY`, `ANTHROPIC_API_KEY` | 선택적 코인 데이터·AI 기능 |
| `KIS_*`, `KB_*` | 증권사 테스트 환경 변수 대안 |
| `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` | Alpaca Paper API 키 대안 |

`.env`, `*.key`, 토큰, 계좌번호, 비밀번호, 실제 주문 응답을 Git·문서·화면 캡처·브라우저 코드에 넣지 마세요.

## 저장소 구조

```text
.
├── frontend/                         # 정적 웹 애플리케이션
│   ├── index.html                     # 대시보드
│   ├── trade/                         # 코인·주식·대체자산 모의거래
│   ├── learning/                      # TradingView, KB, KIS, Alpaca 실전연습
│   ├── alpaca-test.html               # Alpaca Paper 연결 테스트
│   ├── broker-api-test.html           # KIS·KB 연결 테스트
│   ├── member/                        # 로그인·회원가입·플랫폼 API 키
│   ├── js/common.js                   # 모든 페이지 공통 offcanvas 메뉴
│   └── images/                        # 학습용 이미지·안내도
├── python-stock-backend/              # Flask API
│   ├── app.py                         # 앱 진입점과 Blueprint 등록
│   ├── members.py / stocks.py          # 회원·주식 모의거래
│   ├── crypto.py / alternatives.py     # 코인·대체자산
│   ├── openapi.py / api_keys.py        # 외부 연동 API와 키 관리
│   ├── broker_test*.py                 # KIS·KB 읽기 전용 테스트
│   ├── alpaca_test*.py                 # Alpaca Paper 읽기 전용 테스트
│   └── stock_market.py                 # 국내 주식 시세·차트
├── database/db.sql                    # MariaDB 초기 스키마·예제 데이터
├── docker/                            # Frontend·Backend 이미지와 Nginx 설정
├── docker-compose.yml                 # 로컬 실행 구성
├── scripts/ec2/deploy.sh              # 배포 전 문법 검사·Compose 재기동
├── .env.example                       # 공유 가능한 환경 변수 예시
└── mcp/                                # (선택, git 미추적) 한투 공식 KIS MCP 서버 clone + 로컬 키
```

## 개발·검증

### Python 문법 검사

```bash
python3 -m py_compile python-stock-backend/*.py
```

### Compose 재빌드와 상태 확인

```bash
docker compose up -d --build
docker compose ps
curl http://localhost:3000/api/alpaca-test/paper/account
```

`scripts/ec2/deploy.sh`는 Python 문법 검사 후 `docker compose up -d --build --remove-orphans`를 실행합니다.

## 운영 시 유의사항

- 이 저장소의 모의 주문과 증권사·Alpaca 테스트는 목적과 권한이 다릅니다. 외부 증권사 주문 연동은 별도 승인·리스크 한도·중복 주문 방지·감사 로그를 갖춘 작업으로 분리하세요.
- Paper Trading은 실제 시장 충격, 슬리피지, 호가 대기 순서 등을 완전히 재현하지 않습니다.
- 외부 API의 URL·인증 방식·호출 제한·이용 가능 국가와 상품은 변경될 수 있으므로 실제 연동 전 공식 문서를 확인하세요.
- 배포 환경에서는 개발용 기본 비밀번호를 사용하지 말고, 비밀 관리 도구 또는 안전한 환경 변수 주입 방식을 사용하세요.
- AI Sheet의 LEAN 백테스트 버튼은 `python-backend` 컨테이너에 호스트의 `/var/run/docker.sock`을 마운트해 QuantConnect LEAN 컨테이너를 직접 실행합니다(Docker-outside-of-Docker). 이는 해당 컨테이너에 사실상 호스트 Docker 데몬 전체에 대한 권한을 부여하는 것과 같으므로, 신뢰할 수 없는 사용자가 접근 가능한 배포 환경에서는 이 기능을 비활성화하거나 별도로 격리하는 것을 고려하세요. `docker/lean/`의 이미지를 미리 빌드해두어야 하며(`docker build -t stock-coin-trade-lean:latest docker/lean`), 없으면 최초 요청 시 자동으로 빌드합니다.
