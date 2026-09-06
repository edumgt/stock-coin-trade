let markets = [], selected = null, category = '전체', chart, candleSeries, propertyMap, propertyMarkers = [];
let lastCash = 0, lastPositions = [];
const won = value => Number(value || 0).toLocaleString('ko-KR') + '원';

(async () => { await initPage({ requireAuth: true }); initChart(); await refresh(); setInterval(refresh, 60_000); })();

function initChart() {
  const el = document.getElementById('alternativeChart');
  if (!el || !window.LightweightCharts) return;
  chart = LightweightCharts.createChart(el, { height: 400, layout: { background: { color: '#fff' }, textColor: '#64748B' }, grid: { vertLines: { color: '#F1F5F9' }, horzLines: { color: '#F1F5F9' } }, rightPriceScale: { borderColor: '#E2E8F0' }, timeScale: { borderColor: '#E2E8F0' } });
  candleSeries = chart.addCandlestickSeries({ upColor: '#E11D48', downColor: '#2563EB', borderUpColor: '#E11D48', borderDownColor: '#2563EB', wickUpColor: '#E11D48', wickDownColor: '#2563EB' });
  window.addEventListener('resize', () => chart?.applyOptions({ width: el.clientWidth }));
}

async function refresh() {
  const [marketRes, meRes, positionRes] = await Promise.all([apiFetch('/api/alternatives/markets'), apiFetch('/api/member/me'), apiFetch('/api/alternatives/positions')]);
  if (!marketRes.ok) return;
  markets = (await marketRes.json()).markets || [];
  const me = await meRes.json(); lastCash = me.asset; document.getElementById('cash').textContent = won(me.asset);
  renderSideMenu(); renderMarkets(); renderPositions((await positionRes.json()).positions || []);
  await loadAltHistory();
  if (selected) {
    // 주문 체결 등으로 재조회할 때, 차트/지도는 다시 불러오지 않고 시세 표시만 최신화한다.
    selected = markets.find(item => item.symbol === selected.symbol) || selected;
    document.getElementById('viewPrice').textContent = won(selected.price);
    const rateColor = selected.changeRate >= 0 ? '#E11D48' : '#2563EB';
    document.getElementById('viewChangeRate').innerHTML = `<span style="color:${rateColor};">${selected.changeRate >= 0 ? '▲' : '▼'} ${Math.abs(selected.changeRate)}%</span>`;
    renderOrderBook(selected.price); updateAmount();
  } else if (markets.length) {
    selectMarket(markets[0].symbol);
  }
}

async function loadAltHistory() {
  const tbody = document.getElementById('altHistoryBody');
  if (!tbody) return;
  try {
    const res = await apiFetch('/api/alternatives/orders/history');
    const rows = res.ok ? (await res.json()).history || [] : [];
    tbody.innerHTML = rows.length ? rows.map(row => {
      const isBuy = row.type === 'BUY'; const color = isBuy ? '#E11D48' : '#2563EB';
      const dt = new Date(row.ts).toLocaleString('ko-KR', { hour12: false });
      return `<tr style="border-bottom:1px solid var(--border);">
        <td style="padding:8px 12px;color:var(--muted);font-size:13px;white-space:nowrap;">${dt}</td>
        <td style="padding:8px 12px;font-weight:700;color:var(--fg);font-size:14px;">${row.name}<br><span style="font-size:11px;color:var(--accent-dark);">${row.symbol}</span></td>
        <td style="padding:8px 12px;text-align:center;font-weight:800;font-size:14px;color:${color};">${isBuy ? '매수' : '매도'}</td>
        <td style="padding:8px 12px;text-align:right;color:var(--fg);font-size:14px;">${Number(row.quantity).toLocaleString('ko-KR')}</td>
        <td style="padding:8px 12px;text-align:right;color:var(--accent-dark);font-weight:700;font-size:14px;">${won(row.amount)}</td>
      </tr>`;
    }).join('') : '<tr><td colspan="5" style="padding:16px;text-align:center;color:var(--muted);">체결 내역이 없습니다.</td></tr>';
  } catch { tbody.innerHTML = '<tr><td colspan="5" style="padding:16px;text-align:center;color:var(--muted);">체결 내역을 불러오지 못했습니다.</td></tr>'; }
}

function renderOrderBook(price) {
  const askBody = document.getElementById('altAskBody'), bidBody = document.getElementById('altBidBody');
  if (!askBody || !bidBody || !price || price <= 0) return;
  let tick = Math.max(1, Math.round(price * 0.002));
  if      (price >= 500000) tick = 1000;
  else if (price >= 100000) tick = 500;
  else if (price >=  50000) tick = 100;
  else if (price >=  10000) tick = 50;
  else if (price >=   1000) tick = 10;

  const qty = (p, o) => Math.max(1, Math.round(((p * 7 + o) % 290) + 10));
  const askRows = Array.from({ length: 5 }, (_, i) => ({ price: price + tick * (i + 1), qty: qty(price + tick * (i + 1), 13) }));
  const bidRows = Array.from({ length: 5 }, (_, i) => ({ price: Math.max(1, price - tick * (5 - i)), qty: qty(price - tick * (5 - i), 31) }));

  askBody.innerHTML = askRows.map(r => `<tr style="background:rgba(37,99,235,0.04);">
    <td style="padding:7px 12px;text-align:right;color:#60A5FA;font-weight:700;font-size:14px;">${Number(r.price).toLocaleString('ko-KR')}</td>
    <td style="padding:7px 12px;text-align:right;color:var(--muted);font-size:14px;">${Number(r.qty).toLocaleString('ko-KR')}</td></tr>`).join('');
  bidBody.innerHTML = bidRows.map(r => `<tr style="background:rgba(225,29,72,0.04);">
    <td style="padding:7px 12px;text-align:right;color:#F87171;font-weight:700;font-size:14px;">${Number(r.price).toLocaleString('ko-KR')}</td>
    <td style="padding:7px 12px;text-align:right;color:var(--muted);font-size:14px;">${Number(r.qty).toLocaleString('ko-KR')}</td></tr>`).join('');

  document.getElementById('altObCurrentPrice').textContent = Number(price).toLocaleString('ko-KR');
  const spread = tick * 2;
  document.getElementById('altObSpread').textContent = `${Number(spread).toLocaleString('ko-KR')} (${((spread / price) * 100).toFixed(3)}%)`;
}

function setOrderQuantityByPercent(side, percent) {
  if (!selected) { document.getElementById('orderMessage').textContent = '상품을 먼저 선택해주세요.'; return; }
  const position = lastPositions.find(pos => pos.symbol === selected.symbol);
  const quantity = side === 'buy'
    ? Math.floor(lastCash * (percent / 100) / selected.tradeAmountPerUnit)
    : Math.floor((position?.quantity ?? 0) * (percent / 100));
  const el = document.getElementById('orderMessage');
  if (quantity < 1) {
    el.style.color = '#E11D48';
    el.textContent = side === 'buy' ? '보유 현금으로 매수 가능한 수량이 없습니다.' : '매도 가능한 보유 수량이 없습니다.';
    return;
  }
  document.getElementById('quantity').value = quantity;
  updateAmount();
}
document.querySelectorAll('.order-percent-btn[data-order-side]').forEach(button => {
  button.addEventListener('click', () => setOrderQuantityByPercent(button.dataset.orderSide, Number(button.dataset.percent)));
});
function renderSideMenu() {
  const chartCategories = ['선물', '옵션', '파생상품', '금', '은'];
  const rows = [
    { title: '부동산 지도 거래', icon: '🗺️', key: '부동산', note: '지역을 지도에서 선택하고 시세를 확인한 뒤 바로 주문합니다.' },
    { title: '캔들 차트 거래', icon: '📈', key: 'ALL_CHART', note: '일봉 차트를 보며 선물·옵션·파생상품·금·은을 주문합니다.' },
    ...chartCategories.map(name => ({ title: name, icon: '•', key: name, note: '' })),
  ];
  document.getElementById('sideMenu').innerHTML = rows.map(item => `<div ${item.note ? 'style="margin-bottom:8px;"' : ''}><button class="asset-menu-btn ${category === item.key || (item.key === 'ALL_CHART' && category === '전체') ? 'active' : ''}" data-menu-category="${item.key}"><span class="asset-menu-icon">${item.icon}</span><span>${item.title}</span></button>${item.note ? `<p class="asset-menu-note">${item.note}</p>` : ''}</div>`).join('');
  document.querySelectorAll('[data-menu-category]').forEach(btn => btn.onclick = () => {
    category = btn.dataset.menuCategory === 'ALL_CHART' ? '전체' : btn.dataset.menuCategory;
    renderSideMenu(); renderMarkets();
    if (category === '부동산') selectMarket(markets.find(item => item.category === '부동산')?.symbol);
    else if (selected?.category === '부동산' || (category !== '전체' && selected?.category !== category)) selectMarket(markets.find(item => item.category === category)?.symbol);
  });
}
function formatActualFutures(item) {
  if (!item.actualMultiplier) return '';
  const notional = item.actualPoint * item.actualMultiplier;
  return `실제 기준: ${Number(item.actualPoint).toLocaleString('ko-KR')}포인트 × ${won(item.actualMultiplier)} = ${won(notional)} (1포인트당 손익 ${won(item.actualMultiplier)})`;
}
function renderMarkets() {
  const rows = markets.filter(item => category === '전체' ? item.category !== '부동산' : item.category === category);
  document.getElementById('marketListTitle').textContent = category === '부동산' ? '부동산 지도 거래 상품' : category === '전체' ? '캔들 차트 거래 상품' : `${category} 캔들 차트 거래 상품`;
  document.getElementById('marketListGuide').textContent = category === '부동산' ? '아래 상품 또는 지도 핀을 선택하면 지역 시세와 주문창이 연동됩니다.' : '상품을 선택하면 일봉 캔들 차트와 주문창이 함께 표시됩니다.';
  document.getElementById('marketBody').innerHTML = rows.map(item => `<tr class="market-row ${selected?.symbol === item.symbol ? 'selected' : ''}" data-symbol="${item.symbol}"><td><div class="font-bold" style="color:var(--fg);">${item.name}</div><div class="mt-1 text-xs" style="color:var(--muted);">${item.description}${item.actualMultiplier ? ' · 실제 기준은 주문창에서 확인' : ''}</div></td><td class="text-right font-bold" style="color:var(--fg);">${won(item.price)}</td><td class="text-right font-bold" style="color:${item.changeRate >= 0 ? '#E11D48' : '#2563EB'};">${item.changeRate >= 0 ? '+' : ''}${item.changeRate}%</td><td class="text-right font-bold" style="color:var(--accent);">${won(item.tradeAmountPerUnit)}</td><td class="text-right text-xs" style="color:var(--muted);">${item.unit}<br>${item.marginRate === 100 ? '현금 100%' : '증거금 ' + item.marginRate + '%'}</td></tr>`).join('');
  document.querySelectorAll('[data-symbol]').forEach(row => row.onclick = () => selectMarket(row.dataset.symbol));
}
async function selectMarket(symbol) {
  selected = markets.find(item => item.symbol === symbol); if (!selected) return;
  document.getElementById('selectedName').textContent = selected.name; document.getElementById('selectedCategory').textContent = selected.category;
  document.getElementById('selectedInfo').textContent = `${selected.description} · ${selected.source} · ${selected.updatedAt}`;
  const futuresContractInfo = document.getElementById('futuresContractInfo');
  futuresContractInfo.textContent = selected.actualMultiplier ? `${formatActualFutures(selected)}. 현재 주문은 계약승수 1의 축소 모의계약이며, 실제 선물 주문이 아닙니다.` : '';
  futuresContractInfo.classList.toggle('hidden', !selected.actualMultiplier);
  document.getElementById('viewTitle').textContent = selected.category === '부동산' ? '부동산 시세 지도' : `${selected.name} 일봉 차트`;
  document.getElementById('viewSubtitle').textContent = selected.category === '부동산' ? `${selected.location?.label || ''} · 지도에서 다른 지역도 선택할 수 있습니다.` : `${selected.source} · 60초마다 갱신 · 주문 기준가는 최신 일봉 종가와 연동됩니다.`;
  document.getElementById('viewBadge').textContent = selected.category === '부동산' ? '지도 시세' : '일봉';
  document.getElementById('chartView').classList.toggle('active', selected.category !== '부동산'); document.getElementById('mapView').classList.toggle('active', selected.category === '부동산');
  document.getElementById('viewPrice').textContent = won(selected.price);
  const rateColor = selected.changeRate >= 0 ? '#E11D48' : '#2563EB';
  document.getElementById('viewChangeRate').innerHTML = `<span style="color:${rateColor};">${selected.changeRate >= 0 ? '▲' : '▼'} ${Math.abs(selected.changeRate)}%</span>`;
  renderOrderBook(selected.price);
  renderMarkets(); updateAmount();
  if (selected.category === '부동산') renderPropertyMap(); else await loadChart();
}
async function loadChart() {
  const res = await apiFetch(`/api/alternatives/markets/${encodeURIComponent(selected.symbol)}/chart?days=120`); if (!res.ok || !candleSeries) return;
  const data = (await res.json()).data || []; candleSeries.setData(data); chart.timeScale().fitContent();
}
function renderPropertyMap() {
  if (!window.L) return;
  const properties = markets.filter(item => item.category === '부동산' && item.location);
  if (!propertyMap) {
    propertyMap = L.map('propertyMap', { scrollWheelZoom: false }).setView([36.6, 127.8], 7);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18, attribution: '&copy; OpenStreetMap contributors' }).addTo(propertyMap);
  }
  propertyMarkers.forEach(marker => marker.remove()); propertyMarkers = properties.map(item => {
    const marker = L.circleMarker([item.location.lat, item.location.lng], { radius: item.symbol === selected.symbol ? 11 : 8, color: item.symbol === selected.symbol ? '#2563EB' : '#64748B', fillColor: item.symbol === selected.symbol ? '#60A5FA' : '#CBD5E1', fillOpacity: 1, weight: 2 }).addTo(propertyMap);
    marker.bindPopup(`<strong>${item.name}</strong><br>${item.location.label}<br>${won(item.price)} / ${item.unit}`); marker.on('click', () => selectMarket(item.symbol)); return marker;
  });
  propertyMap.setView([selected.location.lat, selected.location.lng], 12); setTimeout(() => propertyMap.invalidateSize(), 80);
}
function updateAmount() { const qty = Math.max(1, Number(document.getElementById('quantity').value || 1)); document.getElementById('orderAmount').textContent = selected ? won(selected.tradeAmountPerUnit * qty) : '-'; document.getElementById('orderNote').textContent = selected ? (selected.marginRate === 100 ? '현금 전액 기준' : `명목금액 ${won(selected.notionalPerUnit * qty)} · 증거금 ${selected.marginRate}% 적용`) : ''; }
document.getElementById('quantity').addEventListener('input', updateAmount);
document.getElementById('buyBtn').onclick = () => submitOrder('BUY'); document.getElementById('sellBtn').onclick = () => submitOrder('SELL');
async function submitOrder(side) { if (!selected) return; const quantity = Math.max(1, Number(document.getElementById('quantity').value || 1)); const res = await apiFetch('/api/alternatives/orders', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({symbol:selected.symbol, side, quantity}) }); const data = await res.json(); const el = document.getElementById('orderMessage'); el.style.color = res.ok ? '#059669' : '#E11D48'; el.textContent = res.ok ? `${side === 'BUY' ? '매수' : '매도'} 체결: ${selected.name} ${quantity} × ${selected.unit}` : (data.message || '주문에 실패했습니다.'); if (res.ok) await refresh(); }
function renderPositions(positions) { lastPositions = positions; const tbody = document.getElementById('positionBody'); tbody.innerHTML = positions.length ? positions.map(pos => `<tr><td><div class="font-bold" style="color:var(--fg);">${pos.name}</div><div class="text-xs" style="color:var(--muted);">${pos.category}</div></td><td class="text-right">${Number(pos.quantity).toLocaleString()}${pos.unit}</td><td class="text-right font-bold" style="color:var(--accent);">${won(pos.evalAmount)}</td><td class="text-right font-bold" style="color:${pos.pnl >= 0 ? '#E11D48' : '#2563EB'};">${pos.pnl >= 0 ? '+' : ''}${won(pos.pnl)}</td></tr>`).join('') : '<tr><td colspan="4" class="px-4 py-6 text-center text-sm" style="color:var(--muted);">보유한 대체자산이 없습니다.</td></tr>'; }
