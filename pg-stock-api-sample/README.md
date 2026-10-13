# pg-stock-api-sample

`python-stock-backend` 에서 **pg-stock(PostgreSQL) OHLCV 크롤링과 조회 API** 에 관련된 Python 소스만 떼어내
단독으로 실행할 수 있게 모은 샘플입니다. MariaDB·Redis·Qdrant 등 다른 의존성은 없습니다.

## 폴더 구성

```
pg-stock-api-sample/
├─ main.py                         # FastAPI 진입점 (+ APScheduler lifespan)
├─ requirements.txt
├─ .env.example
├─ sql/pg-stock.sql                # pg-stock 초기 스키마 (tickers, ohlcv, 집계·상태 테이블)
├─ tests/test_ohlcv_sync.py        # 수집 구간 계산 단위 테스트
└─ pgstock/
   ├─ config.py                    # 환경변수 설정 (원본 Settings 의 OHLCV 항목만)
   ├─ errors.py                    # ApiError + JSON 오류 핸들러
   ├─ parsing.py                   # clamp / parse_int
   ├─ jobs/
   │  ├─ ohlcv_crawler.py          # 네이버·야후 일봉 다운로드, upsert, 주요 24종목 CLI
   │  ├─ ohlcv_sync.py             # 연도 단위 증분 수집(멱등), ohlcv_sync_status 기록
   │  ├─ ohlcv_aggregate.py        # 집계 스냅샷 갱신, 일일 배치 원장
   │  └─ scheduler.py              # APScheduler 등록 (09:50·12:50·16:50 KST)
   ├─ services/
   │  ├─ ohlcv_store.py            # pg-stock 읽기 전용 조회 (요약·종목·행·공개 API)
   │  ├─ ohlcv_ingest.py           # 종목 하나 온디맨드 적재
   │  └─ openapi_auth.py           # Bearer 키 검증 + 호출 제한
   └─ api/
      ├─ ohlcv_db.py               # GET /api/ohlcv-db/{summary,tickers,rows}
      └─ openapi_ohlcv.py          # /openapi/v1/ohlcv/{search,tickers,{code}} , POST ingest
```

## 원본과 달라진 점

| 항목 | 원본 (`python-stock-backend`) | 샘플 |
|---|---|---|
| import 경로 | `app.core.*`, `app.jobs.*`, `app.services.*` | `pgstock.*` |
| 설정 | `app.core.config.Settings` 전체 | OHLCV 관련 항목만 (`pgstock/config.py`) |
| 스케줄러 | 코인마켓캡·업비트·봇 거래·OHLCV | OHLCV 증분 수집만 |
| Open API 키 | MariaDB `api_key` 테이블 SHA-256 조회 | `OHLCV_API_KEYS` 환경변수 고정 키 |
| Open API 라우트 | 주식·주문·계좌 포함 | `/openapi/v1/ohlcv/*` 만 |

수집·upsert·집계·조회 로직 자체는 원본과 동일합니다.

## 실행

```bash
cd pg-stock-api-sample
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # OHLCV_DATABASE_URL 을 실제 pg-stock 에 맞게 수정

# (처음 한 번) 빈 DB에 스키마 생성
psql "postgresql://admin:admin1234@localhost:55432/admin" -f sql/pg-stock.sql

# 최초 일괄 수집 (내장 주요 24종목, 2020-01-01 ~ 오늘)
python -m pgstock.jobs.ohlcv_crawler
python -m pgstock.jobs.ohlcv_crawler --ticker 005930 --start 2024-01-01 --provider auto --dry-run

# API + 스케줄러 기동
uvicorn main:app --reload --port 8010
```

pg-stock 을 Docker 로 띄우려면 저장소 루트의 `docker-compose.pg-stock.yml` 을 그대로 쓰면 됩니다.

## 수집 흐름

1. `scheduler.start_scheduler()` 가 기동 시 집계 스냅샷을 한 번 만들고, `run_incremental_sync` 를 cron 으로 등록합니다.
2. `ohlcv_sync.collect_ohlcv()` 가 종목마다 `ohlcv` 의 연도별 마지막 거래일을 보고 빠진 연도는 전체,
   올해는 최근 `OHLCV_SYNC_CORRECTION_DAYS` 일부터 다시 받아 `upsert_ticker()` 로 적재합니다.
3. 결과는 `ohlcv_sync_status` 에 종목·연도 단위로 남고, 끝나면 `refresh_ohlcv_aggregates()` 가
   `ohlcv_summary_snapshot` / `ohlcv_yearly_summary` / `ohlcv_market_summary` 를 갱신합니다.
4. 검색에 없는 종목은 `POST /openapi/v1/ohlcv/ingest` 로 즉시 한 종목만 채울 수 있습니다.

## API

| Method | Path | 인증 | 설명 |
|---|---|---|---|
| GET | `/health` | 없음 | 상태 확인 |
| GET | `/api/ohlcv-db/summary` | 없음 | 일일 스냅샷 기반 전체·연도·시장 집계 |
| GET | `/api/ohlcv-db/tickers?q=&limit=&offset=` | 없음 | 종목별 적재 건수 |
| GET | `/api/ohlcv-db/rows?q=&market=&date_from=&...` | 없음 | AG Grid 용 조건 검색·정렬·페이징 |
| GET | `/openapi/v1/ohlcv/search?q=삼성` | 공개(IP 제한) | 종목 자동완성 |
| GET | `/openapi/v1/ohlcv/tickers?year=2026` | 공개(IP 제한) | 수집 종목 탐색 |
| GET | `/openapi/v1/ohlcv/005930?year=2026` | 공개(IP 제한) | 종목 일봉 페이지 조회 |
| POST | `/openapi/v1/ohlcv/ingest` `{"symbol":"035720.KS","name":"카카오"}` | `Authorization: Bearer <OHLCV_API_KEYS>` | 종목 하나 온디맨드 적재 |

## 테스트

```bash
pytest tests
```
