const LAB_TEMPLATES = {
  ma: `//@version=6
strategy("MA 교차 연습", overlay = true)

fast = ta.sma(close, 5)
slow = ta.sma(close, 20)
buy = ta.crossover(fast, slow)
sell = ta.crossunder(fast, slow)

if buy
    strategy.entry("Long", strategy.long)
if sell
    strategy.close("Long")`,
  rsi: `//@version=6
strategy("RSI 반전 연습", overlay = false)

rsiValue = ta.rsi(close, 14)
buy = ta.crossover(rsiValue, 30)
sell = ta.crossunder(rsiValue, 70)

if buy
    strategy.entry("Long", strategy.long)
if sell
    strategy.close("Long")`,
  indicator: `//@version=6
indicator("20일 이동평균", overlay = true)

ma20 = ta.sma(close, 20)
plot(ma20, color = color.blue, linewidth = 2)`
};

const lab$ = id => document.getElementById(id);
const prices = Array.from({ length: 90 }, (_, i) => {
  const trend = 100 + i * .18;
  const wave = Math.sin(i * .31) * 5.5 + Math.sin(i * .09) * 3;
  return Number((trend + wave).toFixed(2));
});
const smaLab = (values, length) => values.map((_, i) => i < length - 1 ? null : values.slice(i - length + 1, i + 1).reduce((a, b) => a + b, 0) / length);
const emaLab = (values, length) => { const k = 2 / (length + 1); let previous = values[0]; return values.map((v, i) => previous = i ? v * k + previous * (1 - k) : v); };
const rsiLab = (values, length) => values.map((_, i) => { if (i < length) return null; let gains = 0, losses = 0; for (let j = i - length + 1; j <= i; j++) { const d = values[j] - values[j - 1]; if (d >= 0) gains += d; else losses -= d; } return losses === 0 ? 100 : 100 - 100 / (1 + gains / losses); });
const crossLab = (a, b, i, up) => i > 0 && a[i] != null && b[i] != null && a[i - 1] != null && b[i - 1] != null && (up ? a[i] > b[i] && a[i - 1] <= b[i - 1] : a[i] < b[i] && a[i - 1] >= b[i - 1]);
const staticSeries = value => Array(prices.length).fill(Number(value));

function resetMetrics() { ['lastSignal','tradeCount','strategyReturn','maxDrawdown'].forEach(id => lab$(id).textContent = '-'); }
function format(v) { return Number(v).toLocaleString('ko-KR', { maximumFractionDigits: 2 }); }
function parseLab(code) {
  const issues = [];
  if (!/^\s*\/\/\@version=(5|6)\s*$/m.test(code)) issues.push('첫 줄에 //@version=6(또는 5)을 선언하세요.');
  const kind = /\bstrategy\s*\(/.test(code) ? 'strategy' : /\bindicator\s*\(/.test(code) ? 'indicator' : null;
  if (!kind) issues.push('indicator() 또는 strategy() 선언이 필요합니다.');
  const vars = { close: prices };
  const indicators = [];
  for (const m of code.matchAll(/^\s*([A-Za-z_]\w*)\s*=\s*ta\.(sma|ema|rsi)\(\s*close\s*,\s*(\d+)\s*\)/gmi)) {
    const length = Number(m[3]);
    if (length < 2 || length > 80) issues.push(`${m[1]} 기간은 2~80 범위에서 테스트하세요.`);
    else { vars[m[1]] = m[2].toLowerCase() === 'sma' ? smaLab(prices, length) : m[2].toLowerCase() === 'ema' ? emaLab(prices, length) : rsiLab(prices, length); indicators.push(m[1]); }
  }
  const conditions = {};
  for (const m of code.matchAll(/^\s*([A-Za-z_]\w*)\s*=\s*ta\.(crossover|crossunder)\(\s*([A-Za-z_]\w*|\d+(?:\.\d+)?)\s*,\s*([A-Za-z_]\w*|\d+(?:\.\d+)?)\s*\)/gmi)) {
    const left = vars[m[3]] || (Number.isFinite(Number(m[3])) ? staticSeries(m[3]) : null);
    const right = vars[m[4]] || (Number.isFinite(Number(m[4])) ? staticSeries(m[4]) : null);
    if (!left || !right) issues.push(`${m[1]} 조건의 지표 이름을 확인하세요.`);
    else conditions[m[1]] = prices.map((_, i) => crossLab(left, right, i, m[2].toLowerCase() === 'crossover'));
  }
  if (kind === 'strategy' && !Object.keys(conditions).length) issues.push('간단 테스트에서는 ta.crossover 또는 ta.crossunder 조건이 하나 이상 필요합니다.');
  return { issues, kind, vars, indicators, conditions };
}
function runLab() {
  // 비어 있는 상태에서 실행해도 첫 학습 흐름이 끊기지 않도록 기본 예제를 채운다.
  if (!lab$('pineLabCode').value.trim()) lab$('pineLabCode').value = LAB_TEMPLATES.ma;
  const code = lab$('pineLabCode').value;
  const parsed = parseLab(code);
  lab$('lastClose').textContent = format(prices.at(-1));
  lab$('barCount').textContent = String(prices.length);
  if (parsed.issues.length) {
    resetMetrics();
    lab$('labStatus').innerHTML = `<strong class="bad">수정 필요</strong><br>${parsed.issues.map(i => `• ${i}`).join('<br>')}`;
    lab$('signalRows').innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--muted)">문법을 수정한 뒤 다시 테스트하세요.</td></tr>';
    return;
  }
  const names = Object.keys(parsed.conditions);
  const entries = []; const exits = [];
  if (parsed.kind === 'strategy') {
    const lines = code.split('\n');
    let currentCondition = null;
    lines.forEach(line => {
      const condition = line.match(/^\s*if\s+([A-Za-z_]\w*)/); if (condition) currentCondition = condition[1];
      if (/strategy\.entry\([^\n]*strategy\.long/i.test(line) && parsed.conditions[currentCondition]) entries.push(currentCondition);
      if (/strategy\.close\s*\(/i.test(line) && parsed.conditions[currentCondition]) exits.push(currentCondition);
    });
  }
  let inTrade = false, entryPrice = 0, equity = 100, peak = 100, maxDd = 0; const tradeReturns = [], signals = [];
  for (let i = 0; i < prices.length; i++) {
    const buy = entries.some(name => parsed.conditions[name][i]);
    const sell = exits.some(name => parsed.conditions[name][i]);
    if (!inTrade && buy) { inTrade = true; entryPrice = prices[i]; signals.push({ i, type: 'BUY' }); }
    else if (inTrade && sell) { const ret = (prices[i] / entryPrice - 1) * 100; tradeReturns.push(ret); equity *= 1 + ret / 100; inTrade = false; signals.push({ i, type: 'SELL' }); }
    const marked = inTrade ? equity * prices[i] / entryPrice : equity; peak = Math.max(peak, marked); maxDd = Math.min(maxDd, (marked / peak - 1) * 100);
  }
  const lastSignal = signals.at(-1)?.type || '신호 없음';
  lab$('lastSignal').textContent = lastSignal; lab$('tradeCount').textContent = String(tradeReturns.length);
  lab$('strategyReturn').textContent = `${(equity - 100).toFixed(2)}%`; lab$('maxDrawdown').textContent = `${maxDd.toFixed(2)}%`;
  const latest = parsed.indicators.map(name => `${name} ${parsed.vars[name].at(-1) == null ? '-' : parsed.vars[name].at(-1).toFixed(2)}`).join(' · ');
  lab$('labStatus').innerHTML = `<strong class="ok">학습용 테스트 완료</strong><br>${parsed.kind === 'indicator' ? '지표 선언을 확인했습니다. 주문·백테스트는 실행하지 않습니다.' : `완료 거래 ${tradeReturns.length}건, 현재 ${inTrade ? '보유 중' : '미보유'}입니다.`}<br><span style="color:var(--muted)">${latest || '계산 지표 없음'}</span>`;
  const rows = Array.from({ length: 10 }, (_, n) => prices.length - 10 + n).map(i => {
    const signal = signals.find(s => s.i === i)?.type || '-';
    const a = parsed.indicators[0] ? parsed.vars[parsed.indicators[0]][i] : null;
    const b = parsed.indicators[1] ? parsed.vars[parsed.indicators[1]][i] : null;
    return `<tr><td>${i + 1}</td><td>${format(prices[i])}</td><td>${a == null ? '-' : a.toFixed(2)}</td><td>${b == null ? '-' : b.toFixed(2)}</td><td class="${signal === 'BUY' ? 'ok' : signal === 'SELL' ? 'bad' : ''}">${signal}</td></tr>`;
  }).join('');
  lab$('signalRows').innerHTML = rows;
}
document.addEventListener('DOMContentLoaded', () => { initPage(); lab$('pineLabCode').value = LAB_TEMPLATES.ma; document.querySelectorAll('[data-template]').forEach(btn => btn.addEventListener('click', () => { lab$('pineLabCode').value = LAB_TEMPLATES[btn.dataset.template]; runLab(); })); lab$('runLab').addEventListener('click', runLab); runLab(); });
