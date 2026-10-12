/* KIS 모의투자 포트폴리오 탭 (hold.html)
 *
 * 데이터: GET /api/broker-test/kis/balance — 한국투자증권 Testbed 모의계좌 잔고(로그인 필요, 읽기 전용).
 *         응답 holdings 항목은 KIS 원문이라 **값이 문자열**이고 섹터가 없다.
 * 섹터:   GET /api/stocks/list — 종목 마스터(symbol→sector). 섹터 표를 이 파일에 복제하지 않기 위해 받아서 쓴다.
 *
 * 왜 지연 로딩인가: st 는 모든 KIS 호출을 전역 1.05초 간격으로 직렬화한다. 페이지를 열 때마다 잔고를
 * 조회하면 같은 큐를 쓰는 fd 자동매매(주문·체결 확인)의 지연을 키운다. 그래서 탭을 실제로 열 때만 조회하고,
 * 한 번 받은 값은 캐시해 「새로고침」을 누를 때만 다시 받는다. 숨은 패널에서 Highcharts 가 폭 0 으로
 * 그려지는 문제도 같은 방식으로 피한다.
 *
 * fmt·setText·setColorText 는 hold_crypto.js 의 전역 함수를 그대로 쓴다(먼저 로드된다).
 */

const KIS_PALETTE = ['#2563EB', '#7C3AED', '#059669', '#EA580C', '#DB2777', '#0891B2', '#65A30D', '#D97706'];
let kisPortfolioLoaded = false;
let kisPortfolioLoading = false;
let kisSectorMap = null;
let kisPortfolioGridApi = null;

/** KIS 응답은 숫자가 문자열("1,234" 포함)로 온다. */
function kisNum(value) {
  if (value == null) return 0;
  const n = Number(String(value).replace(/,/g, ''));
  return Number.isFinite(n) ? n : 0;
}

function kisStatus(message) {
  const el = document.getElementById('kisPortfolioStatus');
  if (el) el.textContent = message;
}

/** 빈 그리드에 안내 문구를 띄운다(행이 없을 때 ag-Grid 오버레이로 표시). */
function kisTableMessage(message) {
  const api = ensureKisPortfolioGrid();
  if (!api) return;
  api.setGridOption('overlayNoRowsTemplate', `<span style="padding:16px;color:#64748B;">${message}</span>`);
  api.setGridOption('rowData', []);
  api.showNoRowsOverlay();
}

function kisChartsMessage(message) {
  const html = `<div class="flex h-[270px] items-center justify-center text-sm" style="color:var(--muted);">${message}</div>`;
  ['kisAllocationChart', 'kisSectorChart'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
  });
  const summary = document.getElementById('kisSectorSummary');
  if (summary) summary.innerHTML = '';
}

/** 종목 마스터에서 symbol→sector 를 한 번만 받아 캐시한다. 실패해도 포트폴리오는 보여준다. */
async function loadKisSectorMap() {
  if (kisSectorMap) return kisSectorMap;
  kisSectorMap = {};
  try {
    const res = await apiFetch('/api/stocks/list?limit=100');
    if (res.ok) {
      const { stocks = [] } = await res.json();
      stocks.forEach(stock => { if (stock.symbol) kisSectorMap[String(stock.symbol)] = stock.sector || '기타'; });
    }
  } catch { /* 섹터는 보조 정보다 — 없으면 '기타'로 표시한다 */ }
  return kisSectorMap;
}

function renderKisSectorSummary(rows, totalEval) {
  const el = document.getElementById('kisSectorSummary');
  if (!el) return;
  if (!rows.length || totalEval <= 0) { el.innerHTML = ''; return; }
  const sectors = rows.reduce((acc, row) => {
    const name = row.sector || '기타';
    if (!acc[name]) acc[name] = { eval: 0, pnl: 0, count: 0 };
    acc[name].eval += row.evalAmount;
    acc[name].pnl += row.profitLoss;
    acc[name].count += 1;
    return acc;
  }, {});
  const entries = Object.entries(sectors).sort((a, b) => b[1].eval - a[1].eval);
  el.innerHTML = `<div class="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">${entries.map(([name, info], index) => {
    const share = info.eval / totalEval * 100;
    const color = info.pnl >= 0 ? '#E11D48' : '#2563EB';
    return `<div class="rounded-lg p-3" style="border:1px solid var(--border);background:var(--surface);">
      <div class="flex items-center justify-between">
        <span class="text-sm font-extrabold" style="color:${KIS_PALETTE[index % KIS_PALETTE.length]};">${name}</span>
        <span class="text-sm" style="color:var(--muted);">${info.count}종목 · ${share.toFixed(1)}%</span>
      </div>
      <div class="mt-1 font-bold" style="color:var(--fg);">${fmt(info.eval)}원</div>
      <div class="text-sm font-bold" style="color:${color};">${info.pnl >= 0 ? '+' : ''}${fmt(info.pnl)}원</div>
    </div>`;
  }).join('')}</div>`;
}

/** 주식 패널과 같은 구성: 종목별 비중 도넛 + 섹터별 평가금액 바 */
function renderKisPortfolioCharts(rows, totalEval) {
  if (typeof Highcharts === 'undefined') return;
  if (!rows.length || totalEval <= 0) { kisChartsMessage('보유 종목이 있으면 차트가 표시됩니다.'); return; }

  const sorted = [...rows].sort((a, b) => b.evalAmount - a.evalAmount);
  const top = sorted.slice(0, 6);
  const otherEval = sorted.slice(6).reduce((sum, row) => sum + row.evalAmount, 0);
  const allocationData = top.map((row, index) => ({
    name: row.name || row.symbol, y: row.evalAmount, color: KIS_PALETTE[index % KIS_PALETTE.length],
  }));
  if (otherEval > 0) allocationData.push({ name: '기타 종목', y: otherEval, color: '#94A3B8' });

  const sectors = rows.reduce((acc, row) => {
    const name = row.sector || '기타';
    acc[name] = (acc[name] || 0) + row.evalAmount;
    return acc;
  }, {});
  const sectorData = Object.entries(sectors).sort((a, b) => b[1] - a[1]);
  const sharedTooltip = { backgroundColor: '#FFFFFF', borderColor: '#CBD5E1', style: { color: '#1E293B' }, valueSuffix: '원' };

  Highcharts.chart('kisAllocationChart', {
    chart: { type: 'pie', backgroundColor: 'transparent', height: 270, style: { fontFamily: "'Pretendard', sans-serif" } },
    title: { text: null },
    tooltip: { ...sharedTooltip, pointFormat: '<b>{point.y:,.0f}원</b><br/>전체의 {point.percentage:.1f}%' },
    plotOptions: { pie: {
      innerSize: '58%', borderWidth: 2, borderColor: '#FFFFFF',
      dataLabels: { enabled: true, format: '<b>{point.name}</b><br/>{point.percentage:.1f}%', distance: 14,
        style: { color: '#334155', fontSize: '13.5px', fontWeight: '700', textOutline: 'none' },
        filter: { property: 'percentage', operator: '>', value: 4 } },
    } },
    credits: { enabled: false },
    series: [{ name: '평가금액', data: allocationData }],
  });

  Highcharts.chart('kisSectorChart', {
    chart: { type: 'bar', backgroundColor: 'transparent', height: 270, style: { fontFamily: "'Pretendard', sans-serif" }, marginLeft: 105 },
    title: { text: null },
    xAxis: { categories: sectorData.map(([name]) => name), lineColor: '#CBD5E1', tickLength: 0,
      labels: { style: { color: '#475569', fontSize: '13.5px', fontWeight: '700' } } },
    yAxis: { min: 0, title: { text: null }, gridLineColor: '#E2E8F0',
      labels: { style: { color: '#64748B', fontSize: '13px' }, formatter() { return Highcharts.numberFormat(this.value, 0, '.', ','); } } },
    tooltip: { ...sharedTooltip, pointFormat: '<b>{point.y:,.0f}원</b><br/>전체의 {point.percentage:.1f}%' },
    legend: { enabled: false },
    plotOptions: { series: { borderRadius: 4, pointPadding: 0.12, groupPadding: 0.08,
      dataLabels: { enabled: true, format: '{point.percentage:.1f}%', align: 'right', inside: false,
        style: { color: '#475569', fontSize: '13px', fontWeight: '700', textOutline: 'none' } } } },
    credits: { enabled: false },
    series: [{ name: '평가금액', colorByPoint: true, data: sectorData.map(([name, value], index) => ({
      name, y: value, percentage: value / totalEval * 100, color: KIS_PALETTE[index % KIS_PALETTE.length],
    })) }],
  });
}

/* ── 보유 종목 ag-Grid ──────────────────────────────────────────────────────
   같은 trade/ 폴더의 history.html 과 같은 방식(ag-grid-community 36.0.2, --ag-* 테마 변수,
   defaultColDef 에 정렬·필터·리사이즈, 페이지네이션)으로 맞춘다.
   금액 컬럼은 valueFormatter 로만 가공해 **원본 숫자를 셀 값으로 유지**한다 — 그래야 정렬과
   숫자 필터가 문자열이 아니라 값 기준으로 동작한다. */
function kisPortfolioColumnDefs() {
  const pnlStyle = params => ({ fontWeight: '800', color: Number(params.value) >= 0 ? '#E11D48' : '#2563EB' });
  const signedKrw = params => `${Number(params.value) >= 0 ? '+' : ''}${fmt(Number(params.value))}원`;
  return [
    { headerName:'종목', field:'name', minWidth:190, flex:1.2,
      cellRenderer: params => `<a href="/trade/stock.html?symbol=${encodeURIComponent(params.data.symbol)}" title="${params.value} 시세·매매" style="font-weight:800;color:var(--fg);text-decoration:none;">${params.value} <span style="font-size:13px;color:var(--accent);">시세 ↗</span></a>` },
    { headerName:'종목코드', field:'symbol', width:112, cellStyle:{ color:'var(--accent)', fontWeight:'700' } },
    { headerName:'섹터', field:'sector', minWidth:140,
      cellRenderer: params => `<span class="badge badge-muted" style="font-size:13px;">${params.value || '기타'}</span>` },
    { headerName:'보유수량', field:'quantity', width:118, type:'rightAligned',
      valueFormatter: params => `${fmt(Number(params.value))}주` },
    { headerName:'매수평균가', field:'avgPrice', minWidth:130, type:'rightAligned',
      valueFormatter: params => `${fmt(Math.round(Number(params.value)))}원` },
    { headerName:'현재가', field:'currentPrice', minWidth:120, type:'rightAligned',
      valueFormatter: params => `${fmt(Number(params.value))}원` },
    { headerName:'평가금액', field:'evalAmount', minWidth:140, type:'rightAligned', sort:'desc',
      valueFormatter: params => `${fmt(Number(params.value))}원`,
      cellStyle:{ fontWeight:'800', color:'var(--accent-dark)' } },
    { headerName:'평가손익', field:'profitLoss', minWidth:135, type:'rightAligned',
      valueFormatter: signedKrw, cellStyle: pnlStyle },
    { headerName:'수익률', field:'profitLossRate', width:112, type:'rightAligned',
      valueFormatter: params => `${Number(params.value) >= 0 ? '+' : ''}${Number(params.value).toFixed(2)}%`,
      cellStyle: pnlStyle },
  ];
}

/** 그리드를 한 번만 만들고 API 를 캐시한다. 탭이 열린 뒤에 호출되므로 폭이 0 이 아니다. */
function ensureKisPortfolioGrid() {
  if (kisPortfolioGridApi) return kisPortfolioGridApi;
  const element = document.getElementById('kisPortfolioGrid');
  if (!element || !window.agGrid) return null;
  kisPortfolioGridApi = agGrid.createGrid(element, {
    columnDefs: kisPortfolioColumnDefs(),
    rowData: [],
    defaultColDef: { sortable:true, filter:true, resizable:true, suppressHeaderMenuButton:true },
    animateRows: true,
    pagination: true,
    paginationPageSize: 20,
    paginationPageSizeSelector: [20, 50, 100],
    overlayNoRowsTemplate: '<span style="padding:16px;color:#64748B;">탭을 열면 조회합니다.</span>',
  });
  return kisPortfolioGridApi;
}

function renderKisPortfolioTable(rows) {
  const api = ensureKisPortfolioGrid();
  if (!api) return;
  if (!rows.length) { kisTableMessage('KIS 모의계좌에 보유 종목이 없습니다.'); return; }
  api.setGridOption('rowData', rows);
  api.hideOverlay();
}

/** 탭을 열 때 호출된다(hold.html switchHoldTab). force=true 면 캐시를 무시하고 다시 받는다. */
async function loadKisPortfolio(force = false) {
  if (kisPortfolioLoading || (kisPortfolioLoaded && !force)) return;
  kisPortfolioLoading = true;
  kisStatus('KIS 모의계좌 잔고를 불러오는 중…');
  try {
    const [balanceRes, sectorMap] = await Promise.all([
      apiFetch('/api/broker-test/kis/balance'),
      loadKisSectorMap(),
    ]);
    const body = await balanceRes.json().catch(() => ({}));
    if (!balanceRes.ok) {
      const message = body.message || (balanceRes.status === 401
        ? 'KIS 모의계좌 잔고는 로그인 후 조회할 수 있습니다.'
        : 'KIS 모의계좌 잔고를 불러올 수 없습니다.');
      kisStatus(message);
      kisTableMessage(message);
      kisChartsMessage(message);
      return;
    }
    const balance = body.balance || {};
    const rows = (balance.holdings || []).map(item => ({
      symbol: String(item.symbol || ''),
      name: item.name || String(item.symbol || ''),
      sector: sectorMap[String(item.symbol || '')] || '기타',
      quantity: kisNum(item.quantity),
      avgPrice: kisNum(item.avgPrice),
      currentPrice: kisNum(item.currentPrice),
      evalAmount: kisNum(item.evalAmount),
      profitLoss: kisNum(item.profitLoss),
      profitLossRate: kisNum(item.profitLossRate),
    })).filter(row => row.quantity > 0);

    const totalEval = rows.reduce((sum, row) => sum + row.evalAmount, 0);
    const totalPnl = kisNum(balance.totalProfitLoss) || rows.reduce((sum, row) => sum + row.profitLoss, 0);

    setText('kisPositionCount', rows.length);
    setText('kisCashBalance', fmt(kisNum(balance.cashBalance)));
    setText('kisTotalEval', fmt(kisNum(balance.totalEvalAmount) || totalEval));
    setColorText('kisTotalPnl', totalPnl >= 0 ? '+' + fmt(totalPnl) : fmt(totalPnl), totalPnl);

    renderKisPortfolioCharts(rows, totalEval);
    renderKisSectorSummary(rows, totalEval);
    renderKisPortfolioTable(rows);
    kisStatus(`${rows.length}종목 · ${new Date().toLocaleTimeString('ko-KR', { hour12: false, timeZone: 'Asia/Seoul' })} KST 기준 (${balance.broker || '한국투자증권 Testbed'})`);
    kisPortfolioLoaded = true;
  } catch (error) {
    const message = `KIS 모의계좌 잔고를 불러올 수 없습니다: ${error.message}`;
    kisStatus(message);
    kisTableMessage(message);
    kisChartsMessage('잔고를 불러오지 못해 차트를 표시할 수 없습니다.');
  } finally {
    kisPortfolioLoading = false;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const button = document.getElementById('kisPortfolioRefresh');
  if (button) button.addEventListener('click', () => loadKisPortfolio(true));
});
