(() => {
  const apiBase = window.APP_CONFIG?.apiBase || '';
  const exchange = document.body.dataset.exchange;
  const symbolInput = document.getElementById('symbol');
  const result = document.getElementById('result');
  const symbolSearch = document.getElementById('symbol-search');
  const quoteFilter = document.getElementById('quote-filter');
  const symbolList = document.getElementById('symbol-list');
  const symbolMeta = document.getElementById('symbol-meta');
  const normalizeSymbol = (value) => value.trim().toUpperCase().replace(/[\s/_-]/g, '');
  const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));

  const run = async (kind) => {
    const symbol = exchange === 'binance' ? normalizeSymbol(symbolInput.value) : symbolInput.value.trim();
    if (!symbol) { result.textContent = '거래쌍을 입력하세요.'; return; }
    symbolInput.value = symbol;
    const button = document.querySelector(`[data-test="${kind}"]`);
    button.disabled = true; result.classList.remove('error'); result.textContent = '거래소 공개 API를 조회하는 중…';
    try {
      const response = await fetch(`${apiBase}/api/crypto-exchange-test/${exchange}/${kind}?symbol=${encodeURIComponent(symbol)}`);
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.message || '조회에 실패했습니다.');
      result.textContent = JSON.stringify(data.result, null, 2);
    } catch (error) { result.classList.add('error'); result.textContent = `조회 실패\n${error.message}`; }
    finally { button.disabled = false; }
  };

  const selectSymbol = (symbol, fetchTicker = false) => {
    if (!symbolInput) return;
    symbolInput.value = symbol;
    document.querySelectorAll('.symbol-item').forEach((item) => item.classList.toggle('selected', item.dataset.symbol === symbol));
    if (fetchTicker) run('ticker');
  };

  const renderSymbols = (payload) => {
    const rows = payload.symbols || [];
    symbolMeta.textContent = `${payload.totalMatches.toLocaleString('ko-KR')}개 중 ${rows.length}개 표시 · 클릭하면 시세를 조회합니다.`;
    if (!rows.length) {
      symbolList.innerHTML = '<div class="note">일치하는 거래 가능 Spot 심볼이 없습니다. 검색어나 결제 자산을 바꿔 보세요.</div>';
      return;
    }
    symbolList.innerHTML = rows.map((row) => `<button class="symbol-item" type="button" role="option" data-symbol="${escapeHtml(row.symbol)}"><span><b>${escapeHtml(row.symbol)}</b><small>${escapeHtml(row.baseAsset)} / ${escapeHtml(row.quoteAsset)}</small></span><span>${escapeHtml(row.status)}</span></button>`).join('');
    symbolList.querySelectorAll('.symbol-item').forEach((item) => item.addEventListener('click', () => selectSymbol(item.dataset.symbol, true)));
  };

  const searchSymbols = async () => {
    if (!symbolList) return;
    const button = document.getElementById('search-symbols');
    const query = normalizeSymbol(symbolSearch.value);
    symbolSearch.value = query;
    button.disabled = true;
    symbolMeta.textContent = 'Binance Spot 심볼을 검색하는 중…';
    symbolList.innerHTML = '';
    try {
      const params = new URLSearchParams({ q: query, quote: quoteFilter.value, limit: '100' });
      const response = await fetch(`${apiBase}/api/crypto-exchange-test/binance/symbols?${params}`);
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.message || '심볼 검색에 실패했습니다.');
      renderSymbols(data.result);
    } catch (error) {
      symbolMeta.textContent = '심볼 검색 실패';
      symbolList.innerHTML = `<div class="note">${escapeHtml(error.message)}</div>`;
    } finally {
      button.disabled = false;
    }
  };

  const boot = () => {
    document.querySelectorAll('[data-test]').forEach((button) => button.addEventListener('click', () => run(button.dataset.test)));
    if (symbolList) {
      document.getElementById('search-symbols').addEventListener('click', searchSymbols);
      symbolSearch.addEventListener('keydown', (event) => { if (event.key === 'Enter') searchSymbols(); });
      quoteFilter.addEventListener('change', searchSymbols);
      document.querySelectorAll('[data-symbol-preset]').forEach((button) => button.addEventListener('click', () => {
        const symbol = button.dataset.symbolPreset;
        symbolSearch.value = symbol;
        quoteFilter.value = symbol.endsWith('USDT') ? 'USDT' : '';
        selectSymbol(symbol, true);
        searchSymbols();
      }));
      searchSymbols();
    }
    // 첫 화면에서도 연결 상태를 바로 확인할 수 있게 기본 시세를 1회 조회한다.
    run('ticker');
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
