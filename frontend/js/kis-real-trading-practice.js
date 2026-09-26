(() => {
  const base = window.APP_CONFIG?.apiBase || '';
  let user = null;
  let side = 'BUY';
  let quote = null;
  let chartRows = [];
  let chartPeriod = '1m';
  let accountState = { cash: 0, totalAsset: 0 };
  let positionsState = [];
  let stocksState = [];

  const el = id => document.getElementById(id);
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
    document.querySelectorAll('.watch-item').forEach(item => item.classList.toggle('active', item.dataset.symbol === selectedSymbol()));
    updateEstimate();
  }

  async function loadQuote() {
    const data = await jsonFetch(`/api/broker-test/kis/quote?symbol=${encodeURIComponent(selectedSymbol())}`);
    const raw = data.quote || {};
    const label = el('stockSelect').selectedOptions[0]?.textContent || selectedSymbol();
    quote = { ...raw, name: label.replace(/\s*\([0-9]{6}\)\s*$/, ''), market: 'KRX' };
    updateQuoteView();
  }

  async function loadChart() {
    const state = el('chartState');
    state.textContent = '차트 불러오는 중…'; state.classList.remove('hidden');
    try {
      const days = { '1w':7, '1m':30, '3m':90, '1y':365 }[chartPeriod] || 30;
      const data = await jsonFetch(`/api/broker-test/kis/chart?symbol=${encodeURIComponent(selectedSymbol())}&days=${days}`);
      chartRows = (data.chart?.candles || []).map(row => ({ x:`${String(row.date).slice(0,4)}-${String(row.date).slice(4,6)}-${String(row.date).slice(6,8)}`, c:Number(row.close) })).reverse();
      drawChart();
      state.classList.toggle('hidden', chartRows.length > 0);
      if (!chartRows.length) state.textContent = '표시할 차트 데이터가 없습니다.';
    } catch (error) { chartRows = []; state.textContent = error.message; }
  }

  async function loadSelectedStock() {
    await Promise.all([loadQuote(), loadChart()]);
  }

  function drawChart() {
    const canvas = el('priceChart');
    if (!canvas || !chartRows.length) return;
    const rect = canvas.getBoundingClientRect();
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.max(1, Math.round(rect.width * ratio)); canvas.height = Math.max(1, Math.round(rect.height * ratio));
    const context = canvas.getContext('2d'); context.scale(ratio, ratio);
    const width = rect.width, height = rect.height, pad = { left:12, right:68, top:14, bottom:24 };
    const closes = chartRows.map(row => Number(row.c)).filter(Number.isFinite);
    const low = Math.min(...closes), high = Math.max(...closes), spread = Math.max(high - low, high * .01, 1);
    const x = index => pad.left + index / Math.max(chartRows.length - 1, 1) * (width - pad.left - pad.right);
    const y = value => pad.top + (high + spread * .08 - value) / (spread * 1.16) * (height - pad.top - pad.bottom);
    context.clearRect(0, 0, width, height); context.font = '10px Pretendard, sans-serif';
    for (let line = 0; line < 4; line++) {
      const lineY = pad.top + line / 3 * (height - pad.top - pad.bottom);
      context.beginPath(); context.moveTo(pad.left, lineY); context.lineTo(width - pad.right, lineY); context.strokeStyle = '#edf1f6'; context.stroke();
      const label = high + spread * .08 - line / 3 * spread * 1.16;
      context.fillStyle = '#8794a6'; context.fillText(number(Math.round(label)), width - pad.right + 8, lineY + 3);
    }
    const rising = closes.at(-1) >= closes[0], color = rising ? '#e11d48' : '#2563eb';
    context.beginPath(); chartRows.forEach((row, index) => index ? context.lineTo(x(index), y(Number(row.c))) : context.moveTo(x(index), y(Number(row.c))));
    context.lineWidth = 2; context.strokeStyle = color; context.stroke();
    const gradient = context.createLinearGradient(0, pad.top, 0, height - pad.bottom); gradient.addColorStop(0, rising ? 'rgba(225,29,72,.18)' : 'rgba(37,99,235,.18)'); gradient.addColorStop(1, 'rgba(255,255,255,0)');
    context.lineTo(x(chartRows.length - 1), height - pad.bottom); context.lineTo(x(0), height - pad.bottom); context.closePath(); context.fillStyle = gradient; context.fill();
    const firstDate = new Date(chartRows[0].x), lastDate = new Date(chartRows.at(-1).x);
    context.fillStyle = '#8794a6'; context.fillText(firstDate.toLocaleDateString('ko-KR',{month:'2-digit',day:'2-digit'}), pad.left, height - 5);
    const lastLabel = lastDate.toLocaleDateString('ko-KR',{month:'2-digit',day:'2-digit'}); context.fillText(lastLabel, width - pad.right - 35, height - 5);
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

  async function submitOrder() {
    const quantity = Number(el('quantity').value);
    if (!Number.isInteger(quantity) || quantity < 1) { setMessage('주문수량은 1주 이상의 정수여야 합니다.'); return; }
    const orderType = el('orderType').value;
    const price = orderType === 'LIMIT' ? Number(el('limitPrice').value) : 0;
    if (orderType === 'LIMIT' && (!Number.isInteger(price) || price < 1)) { setMessage('지정가는 1원 이상의 정수여야 합니다.'); return; }
    const intent = { symbol:selectedSymbol(), side, quantity, orderType, price };
    const label = `${quote?.name || selectedSymbol()} ${quantity}주 ${side === 'BUY' ? '매수' : '매도'} ${orderType === 'MARKET' ? '시장가' : won(price)}`;
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
    document.querySelectorAll('.side-btn[data-side]').forEach(item => item.classList.toggle('active', item.dataset.side === side));
    el('orderBtn').textContent = `${side === 'BUY' ? '매수' : '매도'} 주문`; el('orderBtn').classList.toggle('sell', side === 'SELL'); updateEstimate();
  }

  function bindEvents() {
    document.querySelectorAll('.side-btn[data-side]').forEach(button => button.addEventListener('click', () => setSide(button.dataset.side)));
    document.querySelectorAll('[data-period]').forEach(button => button.addEventListener('click', async () => {
      chartPeriod = button.dataset.period; document.querySelectorAll('[data-period]').forEach(item => item.classList.toggle('active', item === button)); await loadChart();
    }));
    document.querySelectorAll('.portfolio-tabs [data-tab]').forEach(button => button.addEventListener('click', () => {
      document.querySelectorAll('.portfolio-tabs [data-tab]').forEach(item => item.classList.toggle('active', item === button));
      document.querySelectorAll('[data-tab-panel]').forEach(panel => { panel.hidden = panel.dataset.tabPanel !== button.dataset.tab; });
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
    let resizeTimer; window.addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(drawChart, 120); });
  }

  document.addEventListener('DOMContentLoaded', async () => {
    user = await initPage({ requireAuth: true }); if (!user) return;
    bindEvents();
    const results = await Promise.allSettled([loadRealStatus(), loadMarket(), loadStocks(), refreshAccount()]);
    const failed = results.find(result => result.status === 'rejected'); if (failed) setMessage(failed.reason?.message || '일부 데이터를 불러오지 못했습니다.');
  });
})();
