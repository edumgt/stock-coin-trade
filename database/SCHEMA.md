# 시스템 데이터 스키마

이 시스템은 데이터 성격에 따라 세 저장소를 분리한다. 브라우저는 어느 DB에도 직접 연결하지 않고, Nginx와 Flask API를 통해서만 접근한다.

## 저장소 경계

| 저장소 | 용도 | 초기화 파일 | 민감정보 원칙 |
| --- | --- | --- | --- |
| MariaDB `mockinv` | 회원, 모의주문, 포지션, 관심종목 메모, 서비스 오류 | `database/db.sql` | 증권사 App Key/Secret·계좌 비밀번호는 저장하지 않음 |
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
 ├──< hts_watch_memo       관심종목 개인 메모(주식 화면 메모 탭, 옛 HTS 화면에서 이어 씀)
 ├──< api_key              이 웹앱 Open API용 해시된 키
 ├──< member_session       로그인 세션(토큰 해시만)
 ├──< member_token         메일 인증·재설정 1회용 토큰(해시만)
 ├──< member_activity_day  로그인한 날(KST) 하루 1행, IP·기기 없음
 ├──< api_usage_log        외부 API 테스트 호출·결과 이력 (선택 관계)
 └──< system_error_log     서버·브라우저 오류 분석 로그 (선택 관계)

crypto_rank                공개 시세 랭킹 캐시, 회원과 독립
dart_disclosures           DART 공시 목록과 교육용 유형·위험 판정, 회원과 독립
```

`stock_order.simulated`는 실시세를 받지 못해 시뮬레이션 가격으로 체결한 주문을 표시한다(공개 프로필은 이런 주문을 거절한다).

`*_order`는 변경하지 않는 거래 이력이고, `*_position` 및 `hold_crypto`는 화면의 현재 보유 상태를 빠르게 조회하기 위한 요약 테이블이다. 주문 처리 시 두 종류를 함께 갱신해야 한다.

### API 사용이력 (`api_usage_log`)

| 필드 | 설명 |
| --- | --- |
| `called_at`, `member_id` | 호출 시각과 로그인 회원 식별자 |
| `provider`, `operation`, `method`, `path` | KIS·KB증권·Alpaca 등 제공사와 실행한 테스트 API |
| `request_meta` | 민감값을 제외한 입력값(예: 종목코드) |
| `http_status`, `success`, `duration_ms` | HTTP 결과, 성공 여부, 서버 처리시간 |
| `result_summary`, `response_body` | 마스킹·길이 제한을 적용한 결과 요약과 응답 상세 |

### 회원 인증·동의 기록 (`member`의 추가 열)

| 필드 | 설명 |
| --- | --- |
| `email_verified_at` | 메일 인증 시각. 비어 있으면 로그인할 수 없다(메일 인증을 쓰는 배포). 이 열이 생기기 전 계정은 이전 때 채웠다 |
| `created_at` | 가입 시각. 7일 미인증 정리에 쓴다 |
| `consent_version`, `consented_at` | 동의한 개인정보 처리방침 버전(`accounts.PRIVACY_VERSION`)과 시각. 새 가입 흐름에서만 채운다 |

### 메일 토큰 (`member_token`)

| 필드 | 설명 |
| --- | --- |
| `token_hash` | 토큰의 SHA-256(기본 키). 원본은 메일 링크의 프래그먼트(`#t=`)에만 있다 |
| `member_id`, `purpose` | 회원과 목적(`verify` 24시간, `reset` 30분) |
| `expires_at`, `used_at` | 만료·사용 시각(UTC). 사용은 `used_at IS NULL AND expires_at > now`인 행 하나를 원자적으로 바꿀 때만 성공한다 |

### 활동일·보관 기간

- `member_activity_day(member_id, day)`: 로그인하거나 1시간 넘게 지나 다시 요청한 날(KST)을 하루 한 줄만 남긴다. IP·기기·페이지 정보는 없다. 주간 활성·잔존 집계용이다.
- worker(`retention.py`): 매일 03:10 KST에 가입 흐름(동의 기록 있음)으로 만든 뒤 7일 안에 인증하지 않은 계정을 탈퇴 경로로 지우고, 03:20 KST에 90일 지난 `system_error_log`·`api_usage_log`를 지운다.

### 탈퇴 (`member_delete.py`)

`POST /api/member/delete`(현재 비밀번호 확인)는 한 트랜잭션으로 처리한다.

- 지우는 표: `DELETE_TABLES`(모의투자 주문·보유·메모·API 키·세션·토큰·활동일 등).
- 연결만 끊는 표: `system_error_log`, `api_usage_log`, `ai_usage`의 `member_id`를 NULL로 바꾼다. `ai_usage`는 월 AI 예산 합계를 지키려고 남기므로 `member_id`가 NULL을 허용한다(`ensure_deletable`). `ai_invite`는 연결을 끊고 폐기 처리한다.
- `member_id` 열을 가진 새 표를 만들면 삭제 목록에 넣어야 한다. 넣지 않으면 `tests/integration/test_member_delete.py`가 `information_schema`를 훑어 실패한다.

### 로그인 세션 (`member_session`)

쿠키(Flask 서명 쿠키)에는 `member_id`와 무작위 토큰 `sid`가 있고, 요청마다 이 표로 확인한다(`python-stock-backend/member_sessions.py`). 표에 없거나 만료됐으면 로그아웃 상태가 되며, DB 조회가 실패해도 로그아웃으로 처리한다.

| 필드 | 설명 |
| --- | --- |
| `token_hash` | 토큰의 SHA-256(기본 키). 원본 토큰은 저장하지 않는다 |
| `member_id` | 회원 |
| `created_at`, `last_seen_at` | 발급·마지막 사용 시각(UTC). 마지막 사용은 1시간에 한 번만 갱신한다 |

- 마지막 사용 뒤 7일 또는 발급 뒤 30일이 지나면 만료. worker가 매일 03:00 KST에 만료 행을 지운다.
- 로그아웃은 그 행만, 모든 기기 로그아웃은 회원의 모든 행을 지운다.

### DART 공시 레이더 (`dart_disclosures`)

worker가 5분마다 OpenDART 오늘 목록을 읽어 상장사(유가·코스닥·코넥스) 공시만 넣는다(`python-stock-backend/dart_radar.py`, local 전용).

| 필드 | 설명 |
| --- | --- |
| `rcept_no` | 접수번호(기본 키). 앞 8자리를 날짜로 쓰지 않는다 |
| `rcept_dt` | 접수일. DART가 주는 날짜이며 시각은 없다 |
| `corp_code`, `corp_name`, `stock_code`, `corp_cls` | 회사 고유번호·이름·종목코드·법인구분(Y·K·N) |
| `report_nm`, `rm`, `flr_nm` | 공시 제목(연속 공백 정리), 비고 코드, 제출인 |
| `first_seen_at` | 수집기가 처음 본 시각(UTC). 화면은 KST로 보여 준다 |
| `kind`, `corrected` | 교육용 유형(`src/deskjev/disclosures.py` KINDS)과 정정 공시 여부 |
| `risk`, `kind_prob`, `risk_prob` | 매매 불가 위험 표시와 판정 모델이 정한 항목의 모델 판단 확률(규칙이 정하면 NULL) |
| `judged_by`, `model`, `judged_at` | 판정 주체(`rules`·`jev`), 판정 모델 버전, 판정 시각(UTC) |

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
4. `api_usage_log`는 KIS·KB증권·Alpaca·Binance·Korbit·AWS SSM 테스트 경로만 기록한다. 요청 쿼리, 응답 본문, 실패 메시지는 민감값을 마스킹하고 각각 길이 제한을 둔다. 조회 화면은 로그인한 회원 자신의 이력만 반환한다.
5. MariaDB와 PostgreSQL은 서로 FK를 만들지 않는다. 서비스 API가 데이터 경계와 권한 검사를 담당한다.
6. Qdrant는 관계형 DB가 아니므로 FK가 없다. 문서 식별자와 카테고리는 검색 결과의 메타데이터로 관리한다.
7. `dart_disclosures`에는 OpenDART 인증키를 넣지 않는다. 판정 모델에는 공시 제목·비고·시장만 보내고 회사명은 보내지 않는다.
