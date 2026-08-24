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
- AI Sheet, 투자 분석 학습, Qdrant 기반 지식 검색 및 AI 분석 기능
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

## 기본 계정과 메뉴

기동 시 테스트 계정과 예제 투자자 데이터가 준비됩니다. 기본 테스트 계정은 다음과 같습니다.

```text
test1@test.com / 123456
test2@test.com / 123456
```

좌측 공통 offcanvas 메뉴는 모든 페이지가 같은 `frontend/js/common.js`를 사용합니다.

| 메뉴 | 주요 화면 |
|---|---|
| 거래 | 코인, 주식, 대체자산 |
| 자산관리 | 보유자산, 거래이력, 물타기 계산기 |
| 실전연습 | TradingView(Pine), KB증권, 한국투자증권 API, Alpaca API |
| 분석 · 도구 | AI Sheet, Open API, 증권사 시세 테스트, Alpaca Test |

## API 요약

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
