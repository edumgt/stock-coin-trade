const TPA_LESSONS={
  15:{
    title:'strategy.exit() 손절·익절 테스트',short:'ATR 기준 리스크 관리',
    desc:'5일 이동평균선이 20일 이동평균선을 상향 돌파하면 매수하고, 시장 변동성을 나타내는 ATR을 이용해 손절가와 익절가를 자동 계산하는 추세 추종형 리스크 관리 전략입니다.',
    command:'strategy.exit() · stop · limit · ta.atr()',
    code:`//@version=6
// 전략 선언: 가격 차트 위에 표시하며 초기 자본, 수수료, 주문 비중을 설정합니다.
strategy("5·20 + 손절익절", overlay=true,
     initial_capital=10000000,
     commission_type=strategy.commission.percent, commission_value=0.015,
     default_qty_type=strategy.percent_of_equity, default_qty_value=20)

// 진입 신호 계산: 단기 5일선과 중기 20일선을 매 봉마다 계산합니다.
fast = ta.sma(close, 5)
slow = ta.sma(close, 20)

// 변동성 계산: 최근 14개 봉의 평균 진폭인 ATR을 사용합니다.
// ATR이 커지면 손절·익절 간격도 함께 넓어집니다.
atr  = ta.atr(14)

// 5일선이 20일선을 아래에서 위로 돌파한 봉에서 Long 매수 주문을 냅니다.
if ta.crossover(fast, slow)
    strategy.entry("Long", strategy.long)

// Long 포지션의 평균 진입가를 기준으로 청산 주문을 계속 갱신합니다.
// stop: 진입가에서 ATR 2배 아래, limit: 진입가에서 ATR 3배 위입니다.
// 따라서 이론상 위험 1에 대한 기대 보상은 1.5가 됩니다.
strategy.exit("Exit", from_entry="Long",
     stop  = strategy.position_avg_price - atr * 2,
     limit = strategy.position_avg_price + atr * 3)`,
    mission:'손절 ATR 배수 2를 1.5로 바꾸거나 익절 배수 3을 4로 바꾼 뒤 손절선·익절선과 손익비 변화를 확인합니다.',
    strategy:[['전략 목적','골든크로스로 상승 추세 진입을 시도하되, 고정 금액이 아닌 최근 변동성에 비례한 청산 가격을 사용해 종목과 시기별 가격 움직임 차이에 대응합니다.'],['진입 조건','ta.crossover(fast, slow)는 직전 봉까지 5일선이 20일선 이하에 있다가 현재 봉에서 위로 올라설 때 한 번만 참이 됩니다. 참이 된 봉에서 Long 주문을 생성합니다.'],['청산 조건','strategy.exit는 동일한 Long 진입 주문에 손절 stop과 익절 limit를 동시에 연결합니다. 어느 가격에 먼저 닿는지에 따라 포지션이 청산되며, 포지션 평균가가 바뀌면 기준 가격도 갱신됩니다.'],['손익 구조','손절 거리는 ATR의 2배, 익절 거리는 ATR의 3배이므로 수수료와 슬리피지를 제외한 명목 손익비는 1:1.5입니다. 승률만 보지 말고 평균 손익과 최대 낙폭을 함께 평가해야 합니다.']],
    codeGuide:[['strategy()','백테스트 전략의 이름과 실행 환경을 선언합니다. initial_capital은 시작 자본, commission_value는 거래 수수료율, default_qty_value는 주문당 자산 비중입니다.'],['ta.sma()','종가의 단순 이동평균을 계산합니다. fast는 최근 5개 봉에 민감하게 반응하고 slow는 20개 봉의 완만한 방향을 보여줍니다.'],['ta.atr(14)','고가·저가·이전 종가를 반영한 실제 변동폭의 14기간 평균입니다. 방향 지표가 아니라 가격이 얼마나 크게 움직이는지를 나타냅니다.'],['strategy.entry()','조건이 참일 때 Long 식별자로 매수 진입을 요청합니다. 이 식별자는 뒤의 from_entry와 정확히 일치해야 합니다.'],['strategy.position_avg_price','현재 보유 포지션의 평균 체결 가격입니다. 미보유 구간에는 유효 가격이 없으므로 실제 전략에서는 포지션 보유 여부도 함께 점검할 수 있습니다.'],['strategy.exit()','stop과 limit를 한 번에 지정해 보호성 손절과 목표가 청산을 구성합니다. 백테스트 체결은 봉 데이터와 엔진 가정에 따라 실제 체결과 다를 수 있습니다.']],
    cautions:['이동평균 교차는 후행 신호이므로 횡보장에서는 잦은 진입과 연속 손절이 발생할 수 있습니다.','ATR 배수는 손실 금액 자체를 제한하지 않습니다. 종목 가격, 주문 수량, 계좌 위험 한도를 함께 고려해야 합니다.','갭 하락이나 급변 구간에서는 지정한 stop 가격보다 불리하게 체결될 수 있으며 수수료·세금·슬리피지가 성과를 낮춥니다.'],
    checks:[['진입과 청산 연결','strategy.entry의 Long과 strategy.exit의 from_entry가 같은지 검사합니다.'],['위험 범위 확인','손절가는 진입가보다 낮고 익절가는 진입가보다 높은지 차트에서 확인합니다.'],['현실 조건 반영','수수료와 주문 비중을 전략 선언에 포함해 과도한 결과 해석을 줄입니다.']],
    previous:'/learning/tr-pine/step-14.html',previousLabel:'14단계 · 볼린저 밴드',next:'/learning/tr-pine/step-16.html',nextLabel:'16단계 · table 대시보드'
  },
  16:{
    title:'table 지표 대시보드 테스트',short:'현재 RSI·추세 요약 표',
    desc:'RSI(14)로 현재 과매수·과매도 강도를 판단하고 종가와 20일 이동평균을 비교한 추세 상태를 표로 요약하는 보조지표입니다. overlay=false이므로 가격 차트와 분리된 지표 영역에서 실행됩니다.',
    command:'table.new() · table.cell() · barstate.islast',
    code:`//@version=6
// 보조지표 선언: overlay=false로 가격 차트와 분리된 지표 영역에서 실행합니다.
indicator("지표 대시보드", overlay=false)

// 모멘텀 계산: 최근 14개 봉의 상승·하락 강도를 0~100 값으로 변환합니다.
r = ta.rsi(close, 14)

// 추세 기준 계산: 현재 종가가 20일 이동평균 위인지 아래인지 비교합니다.
trend = ta.sma(close, 20)

// var를 사용해 2열×2행 표를 최초 한 번만 만들고 이후 같은 표를 재사용합니다.
// position.top_left는 표를 지표 영역의 왼쪽 위에 고정합니다.
var table t = table.new(position.top_left, 2, 2, border_width=1)

// 마지막 봉에서만 셀을 갱신해 불필요한 과거 봉의 반복 출력을 줄입니다.
if barstate.islast
    // 첫째 행: RSI 이름과 현재 값을 소수점 한 자리 문자열로 표시합니다.
    table.cell(t, 0, 0, "RSI", text_color=color.white, bgcolor=color.gray)
    table.cell(t, 1, 0, str.tostring(r, "#.0"),
         bgcolor = r > 70 ? color.red : r < 30 ? color.green : color.gray,
         text_color=color.white)
    // 둘째 행: 종가가 20일선보다 높으면 상승, 그렇지 않으면 하락으로 표시합니다.
    table.cell(t, 0, 1, "추세")
    table.cell(t, 1, 1, close > trend ? "상승" : "하락")`,
    mission:'position.top_left를 position.top_right로 바꾸고 RSI 기준 70·30을 65·35로 변경해 대시보드 위치와 상태색을 비교합니다.',
    strategy:[['지표 목적','여러 계산값을 차트에 각각 그리는 대신 현재 시점의 RSI와 이동평균 추세를 작은 표로 요약해 시장 상태를 빠르게 읽도록 돕습니다. 이 코드는 주문을 내지 않는 indicator입니다.'],['RSI 해석','RSI는 최근 상승폭과 하락폭의 상대적 크기를 0~100으로 정규화합니다. 70 초과는 과매수, 30 미만은 과매도로 분류하지만 반전이 즉시 발생한다는 뜻은 아닙니다.'],['추세 해석','현재 종가가 20일 단순 이동평균보다 높으면 상승, 같거나 낮으면 하락으로 표시합니다. 단일 조건이므로 추세의 강도나 지속 기간까지 설명하지는 않습니다.'],['조합 방법','RSI는 모멘텀, 20일선 비교는 방향을 담당합니다. 예를 들어 상승 추세의 과매도 회복처럼 두 정보가 함께 정렬되는지를 관찰하는 보조 판단 도구로 사용할 수 있습니다.']],
    codeGuide:[['indicator()','주문을 생성하지 않는 보조지표를 선언합니다. overlay=false는 가격 캔들 위가 아니라 별도의 지표 패널에서 스크립트를 실행한다는 의미입니다.'],['ta.rsi(close, 14)','종가 기준 14기간 RSI를 계산합니다. 값이 높을수록 최근 상승 압력이, 낮을수록 최근 하락 압력이 상대적으로 강했음을 뜻합니다.'],['ta.sma(close, 20)','최근 20개 종가의 산술평균을 계산해 단순한 추세 기준선으로 사용합니다.'],['var table','var로 선언한 변수는 첫 실행 때 한 번 초기화되고 다음 봉에서도 같은 객체를 유지합니다. 표를 매 봉 새로 만드는 것을 방지합니다.'],['barstate.islast','데이터셋의 마지막 봉 또는 실시간 최신 봉에서만 내부 코드를 실행합니다. 현재 상태판처럼 과거 봉마다 표를 갱신할 필요가 없는 UI에 적합합니다.'],['table.cell()','열·행 좌표의 셀 내용과 색상을 설정합니다. str.tostring은 숫자 RSI를 표시 가능한 문자열로 바꾸고 삼항 연산자는 상태에 따라 배경색을 선택합니다.']],
    cautions:['과매수는 무조건 매도, 과매도는 무조건 매수를 뜻하지 않습니다. 강한 추세에서는 극단값이 오래 유지될 수 있습니다.','현재 값만 보여주는 table은 과거 상태 변화를 직접 그리지 않으므로 검증할 때는 RSI 선이나 신호 이력을 별도로 확인해야 합니다.','20일선 하나로 상승·하락을 이분하면 횡보 구간에서 상태가 자주 바뀔 수 있으므로 기울기, 장기 이동평균 또는 거래량 조건을 보완할 수 있습니다.'],
    checks:[['표는 한 번만 생성','var table과 table.new()로 동일 표가 매 봉마다 다시 만들어지지 않게 합니다.'],['마지막 봉에서 갱신','barstate.islast 안에서 현재 계산값만 table.cell()에 반영합니다.'],['숫자를 문자열로 변환','str.tostring()으로 RSI 숫자를 표에 표시할 텍스트로 변환합니다.']],
    previous:'/learning/tr-pine/step-15.html',previousLabel:'15단계 · 손절·익절',next:'/learning/tradingview-pine.html',nextLabel:'TR 실전연습 개요'
  }
};

const tpaEsc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const TPA_CLOSE=[48,49,50,49,51,53,54,52,51,50,49,48,47,49,51,54,56,58,57,55,53,52,54,57,60,62,61,59,57,56,58,61,64,66,65,63,62,64,67,69,68,66,65,67,70,73,72,71,69,68,70,74,76,75,73,72,74,77,79,78];
let TPA_VIEW='line';
const tpaSma=(values,length)=>values.map((_,index)=>index<length-1?null:values.slice(index-length+1,index+1).reduce((sum,value)=>sum+value,0)/length);
const tpaRsi=(values,length)=>{let gains=0,losses=0;for(let index=Math.max(1,values.length-length);index<values.length;index++){const change=values[index]-values[index-1];if(change>0)gains+=change;else losses-=change}return losses===0?100:100-(100/(1+(gains/length)/(losses/length)))};
const tpaAtr=(values,length)=>{const ranges=values.slice(-length).map((value,index,array)=>{const globalIndex=values.length-length+index,previous=values[Math.max(0,globalIndex-1)],high=value+1.4+(globalIndex%3)*.2,low=value-1.2-(globalIndex%2)*.25;return Math.max(high-low,Math.abs(high-previous),Math.abs(low-previous))});return ranges.reduce((sum,value)=>sum+value,0)/ranges.length};

function tpaValidate(code,step){
  const errors=[];
  const required=step===15?[
    ['strategy(', 'strategy() 선언이 필요합니다.'],['strategy.entry(', '진입 명령 strategy.entry()가 필요합니다.'],['strategy.exit(', '청산 명령 strategy.exit()가 필요합니다.'],['stop', '손절 가격 stop이 필요합니다.'],['limit', '익절 가격 limit가 필요합니다.']
  ]:[['indicator(', 'indicator() 선언이 필요합니다.'],['table.new(', 'table.new() 표 생성이 필요합니다.'],['table.cell(', 'table.cell() 값 입력이 필요합니다.'],['barstate.islast', '마지막 봉 갱신 조건이 필요합니다.']];
  required.forEach(([token,message])=>{if(!code.includes(token))errors.push(message)});
  if(step===15&&/strategy\.exitt\s*\(/.test(code))errors.push('strategy.exitt가 아니라 strategy.exit를 사용하세요.');
  if(step===16&&/table\.cel\s*\(/.test(code))errors.push('table.cel이 아니라 table.cell을 사용하세요.');
  const pairs=[['(',')'],['[',']']];pairs.forEach(([open,close])=>{if((code.split(open).length-1)!==(code.split(close).length-1))errors.push(`${open}${close} 괄호 수가 맞지 않습니다.`)});
  return [...new Set(errors)];
}

function tpaTemplate(step,lesson){
  return `<div class="tp-shell"><div class="tp-title-row"><div class="tp-kicker">TR 실전연습 · 독립 웹앱 ${String(step).padStart(2,'0')} / 16</div><h1>${step}단계. ${lesson.title}</h1><button id="tpaSyntax" type="button" class="tp-syntax-open">기본 문법</button></div><section class="tp-grid"><article class="tp-pane"><div class="tp-instruction"><h3>${lesson.short}</h3><p>${lesson.desc}</p><button id="tpaDetailOpen" type="button" class="tp-plot-help-open">${step===15?'strategy.exit 상세 설명 보기':'table 상세 설명 보기'}</button></div><section id="tpaValidationPass" class="tp-editor-validation-pass" aria-live="polite"><span aria-hidden="true">✓</span><div><b>문법 Validation 통과</b><p>현재 지원 문법에서 오류가 없습니다. 오른쪽 차트와 계산값 변화를 함께 확인하세요.</p></div></section><div class="tp-editor-wrap"><div class="tp-editor-top"><i class="tp-dot"></i><i class="tp-dot"></i><i class="tp-dot"></i><span style="margin-left:5px">Pine Editor · lesson_${step}.pine</span><div class="tp-actions tp-editor-actions" aria-label="Pine Editor 실행 도구"><button id="tpaRun" class="tp-button" type="button">▶ 문법 검사·반영</button><button id="tpaReset" class="tp-button secondary" type="button">처음 코드</button><button id="tpaCopy" class="tp-button copy" type="button">코드 복사</button><span id="tpaStatus" class="tp-status">검사 준비</span></div></div><textarea id="tpaEditor" class="tp-editor" spellcheck="false" aria-label="Pine Script 편집기">${tpaEsc(lesson.code)}</textarea></div><div id="tpaErrors" class="tp-errors" role="alert" aria-live="assertive"></div><section class="tp-code-validation tpa-analysis" aria-live="polite"><div class="tp-validation-head"><div><span>LIVE CODE ANALYSIS</span><h3>코드 Validation · 핵심 변수</h3><p>${step===15?'손절·익절 가격과 손익비를 분석합니다.':'table 생성과 마지막 봉 출력값을 분석합니다.'}</p></div><div class="tp-validation-stats"><b class="is-ok">문법 정상</b><span>${step===15?'전략 1개':'table 1개'}</span></div></div><div id="tpaAnalysisRows" class="tpa-analysis-rows"></div></section><div class="tp-help"><div class="tp-note"><b>핵심 명령 · ${lesson.command}</b>${step===15?'진입 주문과 연결된 stop·limit 가격을 매 봉 계산합니다.':'마지막 봉의 계산값을 차트 위 고정 표에 기록합니다.'}</div><div class="tp-note"><b>작은 미션</b>${lesson.mission}</div></div></article><article class="tp-pane"><div class="tp-chart-meta"><span>마지막 값<strong id="tpaLast">—</strong></span><span>신호<strong id="tpaSignal">—</strong></span><span>실행 유형<strong id="tpaMode">—</strong></span><div class="tp-chart-tools"><span class="tp-tool">KRX:005930</span><span class="tp-tool">1일</span><div class="tp-chart-view" role="group" aria-label="배경 가격 차트 보기"><span>가격 보기</span><button type="button" data-tpa-view="line" class="is-active" aria-pressed="true">라인</button><button type="button" data-tpa-view="candle" aria-pressed="false">캔들</button></div></div></div><div class="tpa-result-stage"><canvas id="tpaChart" aria-label="스크립트 반영 결과 차트"></canvas><div id="tpaDashboard" class="tpa-dashboard" hidden></div></div><div id="tpaResult" class="tp-result"><span class="tp-result-icon">✓</span><span id="tpaResultText"></span></div><section class="tp-live-data tpa-live-data" aria-live="polite"><div class="tp-live-head"><div><span>DAILY OHLCV EXAMPLE</span><h3>${step===15?'ATR 손절·익절 계산값':'RSI·추세 table 계산값'}</h3><p>X축의 일봉 데이터와 현재 스크립트 결과를 함께 확인합니다.</p></div><b><i></i>실시간 반영</b></div><div id="tpaMetrics" class="tpa-metrics"></div></section></article></section><nav class="tpa-stepnav"><a href="${lesson.previous}"><b>← 이전</b>${lesson.previousLabel}</a><a href="${lesson.next}"><b>다음 →</b>${lesson.nextLabel}</a></nav><footer class="tp-footer">EDUMGT · 교육용 모의 차트 · 실제 투자 신호가 아닙니다.</footer></div><div id="tpaModal" class="tp-plot-modal" aria-hidden="true"><div class="tp-plot-modal-backdrop" data-tpa-close></div><section class="tp-plot-modal-dialog" role="dialog" aria-modal="true" aria-labelledby="tpaModalTitle"><header><div><span>STEP ${step} COMMAND GUIDE</span><h2 id="tpaModalTitle">${step===15?'strategy.exit() 상세 설명':'table 대시보드 상세 설명'}</h2><p>${lesson.desc}</p></div><button type="button" data-tpa-close aria-label="설명 닫기">×</button></header><div class="tp-plot-modal-body"><section class="tpa-guide"><span>STEP ${step} TEST GUIDE</span><h3>반영 결과 확인 순서</h3><div class="tpa-guide-grid">${lesson.checks.map(item=>`<div><b>${item[0]}</b><p>${item[1]}</p></div>`).join('')}</div></section></div></section></div><div id="tpaSyntaxModal" class="tp-syntax-modal" aria-hidden="true"><div class="tp-syntax-backdrop" data-tpa-syntax-close></div><section class="tp-syntax-dialog" role="dialog" aria-modal="true" aria-labelledby="tpaSyntaxTitle"><header><div><span>PINE SCRIPT REFERENCE</span><h2 id="tpaSyntaxTitle">기본 문법</h2><p>이번 단계에서 사용하는 핵심 명령어입니다.</p></div><button type="button" data-tpa-syntax-close aria-label="기본 문법 닫기">×</button></header><div class="tpa-syntax-body">${lesson.checks.map(item=>`<article><b>${item[0]}</b><p>${item[1]}</p></article>`).join('')}</div></section></div>`;
}

function tpaAddKoreanGuides(step,lesson){
  const detailBody=document.querySelector('#tpaModal .tp-plot-modal-body');
  const syntaxBody=document.querySelector('#tpaSyntaxModal .tpa-syntax-body');
  const modalTitle=document.getElementById('tpaModalTitle');
  if(modalTitle)modalTitle.textContent=step===15?'ATR 손절·익절 전략 상세 설명':'RSI·추세 대시보드 상세 설명';
  if(detailBody){
    detailBody.classList.add('tpa-detail-body');
    detailBody.style.display='grid';detailBody.style.gap='14px';
    detailBody.innerHTML=`<section class="tpa-guide"><span>STRATEGY OVERVIEW</span><h3>${step===15?'전략 실행 원리와 해석':'지표 구성 원리와 해석'}</h3><div class="tpa-guide-grid tpa-strategy-grid">${lesson.strategy.map(item=>`<div><b>${item[0]}</b><p>${item[1]}</p></div>`).join('')}</div></section><section class="tpa-guide"><span>CODE WALKTHROUGH</span><h3>코드 명령어별 한글 설명</h3><div class="tpa-guide-grid tpa-code-grid">${lesson.codeGuide.map(item=>`<div><b>${item[0]}</b><p>${item[1]}</p></div>`).join('')}</div></section><section class="tpa-guide tpa-caution"><span>INTERPRETATION CAUTION</span><h3>사용 및 해석 시 주의점</h3><ul style="margin:0;padding-left:22px;color:#526079;font-size:13px;line-height:1.8">${lesson.cautions.map(item=>`<li>${item}</li>`).join('')}</ul></section><section class="tpa-guide"><span>STEP ${step} TEST GUIDE</span><h3>반영 결과 확인 순서</h3><div class="tpa-guide-grid">${lesson.checks.map(item=>`<div><b>${item[0]}</b><p>${item[1]}</p></div>`).join('')}</div></section>`;
  }
  if(syntaxBody)syntaxBody.innerHTML=lesson.codeGuide.map(item=>`<article><b>${item[0]}</b><p>${item[1]}</p></article>`).join('');
}

function tpaCanvasBase(canvas){
  const ratio=Math.max(1,window.devicePixelRatio||1),width=canvas.clientWidth||640,height=canvas.clientHeight||410;canvas.width=Math.round(width*ratio);canvas.height=Math.round(height*ratio);const context=canvas.getContext('2d');context.setTransform(ratio,0,0,ratio,0,0);context.clearRect(0,0,width,height);context.fillStyle='#fff';context.fillRect(0,0,width,height);return {context,width,height,pad:{left:48,right:20,top:28,bottom:38}};
}

function tpaDrawSeries(canvas,extra={}){
  const {context,width,height,pad}=tpaCanvasBase(canvas),chartWidth=width-pad.left-pad.right,chartHeight=height-pad.top-pad.bottom,all=[...TPA_CLOSE,...(extra.lines||[]).flat().filter(Number.isFinite),...(extra.levels||[]).map(level=>level.value).filter(Number.isFinite)],min=Math.min(...all)-2,max=Math.max(...all)+2,x=index=>pad.left+index/(TPA_CLOSE.length-1)*chartWidth,y=value=>pad.top+(max-value)/(max-min)*chartHeight;
  context.strokeStyle='#edf0f5';context.lineWidth=1;for(let index=0;index<5;index++){const yy=pad.top+index*chartHeight/4;context.beginPath();context.moveTo(pad.left,yy);context.lineTo(width-pad.right,yy);context.stroke()}
  context.fillStyle='#7b8798';context.font='10px Pretendard';context.textAlign='right';for(let index=0;index<5;index++){const value=max-index*(max-min)/4;context.fillText(value.toFixed(1),pad.left-7,pad.top+index*chartHeight/4+3)}
  if(TPA_VIEW==='candle'){const bodyWidth=Math.max(3,Math.min(8,chartWidth/TPA_CLOSE.length*.58));TPA_CLOSE.forEach((close,index)=>{const open=index?TPA_CLOSE[index-1]:close-.5,high=Math.max(open,close)+1.2,low=Math.min(open,close)-1.1,up=close>=open,color=up?'#0f9d83':'#ef5350',xx=x(index);context.strokeStyle=color;context.fillStyle=color;context.lineWidth=1;context.beginPath();context.moveTo(xx,y(high));context.lineTo(xx,y(low));context.stroke();context.fillRect(xx-bodyWidth/2,y(Math.max(open,close)),bodyWidth,Math.max(2,y(Math.min(open,close))-y(Math.max(open,close))))})}else{context.strokeStyle='#aab2c1';context.lineWidth=1.5;context.beginPath();TPA_CLOSE.forEach((value,index)=>index?context.lineTo(x(index),y(value)):context.moveTo(x(index),y(value)));context.stroke()}
  (extra.lines||[]).forEach((values,index)=>{context.strokeStyle=['#2962ff','#f59e0b'][index]||'#8b5cf6';context.lineWidth=2;context.beginPath();let started=false;values.forEach((value,point)=>{if(!Number.isFinite(value))return;if(started)context.lineTo(x(point),y(value));else{context.moveTo(x(point),y(value));started=true}});context.stroke()});
  (extra.levels||[]).forEach(level=>{const yy=y(level.value);context.save();context.strokeStyle=level.color;context.fillStyle=level.color;context.setLineDash([6,5]);context.beginPath();context.moveTo(pad.left,yy);context.lineTo(width-pad.right,yy);context.stroke();context.setLineDash([]);context.textAlign='left';context.font='700 10px Pretendard';context.fillText(`${level.label} ${level.value.toFixed(2)}`,pad.left+7,yy-5);context.restore()});
}

function tpaRenderStep15(code){
  const atr=tpaAtr(TPA_CLOSE,14),entry=TPA_CLOSE.at(-1),numbers=[...code.matchAll(/atr\s*\*\s*(\d+(?:\.\d+)?)/g)].map(match=>Number(match[1])),stopMultiple=numbers[0]||2,limitMultiple=numbers[1]||3,stop=entry-atr*stopMultiple,limit=entry+atr*limitMultiple,risk=entry-stop,reward=limit-entry,ratio=reward/risk;
  tpaDrawSeries(document.getElementById('tpaChart'),{lines:[tpaSma(TPA_CLOSE,5),tpaSma(TPA_CLOSE,20)],levels:[{label:'익절',value:limit,color:'#0f9d83'},{label:'진입',value:entry,color:'#2962ff'},{label:'손절',value:stop,color:'#ef5350'}]});
  document.getElementById('tpaMetrics').innerHTML=`<div class="tpa-metric"><small>진입 기준</small><b>${entry.toFixed(2)}</b></div><div class="tpa-metric stop"><small>손절 · ATR×${stopMultiple}</small><b>${stop.toFixed(2)}</b></div><div class="tpa-metric limit"><small>익절 · ATR×${limitMultiple}</small><b>${limit.toFixed(2)}</b></div><div class="tpa-metric"><small>손익비</small><b>1 : ${ratio.toFixed(2)}</b></div>`;
  document.getElementById('tpaAnalysisRows').innerHTML=`<div><span>ATR(14)</span><b>${atr.toFixed(3)}</b></div><div><span>stop 계산</span><b>진입가 − ATR×${stopMultiple}</b></div><div><span>limit 계산</span><b>진입가 + ATR×${limitMultiple}</b></div>`;
  document.getElementById('tpaLast').textContent=entry.toFixed(2);document.getElementById('tpaSignal').textContent=`손절 ${stopMultiple} · 익절 ${limitMultiple}`;document.getElementById('tpaMode').textContent='전략 · ATR 리스크 관리';document.getElementById('tpaResultText').textContent=`strategy.exit()가 Long 진입과 연결되었습니다. 손절 ${stop.toFixed(2)}, 익절 ${limit.toFixed(2)}, 손익비 1:${ratio.toFixed(2)}로 계산됩니다.`;
}

function tpaRenderStep16(code){
  const rsi=tpaRsi(TPA_CLOSE,14),trend=tpaSma(TPA_CLOSE,20).at(-1),isUp=TPA_CLOSE.at(-1)>trend,position=/position\.top_right/.test(code)?'right':'left',thresholds=[...code.matchAll(/r\s*[><]\s*(\d+)/g)].map(match=>Number(match[1])),high=thresholds[0]||70,low=thresholds[1]||30,state=rsi>high?'과매수':rsi<low?'과매도':'중립';
  tpaDrawSeries(document.getElementById('tpaChart'),{lines:[tpaSma(TPA_CLOSE,20)]});const dashboard=document.getElementById('tpaDashboard');dashboard.hidden=false;dashboard.style.left=position==='left'?'18px':'auto';dashboard.style.right=position==='right'?'18px':'auto';dashboard.innerHTML=`<header>TABLE · TOP ${position.toUpperCase()}</header><div><span>RSI</span><b class="${state==='과매수'?'down':state==='과매도'?'up':''}">${rsi.toFixed(1)}</b></div><div><span>상태</span><b>${state}</b></div><div><span>추세</span><b class="${isUp?'up':'down'}">${isUp?'상승':'하락'}</b></div>`;
  document.getElementById('tpaMetrics').innerHTML=`<div class="tpa-metric"><small>RSI(14)</small><b>${rsi.toFixed(1)}</b></div><div class="tpa-metric"><small>RSI 상태</small><b>${state}</b></div><div class="tpa-metric"><small>20일선</small><b>${trend.toFixed(2)}</b></div><div class="tpa-metric"><small>표 위치</small><b>TOP ${position.toUpperCase()}</b></div>`;
  document.getElementById('tpaAnalysisRows').innerHTML=`<div><span>table 위치</span><b>TOP ${position.toUpperCase()}</b></div><div><span>RSI 기준</span><b>${low} · ${high}</b></div><div><span>barstate</span><b>마지막 봉 갱신</b></div>`;
  document.getElementById('tpaLast').textContent=TPA_CLOSE.at(-1).toFixed(2);document.getElementById('tpaSignal').textContent=`RSI ${state}`;document.getElementById('tpaMode').textContent='지표 · table 대시보드';document.getElementById('tpaResultText').textContent=`마지막 봉의 RSI ${rsi.toFixed(1)}와 20일선 기준 ${isUp?'상승':'하락'} 추세가 table에 반영되었습니다.`;
}

async function tpaCopy(text){if(navigator.clipboard?.writeText&&window.isSecureContext)return navigator.clipboard.writeText(text);const area=document.createElement('textarea');area.value=text;area.style.cssText='position:fixed;left:-9999px';document.body.append(area);area.select();document.execCommand('copy');area.remove()}

document.addEventListener('DOMContentLoaded',async()=>{
  if(typeof initPage==='function')await initPage();
  const step=Number(document.body.dataset.step),lesson=TPA_LESSONS[step],app=document.getElementById('tpAdvancedApp');if(!lesson||!app)return;
  document.title=`${step}단계 · ${lesson.title} — TR 실전연습`;app.innerHTML=tpaTemplate(step,lesson);tpaAddKoreanGuides(step,lesson);
  const editor=document.getElementById('tpaEditor'),errors=document.getElementById('tpaErrors'),status=document.getElementById('tpaStatus'),result=document.getElementById('tpaResult'),validationPass=document.getElementById('tpaValidationPass');
  const run=()=>{const issues=tpaValidate(editor.value,step);if(issues.length){validationPass.hidden=true;errors.classList.add('show');errors.innerHTML=`<strong>코드를 반영하지 못했습니다.</strong>\n${issues.map(issue=>`• ${tpaEsc(issue)}`).join('\n')}`;status.textContent=`오류 ${issues.length}개`;status.className='tp-status error';result.classList.add('is-error');result.querySelector('.tp-result-icon').textContent='!';document.getElementById('tpaResultText').textContent='왼쪽 오류를 수정한 뒤 다시 문법 검사·반영을 실행하세요.';return}validationPass.hidden=false;errors.classList.remove('show');errors.innerHTML='';status.textContent='문법 정상 · 차트 반영 완료';status.className='tp-status ok';result.classList.remove('is-error');result.querySelector('.tp-result-icon').textContent='✓';if(step===15)tpaRenderStep15(editor.value);else tpaRenderStep16(editor.value)};
  document.getElementById('tpaRun').addEventListener('click',run);document.getElementById('tpaReset').addEventListener('click',()=>{editor.value=lesson.code;run()});document.getElementById('tpaCopy').addEventListener('click',async event=>{const button=event.currentTarget;try{await tpaCopy(editor.value);button.textContent='✓ 복사 완료';setTimeout(()=>button.textContent='코드 복사',1400)}catch{button.textContent='복사 실패';setTimeout(()=>button.textContent='코드 복사',1400)}});
  document.querySelectorAll('[data-tpa-view]').forEach(button=>button.addEventListener('click',()=>{TPA_VIEW=button.dataset.tpaView;document.querySelectorAll('[data-tpa-view]').forEach(item=>{const active=item===button;item.classList.toggle('is-active',active);item.setAttribute('aria-pressed',String(active))});run()}));
  const modal=document.getElementById('tpaModal'),syntaxModal=document.getElementById('tpaSyntaxModal'),openModal=target=>{target.classList.add('open');target.setAttribute('aria-hidden','false');document.body.style.overflow='hidden'},closeModal=target=>{target.classList.remove('open');target.setAttribute('aria-hidden','true');document.body.style.overflow=''};
  document.getElementById('tpaDetailOpen').addEventListener('click',()=>openModal(modal));modal.querySelectorAll('[data-tpa-close]').forEach(item=>item.addEventListener('click',()=>closeModal(modal)));document.getElementById('tpaSyntax').addEventListener('click',()=>openModal(syntaxModal));syntaxModal.querySelectorAll('[data-tpa-syntax-close]').forEach(item=>item.addEventListener('click',()=>closeModal(syntaxModal)));document.addEventListener('keydown',event=>{if(event.key==='Escape'){closeModal(modal);closeModal(syntaxModal)}});
  let inputTimer,resizeTimer;editor.addEventListener('input',()=>{clearTimeout(inputTimer);inputTimer=setTimeout(run,400)});window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(run,120)});run();
});
