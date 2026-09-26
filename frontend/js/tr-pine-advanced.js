const TPA_LESSONS={
  15:{
    title:'strategy.exit() 손절·익절 테스트',short:'ATR 기준 리스크 관리',
    desc:'진입가를 기준으로 ATR 손절·익절 가격을 계산하고 오른쪽 모의 차트에서 주문 범위와 손익비를 확인합니다.',
    command:'strategy.exit() · stop · limit · ta.atr()',
    code:`//@version=6
strategy("5·20 + 손절익절", overlay=true,
     initial_capital=10000000,
     commission_type=strategy.commission.percent, commission_value=0.015,
     default_qty_type=strategy.percent_of_equity, default_qty_value=20)

fast = ta.sma(close, 5)
slow = ta.sma(close, 20)
atr  = ta.atr(14)

if ta.crossover(fast, slow)
    strategy.entry("Long", strategy.long)

strategy.exit("Exit", from_entry="Long",
     stop  = strategy.position_avg_price - atr * 2,
     limit = strategy.position_avg_price + atr * 3)`,
    mission:'손절 ATR 배수 2를 1.5로 바꾸거나 익절 배수 3을 4로 바꾼 뒤 손절선·익절선과 손익비 변화를 확인합니다.',
    checks:[['진입과 청산 연결','strategy.entry의 Long과 strategy.exit의 from_entry가 같은지 검사합니다.'],['위험 범위 확인','손절가는 진입가보다 낮고 익절가는 진입가보다 높은지 차트에서 확인합니다.'],['현실 조건 반영','수수료와 주문 비중을 전략 선언에 포함해 과도한 결과 해석을 줄입니다.']],
    previous:'/learning/tr-pine/step-14.html',previousLabel:'14단계 · 볼린저 밴드',next:'/learning/tr-pine/step-16.html',nextLabel:'16단계 · table 대시보드'
  },
  16:{
    title:'table 지표 대시보드 테스트',short:'현재 RSI·추세 요약 표',
    desc:'table.new()와 table.cell()을 실행해 현재 RSI와 20일선 기준 추세를 오른쪽 차트 위 대시보드로 확인합니다.',
    command:'table.new() · table.cell() · barstate.islast',
    code:`//@version=6
indicator("지표 대시보드", overlay=true)
r = ta.rsi(close, 14)
trend = ta.sma(close, 20)

var table t = table.new(position.top_left, 2, 2, border_width=1)
if barstate.islast
    table.cell(t, 0, 0, "RSI", text_color=color.white, bgcolor=color.gray)
    table.cell(t, 1, 0, str.tostring(r, "#.0"),
         bgcolor = r > 70 ? color.red : r < 30 ? color.green : color.gray,
         text_color=color.white)
    table.cell(t, 0, 1, "추세")
    table.cell(t, 1, 1, close > trend ? "상승" : "하락")`,
    mission:'position.top_left를 position.top_right로 바꾸고 RSI 기준 70·30을 65·35로 변경해 대시보드 위치와 상태색을 비교합니다.',
    checks:[['표는 한 번만 생성','var table과 table.new()로 동일 표가 매 봉마다 다시 만들어지지 않게 합니다.'],['마지막 봉에서 갱신','barstate.islast 안에서 현재 계산값만 table.cell()에 반영합니다.'],['숫자를 문자열로 변환','str.tostring()으로 RSI 숫자를 표에 표시할 텍스트로 변환합니다.']],
    previous:'/learning/tr-pine/step-15.html',previousLabel:'15단계 · 손절·익절',next:'/learning/tradingview-pine.html',nextLabel:'TR 실전연습 개요'
  }
};

const tpaEsc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const TPA_CLOSE=[48,49,50,49,51,53,54,52,51,50,49,48,47,49,51,54,56,58,57,55,53,52,54,57,60,62,61,59,57,56,58,61,64,66,65,63,62,64,67,69,68,66,65,67,70,73,72,71,69,68,70,74,76,75,73,72,74,77,79,78];
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
  return `<div class="tp-shell"><div class="tp-title-row"><div class="tp-kicker">TR 실전연습 · 독립 웹앱 ${String(step).padStart(2,'0')} / 16</div><h1>${step}단계. ${lesson.title}</h1><a class="tp-start tp-outline" href="https://www.tradingview.com/chart/" target="_blank" rel="noopener">TradingView 열기 ↗</a></div><section class="tp-grid"><article class="tp-pane"><div class="tp-pane-head"><h2>왼쪽 · 스크립트</h2><span class="tpa-badge">직접 수정 가능</span></div><div class="tp-instruction"><h3>${lesson.short}</h3><p>${lesson.desc}</p></div><div class="tp-editor-wrap"><div class="tp-editor-top"><i class="tp-dot"></i><i class="tp-dot"></i><i class="tp-dot"></i><span style="margin-left:5px">Pine Editor · lesson_${step}.pine</span></div><textarea id="tpaEditor" class="tp-editor" spellcheck="false" aria-label="Pine Script 편집기">${tpaEsc(lesson.code)}</textarea></div><div id="tpaErrors" class="tp-errors" role="alert" aria-live="assertive"></div><div class="tp-actions"><button id="tpaRun" class="tp-button" type="button">▶ 문법 검사·반영</button><button id="tpaReset" class="tp-button secondary" type="button">처음 코드</button><button id="tpaCopy" class="tp-button copy" type="button">코드 복사</button><span id="tpaStatus" class="tp-status">검사 준비</span></div><div class="tp-help"><div class="tp-note"><b>핵심 명령 · ${lesson.command}</b>${step===15?'진입 주문과 연결된 stop·limit 가격을 매 봉 계산합니다.':'마지막 봉의 계산값을 차트 위 고정 표에 기록합니다.'}</div><div class="tp-note"><b>작은 미션</b>${lesson.mission}</div></div></article><article class="tp-pane"><div class="tp-pane-head"><h2>오른쪽 · 반영 결과</h2><div class="tp-chart-tools"><span class="tp-tool">KRX:005930</span><span class="tp-tool">1일</span></div></div><div class="tp-chart-meta"><span>마지막 값<strong id="tpaLast">—</strong></span><span>실행 상태<strong id="tpaSignal">—</strong></span><span>실행 유형<strong id="tpaMode">—</strong></span></div><div class="tpa-result-stage"><canvas id="tpaChart" aria-label="스크립트 반영 결과 차트"></canvas><div id="tpaDashboard" class="tpa-dashboard" hidden></div></div><div id="tpaMetrics" class="tpa-metrics"></div><div id="tpaResult" class="tp-result"><span class="tp-result-icon">✓</span><span id="tpaResultText"></span></div></article></section><section class="tpa-guide"><span>STEP ${step} TEST GUIDE</span><h3>반영 결과 확인 순서</h3><div class="tpa-guide-grid">${lesson.checks.map(item=>`<div><b>${item[0]}</b><p>${item[1]}</p></div>`).join('')}</div></section><nav class="tpa-stepnav"><a href="${lesson.previous}"><b>← 이전</b>${lesson.previousLabel}</a><a href="${lesson.next}"><b>다음 →</b>${lesson.nextLabel}</a></nav><footer class="tp-footer">EDUMGT · 교육용 모의 차트 · 실제 투자 신호가 아닙니다.</footer></div>`;
}

function tpaCanvasBase(canvas){
  const ratio=Math.max(1,window.devicePixelRatio||1),width=canvas.clientWidth||640,height=canvas.clientHeight||410;canvas.width=Math.round(width*ratio);canvas.height=Math.round(height*ratio);const context=canvas.getContext('2d');context.setTransform(ratio,0,0,ratio,0,0);context.clearRect(0,0,width,height);context.fillStyle='#fff';context.fillRect(0,0,width,height);return {context,width,height,pad:{left:48,right:20,top:28,bottom:38}};
}

function tpaDrawSeries(canvas,extra={}){
  const {context,width,height,pad}=tpaCanvasBase(canvas),chartWidth=width-pad.left-pad.right,chartHeight=height-pad.top-pad.bottom,all=[...TPA_CLOSE,...(extra.lines||[]).flat().filter(Number.isFinite),...(extra.levels||[]).map(level=>level.value).filter(Number.isFinite)],min=Math.min(...all)-2,max=Math.max(...all)+2,x=index=>pad.left+index/(TPA_CLOSE.length-1)*chartWidth,y=value=>pad.top+(max-value)/(max-min)*chartHeight;
  context.strokeStyle='#edf0f5';context.lineWidth=1;for(let index=0;index<5;index++){const yy=pad.top+index*chartHeight/4;context.beginPath();context.moveTo(pad.left,yy);context.lineTo(width-pad.right,yy);context.stroke()}
  context.fillStyle='#7b8798';context.font='10px Pretendard';context.textAlign='right';for(let index=0;index<5;index++){const value=max-index*(max-min)/4;context.fillText(value.toFixed(1),pad.left-7,pad.top+index*chartHeight/4+3)}
  context.strokeStyle='#aab2c1';context.lineWidth=1.5;context.beginPath();TPA_CLOSE.forEach((value,index)=>index?context.lineTo(x(index),y(value)):context.moveTo(x(index),y(value)));context.stroke();
  (extra.lines||[]).forEach((values,index)=>{context.strokeStyle=['#2962ff','#f59e0b'][index]||'#8b5cf6';context.lineWidth=2;context.beginPath();let started=false;values.forEach((value,point)=>{if(!Number.isFinite(value))return;if(started)context.lineTo(x(point),y(value));else{context.moveTo(x(point),y(value));started=true}});context.stroke()});
  (extra.levels||[]).forEach(level=>{const yy=y(level.value);context.save();context.strokeStyle=level.color;context.fillStyle=level.color;context.setLineDash([6,5]);context.beginPath();context.moveTo(pad.left,yy);context.lineTo(width-pad.right,yy);context.stroke();context.setLineDash([]);context.textAlign='left';context.font='700 10px Pretendard';context.fillText(`${level.label} ${level.value.toFixed(2)}`,pad.left+7,yy-5);context.restore()});
}

function tpaRenderStep15(code){
  const atr=tpaAtr(TPA_CLOSE,14),entry=TPA_CLOSE.at(-1),numbers=[...code.matchAll(/atr\s*\*\s*(\d+(?:\.\d+)?)/g)].map(match=>Number(match[1])),stopMultiple=numbers[0]||2,limitMultiple=numbers[1]||3,stop=entry-atr*stopMultiple,limit=entry+atr*limitMultiple,risk=entry-stop,reward=limit-entry,ratio=reward/risk;
  tpaDrawSeries(document.getElementById('tpaChart'),{lines:[tpaSma(TPA_CLOSE,5),tpaSma(TPA_CLOSE,20)],levels:[{label:'익절',value:limit,color:'#0f9d83'},{label:'진입',value:entry,color:'#2962ff'},{label:'손절',value:stop,color:'#ef5350'}]});
  document.getElementById('tpaMetrics').innerHTML=`<div class="tpa-metric"><small>진입 기준</small><b>${entry.toFixed(2)}</b></div><div class="tpa-metric stop"><small>손절 · ATR×${stopMultiple}</small><b>${stop.toFixed(2)}</b></div><div class="tpa-metric limit"><small>익절 · ATR×${limitMultiple}</small><b>${limit.toFixed(2)}</b></div><div class="tpa-metric"><small>손익비</small><b>1 : ${ratio.toFixed(2)}</b></div>`;
  document.getElementById('tpaLast').textContent=entry.toFixed(2);document.getElementById('tpaSignal').textContent=`손절 ${stopMultiple} · 익절 ${limitMultiple}`;document.getElementById('tpaMode').textContent='전략 · ATR 리스크 관리';document.getElementById('tpaResultText').textContent=`strategy.exit()가 Long 진입과 연결되었습니다. 손절 ${stop.toFixed(2)}, 익절 ${limit.toFixed(2)}, 손익비 1:${ratio.toFixed(2)}로 계산됩니다.`;
}

function tpaRenderStep16(code){
  const rsi=tpaRsi(TPA_CLOSE,14),trend=tpaSma(TPA_CLOSE,20).at(-1),isUp=TPA_CLOSE.at(-1)>trend,position=/position\.top_right/.test(code)?'right':'left',thresholds=[...code.matchAll(/r\s*[><]\s*(\d+)/g)].map(match=>Number(match[1])),high=thresholds[0]||70,low=thresholds[1]||30,state=rsi>high?'과매수':rsi<low?'과매도':'중립';
  tpaDrawSeries(document.getElementById('tpaChart'),{lines:[tpaSma(TPA_CLOSE,20)]});const dashboard=document.getElementById('tpaDashboard');dashboard.hidden=false;dashboard.style.left=position==='left'?'18px':'auto';dashboard.style.right=position==='right'?'18px':'auto';dashboard.innerHTML=`<header>TABLE · TOP ${position.toUpperCase()}</header><div><span>RSI</span><b class="${state==='과매수'?'down':state==='과매도'?'up':''}">${rsi.toFixed(1)}</b></div><div><span>상태</span><b>${state}</b></div><div><span>추세</span><b class="${isUp?'up':'down'}">${isUp?'상승':'하락'}</b></div>`;
  document.getElementById('tpaMetrics').innerHTML=`<div class="tpa-metric"><small>RSI(14)</small><b>${rsi.toFixed(1)}</b></div><div class="tpa-metric"><small>RSI 상태</small><b>${state}</b></div><div class="tpa-metric"><small>20일선</small><b>${trend.toFixed(2)}</b></div><div class="tpa-metric"><small>표 위치</small><b>TOP ${position.toUpperCase()}</b></div>`;
  document.getElementById('tpaLast').textContent=TPA_CLOSE.at(-1).toFixed(2);document.getElementById('tpaSignal').textContent=`RSI ${state}`;document.getElementById('tpaMode').textContent='지표 · table 대시보드';document.getElementById('tpaResultText').textContent=`마지막 봉의 RSI ${rsi.toFixed(1)}와 20일선 기준 ${isUp?'상승':'하락'} 추세가 table에 반영되었습니다.`;
}

async function tpaCopy(text){if(navigator.clipboard?.writeText&&window.isSecureContext)return navigator.clipboard.writeText(text);const area=document.createElement('textarea');area.value=text;area.style.cssText='position:fixed;left:-9999px';document.body.append(area);area.select();document.execCommand('copy');area.remove()}

document.addEventListener('DOMContentLoaded',async()=>{
  if(typeof initPage==='function')await initPage();
  const step=Number(document.body.dataset.step),lesson=TPA_LESSONS[step],app=document.getElementById('tpAdvancedApp');if(!lesson||!app)return;
  document.title=`${step}단계 · ${lesson.title} — TR 실전연습`;app.innerHTML=tpaTemplate(step,lesson);
  const editor=document.getElementById('tpaEditor'),errors=document.getElementById('tpaErrors'),status=document.getElementById('tpaStatus'),result=document.getElementById('tpaResult');
  const run=()=>{const issues=tpaValidate(editor.value,step);if(issues.length){errors.classList.add('show');errors.innerHTML=`<strong>코드를 반영하지 못했습니다.</strong>\n${issues.map(issue=>`• ${tpaEsc(issue)}`).join('\n')}`;status.textContent=`오류 ${issues.length}개`;status.className='tp-status error';result.classList.add('is-error');result.querySelector('.tp-result-icon').textContent='!';document.getElementById('tpaResultText').textContent='왼쪽 오류를 수정한 뒤 다시 문법 검사·반영을 실행하세요.';return}errors.classList.remove('show');errors.innerHTML='';status.textContent='문법 정상 · 반영 완료';status.className='tp-status ok';result.classList.remove('is-error');result.querySelector('.tp-result-icon').textContent='✓';if(step===15)tpaRenderStep15(editor.value);else tpaRenderStep16(editor.value)};
  document.getElementById('tpaRun').addEventListener('click',run);document.getElementById('tpaReset').addEventListener('click',()=>{editor.value=lesson.code;run()});document.getElementById('tpaCopy').addEventListener('click',async event=>{const button=event.currentTarget;try{await tpaCopy(editor.value);button.textContent='✓ 복사 완료';setTimeout(()=>button.textContent='코드 복사',1400)}catch{button.textContent='복사 실패';setTimeout(()=>button.textContent='코드 복사',1400)}});let resizeTimer;window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(run,120)});run();
});
