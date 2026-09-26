// KIS 종목 차트: 서버(/api/kis-chart/*)가 .env로 KIS Testbed를 호출해 준 캔들을 lightweight-charts로 그린다.
(() => {
  const apiBase = window.APP_CONFIG?.apiBase || '';
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmt = (v, d = 0) => (v === null || v === undefined || Number.isNaN(Number(v)) ? '-' : Number(v).toLocaleString(undefined, { maximumFractionDigits: d }));
  const fmtAmt = (v) => (v === null || v === undefined ? '-' : v >= 1e12 ? `${(v / 1e12).toFixed(2)}조` : v >= 1e8 ? `${(v / 1e8).toFixed(1)}억` : v >= 1e4 ? `${(v / 1e4).toFixed(0)}만` : fmt(v));

  let period = 'D';
  let symbol = '005930';
  let symbolName = '';
  let data = [];
  let chart; let candleSeries; let volumeSeries; const maSeries = {};
  const MA = [[5, '#F59E0B'], [20, '#10B981'], [60, '#8B5CF6']];

  // ── 차트 생성 ─────────────────────────────────────────────────────────
  function initChart() {
    const el = $('chart');
    chart = LightweightCharts.createChart(el, {
      layout: { background: { color: '#FFFFFF' }, textColor: '#6B7280', fontFamily: 'inherit' },
      grid: { vertLines: { color: '#F1F5F9' }, horzLines: { color: '#F1F5F9' } },
      rightPriceScale: { borderColor: '#E5E7EB', scaleMargins: { top: 0.08, bottom: 0.28 } },
      timeScale: { borderColor: '#E5E7EB', timeVisible: true, secondsVisible: false, rightOffset: 4 },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
      localization: { locale: 'ko-KR', priceFormatter: (p) => Number(p).toLocaleString() },
      autoSize: true,
    });
    candleSeries = chart.addCandlestickSeries({ upColor: '#E11D48', downColor: '#2563EB', borderUpColor: '#E11D48', borderDownColor: '#2563EB', wickUpColor: '#E11D48', wickDownColor: '#2563EB', priceFormat: { type: 'price', precision: 0, minMove: 1 } });
    volumeSeries = chart.addHistogramSeries({ priceFormat: { type: 'volume' }, priceScaleId: 'volume' });
    chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.78, bottom: 0 } });
    MA.forEach(([n, color]) => { maSeries[n] = chart.addLineSeries({ color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }); });
    chart.subscribeCrosshairMove(onCrosshair);
  }

  const timeKey = (c) => (period === '1m' ? c.timestamp : c.time);
  function movingAverage(n) {
    const out = [];
    let sum = 0;
    data.forEach((c, i) => { sum += c.close; if (i >= n) sum -= data[i - n].close; if (i >= n - 1) out.push({ time: timeKey(c), value: sum / n }); });
    return out;
  }
  function draw() {
    candleSeries.setData(data.map((c) => ({ time: timeKey(c), open: c.open, high: c.high, low: c.low, close: c.close })));
    volumeSeries.setData(data.map((c) => ({ time: timeKey(c), value: c.volume || 0, color: c.close >= c.open ? 'rgba(225,29,72,.35)' : 'rgba(37,99,235,.35)' })));
    const showMa = $('ma').checked && period !== '1m';
    MA.forEach(([n]) => maSeries[n].setData(showMa && data.length >= n ? movingAverage(n) : []));
    chart.timeScale().fitContent();
    if (data.length) showLegend(data[data.length - 1]);
  }

  // ── 범례·표 ──────────────────────────────────────────────────────────
  function showLegend(c, maVals) {
    const diff = c.close - c.open;
    const cls = diff > 0 ? 'up' : diff < 0 ? 'down' : '';
    const parts = [
      `<b>${esc(symbolName || symbol)}</b> ${esc(c.time)}`,
      `시 <b>${fmt(c.open)}</b>`, `고 <b>${fmt(c.high)}</b>`, `저 <b>${fmt(c.low)}</b>`,
      `종 <b class="${cls}">${fmt(c.close)}</b> <span class="${cls}">(${diff >= 0 ? '+' : ''}${fmt(diff)} / ${c.open ? ((diff / c.open) * 100).toFixed(2) : '0.00'}%)</span>`,
      `거래량 <b>${fmt(c.volume)}</b>`, c.amount ? `대금 <b>${fmtAmt(c.amount)}</b>` : '',
    ];
    if (maVals) MA.forEach(([n]) => { if (maVals[n] !== undefined) parts.push(`<span class="ma${n}">MA${n} ${fmt(maVals[n])}</span>`); });
    $('legend').innerHTML = parts.filter(Boolean).join(' · ');
  }
  function onCrosshair(param) {
    if (!param.time || !data.length) return;
    const bar = param.seriesData.get(candleSeries);
    if (!bar) return;
    const c = data.find((x) => timeKey(x) === param.time);
    if (!c) return;
    const maVals = {};
    MA.forEach(([n]) => { const v = param.seriesData.get(maSeries[n]); if (v) maVals[n] = v.value; });
    showLegend(c, maVals);
  }
  function renderTable() {
    const rows = [...data].reverse();
    $('tblCount').textContent = `${rows.length}건`;
    $('tbody').innerHTML = rows.map((c, i) => {
      const prev = rows[i + 1];
      const d = prev ? c.close - prev.close : null;
      const cls = d > 0 ? 'up' : d < 0 ? 'down' : '';
      return `<tr><td>${esc(c.time)}</td><td>${fmt(c.open)}</td><td>${fmt(c.high)}</td><td>${fmt(c.low)}</td><td class="${cls}">${fmt(c.close)}</td><td class="${cls}">${d === null ? '-' : `${d >= 0 ? '+' : ''}${fmt(d)}`}</td><td>${fmt(c.volume)}</td><td>${fmtAmt(c.amount)}</td></tr>`;
    }).join('');
  }
  function renderQuote(s) {
    if (!s) { $('quote').innerHTML = ''; return; }
    const cls = (s.change || 0) > 0 ? 'up' : (s.change || 0) < 0 ? 'down' : '';
    symbolName = s.name || symbolName;
    $('quote').innerHTML = `
      <div style="display:flex;flex-wrap:wrap;gap:6px 14px;align-items:baseline;margin-top:14px">
        <span style="font-size:18px;font-weight:900;color:var(--fg)">${esc(s.name || symbol)} <small style="color:var(--muted);font-weight:700">${esc(symbol)}</small></span>
        <span class="price-big ${cls}">${fmt(s.price)}</span>
        <span class="${cls}" style="font-weight:800">${s.change >= 0 ? '+' : ''}${fmt(s.change)} (${s.changeRate >= 0 ? '+' : ''}${fmt(s.changeRate, 2)}%)</span>
        <span style="font-size:12px;color:var(--muted)">KIS Testbed · 기준 시점의 현재가</span>
      </div>
      <div class="q-grid">
        <div class="q"><small>시가 / 고가 / 저가</small><b>${fmt(s.open)} / ${fmt(s.high)} / ${fmt(s.low)}</b></div>
        <div class="q"><small>전일 종가</small><b>${fmt(s.prevClose)}</b></div>
        <div class="q"><small>누적 거래량</small><b>${fmt(s.volume)}</b></div>
        <div class="q"><small>누적 거래대금</small><b>${fmtAmt(s.amount)}</b></div>
        <div class="q"><small>상한가 / 하한가</small><b>${fmt(s.upperLimit)} / ${fmt(s.lowerLimit)}</b></div>
        <div class="q"><small>시가총액</small><b>${s.marketCap ? `${fmt(s.marketCap)}억` : '-'}</b></div>
        <div class="q"><small>PER / PBR / EPS</small><b>${fmt(s.per, 2)} / ${fmt(s.pbr, 2)} / ${fmt(s.eps)}</b></div>
      </div>`;
  }

  // ── 데이터 로드 ────────────────────────────────────────────────────────
  async function load() {
    const input = $('symbol').value.trim();
    if (/^\d{6}$/.test(input)) symbol = input;
    else if (input) { const hit = await search(input, 1); if (hit.length) { symbol = hit[0].symbol; symbolName = hit[0].name; $('symbol').value = symbol; } else { showMsg(`'${input}' 에 해당하는 종목을 찾지 못했습니다. 6자리 종목코드를 입력하세요.`, true); return; } }
    const count = $('count').value;
    const url = period === '1m' ? `/api/kis-chart/minutes?symbol=${symbol}&count=${Math.min(240, count)}` : `/api/kis-chart/candles?symbol=${symbol}&period=${period}&count=${count}`;
    $('load').disabled = true; $('loading').style.display = 'flex'; showMsg('');
    try {
      const res = await fetch(`${apiBase}${url}`);
      const text = await res.text();
      let body;
      try { body = JSON.parse(text); } catch { throw new Error(`서버 응답을 해석할 수 없습니다 (HTTP ${res.status}).`); }
      if (!body.ok) throw new Error(body.message || '조회에 실패했습니다.');
      data = body.candles.filter((c) => c.open !== null && c.close !== null);
      renderQuote(body.summary);
      if (!data.length) { showMsg(period === '1m' ? '당일 분봉 데이터가 없습니다. 휴장일이거나 장 시작 전일 수 있습니다. 일봉으로 확인하세요.' : '캔들 데이터가 없습니다.', true); candleSeries.setData([]); volumeSeries.setData([]); MA.forEach(([n]) => maSeries[n].setData([])); $('tbody').innerHTML = ''; return; }
      draw(); renderTable();
      history.replaceState(null, '', `?symbol=${symbol}&period=${period}`);
    } catch (error) {
      showMsg(error.message, true);
    } finally { $('load').disabled = false; $('loading').style.display = 'none'; }
  }
  function showMsg(text, isError) { $('msg').innerHTML = text ? `<div class="${isError ? 'danger' : 'notice'}">${esc(text)}</div>` : ''; }

  // ── 종목 검색 (이 웹앱의 KRX 종목 마스터, KIS 호출 아님) ─────────────────
  async function search(q, limit = 8) {
    try { const res = await fetch(`${apiBase}/api/stocks/search?q=${encodeURIComponent(q)}&limit=${limit}`); const body = await res.json(); return body.stocks || []; } catch { return []; }
  }
  let sugTimer;
  $('symbol').addEventListener('input', () => {
    clearTimeout(sugTimer);
    const q = $('symbol').value.trim();
    if (!q || /^\d{6}$/.test(q)) { $('sug').style.display = 'none'; return; }
    sugTimer = setTimeout(async () => {
      const hits = await search(q);
      if (!hits.length) { $('sug').style.display = 'none'; return; }
      $('sug').innerHTML = hits.map((h) => `<button data-s="${esc(h.symbol)}" data-n="${esc(h.name)}"><b>${esc(h.name)}</b><small>${esc(h.symbol)} · ${esc(h.market || '')}</small></button>`).join('');
      $('sug').style.display = 'block';
    }, 200);
  });
  $('sug').addEventListener('click', (e) => { const b = e.target.closest('button'); if (!b) return; symbol = b.dataset.s; symbolName = b.dataset.n; $('symbol').value = symbol; $('sug').style.display = 'none'; load(); });
  document.addEventListener('click', (e) => { if (!e.target.closest('.c-search')) $('sug').style.display = 'none'; });
  $('symbol').addEventListener('keydown', (e) => { if (e.key === 'Enter') { $('sug').style.display = 'none'; load(); } });
  $('periods').addEventListener('click', (e) => { const b = e.target.closest('button[data-p]'); if (!b) return; period = b.dataset.p; $('periods').querySelectorAll('button').forEach((x) => x.classList.toggle('on', x === b)); load(); });
  $('count').addEventListener('change', load);
  $('ma').addEventListener('change', () => { if (data.length) draw(); });
  $('load').addEventListener('click', load);

  document.addEventListener('DOMContentLoaded', async () => {
    await initPage();
    initChart();
    const qs = new URLSearchParams(location.search);
    if (/^\d{6}$/.test(qs.get('symbol') || '')) { symbol = qs.get('symbol'); $('symbol').value = symbol; }
    if (['1m', 'D', 'W', 'M', 'Y'].includes(qs.get('period'))) { period = qs.get('period'); $('periods').querySelectorAll('button').forEach((x) => x.classList.toggle('on', x.dataset.p === period)); }
    load();
  });
})();
