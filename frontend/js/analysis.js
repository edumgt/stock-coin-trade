const lessons = [
  { group:'매크로 분석', icon:'fa-earth-asia', items:[
    { id:'macro-indicator', title:'경제지표 분석', subtitle:'금리 · 물가 · 유가로 시장의 온도를 읽는 법', description:'주요 경제지표의 방향과 속도를 함께 확인해 경기 국면과 자산별 영향을 판단합니다.', theory:['금리: 기준금리와 장단기 금리차로 자금 비용과 경기 기대를 확인합니다.','물가: CPI·PCE의 추세와 근원물가를 분리해 통화정책 방향을 읽습니다.','유가: 공급 충격과 수요 회복 신호를 구분하고 운송·화학 업종 영향을 연결합니다.'], tip:'단일 수치보다 <b>전월 대비 변화율</b>과 시장 예상치 대비 차이를 먼저 보세요.', code:`import pandas as pd\nimport matplotlib.pyplot as plt\n\ndf = pd.read_csv('macro_monthly.csv', parse_dates=['date'])\ndf['real_rate'] = df['policy_rate'] - df['cpi_yoy']\nax = df.plot(x='date', y=['policy_rate', 'cpi_yoy', 'oil_usd'])\nplt.show()`, data:{headers:['월','기준금리','CPI YoY','WTI'], rows:[['2025.01','3.00%','2.1%','$75'],['2025.02','2.75%','2.0%','$71'],['2025.03','2.75%','2.1%','$69']]}, result:{value:'-0.65%p',label:'실질금리',bars:[['금리 수준',68],['물가 압력',49],['유가 부담',41]],note:'금리 인하와 안정된 물가는 위험자산에 우호적일 수 있지만, 유가 반등 시 물가 재상승 위험을 함께 점검합니다.'}},
    { id:'macro-practice', title:'거시경제상황 분석 실습', subtitle:'지표를 하나의 투자 시나리오로 연결하기', description:'경제 데이터에서 신호를 찾아 강세·중립·경계 시나리오를 작성하는 실습입니다.', theory:['① 성장(산업생산·고용) ② 물가 ③ 금리 ④ 환율·원자재 순으로 체크합니다.','지표가 좋아도 이미 주가에 반영됐는지 밸류에이션과 함께 판단합니다.','시나리오마다 수혜 업종, 위험 요인, 무효화 조건을 한 줄로 기록합니다.'], tip:'결론은 “상승/하락” 대신 <b>조건부 시나리오</b>로 작성해보세요.', code:`signals = {'growth': 1, 'inflation': 0, 'liquidity': 1}\nscore = sum(signals.values())\nscenario = '확장 국면' if score >= 2 else '방어 국면'\nprint(f'거시 시나리오: {scenario}')`, data:{headers:['지표','최근','전월','판단'], rows:[['산업생산','+1.2%','+0.4%','개선'],['실업률','2.7%','2.8%','개선'],['원/달러','1,345','1,330','경계']]}, result:{value:'확장 국면',label:'매크로 스코어 2 / 3',bars:[['성장',78],['물가 안정',55],['유동성',72]],note:'성장과 유동성은 긍정적입니다. 다만 환율 상승이 지속되면 외국인 수급과 수입물가를 재점검합니다.'}}
  ]},
  { group:'산업 분석', icon:'fa-industry', items:[
    { id:'industry-competitiveness', title:'산업 경쟁력 분석', subtitle:'산업 구조와 경쟁 우위를 체계적으로 비교하기', description:'산업 매력도와 기업 경쟁력을 나누어 보며, 포터의 5가지 경쟁요인을 적용합니다.', theory:['산업 경쟁력은 수익성·성장성·진입장벽·협상력·규제 환경을 종합해 판단합니다.','포터의 5 Forces: 신규 진입, 대체재, 공급자, 구매자, 기존 경쟁 강도입니다.','산업별 핵심 지표가 다릅니다. 반도체는 CAPEX·재고일수, 플랫폼은 MAU·ARPU를 봅니다.'], tip:'시장 점유율이 높아도 가격 결정력이 약하면 높은 수익성을 유지하기 어렵습니다.', code:`forces = {'진입장벽': 4, '구매자 협상력': 2, '대체재 위협': 3}\n# 점수가 높을수록 산업 매력도 우수\nattractiveness = sum(forces.values()) / len(forces)\nprint(f'산업 매력도: {attractiveness:.1f} / 5')`, data:{headers:['경쟁요인','반도체','2차전지','플랫폼'], rows:[['진입장벽','높음','높음','중간'],['가격 결정력','중간','낮음','높음'],['수요 변동성','높음','높음','중간']]}, result:{value:'3.0 / 5',label:'산업 매력도',bars:[['진입장벽',80],['성장성',72],['가격 결정력',48]],note:'고성장 산업이라도 공급 과잉과 고객 협상력이 수익성을 낮출 수 있습니다. 산업 내 선도 기업의 비용 우위를 확인하세요.'}},
    { id:'industry-practice', title:'산업 분석 실습', subtitle:'산업별 핵심지표를 비교해 투자 가설 만들기', description:'동일 산업의 기업을 같은 기준으로 비교하고, 숫자 뒤의 사업 구조를 해석합니다.', theory:['비교 기업의 사업 포트폴리오와 회계연도, 일회성 요인을 먼저 맞춥니다.','매출 성장률·영업이익률·CAPEX·점유율을 한 표에서 추적합니다.','선도 기업과 후발 기업의 격차가 확대되는지 확인합니다.'], tip:'숫자의 우열보다 <b>왜 차이가 생겼는지</b> 사업모델로 설명해보세요.', code:`peer = pd.DataFrame({'기업':['A','B','C'],\n '매출성장률':[14.2,8.6,11.3], '영업이익률':[18.1,9.4,13.0]})\npeer['경쟁력점수'] = peer['매출성장률'] + peer['영업이익률']\nprint(peer.sort_values('경쟁력점수', ascending=False))`, data:{headers:['기업','매출 성장','영업이익률','점유율'], rows:[['A사','14.2%','18.1%','32%'],['B사','8.6%','9.4%','21%'],['C사','11.3%','13.0%','17%']]}, result:{value:'A사 우위',label:'수익성 · 점유율 동시 선도',bars:[['성장성',81],['수익성',86],['시장지위',78]],note:'A사는 성장성과 수익성을 동시에 확보했습니다. 다음 단계는 밸류에이션 프리미엄이 정당한지 확인하는 것입니다.'}}
  ]},
  { group:'기본적 분석', icon:'fa-file-invoice-dollar', items:[
    { id:'fundamental-financials', title:'재무제표 분석', subtitle:'손익계산서 · 재무상태표 · 현금흐름표 읽기', description:'세 재무제표를 연결해 회사의 이익 품질과 재무 안전성을 점검합니다.', theory:['손익계산서: 매출 성장, 마진, 비용 구조에서 이익의 원천을 봅니다.','재무상태표: 부채비율, 유동비율, 운전자본으로 안전성을 살핍니다.','현금흐름표: 영업현금흐름이 순이익을 꾸준히 뒷받침하는지 확인합니다.'], tip:'순이익이 늘어도 <b>영업현금흐름이 따라오지 않으면</b> 매출채권·재고를 확인하세요.', code:`income = {'revenue': 1200, 'op_income': 180}\ncashflow = {'net_income': 142, 'ocf': 165}\nmargin = income['op_income'] / income['revenue'] * 100\ncash_quality = cashflow['ocf'] / cashflow['net_income']\nprint(f'영업이익률 {margin:.1f}%, 이익현금화 {cash_quality:.2f}배')`, data:{headers:['항목','2023','2024','2025E'], rows:[['매출액','1,000','1,110','1,200'],['영업이익','120','142','180'],['영업현금흐름','116','151','165']]}, result:{value:'15.0%',label:'예상 영업이익률',bars:[['매출 성장',74],['마진 개선',83],['현금 창출',88]],note:'매출보다 이익이 빠르게 증가하고 현금흐름도 뒷받침합니다. 재고와 차입금 증감까지 보면 분석이 완성됩니다.'}},
    { id:'fundamental-valuation', title:'기업가치 분석', subtitle:'상대가치평가(멀티플)와 절대가치평가(DCF)', description:'비슷한 기업과 비교하는 멀티플, 미래 현금을 할인하는 DCF를 함께 사용합니다.', theory:['PER·PBR·EV/EBITDA는 동종 기업의 성장성·수익성·부채를 맞춰 비교합니다.','DCF는 FCF, 할인율(WACC), 영구성장률 가정에 민감합니다.','EVA는 자본비용을 웃도는 경제적 이익을 측정합니다.'], tip:'DCF의 숫자 하나보다 <b>가정 변화에 따른 가치 범위</b>를 확인하는 것이 중요합니다.', code:`fcf = [120, 138, 156, 171, 184]\nwacc, g = 0.09, 0.02\npv = sum(cf / (1+wacc)**(i+1) for i, cf in enumerate(fcf))\ntv = fcf[-1] * (1+g) / (wacc-g) / (1+wacc)**5\nenterprise_value = pv + tv\nprint(round(enterprise_value, 1))`, data:{headers:['방법','산출가치','비중','핵심 가정'], rows:[['PER 비교','62,000원','30%','EPS 성장률'],['EV/EBITDA','58,000원','30%','동종 멀티플'],['DCF','65,000원','40%','WACC 9.0%']]}, result:{value:'62,100원',label:'가중 목표주가',bars:[['멀티플 평가',76],['DCF 평가',82],['안전마진',61]],note:'현재가와의 차이가 안전마진입니다. 목표가보다 DCF의 할인율·성장률 가정이 현실적인지 먼저 검증하세요.'}},
    { id:'fundamental-practice', title:'분석기업선정 및 밸류에이션 실습', subtitle:'투자 후보를 고르고 적정가치를 계산하는 전 과정', description:'스크리닝부터 기업 선택, 동종사 비교, 목표가와 투자 메모 작성까지 진행합니다.', theory:['산업 성장성 → 재무 품질 → 경쟁우위 → 밸류에이션 순으로 후보를 좁힙니다.','선정 기준을 사전에 정하면 확증편향을 줄일 수 있습니다.','목표가와 함께 매수 근거, 리스크, 매도 기준을 기록합니다.'], tip:'“좋은 기업”과 “좋은 가격”은 다릅니다. 두 조건을 분리해 체크하세요.', code:`universe = df.query('roe > 10 and debt_ratio < 100')\nselected = universe.sort_values('earnings_growth', ascending=False).head(5)\nselected['target_price'] = selected['eps'] * selected['peer_per']\nprint(selected[['name', 'target_price']])`, data:{headers:['기준','후보 A','후보 B','기준값'], rows:[['ROE','16.2%','11.8%','> 10%'],['부채비율','62%','94%','< 100%'],['예상 PER','11.4x','16.8x','업종 14x']]}, result:{value:'후보 A 선정',label:'재무 품질 · 밸류에이션 우위',bars:[['수익성',81],['안정성',75],['가격 매력',78]],note:'후보 A는 수익성과 밸류에이션이 균형적입니다. 실적 추정치가 유지되는지 분기마다 업데이트하세요.'}}
  ]},
  { group:'기술적 분석', icon:'fa-chart-line', items:[
    { id:'technical-trend', title:'추세 분석', subtitle:'지지·저항 · 이동평균 · 갭 · 되돌림', description:'가격의 방향성과 힘을 먼저 정의하고, 진입·손절 기준을 가격대로 설정합니다.', theory:['상승추세는 고점과 저점이 높아지는 구조로 확인합니다.','이동평균선은 추세 필터로 쓰고, 지지·저항은 거래량과 함께 검증합니다.','갭과 피보나치 되돌림은 반전 가능 구간을 찾는 보조도구입니다.'], tip:'추세선은 예측선이 아니라 <b>시장 참여자의 기준선</b>으로 활용하세요.', code:`df['ma20'] = df['close'].rolling(20).mean()\ndf['ma60'] = df['close'].rolling(60).mean()\ndf['trend'] = (df['ma20'] > df['ma60']).map({True:'상승', False:'하락'})\nprint(df[['close','ma20','ma60','trend']].tail())`, data:{headers:['일자','종가','20일선','60일선'], rows:[['06/03','71,200','69,840','67,130'],['06/04','72,000','70,050','67,240'],['06/05','71,650','70,280','67,360']]}, result:{value:'상승 추세',label:'20일선이 60일선 상회',bars:[['단기 추세',76],['중기 추세',69],['지지 강도',64]],note:'20일선 부근이 첫 지지 후보입니다. 이탈 시 거래량 증가 여부를 보고 손절 기준을 지킵니다.'}},
    { id:'technical-pattern', title:'패턴 · 캔들 차트 분석', subtitle:'가격 패턴과 캔들 심리로 전환 신호 찾기', description:'차트 패턴을 단독 신호로 쓰지 않고 거래량·추세·지지저항과 결합합니다.', theory:['이중바닥·컵앤핸들·삼각수렴은 완성 조건과 돌파 거래량이 중요합니다.','캔들 몸통은 종가 방향, 꼬리는 가격대에서의 매수·매도 공방을 보여줍니다.','반전 패턴은 기존 추세가 충분히 진행된 뒤에 신뢰도가 높아집니다.'], tip:'패턴은 “발견”보다 <b>무효화 가격</b>을 먼저 정할 때 실전에 도움이 됩니다.', code:`body = abs(df.close - df.open)\nrange_ = df.high - df.low\ndf['doji'] = (body / range_) < 0.1\n# 거래량이 동반된 돌파만 후보로 추림\ndf['breakout'] = (df.close > df.high.shift(20)) & (df.volume > df.volume.rolling(20).mean())`, data:{headers:['신호','가격대','거래량','해석'], rows:[['저항 돌파','72,000','평균 1.8배','강세'],['도지','71,650','평균 수준','관망'],['지지 확인','69,800','평균 1.2배','유지']]}, result:{value:'돌파 확인',label:'거래량 동반 저항 돌파',bars:[['패턴 완성도',74],['거래량 확인',82],['추세 일치',70]],note:'저항 돌파 뒤 종가 기준으로 지지 전환되는지 확인합니다. 돌파 당일 추격매수는 손익비를 낮출 수 있습니다.'}},
    { id:'technical-indicators', title:'지표 분석 · 엘리어트파동이론', subtitle:'RSI · MACD · 파동을 보조 신호로 활용하기', description:'보조지표는 가격보다 늦을 수 있으므로 추세와 가격 구조를 우선합니다.', theory:['RSI는 과매수·과매도보다 다이버전스와 50선 회복을 함께 봅니다.','MACD는 모멘텀 변화, 볼린저밴드는 변동성 확대·축소를 관찰합니다.','엘리어트 파동은 하나의 가설입니다. 카운팅보다 무효화 조건이 중요합니다.'], tip:'지표가 여러 개 일치해도 <b>가격의 손절선</b> 없이 진입하지 마세요.', code:`delta = df.close.diff()\ngain = delta.clip(lower=0).rolling(14).mean()\nloss = -delta.clip(upper=0).rolling(14).mean()\ndf['rsi14'] = 100 - (100 / (1 + gain / loss))\nprint(df[['close','rsi14']].tail())`, data:{headers:['지표','현재','전일','해석'], rows:[['RSI(14)','58.4','55.1','중립 상단'],['MACD','+182','+146','상승'],['볼린저 %B','0.72','0.65','상단 접근']]}, result:{value:'중립 · 상승',label:'모멘텀 회복 구간',bars:[['RSI 모멘텀',58],['MACD 방향',72],['변동성',55]],note:'RSI가 과매수권이 아니고 MACD가 개선 중입니다. 다만 밴드 상단 근처에서는 분할 진입과 손절가 설정이 필요합니다.'}},
    { id:'technical-practice', title:'분석기업선정 및 기술적 분석 실습', subtitle:'종목 스크리닝부터 매매계획 수립까지', description:'유동성과 추세가 있는 종목을 고르고, 진입·목표·손절 가격을 수치로 설계합니다.', theory:['거래대금·변동성·추세 조건으로 실습 종목을 먼저 좁힙니다.','진입가, 손절가, 목표가와 포지션 크기를 동시에 정합니다.','손익비와 승률을 기록해 전략을 검증합니다.'], tip:'매매 계획은 장중이 아니라 <b>장 시작 전</b> 작성하는 것이 좋습니다.', code:`entry, stop, target = 71600, 69800, 75200\nrisk = entry - stop\nreward = target - entry\nrr = reward / risk\nposition = 1_000_000 / risk  # 허용 손실 100만원 기준\nprint(f'손익비 {rr:.2f}, 수량 {position:.0f}주')`, data:{headers:['항목','가격','설정 근거'], rows:[['진입가','71,600원','돌파 후 눌림'],['손절가','69,800원','20일선 이탈'],['목표가','75,200원','전고점 구간']]}, result:{value:'2.00 : 1',label:'예상 손익비',bars:[['진입 신뢰도',71],['손절 명확성',88],['보상 가능성',79]],note:'손익비가 2 이상인 계획입니다. 진입 후에는 손절선을 임의로 낮추지 않고, 거래 기록으로 규칙을 검증하세요.'}}
  ]},
  { group:'일자별 학습', icon:'fa-calendar-days', items:[
    { id:'quant-day5', title:'데이터 활용 퀀트 모델링' }
  ]},
  { group:'분석 도구', icon:'fa-shield-halved', items:[
    { id:'json-consistency', title:'정합성검사' }
  ]}
];

const lessonMap = Object.fromEntries(lessons.flatMap(group => group.items.map(item => [item.id, {...item, group:group.group, icon:group.icon}])));
const analysisStorageKey = 'edumgt-investment-academy-progress-v1';
const globalProgressTarget = 100;
function loadLearningState() { try { return JSON.parse(localStorage.getItem(analysisStorageKey)) ?? { lessons:{}, clicks:[] }; } catch { return { lessons:{}, clicks:[] }; } }
let learningState = loadLearningState();
learningState.lessons ??= {}; learningState.clicks ??= []; learningState.completed ??= {};
function saveLearningState() { localStorage.setItem(analysisStorageKey, JSON.stringify(learningState)); }
function lessonLearningState(id) { return learningState.lessons[id] ??= { fields:{}, actions:{} }; }
function markLearningProgress(key) { learningState.completed[key] = true; }
function trackedFieldKey(field) {
  if (field.dataset.quantField) return `quant:${field.dataset.quantField}`;
  if (field.dataset.finance) return `finance:${field.dataset.finance}`;
  if (field.dataset.technicalNote) return `technical:${field.dataset.technicalNote}`;
  if (field.dataset.practiceNote) return `practice:${field.dataset.practiceNote}`;
  if (field.dataset.simCondition !== undefined) return `condition:${field.dataset.conditionIndex}`;
  if (field.dataset.simConditionRange !== undefined) return `strength:${field.dataset.simConditionRange}`;
  if (field.name === 'practice-stock') return 'practice-stock';
  return null;
}
function saveTrackedField(field) { const key=trackedFieldKey(field); if (!key) return; const state=lessonLearningState(activeLesson); state.fields[key] = field.type === 'checkbox' || field.type === 'radio' ? field.checked : field.value; markLearningProgress(`input:${activeLesson}:${key}`); saveLearningState(); updateLearningProgress(); }
function restoreTrackedFields(id) { const fields=lessonLearningState(id).fields; document.querySelectorAll('[data-finance],[data-technical-note],[data-practice-note],[data-sim-condition],[data-sim-condition-range],[data-quant-field],input[name="practice-stock"]').forEach(field => { const key=trackedFieldKey(field); if (!(key in fields)) return; if (field.type === 'checkbox' || field.type === 'radio') field.checked=Boolean(fields[key]) && (field.type !== 'radio' || field.value === fields[key] || fields[key] === true); else field.value=fields[key]; }); }
function learningProgress(id=activeLesson) {
  const state=lessonLearningState(id), fields=state.fields, panel=document.getElementById('analysis-panels');
  if (!panel) return { completed:0, total:1, percent:0 };
  const elements=[...panel.querySelectorAll('[data-finance],[data-technical-note],[data-practice-note],[data-sim-condition],[data-sim-condition-range],[data-quant-field],input[name="practice-stock"]')];
  const keys=[...new Set(elements.map(trackedFieldKey).filter(Boolean))];
  const completed=keys.filter(key => { const value=fields[key]; return typeof value === 'boolean' ? value : String(value ?? '').trim() !== ''; }).length + Object.keys(state.actions).filter(key => key.startsWith('run:') || key === 'sector-select').length;
  const total=keys.length + (panel.querySelector('[data-sim-run],[data-finance-run],[data-practice-review],[data-technical-practice-review],[data-quant-backtest],[data-quant-seasonality],[data-pine-check]') ? 1 : 0) + (id === 'fundamental-practice' ? 1 : 0);
  return { completed:Math.min(completed,total), total, percent:Math.min(100, Math.round(completed / Math.max(total,1) * 100)) };
}
function globalLearningProgress() { const completed=Object.keys(learningState.completed).length; return { completed, total:globalProgressTarget, percent:Math.min(100, Math.round(completed / globalProgressTarget * 100)) }; }
function updateLearningProgress() { const progress=globalLearningProgress(); const bar=document.querySelector('[data-learning-progress-bar]'); const label=document.querySelector('[data-learning-progress-label]'); if (!bar || !label) return; bar.style.width=`${progress.percent}%`; bar.classList.toggle('complete', progress.percent >= 80); label.textContent=`전체 저장 데이터 ${progress.percent}% (${progress.completed}/${progress.total})`; }
const requestedLesson = new URLSearchParams(window.location.search).get('lesson');
let activeLesson = lessonMap[requestedLesson] ? requestedLesson : lessonMap[learningState.activeLesson] ? learningState.activeLesson : 'macro-indicator';
const fullMetricNames = {
  'CPI YoY':'Consumer Price Index Year-over-Year (소비자물가 전년동월비)',
  'WTI':'West Texas Intermediate (서부텍사스산 원유)',
  'ROE':'Return on Equity (자기자본이익률)',
  'PER':'Price to Earnings Ratio (주가수익비율)',
  'EPS':'Earnings Per Share (주당순이익)',
  'EV/EBITDA':'Enterprise Value / Earnings Before Interest, Taxes, Depreciation and Amortization (기업가치/감가상각 전 영업이익)',
  'DCF':'Discounted Cash Flow (현금흐름 할인평가)',
  'WACC':'Weighted Average Cost of Capital (가중평균자본비용)',
  'RSI(14)':'Relative Strength Index, 14-day (14일 상대강도지수)',
  'MACD':'Moving Average Convergence Divergence (이동평균 수렴·확산지수)',
  'CPI':'Consumer Price Index (소비자물가지수)',
  'PCE':'Personal Consumption Expenditures Price Index (개인소비지출 물가지수)',
  'FCF':'Free Cash Flow (잉여현금흐름)',
  'EVA':'Economic Value Added (경제적 부가가치)',
  'PBR':'Price to Book Ratio (주가순자산비율)',
  'CAPEX':'Capital Expenditures (설비투자)',
  'MAU':'Monthly Active Users (월간 활성 이용자 수)',
  'ARPU':'Average Revenue Per User (사용자당 평균 매출)'
};
const metricSources = {
  'CPI YoY': { source:'통계청 국가통계포털(KOSIS)', description:'소비자물가지수의 전년동월비 변화율입니다. 물가 상승 속도를 확인할 때 사용합니다.', url:'https://kosis.kr/' },
  'CPI': { source:'통계청 국가통계포털(KOSIS)', description:'가계가 구입하는 상품과 서비스의 가격 변화를 측정하는 대표 물가지수입니다.', url:'https://kosis.kr/' },
  'PCE': { source:'미국 상무부 경제분석국(BEA)', description:'미국 개인소비지출을 기준으로 산출하는 물가지수입니다. 미국 연방준비제도가 중요하게 참고합니다.', url:'https://www.bea.gov/data/personal-consumption-expenditures-price-index' },
  'WTI': { source:'미국 에너지정보청(EIA)', description:'미국 서부텍사스산 원유의 현물가격 지표입니다. 국제 유가와 에너지·운송 비용 흐름을 살필 때 사용합니다.', url:'https://www.eia.gov/dnav/pet/pet_pri_spt_s1_d.htm' },
  'ROE': { source:'금융감독원 전자공시시스템(DART) · 한국거래소(KRX)', description:'자기자본을 활용해 얼마나 이익을 냈는지 보여주는 수익성 지표입니다.', url:'https://dart.fss.or.kr/' },
  'PER': { source:'금융감독원 전자공시시스템(DART) · 한국거래소(KRX)', description:'주가가 주당순이익의 몇 배인지 나타내는 상대가치평가 지표입니다.', url:'https://dart.fss.or.kr/' },
  'PBR': { source:'금융감독원 전자공시시스템(DART) · 한국거래소(KRX)', description:'주가와 주당순자산의 비율로 기업의 순자산 대비 시장가치를 비교합니다.', url:'https://dart.fss.or.kr/' },
  'EPS': { source:'금융감독원 전자공시시스템(DART)', description:'보통주 한 주당 벌어들인 이익을 뜻합니다. 기업 실적과 밸류에이션의 기초 자료입니다.', url:'https://dart.fss.or.kr/' },
  'EV/EBITDA': { source:'금융감독원 전자공시시스템(DART) · 한국거래소(KRX)', description:'기업가치를 감가상각 전 영업이익으로 나눈 지표로, 자본구조가 다른 기업 비교에 활용합니다.', url:'https://dart.fss.or.kr/' },
  'DCF': { source:'기업 공시자료(DART) 및 자체 추정', description:'미래 잉여현금흐름을 현재가치로 할인해 기업가치를 산정하는 방법입니다.', url:'https://dart.fss.or.kr/' },
  'WACC': { source:'기업 공시자료(DART) · 한국은행 경제통계시스템(ECOS)', description:'부채와 자기자본의 비용을 가중평균한 할인율입니다. DCF 가치평가의 핵심 가정입니다.', url:'https://ecos.bok.or.kr/' },
  'FCF': { source:'금융감독원 전자공시시스템(DART)', description:'영업활동과 투자에 필요한 지출 후 기업에 남는 현금흐름입니다.', url:'https://dart.fss.or.kr/' },
  'EVA': { source:'기업 공시자료(DART) 및 자체 계산', description:'세후 영업이익에서 자본비용을 차감해 경제적으로 창출한 부가가치를 측정합니다.', url:'https://dart.fss.or.kr/' },
  'CAPEX': { source:'금융감독원 전자공시시스템(DART)', description:'설비·공장·장비 등에 사용하는 자본적 지출입니다. 기업의 미래 생산능력 투자 수준을 보여줍니다.', url:'https://dart.fss.or.kr/' },
  'MAU': { source:'기업 실적발표 자료 및 공시', description:'한 달 동안 서비스를 실제 이용한 사용자 수입니다. 플랫폼 기업의 규모와 성장성을 판단할 때 봅니다.', url:'https://dart.fss.or.kr/' },
  'ARPU': { source:'기업 실적발표 자료 및 공시', description:'사용자 한 명당 평균 매출입니다. 플랫폼·통신 서비스의 수익화 수준을 보여줍니다.', url:'https://dart.fss.or.kr/' },
  'RSI(14)': { source:'한국거래소(KRX) 시세 또는 증권사 HTS', description:'최근 14일의 상승·하락 강도를 비교해 모멘텀을 나타내는 기술적 지표입니다.', url:'https://data.krx.co.kr/' },
  'MACD': { source:'한국거래소(KRX) 시세 또는 증권사 HTS', description:'두 이동평균선의 차이를 이용해 추세와 모멘텀 변화를 보는 기술적 지표입니다.', url:'https://data.krx.co.kr/' }
};
const marketCheckSources = {
  '성장(산업생산·고용)': { source:'통계청 국가통계포털(KOSIS)', description:'산업생산지수로 기업 활동과 생산 흐름을, 고용·실업 통계로 가계와 노동시장의 강도를 확인합니다. 두 지표를 함께 보면 경기 확장 또는 둔화 신호를 더 균형 있게 판단할 수 있습니다.', links:[{ label:'KOSIS 산업생산·고용 통계', url:'https://kosis.kr/' }] },
  '물가': { source:'통계청 국가통계포털(KOSIS)', description:'소비자물가지수(CPI)와 근원물가를 확인해 생활물가의 상승 속도와 통화정책 부담을 살핍니다.', links:[{ label:'KOSIS 소비자물가 통계', url:'https://kosis.kr/' }] },
  '금리': { source:'한국은행 경제통계시스템(ECOS)', description:'기준금리, 국고채 금리, 시장금리를 통해 자금 조달 비용과 향후 경기·물가 기대를 확인합니다.', links:[{ label:'한국은행 ECOS 금리 통계', url:'https://ecos.bok.or.kr/' }] },
  '환율·원자재': { source:'한국은행 ECOS · 세계은행 Commodity Markets', description:'원/달러 환율은 대외 수급과 수입물가 부담을, 원유·금속 등 원자재 가격은 생산비와 글로벌 수요 흐름을 보여줍니다.', links:[{ label:'한국은행 ECOS 환율 통계', url:'https://ecos.bok.or.kr/' },{ label:'World Bank 원자재 가격 자료', url:'https://www.worldbank.org/en/research/commodity-markets' }] }
};
const strategyConceptSources = {
  '포터의 5 Forces': { source:'Harvard Business Review · Michael E. Porter', description:'산업의 평균 수익성과 경쟁 강도를 다섯 가지 힘으로 분석하는 산업구조 분석 모형입니다. 단순히 현재 경쟁사만 보는 것이 아니라, 산업의 이익을 압박하는 모든 방향을 함께 점검합니다.', details:['<b>기존 경쟁자 간 경쟁:</b> 가격 경쟁, 차별화, 시장 성장률이 현재 기업들의 수익성을 얼마나 압박하는지 봅니다.','<b>신규 진입자의 위협:</b> 자본·기술·브랜드·규제·유통망 같은 진입장벽이 낮을수록 새 경쟁자가 늘어날 수 있습니다.','<b>공급자의 교섭력:</b> 핵심 원재료·부품·인력 공급자가 적거나 대체가 어렵다면 기업의 비용이 올라갈 수 있습니다.','<b>구매자의 교섭력:</b> 고객이 소수이거나 가격 비교·전환이 쉬우면 판매가격과 마진에 압력이 생깁니다.','<b>대체재의 위협:</b> 다른 제품·서비스가 같은 고객 문제를 더 싸거나 편리하게 해결하면 수요가 이동할 수 있습니다.'], links:[{ label:'HBR 원문: The Five Competitive Forces That Shape Strategy', url:'https://hbr.org/2008/01/the-five-competitive-forces-that-shape-strategy' }] }
};
const valuationTermSources = {
  '상대가치평가': { description:'비슷한 사업을 하는 다른 기업이 시장에서 몇 배의 가치를 받고 있는지 비교해 적정가치를 추정하는 방법입니다. PER, PBR, EV/EBITDA 같은 멀티플을 사용합니다.', source:'학습용 밸류에이션 개념 · 기업 공시자료(DART)', url:'https://dart.fss.or.kr/' },
  '절대가치평가': { description:'다른 기업의 주가와 비교하지 않고, 이 기업이 앞으로 만들 현금흐름 자체를 추정해 현재가치로 바꾸는 방법입니다. 대표적으로 DCF가 있습니다.', source:'학습용 밸류에이션 개념 · 기업 공시자료(DART)', url:'https://dart.fss.or.kr/' },
  '밸류에이션': { description:'기업의 실적, 자산, 현금흐름을 바탕으로 기업 또는 주식의 적정가치를 추정하는 과정입니다. 좋은 기업이라도 가격이 너무 높으면 투자 매력은 달라질 수 있습니다.', source:'학습용 밸류에이션 개념 · 기업 공시자료(DART)', url:'https://dart.fss.or.kr/' },
  '멀티플': { description:'이익·매출·자산의 몇 배로 시장가치를 비교하는 배수입니다. 예를 들어 PER은 주가가 주당순이익의 몇 배인지를 뜻합니다.', source:'학습용 밸류에이션 개념 · 기업 공시자료(DART)', url:'https://dart.fss.or.kr/' },
  '적정가치': { description:'가정한 실적과 할인율, 비교기업 배수를 기준으로 계산한 가치 추정치입니다. 확정된 정답이 아니라 가정에 따라 달라지는 범위입니다.', source:'학습용 밸류에이션 개념 · 기업 공시자료(DART)', url:'https://dart.fss.or.kr/' },
  '목표주가': { description:'분석자가 정한 적정가치를 주식 한 주 기준 가격으로 나타낸 값입니다. 기간과 전제조건을 함께 확인해야 합니다.', source:'학습용 밸류에이션 개념 · 기업 공시자료(DART)', url:'https://dart.fss.or.kr/' },
  'SOTP': { description:'Sum of the Parts의 약자로, 사업부가 여러 개인 기업을 사업부별로 따로 평가한 뒤 합산하는 방법입니다.', source:'학습용 밸류에이션 개념 · 기업 공시자료(DART)', url:'https://dart.fss.or.kr/' },
  '정상화 이익': { description:'업황의 최고·최저점이나 일회성 손익을 제거하고, 장기적으로 유지 가능하다고 보는 대표 이익 수준입니다.', source:'학습용 밸류에이션 개념 · 기업 공시자료(DART)', url:'https://dart.fss.or.kr/' },
  '영구성장률': { description:'DCF에서 명시적 추정 기간 이후에도 현금흐름이 장기적으로 성장한다고 가정하는 비율입니다. 작은 차이도 가치에 큰 영향을 줄 수 있습니다.', source:'학습용 밸류에이션 개념 · 기업 공시자료(DART)', url:'https://dart.fss.or.kr/' },
  '안전마진': { description:'현재 주가가 추정 적정가치보다 얼마나 낮은지를 뜻하는 여유 폭입니다. 추정의 오차와 예상 밖 위험에 대비하는 개념입니다.', source:'학습용 밸류에이션 개념 · 기업 공시자료(DART)', url:'https://dart.fss.or.kr/' }
};
const technicalTermSources = {
  '엘리어트 파동': { source:'Alchemy Markets · 차트 예시', description:'엘리어트 파동은 시장 심리가 반복된다는 가정 아래, 가격 흐름을 추세 방향의 5개 추진 파동과 반대 방향의 3개 조정 파동으로 해석하는 방법입니다. 정답을 맞히는 도구가 아니라 가능한 시나리오를 세우는 보조 틀로 사용합니다.', image:'https://alchemymarkets.com/wp-content/uploads/2024/11/image-104.jpeg', links:[{label:'엘리어트 파동 차트 예시 출처',url:'https://alchemymarkets.com/education/guides/elliott-wave-theory/'}] },
  '무효화 조건': { source:'학습용 위험관리 개념', description:'분석 가설이 더 이상 유효하지 않다고 판단하는 사전 조건입니다. 파동 카운팅이나 지표 해석은 여러 경우의 수가 있으므로 반드시 함께 정합니다.', image:'/img/technical-elliott.svg', links:[{label:'엘리어트 파동 차트 예시 출처',url:'https://alchemymarkets.com/education/guides/elliott-wave-theory/'}] },
  '50선': { source:'학습용 기술지표 개념', description:'RSI의 0~100 범위 가운데 50 수준을 말합니다. 시장의 상승·하락 모멘텀이 어느 쪽에 더 기울었는지 보는 보조 기준입니다.', image:'/img/technical-indicator.svg', links:[{label:'RSI 차트 예시 출처',url:'https://www.valoralgo.com/blog/divergence-rsi'}] },
  '엘리어트파동이론': { source:'Alchemy Markets · 차트 예시', description:'가격 흐름을 추세 방향의 5개 추진 파동과 반대 방향의 3개 조정 파동으로 해석하는 이론입니다. 파동 수는 여러 방식으로 해석될 수 있으므로 하나의 가설로 다루고 무효화 가격을 함께 정합니다.', image:'https://alchemymarkets.com/wp-content/uploads/2024/11/image-104.jpeg', links:[{label:'엘리어트 파동 차트 예시 출처',url:'https://alchemymarkets.com/education/guides/elliott-wave-theory/'}] },
  '추진 파동': { source:'Alchemy Markets · 차트 예시', description:'엘리어트파동이론에서 큰 추세 방향으로 진행되는 1·2·3·4·5의 다섯 파동 구간입니다. 1·3·5파가 방향성을 만들고 2·4파는 조정으로 해석합니다.', image:'https://alchemymarkets.com/wp-content/uploads/2024/11/image-104.jpeg', links:[{label:'엘리어트 파동 차트 예시 출처',url:'https://alchemymarkets.com/education/guides/elliott-wave-theory/'}] },
  '조정 파동': { source:'Alchemy Markets · 차트 예시', description:'추진 파동 뒤에 기존 추세와 반대 방향으로 나타나는 A·B·C 세 파동 구간입니다. 조정의 깊이와 모양은 다양하므로 고정된 예측에 의존하지 않습니다.', image:'https://alchemymarkets.com/wp-content/uploads/2024/11/image-104.jpeg', links:[{label:'엘리어트 파동 차트 예시 출처',url:'https://alchemymarkets.com/education/guides/elliott-wave-theory/'}] },
  '파동 카운팅': { source:'Alchemy Markets · 차트 예시', description:'가격 움직임을 1~5, A~C 파동으로 번호를 붙여 해석하는 작업입니다. 여러 해석이 가능하므로 반드시 무효화 조건과 함께 기록해야 합니다.', image:'https://alchemymarkets.com/wp-content/uploads/2024/11/image-104.jpeg', links:[{label:'엘리어트 파동 차트 예시 출처',url:'https://alchemymarkets.com/education/guides/elliott-wave-theory/'}] },
  '다이버전스': { source:'ValorAlgo · RSI 차트 예시', description:'가격의 고점·저점 방향과 보조지표의 고점·저점 방향이 서로 다르게 나타나는 현상입니다. 모멘텀 약화를 알리는 보조 신호일 수 있지만 단독 매매 신호는 아닙니다.', image:'https://valortraders.s3.eu-west-2.amazonaws.com/media/1763318788898-rsi-divergence-example.webp', links:[{label:'RSI 다이버전스 차트 예시 출처',url:'https://www.valoralgo.com/blog/divergence-rsi'}] },
  '볼린저밴드': { source:'학습용 기술지표 개념', description:'이동평균선을 중심으로 가격 변동성을 반영한 상단·하단 밴드를 그리는 지표입니다. 밴드 폭의 확대·축소와 가격 위치를 함께 봅니다.', image:'/img/technical-indicator.svg', links:[{label:'기술지표 참고 자료',url:'https://www.valoralgo.com/blog/divergence-rsi'}] },
  '과매수': { source:'학습용 기술지표 개념', description:'RSI 같은 지표가 최근 상승 강도가 높다고 보여주는 구간입니다. 즉시 하락을 뜻하지 않으므로 추세와 가격 구조를 함께 확인합니다.', image:'https://valortraders.s3.eu-west-2.amazonaws.com/media/1763318788898-rsi-divergence-example.webp', links:[{label:'RSI 차트 예시 출처',url:'https://www.valoralgo.com/blog/divergence-rsi'}] },
  '과매도': { source:'학습용 기술지표 개념', description:'RSI 같은 지표가 최근 하락 강도가 높다고 보여주는 구간입니다. 즉시 반등을 보장하지 않으므로 지지선과 거래량을 함께 확인합니다.', image:'https://valortraders.s3.eu-west-2.amazonaws.com/media/1763318788898-rsi-divergence-example.webp', links:[{label:'RSI 차트 예시 출처',url:'https://www.valoralgo.com/blog/divergence-rsi'}] },
  '모멘텀': { source:'ValorAlgo · RSI 차트 예시', description:'가격이 상승 또는 하락하는 힘과 속도를 뜻합니다. RSI·MACD 같은 지표로 보조적으로 확인하며 가격 추세보다 늦을 수 있습니다.', image:'https://valortraders.s3.eu-west-2.amazonaws.com/media/1763318788898-rsi-divergence-example.webp', links:[{label:'RSI 차트 예시 출처',url:'https://www.valoralgo.com/blog/divergence-rsi'}] },
  '변동성': { source:'학습용 기술지표 개념', description:'가격이 일정 기간에 얼마나 크게 움직이는지를 뜻합니다. 변동성이 높을수록 손절 폭과 포지션 크기를 더 보수적으로 정할 필요가 있습니다.', image:'/img/technical-indicator.svg', links:[{label:'기술지표 참고 자료',url:'https://www.valoralgo.com/blog/divergence-rsi'}] },
  'RSI': { source:'ValorAlgo · RSI 차트 예시', description:'Relative Strength Index의 약자로, 최근 상승폭과 하락폭을 비교해 모멘텀을 0~100 범위로 나타내는 지표입니다.', image:'https://valortraders.s3.eu-west-2.amazonaws.com/media/1763318788898-rsi-divergence-example.webp', links:[{label:'RSI 차트 예시 출처',url:'https://www.valoralgo.com/blog/divergence-rsi'}] },
  'MACD': { source:'학습용 기술지표 개념', description:'Moving Average Convergence Divergence의 약자로, 서로 다른 이동평균선의 차이로 모멘텀 변화를 보는 지표입니다.', image:'/img/technical-indicator.svg', links:[{label:'기술지표 참고 자료',url:'https://www.valoralgo.com/blog/divergence-rsi'}] },
  '완성 조건': { source:'InvestingGoal · 차트 예시', description:'패턴이 단지 비슷하게 보이는 단계가 아니라, 넥라인·추세선 등 핵심 경계를 종가와 거래량으로 확인한 상태를 말합니다.', image:'https://img.investingoal.com/app/uploads/2024/11/How-Does-A-Double-Bottom-Pattern-Work-900x600.jpg', links:[{label:'패턴 완성 예시 출처',url:'https://investingoal.com/forex/terminology/chart-pattern/double-bottom/'}] },
  '지지 전환': { source:'Strike Money · 차트 예시', description:'이전에 저항이었던 가격대가 돌파 후 조정 과정에서 지지 역할을 하는 현상입니다. 한 번의 터치보다 종가와 거래량을 확인합니다.', image:'https://www.strike.money/wp-content/uploads/2024/03/How-to-identify-support-resistance-levels.jpg', links:[{label:'지지·저항 차트 예시 출처',url:'https://www.strike.money/technical-analysis/support-resistance'}] },
  '기존 추세': { source:'BacktestMarket · 차트 예시', description:'패턴이 나타나기 전 시장이 진행해 온 상승 또는 하락 흐름입니다. 반전 패턴은 기존 추세가 충분히 형성된 뒤에 해석하는 것이 일반적입니다.', image:'https://www.backtestmarket.com/media/wysiwyg/blog/uptrend.png', links:[{label:'추세 차트 예시 출처',url:'https://www.backtestmarket.com/blog/post/top-day-trading-strategies'}] },
  '패턴': { source:'InvestingGoal · 차트 예시', description:'가격 움직임이 반복적으로 만드는 모양입니다. 패턴은 미래를 보장하지 않으며 추세·거래량·위험 기준과 함께 사용합니다.', image:'https://img.investingoal.com/app/uploads/2024/11/How-Does-A-Double-Bottom-Pattern-Work-900x600.jpg', links:[{label:'패턴 차트 예시 출처',url:'https://investingoal.com/forex/terminology/chart-pattern/double-bottom/'}] },
  '차트 패턴': { source:'InvestingGoal · 차트 예시', description:'가격이 반복적으로 만드는 모양을 통해 시장 참여자의 매수·매도 균형 변화를 읽는 방법입니다. 패턴만으로 결론 내리지 않고 추세와 거래량을 함께 확인합니다.', image:'https://img.investingoal.com/app/uploads/2024/11/How-Does-A-Double-Bottom-Pattern-Work-900x600.jpg', links:[{label:'패턴 차트 예시 출처',url:'https://investingoal.com/forex/terminology/chart-pattern/double-bottom/'}] },
  '이중바닥': { source:'InvestingGoal · 차트 예시', description:'하락 뒤 비슷한 가격대의 저점이 두 번 형성되는 W자 모양의 패턴입니다. 두 저점 사이의 고점인 넥라인을 거래량과 함께 돌파하는지 확인합니다.', image:'https://img.investingoal.com/app/uploads/2024/11/How-Does-A-Double-Bottom-Pattern-Work-900x600.jpg', links:[{label:'이중바닥 차트 예시 출처',url:'https://investingoal.com/forex/terminology/chart-pattern/double-bottom/'}] },
  '컵앤핸들': { source:'학습용 차트 패턴 개념', description:'완만한 U자형 조정 뒤 짧은 눌림이 이어지는 모양을 말합니다. 패턴 형태보다 돌파 시 거래량과 손절 기준을 함께 정하는 것이 중요합니다.', image:'https://img.investingoal.com/app/uploads/2024/11/How-Does-A-Double-Bottom-Pattern-Work-900x600.jpg', links:[{label:'차트 패턴 학습 자료',url:'https://investingoal.com/forex/terminology/chart-pattern/double-bottom/'}] },
  '삼각수렴': { source:'학습용 차트 패턴 개념', description:'고점은 낮아지고 저점은 높아지며 가격 폭이 좁아지는 모양입니다. 위·아래 어느 방향으로 돌파하는지와 거래량 증가를 확인합니다.', image:'https://img.investingoal.com/app/uploads/2024/11/How-Does-A-Double-Bottom-Pattern-Work-900x600.jpg', links:[{label:'차트 패턴 학습 자료',url:'https://investingoal.com/forex/terminology/chart-pattern/double-bottom/'}] },
  '반전 패턴': { source:'InvestingGoal · 차트 예시', description:'기존 상승 또는 하락 추세가 바뀔 가능성을 보여주는 가격 구조입니다. 이중바닥처럼 패턴 완성 뒤의 돌파와 거래량 확인이 필요합니다.', image:'https://img.investingoal.com/app/uploads/2024/11/How-Does-A-Double-Bottom-Pattern-Work-900x600.jpg', links:[{label:'반전 패턴 차트 예시 출처',url:'https://investingoal.com/forex/terminology/chart-pattern/double-bottom/'}] },
  '캔들 몸통': { source:'FameEX · 차트 예시', description:'캔들에서 시가와 종가 사이의 굵은 부분입니다. 몸통의 방향과 길이는 해당 기간 매수·매도 우위와 가격 변화를 보여줍니다.', image:'https://static.fameex.com/20230227/33/673/tv4.png', links:[{label:'캔들 구조 예시 출처',url:'https://www.fameex.com/en-US/learning/candlestick-charts-101-a-comprehensive-guide-for-beginners'}] },
  '꼬리': { source:'FameEX · 차트 예시', description:'캔들 몸통 위·아래로 뻗은 가는 선으로, 해당 기간의 고가와 저가를 보여줍니다. 긴 꼬리는 그 가격대에서 매수·매도 공방이 컸음을 뜻할 수 있습니다.', image:'https://static.fameex.com/20230227/33/673/tv4.png', links:[{label:'캔들 구조 예시 출처',url:'https://www.fameex.com/en-US/learning/candlestick-charts-101-a-comprehensive-guide-for-beginners'}] },
  '캔들': { source:'FameEX · 차트 예시', description:'일정 기간의 시가·고가·저가·종가를 한 개의 막대로 보여주는 가격 표현 방식입니다. 한 개의 캔들보다 추세와 위치를 함께 해석합니다.', image:'https://static.fameex.com/20230227/33/673/tv4.png', links:[{label:'캔들 구조 예시 출처',url:'https://www.fameex.com/en-US/learning/candlestick-charts-101-a-comprehensive-guide-for-beginners'}] },
  '돌파 거래량': { source:'InvestingGoal · 차트 예시', description:'저항선이나 패턴 넥라인을 넘을 때 평소보다 증가한 거래량입니다. 돌파에 참여한 매수세가 충분한지 판단하는 보조 신호입니다.', image:'https://img.investingoal.com/app/uploads/2024/11/How-Does-A-Double-Bottom-Pattern-Work-900x600.jpg', links:[{label:'이중바닥 돌파 예시 출처',url:'https://investingoal.com/forex/terminology/chart-pattern/double-bottom/'}] },
  '돌파': { source:'InvestingGoal · 차트 예시', description:'가격이 중요한 저항선·지지선·패턴 경계를 넘어서는 움직임입니다. 장중 움직임보다 종가와 거래량으로 확인하는 습관이 필요합니다.', image:'https://img.investingoal.com/app/uploads/2024/11/How-Does-A-Double-Bottom-Pattern-Work-900x600.jpg', links:[{label:'패턴 돌파 예시 출처',url:'https://investingoal.com/forex/terminology/chart-pattern/double-bottom/'}] },
  '무효화 가격': { source:'InvestingGoal · 차트 예시', description:'분석한 패턴이나 매매 가설이 더 이상 유효하지 않다고 판단하는 가격입니다. 진입 전에 정해 위험을 제한하는 기준으로 사용합니다.', image:'https://img.investingoal.com/app/uploads/2024/11/How-Does-A-Double-Bottom-Pattern-Work-900x600.jpg', links:[{label:'패턴 위험관리 예시 출처',url:'https://investingoal.com/forex/terminology/chart-pattern/double-bottom/'}] },
  '추격매수': { source:'학습용 위험관리 개념', description:'가격이 급등한 뒤 뒤늦게 매수하는 행동입니다. 손절가가 멀어져 손익비가 나빠질 수 있으므로 눌림과 위험 기준을 먼저 점검합니다.', image:'https://img.investingoal.com/app/uploads/2024/11/How-Does-A-Double-Bottom-Pattern-Work-900x600.jpg', links:[{label:'패턴 위험관리 예시 출처',url:'https://investingoal.com/forex/terminology/chart-pattern/double-bottom/'}] },
  '손익비': { source:'학습용 위험관리 개념', description:'예상 수익 폭을 감수할 손실 폭으로 나눈 비율입니다. 같은 승률이라도 손익비가 낮으면 장기 성과가 나빠질 수 있습니다.', image:'https://img.investingoal.com/app/uploads/2024/11/How-Does-A-Double-Bottom-Pattern-Work-900x600.jpg', links:[{label:'패턴 위험관리 예시 출처',url:'https://investingoal.com/forex/terminology/chart-pattern/double-bottom/'}] },
  '추세 필터': { source:'BacktestMarket · 차트 예시', description:'현재 가격이 어느 방향의 흐름에 있는지 먼저 거르는 기준입니다. 이동평균선, 고점·저점 구조 등을 조합해 역추세 진입을 줄이는 데 사용합니다.', image:'https://www.backtestmarket.com/media/wysiwyg/blog/uptrend.png', links:[{label:'추세 차트 예시 출처',url:'https://www.backtestmarket.com/blog/post/top-day-trading-strategies'}] },
  '기준선': { source:'BacktestMarket · 차트 예시', description:'매매 판단을 일관되게 하기 위해 미리 정한 가격 또는 추세 기준입니다. 이동평균선, 지지·저항, 손절가 등이 기준선이 될 수 있습니다.', image:'https://www.backtestmarket.com/media/wysiwyg/blog/uptrend.png', links:[{label:'추세 차트 예시 출처',url:'https://www.backtestmarket.com/blog/post/top-day-trading-strategies'}] },
  '반전': { source:'PineScript Market · 차트 예시', description:'기존 상승 또는 하락 흐름이 반대 방향으로 바뀌는 움직임입니다. 한 번의 캔들보다 추세 구조, 거래량, 지지·저항 확인을 함께 봐야 합니다.', image:'https://pinescriptmarket.com/learn/technical-analysis/fibonacci-retracement/fibonacci-cover.png', links:[{label:'되돌림 차트 예시 출처',url:'https://pinescriptmarket.com/learn/technical-analysis/fibonacci-retracement'}] },
  '이탈': { source:'Strike Money · 차트 예시', description:'가격이 지지선·이동평균선 등 중요 기준 아래 또는 위로 벗어나는 것입니다. 종가 기준 이탈인지, 거래량이 동반됐는지를 확인합니다.', image:'https://www.strike.money/wp-content/uploads/2024/03/How-to-identify-support-resistance-levels.jpg', links:[{label:'지지·저항 차트 예시 출처',url:'https://www.strike.money/technical-analysis/support-resistance'}] },
  '진입': { source:'BacktestMarket · 차트 예시', description:'분석한 조건에 따라 매수 또는 매도 포지션을 시작하는 시점입니다. 진입가와 손절가, 목표가를 함께 정해 위험을 관리합니다.', image:'https://www.backtestmarket.com/media/wysiwyg/blog/uptrend.png', links:[{label:'추세 차트 예시 출처',url:'https://www.backtestmarket.com/blog/post/top-day-trading-strategies'}] },
  '가격': { source:'BacktestMarket · 차트 예시', description:'시장 참여자가 거래를 통해 형성한 현재 또는 과거의 거래 수준입니다. 기술적 분석에서는 가격의 방향, 고점·저점, 거래량 관계를 함께 봅니다.', image:'https://www.backtestmarket.com/media/wysiwyg/blog/uptrend.png', links:[{label:'추세 차트 예시 출처',url:'https://www.backtestmarket.com/blog/post/top-day-trading-strategies'}] },
  '지지': { source:'Strike Money · 차트 예시', description:'가격 하락 시 매수세가 유입될 가능성이 있는 가격대라는 뜻입니다. 한 번의 반등보다 반복 확인과 거래량을 함께 봅니다.', image:'https://www.strike.money/wp-content/uploads/2024/03/How-to-identify-support-resistance-levels.jpg', links:[{label:'지지·저항 차트 예시 출처',url:'https://www.strike.money/technical-analysis/support-resistance'}] },
  '저항': { source:'Strike Money · 차트 예시', description:'가격 상승 시 매도세가 강해질 가능성이 있는 가격대라는 뜻입니다. 돌파 여부와 돌파 후 지지 전환을 확인합니다.', image:'https://www.strike.money/wp-content/uploads/2024/03/How-to-identify-support-resistance-levels.jpg', links:[{label:'지지·저항 차트 예시 출처',url:'https://www.strike.money/technical-analysis/support-resistance'}] },
  '피보나치 되돌림': { source:'PineScript Market · 차트 예시', description:'상승 또는 하락이 한 차례 진행된 뒤, 되돌림이 멈출 가능성이 있는 비율 구간을 23.6%·38.2%·50%·61.8% 등으로 표시하는 도구입니다. 단독 신호가 아니라 지지·저항과 거래량을 함께 확인합니다.', image:'https://pinescriptmarket.com/learn/technical-analysis/fibonacci-retracement/fibonacci-cover.png', links:[{label:'되돌림 차트 예시 출처',url:'https://pinescriptmarket.com/learn/technical-analysis/fibonacci-retracement'}] },
  '이동평균선': { source:'BacktestMarket · 차트 예시', description:'일정 기간의 평균 가격을 선으로 이은 지표입니다. 단기선과 장기선의 위치, 가격이 평균선 위·아래에 있는지를 통해 추세를 보조적으로 판단합니다.', image:'https://www.backtestmarket.com/media/wysiwyg/blog/uptrend.png', links:[{label:'추세 차트 예시 출처',url:'https://www.backtestmarket.com/blog/post/top-day-trading-strategies'}] },
  '상승추세': { source:'BacktestMarket · 차트 예시', description:'고점과 저점이 이전보다 높아지는 가격 구조입니다. 추세가 이어지는지 보려면 고점뿐 아니라 조정 시 저점이 유지되는지도 확인합니다.', image:'https://www.backtestmarket.com/media/wysiwyg/blog/uptrend.png', links:[{label:'상승추세 차트 예시 출처',url:'https://www.backtestmarket.com/blog/post/top-day-trading-strategies'}] },
  '하락추세': { source:'BacktestMarket · 차트 예시', description:'고점과 저점이 이전보다 낮아지는 가격 구조입니다. 반등이 나와도 이전 고점을 넘지 못하는지 살펴봅니다.', image:'https://www.backtestmarket.com/media/wysiwyg/blog/uptrend.png', links:[{label:'추세 구조 차트 예시 출처',url:'https://www.backtestmarket.com/blog/post/top-day-trading-strategies'}] },
  '지지선': { source:'Strike Money · 차트 예시', description:'가격이 하락하다가 매수세가 유입돼 멈추거나 반등한 가격대입니다. 한 줄보다 일정 범위로 보고, 여러 번 확인된 구간과 거래량을 함께 봅니다.', image:'https://www.strike.money/wp-content/uploads/2024/03/How-to-identify-support-resistance-levels.jpg', links:[{label:'지지·저항 차트 예시 출처',url:'https://www.strike.money/technical-analysis/support-resistance'}] },
  '저항선': { source:'Strike Money · 차트 예시', description:'가격이 상승하다가 매도세가 강해져 멈추거나 되돌린 가격대입니다. 돌파 뒤 이 가격대가 지지로 바뀌는지 확인할 수 있습니다.', image:'https://www.strike.money/wp-content/uploads/2024/03/How-to-identify-support-resistance-levels.jpg', links:[{label:'지지·저항 차트 예시 출처',url:'https://www.strike.money/technical-analysis/support-resistance'}] },
  '갭': { source:'StockCharts ChartSchool · 차트 예시', description:'전일 종가와 다음 거래일 시가 사이에 가격이 비어 보이는 구간입니다. 장 마감 뒤의 뉴스나 주문 불균형으로 생길 수 있으며, 갭의 종류와 거래량을 함께 봅니다.', image:'https://i0.wp.com/stocksaim.com/wp-content/uploads/2021/12/what-is-Gap-up-and-gap-down-in-stock-market-.png?fit=1024%2C509&ssl=1', links:[{label:'갭 차트 예시 출처',url:'https://chartschool.stockcharts.com/table-of-contents/chart-analysis/gaps-and-gap-analysis'}] },
  '되돌림': { source:'PineScript Market · 차트 예시', description:'기존 추세와 반대 방향으로 일시 조정되는 움직임입니다. 추세가 끝난 반전인지, 추세 안에서의 조정인지는 지지·저항과 거래량으로 구분합니다.', image:'https://pinescriptmarket.com/learn/technical-analysis/fibonacci-retracement/fibonacci-cover.png', links:[{label:'되돌림 차트 예시 출처',url:'https://pinescriptmarket.com/learn/technical-analysis/fibonacci-retracement'}] },
  '추세선': { source:'BacktestMarket · 차트 예시', description:'상승추세에서는 저점들을, 하락추세에서는 고점들을 연결해 가격 방향을 시각화한 선입니다. 예측선이 아니라 현재 추세가 유지되는지 점검하는 기준선입니다.', image:'https://www.backtestmarket.com/media/wysiwyg/blog/uptrend.png', links:[{label:'추세선 차트 예시 출처',url:'https://www.backtestmarket.com/blog/post/top-day-trading-strategies'}] },
  '거래량': { source:'Swim Trading · 차트 예시', description:'일정 기간에 거래된 주식 수입니다. 가격 돌파나 이탈 때 거래량이 평소보다 늘었는지 보면 움직임의 참여 강도를 보조적으로 판단할 수 있습니다.', image:'https://www.swimtrading.com/wp-content/uploads/2020/10/AAPL-Gaps-1024x610.png', links:[{label:'거래량 차트 예시 출처',url:'https://www.swimtrading.com/the-5-most-reliable-bullish-continuation-candlestick-patterns-youll-love/'}] },
  '손절가': { source:'Strike Money · 차트 예시', description:'매매 가설이 틀렸다고 판단해 손실을 제한하기 위해 미리 정하는 가격입니다. 진입 후 임의로 낮추기보다 지지선 이탈 등 객관적 기준과 연결합니다.', image:'https://www.strike.money/wp-content/uploads/2024/03/How-to-identify-support-resistance-levels.jpg', links:[{label:'지지·저항 차트 예시 출처',url:'https://www.strike.money/technical-analysis/support-resistance'}] },
  '손절': { source:'Strike Money · 차트 예시', description:'정한 손절가에 도달했을 때 포지션을 정리해 추가 손실을 제한하는 위험관리 행동입니다.', image:'https://www.strike.money/wp-content/uploads/2024/03/How-to-identify-support-resistance-levels.jpg', links:[{label:'지지·저항 차트 예시 출처',url:'https://www.strike.money/technical-analysis/support-resistance'}] },
  '전고점': { source:'Strike Money · 차트 예시', description:'현재 시점보다 앞선 구간에서 형성된 중요한 고점 가격대입니다. 저항 후보가 되거나 돌파 뒤 지지 후보가 될 수 있습니다.', image:'https://www.strike.money/wp-content/uploads/2024/03/How-to-identify-support-resistance-levels.jpg', links:[{label:'지지·저항 차트 예시 출처',url:'https://www.strike.money/technical-analysis/support-resistance'}] },
  '고점': { source:'BacktestMarket · 차트 예시', description:'일정 기간 가격 움직임 중 상대적으로 높게 형성된 지점입니다. 이전 고점과 비교해 추세 구조를 판단합니다.', image:'https://www.backtestmarket.com/media/wysiwyg/blog/uptrend.png', links:[{label:'추세 차트 예시 출처',url:'https://www.backtestmarket.com/blog/post/top-day-trading-strategies'}] },
  '저점': { source:'BacktestMarket · 차트 예시', description:'일정 기간 가격 움직임 중 상대적으로 낮게 형성된 지점입니다. 상승추세에서는 저점이 높아지는지 확인합니다.', image:'https://www.backtestmarket.com/media/wysiwyg/blog/uptrend.png', links:[{label:'추세 차트 예시 출처',url:'https://www.backtestmarket.com/blog/post/top-day-trading-strategies'}] },
  '20일선': { source:'BacktestMarket · 차트 예시', description:'최근 20거래일 종가의 평균을 이은 단기 이동평균선입니다. 짧은 기간의 추세와 지지·저항 후보를 보는 보조 기준입니다.', image:'https://www.backtestmarket.com/media/wysiwyg/blog/uptrend.png', links:[{label:'이동평균 차트 예시 출처',url:'https://www.backtestmarket.com/blog/post/top-day-trading-strategies'}] },
  '60일선': { source:'BacktestMarket · 차트 예시', description:'최근 60거래일 종가의 평균을 이은 중기 이동평균선입니다. 단기선과의 위치 관계로 추세 변화를 보조적으로 확인합니다.', image:'https://www.backtestmarket.com/media/wysiwyg/blog/uptrend.png', links:[{label:'이동평균 차트 예시 출처',url:'https://www.backtestmarket.com/blog/post/top-day-trading-strategies'}] }
};
const sectorPracticeData = {
  power: { label:'전력', stocks:['HD현대일렉트릭','효성중공업','LS ELECTRIC'] },
  defense: { label:'방산', stocks:['한화에어로스페이스','LIG넥스원','한국항공우주'] },
  shipbuilding: { label:'조선', stocks:['HD한국조선해양','한화오션','삼성중공업'] }
};
const financialTermSources = {
  '재무제표': { description:'기업의 경영성과와 재무상태, 현금 흐름을 체계적으로 보여주는 보고서 묶음입니다. 손익계산서·재무상태표·현금흐름표를 함께 읽어야 합니다.' },
  '손익계산서': { description:'일정 기간에 발생한 매출, 비용, 이익을 보여줍니다. 얼마나 팔았고 얼마를 비용으로 썼으며 최종적으로 얼마나 벌었는지 확인합니다.' },
  '매출 성장률': { description:'전년 또는 전분기 대비 매출액이 얼마나 늘거나 줄었는지 나타내는 비율입니다. 성장의 속도와 지속성을 함께 봅니다.' },
  '매출 성장': { description:'제품 판매나 서비스 제공으로 발생하는 매출액이 늘어나는 흐름입니다. 가격 인상, 판매량 증가, 제품 믹스 개선의 원인을 구분합니다.' },
  '영업이익률': { description:'영업이익을 매출액으로 나눈 비율입니다. 본업에서 발생하는 수익성을 보여주며, 동종 기업과 비교할 때 유용합니다.' },
  '영업이익': { description:'매출액에서 매출원가와 판매관리비 등 본업에 필요한 비용을 뺀 이익입니다.' },
  '당기순이익': { description:'영업외손익과 법인세 등을 반영한 뒤 최종적으로 남은 이익입니다. 일회성 손익의 영향도 함께 확인해야 합니다.' },
  '순이익': { description:'일정 기간의 모든 수익과 비용, 세금을 반영하고 남은 최종 이익입니다.' },
  '매출액': { description:'기업이 상품·서비스를 제공해 벌어들인 총수익입니다. 매출 증가가 판매량·가격·환율 중 무엇에 따른 것인지 확인합니다.' },
  '이익률': { description:'이익을 매출액으로 나눈 비율입니다. 어떤 단계의 이익을 사용하는지에 따라 매출총이익률·영업이익률·순이익률로 나뉩니다.' },
  '이익': { description:'수익에서 비용을 차감하고 남은 금액입니다. 영업이익인지 순이익인지, 일회성 손익이 포함됐는지를 구분해야 합니다.' },
  '마진': { description:'매출에서 비용을 빼고 남는 비율 또는 금액을 말합니다. 매출총이익률·영업이익률·순이익률처럼 단계별로 볼 수 있습니다.' },
  '비용 구조': { description:'매출원가, 인건비, 판매비, 감가상각비처럼 비용이 어떤 항목으로 구성되고 매출 변화에 얼마나 민감한지 보여줍니다.' },
  '재무상태표': { description:'특정 시점의 자산·부채·자본을 보여줍니다. 기업이 무엇을 보유하고 얼마나 빚을 지며 자기자본이 얼마인지 확인합니다.' },
  '유동자산': { description:'현금, 매출채권, 재고처럼 일반적으로 1년 안에 현금화하거나 사용하는 자산입니다.' },
  '비유동자산': { description:'토지·건물·설비·장기투자자산처럼 1년을 넘어 장기간 보유·사용하는 자산입니다.' },
  '유동부채': { description:'매입채무·단기차입금처럼 일반적으로 1년 안에 상환해야 하는 부채입니다.' },
  '비유동부채': { description:'장기차입금·사채처럼 상환기일이 1년을 넘는 부채입니다.' },
  '자본': { description:'자산에서 부채를 뺀 순자산으로, 주주가 기업에 투자하고 기업이 축적한 몫을 뜻합니다.' },
  '부채비율': { description:'부채를 자기자본으로 나눈 비율입니다. 높을수록 자금조달 위험과 이자 부담을 추가로 점검해야 합니다.' },
  '유동비율': { description:'유동자산을 유동부채로 나눈 비율입니다. 1년 이내 갚아야 할 부채를 단기 자산으로 감당할 수 있는지 보는 지표입니다.' },
  '운전자본': { description:'영업활동에 필요한 유동자산에서 유동부채를 뺀 자금입니다. 매출채권과 재고가 늘면 현금이 묶일 수 있습니다.' },
  '현금 전환율': { description:'영업현금흐름을 순이익으로 나눈 비율입니다. 회계상 이익이 실제 현금 창출로 이어지는지 확인합니다.' },
  '현금흐름표': { description:'영업·투자·재무활동에 따라 실제 현금이 들어오고 나간 내역을 보여줍니다.' },
  '현금흐름': { description:'일정 기간 동안 실제 현금이 들어오고 나간 흐름입니다. 회계상 이익과 달리 현금의 실제 이동을 반영합니다.' },
  '투자현금흐름': { description:'설비·유가증권 등 장기자산의 취득·처분에서 발생한 현금흐름입니다. 성장 투자 시 보통 현금 유출로 나타납니다.' },
  '재무현금흐름': { description:'차입·상환, 유상증자, 배당처럼 자본과 부채를 조달·상환하면서 생기는 현금흐름입니다.' },
  '기초현금': { description:'해당 회계기간이 시작될 때 보유한 현금 및 현금성자산 잔액입니다.' },
  '기말현금': { description:'해당 회계기간이 끝날 때 보유한 현금 및 현금성자산 잔액입니다.' },
  '영업현금흐름': { description:'기업의 주된 영업활동에서 발생한 실제 현금 흐름입니다. 순이익의 질을 판단하는 핵심 지표입니다.' },
  '매출채권': { description:'제품이나 서비스를 먼저 제공하고 아직 받지 못한 대금입니다. 과도하게 늘면 매출의 현금화가 늦어졌을 수 있습니다.' },
  '재고': { description:'판매 또는 생산을 위해 보유한 상품·제품·원재료입니다. 재고가 빠르게 늘면 수요 둔화나 재고평가 위험을 확인합니다.' }
};
const orderedMetricTerms = Object.entries(fullMetricNames).sort(([a], [b]) => b.length - a.length);
const orderedMarketChecks = Object.keys(marketCheckSources);
const orderedStrategyConcepts = Object.keys(strategyConceptSources);
const orderedValuationTerms = Object.keys(valuationTermSources).sort((a, b) => b.length - a.length);
const orderedTechnicalTerms = Object.keys(technicalTermSources).sort((a, b) => b.length - a.length);
const orderedFinancialTerms = Object.keys(financialTermSources).sort((a, b) => b.length - a.length);
function readableMetric(value) {
  const text = String(value);
  return fullMetricNames[text] ?? text;
}
function expandMetricTerms(text) {
  return orderedMetricTerms
    .reduce((expanded, [term, fullName], index) => expanded.replace(new RegExp(term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), `<button type="button" class="metric-link" data-metric-index="${index}">${fullName}<span>ⓘ</span></button>`), String(text));
}
function valuationTermLink(term) { return `<button type="button" class="metric-link" data-valuation-term-index="${orderedValuationTerms.indexOf(term)}">${term}<span>ⓘ</span></button>`; }
function expandValuationTerms(text) {
  const masked = orderedValuationTerms.reduce((value, term, index) => value.replace(new RegExp(term, 'g'), `@@VAL${index}@@`), String(text));
  return masked.replace(/@@VAL(\d+)@@/g, (_, index) => valuationTermLink(orderedValuationTerms[Number(index)]));
}
function expandEducationalTerms(text) { return expandValuationTerms(expandMetricTerms(text)); }
function technicalTermLink(term) { return `<button type="button" class="metric-link" data-technical-term-index="${orderedTechnicalTerms.indexOf(term)}">${term}<span>ⓘ</span></button>`; }
function expandTechnicalTerms(text) {
  const masked = orderedTechnicalTerms.reduce((value, term, index) => value.replace(new RegExp(term, 'g'), `@@TECH${index}@@`), String(text));
  return masked.replace(/@@TECH(\d+)@@/g, (_, index) => technicalTermLink(orderedTechnicalTerms[Number(index)]));
}
function marketCheckLink(term) { return `<button type="button" class="metric-link" data-market-check-index="${orderedMarketChecks.indexOf(term)}">${term}<span>ⓘ</span></button>`; }
function strategyConceptLink(term) { return `<button type="button" class="metric-link" data-strategy-concept-index="${orderedStrategyConcepts.indexOf(term)}">${term}<span>ⓘ</span></button>`; }
function financialTermLink(term) { return `<button type="button" class="metric-link" data-financial-term-index="${orderedFinancialTerms.indexOf(term)}">${term}<span>ⓘ</span></button>`; }
function expandFinancialTerms(text) {
  const masked = orderedFinancialTerms.reduce((value, term, index) => value.replace(new RegExp(term, 'g'), `@@FIN${index}@@`), String(text));
  return masked.replace(/@@FIN(\d+)@@/g, (_, index) => financialTermLink(orderedFinancialTerms[Number(index)]));
}
function companyComparisonExample(item) {
  if (item.id !== 'industry-practice') return '';
  return `<section class="company-case"><h4>비교 예시 · 삼성전자 vs SK하이닉스</h4><p>반도체 산업을 분석할 때 두 회사를 같은 질문으로 비교하는 학습용 프레임입니다. 아래 내용은 매수·매도 의견이 아닙니다.</p><div class="company-case-grid"><article class="company-case-card"><strong>삼성전자</strong><p>메모리 반도체뿐 아니라 System LSI와 Foundry를 함께 보유한 포트폴리오를 기준으로, 사업 다각화와 각 부문의 수익성을 분리해 확인합니다.</p></article><article class="company-case-card"><strong>SK하이닉스</strong><p>DRAM·NAND와 고부가 메모리 제품을 중심으로, AI 메모리 수요·제품 믹스·고객 인증이 실적에 미치는 영향을 점검합니다.</p></article></div><ul class="company-case-check"><li><b>제품·수요:</b> HBM, 서버 DRAM, NAND/eSSD 등 고부가 제품 비중과 고객 수요를 비교합니다.</li><li><b>공급·투자:</b> CAPEX, 생산능력 확대 시점, 재고일수로 공급 증가와 가격 변동 위험을 점검합니다.</li><li><b>수익성:</b> 매출 성장률, 영업이익률, 영업현금흐름이 함께 개선되는지 확인합니다.</li><li><b>경쟁력:</b> 공정·패키징 기술, 고객 다변화, 대체 공급사 진입 가능성을 포터의 5 Forces로 연결합니다.</li></ul><div class="company-case-links"><a href="https://images.samsung.com/is/content/samsung/assets/global/ir/docs/2025_3Q_Interim_Report.pdf" target="_blank" rel="noopener noreferrer">삼성전자 공식 사업보고서 ↗</a><a href="https://news.skhynix.com/sk-hynix-announces-fy25-financial-results/" target="_blank" rel="noopener noreferrer">SK하이닉스 공식 실적자료 ↗</a></div></section>`;
}
function valuationComparisonExample(item) {
  if (item.id !== 'fundamental-valuation') return '';
  return expandEducationalTerms(`<section class="valuation-case"><h4>밸류에이션 예시 · 삼성전자 vs SK하이닉스</h4><p>두 회사의 적정가치를 같은 숫자 하나로 비교하기보다 사업구조와 메모리 업황 민감도를 반영해 가정을 다르게 두는 학습용 사례입니다. 실제 목표주가나 투자 의견이 아닙니다.</p><div class="company-case-grid"><article class="company-case-card"><strong>삼성전자</strong><p>메모리 외에 System LSI·Foundry와 완제품 사업이 있어, 전체 PER 하나보다 사업부별 이익과 현금흐름을 나누어 보는 SOTP(사업부 합산가치) 관점을 함께 검토합니다.</p></article><article class="company-case-card"><strong>SK하이닉스</strong><p>메모리 업황과 고부가 제품의 수요·가격 변화가 실적에 크게 반영될 수 있으므로, 한 해 이익보다 정상화 이익과 CAPEX 사이클을 함께 가정합니다.</p></article></div><div class="valuation-case-methods"><article class="valuation-method"><strong>PER 비교</strong><p>EPS 성장률, 메모리 업황 위치, 사업 포트폴리오를 맞춘 뒤 동종 기업 대비 멀티플을 비교합니다.</p></article><article class="valuation-method"><strong>EV/EBITDA 비교</strong><p>감가상각과 CAPEX 비중이 큰 반도체 산업에서는 부채를 포함한 기업가치 기준을 함께 확인합니다.</p></article><article class="valuation-method"><strong>DCF</strong><p>HBM·서버 수요, CAPEX, FCF, WACC, 영구성장률을 보수·기준·낙관 시나리오로 나눠 가치 범위를 만듭니다.</p></article></div><ul class="company-case-check"><li><b>비교 원칙:</b> 삼성전자의 다각화와 SK하이닉스의 메모리 민감도를 같은 멀티플 하나로 단순 비교하지 않습니다.</li><li><b>핵심 가정:</b> 평균판매가격(ASP), 출하량, 제품 믹스, CAPEX와 재고 변화를 실적 추정에 반영합니다.</li><li><b>결론:</b> 현재가와 가치 범위의 차이뿐 아니라 가정이 틀릴 때의 하방 위험도 함께 기록합니다.</li></ul><div class="company-case-links"><a href="https://images.samsung.com/is/content/samsung/assets/global/ir/docs/2025_3Q_Interim_Report.pdf" target="_blank" rel="noopener noreferrer">삼성전자 공식 사업보고서 ↗</a><a href="https://news.skhynix.com/sk-hynix-announces-fy25-financial-results/" target="_blank" rel="noopener noreferrer">SK하이닉스 공식 실적자료 ↗</a></div></section>`);
}
function elliottWaveExplanation(item) {
  if (item.id !== 'technical-indicators') return '';
  return `<section class="valuation-case"><h4>${technicalTermLink('엘리어트 파동')} 쉽게 이해하기</h4><p>엘리어트 파동은 가격이 한 방향으로만 움직이지 않고, 전진과 조정을 반복한다는 관점입니다. 미래를 확정하는 예측법이 아니라 여러 시나리오 중 하나를 점검하는 보조 도구로 사용합니다.</p><div class="valuation-case-methods"><article class="valuation-method"><strong>①~⑤ 추진 파동</strong><p>큰 추세 방향으로 전진하는 다섯 구간입니다. 보통 1·3·5파는 추세 방향, 2·4파는 중간 조정으로 해석합니다.</p></article><article class="valuation-method"><strong>A·B·C 조정 파동</strong><p>추진 파동 뒤에 나타나는 반대 방향의 세 구간입니다. 조정의 깊이와 기간은 일정하지 않습니다.</p></article><article class="valuation-method"><strong>실전 적용 원칙</strong><p>파동 번호보다 지지·저항, 거래량, 손절가를 우선합니다. 예상과 다르면 미리 정한 무효화 조건에서 가설을 수정합니다.</p></article></div></section>`;
}
function theoryText(item, text, index) {
  if (item.id === 'macro-practice' && index === 0) return `① ${marketCheckLink('성장(산업생산·고용)')} ② ${marketCheckLink('물가')} ③ ${marketCheckLink('금리')} ④ ${marketCheckLink('환율·원자재')} 순으로 체크합니다.`;
  if (item.id === 'industry-competitiveness' && index === 1) return `${strategyConceptLink('포터의 5 Forces')}: 신규 진입, 대체재, 공급자, 구매자, 기존 경쟁 강도를 함께 분석합니다.`;
  if (item.id === 'fundamental-financials') return expandFinancialTerms(text);
  if (item.id === 'technical-trend') return expandTechnicalTerms(text);
  if (item.id === 'technical-pattern') return expandTechnicalTerms(text);
  if (item.id === 'technical-indicators') return expandTechnicalTerms(text);
  return expandEducationalTerms(text);
}
function toneFrom(value) { return value >= 70 ? '긍정' : value >= 45 ? '중립' : '주의'; }
function toneClass(tone) { return tone === '긍정' ? 'positive' : tone === '주의' ? 'caution' : 'neutral'; }
function signalLight(tone, metric, observation) {
  const cls = toneClass(tone);
  const active = cls === 'positive' ? 'positive' : cls === 'neutral' ? 'neutral' : 'caution';
  return `<div class="signal-display"><div class="traffic-light" aria-label="${tone} 신호"><i class="signal-bulb positive ${active === 'positive' ? 'active' : ''}"></i><i class="signal-bulb neutral ${active === 'neutral' ? 'active' : ''}"></i><i class="signal-bulb caution ${active === 'caution' ? 'active' : ''}"></i></div><div><div class="signal-title ${cls}">${tone} 신호</div><div class="signal-detail">${readableMetric(metric)}</div><div class="signal-observation">핵심 관측값 · ${observation}</div></div></div>`;
}

function renderMenu() {
  document.getElementById('analysis-menu').innerHTML = lessons.map(group => `<div class="academy-menu-group"><div class="academy-menu-title"><i class="fa-solid ${group.icon}"></i>${group.group}</div>${group.items.map(item => `<button class="academy-menu-item ${item.id === activeLesson ? 'active' : ''}" data-lesson="${item.id}">${item.title}</button>`).join('')}</div>`).join('');
  document.querySelectorAll('[data-lesson]').forEach(button => button.addEventListener('click', () => selectLesson(button.dataset.lesson)));
}
function bars(result, selected = null) { return `<div class="result-bars">${result.bars.map(([label,value])=>{ const isSelected=!selected || selected.includes(label), tone=toneFrom(value), cls=toneClass(tone); return `<div class="result-row ${isSelected ? '' : 'inactive'}"><span>${readableMetric(label)}</span><div class="result-track"><div class="result-fill" style="width:${isSelected ? value : 0}%"></div></div><span class="signal-chip ${isSelected ? cls : 'inactive'}"><i></i>${isSelected ? tone : '제외'}</span></div>`; }).join('')}</div>`; }
function panel(n, title, inner, full='') { return `<article class="academy-panel ${full}"><div class="academy-panel-head"><span class="academy-panel-num">0${n}</span><h3>${title}</h3></div><div class="academy-panel-body">${inner}</div></article>`; }
function simulation(item) {
  if (item.id === 'fundamental-financials') return financialSheetSimulation();
  if (item.id === 'fundamental-practice') return companySelectionPractice();
  if (item.id === 'technical-practice') return technicalPracticeWorkspace();
  const conditions = item.result.bars.map(([label], index) => `<label class="sim-check"><span class="sim-check-title"><input type="checkbox" data-sim-condition data-condition-index="${index}" value="${label}" ${index < 2 ? 'checked' : ''}>${readableMetric(label)}</span><input class="sim-range" data-sim-condition-range="${index}" type="range" min="1" max="5" value="3"><span class="sim-mini-scale"><span>보수적</span><span>중립</span><span>적극적</span></span></label>`).join('');
  return `<p class="sim-intro">여러 조건을 함께 선택해보세요. <b>교집합 방식</b>으로 선택한 모든 조건이 만족될 때만 긍정 신호로 해석합니다.</p>
    <div class="sim-controls">
      <div class="sim-condition-block"><span class="sim-condition-title">복합 분석 조건 · 각 척도의 강도를 따로 설정하세요</span><div class="sim-condition-list">${conditions}</div></div>
    </div>
    <button class="sim-action" type="button" data-sim-run><i class="fa-solid fa-play"></i> 시뮬레이션 실행</button>
    <div class="sim-output" data-sim-output><strong>조건을 선택하세요.</strong> 실행하면 이 주제의 핵심 지표를 간단히 해석합니다.</div>`;
}
function technicalPracticeWorkspace() {
  return `<p class="selection-intro">아래 순서대로 직접 찾은 종목의 차트를 보며 기술적 분석 계획을 작성하세요. <b>빈 앞 항목을 건너뛰고 다음 칸을 누르면 작성 이유와 예시를 다시 안내합니다.</b></p><div class="memo-grid"><div class="memo-field"><label>종목명·티커 <span>분석 대상</span></label><textarea data-technical-note="company" data-technical-step="0" placeholder="예: 삼성전자 / 005930 / KOSPI"></textarea><p class="memo-example">예시: 삼성전자(005930), KOSPI</p></div><div class="memo-field"><label>차트 주기·자료 링크 <span>일봉·주봉·참고 URL</span></label><textarea data-technical-note="source" data-technical-step="1" placeholder="예: 일봉·주봉 / TradingView 링크"></textarea><p class="memo-example">예시: 일봉·주봉 확인, TradingView 차트와 DART 실적 공시</p></div><div class="memo-field full"><label>① 종목 선택 근거 <span>거래대금·변동성·시장 관심도</span></label><textarea data-technical-note="selection" data-technical-step="2" placeholder="예: 최근 거래대금 증가와 반도체 업황 회복 기대"></textarea><p class="memo-example">예시: 최근 20일 평균보다 거래대금이 늘었고, 반도체 업황 회복 기대가 있어 차트 흐름을 관찰한다.</p></div><div class="memo-field"><label>② 추세·지지·저항 <span>고점·저점 구조와 가격대</span></label><textarea data-technical-note="trend" data-technical-step="3" placeholder="예: 상승 추세 / 지지 70,000원 / 저항 75,000원"></textarea><p class="memo-example">예시: 저점이 높아지는 상승 추세. 70,000원은 지지, 75,000원은 전고점 저항으로 본다.</p></div><div class="memo-field"><label>③ 패턴·캔들·지표 <span>RSI·MACD·이동평균 등</span></label><textarea data-technical-note="signal" data-technical-step="4" placeholder="예: 20일선 상회, RSI 58, 거래량 증가"></textarea><p class="memo-example">예시: 종가가 20일 이동평균선 위에 있고 RSI 58로 과열은 아니다. 저항 돌파 시 거래량을 확인한다.</p></div><div class="memo-field"><label>④ 진입·목표·손절 계획 <span>가격과 근거</span></label><textarea data-technical-note="plan" data-technical-step="5" placeholder="예: 진입 72,000원 / 목표 76,000원 / 손절 69,500원"></textarea><p class="memo-example">예시: 72,000원 돌파 후 안착 시 진입, 76,000원 전고점 부근을 목표로 하고 69,500원 이탈 시 손절한다.</p></div><div class="memo-field"><label>⑤ 반대 시나리오·재검토 조건 <span>가설 무효화 기준</span></label><textarea data-technical-note="risk" data-technical-step="6" placeholder="예: 69,500원 종가 이탈·거래량 감소 시 재검토"></textarea><p class="memo-example">예시: 69,500원 아래에서 종가가 마감되거나 돌파 뒤 거래량이 줄면 계획을 중단하고 다음 실적 발표 후 재검토한다.</p></div></div><div class="company-case-links" style="margin-top:14px;"><a href="https://data.krx.co.kr/" target="_blank" rel="noopener noreferrer">KRX 정보데이터시스템 ↗</a><a href="https://kr.tradingview.com/" target="_blank" rel="noopener noreferrer">TradingView 차트 ↗</a><a href="https://dart.fss.or.kr/" target="_blank" rel="noopener noreferrer">DART 공시 ↗</a></div><button class="sim-action" type="button" data-technical-practice-review><i class="fa-solid fa-pen-to-square"></i> 기술적 분석 메모 점검</button><div class="sim-output" data-technical-practice-output><strong>분석 종목과 근거를 기록하세요.</strong> 각 항목을 채우면 매매계획의 작성 상태를 확인합니다.</div>`;
}
function companySelectionPractice() {
  return `<p class="selection-intro">관심 섹터와 대표 종목을 고른 뒤, 아래 다섯 항목을 직접 작성해보세요. 숫자를 그대로 옮기기보다 <b>왜 이 기업을 선택했고 어떤 가정으로 가치를 판단하는지</b> 기록하는 실습입니다.</p><div class="sector-selector">${Object.entries(sectorPracticeData).map(([key, sector], index) => `<button type="button" class="sector-select-btn ${index === 0 ? 'active' : ''}" data-sector-select="${key}">${sector.label}</button>`).join('')}</div><div id="sector-stock-list" class="stock-choice-list"></div><div class="memo-grid"><div class="memo-field full"><label>① 기업 선택 이유 <span>산업 내 위치와 투자 가설</span></label><textarea data-practice-note="thesis" placeholder="예: 전력기기 교체 수요와 수주 증가가 실적에 어떻게 반영될지 작성"></textarea></div><div class="memo-field"><label>② 확인할 핵심 지표 <span>매출·수주·마진·CAPEX 등</span></label><textarea data-practice-note="metrics" placeholder="확인할 지표와 기준을 작성"></textarea></div><div class="memo-field"><label>③ ${valuationTermLink('밸류에이션')} 근거 <span>비교기업·멀티플·DCF 가정</span></label><textarea data-practice-note="valuation" placeholder="사용할 평가 방법과 가정을 작성"></textarea></div><div class="memo-field"><label>④ 위험 요인 <span>가정이 틀릴 수 있는 조건</span></label><textarea data-practice-note="risk" placeholder="업황, 원가, 수주, 환율 등 위험을 작성"></textarea></div><div class="memo-field"><label>⑤ 결론과 확인 일정 <span>다음 실적 전 확인할 항목</span></label><textarea data-practice-note="conclusion" placeholder="판단 보류·추적·재검토 기준을 작성"></textarea></div></div><button class="sim-action" type="button" data-practice-review><i class="fa-solid fa-pen-to-square"></i> 작성 내용 점검</button><div class="sim-output" data-practice-output><strong>섹터와 종목을 선택하세요.</strong> 다섯 항목을 작성하면 실습 메모의 완성도를 확인합니다.</div>`;
}
function renderSectorStocks(sectorKey) {
  const sector = sectorPracticeData[sectorKey];
  const list = document.getElementById('sector-stock-list');
  if (!list || !sector) return;
  const savedStock = lessonLearningState('fundamental-practice').fields['practice-stock'];
  list.innerHTML = sector.stocks.map((stock, index) => `<label class="stock-choice"><input type="radio" name="practice-stock" value="${stock}" ${savedStock ? (savedStock === stock ? 'checked' : '') : (index === 0 ? 'checked' : '')}>${stock}</label>`).join('');
}
function financialSheetSimulation() {
  const row = (label, reference, key, placeholder, allowNegative = false) => `<tr><td>${financialTermLink(label)}</td><td class="sheet-ref">${reference}</td><td><input class="sheet-input" data-finance="${key}" type="number" ${allowNegative ? '' : 'min="0"'} placeholder="${placeholder}"></td></tr>`;
  const sheet = rows => `<div class="sheet-wrap"><table class="finance-sheet"><thead><tr><th>항목</th><th>2024 기준</th><th>2025 입력값</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  return `<p class="sheet-intro">세 가지 재무제표를 각각 입력해보세요. 노란색 칸의 금액 관계가 맞지 않으면 이유를 모달로 안내합니다. <b>단위: 억원</b></p><div class="finance-sheet-tabs"><button class="finance-sheet-tab active" data-finance-tab="income">손익계산서</button><button class="finance-sheet-tab" data-finance-tab="balance">재무상태표</button><button class="finance-sheet-tab" data-finance-tab="cash">현금흐름표</button></div><section class="finance-sheet-panel active" data-finance-panel="income">${sheet(row('매출액','1,110','revenue','예: 1,200') + row('영업이익','142','operating','예: 180') + row('당기순이익','112','net','예: 142') + row('영업현금흐름','151','cashflow','예: 165'))}<p class="sheet-note">매출 대비 이익률과 순이익 대비 영업현금흐름을 검증합니다.</p></section><section class="finance-sheet-panel" data-finance-panel="balance">${sheet(row('유동자산','780','current_assets','예: 850') + row('비유동자산','1,120','noncurrent_assets','예: 1,180') + row('유동부채','510','current_liabilities','예: 530') + row('비유동부채','590','noncurrent_liabilities','예: 620') + row('자본','800','equity','예: 880'))}<p class="sheet-note">자산 = 부채 + 자본의 기본 등식과 유동자산·유동부채 관계를 검증합니다.</p></section><section class="finance-sheet-panel" data-finance-panel="cash">${sheet(row('영업현금흐름','151','cf_operating','예: 165',true) + row('투자현금흐름','-170','cf_investing','예: -180',true) + row('재무현금흐름','80','cf_financing','예: 95',true) + row('기초현금','120','cash_begin','예: 181') + row('기말현금','181','cash_end','예: 261'))}<p class="sheet-note">기초현금 + 영업·투자·재무 현금흐름 = 기말현금의 관계를 검증합니다.</p></section><button class="sim-action" type="button" data-finance-run><i class="fa-solid fa-table-cells-large"></i> 재무제표 정합성 시뮬레이션</button><div class="sheet-result" data-finance-summary><div class="sheet-result-item">손익계산서<strong>입력 대기</strong></div><div class="sheet-result-item">재무상태표<strong>입력 대기</strong></div><div class="sheet-result-item">현금흐름표<strong>입력 대기</strong></div></div><div class="sim-output" data-sim-output><strong>한 시트 이상 완성해보세요.</strong> 완성된 시트부터 금액 정합성을 확인합니다.</div>`;
}
function clamp(value) { return Math.min(99, Math.max(1, value)); }
function financeValidationIssues(values) {
  const growth = (values.revenue / 1110 - 1) * 100;
  const conversion = values.cashflow / values.net;
  const issues = [];
  if (values.operating >= values.revenue) issues.push('<b>영업이익이 매출액 이상입니다.</b> 영업이익은 일반적으로 매출액에서 매출원가와 판매관리비를 차감한 금액입니다. 숫자 단위 또는 입력 열을 다시 확인하세요.');
  if (values.net >= values.revenue) issues.push('<b>당기순이익이 매출액 이상입니다.</b> 대규모 영업외이익·일회성 이익이 아니라면 일반적인 관계와 다릅니다. 순이익과 매출액 입력값을 재확인하세요.');
  if (conversion < 0.8) issues.push('<b>영업현금흐름이 순이익보다 많이 낮습니다.</b> 매출채권·재고 증가로 현금이 묶였거나, 입력한 영업현금흐름이 맞는지 확인이 필요합니다.');
  if (growth > 50 && values.operating / values.revenue < 0.05) issues.push('<b>매출은 급증했지만 영업이익률이 낮습니다.</b> 원가 상승, 판촉비 증가, 신규 투자 비용 등의 원인이 있는지 확인하세요.');
  return issues;
}
function openFinanceValidationModal(issues) {
  const modal = document.getElementById('finance-validation-modal');
  document.getElementById('finance-modal-details').innerHTML = issues.map(issue => `<li>${issue}</li>`).join('');
  modal.classList.add('open'); modal.setAttribute('aria-hidden','false'); document.body.style.overflow='hidden';
}
function closeFinanceValidationModal() { const modal=document.getElementById('finance-validation-modal'); modal?.classList.remove('open'); modal?.setAttribute('aria-hidden','true'); document.body.style.overflow=''; }
const technicalPracticeGuides = [
  { title:'종목명·티커를 먼저 입력하세요', description:'어떤 종목의 차트를 보는지 정해야 이후의 가격대와 기술 신호를 같은 기준으로 기록할 수 있습니다.', example:'<b>작성 예시</b>삼성전자(005930), KOSPI' },
  { title:'차트 주기·자료를 기록하세요', description:'일봉·주봉처럼 본 차트의 시간 단위와 확인한 자료를 남기면 나중에 같은 화면에서 분석을 재검토할 수 있습니다.', example:'<b>작성 예시</b>일봉과 주봉을 확인했고, TradingView 차트 및 DART 분기보고서를 참고했다.' },
  { title:'종목 선택 근거를 먼저 적으세요', description:'단순히 관심 종목이라서가 아니라 거래대금, 업황, 뉴스 등 관찰할 이유를 한 문장으로 남겨보세요.', example:'<b>작성 예시</b>최근 20일 평균보다 거래대금이 늘고 반도체 업황 회복 기대가 있어 관찰 대상으로 선정했다.' },
  { title:'추세·지지·저항을 먼저 정리하세요', description:'진입 계획을 세우기 전에 가격이 어느 방향으로 움직이는지와 중요한 가격대를 확인해야 합니다.', example:'<b>작성 예시</b>저점이 높아지는 상승 추세이며, 70,000원은 지지·75,000원은 전고점 저항으로 본다.' },
  { title:'패턴·캔들·지표 신호를 확인하세요', description:'가격 구조를 보완하는 신호를 적습니다. 지표 하나만으로 판단하지 말고 추세·거래량과 함께 봅니다.', example:'<b>작성 예시</b>종가가 20일선 위에 있고 RSI 58로 과열은 아니다. 저항 돌파 시 거래량 증가를 확인한다.' },
  { title:'진입·목표·손절 가격을 먼저 정하세요', description:'매수 전 손실을 제한할 가격과 기대 수익 가격을 함께 정해야 계획의 손익비를 검토할 수 있습니다.', example:'<b>작성 예시</b>72,000원 돌파 후 안착 시 진입, 76,000원을 목표로 하고 69,500원 이탈 시 손절한다.' }
];
let pendingTechnicalGuideFocus = null;
function openTechnicalGuideModal(index, focusTarget) {
  const guide = technicalPracticeGuides[index];
  if (!guide) return;
  pendingTechnicalGuideFocus = focusTarget;
  document.getElementById('technical-guide-title').textContent = guide.title;
  document.getElementById('technical-guide-description').textContent = guide.description;
  document.getElementById('technical-guide-example').innerHTML = guide.example;
  const modal = document.getElementById('technical-guide-modal');
  modal.classList.add('open'); modal.setAttribute('aria-hidden','false'); document.body.style.overflow='hidden';
}
function closeTechnicalGuideModal() { const modal=document.getElementById('technical-guide-modal'); modal?.classList.remove('open'); modal?.setAttribute('aria-hidden','true'); document.body.style.overflow=''; const target=pendingTechnicalGuideFocus; pendingTechnicalGuideFocus=null; target?.focus(); }
function readFinanceSection(keys) {
  const raw = keys.map(key => document.querySelector(`[data-finance="${key}"]`)?.value ?? '');
  if (!raw.some(value => value.trim() !== '')) return { state:'empty' };
  if (!raw.every(value => value.trim() !== '')) return { state:'partial' };
  const values = Object.fromEntries(keys.map((key, index) => [key, Number(raw[index])]));
  return { state:Object.values(values).every(Number.isFinite) ? 'complete' : 'invalid', values };
}
function runFinancialSimulation(item) {
  const income = readFinanceSection(['revenue','operating','net','cashflow']);
  const balance = readFinanceSection(['current_assets','noncurrent_assets','current_liabilities','noncurrent_liabilities','equity']);
  const cash = readFinanceSection(['cf_operating','cf_investing','cf_financing','cash_begin','cash_end']);
  const sections = [['손익계산서',income],['재무상태표',balance],['현금흐름표',cash]];
  if (!sections.some(([, section]) => section.state === 'complete')) { document.querySelector('[data-sim-output]').innerHTML = '<strong>한 시트를 모두 입력하세요.</strong><br>각 시트의 노란색 칸을 모두 채우면 해당 시트부터 검증합니다.'; return; }
  const issues = [];
  const summary = [];
  if (income.state === 'complete') {
    const values = income.values;
    if (Object.values(values).some(value => value <= 0)) issues.push('<b>손익계산서 입력값을 확인하세요.</b> 매출액·이익·영업현금흐름은 이 실습에서 0보다 큰 금액으로 입력합니다.');
    else {
      const growth = (values.revenue / 1110 - 1) * 100, margin = values.operating / values.revenue * 100, conversion = values.cashflow / values.net;
      issues.push(...financeValidationIssues(values));
      summary.push(`<div class="sheet-result-item">손익계산서<strong>${issues.length ? '검토 필요' : '정합성 양호'}</strong><span>성장 ${growth.toFixed(1)}% · 이익률 ${margin.toFixed(1)}%</span></div>`);
    }
  } else summary.push(`<div class="sheet-result-item">손익계산서<strong>${income.state === 'partial' ? '입력 미완료' : '입력 대기'}</strong></div>`);
  if (balance.state === 'complete') {
    const v = balance.values, assets = v.current_assets + v.noncurrent_assets, funding = v.current_liabilities + v.noncurrent_liabilities + v.equity, difference = assets - funding;
    if (Object.values(v).some(value => value < 0)) issues.push('<b>재무상태표에 음수 금액이 있습니다.</b> 자산·부채·자본의 입력 단위와 부호를 확인하세요.');
    if (Math.abs(difference) > 1) issues.push(`<b>자산과 부채·자본의 합이 ${Math.abs(difference).toLocaleString()}억원 차이 납니다.</b> 재무상태표는 자산 = 부채 + 자본이 성립해야 합니다.`);
    const liquidity = v.current_liabilities ? v.current_assets / v.current_liabilities : 0;
    summary.push(`<div class="sheet-result-item">재무상태표<strong>${Math.abs(difference) <= 1 ? '정합성 양호' : '검토 필요'}</strong><span>유동비율 ${(liquidity * 100).toFixed(1)}%</span></div>`);
  } else summary.push(`<div class="sheet-result-item">재무상태표<strong>${balance.state === 'partial' ? '입력 미완료' : '입력 대기'}</strong></div>`);
  if (cash.state === 'complete') {
    const v = cash.values, expected = v.cash_begin + v.cf_operating + v.cf_investing + v.cf_financing, difference = v.cash_end - expected;
    if (v.cash_begin < 0 || v.cash_end < 0) issues.push('<b>기초·기말 현금이 음수입니다.</b> 현금 잔액 입력값과 단위를 다시 확인하세요.');
    if (Math.abs(difference) > 1) issues.push(`<b>기말현금이 현금흐름 합계와 ${Math.abs(difference).toLocaleString()}억원 차이 납니다.</b> 기초현금 + 영업·투자·재무 현금흐름 = 기말현금 관계를 확인하세요.`);
    summary.push(`<div class="sheet-result-item">현금흐름표<strong>${Math.abs(difference) <= 1 ? '정합성 양호' : '검토 필요'}</strong><span>기말현금 차이 ${difference.toLocaleString()}억원</span></div>`);
  } else summary.push(`<div class="sheet-result-item">현금흐름표<strong>${cash.state === 'partial' ? '입력 미완료' : '입력 대기'}</strong></div>`);
  const tone = issues.length === 0 ? '긍정' : issues.length === 1 ? '중립' : '주의';
  document.querySelector('[data-finance-summary]').innerHTML = summary.join('');
  document.querySelector('[data-sim-output]').innerHTML = `<strong>${issues.length ? '입력값 재확인 필요' : '금액 변동 정합성 양호'} · ${tone} 신호</strong><br>${issues.length ? '재확인이 필요한 이유를 모달에서 안내합니다.' : '매출·이익·현금흐름의 기본 관계가 자연스럽습니다.'}`;
  document.querySelector('[data-sim-insight]').innerHTML = `<strong>재무제표 변동 검증 결과입니다.</strong> 입력을 완료한 시트의 금액 관계를 함께 확인했습니다.`;
  document.querySelector('.signal-display').outerHTML = signalLight(tone, '재무제표 정합성', `완료 시트: ${sections.filter(([, section]) => section.state === 'complete').map(([name]) => name).join(', ')}`);
  document.querySelector('.result-bars')?.remove();
  document.querySelector('.result-note').innerHTML = issues.length ? `<strong>검토 항목:</strong> ${issues.join('<br>')}` : '<strong>정합성 양호:</strong> 손익계산서·재무상태표·현금흐름표의 관계가 기본 등식에 맞습니다.';
  if (issues.length) openFinanceValidationModal(issues);
}
function escapeHtml(value) { return String(value).replace(/[&<>'"]/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' })[char]); }
function jsonValueType(value) { return value === null ? 'null' : Array.isArray(value) ? 'array' : typeof value; }
function jsonParseErrorLocation(source, error) {
  const position = Number(error.message.match(/position (\d+)/i)?.[1]);
  if (!Number.isFinite(position)) return '';
  const before = source.slice(0, position);
  return ` (${before.split('\n').length}행 ${position - before.lastIndexOf('\n')}열 부근)`;
}
function inspectJsonConsistency(data) {
  const stats = { objects:0, arrays:0, values:0, maxDepth:0 };
  const issues = [];
  const addIssue = message => { if (issues.length < 20) issues.push(message); };
  const visit = (value, path, depth) => {
    stats.maxDepth = Math.max(stats.maxDepth, depth);
    if (Array.isArray(value)) {
      stats.arrays += 1;
      const objectRows = value.filter(row => row && typeof row === 'object' && !Array.isArray(row));
      if (objectRows.length && objectRows.length !== value.length) addIssue(`${path} 배열에 객체와 다른 자료형이 함께 있습니다.`);
      if (objectRows.length > 1) {
        const referenceKeys = Object.keys(objectRows[0]);
        const referenceSet = new Set(referenceKeys);
        objectRows.slice(1).forEach((row, index) => {
          const rowPath = `${path}[${value.indexOf(row)}]`;
          const keys = Object.keys(row);
          const missing = referenceKeys.filter(key => !(key in row));
          const extra = keys.filter(key => !referenceSet.has(key));
          if (missing.length) addIssue(`${rowPath}: 기준 객체에 있는 필드 ${missing.map(key => `“${key}”`).join(', ')}가 없습니다.`);
          if (extra.length) addIssue(`${rowPath}: 기준 객체에 없는 필드 ${extra.map(key => `“${key}”`).join(', ')}가 있습니다.`);
          keys.filter(key => referenceSet.has(key)).forEach(key => {
            const expected = jsonValueType(objectRows[0][key]);
            const actual = jsonValueType(row[key]);
            if (expected !== actual) addIssue(`${rowPath}.${key}: 자료형이 기준(${expected})과 다릅니다. 현재 ${actual}`);
          });
        });
      }
      value.forEach((child, index) => visit(child, `${path}[${index}]`, depth + 1));
      return;
    }
    if (value && typeof value === 'object') {
      stats.objects += 1;
      Object.entries(value).forEach(([key, child]) => visit(child, `${path}.${key}`, depth + 1));
      return;
    }
    stats.values += 1;
  };
  visit(data, '$', 0);
  return { stats, issues };
}
function renderJsonCheckResult(result) {
  const target = document.querySelector('[data-json-check-result]');
  if (!target) return;
  const { stats, issues } = result;
  const status = issues.length ? '검토 필요' : '정합성 양호';
  target.innerHTML = `<div class="json-check-status ${issues.length ? 'has-issues' : 'is-valid'}"><i class="fa-solid ${issues.length ? 'fa-triangle-exclamation' : 'fa-circle-check'}"></i><div><strong>${status}</strong><span>${issues.length ? `${issues.length}개의 구조 불일치를 확인하세요.` : 'JSON 형식과 탐지 가능한 객체 구조가 일관됩니다.'}</span></div></div><div class="json-check-stats"><span>객체 <b>${stats.objects}</b></span><span>배열 <b>${stats.arrays}</b></span><span>값 <b>${stats.values}</b></span><span>최대 깊이 <b>${stats.maxDepth}</b></span></div><div class="json-check-issues">${issues.length ? `<ol>${issues.map(issue => `<li>${escapeHtml(issue)}</li>`).join('')}</ol>` : '<p>배열 안의 객체 필드와 자료형을 비교했으며, 불일치가 발견되지 않았습니다.</p>'}</div>`;
}
function runJsonConsistencyCheck() {
  const input = document.querySelector('[data-json-consistency-input]');
  if (!input) return;
  const source = input.value.trim();
  if (!source) {
    renderJsonCheckResult({ stats:{ objects:0, arrays:0, values:0, maxDepth:0 }, issues:['검사할 JSON 내용을 입력하세요.'] });
    return;
  }
  try {
    renderJsonCheckResult(inspectJsonConsistency(JSON.parse(source)));
  } catch (error) {
    renderJsonCheckResult({ stats:{ objects:0, arrays:0, values:0, maxDepth:0 }, issues:[`JSON 문법 오류${jsonParseErrorLocation(source, error)}: ${error.message}`] });
  }
}
function renderJsonConsistencyChecker() {
  const saved = lessonLearningState('json-consistency').fields.jsonSource ?? '';
  document.getElementById('analysis-breadcrumb').innerHTML = '';
  document.getElementById('analysis-hero').innerHTML = `<div class="academy-hero-content"><span class="academy-hero-tag"><i class="fa-solid fa-shield-halved"></i> ANALYSIS TOOL</span><h2>JSON 정합성검사</h2><p>JSON 데이터를 붙여넣고 문법, 배열 내 객체의 필드 누락·추가, 자료형 불일치를 확인하세요.</p></div>`;
  document.getElementById('analysis-panels').innerHTML = `<article class="academy-panel full json-consistency-panel"><div class="academy-panel-head"><span class="academy-panel-num"><i class="fa-solid fa-code"></i></span><h3>JSON 입력 및 정합성 검사</h3></div><div class="academy-panel-body"><div class="json-consistency-workspace"><section class="json-input-column"><div class="json-column-head"><label for="json-consistency-input">JSON 내용</label><span>붙여넣기 후 검사 버튼을 누르세요</span></div><textarea id="json-consistency-input" class="json-consistency-input" data-json-consistency-input spellcheck="false" placeholder='[\n  {"ticker": "005930", "price": 71000}\n]'></textarea></section><section class="json-result-column"><div class="json-column-head"><strong>정합성 검사</strong><span>브라우저에서만 검사됩니다</span></div><div class="json-check-result" data-json-check-result><p>JSON을 입력한 뒤 검사를 실행하세요.</p></div></section></div><div class="json-check-actions"><button class="sim-action" type="button" data-json-check-run><i class="fa-solid fa-shield-halved"></i> 정합성 검사 실행</button><button class="json-format-action" type="button" data-json-format><i class="fa-solid fa-align-left"></i> JSON 정렬</button></div></div></article>`;
  const input = document.querySelector('[data-json-consistency-input]');
  input.value = saved;
  input.addEventListener('input', () => {
    lessonLearningState('json-consistency').fields.jsonSource = input.value;
    saveLearningState();
  });
  document.querySelector('[data-json-check-run]').addEventListener('click', runJsonConsistencyCheck);
  document.querySelector('[data-json-format]').addEventListener('click', () => {
    try { input.value = JSON.stringify(JSON.parse(input.value), null, 2); input.dispatchEvent(new Event('input')); runJsonConsistencyCheck(); }
    catch { runJsonConsistencyCheck(); }
  });
}
const pineTemplates = {
  crossover: `//@version=5
strategy("MA Crossover Practice", overlay=true, initial_capital=10000000)
fast = ta.sma(close, 20)
slow = ta.sma(close, 60)
longCondition = ta.crossover(fast, slow)
if longCondition
    strategy.entry("Long", strategy.long)
if ta.crossunder(fast, slow)
    strategy.close("Long")
plot(fast, color=color.blue)
plot(slow, color=color.orange)`,
  rsi: `//@version=5
strategy("RSI Reversal Practice", overlay=true, initial_capital=10000000)
rsiValue = ta.rsi(close, 14)
if ta.crossover(rsiValue, 30)
    strategy.entry("Long", strategy.long)
if ta.crossunder(rsiValue, 70)
    strategy.close("Long")
plot(rsiValue, "RSI", color=color.purple)`
};
function formatPercent(value) { return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`; }
function calculateQuantBacktest(strategy, cost) {
  const patterns = { crossover:[1.8,-2.1,3.4,0.6,2.9,-1.6,1.5,2.6,-0.8,3.1,1.2,2.3], momentum:[2.4,-1.8,4.2,1.1,3.7,-2.4,2.8,3.1,-1.3,4.0,1.6,2.9], reversal:[1.6,-1.2,2.1,0.9,1.8,-0.7,1.2,1.7,-0.5,2.0,0.8,1.5] };
  const returns = patterns[strategy].map(value => value - cost * 2.4); let equity=100, peak=100, mdd=0;
  returns.forEach(value => { equity *= 1 + value / 100; peak=Math.max(peak,equity); mdd=Math.min(mdd,(equity / peak - 1) * 100); });
  const mean=returns.reduce((a,b)=>a+b,0)/returns.length, deviation=Math.sqrt(returns.reduce((sum,value)=>sum+(value-mean)**2,0)/(returns.length-1));
  return { returns, equity, cagr:(Math.pow(equity/100,1/(returns.length/12))-1)*100, mdd, sharpe:(mean*12-3)/(deviation*Math.sqrt(12)), win:returns.filter(value=>value>0).length/returns.length*100 };
}
function renderQuantBacktest() {
  const strategy=document.querySelector('[data-quant-field="strategy"]')?.value ?? 'crossover', cost=Number(document.querySelector('[data-quant-field="cost"]')?.value ?? .15), data=calculateQuantBacktest(strategy,cost), labels=['1월','2월','3월','4월','5월','6월','7월','8월','9월','10월','11월','12월'];
  const rows=data.returns.map((value,index)=>`<div class="quant-return-bar"><span>${labels[index]}</span><i class="${value < 0 ? 'loss' : ''}" style="width:${Math.min(100,Math.abs(value)*22)}%"></i><b>${formatPercent(value)}</b></div>`).join('');
  document.querySelector('[data-quant-backtest-result]').innerHTML=`<div class="quant-metric-grid"><div><span>누적 수익률</span><strong>${formatPercent(data.equity-100)}</strong></div><div><span>CAGR</span><strong>${formatPercent(data.cagr)}</strong></div><div><span>MDD</span><strong class="down">${data.mdd.toFixed(1)}%</strong></div><div><span>Sharpe ratio</span><strong>${data.sharpe.toFixed(2)}</strong></div><div><span>승률</span><strong>${data.win.toFixed(0)}%</strong></div></div><div class="quant-return-chart">${rows}</div><p class="quant-result-note"><b>해석:</b> MDD는 고점 대비 최대 하락폭이며 작을수록 낙폭 관리가 좋습니다. Sharpe ratio는 변동성 1단위당 초과수익으로, 비용·슬리피지를 반영해 과대평가를 줄여야 합니다.</p>`;
}
function renderSeasonality() {
  const type=document.querySelector('[data-quant-field="seasonality"]')?.value ?? 'month';
  const data=type === 'weekday' ? [['월요일',-0.18,51],['화요일',0.12,54],['수요일',0.21,56],['목요일',0.08,53],['금요일',-0.05,50]] : [['1월',1.9,58],['2월',0.7,54],['3월',1.1,55],['4월',0.3,52],['5월',-0.4,48],['6월',-0.8,45],['7월',0.6,53],['8월',-0.3,49],['9월',-1.1,43],['10월',1.5,57],['11월',2.1,60],['12월',2.8,63]];
  const best=[...data].sort((a,b)=>b[1]-a[1])[0], worst=[...data].sort((a,b)=>a[1]-b[1])[0];
  document.querySelector('[data-seasonality-result]').innerHTML=`<div class="seasonality-summary"><span>가장 강한 구간 <b>${best[0]} ${formatPercent(best[1])}</b></span><span>가장 약한 구간 <b>${worst[0]} ${formatPercent(worst[1])}</b></span></div><div class="seasonality-table">${data.map(([label,average,win])=>`<div><b>${label}</b><span class="seasonality-track"><i class="${average < 0 ? 'loss' : ''}" style="width:${Math.abs(average)*25}%"></i></span><strong>${formatPercent(average)}</strong><small>승률 ${win}%</small></div>`).join('')}</div><p class="quant-result-note">표본의 평균 수익률과 승률은 학습용 예시입니다. 연말 랠리·월별·요일 효과는 시장·기간에 따라 달라지므로, 여러 기간과 비용을 포함해 재검증한 뒤 가설로만 사용하세요.</p>`;
}
function checkPineScript() {
  const code=document.querySelector('[data-quant-field="pine-code"]')?.value ?? '', tests=[['버전 선언',/\/\/\@version=5/.test(code)],['strategy 선언',/\bstrategy\s*\(/.test(code)],['진입 규칙',/strategy\.entry\s*\(/.test(code)],['청산/손절 규칙',/strategy\.(close|exit)\s*\(/.test(code)]], passed=tests.filter(([,ok])=>ok).length;
  document.querySelector('[data-pine-result]').innerHTML=`<div class="pine-status ${passed === tests.length ? 'valid' : ''}"><b>${passed === tests.length ? '구조 점검 통과' : `${passed}/4 항목 확인`}</b><span>이 도구는 TradingView 실행 전 전략의 필수 구조를 빠르게 확인하는 학습용 점검기입니다.</span></div><ul class="pine-check-list">${tests.map(([label,ok])=>`<li class="${ok ? 'ok' : ''}"><i class="fa-solid ${ok ? 'fa-circle-check' : 'fa-circle-xmark'}"></i>${label}</li>`).join('')}</ul>`;
}
function renderQuantDay5() {
  const state=lessonLearningState('quant-day5').fields;
  document.getElementById('analysis-breadcrumb').innerHTML = '<span>퀀트 학습</span><i class="fa-solid fa-chevron-right"></i><strong>데이터 활용 모델링</strong>';
  document.getElementById('analysis-hero').innerHTML = `<div class="academy-hero-content"><span class="academy-hero-tag"><i class="fa-solid fa-flask"></i> DAY 5 PRACTICE</span><h2>데이터 활용 퀀트 모델링</h2><p>성과 지표를 해석하고, 계절성 가설을 검증하며, Pine Script 전략의 뼈대를 직접 작성합니다.</p></div>`;
  document.getElementById('analysis-panels').innerHTML = `<article class="academy-panel full quant-panel"><div class="academy-panel-head"><span class="academy-panel-num">01</span><h3>백테스트 성과 지표 실습</h3></div><div class="academy-panel-body"><p class="academy-summary">전략·거래비용을 바꿔 <b>CAGR, MDD, Sharpe ratio, 승률</b>이 함께 어떻게 달라지는지 확인하세요. 수익률만 높고 MDD가 큰 전략은 실제 운용 난도가 높을 수 있습니다.</p><div class="quant-controls"><label>전략<select class="sim-select" data-quant-field="strategy"><option value="crossover">이동평균 교차</option><option value="momentum">모멘텀</option><option value="reversal">평균회귀</option></select></label><label>왕복 거래비용(%)<input class="sim-select" type="number" min="0" max="2" step="0.05" value="${state['quant:cost'] ?? '.15'}" data-quant-field="cost"></label><button class="sim-action" type="button" data-quant-backtest>백테스트 계산</button></div><div data-quant-backtest-result class="quant-work-result">조건을 설정하고 계산하세요.</div><div class="quant-improve"><b>개선 방향</b><span>① 비용·슬리피지 반영 ② 상승/하락 국면 분리 ③ Out-of-sample 검증 ④ MDD 한도와 포지션 크기 규칙을 함께 설계</span></div></div></article><article class="academy-panel quant-panel"><div class="academy-panel-head"><span class="academy-panel-num">02</span><h3>주식 시장 계절성 탐색</h3></div><div class="academy-panel-body"><p class="academy-summary">연말 랠리, 월별 효과, 요일 효과는 예측이 아니라 <b>검증할 가설</b>입니다. 기준을 바꿔 평균 수익률과 승률을 비교하세요.</p><label class="quant-select-label">분석 기준<select class="sim-select" data-quant-field="seasonality"><option value="month">월별 효과 · 연말 랠리 포함</option><option value="weekday">요일 효과</option></select></label><button class="sim-action" type="button" data-quant-seasonality>계절성 비교</button><div data-seasonality-result class="quant-work-result">분석 기준을 선택하세요.</div></div></article><article class="academy-panel quant-panel"><div class="academy-panel-head"><span class="academy-panel-num">03</span><h3>TradingView Pine Script 기초</h3></div><div class="academy-panel-body"><p class="academy-summary">아래 코드를 수정해 진입·청산 규칙을 만들어 보세요. 구조 점검 후 TradingView Pine Editor에서 실제 차트 백테스트를 실행할 수 있습니다.</p><div class="pine-toolbar"><select class="sim-select" data-pine-template><option value="crossover">이동평균 교차 템플릿</option><option value="rsi">RSI 반전 템플릿</option></select><a href="/trade/pine-guide.html" class="pine-guide-link">기존 Pine 가이드 열기 <i class="fa-solid fa-arrow-up-right-from-square"></i></a></div><textarea class="pine-editor" data-quant-field="pine-code" spellcheck="false">${state['quant:pine-code'] ?? pineTemplates.crossover}</textarea><button class="sim-action" type="button" data-pine-check>전략 구조 점검</button><div data-pine-result class="quant-work-result">코드를 수정한 뒤 점검하세요.</div></div></article>`;
  restoreTrackedFields('quant-day5');
  document.querySelector('[data-quant-backtest]').addEventListener('click', renderQuantBacktest); document.querySelector('[data-quant-seasonality]').addEventListener('click', renderSeasonality); document.querySelector('[data-pine-check]').addEventListener('click', checkPineScript);
  document.querySelector('[data-pine-template]').addEventListener('change', event => { const editor=document.querySelector('[data-quant-field="pine-code"]'); editor.value=pineTemplates[event.target.value]; editor.dispatchEvent(new Event('input')); });
}
function quantEscape(value) { return String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[char]); }
function quantTable(rows, columns) {
  if (!rows?.length) return '<p class="quant-db-empty">조회 결과가 없습니다.</p>';
  return `<div class="quant-db-table-wrap"><table class="quant-db-table"><thead><tr>${columns.map(([key,label]) => `<th>${label}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${columns.map(([key]) => `<td>${quantEscape(typeof row[key] === 'number' ? row[key].toLocaleString(undefined,{maximumFractionDigits:4}) : row[key])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}
function quantSql(kind) {
  const queries={
    market:`SELECT symbol, trade_time, open, high, low, close, volume, adjusted_close\nFROM market_data WHERE symbol = :symbol\nORDER BY trade_time DESC LIMIT :limit;`,
    signal:`WITH ma AS (SELECT trade_time, adjusted_close,\n AVG(adjusted_close) OVER (ORDER BY trade_time ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) fast_ma,\n AVG(adjusted_close) OVER (ORDER BY trade_time ROWS BETWEEN 49 PRECEDING AND CURRENT ROW) slow_ma FROM market_data WHERE symbol = :symbol)\nSELECT *, CASE WHEN fast_ma > slow_ma THEN 'BUY' ELSE 'SELL' END signal FROM ma;`,
    trades:`SELECT trade_id, strategy_id, symbol, trade_time, side, price, quantity, fee, slippage, pnl\nFROM trade_logs ORDER BY trade_id DESC LIMIT 50;`
  }; return queries[kind];
}
async function loadQuantData(kind='market') {
  const symbol=document.querySelector('[data-quant-db-symbol]').value.trim().toUpperCase() || '005930';
  const result=document.querySelector('[data-quant-db-result]'); const sql=document.querySelector('[data-quant-db-sql]');
  result.innerHTML='PostgreSQL에서 조회 중…'; sql.textContent=quantSql(kind);
  try {
    const url=kind === 'market' ? `/api/quant/market-data?symbol=${encodeURIComponent(symbol)}&limit=40` : kind === 'signal' ? `/api/quant/signals?symbol=${encodeURIComponent(symbol)}&fast=20&slow=50&limit=80` : '/api/quant/results';
    const response=await fetch(url); const payload=await response.json(); if (!response.ok) throw new Error(payload.message || '조회 실패');
    if (kind === 'market') result.innerHTML=quantTable(payload.rows,[['symbol','종목'],['trade_time','시간'],['open','시가'],['high','고가'],['low','저가'],['close','종가'],['volume','거래량']]);
    else if (kind === 'signal') result.innerHTML=quantTable(payload.rows,[['trade_time','시간'],['adjusted_close','수정종가'],['fast_ma','MA20'],['slow_ma','MA50'],['signal','신호']]);
    else result.innerHTML=quantTable(payload.trades,[['trade_id','ID'],['strategy_id','전략'],['symbol','종목'],['trade_time','시간'],['side','구분'],['price','체결가'],['quantity','수량'],['pnl','손익']]);
  } catch (error) { result.innerHTML=`<p class="quant-db-error">${quantEscape(error.message)}. PostgreSQL 컨테이너와 QUANT_DATABASE_URL을 확인하세요.</p>`; }
}
async function runDatabaseBacktest() {
  const symbol=document.querySelector('[data-quant-db-symbol]').value.trim().toUpperCase() || '005930';
  const output=document.querySelector('[data-quant-db-backtest]'); output.textContent='백테스트 실행 및 거래 로그 저장 중…';
  try {
    const response=await fetch('/api/quant/backtests',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbol,fast:20,slow:50,quantity:10,feeRate:.00015,slippage:.0005})});
    const data=await response.json(); if (!response.ok) throw new Error(data.message || '실행 실패');
    output.innerHTML=`<strong>전략 #${data.strategyId} 저장 완료</strong> · 체결 ${data.tradeCount}건 · 실현 손익 ${Number(data.realizedPnl).toLocaleString()} · 수익률 ${data.totalReturn}%<br><small>${data.message}</small>`;
  } catch (error) { output.innerHTML=`<span class="quant-db-error">${quantEscape(error.message)}</span>`; }
}
async function renderQuantDatabase() {
  document.getElementById('analysis-breadcrumb').innerHTML='<span>분석 도구</span><i class="fa-solid fa-chevron-right"></i><strong>PostgreSQL 퀀트 랩</strong>';
  document.getElementById('analysis-hero').innerHTML='<div class="academy-hero-content"><span class="academy-hero-tag"><i class="fa-solid fa-database"></i> POSTGRESQL QUANT</span><h2>시계열 데이터 · SQL · 백테스트</h2><p>파티션된 OHLCV 데이터에서 이동평균 시그널을 계산하고, 거래 로그와 성과 결과를 PostgreSQL에 남깁니다.</p></div>';
  document.getElementById('analysis-panels').innerHTML=`<article class="academy-panel full quant-db-panel"><div class="academy-panel-head"><span class="academy-panel-num">01</span><h3>데이터 탐색 및 SQL</h3></div><div class="academy-panel-body"><div class="quant-db-controls"><label>종목 코드<input class="sim-select" data-quant-db-symbol value="005930" maxlength="20"></label><button class="sim-action" type="button" data-quant-db-load="market">OHLCV 조회</button><button class="sim-action" type="button" data-quant-db-load="signal">MA 시그널</button><button class="sim-action" type="button" data-quant-db-load="trades">거래 로그</button></div><p class="quant-db-note">허용된 읽기 전용 템플릿만 실행합니다. 값은 바인딩하므로 화면에서 임의 SQL을 실행하지 않습니다.</p><pre class="quant-db-sql" data-quant-db-sql></pre><div class="quant-db-result" data-quant-db-result>종목과 조회 유형을 선택하세요.</div></div></article><article class="academy-panel full quant-db-panel"><div class="academy-panel-head"><span class="academy-panel-num">02</span><h3>DB 기록형 이동평균 백테스트</h3></div><div class="academy-panel-body"><p class="academy-summary">MA 20/50 교차를 신호로 사용하고 수수료 0.015%, 슬리피지 0.05%, 10주 기준으로 실행합니다. 결과는 <code>strategies</code>, <code>trade_logs</code>, <code>performance_metrics</code>에 저장됩니다.</p><button class="sim-action quant-db-run" type="button" data-quant-db-run>백테스트 실행 후 결과 저장</button><div class="quant-db-backtest" data-quant-db-backtest>아직 실행하지 않았습니다.</div></div></article>`;
  document.querySelectorAll('[data-quant-db-load]').forEach(button => button.addEventListener('click', () => loadQuantData(button.dataset.quantDbLoad)));
  document.querySelector('[data-quant-db-run]').addEventListener('click', runDatabaseBacktest);
  try { const response=await fetch('/api/quant/overview'); const data=await response.json(); if (response.ok) document.querySelector('[data-quant-db-result]').innerHTML=`<p class="quant-db-overview">연결됨 · OHLCV <b>${Number(data.market_rows).toLocaleString()}</b>건 · 전략 <b>${data.strategy_count}</b>개 · 거래 로그 <b>${data.trade_count}</b>건 · ${quantEscape((data.symbols || []).join(', '))}</p>`; } catch (_) {}
}
function renderLesson() {
  if (activeLesson === 'quant-day5') { renderQuantDay5(); return; }
  if (activeLesson === 'json-consistency') { renderJsonConsistencyChecker(); return; }
  const item = lessonMap[activeLesson];
  document.getElementById('analysis-breadcrumb').innerHTML = '';
  document.getElementById('analysis-hero').innerHTML = `<div class="academy-hero-content"><h2>${item.title}</h2><div class="learning-progress" aria-label="전체 학습 데이터 저장 진행률"><div class="learning-progress-copy"><span>전체 학습 진행률</span><strong data-learning-progress-label>전체 저장 데이터 0%</strong></div><div class="learning-progress-track"><span data-learning-progress-bar></span></div></div></div>`;
  const expandText = item.id === 'fundamental-financials' ? expandFinancialTerms : ['technical-trend','technical-pattern','technical-indicators'].includes(item.id) ? expandTechnicalTerms : expandEducationalTerms;
  const explanation = `<p class="academy-summary">${expandText(item.description)}</p><ul class="academy-list">${item.theory.map((x,index)=>`<li>${theoryText(item, x, index)}</li>`).join('')}</ul>${companyComparisonExample(item)}${valuationComparisonExample(item)}${elliottWaveExplanation(item)}<div class="academy-tip">💡 <b>학습 포인트</b> · ${expandText(item.tip)}</div><div class="sim-flow" data-sim-insight>시뮬레이션을 실행하면 선택한 조건이 이 설명과 결과에 함께 반영됩니다.</div>`;
  const practice = simulation(item);
  const initialTone = toneFrom(Math.round(item.result.bars.reduce((sum, [, value]) => sum + value, 0) / item.result.bars.length));
  const resultText = ['technical-trend','technical-pattern','technical-indicators'].includes(item.id) ? expandTechnicalTerms : expandEducationalTerms;
  const result = `${signalLight(initialTone, item.result.label, item.result.value)}${['fundamental-financials','technical-practice'].includes(item.id) ? '' : bars(item.result)}<p class="result-note">${resultText(item.result.note)}</p>`;
  document.getElementById('analysis-panels').innerHTML = panel(1,'설명',explanation) + panel(2,'간단 실습 시뮬레이션',practice) + panel(3,'결과',result,'full');
  restoreTrackedFields(item.id);
  updateLearningProgress();
  const run = document.querySelector('[data-sim-run]');
  const financeRun = document.querySelector('[data-finance-run]');
  const practiceReview = document.querySelector('[data-practice-review]');
  const technicalPracticeReview = document.querySelector('[data-technical-practice-review]');
  if (technicalPracticeReview) {
    document.querySelectorAll('[data-technical-note]').forEach(field => field.addEventListener('focus', () => {
      const step = Number(field.dataset.technicalStep);
      const priorFields = [...document.querySelectorAll('[data-technical-note]')].slice(0, step);
      const missing = priorFields.find(target => !target.value.trim());
      if (!missing || document.getElementById('technical-guide-modal')?.classList.contains('open')) return;
      field.blur();
      openTechnicalGuideModal(Number(missing.dataset.technicalStep), missing);
    }));
    technicalPracticeReview.addEventListener('click', () => {
      const filled = [...document.querySelectorAll('[data-technical-note]')].filter(field => field.value.trim()).length;
      const company = document.querySelector('[data-technical-note="company"]')?.value.trim() || '분석 종목 미입력';
      document.querySelector('[data-technical-practice-output]').innerHTML = `<strong>${company} · 기술적 분석 워크시트</strong><br>작성 항목 ${filled}/7개입니다. ${filled === 7 ? '종목 선정부터 반대 시나리오까지 기록되었습니다. 실제 매매 전에는 손절가와 포지션 크기를 다시 확인하세요.' : '비어 있는 항목을 채워 추세·진입·위험관리 근거를 완성하세요.'}`;
    });
    return;
  }
  if (practiceReview) {
    let currentSector = lessonLearningState(item.id).fields.sector ?? 'power';
    renderSectorStocks(currentSector);
    document.querySelectorAll('[data-sector-select]').forEach(target => target.classList.toggle('active', target.dataset.sectorSelect === currentSector));
    document.querySelectorAll('[data-sector-select]').forEach(button => button.addEventListener('click', () => {
      currentSector = button.dataset.sectorSelect;
      document.querySelectorAll('[data-sector-select]').forEach(target => target.classList.toggle('active', target === button));
      renderSectorStocks(currentSector);
    }));
    practiceReview.addEventListener('click', () => {
      const filled = [...document.querySelectorAll('[data-practice-note]')].filter(field => field.value.trim()).length;
      const stock = document.querySelector('[name="practice-stock"]:checked')?.value ?? '미선택';
      const sector = sectorPracticeData[currentSector].label;
      const output = document.querySelector('[data-practice-output]');
      output.innerHTML = `<strong>${sector} · ${stock} 분석 메모</strong><br>필수 작성 항목 ${filled}/5개를 입력했습니다. ${filled === 5 ? '기업 선택·가치평가·위험·재검토 기준이 모두 기록되었습니다.' : '비어 있는 항목을 채워 투자 가설과 반대 시나리오를 함께 점검하세요.'}`;
    });
    return;
  }
  if (financeRun) {
    financeRun.addEventListener('click', () => runFinancialSimulation(item));
    document.querySelectorAll('[data-finance-tab]').forEach(tab => tab.addEventListener('click', () => {
      document.querySelectorAll('[data-finance-tab]').forEach(button => button.classList.toggle('active', button === tab));
      document.querySelectorAll('[data-finance-panel]').forEach(panel => panel.classList.toggle('active', panel.dataset.financePanel === tab.dataset.financeTab));
    }));
    document.querySelectorAll('[data-finance]').forEach(input => input.addEventListener('change', () => runFinancialSimulation(item)));
    return;
  }
  run?.addEventListener('click', () => {
    const selected = [...document.querySelectorAll('[data-sim-condition]:checked')].map(input => ({ label:input.value, index:input.dataset.conditionIndex, strength:Number(document.querySelector(`[data-sim-condition-range="${input.dataset.conditionIndex}"]`).value) }));
    if (!selected.length) { document.querySelector('[data-sim-output]').innerHTML = '<strong>분석 조건을 1개 이상 선택하세요.</strong><br>교집합 분석은 선택한 조건을 함께 평가합니다.'; return; }
    const values = selected.map(({label, strength}) => (item.result.bars.find(([name]) => name === label)?.[1] ?? 50) + (strength - 3) * 8);
    const intersection = Math.min(...values);
    const adjusted = Math.min(99, Math.max(1, intersection));
    const tone = toneFrom(adjusted);
    const conditionText = selected.map(({label, strength}) => `${readableMetric(label)} (${strength}/5)`).join(' · ');
    document.querySelector('[data-sim-output]').innerHTML = `<strong>교집합 분석 · ${tone} 신호</strong><br>선택한 ${selected.length}개 조건을 동시에 평가했습니다. 가장 약한 조건을 기준으로 신호가 결정됩니다.`;
    document.querySelector('[data-sim-insight]').innerHTML = `<strong>선택 조건의 교집합을 해석 중입니다.</strong> ${conditionText}가 모두 충족되는지 확인하며, 각 척도의 개별 강도를 반영했을 때 ${tone} 신호가 나타났습니다.`;
    const selectedLabels = selected.map(({label}) => label);
    const liveBars = item.result.bars.map(([label, value]) => { const setting=selected.find(condition => condition.label === label); return [label, setting ? Math.max(1, Math.min(99, value + (setting.strength - 3) * 8)) : value]; });
    document.querySelector('.signal-display').outerHTML = signalLight(tone, `교집합 분석 · ${selected.length}개 조건`, `선택 조건: ${conditionText}`);
    document.querySelector('.result-bars').innerHTML = bars({bars:liveBars}, selectedLabels).replace('<div class="result-bars">','').replace(/<\/div>$/,'');
    document.querySelector('.result-note').innerHTML = `<strong>교집합 분석:</strong> ${conditionText}가 모두 같은 방향을 보여야 신호의 신뢰도가 높아집니다. ${tone} 신호라도 최신 시장 상황과 위험 요인을 함께 확인하세요.`;
  });
}
function openMetricModal(term) {
  const source = metricSources[term] ?? marketCheckSources[term] ?? strategyConceptSources[term] ?? financialTermSources[term] ?? valuationTermSources[term] ?? technicalTermSources[term] ?? { source:'금융감독원 전자공시시스템(DART) · 한국거래소(KRX)', description:'기업 공시 및 시장 데이터를 바탕으로 확인하는 학습용 지표입니다.', url:'https://dart.fss.or.kr/' };
  const modal = document.getElementById('metric-modal');
  document.getElementById('metric-modal-title').textContent = readableMetric(term);
  document.getElementById('metric-modal-description').textContent = source.description;
  const image = document.getElementById('metric-modal-image');
  const fallbackImage = /엘리어트|추진 파동|조정 파동|파동 카운팅/.test(term) ? '/img/technical-elliott.svg' : /RSI|MACD|볼린저|다이버전스|과매수|과매도|모멘텀|변동성/.test(term) ? '/img/technical-indicator.svg' : /캔들|몸통|꼬리/.test(term) ? '/img/technical-candle.svg' : /패턴|이중바닥|컵앤핸들|삼각수렴|돌파|무효화|추격매수|손익비/.test(term) ? '/img/technical-pattern.svg' : term.includes('갭') ? '/img/technical-gap.svg' : term.includes('되돌림') ? '/img/technical-retracement.svg' : /지지|저항|손절|전고점|이탈/.test(term) ? '/img/technical-support.svg' : '/img/technical-trend.svg';
  image.onerror = () => { image.onerror = null; image.src = fallbackImage; };
  image.src = source.image ?? ''; image.classList.toggle('show', Boolean(source.image));
  document.getElementById('metric-modal-details').innerHTML = (source.details ?? []).map(detail => `<li>${detail}</li>`).join('');
  document.getElementById('metric-modal-source').textContent = source.source;
  const links = source.links ?? [{ label:'금융감독원 DART 공시 확인', url:source.url ?? 'https://dart.fss.or.kr/' }];
  document.getElementById('metric-modal-links').innerHTML = links.map(link => `<a href="${link.url}" class="metric-source-link" target="_blank" rel="noopener noreferrer">${link.label} <i class="fa-solid fa-arrow-up-right-from-square"></i></a>`).join('');
  modal.classList.add('open'); modal.setAttribute('aria-hidden', 'false'); document.body.style.overflow = 'hidden';
}
function closeMetricModal() { const modal=document.getElementById('metric-modal'); modal?.classList.remove('open'); modal?.setAttribute('aria-hidden','true'); document.body.style.overflow=''; }
function recordLearningClick(event) {
  const target=event.target.closest('button,a,input,textarea,select,label');
  if (!target) return;
  const state=lessonLearningState(activeLesson);
  const text=(target.getAttribute('aria-label') || target.textContent || target.value || target.tagName).replace(/\s+/g,' ').trim().slice(0,120);
  const clickKey=`click:${target.tagName.toLowerCase()}:${target.dataset.lesson ?? target.dataset.metricIndex ?? target.dataset.marketCheckIndex ?? target.dataset.strategyConceptIndex ?? target.dataset.financialTermIndex ?? target.dataset.valuationTermIndex ?? target.dataset.technicalTermIndex ?? target.dataset.sectorSelect ?? target.getAttribute('href') ?? text}`;
  learningState.clicks.push({ lesson:activeLesson, target:target.tagName.toLowerCase(), text, at:new Date().toISOString() });
  markLearningProgress(clickKey);
  const run=target.closest('[data-sim-run],[data-finance-run],[data-practice-review],[data-technical-practice-review],[data-quant-backtest],[data-quant-seasonality],[data-pine-check]');
  if (run) { const action=`run:${run.dataset.simRun !== undefined ? 'simulation' : run.dataset.financeRun !== undefined ? 'finance' : run.dataset.practiceReview !== undefined ? 'company-practice' : run.dataset.technicalPracticeReview !== undefined ? 'technical-practice' : run.dataset.quantBacktest !== undefined ? 'quant-backtest' : run.dataset.quantSeasonality !== undefined ? 'seasonality' : 'pine-check'}`; state.actions[action]=true; markLearningProgress(`action:${activeLesson}:${action}`); }
  const sector=target.closest('[data-sector-select]');
  if (sector) { state.fields.sector=sector.dataset.sectorSelect; state.actions['sector-select']=true; markLearningProgress(`action:${activeLesson}:sector-select`); }
  saveLearningState(); updateLearningProgress();
}
function selectLesson(id) { activeLesson=id; learningState.activeLesson=id; saveLearningState(); renderMenu(); renderLesson(); document.querySelector('.academy-content').scrollTo?.({top:0, behavior:'smooth'}); }
document.addEventListener('DOMContentLoaded', async () => { await initPage(); renderMenu(); renderLesson(); document.addEventListener('input', event => saveTrackedField(event.target)); document.addEventListener('change', event => saveTrackedField(event.target)); document.addEventListener('click', event => { recordLearningClick(event); const link=event.target.closest('[data-metric-index]'); const check=event.target.closest('[data-market-check-index]'); const concept=event.target.closest('[data-strategy-concept-index]'); const finance=event.target.closest('[data-financial-term-index]'); const valuation=event.target.closest('[data-valuation-term-index]'); const technical=event.target.closest('[data-technical-term-index]'); if (link) openMetricModal(orderedMetricTerms[Number(link.dataset.metricIndex)]?.[0]); if (check) openMetricModal(orderedMarketChecks[Number(check.dataset.marketCheckIndex)]); if (concept) openMetricModal(orderedStrategyConcepts[Number(concept.dataset.strategyConceptIndex)]); if (finance) openMetricModal(orderedFinancialTerms[Number(finance.dataset.financialTermIndex)]); if (valuation) openMetricModal(orderedValuationTerms[Number(valuation.dataset.valuationTermIndex)]); if (technical) openMetricModal(orderedTechnicalTerms[Number(technical.dataset.technicalTermIndex)]); if (event.target.closest('[data-metric-close]')) closeMetricModal(); if (event.target.closest('[data-finance-modal-close]')) closeFinanceValidationModal(); if (event.target.closest('[data-technical-guide-close]')) closeTechnicalGuideModal(); }); document.addEventListener('keydown', event => { if (event.key === 'Escape') { closeMetricModal(); closeFinanceValidationModal(); closeTechnicalGuideModal(); } }); });
