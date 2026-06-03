/* ── 상태 ─────────────────────────────────────────────────────────────────── */
let currentMarketCode = 'KRW-BTC';
let currentUser       = null;
let currentPeriod     = 'days';
let selectedExchange  = 'UPBIT';
let priceLinesMap     = {};   // exchange code → LW Charts priceLine

const EXCHANGE_META = {
  UPBIT:   { label: '업비트', color: '#2563EB', lineStyle: 0 },
  BITHUMB: { label: '빗썸',   color: '#E11D48', lineStyle: 1 },
  COINONE: { label: '코인원', color: '#059669', lineStyle: 1 },
  KORBIT:  { label: '코빗',   color: '#D97706', lineStyle: 1 },
};

const CRYPTO_WATCH_KEY = 'cryptoWatchlist';
let cryptoWatchlist = new Set(JSON.parse(localStorage.getItem(CRYPTO_WATCH_KEY) || '[]'));

/* ── LW Charts 인스턴스 ──────────────────────────────────────────────────── */
let lwChart     = null;
let lwCandle    = null;
let lwVolume    = null;

function initLwChart() {
  const container = document.getElementById('coinChart');
  if (!container || !window.LightweightCharts) return;

  lwChart = LightweightCharts.createChart(container, {
    layout:     { background: { color: '#FFFFFF' }, textColor: '#6B7280' },
    grid:       { vertLines: { color: '#F3F4F6' }, horzLines: { color: '#F3F4F6' } },
    crosshair:  { mode: LightweightCharts.CrosshairMode.Normal },
    rightPriceScale: { borderColor: '#E5E7EB' },
    timeScale:  { borderColor: '#E5E7EB', timeVisible: true, secondsVisible: false },
    handleScroll: true,
    handleScale:  true,
  });

  lwCandle = lwChart.addCandlestickSeries({
    upColor:   '#E11D48', downColor: '#2563EB',
    borderUpColor: '#E11D48', borderDownColor: '#2563EB',
    wickUpColor:   '#E11D48', wickDownColor:   '#2563EB',
  });

  lwVolume = lwChart.addHistogramSeries({
    color:      'rgba(41,98,255,0.35)',
    priceFormat: { type: 'volume' },
    priceScaleId: 'volume',
    scaleMargins: { top: 0.85, bottom: 0 },
  });

  new ResizeObserver(() => {
    if (lwChart && container) lwChart.resize(container.clientWidth, container.clientHeight);
  }).observe(container);
}

/* ── Upbit 캔들 fetch ────────────────────────────────────────────────────── */
async function loadCoinChart(marketCode, period) {
  if (!lwCandle) return;
  const symbol = marketCode.split('-')[1];

  const upbitUrls = {
    'days':       `https://api.upbit.com/v1/candles/days?market=${marketCode}&count=200`,
    'weeks':      `https://api.upbit.com/v1/candles/weeks?market=${marketCode}&count=100`,
    'minutes/1':  `https://api.upbit.com/v1/candles/minutes/1?market=${marketCode}&count=200`,
    'minutes/60': `https://api.upbit.com/v1/candles/minutes/60?market=${marketCode}&count=200`,
  };
  const url = upbitUrls[period] ?? upbitUrls['days'];

  try {
    const res  = await fetch(url);
    const data = await res.json();
    if (!Array.isArray(data)) return;

    const candles = data.map(d => ({
      time:  Math.floor(new Date(d.candle_date_time_utc).getTime() / 1000),
      open:  d.opening_price,
      high:  d.high_price,
      low:   d.low_price,
      close: d.trade_price,
    })).sort((a, b) => a.time - b.time);

    const volumes = data.map(d => ({
      time:  Math.floor(new Date(d.candle_date_time_utc).getTime() / 1000),
      value: d.candle_acc_trade_volume,
      color: d.trade_price >= d.opening_price ? 'rgba(248,113,113,0.35)' : 'rgba(96,165,250,0.35)',
    })).sort((a, b) => a.time - b.time);

    lwCandle.setData(candles);
    lwVolume.setData(volumes);
    lwChart.timeScale().fitContent();
  } catch {}
}

/* ── 기간 버튼 ───────────────────────────────────────────────────────────── */
document.getElementById('coinPeriodBtns')?.addEventListener('click', async (e) => {
  const btn = e.target.closest('.period-btn');
  if (!btn) return;
  currentPeriod = btn.dataset.period;
  document.querySelectorAll('#coinPeriodBtns .period-btn').forEach(b =>
    b.classList.toggle('active', b === btn));
  await loadCoinChart(currentMarketCode, currentPeriod);
});

/* ── 초기화 ──────────────────────────────────────────────────────────────── */
(async () => {
  currentUser = await initPage();

  const [marketRes] = await Promise.all([apiFetch('/api/crypto/market-list')]);
  if (!marketRes.ok) return;
  const { markets, marketCodes } = await marketRes.json();

  renderMarketSidebar(markets);
  initLwChart();
  initWebSocket(marketCodes);
  await getCryptoInfo('KRW-BTC');
  await loadCoinChart('KRW-BTC', currentPeriod);
  updateAssetDisplay();
})();

/* ── 마켓 사이드바 렌더 ──────────────────────────────────────────────────── */
function renderMarketSidebar(markets) {
  const tbody = document.getElementById('marketListBody');
  if (!tbody) return;
  tbody.innerHTML = markets.map(m => `
    <tr onclick="selectCoin('${m.market}')" style="cursor:pointer;border-bottom:1px solid var(--border);">
      <td style="padding:7px 10px;font-weight:600;color:var(--fg);">${m.koreanName}</td>
      <td style="padding:7px 10px;text-align:right;font-weight:700;" id="${m.market}-trade_price">-</td>
      <td style="padding:7px 10px;text-align:right;font-size:11px;" id="${m.market}-signed_change_rate">-</td>
      <td style="padding:7px 5px;text-align:center;" onclick="event.stopPropagation()">
        <button id="${m.market}-watch-btn" onclick="toggleCryptoWatch('${m.market}')"
          style="background:none;border:none;cursor:pointer;font-size:13px;color:var(--muted);">☆</button>
      </td>
    </tr>`).join('');
  renderCryptoWatchBtns();
}

async function selectCoin(marketCode) {
  currentMarketCode = marketCode;
  await getCryptoInfo(marketCode);
  await loadCoinChart(marketCode, currentPeriod);
}

/* ── 업비트 웹소켓 ───────────────────────────────────────────────────────── */
function initWebSocket(marketCodes) {
  const socket = new WebSocket('wss://api.upbit.com/websocket/v1');
  socket.onopen = () => {
    socket.send(JSON.stringify([
      { ticket: 'edumgt-order' },
      { type: 'ticker', codes: marketCodes },
    ]));
  };
  socket.onmessage = async (e) => {
    try {
      const r     = JSON.parse(await e.data.text());
      if (r.type !== 'ticker') return;
      const code  = r.code;
      const price = new Intl.NumberFormat('ko-KR').format(r.trade_price);
      let   rate  = (r.signed_change_rate * 100).toFixed(2);
      const color = rate > 0 ? '#E11D48' : rate < 0 ? '#2563EB' : '#787B86';
      if (rate > 0) rate = '+' + rate;

      const tEl = document.getElementById(code + '-trade_price');
      const rEl = document.getElementById(code + '-signed_change_rate');
      if (tEl) { tEl.textContent = price; tEl.style.color = color; }
      if (rEl) { rEl.textContent = rate + '%'; rEl.style.color = color; }

      if (code === currentMarketCode) {
        const lp = document.getElementById('crypto_live_price');
        const lr = document.getElementById('crypto_live_rate');
        if (lp) { lp.textContent = price; lp.style.color = color; }
        if (lr) { lr.textContent = rate + '%'; lr.style.color = color; }
      }

      // acc_trade_price_24h는 ticker에서 생략 (표시 공간 절약)
    } catch {}
  };
  socket.onerror = () => console.warn('웹소켓 연결 실패');
}

/* ── 코인 정보 + 국내 시세 ───────────────────────────────────────────────── */
let domesticTimer = null;
let selectedDomesticCode = 'KRW-BTC';
const exchangeCodes = ['UPBIT','BITHUMB','COINONE','KORBIT'];
let domPriceMap = {};

async function getCryptoInfo(marketCode) {
  currentMarketCode = marketCode;
  const res = await apiFetch('/api/crypto/' + marketCode);
  if (!res.ok) return;
  const data = await res.json();
  const sym = data.marketCode?.split('-')[1] ?? 'BTC';

  setText('crypto_korean_name', data.koreanName ?? '-');
  setText('crypto_symbol_name', data.marketCode ?? '-');
  setText('buy_symbol_name',    `${data.koreanName}(${sym})`);
  setText('sell_symbol_name',   `${data.koreanName}(${sym})`);
  setText('holdCryptoCount',    data.buyCryptoCount ?? 0);
  setText('holdCryptoSymbol',   sym);

  startDomesticPolling(marketCode);
}

function startDomesticPolling(marketCode) {
  selectedDomesticCode = marketCode;
  domPriceMap = {};
  renderInlineDomesticBar();
  fetchDomesticPrices(marketCode);
  if (domesticTimer) clearInterval(domesticTimer);
  domesticTimer = setInterval(() => fetchDomesticPrices(selectedDomesticCode), 5000);
}

async function fetchDomesticPrices(code) {
  try {
    const res  = await apiFetch('/api/crypto/' + encodeURIComponent(code) + '/domestic-prices');
    const data = await res.json();
    setText('domestic_price_symbol', data.symbol ?? 'BTC');
    setText('domestic_price_updated_at', '갱신 ' + (data.fetchedAt ? new Date(data.fetchedAt).toLocaleTimeString('ko-KR',{hour12:false}) : '-'));
    domPriceMap = {};
    (data.prices ?? []).forEach(p => { domPriceMap[p.exchangeCode] = p.tradePriceKrw; });
    renderInlineDomesticBar();
    updateChartPriceLines();
    updateSelectedExchangeDisplay();
  } catch {}
}

/* 거래소 인라인 바 렌더 */
function renderInlineDomesticBar() {
  exchangeCodes.forEach(code => {
    const cell = document.getElementById('domestic-price-' + code);
    const item = document.querySelector(`.dom-inline-item[data-exchange="${code}"]`);
    const p = domPriceMap[code];
    if (cell) cell.textContent = p != null ? new Intl.NumberFormat('ko-KR').format(p) : '-';
    if (item) item.classList.toggle('selected', code === selectedExchange);
  });
}

/* 선택 거래소 현재가 업데이트 */
function updateSelectedExchangeDisplay() {
  const meta  = EXCHANGE_META[selectedExchange] ?? EXCHANGE_META.UPBIT;
  const price = domPriceMap[selectedExchange];
  setText('selectedExchangeLabel', meta.label);
  const el = document.getElementById('selectedExchangePrice');
  if (el) {
    el.textContent = price != null ? new Intl.NumberFormat('ko-KR').format(price) : '-';
    el.style.color = meta.color;
  }
}

/* 차트에 거래소별 가격선 오버레이 */
function updateChartPriceLines() {
  if (!lwCandle) return;
  // 기존 가격선 제거
  Object.values(priceLinesMap).forEach(pl => { try { lwCandle.removePriceLine(pl); } catch {} });
  priceLinesMap = {};

  // 각 거래소 가격선 추가 (Upbit 제외 — 캔들 자체가 Upbit)
  exchangeCodes.forEach(code => {
    const price = domPriceMap[code];
    if (price == null || price <= 0) return;
    const meta  = EXCHANGE_META[code] ?? {};
    const isSelected = code === selectedExchange;
    priceLinesMap[code] = lwCandle.createPriceLine({
      price,
      color:            meta.color,
      lineWidth:        isSelected ? 2 : 1,
      lineStyle:        isSelected ? LightweightCharts.LineStyle.Solid : LightweightCharts.LineStyle.Dashed,
      axisLabelVisible: isSelected,
      title:            isSelected ? meta.label : '',
    });
  });
}

/* 거래소 탭 클릭 핸들러 */
document.getElementById('exchangeTabs')?.addEventListener('click', e => {
  const btn = e.target.closest('.exchange-tab');
  if (!btn) return;
  selectedExchange = btn.dataset.exchange;
  document.querySelectorAll('.exchange-tab').forEach(b => b.classList.toggle('active', b === btn));
  renderInlineDomesticBar();
  updateChartPriceLines();
  updateSelectedExchangeDisplay();
});

/* 인라인 바 클릭으로도 거래소 선택 */
document.addEventListener('click', e => {
  const item = e.target.closest('.dom-inline-item');
  if (!item) return;
  const code = item.dataset.exchange;
  if (!code) return;
  selectedExchange = code;
  document.querySelectorAll('.exchange-tab').forEach(b => b.classList.toggle('active', b.dataset.exchange === code));
  renderInlineDomesticBar();
  updateChartPriceLines();
  updateSelectedExchangeDisplay();
});

/* ── 보유자산 표시 ───────────────────────────────────────────────────────── */
async function updateAssetDisplay() {
  const el = document.getElementById('holdAsset');
  if (!el) return;
  const user = currentUser ?? await getCurrentUser();
  if (user?.loggedIn) {
    el.textContent = new Intl.NumberFormat('ko-KR').format(user.asset);
  } else {
    const disp = document.getElementById('buyAssetDisplay');
    if (disp) disp.innerHTML = '<span style="font-size:12px;color:var(--muted);">로그인 필요</span>';
    el.textContent = '0';
  }
}

/* ── 퍼센트 버튼 ─────────────────────────────────────────────────────────── */
document.querySelectorAll('#buyQuantityBtnGroup > button').forEach(btn =>
  btn.addEventListener('click', () => {
    const asset = parseInt(document.getElementById('holdAsset').textContent.replaceAll(',', '')) || 0;
    const pct   = parseInt(btn.textContent) / 100;
    document.getElementById('buyKrw').value = new Intl.NumberFormat('ko-KR').format(Math.floor(asset * pct));
  })
);
document.querySelectorAll('#sellQuantityBtnGroup > button').forEach(btn =>
  btn.addEventListener('click', () => {
    const count = parseFloat(document.getElementById('holdCryptoCount').textContent) || 0;
    const pct   = parseInt(btn.textContent) / 100;
    document.getElementById('sellCount').value = Math.round(count * pct * 1e8) / 1e8;
  })
);

/* ── 매수 ────────────────────────────────────────────────────────────────── */
async function submitBuy() {
  if (!currentUser?.loggedIn) { location.href = '/member/login.html'; return; }
  clearOrderErrors();
  const res  = await apiFetch('/api/trade/order/buy', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ marketCode: currentMarketCode, buyKrw: document.getElementById('buyKrw').value }),
  });
  const data = await res.json();
  if (res.ok) {
    document.getElementById('holdAsset').textContent = new Intl.NumberFormat('ko-KR').format(data.asset);
    document.getElementById('buyKrw').value = '';
    await getCryptoInfo(currentMarketCode);
  } else {
    showOrderError('buyError', data.error ?? '매수 실패');
  }
}

/* ── 매도 ────────────────────────────────────────────────────────────────── */
async function submitSell() {
  if (!currentUser?.loggedIn) { location.href = '/member/login.html'; return; }
  clearOrderErrors();
  const res  = await apiFetch('/api/trade/order/sell', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ marketCode: currentMarketCode, sellCount: document.getElementById('sellCount').value }),
  });
  const data = await res.json();
  if (res.ok) {
    document.getElementById('holdAsset').textContent = new Intl.NumberFormat('ko-KR').format(data.asset);
    document.getElementById('sellCount').value = '';
    await getCryptoInfo(currentMarketCode);
  } else {
    showOrderError('sellError', data.error ?? '매도 실패');
  }
}

function clearOrderErrors() {
  ['buyError','sellError'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.style.display = 'none'; el.textContent = ''; }
  });
}
function showOrderError(id, msg) {
  const el = document.getElementById(id);
  if (el) { el.textContent = msg; el.style.display = 'block'; }
}

/* ── 관심종목 ────────────────────────────────────────────────────────────── */
function saveCryptoWatchlist() { localStorage.setItem(CRYPTO_WATCH_KEY, JSON.stringify([...cryptoWatchlist])); }
function renderCryptoWatchBtns() {
  cryptoWatchlist.forEach(code => {
    const btn = document.getElementById(code + '-watch-btn');
    if (btn) { btn.textContent = '⭐'; btn.style.color = '#FFCC00'; }
  });
}
function toggleCryptoWatch(code) {
  const btn = document.getElementById(code + '-watch-btn');
  if (cryptoWatchlist.has(code)) {
    cryptoWatchlist.delete(code);
    if (btn) { btn.textContent = '☆'; btn.style.color = 'var(--muted)'; }
  } else {
    cryptoWatchlist.add(code);
    if (btn) { btn.textContent = '⭐'; btn.style.color = '#FFCC00'; }
  }
  saveCryptoWatchlist();
}

/* ── 유틸 ────────────────────────────────────────────────────────────────── */
function setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }
