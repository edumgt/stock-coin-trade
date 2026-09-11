# 시스템 데이터 스키마

이 시스템은 데이터 성격에 따라 세 저장소를 분리한다. 브라우저는 어느 DB에도 직접 연결하지 않고, Nginx와 Flask API를 통해서만 접근한다.

## 저장소 경계

| 저장소 | 용도 | 초기화 파일 | 민감정보 원칙 |
| --- | --- | --- | --- |
| MariaDB `mockinv` | 회원, 모의주문, 포지션, HTS 메모, 서비스 오류 | `database/db.sql` | 증권사 App Key/Secret·계좌 비밀번호는 저장하지 않음 |
| PostgreSQL Quant | OHLCV, 전략, 백테스트 체결·성과, 팩터 | `database/quant-postgres.sql` | 연구 데이터 전용, 회원 DB와 직접 조인하지 않음 |
| Qdrant `market_knowledge` | AI 검색용 문서·카테고리·벡터 | 앱의 `qdrant_service.py` | 원문은 교육/분석 문서만 적재, 비밀값 제외 |

## MariaDB ERD

```text
member (1)
 ├──< stock_position        현재 주식 모의 보유수량과 평균단가
 ├──< stock_order           주식 모의 매수·매도 이력
 ├──< crypto_order          코인 모의 매수·매도 이력
 ├──< hold_crypto >──(1) upbit_market
 ├──< alternative_position 파생·금속·부동산 현재 포지션
 ├──< alternative_order    파생·금속·부동산 주문 이력
 ├──< hts_watch_memo       HTS 관심종목 개인 메모
 ├──< api_key              이 웹앱 Open API용 해시된 키
 └──< system_error_log     서버·브라우저 오류 분석 로그 (선택 관계)

crypto_rank                공개 시세 랭킹 캐시, 회원과 독립
```

`*_order`는 변경하지 않는 거래 이력이고, `*_position` 및 `hold_crypto`는 화면의 현재 보유 상태를 빠르게 조회하기 위한 요약 테이블이다. 주문 처리 시 두 종류를 함께 갱신해야 한다.

## PostgreSQL Quant ERD

```text
market_data (symbol, trade_time)
  └─ OHLCV 시계열. trade_time 범위 파티션과 symbol·time 인덱스 사용

strategies (1) ──< trade_logs
strategies (1) ──< performance_metrics

factor_returns ──[분석 입력]──> factor_exposures
```

| 테이블 | 기본 키 | 역할 |
| --- | --- | --- |
| `market_data` | `symbol, trade_time` | 시가·고가·저가·종가·거래량·수정종가 |
| `strategies` | `strategy_id` | 전략 이름과 JSONB 파라미터 |
| `trade_logs` | `trade_id` | 전략별 BUY/SELL, 비용, 슬리피지, 손익 |
| `performance_metrics` | `strategy_id, start_date, end_date` | 수익률, Sharpe, MDD, 거래 수 |
| `factor_returns` | `factor_date` | 일별 시장·규모·가치 등 팩터 수익률 |
| `factor_exposures` | 기간을 포함한 복합 키 | 종목의 팩터 로딩과 알파·결정계수 |

## 운영 규칙

1. 실제 증권사 인증정보는 프로젝트 루트의 `kis.key`, `kb*.key` 또는 AWS SSM에만 보관한다. DB와 오류 로그에는 원문을 넣지 않는다.
2. `api_key.key_hash`에는 웹앱 자체 API 키의 SHA-256 해시만 저장한다. 원문 키는 생성 시 한 번만 사용자에게 표시한다.
3. `system_error_log`의 요청 메타데이터·메시지는 저장 전에 토큰, 비밀번호, App Key/Secret을 마스킹한다.
4. MariaDB와 PostgreSQL은 서로 FK를 만들지 않는다. 서비스 API가 데이터 경계와 권한 검사를 담당한다.
5. Qdrant는 관계형 DB가 아니므로 FK가 없다. 문서 식별자와 카테고리는 검색 결과의 메타데이터로 관리한다.
