(() => {
  const quantTables = [
    ['market_data','PK (symbol, trade_time)','symbol, trade_time, OHLC, volume, adjusted_close','OHLCV 파티션 부모','연도 RANGE · BRIN(time) · BTREE(symbol,time)'],
    ['market_data_2025 / 2026 / default','부모 PK 상속','market_data와 동일','연도별 실제 저장 파티션','파티션별 PK·BRIN·symbol/time 인덱스'],
    ['strategies','PK strategy_id','name, parameters jsonb, created_at','백테스트 전략과 재현 파라미터','trade_logs·performance_metrics 부모'],
    ['trade_logs','PK trade_id · FK strategy_id','symbol, trade_time, side, price, quantity, fee, slippage, pnl','전략별 모의 체결 이벤트','CASCADE · strategy/time 인덱스'],
    ['performance_metrics','PK (strategy_id,start_date,end_date) · FK','Sharpe, MDD, 연환산·총수익률, 거래 수','전략·검증기간별 성과','strategies 삭제 시 CASCADE'],
    ['factor_returns','PK factor_date','risk_free, market_excess, smb, hml, rmw, cma, mom, source','CAPM·멀티팩터 일별 입력','현재 학습 샘플'],
    ['factor_exposures','복합 PK (symbol,model,factor_name,기간)','loading, alpha_annual, r_squared, observations, calculated_at','종목·모델·기간별 노출 결과','symbol/calculated_at 인덱스'],
  ];
  const stockTables = [
    ['tickers','PK ticker_code','name, market, created_at','종목 마스터'],
    ['ohlcv','PK (ticker_code,trade_date) · FK ticker_code','OHLC, adj_close, volume','종목·거래일 원본 일봉'],
    ['ohlcv_data_quality_issues','PK (ticker_code,trade_date,reason)','reason, source_file, detected_at','품질 검증 격리 이력'],
    ['ohlcv_sync_status','PK (ticker_code,data_year)','provider, status, 요청기간, 건수, 오류, 실행시각','종목·연도 수집 상태'],
    ['ohlcv_summary_snapshot','PK snapshot_id=1','전체 건수·기간, 품질·동기화 통계, refreshed_at','전체 집계 스냅샷'],
    ['ohlcv_yearly_summary','PK data_year','row_count, ticker_count, 기간, refreshed_at','연도별 집계'],
    ['ohlcv_market_summary','PK market','ticker_count, refreshed_at','시장별 집계'],
    ['ohlcv_daily_batch_runs','PK batch_date','status, 수집·upsert 건수, 실행시각, 오류','하루 한 번 배치 원장'],
  ];
  const serviceTables = [
    ['member','회원 기준 엔터티','모든 개인화·거래 테이블의 부모'],
    ['stock_position · stock_order','주식 모의 잔고 · 주문','member_id FK'],
    ['hold_crypto · crypto_order · upbit_market','코인 잔고 · 주문 · 마켓','member_id, upbit_market_id FK'],
    ['alternative_position · alternative_order','대체자산 포지션 · 주문','member_id FK'],
    ['kis_practice_account · position · order','저장소 내부 KIS 연습 데이터','member_id FK; 외부 KIS Paper와 구분'],
    ['hts_watch_memo','관심종목 개인 메모','member_id FK'],
    ['api_key · api_usage_log','Open API 키 해시 · 호출 감사','member_id FK; 원문 키 저장 금지'],
    ['system_error_log','서버·브라우저 오류','선택적 member_id FK · 민감값 마스킹'],
    ['crypto_rank','공개 코인 랭킹 캐시','회원과 독립'],
  ];
  const rows = items => items.map(item => `<tr>${item.map(value => `<td>${value}</td>`).join('')}</tr>`).join('');
  const quantErd = `market_data (symbol, trade_time) [PARTITIONED]\n ├─ market_data_2025\n ├─ market_data_2026\n └─ market_data_default\n\nstrategies (1)\n ├──< trade_logs (N)          [FK, CASCADE]\n └──< performance_metrics (N) [FK, CASCADE]\n\nmarket_data + factor_returns\n └·· 분석 입력 ··> factor_exposures`;
  const stockErd = `tickers (1) ──< ohlcv (N) [FK]\n\n수집 배치\n ├··> ohlcv_sync_status\n ├··> ohlcv_data_quality_issues\n └··> ohlcv_daily_batch_runs\n\n원본 tickers + ohlcv\n ├··> ohlcv_summary_snapshot\n ├··> ohlcv_yearly_summary\n └··> ohlcv_market_summary`;
  const serviceErd = `member (1)\n ├──< stock_position / stock_order\n ├──< hold_crypto / crypto_order\n ├──< alternative_position / order\n ├──< kis_practice_account / position / order\n ├──< hts_watch_memo\n ├──< api_key / api_usage_log\n └──< system_error_log\n\nupbit_market (1) ──< hold_crypto`;
  const vectorErd = `market_knowledge collection\n point UUID\n ├─ vector: embedding(model output)\n └─ payload\n     ├─ document: 원문\n     ├─ title: 문서 제목\n     └─ category: 분류\n\nRedis\n └─ 현재 서비스·키·TTL·자료구조 없음`;
  const section = document.getElementById('quant-schema');
  document.getElementById('quant-dataset')?.remove();
  document.getElementById('system-erd')?.remove();
  if (!section) return;
  section.outerHTML = `
    <section id="quant-schema" class="quant-card quant-guide-card schema-doc" data-quant-tab="schema"><span data-stack-summary hidden></span><header><b>01</b><div><h2>데이터 저장소 카탈로그</h2><p>실행 중인 Docker 구성과 코드 설정을 기준으로 RDB·VectorDB·Redis 상태를 구분합니다.</p></div></header><div class="guide-body"><div class="schema-version"><b>기준일 2026-09-26</b><span>실행 DB introspection + DDL + Docker Compose 기준</span></div><div class="store-catalog">
      <article class="is-active"><span>RDB · 운영 중</span><h3>PostgreSQL 16 · quant_research</h3><p>Quant 전용 OHLCV, 전략, 체결, 성과, 팩터 데이터입니다. <code>postgres-quant-data</code> 볼륨과 <code>QUANT_DATABASE_URL</code>을 사용합니다.</p><small>내부 5432 · 외부 미공개</small></article>
      <article class="is-active"><span>RDB · 외부 네트워크</span><h3>PostgreSQL · pg-stock</h3><p>국내주식 원본 일봉, 수집 상태, 품질 이슈와 일일 집계 스냅샷을 보관하며 Quant 연구 DB와 분리됩니다.</p><small>OHLCV_DATABASE_URL · 일 1회 배치</small></article>
      <article class="is-active"><span>RDB · 운영 중</span><h3>MariaDB 11.4 · mockinv</h3><p>회원, 웹 모의주문·포지션, KIS 연습 데이터, API 사용 이력과 오류 로그를 처리합니다.</p><small>local-db 프로필 · 내부 3306</small></article>
      <article class="is-memory"><span>VectorDB · 인메모리</span><h3>Qdrant · market_knowledge</h3><p>투자 지식 문서와 임베딩을 검색합니다. 현재 <code>QDRANT_URL=:memory:</code>이므로 재시작 시 시드로 재구성됩니다.</p><small>paraphrase-multilingual-MiniLM-L12-v2</small></article>
      <article class="is-off"><span>Cache · 미도입</span><h3>Redis · 연결 없음</h3><p>Compose 서비스, Python 클라이언트, URL 환경변수, 세션·캐시·큐 의존성이 없습니다. 현재 Redis 데이터 구조도 없습니다.</p><small>필요 시 별도 설계 후 도입</small></article>
    </div><div class="stack-flow schema-stack"><span>Browser</span><i>→</i><span>Nginx</span><i>→</i><span>Flask + SQLAlchemy</span><i>→</i><span>PostgreSQL / MariaDB</span><i>↔</i><span>Qdrant RAG</span></div><p class="guide-note">브라우저는 DB에 직접 연결하지 않습니다. RDB 간 FK는 없고 Flask API가 데이터 경계와 권한을 관리하며 Qdrant는 FK 대상이 아닙니다.</p></div></section>
    <section id="quant-erd-doc" class="quant-card quant-guide-card schema-doc" data-quant-tab="schema"><header><b>02</b><div><h2>전체 데이터 ERD와 논리 관계</h2><p>실제 FK와 분석 입력·집계 생성 같은 논리 관계를 구분해 표시합니다.</p></div></header><div class="guide-body erd-doc-grid"><article><h3>PostgreSQL Quant ERD</h3><pre>${quantErd}</pre></article><article><h3>PostgreSQL pg-stock ERD</h3><pre>${stockErd}</pre></article><article><h3>MariaDB 서비스 ERD</h3><pre>${serviceErd}</pre></article><article><h3>Qdrant 논리 구조 · Redis 상태</h3><pre>${vectorErd}</pre></article></div></section>
    <section id="quant-table-spec" class="quant-card quant-guide-card schema-doc" data-quant-tab="schema"><header><b>03</b><div><h2>테이블·컬렉션 명세서</h2><p>현재 실행 스키마의 키, 주요 컬럼, 역할과 인덱스를 저장소별로 정리합니다.</p></div></header><div class="guide-body spec-groups">
      <details open><summary>PostgreSQL Quant · 6개 논리 테이블 + 3개 파티션</summary><div class="spec-table-wrap"><table><thead><tr><th>테이블</th><th>키·관계</th><th>주요 컬럼</th><th>역할</th><th>인덱스·정책</th></tr></thead><tbody>${rows(quantTables)}</tbody></table></div></details>
      <details><summary>PostgreSQL pg-stock · 8개 테이블</summary><div class="spec-table-wrap"><table><thead><tr><th>테이블</th><th>키·관계</th><th>주요 컬럼</th><th>역할</th></tr></thead><tbody>${rows(stockTables)}</tbody></table></div></details>
      <details><summary>MariaDB mockinv · 16개 테이블</summary><div class="spec-table-wrap"><table><thead><tr><th>테이블·그룹</th><th>역할</th><th>관계·보안</th></tr></thead><tbody>${rows(serviceTables)}</tbody></table></div></details>
      <details><summary>Qdrant 컬렉션 · Redis</summary><div class="vector-spec"><article><h3>Qdrant <code>market_knowledge</code></h3><dl><dt>ID</dt><dd>UUID 문자열</dd><dt>Vector</dt><dd>FastEmbed 모델 출력</dd><dt>Payload</dt><dd><code>document</code>, <code>title</code>, <code>category</code></dd><dt>연산</dt><dd>시드, 문서 추가, 시맨틱 query, payload scroll</dd><dt>영속성</dt><dd>현재 없음(<code>:memory:</code>)</dd></dl></article><article class="redis-empty"><h3>Redis</h3><p>현재 키 명세·TTL·eviction·영속화 정책이 없습니다. 향후 도입 시 세션, 시세 캐시, 작업 큐 중 목적을 확정하고 RDB를 원본으로 유지해야 합니다.</p></article></div></details>
    </div></section>
    <section id="quant-data-policy" class="quant-card quant-guide-card schema-doc" data-quant-tab="schema"><header><b>04</b><div><h2>데이터 흐름·운영 원칙</h2><p>저장소 간 경계, 영속성, 백업과 민감정보 원칙입니다.</p></div></header><div class="guide-body"><div class="schema-details"><article><h3>Quant 연구 흐름</h3><p><code>market_data</code> 조회 → 전략 계산 → <code>strategies</code> 생성 → 체결·성과 저장 순서입니다. 팩터 분석 결과는 <code>factor_exposures</code>에 기록합니다.</p></article><article><h3>주식 원본 흐름</h3><p><code>pg-stock</code>은 최초 적재 후 일 1회 증분 upsert하고 같은 배치에서 집계 스냅샷을 갱신합니다. Quant DB와 자동 복제하거나 FK로 연결하지 않습니다.</p></article><article><h3>AI 검색 흐름</h3><p>문서를 임베딩해 Qdrant에 저장하고 유사도 검색합니다. 비밀번호·토큰·계좌번호·App Secret은 payload나 RDB 로그에 저장하지 않습니다.</p></article></div><div class="policy-strip"><span><b>PostgreSQL</b>named volume · pg_dump</span><span><b>MariaDB</b>named volume · mariadb-dump</span><span><b>Qdrant</b>현재 인메모리 · 재시드</span><span><b>Redis</b>현재 미도입</span></div><div class="guide-warning"><b>네트워크 원칙</b><span>DB 포트를 인터넷에 공개하지 않고 내부 Docker 네트워크 또는 사설 연결만 사용합니다.</span></div></div></section>`;
})();
