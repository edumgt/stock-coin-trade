# 시스템 데이터 스키마

기준일: 2026-09-27. 이 문서는 실행 중인 DB introspection, `database/*.sql`, Flask의 안전 생성문, Docker Compose 설정을 함께 대조한 결과다. 브라우저는 저장소에 직접 연결하지 않고 Nginx와 Flask API를 통해 접근한다.

## 저장소 카탈로그

| 저장소 | 현재 상태 | 역할 | 연결·영속성 |
| --- | --- | --- | --- |
| PostgreSQL 16 `quant_research` | 운영 중 | Quant OHLCV, 전략, 체결, 성과, 팩터 | `QUANT_DATABASE_URL`, 내부 5432, `postgres-quant-data` 볼륨 |
| PostgreSQL `pg-stock` | 외부 Docker 네트워크 | 국내주식 일봉 원본, 품질·수집 이력, 일일 집계 | `OHLCV_DATABASE_URL`, `postgresql_default` 외부 네트워크 |
| MariaDB 11.4 `mockinv` | 운영 중 | 회원, 웹 모의주문·포지션, KIS 연습, 감사·오류 | 내부 3306, `mariadb-data` 볼륨 |
| Qdrant `market_knowledge` | 인메모리 | RAG 투자 지식 문서·임베딩 | 현재 `QDRANT_URL=:memory:`, 재시작 시 시드 재생성 |
| Redis 7.4 | 운영 중 | Flask 로그인 서버 세션 | `REDIS_URL`, DB 0, 7일 TTL, AOF, `redis-session-data` 볼륨 |

Redis는 로그인 상태만 보관한다. 회원 프로필과 인증 원본은 MariaDB `member`가 유지하며 Redis를 회원 데이터의 원본으로 사용하지 않는다.

## 전체 데이터 경계

```text
Browser
  └─> Nginx
       └─> Flask + SQLAlchemy
            ├─> PostgreSQL quant_research
            ├─> PostgreSQL pg-stock
            ├─> MariaDB mockinv
            ├─> Qdrant market_knowledge
            └─> Redis login session
```

RDB 사이에는 교차 DB FK가 없다. Flask API가 인증, 입력 검증, 저장소 선택과 응답 마스킹을 담당한다. Qdrant는 벡터 컬렉션이므로 RDB FK 대상이 아니다.

## PostgreSQL Quant ERD

```text
market_data (symbol, trade_time) [RANGE PARTITION]
 ├─ market_data_2025
 ├─ market_data_2026
 └─ market_data_default

strategies (1)
 ├──< trade_logs (N)                    FK strategy_id, ON DELETE CASCADE
 └──< performance_metrics (N)           FK strategy_id, ON DELETE CASCADE

market_data + factor_returns
 └·· 회귀분석 입력 ··> factor_exposures  논리 관계, FK 없음
```

### PostgreSQL Quant 테이블 명세

| 테이블 | 키·관계 | 주요 컬럼 | 역할·인덱스 |
| --- | --- | --- | --- |
| `market_data` | PK `(symbol, trade_time)` | `symbol`, `trade_time`, OHLC, `volume`, `adjusted_close` | 시계열 부모. RANGE 파티션, BRIN 시간 인덱스, BTREE 종목·시간 인덱스 |
| `market_data_2025` | 부모 PK 상속 | 부모와 동일 | 2025-01-01 이상 2026-01-01 미만 |
| `market_data_2026` | 부모 PK 상속 | 부모와 동일 | 2026-01-01 이상 2027-01-01 미만 |
| `market_data_default` | 부모 PK 상속 | 부모와 동일 | 명시 범위 밖 데이터 |
| `strategies` | PK `strategy_id` | `name`, `parameters jsonb`, `created_at` | 백테스트 실행과 재현 파라미터 |
| `trade_logs` | PK `trade_id`, FK `strategy_id` | `symbol`, `trade_time`, `side`, `price`, `quantity`, `fee`, `slippage`, `pnl` | BUY/SELL 체결 이벤트, `(strategy_id, trade_time)` 인덱스 |
| `performance_metrics` | PK `(strategy_id,start_date,end_date)`, FK `strategy_id` | Sharpe, MDD, 연환산·총수익률, 거래 수 | 전략·검증기간별 성과 |
| `factor_returns` | PK `factor_date` | 무위험·시장·SMB·HML·RMW·CMA·MOM, `source` | CAPM·멀티팩터 일별 입력 |
| `factor_exposures` | PK `(symbol,model,factor_name,start_date,end_date)` | `loading`, `alpha_annual`, `r_squared`, `observations`, `calculated_at` | 팩터 회귀 결과, 종목·계산시각 인덱스 |

## PostgreSQL pg-stock ERD

```text
tickers (1) ──< ohlcv (N)                 실제 FK

일일 수집 배치
 ├··> ohlcv_sync_status
 ├··> ohlcv_data_quality_issues
 └··> ohlcv_daily_batch_runs

tickers + ohlcv 원본
 ├··> ohlcv_summary_snapshot
 ├··> ohlcv_yearly_summary
 └··> ohlcv_market_summary
```

### PostgreSQL pg-stock 테이블 명세

| 테이블 | 기본 키 | 역할 |
| --- | --- | --- |
| `tickers` | `ticker_code` | 종목명·시장 마스터 |
| `ohlcv` | `(ticker_code, trade_date)` | OHLC·수정종가·거래량 원본, `ticker_code` FK |
| `ohlcv_data_quality_issues` | `(ticker_code, trade_date, reason)` | 검증 격리 사유·원본 파일·탐지 시각 |
| `ohlcv_sync_status` | `(ticker_code, data_year)` | 공급자, 요청기간, 성공·실패, 적재 건수와 오류 |
| `ohlcv_summary_snapshot` | `snapshot_id=1` | 전체 행·종목·기간과 품질·동기화 집계 |
| `ohlcv_yearly_summary` | `data_year` | 연도별 행·종목·기간 집계 |
| `ohlcv_market_summary` | `market` | 시장별 종목 집계 |
| `ohlcv_daily_batch_runs` | `batch_date` | 하루 한 번 실행 보장과 배치 감사 이력 |

## MariaDB 서비스 ERD

```text
member (1)
 ├──< stock_position / stock_order
 ├──< hold_crypto / crypto_order
 ├──< alternative_position / alternative_order
 ├──< kis_practice_account / kis_practice_position / kis_practice_order
 ├──< hts_watch_memo
 ├──< api_key / api_usage_log
 └──< system_error_log

upbit_market (1) ──< hold_crypto
crypto_rank                     회원과 독립
```

### MariaDB 테이블 명세

| 테이블·그룹 | 역할 | 관계·보안 |
| --- | --- | --- |
| `member` | 회원과 웹 모의투자 자산 | 서비스 관계의 기준 엔터티 |
| `stock_position`, `stock_order` | 주식 현재 잔고·주문 이력 | `member_id` FK |
| `hold_crypto`, `crypto_order`, `upbit_market` | 코인 잔고·주문·마켓 | 회원·마켓 FK |
| `alternative_position`, `alternative_order` | 대체자산 포지션·주문 | `member_id` FK |
| `kis_practice_account`, `kis_practice_position`, `kis_practice_order` | 저장소 내부 KIS 연습 데이터 | `member_id` FK, 외부 KIS Paper 계좌와 구분 |
| `hts_watch_memo` | 관심종목 개인 메모 | `member_id` FK |
| `api_key` | 웹앱 Open API 키 | SHA-256 해시만 저장, 원문 미저장 |
| `api_usage_log` | 외부 API 테스트 감사 | 민감 입력·응답 마스킹, 선택적 `member_id` FK |
| `kis_order_approval` | KIS 자동매매 60초 1회용 승인 토큰 | 토큰·의도 SHA-256 다이제스트만 저장, API Key 단위 |
| `kis_autotrade_order` | KIS 자동매매 주문·체결 기록 | (`environment`,`client_order_id`) 멱등키, 계좌번호 마스킹 |
| `system_error_log` | 서버·브라우저 오류 진단 | 토큰·비밀번호 마스킹, 선택적 `member_id` FK |
| `crypto_rank` | 공개 코인 랭킹 캐시 | 회원과 독립 |

## Qdrant 컬렉션 명세

| 항목 | 값 |
| --- | --- |
| 컬렉션 | `market_knowledge` |
| Point ID | UUID 문자열 |
| 임베딩 모델 | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| Payload | `document`, `title`, `category` |
| 연산 | 시드 생성, 문서 추가, 시맨틱 query, payload scroll |
| 현재 영속성 | 없음. `:memory:` 모드이며 재시작 시 기본 지식을 재시드 |

외부 Qdrant를 사용하려면 `QDRANT_URL`을 지정하고 서버 측 볼륨·백업·접근제어를 별도로 구성한다. 인증정보와 회원 개인정보는 vector 또는 payload에 넣지 않는다.

## Redis 로그인 세션 명세

| 항목 | 값 |
| --- | --- |
| 용도 | Flask-Session 기반 로그인 상태 저장 |
| 키 | `stock-coin-trade:session:<sid>` (`REDIS_SESSION_KEY_PREFIX`로 변경 가능) |
| 값 | `member_id`, permanent 상태 등 서버 측 세션 데이터 |
| 브라우저 쿠키 | 서명된 임의 세션 ID만 저장, `HttpOnly`, `SameSite=Lax` |
| TTL | 7일 (`PERMANENT_SESSION_LIFETIME`) |
| 세션 교체 | 로그인·회원가입 성공 시 기존 SID를 폐기하고 새 SID 발급 |
| 영속성 | AOF `everysec`, `redis-session-data` named volume |
| 네트워크 | Compose `internal`, 호스트 포트 미공개 |

로그아웃하면 해당 Redis 세션을 삭제한다. Redis 장애 시 로그인 상태를 MariaDB나 브라우저 쿠키로 대체하지 않으며, Redis 복구 후 다시 로그인한다.

## 운영·보안 규칙

1. 증권사 App Key/Secret, 계좌 비밀번호, AWS 키는 루트 `.env` 또는 AWS Secrets Manager에만 두고 DB·Qdrant·로그에 원문을 저장하지 않는다.
2. PostgreSQL과 MariaDB 포트를 인터넷에 공개하지 않는다. 운영 접근은 컨테이너 내부 명령, SSM, VPN 또는 사설망을 사용한다.
3. `market_data` 파티션은 운영 연도 전에 미리 추가하고 default 파티션의 잔류 데이터를 점검한다.
4. `pg-stock`은 최초 적재 후 12시간마다 증분 수집과 집계 스냅샷 갱신을 실행한다. 기본 실행 시각은 06:20·18:20(Asia/Seoul)이며, 대시보드는 원본 전체 집계를 반복하지 않는다.
5. 백업은 PostgreSQL `pg_dump`, MariaDB `mariadb-dump`를 사용한다. named volume만으로는 백업이 아니다.
6. Qdrant 인메모리 모드는 개발용이다. 사용자 추가 문서를 보존해야 하면 외부 Qdrant와 영속 볼륨·백업을 먼저 구성한다.
7. Redis는 로그인 세션 전용으로 사용하며 회원 원본, 시세 캐시, 작업 큐 용도로 혼용하지 않는다. 세션 키에는 비밀번호·API 키·계좌번호를 저장하지 않는다.
