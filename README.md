# 한국 코인·주식 모의투자 Web App

Flask REST API + Vanilla JS 기반의 코인·주식 통합 모의투자 웹 애플리케이션입니다.  
업비트/빗썸/코인원/코빗 시세 비교와 KOSPI·KOSDAQ 주식 실습을 한 화면 흐름으로 제공합니다.

---

![alt text](./captures/image.png)

![alt text](./captures/image-01.png)

---

## 아키텍처

```
Browser
  │
  ▼
Nginx (Frontend · :3000)
  ├── /          → 정적 HTML/JS/CSS 서빙
  └── /api/      → Python Backend 프록시
        │
        └── Python Backend (Flask REST API · :8200 내부)
              └── MariaDB (external shared-net)
```

| 레이어 | 기술 | 역할 |
|---|---|---|
| **Frontend** | Vanilla JS + Tailwind CSS + Nginx | 정적 HTML 페이지, fetch API 호출 |
| **Python BE** | Flask · SQLAlchemy · bcrypt · yfinance · APScheduler | 회원 인증, 코인 매수/매도, 시세 API, 주식 시세/주문, AI 분석 스트리밍 |
| **DB** | MariaDB | 회원, 보유 코인, 업비트 마켓 |

---

## 1) 참고 앱 기능 분석 및 적용

6개 주요 주식·코인 거래 앱을 분석하여 아래 기능을 이 프로젝트에 반영하였습니다.

### 1-1. 분석 앱 및 주요 기능

| 앱 | 특징 | 핵심 참고 기능 |
|---|---|---|
| **토스증권** (KR) | 심플·초보 친화 UX, 모바일 퍼스트 | 관심종목(⭐) 등록·해제, 손익분기가(매입단가) 표시, 간편 %비율 주문 버튼 |
| **키움증권** (KR) | 전문 트레이더 특화, 최다 사용자 | 호가창(매도/매수 호가 레벨), 거래 내역(체결 내역), 상승·하락 TOP 종목 랭킹 |
| **삼성증권 POP** (KR) | 자산 분석 중심, 포트폴리오 뷰 | 포트폴리오 파이 차트(종목별 보유 비중 도넛 차트), 보유자산 시각화 |
| **Robinhood** (US) | 수수료 0원, 감성 피드 UX | 관심종목(Watchlist), 주문 성공/실패 즉시 피드백 메시지, 깔끔한 손익 표시 |
| **eToro** (EU) | 소셜 트레이딩, 멀티 마켓 | 시장 탭 필터(KOSPI / KOSDAQ / 관심종목), 종목명·코드 통합 검색 |
| **Trading 212** (EU) | 모의투자 연습 특화, 파이 포트폴리오 | 계좌 초기화(모의투자 전체 리셋), 종목 검색, 직관적 포지션 관리 |

### 1-2. 이 프로젝트에 적용된 기능

| 기능 | 참고 앱 | 위치 |
|---|---|---|
| ⭐ 관심종목 (Watchlist) | 토스증권·Robinhood | 주식 거래 / 코인 거래 마켓 리스트 |
| 📋 호가창 (Order Book) | 키움증권 | 주식 거래 · 매도/매수 호가 5단계 |
| 📈 상승/하락 TOP 3 (Market Movers) | 키움증권 | 주식 거래 페이지 상단 |
| 🗒️ 거래 내역 (Trade History) | 키움증권·Robinhood | 주식 거래 페이지 하단 |
| 🥧 포트폴리오 파이 차트 | 삼성증권 POP | 주식 계좌 현황 카드 내 도넛 차트 |
| 🔄 계좌 초기화 | Trading 212 | 주식 계좌 현황 카드 초기화 버튼 |
| 🔍 종목 검색 | eToro·Trading 212 | 주식 거래 차트 섹션 검색창 |
| 🗂️ 시장 탭 필터 | eToro | 전체 / KOSPI / KOSDAQ / ⭐관심 탭 |
| 💡 손익분기가 표시 | 토스증권 | 주식 현재 시세 카드 (매입단가 표시) |

---

## 2) 주요 기능

- Tailwind 기반 반응형 UI (Vanilla JS · 서버 렌더링 없음)
- 회원가입/로그인 (세션 + BCrypt) — REST API + 쿠키 세션
- KRW 마켓 기준 코인 모의 매수/매도
- 주식 거래 실습 화면 (Python 백엔드 연동)
- 보유자산(평가금액/수익률) 실시간 계산
- 업비트 WebSocket 실시간 시세
- 국내 4대 거래소 시세 비교 (`GET /api/crypto/{code}/domestic-prices`)
- Docker Compose 3-컨테이너 구성 (Nginx + Python + MariaDB)
- Kubernetes / Amazon EKS 배포 구성

---

## 3) 테스트 로그인 계정

앱 시작 시 아래 계정이 없으면 자동 생성됩니다.

- `test1@test.com / 123456`
- `test2@test.com / 123456`

---

## 4) 기술 스택

| 분류 | 기술 |
|---|---|
| **Frontend** | Vanilla JS, Tailwind CSS (CDN), Highcharts, ApexCharts, TradingView Widget |
| **Backend** | Python 3.11, Flask, SQLAlchemy, PyMySQL, bcrypt, APScheduler, yfinance |
| **DB** | MariaDB |
| **Infra** | Docker, Docker Compose, Nginx, Kubernetes, Amazon EKS |
| **Security** | BCrypt + 서명된 쿠키 세션(Flask session) |
| **External API** | Upbit REST/WebSocket, Bithumb REST, Coinone REST, Korbit REST, CoinMarketCap REST |

---

## 5) 저장소 구조

```
stock-coin-trade/
├── frontend/                    # Vanilla JS 정적 프론트엔드
│   ├── index.html               # 홈 (시가총액 Top 100)
│   ├── trade/
│   │   ├── order.html           # 코인 거래
│   │   ├── hold.html            # 보유자산
│   │   └── stock.html           # 주식 실습
│   ├── member/
│   │   ├── login.html
│   │   ├── register.html
│   │   └── api-keys.html        # Open API 키 발급/조회/폐기 (로그인 필요)
│   ├── openapi.html             # Open API 공개 명세 페이지
│   ├── js/
│   │   ├── config.js            # API base URL 설정
│   │   ├── common.js            # 헤더 렌더, 인증 유틸
│   │   ├── order.js             # 코인 거래 로직
│   │   ├── hold_crypto.js       # 보유자산 로직
│   │   ├── stock.js             # 주식 거래 로직
│   │   └── api-keys.js          # Open API 키 관리 로직
│   ├── css/style.css
│   ├── fonts/
│   └── img/
│
├── python-stock-backend/        # Flask REST API (회원/코인/주식/관리자/AI/Open API 전부)
│   ├── app.py                   # 앱 진입점, 블루프린트 등록, 주식 시세/RAG/뉴스 라우트
│   ├── members.py                # /api/member/* — 회원가입/로그인/세션
│   ├── crypto.py                 # /api/crypto/*, /api/trade/* — 시세/매수/매도
│   ├── admin.py                  # /api/admin/* — 관리자 전용 (k8s 현황 등)
│   ├── ai.py                     # /api/ai/analyze — Claude 스트리밍 분석
│   ├── stock_market.py            # 주식 시세/차트/지수 조회 + 캐시 (종목 마스터 데이터 포함)
│   ├── stock_trading.py           # 주식 매수/매도 실행 공용 로직 (웹 세션 + Open API 공유)
│   ├── stocks.py                  # /api/stocks/{account,positions,orders/*} — 세션 인증, DB 영속화
│   ├── api_keys.py                # /api/member/api-keys/* — Open API 키 발급/조회/폐기
│   ├── openapi.py                 # /openapi/v1/* — API Key(Bearer) 인증 외부 연동 API
│   ├── scheduler.py              # CoinMarketCap/Upbit 주기 동기화
│   ├── db.py / models.py         # SQLAlchemy 세션 / 테이블 매핑
│   ├── k8s_overview.py           # EKS 클러스터 현황 조회 로직
│   ├── qdrant_service.py         # Qdrant RAG 연동
│   └── requirements.txt
│
├── database/
│   └── db.sql                   # 초기 스키마
│
├── docker/
│   ├── frontend.Dockerfile
│   ├── python-backend.Dockerfile
│   └── nginx.conf
│
├── docker-compose.yml
├── k8s/                         # Kubernetes 매니페스트
└── scripts/                     # AWS / CI/CD 스크립트
```

---

## 6) REST API 엔드포인트

### 회원

| Method | Path | 설명 | 인증 |
|---|---|---|---|
| `GET`  | `/api/member/me`       | 현재 로그인 사용자 정보 | 불필요 |
| `POST` | `/api/member/login`    | 로그인 (세션 발급) | - |
| `POST` | `/api/member/register` | 회원가입 + 자동 로그인 | - |
| `POST` | `/api/member/logout`   | 로그아웃 | - |

### 코인

| Method | Path | 설명 |
|---|---|---|
| `GET` | `/api/crypto/rankings`                     | 시가총액 Top 100 (CoinMarketCap) |
| `GET` | `/api/crypto/market-list`                  | 업비트 KRW 마켓 목록 |
| `GET` | `/api/crypto/{code}`                       | 개별 코인 정보 + 보유 수량 |
| `GET` | `/api/crypto/{code}/domestic-prices`       | 국내 4대 거래소 시세 비교 |

### 거래 (로그인 필요)

| Method | Path | 설명 |
|---|---|---|
| `GET`  | `/api/trade/hold`       | 보유 코인 목록 + 자산 현황 |
| `POST` | `/api/trade/order/buy`  | 코인 매수 |
| `POST` | `/api/trade/order/sell` | 코인 매도 |

### 주식

| Method | Path | 설명 | 인증 |
|---|---|---|---|
| `GET`  | `/api/stocks/list`           | 종목 목록 | 불필요 |
| `GET`  | `/api/stocks/market`         | KOSPI/KOSDAQ 지수 | 불필요 |
| `GET`  | `/api/stocks/quote`          | 개별 종목 시세 | 불필요 |
| `GET`  | `/api/stocks/chart`          | 캔들 차트 데이터 | 불필요 |
| `GET`  | `/api/stocks/movers`         | 상승/하락 TOP 3 | 불필요 |
| `GET`  | `/api/stocks/account`        | 계좌 현황 (예수금은 `member.asset` 공유) | 로그인 필요 |
| `GET`  | `/api/stocks/positions`      | 보유 포지션 (`stock_position` 테이블) | 로그인 필요 |
| `GET`  | `/api/stocks/orders/history` | 거래 내역 (`stock_order` 테이블) | 로그인 필요 |
| `POST` | `/api/stocks/orders/buy`     | 주식 매수 | 로그인 필요 |
| `POST` | `/api/stocks/orders/sell`    | 주식 매도 | 로그인 필요 |
| `POST` | `/api/stocks/account/reset`  | 계좌 초기화 | 로그인 필요 |

> 주식 계좌는 코인 계좌와 동일하게 `member.asset`(예수금)을 공유합니다. 과거에는 서버 전역 메모리에만 존재해 로그인 없이도 거래가 가능했지만, 현재는 `stock_position`/`stock_order` 테이블에 회원별로 영속화되어 로그인이 필요합니다.

### Open API 키 관리 (로그인 필요)

| Method | Path | 설명 |
|---|---|---|
| `GET`    | `/api/member/api-keys`      | 내 API 키 목록 (마스킹) |
| `POST`   | `/api/member/api-keys`      | 새 API 키 발급 (원문은 응답에 1회만 포함) |
| `DELETE` | `/api/member/api-keys/{id}` | API 키 폐기 |

---

## 6-1) Open API (외부 연동)

외부 시스템(트레이딩 봇 등)이 API Key로 이 플랫폼의 가상 주식 계좌를 조회·매매할 수 있도록 `/openapi/v1/*` 를 제공합니다. 웹 UI에서 `/member/api-keys.html` 페이지로 키를 발급받고, 전체 명세는 `/openapi.html` 페이지(내비게이션의 "Open API" 메뉴)에서 확인할 수 있습니다.

- **인증**: `Authorization: Bearer <api_key>` 헤더. 키는 발급 시 원문이 1회만 노출되며 서버에는 SHA-256 해시만 저장됩니다.
- **요청 제한**: API 키당 분당 60회 (초과 시 `429 RATE_LIMITED`).
- **지갑 공유**: Open API로 실행한 매매도 웹에서 로그인해 매매한 것과 동일한 `member.asset`(예수금)·`stock_position`(보유종목)을 사용합니다.

| Method | Path | 설명 |
|---|---|---|
| `GET`  | `/openapi/v1/stocks`        | 매매 가능 종목 목록 |
| `GET`  | `/openapi/v1/quote/{symbol}` | 개별 종목 시세 |
| `GET`  | `/openapi/v1/account`       | 예수금(cash) / 총자산 / 손익률 |
| `GET`  | `/openapi/v1/positions`     | 보유 종목 목록 및 평가손익 |
| `POST` | `/openapi/v1/orders`        | 시장가 매수/매도 (`{"symbol","side":"BUY|SELL","quantity"}`) |
| `GET`  | `/openapi/v1/orders?limit=` | 주문/체결 내역 |

```bash
# 계좌 조회
curl https://<서비스 도메인>/openapi/v1/account \
  -H "Authorization: Bearer eduapi_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# 삼성전자(005930) 1주 시장가 매수
curl -X POST https://<서비스 도메인>/openapi/v1/orders \
  -H "Authorization: Bearer eduapi_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "005930", "side": "BUY", "quantity": 1}'
```

> **DB 마이그레이션 안내**: `stock_position`/`stock_order`/`api_key` 테이블은 `database/db.sql`에 추가되었습니다. Alembic 등 마이그레이션 도구가 없는 프로젝트 구조상, 이미 데이터가 있는 기존 MariaDB 볼륨에는 자동 반영되지 않습니다. 새로 컨테이너를 띄우는 경우(`docker-entrypoint-initdb.d`)는 자동 적용되며, 기존 볼륨을 계속 쓰는 경우 `database/db.sql`의 신규 `CREATE TABLE` 3개를 해당 DB에 직접 실행해야 합니다.

---

## 7) Docker 실행

### 7-1. 사전 요구사항

`docker-compose.yml`에 로컬 개발용 `mariadb` 컨테이너가 포함되어 있어 별도 준비 없이 바로 기동할 수 있습니다.
최초 기동 시 `database/db.sql`이 `/docker-entrypoint-initdb.d/`로 마운트되어 스키마와 시드 데이터가 자동 적용됩니다.

### 7-2. 앱 실행

```bash
docker compose up -d --build
```

### 7-3. 접속

| 서비스 | URL |
|---|---|
| 웹 서비스 (Nginx) | `http://localhost:3000` |
| Python BE (내부용) | `http://localhost:3000/api/...` (nginx 프록시) |

### 7-4. 종료

```bash
docker compose down

# 볼륨까지 삭제
docker compose down -v
```

### 7-5. 컨테이너 구성

```
crypto-mock-frontend  (Nginx)         :3000 → :80
crypto-mock-mariadb   (MariaDB)       expose 3306 (내부만)
crypto-mock-python    (Flask)         expose 8200 (내부만)
```

Python BE는 외부 포트를 노출하지 않으며, Nginx가 `/api/` 요청을 내부 네트워크를 통해 `python-backend:8200`으로 프록시합니다.

---

## 8) 로컬 개발 (Docker 없이)

Frontend와 Backend를 분리 실행할 경우:

```bash
# 1. Python BE 실행 (DB_HOST 등은 로컬 MariaDB에 맞게 조정)
cd python-stock-backend
pip install -r requirements.txt
DB_HOST=localhost DB_USER=mockinv DB_PASSWORD=12345678!! python app.py

# 2. Frontend 서빙 (python 예시, 포트 임의)
cd frontend
python -m http.server 3000
```

로컬 개발 시 CORS 이슈가 있으므로 [frontend/js/config.js](frontend/js/config.js)의 `apiBase`를 수정합니다:

```js
// frontend/js/config.js
window.APP_CONFIG = {
  apiBase: 'http://localhost:8200',  // Python BE 주소
};
```

---

## 9) Kubernetes 실행 (일반 k8s / dev)

### 9-1. base 배포

```bash
docker build -t python-k-serve-app:latest -f docker/python-backend.Dockerfile .
kubectl apply -k k8s/base
kubectl -n k-serve port-forward svc/k-serve-app 8200:80
```

### 9-2. dev overlay 배포

```bash
docker build -t python-k-serve-app:dev -f docker/python-backend.Dockerfile .
kubectl apply -k k8s/overlays/dev
kubectl -n k-serve-dev port-forward svc/k-serve-app 8200:80
```

---

## 10) Amazon EKS 실행

`k8s/eks`는 EKS + ALB Ingress + in-cluster MariaDB 구성입니다.

### 10-1. 사전 준비

- EKS 클러스터
- AWS Load Balancer Controller 설치
- ECR 리포지토리 생성
- `aws`, `eksctl`, `kubectl`, `docker` CLI

### 10-2. 이미지 빌드 / 푸시

```bash
aws ecr get-login-password --region ap-northeast-2 | \
  docker login --username AWS --password-stdin 123456789012.dkr.ecr.ap-northeast-2.amazonaws.com

docker build -t python-crypto-mock:latest -f docker/python-backend.Dockerfile .
docker tag python-crypto-mock:latest 123456789012.dkr.ecr.ap-northeast-2.amazonaws.com/python-crypto-mock:latest
docker push 123456789012.dkr.ecr.ap-northeast-2.amazonaws.com/python-crypto-mock:latest
```

### 10-3. 배포

```bash
kubectl apply -k k8s/eks
kubectl -n k-serve get ingress k-serve-ingress
```

### 10-4. 배포 스크립트

```bash
export AWS_REGION=ap-northeast-2
export CLUSTER_NAME=crypto-mock-stage
export ECR_REPO=python-crypto-mock-stage

./scripts/aws/01-env.sh
./scripts/aws/02-create-infra.sh
./scripts/aws/03-build-push-image.sh
./scripts/aws/04-deploy.sh
./scripts/aws/05-verify.sh
```

---

## 11) 환경 구분

| 환경 | 런타임 | DB | 진입점 | 배포 기준 |
|---|---|---|---|---|
| `local` | Docker Compose | 로컬 MariaDB 컨테이너 | `localhost:3000` | `docker compose up -d --build` |
| `dev` | 일반 Kubernetes | in-cluster MariaDB | port-forward | `k8s/overlays/dev` |
| `stage` | Amazon EKS + ALB | MariaDB PVC | ALB DNS | `k8s/eks` + `scripts/aws/*` |
| `prod` | Amazon EKS + ALB | 운영 DB | ALB / Route53 | `k8s/eks` + prod env |

---

## 12) CI/CD shell 구성

```bash
./scripts/cicd/ci.sh local
./scripts/cicd/ci.sh dev
./scripts/cicd/ci.sh stage

./scripts/cicd/deploy.sh local
./scripts/cicd/deploy.sh dev
./scripts/cicd/deploy.sh stage
./scripts/cicd/deploy.sh prod
```

| 환경 | 동작 |
|---|---|
| `local` | Python 컴파일 체크 + docker compose 검증 후 로컬 기동 |
| `dev` | Python 컴파일 체크 + k8s/overlays/dev 검증 후 일반 k8s 배포 |
| `stage/prod` | Python 컴파일 체크 + ECR push + EKS 배포 |

---

## 13) Mermaid 다이어그램

### 13-1. 환경별 배포 흐름

```mermaid
flowchart LR
    DEV[Developer]
    LOCAL[local<br/>Docker Compose]
    DEVK8S[dev<br/>k8s/overlays/dev]
    STAGE[stage<br/>EKS + ALB]
    PROD[prod<br/>EKS + ALB]

    DEV --> LOCAL
    LOCAL --> DEVK8S
    DEVK8S --> STAGE
    STAGE --> PROD
```

### 13-2. Docker 런타임 구조

```mermaid
flowchart TD
    USER[Browser :3000]
    NGINX[Nginx Frontend]
    PY[Python BE :8200]
    DB[(MariaDB<br/>shared-net)]

    USER -->|정적 파일| NGINX
    USER -->|/api/ 요청| NGINX
    NGINX -->|proxy_pass| PY
    PY -->|SQLAlchemy| DB
```

### 13-3. 매수 처리 시퀀스

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Browser (JS)
    participant API as crypto.py (trade_bp)
    participant UAPI as Upbit REST API
    participant DB as MariaDB

    U->>FE: 매수 금액 입력 후 클릭
    FE->>API: POST /api/trade/order/buy (JSON)
    API->>API: 세션 회원 조회 및 입력 검증
    API->>UAPI: GET /v1/ticker?markets=KRW-BTC
    UAPI-->>API: 현재가 응답
    API->>DB: HoldCrypto insert/update
    API->>DB: Member.asset 차감
    API-->>FE: { success: true, asset: 잔여금액 }
    FE-->>U: 보유자산 표시 업데이트
```

### 13-4. 국내 거래소 시세 비교 시퀀스

```mermaid
sequenceDiagram
    participant B as Browser
    participant API as crypto.py (market_bp)
    participant U as Upbit
    participant BH as Bithumb
    participant C as Coinone
    participant K as Korbit

    B->>API: GET /api/crypto/{code}/domestic-prices
    API->>U: 현재가 조회
    API->>BH: 현재가 조회
    API->>C: 현재가 조회
    API->>K: 현재가 조회
    U-->>API: KRW price
    BH-->>API: KRW price
    C-->>API: KRW price
    K-->>API: KRW price
    API-->>B: JSON 응답 (5초 주기 polling)
```

---

## 14) AWS 아키텍처

![AWS EKS Architecture](docs/architecture-eks.svg)

---

## 15) MariaDB EC2 배포 플로우

### 환경 정보

| 항목 | 값 |
|---|---|
| **EC2 IP** | `13.125.166.5` |
| **도메인** | `dbms.edumgt.co.kr` |
| **OS** | Amazon Linux 2023 |
| **MariaDB** | 11.4.x (LTS) |
| **포트** | 3306 |
| **접속 계정** | `root / 12345678!!` |

### 배포 플로우

```mermaid
flowchart TD
    A(["로컬 개발 머신"])
    B["AWS IAM 인증"]
    C["EC2 13.125.166.5\nAmazon Linux 2023 / t3.medium"]
    D["MariaDB 11.4 repo 등록\ndlm.mariadb.com"]
    E["MariaDB 11.4.12 설치 완료"]
    F["systemctl enable --now mariadb"]
    G["root 계정 설정\nALTER USER + GRANT ALL"]
    H["EC2 Security Group\nTCP 3306 오픈 확인"]
    I["Docker MariaDB Client\nmariadb -h dbms.edumgt.co.kr\n-u root -p"]
    J(["MariaDB 11.4.12\ndbms.edumgt.co.kr:3306"])

    A -->|"1. aws configure\nAccess Key + Secret Key"| B
    B -->|"2. EC2 인스턴스 조회"| C
    A -->|"3. SSH 접속 ai-agent.pem"| C
    C -->|"4. yum repo 파일 생성"| D
    D -->|"5. dnf install MariaDB-server"| E
    E -->|"6. 서비스 활성화"| F
    F -->|"7. root 비밀번호 설정"| G
    G -->|"8. 0.0.0.0:3306 리스닝 확인"| H
    H -->|"9. 연결 테스트"| I
    I -->|"✅ Connection OK"| J

    style A fill:#4A90D9,color:#fff
    style J fill:#27AE60,color:#fff
    style I fill:#8E44AD,color:#fff
    style H fill:#E67E22,color:#fff
```

### 단계별 명령어 요약

```bash
# 1. AWS CLI 구성 (access key 기반)
aws configure set aws_access_key_id     <ACCESS_KEY_ID>
aws configure set aws_secret_access_key <SECRET_ACCESS_KEY>
aws configure set region                ap-northeast-2

# 2. EC2 인스턴스 확인
aws ec2 describe-instances \
  --filters "Name=ip-address,Values=13.125.166.5" \
  --query 'Reservations[*].Instances[*].{ID:InstanceId,State:State.Name}'

# 3. SSH 접속
chmod 400 ai-agent.pem
ssh -i ai-agent.pem ec2-user@13.125.166.5

# 4. MariaDB 11.4 repo 등록 (EC2 내부)
sudo tee /etc/yum.repos.d/mariadb.repo << 'EOF'
[mariadb]
name = MariaDB 11.4
baseurl = https://dlm.mariadb.com/repo/mariadb-server/11.4/yum/rhel/9/x86_64
gpgkey = https://downloads.mariadb.com/MariaDB/RPM-GPG-KEY-MariaDB
gpgcheck = 1
enabled = 1
EOF

# 5. 설치 및 서비스 시작
sudo dnf install -y MariaDB-server MariaDB-client
sudo systemctl enable --now mariadb

# 6. root 계정 설정
sudo mariadb -u root << 'SQL'
ALTER USER 'root'@'localhost' IDENTIFIED BY '12345678!!';
CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY '12345678!!';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;
FLUSH PRIVILEGES;
SQL

# 7. Docker MariaDB 클라이언트로 접속 테스트 (로컬에서)
docker run --rm mariadb:11.4 \
  mariadb -h dbms.edumgt.co.kr -u root -p'12345678!!' \
  -e "SELECT VERSION(), NOW(), 'Connection OK' AS status;"
```

---

## 16) 주요 경로

| 분류 | 경로 |
|---|---|
| **프론트엔드** | `frontend/` |
| **백엔드 (Python)** | `python-stock-backend/` |
| **DB 스키마** | `database/db.sql` |
| **Docker** | `docker-compose.yml`, `docker/` |
| **Kubernetes(base)** | `k8s/base/` |
| **Kubernetes(dev)** | `k8s/overlays/dev/` |
| **EKS** | `k8s/eks/` |
| **AWS 스크립트** | `scripts/aws/` |
| **CI/CD 스크립트** | `scripts/cicd/` |
| **AWS 콘솔 이미지** | `docs/aws-console/` |
| **AWS 아키텍처 SVG** | `docs/architecture-eks.svg` |

---

# 벡터 데이터베이스(Vector DB) vs 관계형 데이터베이스(RDBMS) 핵심 비교 가이드

본 문서는 전통적인 관계형 데이터베이스(MariaDB)와 AI 기반 서비스의 핵심 인프라인 벡터 데이터베이스(Qdrant)의 패러다임 차이, 작동 방식, 그리고 인덱싱 및 데이터 적재 과정에 대한 핵심 내용을 정리한 가이드입니다.

---

## 1. 핵심 차이점 비교 (Overview)

| 비교 항목 | Qdrant (Vector DB) | MariaDB (RDBMS) |
| :--- | :--- | :--- |
| **주요 데이터 형태** | 고차원 벡터 데이터 (Embedding Vector) | 정형 데이터 (텍스트, 숫자, 날짜 등) |
| **데이터 구조** | 컬렉션(Collection), 포인트(Point), 페이로드(Payload) | 데이터베이스(Database), 테이블(Table), 행/열(Row/Column) |
| **검색 방식** | **유사도 기반 검색 (ANN)**<br>"이 데이터와 맥락이 가장 비슷한 것 5개 찾아줘" | **조건 일치 검색 (SQL)**<br>"이름이 '홍길동'이고 나이가 20세인 사람 찾아줘" |
| **핵심 인덱스** | HNSW (Hierarchical Navigable Small World) 등 | B-Tree, B+Tree |
| **데이터 정합성** | 확률적 결과 (유사도 거리에 따른 근사치) | 철저한 일관성 (**ACID 트랜잭션** 보장) |
| **주요 활용처** | AI 기반 검색, RAG(검색 증강 생성), 추천 시스템 | 회원 관리, 결제/금융 시스템, 전통 웹 백엔드 |

---

## 2. 데이터 적재(Data Pipeline) 용어의 이해

흔히 AI 현업에서 **"참고용 문서를 먹인다"**라고 표현하는 과정은 데이터베이스의 전통적인 데이터 흐름 및 가공 단계와 완벽히 매칭됩니다.

```
[원본 문서 (PDF/Web)] ──(Ingest)──> [텍스트 분할 & 임베딩] ──(Insert/Upsert)──> [Qdrant 저장]
```

* **데이터 인제스트 (Data Ingestion / 수집·유입):** 외부에 있는 원본 문서(PDF, Word, 웹페이지 등)를 시스템 내부로 가져와 가공(Chunking 등)하는 **전체적인 초기 프로세스**를 의미합니다.
* **데이터 인서트 (Data Insertion / 삽입):** 가공 및 변환이 완료된 고차원 벡터 값을 데이터베이스에 **처음으로 새롭게 저장**하는 명확한 동작입니다.
* **데이터 업서트 (Data Upsert / 갱신 및 삽입):** `Update + Insert` 장점을 합친 방식입니다. 데이터가 **기존에 없으면 새로 저장(Insert)하고, 이미 같은 식별자가 존재하면 최신 데이터로 덮어쓰기(Update)**를 수행합니다. 중복 적재를 막기 위해 벡터 DB 파이프라인에서 가장 애용되는 방식입니다.

---

## 3. 인덱스(Index) 메커니즘의 차이

### MariaDB: B-Tree 인덱스
* **개념:** 데이터를 '특정 기준(값)으로 정렬'하여 계층형 구조로 배치하는 방식입니다.
* **특징:** 책 뒷면의 색인(찾아보기)과 같습니다. 조건을 엄격하게 비교하여 (`id = 5` 또는 `age > 20`) 조건에 부합하는 데이터를 **100% 정확하게** 찾아냅니다.

### Qdrant: HNSW 그래프 인덱스
* **개념:** 고차원 공간에 점으로 표현된 벡터들을 **서로 가까운(유사한) 것끼리 선으로 연결하여 다층(Layered) 구조의 네트워크 지도**를 만드는 방식입니다.
* **특징:** 모든 데이터와의 거리를 계산하면 속도가 너무 느려지므로, 그래프 지도를 활용해 최단 거리에 있을 확률이 높은 데이터를 초고속으로 찾아내는 **ANN(근사 최근접 이웃)** 검색을 수행합니다. 결과는 수학적 확률과 유사도 점수로 표현됩니다.

---

## 4. 주요 벡터 데이터베이스(Vector DB) 종류 및 특징

시장에는 Qdrant 외에도 다양한 요구사항에 맞춘 벡터 데이터베이스들이 존재하며, 크게 **전용(Native) DB**와 **기존 DB의 확장형(Extension)**으로 구분됩니다.

### ① 전용(Native) 벡터 DB
* **Qdrant (큐드란트):** Rust 언어로 개발되어 가볍고 빠르며, 강력한 필터링 기능과 오픈소스/자체 구축 환경에 최적화되어 있습니다.
* **Pinecone (파인콘):** 완전 관리형(SaaS) 클라우드 서비스로, 인프라 관리 없이 API 연동만으로 빠르게 AI 서비스를 고도화할 수 있습니다. (서버리스/제옵스)
* **Milvus (밀버스):** 쿠버네티스 기반의 분산 아키텍처를 지원하여 수억에서 수십억 건 규모의 초대형 엔터프라이즈 데이터 처리에 적합합니다.
* **Weaviate (위비에이트):** 키워드 검색(BM25)과 벡터 유사도 검색을 결합한 하이브리드 검색 역량이 뛰어나며 객체 지향 데이터 모델을 지원합니다.
* **Chroma (크로마):** 파이썬 환경에서 메모리/로컬 기반으로 빠르게 동작하여 프로토타입(MVP) 빌드나 AI 실험 시 선호됩니다.

### ② 확장형(Extension) 벡터 DB
* **PostgreSQL + pgvector:** 전통적인 RDBMS 환경 위에서 관계형 데이터와 벡터 데이터를 `SQL JOIN`으로 함께 쿼리할 수 있어 단일 DB 아키텍처 유지에 유리합니다.
* **Elasticsearch / OpenSearch:** 뛰어난 키워드 검색 역량에 벡터 검색 기능을 추가하여, 하이브리드 검색 기반의 대규모 텍스트 검색엔진 구현 시 유수 기업들이 사용합니다.

---

### KServe(구 KFServing)는 쿠버네티스(Kubernetes) 환경에서 머신러닝(ML) 및 딥러닝 모델을 쉽고 효율적으로 배포하고 운영할 수 있도록 도와주는 오픈소스 AI 서빙 플랫폼입니다.

### 쉽게 말해, 데이터 사이언티스트가 학습시킨 AI 모델(예: PyTorch, TensorFlow, LLM 등)을 외부 애플리케이션이 호출해서 쓸 수 있는 안정적이고 확장 가능한 API 엔드포인트(웹 서비스)로 만들어주는 도구입니다.

### KServe의 핵심 특징과 구조를 알기 쉽게 정리해 드립니다.

1. KServe의 핵심 장점
비용 절감을 위한 자동 확장 (Scale-to-Zero): AI 모델, 특히 GPU를 사용하는 모델은 인프라 비용이 매우 비쌉니다. KServe는 트래픽이 없을 때 모델 서버의 개수를 0개로 자동으로 줄여줍니다(Scale-to-Zero). 그러다 사용자의 요청이 들어오면 다시 서버를 띄우는 방식으로 비용을 획기적으로 아낍니다.

표준화된 추론 프로토콜: 모델마다 API 형식을 다르게 짤 필요 없이, 업계 표준인 Open Inference Protocol (V2)이나 OpenAI 호환 API 형식을 그대로 사용할 수 있습니다.

고성능 런타임 내장: 최신 거대 언어 모델(LLM)을 빠르게 서빙하기 위한 vLLM이나, 전통적인 딥러닝을 위한 NVIDIA Triton, 그리고 Scikit-Learn, XGBoost 같은 정형 데이터 모델을 위한 전용 엔진들을 기본적으로 제공합니다. 별도의 Docker 이미지를 직접 만들지 않아도 됩니다.

2. KServe의 3단계 아키텍처
KServe에 모델을 배포(InferenceService)하면, 하나의 요청이 처리되기 위해 크게 3가지 컴포넌트(단계)를 거칠 수 있습니다.

1. Transformer (전처리/후처리 - 선택): 사용자가 보낸 생 데이터(예: 텍스트, 이미지 파일)를 모델이 이해할 수 있는 숫자 배열(텐서, 토큰)로 바꾸거나, 모델의 결과물을 사용자가 보기 편한 형태로 가공합니다.

2. Predictor (예측 엔드포인트 - 필수): 실제 AI 모델이 로드되어 있는 핵심 엔진입니다. 전달받은 데이터를 바탕으로 복잡한 수학 연산을 수행해 예측값을 계산합니다.

3. Explainer (설명 기능 - 선택): AI가 왜 이런 예측 결과를 내놓았는지 그 이유(피처 중요도 등)를 설명해 주는 컴포넌트입니다.

3. 실제 배포는 어떻게 하나요?
복잡한 네트워크 설정이나 서버 환경 구축 필요 없이, 쿠버네티스 설정 파일(YAML) 하나로 엔터프라이즈급 API 서버를 띄울 수 있습니다.

예를 들어, S3 저장소에 저장된 Scikit-learn 모델을 배포하는 코드는 다음과 같이 매우 간단합니다.

---

# 국내 증권사별 Open API 제공 현황 및 특징

**네, 국내 주요 증권사들은 개인 투자자와 개발자를 위한 Open API를 적극적으로 제공하고 있습니다.** 과거에는 윈도우 환경(COM/OCX 방식)에서만 작동하는 제한적인 API가 많았으나, 최근에는 웹이나 모바일 앱 개발에 친숙한 **REST API** 및 실시간 데이터 전송을 위한 **WebSocket** 방식을 도입하는 증권사가 크게 늘었습니다.

---

### 1. 주요 증권사별 Open API 현황

| 증권사 | 서비스 명칭 | 주요 특징 |
| :--- | :--- | :--- |
| **한국투자증권** | KIS Developers | * 국내 최초로 본격적인 **REST API / WebSocket** 도입<br>* 파이썬(Python) 등 다양한 언어 지원, 개발자 커뮤니티 활성화<br>* 해외 주식 및 알고리즘 백테스트 기능 강점 |
| **키움증권** | Open API+ / Next OpenAPI | * 국내 주식 개인 점유율 1위답게 가장 많은 사용자가 이용<br>* 기존 `Open API+`는 윈도우 32비트(OCX) 환경 중심<br>* 최근 REST/WebSocket 기반의 차세대 OpenAPI도 확장 중 |
| **LS증권** *(구 이베스트)* | LS증권 Open API | * 과거 이베스트 시절부터 개발자 친화적인 API 제공<br>* REST API와 WebSocket을 모두 지원하여 시스템 매매에 유용 |
| **미래에셋증권** | Open API | * 자산가 및 다수의 이용자를 위한 주식/파생상품 데이터 및 주문 API 제공 |
| **대신증권** | CYBOS Plus | * 전통의 시스템 트레이딩 강자<br>* 방대한 과거(Historical) 데이터 조회가 가능해 백테스트에 매우 유리<br>* 단, 윈도우 COM 방식 중심이라 파이썬 연결 시 32비트 환경 설정 필요 |

---

### 2. 최근 Open API의 트렌드 변화

* **REST API & WebSocket의 대중화**
  * 과거에는 HTS(Home Trading System)를 켜놓아야만 작동하는 윈도우 전용 API가 대부분이었으나, 현재는 서버 대 서버(Server-to-Server) 통신이 가능한 REST API 방식으로 전환되는 추세입니다. 덕분에 리눅스 서버나 클라우드(AWS 등) 환경에서도 자동매매 프로그램을 구동하기 쉬워졌습니다.
* **해외 주식 거래 지원**
  * 국내 주식뿐만 아니라 미국 주식 등 해외 주식 시세 조회 및 자동 주문을 지원하는 API가 대폭 늘어났습니다.
* **수수료 혜택 및 샘플 코드 제공**
  * 증권사들이 개발자 유치를 위해 깃허브(GitHub) 등을 통해 파이썬, 자바스크립트 샘플 코드를 무료로 공유하고 있습니다.

---

### 💡 이용 시 참고사항

Open API를 이용하려면 **해당 증권사의 계좌를 보유**하고 있어야 하며, 증권사 홈페이지나 개발자 센터에서 **API 사용 신청 및 인증키(App Key / Secret Key)를 발급**받아야 합니다. 

일반적으로 API 이용 자체에 대한 추가 비용은 없으며, 매매 시 발생하는 수수료는 일반 HTS/MTS 수수료와 유사하거나 이벤트 조건에 따라 다르게 적용됩니다.