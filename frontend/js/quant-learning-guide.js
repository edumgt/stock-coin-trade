(() => {
  const overview = document.getElementById('quant-overview');
  if (overview) overview.insertAdjacentHTML('afterend', `
    <section id="simulation-data-guide" class="quant-card quant-guide-card learning-guide" data-quant-tab="simulation">
      <header><b>?</b><div><h2>시뮬레이션에서 사용하는 데이터</h2><p>어떤 값을 입력하고 무엇을 계산하는지 먼저 확인합니다.</p></div></header>
      <div class="guide-body">
        <div class="learning-definition-grid">
          <article><span>종목</span><h3>symbol</h3><p>분석 대상 코드입니다. 현재 예제는 <code>005930</code>, <code>000660</code>, <code>KRW-BTC</code>입니다.</p></article>
          <article><span>날짜</span><h3>trade_time</h3><p>한 일봉이 끝난 시각입니다. 같은 종목도 거래일마다 한 행씩 저장됩니다.</p></article>
          <article><span>가격</span><h3>OHLC</h3><p><b>open</b> 시가, <b>high</b> 고가, <b>low</b> 저가, <b>close</b> 종가입니다.</p></article>
          <article><span>전략 가격</span><h3>adjusted_close</h3><p>분할·배당 영향을 보정한 종가입니다. 이동평균, RSI, 수익률과 체결 계산에 사용합니다.</p></article>
          <article><span>거래 활동</span><h3>volume</h3><p>해당 일봉의 거래량입니다. 거래량 돌파 전략에서 오늘 거래가 평소보다 활발한지 비교합니다.</p></article>
        </div>
        <div class="learning-data-note"><b>현재 데이터의 성격</b><p>2025-01-02부터 2026-08-12까지 평일 기준으로 생성한 결정론적 교육용 OHLCV입니다. 실제 거래소 원본이 아니며 전략 사용법과 DB 저장 흐름을 반복 실습하기 위한 데이터입니다.</p></div>
        <div class="learning-flow"><article><b>1</b><h3>가격 읽기</h3><p>선택 종목의 과거 일봉을 시간순으로 가져옵니다.</p></article><i>→</i><article><b>2</b><h3>신호 계산</h3><p>과거와 현재 데이터만으로 BUY·SELL 후보를 만듭니다.</p></article><i>→</i><article><b>3</b><h3>모의 체결</h3><p>10주, 수수료 0.015%, 슬리피지 0.05%를 반영합니다.</p></article><i>→</i><article><b>4</b><h3>결과 저장</h3><p>전략, 체결 로그, 수익률과 MDD를 PostgreSQL에 남깁니다.</p></article></div>
        <div class="easy-example"><span>쉬운 시뮬레이션 예시</span><h3>100원에 사서 110원에 팔았다면</h3><p>비용을 빼기 전 1주 손익은 <b>+10원</b>입니다. 실제 화면은 수수료와 매수·매도 슬리피지를 차감하므로 저장되는 손익은 10원보다 작습니다. 이처럼 “신호가 맞았는가”뿐 아니라 거래 비용 이후 결과를 확인합니다.</p></div>
        <div class="result-terms"><article><b>실현 손익</b><p>완료된 매수·매도 한 쌍에서 비용을 빼고 남은 금액입니다.</p></article><article><b>총수익률</b><p>초기 투입금 대비 누적 실현 손익의 비율입니다.</p></article><article><b>MDD</b><p>자산 최고점에서 이후 최저점까지 가장 크게 줄어든 비율입니다.</p></article><article><b>Sharpe</b><p>수익의 크기를 변동성과 함께 보는 참고값이며 거래가 적으면 계산되지 않을 수 있습니다.</p></article></div>
      </div>
    </section>`);

  const algorithmBody = document.querySelector('#quant-guide .guide-body');
  if (algorithmBody) algorithmBody.insertAdjacentHTML('afterbegin', `
    <section class="algorithm-learning" data-algorithm-summary>
      <div class="learning-data-note"><b>알고리즘이 실제로 읽는 데이터</b><p>각 종목의 <code>adjusted_close</code>와 <code>volume</code>을 날짜순으로 사용합니다. 미래 날짜 값은 사용하지 않으며, 열린 포지션은 비교 가능한 결과를 위해 마지막 보유 일봉에서 모의 매도합니다.</p></div>
      <div class="concept-strip"><article><b>알고리즘</b><p>가격을 보고 판단하는 계산 규칙</p></article><article><b>신호</b><p>규칙 결과인 BUY·SELL·HOLD</p></article><article><b>백테스트</b><p>과거 데이터에 신호를 적용한 모의 거래</p></article></div>
      <h3 class="learning-title">전략별 쉬운 숫자 예시</h3>
      <div class="algorithm-example-grid">
        <article><span>추세 · MA 5/20</span><h3>짧은 평균이 긴 평균을 추월</h3><p>어제 MA5가 99, MA20이 100이었는데 오늘 MA5가 101이 되면 <b>BUY</b>입니다. 반대로 아래로 교차하면 SELL입니다.</p></article>
        <article><span>눌림목 · MA 20/60</span><h3>상승 추세에서 20일선 회복</h3><p>MA20=105, MA60=100인 상승 추세에서 종가가 어제 104에서 오늘 106으로 20일선을 회복하면 <b>BUY</b>입니다.</p></article>
        <article><span>반전 · RSI(14)</span><h3>과매도 구간에서 회복</h3><p>RSI가 어제 28에서 오늘 32로 30선을 회복하면 <b>BUY</b>입니다. 72에서 68로 70선 아래로 내려오면 SELL입니다.</p></article>
        <article><span>돌파 · 20일 고점+거래량</span><h3>가격과 거래량이 함께 증가</h3><p>직전 20일 최고 종가가 110, 평균 거래량이 100만인데 오늘 112와 150만이면 <b>BUY</b>입니다. 종가가 MA10 아래면 SELL합니다.</p></article>
        <article><span>모멘텀 · 60일</span><h3>60일 전보다 상승하고 평균 위</h3><p>60일 전 100, 오늘 110이면 수익률은 +10%입니다. 오늘 가격이 MA60 위에도 있으면 <b>BUY</b> 조건입니다.</p></article>
        <article><span>기본 · MA 20/50</span><h3>중기 골든크로스</h3><p>MA20이 MA50을 아래에서 위로 통과하면 BUY, 위에서 아래로 통과하면 SELL, 교차가 없으면 HOLD입니다.</p></article>
      </div>
      <div class="formula-help"><article><h3>이동평균(MA)</h3><p>최근 N개 수정종가 합 ÷ N입니다. MA5는 최근 5일 가격의 평균입니다.</p></article><article><h3>RSI</h3><p>최근 14일 상승폭과 하락폭을 비교해 0~100으로 나타낸 모멘텀 값입니다.</p></article><article><h3>60일 수익률</h3><p><code>(오늘 종가 ÷ 60일 전 종가) − 1</code>입니다. 100에서 110이면 +10%입니다.</p></article><article><h3>팩터 데이터</h3><p>시장·규모·가치·수익성·투자·모멘텀 수익률은 현재 교육용 샘플이며 실제 운용 전 교체해야 합니다.</p></article></div>
    </section>`);
})();
