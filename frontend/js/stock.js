/* ── 상태 ─────────────────────────────────────────────────────────────────── */
let currentPeriod       = '1m';
let currentMarketFilter = 'ALL';
let allStocks           = [];
let lastPositions       = [];
let lastCash            = 10_000_000;
let liveStockPrices     = {};
let watchlist           = new Set(JSON.parse(localStorage.getItem('stockWatchlist') || '[]'));

/* ── LW Charts ───────────────────────────────────────────────────────────── */
let lwChart  = null;
let lwCandle = null;
let lwVolume = null;

function initStockChart() {
  const container = document.getElementById('stockChart');
  if (!container || !window.LightweightCharts) return;

  lwChart = LightweightCharts.createChart(container, {
    layout:     { background: { color: '#FFFFFF' }, textColor: '#6B7280' },
    grid:       { vertLines: { color: '#F3F4F6' }, horzLines: { color: '#F3F4F6' } },
    crosshair:  { mode: LightweightCharts.CrosshairMode.Normal },
    rightPriceScale: { borderColor: '#E5E7EB' },
    timeScale:  { borderColor: '#E5E7EB', timeVisible: true, secondsVisible: false },
    handleScroll: true, handleScale: true,
  });

  lwCandle = lwChart.addCandlestickSeries({
    upColor: '#E11D48', downColor: '#2563EB',
    borderUpColor: '#E11D48', borderDownColor: '#2563EB',
    wickUpColor:   '#E11D48', wickDownColor:   '#2563EB',
  });

  lwVolume = lwChart.addHistogramSeries({
    color: 'rgba(41,98,255,0.35)',
    priceFormat: { type: 'volume' },
    priceScaleId: 'volume',
    scaleMargins: { top: 0.85, bottom: 0 },
  });

  new ResizeObserver(() => {
    if (lwChart && container) lwChart.resize(container.clientWidth, container.clientHeight);
  }).observe(container);
}

/* ── 포트폴리오 도넛 (미니) ─────────────────────────────────────────────── */
let portfolioChart = null;

function initPortfolioChart() {
  const el = document.getElementById('portfolioChart');
  if (!el || !window.LightweightCharts) return;
  // ApexCharts 미사용 시 간단히 생략 — 필요 시 별도 라이브러리 추가
}

function updatePortfolioMini(positions, cash) {
  const el = document.getElementById('portfolioChart');
  if (!el) return;
  const total = cash + positions.reduce((s, p) => s + (p.evalAmount || 0), 0);
  if (total <= 0) { el.innerHTML = ''; return; }

  const cashPct = Math.round(cash / total * 100);
  const bars = positions.map(p => {
    const pct = Math.round((p.evalAmount || 0) / total * 100);
    const color = p.pnl >= 0 ? '#E11D48' : '#2563EB';
    return `<div title="${p.name} ${pct}%" style="flex:${pct};background:${color};min-width:3px;"></div>`;
  });
  bars.push(`<div title="현금 ${cashPct}%" style="flex:${cashPct};background:rgba(124,92,252,0.5);min-width:3px;"></div>`);
  el.innerHTML = `<div style="display:flex;height:8px;border-radius:4px;overflow:hidden;gap:1px;margin-top:6px;">${bars.join('')}</div>
    <div style="font-size:10px;color:var(--muted);margin-top:3px;">현금 ${cashPct}% · 주식 ${100 - cashPct}%</div>`;
}

/* ── 포맷터 ──────────────────────────────────────────────────────────────── */
function fmtKrw(v) { return Number(v).toLocaleString('ko-KR') + '원'; }
function fmtVol(v) {
  if (v >= 1e8) return (v / 1e8).toFixed(1) + '억주';
  if (v >= 1e4) return (v / 1e4).toFixed(1) + '만주';
  return Number(v).toLocaleString('ko-KR') + '주';
}
function colorByVal(v) { return v > 0 ? '#E11D48' : v < 0 ? '#2563EB' : '#787B86'; }

/* ── API fetch helper ────────────────────────────────────────────────────── */
async function requestJson(url, options = {}) {
  const fullUrl  = url.startsWith('/') ? API_BASE + url : url;
  const response = await fetch(fullUrl, { credentials: 'include', ...options });
  const raw = await response.text();
  let data = null;
  try { data = raw.trim() ? JSON.parse(raw) : null; } catch { throw new Error('응답 형식 오류'); }
  if (!response.ok) throw new Error(data?.message || '요청 실패');
  if (data === null) throw new Error('빈 응답');
  return data;
}

function showMsg(msg, isErr = false) {
  const el = document.getElementById('stockMessage');
  if (el) { el.textContent = msg; el.style.color = isErr ? '#E11D48' : '#2E7D32'; }
}

/* ── Watchlist ───────────────────────────────────────────────────────────── */
function saveWatchlist() { localStorage.setItem('stockWatchlist', JSON.stringify([...watchlist])); }
function updateWatchBtn(sym) {
  const btn = document.getElementById('watchlistBtn');
  if (!btn) return;
  const has = watchlist.has(sym);
  btn.textContent = has ? '⭐' : '☆';
  btn.style.color = has ? '#FFCC00' : 'rgba(255,255,255,0.4)';
}
document.getElementById('watchlistBtn')?.addEventListener('click', () => {
  const sym = document.getElementById('stockSymbol')?.value;
  if (!sym) return;
  watchlist.has(sym) ? watchlist.delete(sym) : watchlist.add(sym);
  saveWatchlist(); updateWatchBtn(sym);
  if (currentMarketFilter === 'WATCH') rebuildSelectOptions();
});

/* ── 마켓 리스트 (실시간 5초 polling) ───────────────────────────────────── */
async function loadBatchPrices() {
  try {
    const data = await requestJson('/api/stocks/prices');
    liveStockPrices = data.prices ?? {};
    renderStockMarketList();
  } catch {}
}

function renderStockMarketList() {
  const tbody = document.getElementById('stockMarketListBody');
  if (!tbody) return;

  const search = (document.getElementById('stockSearch')?.value ?? '').toLowerCase();
  const stocks = allStocks.filter(s => {
    if (currentMarketFilter === 'KOSPI'  && s.market !== 'KOSPI')  return false;
    if (currentMarketFilter === 'KOSDAQ' && s.market !== 'KOSDAQ') return false;
    if (currentMarketFilter === 'WATCH'  && !watchlist.has(s.symbol)) return false;
    if (search && !s.name.toLowerCase().includes(search) && !s.symbol.includes(search)) return false;
    return true;
  });

  if (!stocks.length) {
    tbody.innerHTML = `<tr><td colspan="4" style="padding:12px;text-align:center;color:var(--muted);">종목 없음</td></tr>`;
    return;
  }

  tbody.innerHTML = stocks.map(s => {
    const p = liveStockPrices[s.symbol];
    const price = p ? Number(p.price).toLocaleString('ko-KR') : '-';
    const rate  = p ? Number(p.changeRate) : 0;
    const color = colorByVal(rate);
    const rateStr = p ? (rate >= 0 ? '+' : '') + rate.toFixed(2) + '%' : '-';
    const hasWatch = watchlist.has(s.symbol);
    return `<tr onclick="selectStockFromList('${s.symbol}')"
              style="cursor:pointer;border-bottom:1px solid var(--border);">
      <td style="padding:6px 10px;">
        <div style="font-weight:700;color:var(--fg);font-size:12px;">${s.name}</div>
        <div style="font-size:10px;color:var(--muted);">${s.market}</div>
      </td>
      <td style="padding:6px 10px;text-align:right;font-weight:700;color:var(--fg);font-size:12px;">${price}</td>
      <td style="padding:6px 10px;text-align:right;font-size:11px;font-weight:700;color:${color};">${rateStr}</td>
      <td style="padding:6px 5px;text-align:center;" onclick="event.stopPropagation()">
        <button onclick="toggleStockWatch('${s.symbol}')"
          style="background:none;border:none;cursor:pointer;font-size:12px;color:${hasWatch ? '#FFCC00' : 'var(--muted)'};">${hasWatch ? '⭐' : '☆'}</button>
      </td>
    </tr>`;
  }).join('');
}

function toggleStockWatch(sym) {
  watchlist.has(sym) ? watchlist.delete(sym) : watchlist.add(sym);
  saveWatchlist();
  renderStockMarketList();
  updateWatchBtn(sym);
  if (currentMarketFilter === 'WATCH') rebuildSelectOptions();
}

async function selectStockFromList(sym) {
  currentMarketFilter = 'ALL';
  document.querySelectorAll('.market-tab').forEach(t => t.classList.toggle('active', t.dataset.market === 'ALL'));
  const el = document.getElementById('stockSymbol');
  if (el) { el.value = sym; }
  updateWatchBtn(sym);
  await Promise.all([loadQuote(sym), loadChart(sym, currentPeriod)]);
}

/* ── 종목 선택 드롭다운 (hidden) ─────────────────────────────────────────── */
async function loadStockList() {
  const data = await requestJson('/api/stocks/list');
  allStocks = data.stocks ?? [];
  rebuildSelectOptions();
}

function getFilteredStocks() {
  const search = (document.getElementById('stockSearch')?.value ?? '').toLowerCase();
  return allStocks.filter(s => {
    if (currentMarketFilter === 'KOSPI'  && s.market !== 'KOSPI')  return false;
    if (currentMarketFilter === 'KOSDAQ' && s.market !== 'KOSDAQ') return false;
    if (currentMarketFilter === 'WATCH'  && !watchlist.has(s.symbol)) return false;
    if (search && !s.name.toLowerCase().includes(search) && !s.symbol.includes(search)) return false;
    return true;
  });
}

function rebuildSelectOptions() {
  renderStockMarketList();
  const sel = document.getElementById('stockSymbol');
  if (!sel) return;
  const filtered = getFilteredStocks();
  const prevVal  = sel.value;
  sel.innerHTML  = '';

  if (!filtered.length) {
    const opt = document.createElement('option');
    opt.disabled = true;
    opt.textContent = currentMarketFilter === 'WATCH' ? '관심종목 없음' : '검색 결과 없음';
    sel.appendChild(opt);
    return;
  }

  const markets = [...new Set(filtered.map(s => s.market))];
  markets.forEach(market => {
    const grp = document.createElement('optgroup');
    grp.label = market;
    filtered.filter(s => s.market === market).forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.symbol;
      opt.textContent = `${s.name} (${s.symbol})`;
      if (s.symbol === prevVal) opt.selected = true;
      grp.appendChild(opt);
    });
    sel.appendChild(grp);
  });

  if (!filtered.some(s => s.symbol === prevVal) && filtered.length > 0) {
    sel.value = filtered[0].symbol;
    Promise.all([loadQuote(sel.value), loadChart(sel.value, currentPeriod)]).catch(() => {});
  }
}

/* ── 마켓 탭 ─────────────────────────────────────────────────────────────── */
document.getElementById('marketTabs')?.addEventListener('click', e => {
  const btn = e.target.closest('.market-tab');
  if (!btn) return;
  currentMarketFilter = btn.dataset.market;
  document.querySelectorAll('.market-tab').forEach(t => t.classList.toggle('active', t === btn));
  rebuildSelectOptions();
});

/* ── 차트 로드 ───────────────────────────────────────────────────────────── */
async function loadChart(symbol, period) {
  if (!lwCandle) return;
  try {
    const data = await requestJson(`/api/stocks/chart?symbol=${encodeURIComponent(symbol)}&period=${encodeURIComponent(period)}`);
    const candles = (data.data ?? []).map(d => ({ time: Math.floor(d.x / 1000), open: d.o, high: d.h, low: d.l, close: d.c }))
      .sort((a, b) => a.time - b.time);
    const volumes = (data.data ?? []).map(d => ({
      time: Math.floor(d.x / 1000), value: d.v,
      color: d.c >= d.o ? 'rgba(248,113,113,0.35)' : 'rgba(96,165,250,0.35)',
    })).sort((a, b) => a.time - b.time);
    lwCandle.setData(candles);
    lwVolume.setData(volumes);
    lwChart.timeScale().fitContent();
  } catch {}
}

/* ── 시세 조회 ───────────────────────────────────────────────────────────── */
async function loadQuote(symbol) {
  if (!symbol) return;
  try {
    const data = await requestJson(`/api/stocks/quote?symbol=${encodeURIComponent(symbol)}`);
    const rate  = Number(data.changeRate ?? 0);
    const color = colorByVal(rate);

    setText('chartStockName',  data.name ?? '-');
    setEl('quotePrice',        fmtKrw(data.price ?? 0), color);
    setEl('quoteChange',       (Number(data.change ?? 0) >= 0 ? '+' : '') + fmtKrw(data.change ?? 0), color);
    setEl('quoteChangeRate',   (rate >= 0 ? '+' : '') + rate.toFixed(2) + '%', color);
    setText('quoteVolume',     data.volume ? fmtVol(data.volume) : '-');
    setText('quoteMarket',     data.market ?? '-');
    if (data.simulated) document.getElementById('dataSourceBadge')?.classList.remove('hidden');
    else                document.getElementById('dataSourceBadge')?.classList.add('hidden');

    renderOrderBook(data.price);
    updateBreakEven(lastPositions, symbol);
    updateWatchBtn(symbol);

    // 라이브 가격 업데이트
    liveStockPrices[symbol] = { ...liveStockPrices[symbol], price: data.price, changeRate: rate };
    renderStockMarketList();
  } catch {}
}

/* ── 시장 지수 ───────────────────────────────────────────────────────────── */
async function loadMarket() {
  try {
    const data = await requestJson('/api/stocks/market');
    for (const [key, val] of Object.entries({ KOSPI: data.KOSPI, KOSDAQ: data.KOSDAQ })) {
      const p = key.toLowerCase();
      setText(p + 'Price', Number(val.price).toLocaleString('ko-KR', { minimumFractionDigits: 2 }));
      const rate  = Number(val.changeRate);
      const color = colorByVal(rate);
      setEl(p + 'Change', `${rate >= 0 ? '▲' : '▼'} ${Math.abs(rate).toFixed(2)}%`, color);
    }
  } catch {}
}

/* ── 계좌 + 포지션 ───────────────────────────────────────────────────────── */
async function loadAccount() {
  const data = await requestJson('/api/stocks/account');
  lastCash = data.cash;
  setText('accountCash',   fmtKrw(data.cash));
  setText('accountAsset',  fmtKrw(data.totalAsset));
  const pnl = Number(data.totalPnlRate);
  setEl('accountPnlRate', (pnl >= 0 ? '+' : '') + pnl.toFixed(2) + '%', colorByVal(pnl));
  updatePortfolioMini(lastPositions, data.cash);
}

async function loadPositions() {
  const data = await requestJson('/api/stocks/positions');
  lastPositions = data.positions ?? [];
  const tbody = document.getElementById('positionsBody');
  if (!tbody) return;

  if (!lastPositions.length) {
    tbody.innerHTML = `<tr><td colspan="5" style="padding:10px;text-align:center;color:var(--muted);">포지션 없음</td></tr>`;
    updatePortfolioMini([], lastCash);
    return;
  }
  tbody.innerHTML = lastPositions.map(pos => {
    const pnl   = Number(pos.pnl ?? 0);
    const color = colorByVal(pnl);
    return `<tr style="border-bottom:1px solid rgba(255,255,255,0.04);">
      <td style="padding:6px 10px;font-weight:700;color:var(--fg);font-size:12px;">${pos.name}<br><span style="font-size:10px;color:var(--accent-dark);">${pos.symbol}</span></td>
      <td style="padding:6px 10px;text-align:right;font-size:12px;color:var(--fg);">${pos.quantity}</td>
      <td style="padding:6px 10px;text-align:right;font-size:12px;color:rgba(255,255,255,0.7);">${fmtKrw(pos.avgPrice)}</td>
      <td style="padding:6px 10px;text-align:right;font-size:12px;color:var(--accent-dark);">${fmtKrw(pos.evalAmount)}</td>
      <td style="padding:6px 10px;text-align:right;font-size:13px;font-weight:800;color:${color};">${pnl >= 0 ? '+' : ''}${fmtKrw(pnl)}</td>
    </tr>`;
  }).join('');
  updatePortfolioMini(lastPositions, lastCash);
  updateBreakEven(lastPositions, document.getElementById('stockSymbol')?.value);
}

async function loadHistory() {
  try {
    const data = await requestJson('/api/stocks/orders/history');
    const tbody = document.getElementById('historyBody');
    if (!tbody) return;
    const hist = (data.history ?? []).slice(0, 30);
    if (!hist.length) {
      tbody.innerHTML = `<tr><td colspan="5" style="padding:10px;text-align:center;color:var(--muted);">거래 내역 없음</td></tr>`;
      return;
    }
    tbody.innerHTML = hist.map(h => {
      const isBuy = h.type === 'BUY';
      const color = isBuy ? '#E11D48' : '#2563EB';
      const dt    = new Date(h.ts).toLocaleTimeString('ko-KR', { hour12: false });
      return `<tr style="border-bottom:1px solid rgba(255,255,255,0.04);">
        <td style="padding:5px 10px;color:var(--muted);font-size:11px;">${dt}</td>
        <td style="padding:5px 10px;font-weight:700;color:var(--fg);font-size:12px;">${h.name}<br><span style="font-size:10px;color:var(--accent-dark);">${h.symbol}</span></td>
        <td style="padding:5px 10px;text-align:center;font-weight:800;font-size:12px;color:${color};">${isBuy ? '매수' : '매도'}</td>
        <td style="padding:5px 10px;text-align:right;color:rgba(255,255,255,0.7);font-size:12px;">${Number(h.quantity).toLocaleString('ko-KR')}주</td>
        <td style="padding:5px 10px;text-align:right;color:var(--accent-dark);font-weight:700;font-size:12px;">${fmtKrw(h.amount)}</td>
      </tr>`;
    }).join('');
  } catch {}
}

/* ── 호가창 ──────────────────────────────────────────────────────────────── */
function renderOrderBook(price) {
  if (!price || price <= 0) return;
  const askBody = document.getElementById('askBody');
  const bidBody = document.getElementById('bidBody');
  if (!askBody || !bidBody) return;

  let tick = 1;
  if      (price >= 500000) tick = 1000;
  else if (price >= 100000) tick = 500;
  else if (price >=  50000) tick = 100;
  else if (price >=  10000) tick = 50;
  else if (price >=   1000) tick = 10;

  const qty = (p, o) => Math.max(50, ((p * 7 + o) % 2900) + 100);
  const askRows = Array.from({ length: 5 }, (_, i) => ({ price: price + tick * (5 - i), qty: qty(price + tick * (5 - i), 13) }));
  const bidRows = Array.from({ length: 5 }, (_, i) => ({ price: price - tick * (i + 1), qty: qty(price - tick * (i + 1), 31) }));

  askBody.innerHTML = askRows.map(r => `<tr style="background:rgba(37,99,235,0.04);">
    <td style="padding:4px 10px;text-align:right;color:#60A5FA;font-weight:700;font-size:11px;">${Number(r.price).toLocaleString('ko-KR')}</td>
    <td style="padding:4px 10px;text-align:right;color:var(--muted);font-size:11px;">${Number(r.qty).toLocaleString('ko-KR')}</td></tr>`).join('');
  bidBody.innerHTML = bidRows.map(r => `<tr style="background:rgba(225,29,72,0.04);">
    <td style="padding:4px 10px;text-align:right;color:#F87171;font-weight:700;font-size:11px;">${Number(r.price).toLocaleString('ko-KR')}</td>
    <td style="padding:4px 10px;text-align:right;color:var(--muted);font-size:11px;">${Number(r.qty).toLocaleString('ko-KR')}</td></tr>`).join('');

  setText('obCurrentPrice', Number(price).toLocaleString('ko-KR'));
  const spread = tick * 2;
  setText('obSpread', `${Number(spread).toLocaleString('ko-KR')} (${((spread / price) * 100).toFixed(3)}%)`);
}

function updateBreakEven(positions, sym) {
  const el = document.getElementById('quoteBreakEven');
  if (!el) return;
  const pos = positions?.find(p => p.symbol === sym);
  if (pos) { el.textContent = `${Number(pos.avgPrice).toLocaleString('ko-KR')}원`; el.style.color = '#FFCC00'; }
  else      { el.textContent = '-'; el.style.color = 'var(--muted)'; }
}

/* ── 주문 ────────────────────────────────────────────────────────────────── */
async function submitOrder(type) {
  const qty = Number(document.getElementById('orderQty')?.value);
  if (!Number.isFinite(qty) || qty <= 0) { showMsg('수량은 1 이상이어야 합니다.', true); return; }
  try {
    await requestJson(`/api/stocks/orders/${type}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol: document.getElementById('stockSymbol')?.value, quantity: qty }),
    });
    showMsg(`${type === 'buy' ? '매수' : '매도'} 완료`);
    await Promise.all([loadAccount(), loadPositions(), loadQuote(document.getElementById('stockSymbol')?.value), loadHistory()]);
  } catch (e) { showMsg(e.message, true); }
}

document.getElementById('buyBtn')?.addEventListener('click',  () => submitOrder('buy'));
document.getElementById('sellBtn')?.addEventListener('click', () => submitOrder('sell'));

/* ── 초기화 버튼 ─────────────────────────────────────────────────────────── */
document.getElementById('resetBtn')?.addEventListener('click', async () => {
  if (!confirm('계좌를 초기화하시겠습니까?')) return;
  try {
    await requestJson('/api/stocks/account/reset', { method: 'POST' });
    showMsg('계좌 초기화 완료');
    await Promise.all([loadAccount(), loadPositions(), loadHistory()]);
  } catch (e) { showMsg(e.message, true); }
});

/* ── 기간 버튼 ───────────────────────────────────────────────────────────── */
document.getElementById('periodBtns')?.addEventListener('click', async e => {
  const btn = e.target.closest('.period-btn');
  if (!btn) return;
  currentPeriod = btn.dataset.period;
  document.querySelectorAll('#periodBtns .period-btn').forEach(b => b.classList.toggle('active', b === btn));
  await loadChart(document.getElementById('stockSymbol')?.value, currentPeriod);
});

/* ── 종목 변경 ───────────────────────────────────────────────────────────── */
document.getElementById('stockSymbol')?.addEventListener('change', async () => {
  const sym = document.getElementById('stockSymbol')?.value;
  if (sym) await Promise.all([loadQuote(sym), loadChart(sym, currentPeriod)]);
});

/* ── 유틸 ────────────────────────────────────────────────────────────────── */
function setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }
function setEl(id, val, color) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = val;
  if (color) el.style.color = color;
}

/* ── 부트 ────────────────────────────────────────────────────────────────── */
(async () => {
  await initPage();
  initStockChart();

  await loadStockList();

  const sym = document.getElementById('stockSymbol')?.value;
  await Promise.all([loadMarket(), loadQuote(sym), loadAccount(), loadPositions()]);
  await Promise.all([loadChart(sym, currentPeriod), loadHistory(), loadBatchPrices()]);

  // 실시간 갱신
  setInterval(() => loadBatchPrices(),  5_000);
  setInterval(() => {
    const s = document.getElementById('stockSymbol')?.value;
    if (s) loadQuote(s);
  }, 5_000);
  setInterval(() => {
    loadMarket();
    loadAccount();
    loadPositions();
  }, 15_000);
  setInterval(() => loadHistory(), 30_000);
})();
