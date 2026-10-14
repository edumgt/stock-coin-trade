(() => {
  const base = window.APP_CONFIG?.apiBase || '';
  // 단독 페이지(kis-real-trading-practice.html)에서는 document 전체, trade/stock.html 의 「KIS 모의투자」 탭처럼
  // 다른 화면에 삽입될 때는 [data-kis-root] 안에서만 요소를 찾고 id 에 data-kis-id-prefix(예: "kis-") 를 붙인다.
  const root = document.querySelector('[data-kis-root]') || document;
  const embedded = root !== document;
  const idPrefix = embedded ? (root.dataset.kisIdPrefix || '') : '';
  let user = null;
  let side = 'BUY';
  let quote = null;
  let chartRows = [];
  let chartPeriod = '1m';
  let chart, candleSeries, volumeSeries, chartController, chartSequence = 0;
  let accountState = { cash: 0, totalAsset: 0 };
  let positionsState = [];
  let stocksState = [];

  const el = id => document.getElementById(idPrefix + id);
  const number = value => Number(value || 0).toLocaleString('ko-KR');
  const won = value => `${number(Math.round(Number(value || 0)))}원`;
  const signedWon = value => `${Number(value || 0) > 0 ? '+' : ''}${won(value)}`;
  const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));

  async function jsonFetch(path, options = {}) {
    const response = await fetch(base + path, { credentials: 'include', ...options });
    const text = await response.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch { data = { message: `서버 응답을 해석할 수 없습니다 (HTTP ${response.status}).` }; }
    if (!response.ok) {
      const error = new Error(data.message || '요청을 처리하지 못했습니다.');
      error.status = response.status;
      error.data = data;
      throw error;
    }
    return data;
  }

  function selectedSymbol() { return el('stockSelect').value; }
  function valueClass(value) { return Number(value) > 0 ? 'profit' : Number(value) < 0 ? 'loss' : ''; }
  function setLoading(button, loading) { button?.classList.toggle('loading', loading); if (button) button.disabled = loading; }

  function setSetupState(id, ready, label) {
    const item = el(id);
    item.classList.toggle('ready', ready);
    item.textContent = `${ready ? '✓' : '○'} ${label}`;
  }

  async function loadRealStatus() {
    const data = await jsonFetch('/api/broker-test/kis/status');
    const status = data.status;
    setSetupState('realAppKeyState', status.credentials, '모의 App Key/Secret');
    setSetupState('realAccountState', status.account, '모의 계좌번호');
    setSetupState('realOwnerState', status.environment === 'paper', 'Paper 환경');
    setSetupState('realSecretState', String(status.testbedUrl || '').includes('openapivts'), 'Testbed 도메인');
    el('realBalanceBtn').disabled = !status.ready;
    el('orderBtn').disabled = !status.ready;
    el('realStatus').className = `message show ${status.ready ? 'success' : 'error'}`;
    el('realStatus').innerHTML = `<strong>${status.ready ? 'KIS 모의투자 연결 준비 완료' : 'KIS 모의투자 설정 필요'}</strong><br>${escapeHtml(status.message || '')}`;
  }

  async function loadRealBalance() {
    const button = el('realBalanceBtn');
    setLoading(button, true);
    try { await refreshAccount(); }
    catch (error) { setMessage(error.message); }
    finally { setLoading(button, false); }
  }

  function renderWatchlist(stocks) {
    stocksState = stocks;
    el('watchlistBody').innerHTML = stocks.length ? stocks.slice(0, 18).map(stock => `<button type="button" class="watch-item${stock.symbol === selectedSymbol() ? ' active' : ''}" data-symbol="${escapeHtml(stock.symbol)}"><b>${escapeHtml(stock.name)}</b><small>${escapeHtml(stock.symbol)} · ${escapeHtml(stock.market || 'KRX')}</small><span>선택</span></button>`).join('') : '<div class="watch-skeleton">검색 결과가 없습니다.</div>';
  }

  async function loadStocks(query = '') {
    const path = query ? `/api/stocks/search?q=${encodeURIComponent(query)}&limit=30` : '/api/stocks/list?limit=50';
    const data = await jsonFetch(path);
    let stocks = data.stocks || [];
    if (!query && !stocks.some(stock => stock.symbol === '005930')) stocks = [{ symbol:'005930', name:'삼성전자', market:'KOSPI' }, ...stocks];
    if (!stocks.length) { renderWatchlist([]); return; }
    const select = el('stockSelect');
    const previous = selectedSymbol();
    select.innerHTML = stocks.map(stock => `<option value="${escapeHtml(stock.symbol)}">${escapeHtml(stock.name)} (${escapeHtml(stock.symbol)})</option>`).join('');
    select.value = query ? stocks[0].symbol : (stocks.some(stock => stock.symbol === previous) ? previous : stocks[0].symbol);
    renderWatchlist(stocks);
    await loadSelectedStock();
  }

  function updateQuoteView() {
    const rate = Number(quote?.changeRate || 0);
    const change = Number(quote?.change || 0);
    el('quoteName').textContent = quote?.name || selectedSymbol();
    el('quoteSymbol').textContent = quote?.symbol || selectedSymbol();
    el('quoteMarket').textContent = quote?.market || 'KRX';
    el('quotePrice').textContent = won(quote?.price);
    el('quoteChange').textContent = `${rate > 0 ? '+' : ''}${rate.toFixed(2)}%`;
    el('quoteChange').className = valueClass(rate);
    el('quotePrevClose').textContent = won(quote?.prevClose || quote?.price);
    el('quoteDelta').textContent = signedWon(change);
    el('quoteDelta').className = valueClass(change);
    el('quoteVolume').textContent = `${number(quote?.volume)}주`;
    el('orderSymbolName').textContent = `${quote?.name || selectedSymbol()} · ${selectedSymbol()}`;
    el('orderCurrentPrice').textContent = won(quote?.price);
    el('estimatedPrice').textContent = won(quote?.price);
    root.querySelectorAll('.watch-item').forEach(item => item.classList.toggle('active', item.dataset.symbol === selectedSymbol()));
    updateEstimate();
  }

  async function loadQuote() {
    const data = await jsonFetch(`/api/broker-test/kis/quote?symbol=${encodeURIComponent(selectedSymbol())}`);
    const raw = data.quote || {};
    const label = el('stockSelect').selectedOptions[0]?.textContent || selectedSymbol();
    quote = { ...raw, name: label.replace(/\s*\([0-9]{6}\)\s*$/, ''), market: 'KRX' };
    updateQuoteView();
  }

  function ensureChart() {
    if (chart) return;
    const L = window.LightweightCharts;
    if (!L) throw new Error('차트 라이브러리를 불러오지 못했습니다. 새로고침해 주세요.');
    let host = el('priceChart');
    // Preserve compatibility with hosts that still embed the previous canvas markup.
    if (host.tagName === 'CANVAS') {
      const container = document.createElement('div'); container.id = host.id;
      container.setAttribute('aria-label', '선택 종목 캔들 및 거래량 차트');
      host.replaceWith(container); host = container;
    }
    chart = L.createChart(host, {
      autoSize: true,
      layout: { background: { color: '#ffffff' }, textColor: '#5d7389', fontSize: 13, attributionLogo: true },
      grid: { vertLines: { color: '#edf2f6' }, horzLines: { color: '#edf2f6' } },
      localization: { locale: 'ko-KR', priceFormatter: value => number(Math.round(value)) },
      timeScale: { timeVisible: false, borderColor: '#bdcbd9' },
      rightPriceScale: { borderColor: '#bdcbd9', scaleMargins: { top: .08, bottom: .27 } },
    });
    candleSeries = chart.addSeries(L.CandlestickSeries, {
      upColor: '#e84250', downColor: '#287ccb', borderVisible: false,
      wickUpColor: '#e84250', wickDownColor: '#287ccb',
      priceFormat: { type: 'price', precision: 0, minMove: 1 },
    });
    volumeSeries = chart.addSeries(L.HistogramSeries, { priceScaleId: 'volume', priceFormat: { type: 'volume' } });
    chart.priceScale('volume').applyOptions({ scaleMargins: { top: .8, bottom: 0 } });
    chart.subscribeCrosshairMove(event => {
      const row = event.seriesData.get(candleSeries);
      if (row) showChartDetail(row, event.seriesData.get(volumeSeries)?.value);
      else if (chartRows.length) showChartDetail(chartRows.at(-1), chartRows.at(-1).volume);
    });
  }

  function showChartDetail(row, volume) {
    const date = typeof row.time === 'string' ? row.time : `${row.time.year}-${String(row.time.month).padStart(2, '0')}-${String(row.time.day).padStart(2, '0')}`;
    if (el('chartDetail')) el('chartDetail').textContent = `${date} · 시가 ${won(row.open)} · 고가 ${won(row.high)} · 저가 ${won(row.low)} · 종가 ${won(row.close)} · 거래량 ${number(volume ?? row.volume)}주`;
  }

  function clearChart() {
    chartRows = []; candleSeries?.setData([]); volumeSeries?.setData([]);
    if (el('chartDetail')) el('chartDetail').textContent = '';
    if (el('chartMeta')) el('chartMeta').textContent = '';
  }

  async function loadChart() {
    const sequence = ++chartSequence;
    chartController?.abort(); chartController = new AbortController();
    const state = el('chartState');
    state.textContent = '차트 불러오는 중…'; state.classList.remove('hidden');
    clearChart();
    try {
      ensureChart();
      const days = { '1w':7, '1m':30, '3m':90, '1y':365 }[chartPeriod] || 30;
      const symbol = selectedSymbol();
      const data = await jsonFetch(`/api/broker-test/kis/chart?symbol=${encodeURIComponent(symbol)}&days=${days}`, { signal: chartController.signal });
      if (sequence !== chartSequence) return;
      const byDate = new Map();
      for (const row of data.chart?.candles || []) {
        const raw = String(row.date || '').replace(/-/g, '');
        if (!/^\d{8}$/.test(raw)) continue;
        const time = `${raw.slice(0,4)}-${raw.slice(4,6)}-${raw.slice(6,8)}`;
        const date = new Date(time + 'T00:00:00Z');
        if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0,10) !== time) continue;
        const item = { time, open: Number(row.open), high: Number(row.high), low: Number(row.low), close: Number(row.close), volume: Number(row.volume) };
        if (![item.open,item.high,item.low,item.close,item.volume].every(Number.isFinite) || item.low <= 0 || item.volume < 0 || item.low > Math.min(item.open,item.close) || item.high < Math.max(item.open,item.close)) continue;
        byDate.set(time, item);
      }
      chartRows = [...byDate.values()].sort((a,b) => a.time.localeCompare(b.time));
      candleSeries.setData(chartRows.map(({ time,open,high,low,close }) => ({ time,open,high,low,close })));
      volumeSeries.setData(chartRows.map(row => ({ time: row.time, value: row.volume, color: row.close >= row.open ? '#e8425066' : '#287ccb66' })));
      chart.timeScale().fitContent();
      state.classList.toggle('hidden', chartRows.length > 0);
      if (!chartRows.length) state.textContent = '표시할 차트 데이터가 없습니다.';
      else {
        showChartDetail(chartRows.at(-1), chartRows.at(-1).volume);
        if (el('chartMeta')) el('chartMeta').textContent = `KIS Testbed · ${symbol} · ${chartRows.length}개 일봉 · ${chartRows[0].time} ~ ${chartRows.at(-1).time} · 조회 ${new Date().toLocaleTimeString('ko-KR', { timeZone: 'Asia/Seoul' })} KST`;
      }
    } catch (error) {
      if (sequence !== chartSequence || error.name === 'AbortError') return;
      clearChart(); state.textContent = error.message;
    }
  }

  async function loadSelectedStock() {
    await Promise.all([loadQuote(), loadChart()]);
  }

  function updateEstimate() {
    const quantity = Math.max(0, Math.floor(Number(el('quantity').value) || 0));
    const orderPrice = el('orderType').value === 'LIMIT' ? Number(el('limitPrice').value || 0) : Number(quote?.price || 0);
    el('estimatedPrice').textContent = orderPrice ? won(orderPrice) : '-';
    el('estimatedAmount').textContent = orderPrice && quantity ? won(orderPrice * quantity) : '-';
    const position = positionsState.find(item => item.symbol === selectedSymbol());
    const available = side === 'BUY' ? Math.floor(Number(accountState.cash || 0) / Math.max(Number(quote?.price || 0), 1)) : Number(position?.quantity || 0);
    el('orderAvailability').textContent = side === 'BUY' ? `매수 가능 ${number(available)}주 · 예수금 ${won(accountState.cash)}` : `매도 가능 ${number(available)}주`;
  }

  function setMessage(message, type = 'error', detail = '') {
    const box = el('orderMessage'); box.className = `message show ${type}`;
    box.innerHTML = `<strong>${escapeHtml(message)}</strong>${detail ? `<br>${escapeHtml(detail)}` : ''}`;
  }

  function renderPositions(positions) {
    el('positionsBadge').textContent = positions.length;
    el('positionsBody').innerHTML = positions.length ? positions.map(position => {
      const rate = Number(position.profitLossRate || 0);
      return `<tr data-symbol="${escapeHtml(position.symbol)}"><td class="symbol-cell"><b>${escapeHtml(position.name)}</b><small>${escapeHtml(position.symbol)}</small></td><td>${number(position.quantity)}주</td><td>${won(position.avgPrice)}</td><td>${won(position.currentPrice)}</td><td>${won(position.evalAmount)}</td><td class="${valueClass(position.profitLoss)}">${signedWon(position.profitLoss)}</td><td class="${valueClass(rate)}">${rate > 0 ? '+' : ''}${rate.toFixed(2)}%</td></tr>`;
    }).join('') : '<tr><td colspan="7" class="empty">보유종목이 없습니다. 종목을 선택해 첫 모의주문을 시작해보세요.</td></tr>';
  }

  function renderHistory(history) {
    el('ordersBadge').textContent = history.length;
    el('historyBody').innerHTML = history.length ? history.map(order => {
      const time = String(order.orderTime || '').padStart(6, '0');
      const quantity = Number(order.filledQuantity || order.orderQuantity || 0);
      const price = Number(order.filledPrice || order.orderPrice || 0);
      return `<tr><td>${escapeHtml(`${time.slice(0,2)}:${time.slice(2,4)}:${time.slice(4,6)}`)}</td><td class="symbol-cell"><b>${escapeHtml(order.name || order.symbol)}</b><small>${escapeHtml(order.symbol)}</small></td><td class="${order.side === 'BUY' ? 'trade-buy' : 'trade-sell'}">${order.side === 'BUY' ? '매수' : '매도'}</td><td>${number(quantity)}주</td><td>${won(price)}</td><td>${won(quantity * price)}</td></tr>`;
    }).join('') : '<tr><td colspan="6" class="empty">오늘 KIS 주문내역이 없습니다.</td></tr>';
  }

  async function refreshAccount() {
    const [balanceData, historyData] = await Promise.all([
      jsonFetch('/api/broker-test/kis/balance'), jsonFetch('/api/broker-test/kis/orders?limit=50'),
    ]);
    const balance = balanceData.balance || {};
    accountState = { cash:Number(balance.cashBalance || 0), totalAsset:Number(balance.totalEvalAmount || 0) };
    positionsState = balance.holdings || [];
    el('cash').textContent = won(accountState.cash); el('totalAsset').textContent = won(accountState.totalAsset);
    const pnl = Number(balance.totalProfitLoss || 0); el('pnlRate').textContent = signedWon(pnl); el('pnlRate').className = valueClass(pnl);
    el('positionCount').textContent = `${positionsState.length}종목`; el('holdingValue').textContent = `평가금액 ${won(Math.max(0, accountState.totalAsset - accountState.cash))}`;
    renderPositions(positionsState); renderHistory(historyData.history?.orders || []); updateEstimate();
  }

  async function loadMarket() {
    try {
      const [kospiData, kosdaqData] = await Promise.all([jsonFetch('/api/broker-test/kis/index?code=0001'), jsonFetch('/api/broker-test/kis/index?code=1001')]);
      [[kospiData.index,'kospi'],[kosdaqData.index,'kosdaq']].forEach(([item,prefix]) => {
        const value = item?.price || 0, rate = Number(item?.changeRate || 0);
        el(`${prefix}Value`).textContent = number(value); el(`${prefix}Change`).textContent = `${rate > 0 ? '+' : ''}${rate.toFixed(2)}%`; el(`${prefix}Change`).className = valueClass(rate);
      });
      el('marketTimestamp').textContent = `${new Date().toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit'})} 기준`;
    } catch { el('marketTimestamp').textContent = '지수 조회 지연'; }
  }

  function warnToast(message, detail = '', type = 'error') {
    if (typeof window.showToast === 'function') window.showToast(detail ? `${message} ${detail}` : message, { type, duration: type === 'error' ? 4500 : 3000 });
    setMessage(message, type === 'error' ? 'error' : 'success', detail);
  }

  async function precheckSell(symbol, quantity) {
    // 화면의 positionsState 는 마지막 조회 시점 값이므로 주문 직전에 잔고를 다시 받는다. 조회 실패 시 화면 상태로 판단한다.
    try { await refreshAccount(); } catch (_) { /* 조회 실패 — 기존 positionsState 로 판단 */ }
    const position = positionsState.find(item => item.symbol === symbol);
    const held = Number(position?.quantity || 0);
    const name = position?.name || quote?.name || symbol;
    if (held <= 0) return { ok:false, held, message:`${name} 보유 수량이 없어 매도할 수 없습니다.`, detail:'보유종목 탭에서 수량을 확인하세요.' };
    if (quantity > held) return { ok:false, held, message:`매도 수량 ${number(quantity)}주가 보유 ${number(held)}주를 초과합니다.`, detail:`매도 가능 ${number(held)}주 — 수량을 줄이거나 '최대' 를 누르세요.` };
    return { ok:true, held, sellAll: quantity === held };
  }

  async function submitOrder() {
    const quantity = Number(el('quantity').value);
    if (!Number.isInteger(quantity) || quantity < 1) { setMessage('주문수량은 1주 이상의 정수여야 합니다.'); return; }
    const orderType = el('orderType').value;
    const price = orderType === 'LIMIT' ? Number(el('limitPrice').value) : 0;
    if (orderType === 'LIMIT' && (!Number.isInteger(price) || price < 1)) { setMessage('지정가는 1원 이상의 정수여야 합니다.'); return; }
    const intent = { symbol:selectedSymbol(), side, quantity, orderType, price };
    const label = `${quote?.name || selectedSymbol()} ${quantity}주 ${side === 'BUY' ? '매수' : '매도'} ${orderType === 'MARKET' ? '시장가' : won(price)}`;
    if (side === 'SELL') {
      // 매도 사전 점검: 최신 보유수량으로 판단해 보유가 없거나 부족하면 토스트로 경고하고 주문을 보내지 않는다 (2026-10-06)
      const check = await precheckSell(intent.symbol, quantity);
      if (!check.ok) { warnToast(check.message, check.detail); return; }
      if (check.sellAll) warnToast(`${quote?.name || intent.symbol} 보유 ${number(check.held)}주를 전량 매도합니다.`, '', 'warn');
    }
    if (!window.confirm(`${label}\n\nKIS Testbed 모의계좌에 주문을 접수할까요?`)) return;
    const button = el('orderBtn'); button.disabled = true; el('orderMessage').className = 'message';
    try {
      const approval = await jsonFetch('/api/broker-test/kis/order-approval', {
        method: 'POST', headers: { 'Content-Type':'application/json', 'X-CSRF-Token': user.csrfToken || '' },
        body: JSON.stringify(intent),
      });
      const result = await jsonFetch('/api/broker-test/kis/orders', {
        method: 'POST', headers: { 'Content-Type':'application/json', 'X-CSRF-Token': user.csrfToken || '' },
        body: JSON.stringify({ ...intent, approvalToken:approval.approvalToken }),
      });
      setMessage('KIS Testbed 모의주문이 접수되었습니다.', 'success', `주문번호 ${result.order?.orderNo || '-'} · ${result.order?.message || ''}`);
      await Promise.all([refreshAccount(), loadQuote()]);
    } catch (error) {
      setMessage(error.message);
    } finally { button.disabled = false; }
  }

  function setSide(nextSide) {
    side = nextSide;
    root.querySelectorAll('.side-btn[data-side]').forEach(item => item.classList.toggle('active', item.dataset.side === side));
    el('orderBtn').textContent = `${side === 'BUY' ? '매수' : '매도'} 주문`; el('orderBtn').classList.toggle('sell', side === 'SELL'); updateEstimate();
    if (side === 'SELL') {
      const held = Number(positionsState.find(item => item.symbol === selectedSymbol())?.quantity || 0);
      if (held <= 0 && typeof window.showToast === 'function') window.showToast(`${quote?.name || selectedSymbol()} 은(는) 보유 수량이 없습니다. 매도 주문은 접수되지 않습니다.`, { type:'warn', duration:3500 });
    }
  }

  function bindEvents() {
    root.querySelectorAll('.side-btn[data-side]').forEach(button => button.addEventListener('click', () => setSide(button.dataset.side)));
    root.querySelectorAll('[data-period]').forEach(button => button.addEventListener('click', async () => {
      chartPeriod = button.dataset.period; root.querySelectorAll('[data-period]').forEach(item => item.classList.toggle('active', item === button)); await loadChart();
    }));
    root.querySelectorAll('.portfolio-tabs [data-tab]').forEach(button => button.addEventListener('click', () => {
      root.querySelectorAll('.portfolio-tabs [data-tab]').forEach(item => item.classList.toggle('active', item === button));
      root.querySelectorAll('[data-tab-panel]').forEach(panel => { panel.hidden = panel.dataset.tabPanel !== button.dataset.tab; });
    }));
    el('stockSelect').addEventListener('change', () => loadSelectedStock().catch(error => setMessage(error.message)));
    el('watchlistBody').addEventListener('click', event => { const button = event.target.closest('[data-symbol]'); if (!button) return; el('stockSelect').value = button.dataset.symbol; loadSelectedStock().catch(error => setMessage(error.message)); });
    el('positionsBody').addEventListener('click', event => { const row = event.target.closest('[data-symbol]'); if (!row) return; if (![...el('stockSelect').options].some(option => option.value === row.dataset.symbol)) el('stockSelect').add(new Option(row.querySelector('b')?.textContent || row.dataset.symbol, row.dataset.symbol)); el('stockSelect').value = row.dataset.symbol; loadSelectedStock().catch(error => setMessage(error.message)); window.scrollTo({top:el('stockSelect').getBoundingClientRect().top + scrollY - 90,behavior:'smooth'}); });
    el('orderType').addEventListener('change', () => {
      const limit = el('orderType').value === 'LIMIT';
      el('limitPrice').hidden = !limit; el('limitPriceLabel').hidden = !limit;
      el('orderTypeSummary').textContent = limit ? '지정가' : '시장가';
      if (limit && !el('limitPrice').value) el('limitPrice').value = Math.round(Number(quote?.price || 0));
      updateEstimate();
    });
    el('limitPrice').addEventListener('input', updateEstimate);
    el('quantity').addEventListener('input', updateEstimate); el('quantityMinus').addEventListener('click', () => { el('quantity').value = Math.max(1, Number(el('quantity').value || 1) - 1); updateEstimate(); }); el('quantityPlus').addEventListener('click', () => { el('quantity').value = Math.max(1, Number(el('quantity').value || 0) + 1); updateEstimate(); });
    el('maxQuantityBtn').addEventListener('click', () => { const position = positionsState.find(item => item.symbol === selectedSymbol()); const max = side === 'BUY' ? Math.floor(Number(accountState.cash || 0) / Math.max(Number(quote?.price || 0), 1)) : Number(position?.quantity || 0); el('quantity').value = Math.max(1, max); updateEstimate(); });
    el('orderBtn').addEventListener('click', submitOrder); el('realBalanceBtn').addEventListener('click', loadRealBalance);
    el('searchBtn').addEventListener('click', () => loadStocks(el('symbolSearch').value.trim()).catch(error => setMessage(error.message))); el('symbolSearch').addEventListener('keydown', event => { if (event.key === 'Enter') el('searchBtn').click(); });
    el('quoteRefreshBtn').addEventListener('click', async event => { setLoading(event.currentTarget, true); try { await loadSelectedStock(); } catch (error) { setMessage(error.message); } finally { setLoading(event.currentTarget, false); } });
    el('refreshAllBtn').addEventListener('click', async event => { setLoading(event.currentTarget, true); try { await Promise.all([loadMarket(),refreshAccount(),loadSelectedStock()]); } catch (error) { setMessage(error.message); } finally { setLoading(event.currentTarget, false); } });
    el('chartFit')?.addEventListener('click', () => chart?.timeScale().fitContent());
  }

  let booted = false;
  async function boot(currentUser) {
    if (booted) return; booted = true;
    user = currentUser;
    bindEvents();
    const results = await Promise.allSettled([loadRealStatus(), loadMarket(), loadStocks(), refreshAccount()]);
    const failed = results.find(result => result.status === 'rejected'); if (failed) setMessage(failed.reason?.message || '일부 데이터를 불러오지 못했습니다.');
  }

  if (embedded) {
    // 삽입 모드: 호스트 화면이 탭을 열 때 init() 을 부른다. 로그인이 안 돼 있으면 리다이렉트 대신 안내만 보여 준다.
    window.KisPaperPanel = {
      async init() {
        if (booted) return true;
        const currentUser = typeof getCurrentUser === 'function' ? await getCurrentUser() : null;
        if (!currentUser?.loggedIn) {
          const guide = el('realStatus');
          if (guide) { guide.className = 'message show error'; guide.innerHTML = '<strong>로그인이 필요합니다</strong><br>KIS 모의투자는 로그인한 회원만 사용할 수 있습니다. <a href="/member/login.html" style="font-weight:800;text-decoration:underline;">로그인</a>'; }
          const orderBtn = el('orderBtn'); if (orderBtn) orderBtn.disabled = true;
          return false;
        }
        await boot(currentUser);
        return true;
      },
      refresh: () => booted ? Promise.allSettled([loadMarket(), refreshAccount(), loadSelectedStock()]) : Promise.resolve(),
    };
  } else {
    document.addEventListener('DOMContentLoaded', async () => {
      const currentUser = await initPage({ requireAuth: true }); if (!currentUser) return;
      await boot(currentUser);
    });
  }
})();
