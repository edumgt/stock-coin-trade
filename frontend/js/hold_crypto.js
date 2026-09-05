/* ── 초기화: 보유자산 fetch → DOM 렌더 → WebSocket 연결 ──────── */
(async () => {
  await initPage({ requireAuth: true });

  const res = await apiFetch('/api/trade/hold');
  if (!res.ok) {
    document.getElementById('holdCryptoTableBody').innerHTML =
      '<tr><td colspan="6" class="px-4 py-6 text-center" style="color:var(--muted);">데이터를 불러올 수 없습니다.</td></tr>';
    return;
  }

  const { memberAsset, totalBuyKrw, holdCryptoList, marketArrayList } = await res.json();

  // 상단 통계 초기값 설정
  setText('member_asset', fmt(memberAsset));
  setText('total_buy_krw', fmt(totalBuyKrw));

  // 보유 코인 테이블 렌더
  renderHoldTable(holdCryptoList);
  await loadStockPortfolio();
  await loadAlternativePortfolio();

  if (!holdCryptoList.length) {
    setText('total_member_asset', fmt(memberAsset));
    setText('total_evaluation_krw', '0');
    setText('total_krw_of_return', '0');
    setText('total_evaluation_rate_of_return', '0');
    // 보유 코인이 없어도 KRW 자산 비중 차트는 표시한다.
    await renderPortfolioChart([], [], memberAsset);
    return;
  }

  // 웹소켓 연결 (평가금액 실시간 업데이트)
  initWebSocket(marketArrayList, memberAsset, totalBuyKrw);

  // 포트폴리오 차트
  renderPortfolioChart(holdCryptoList, marketArrayList, memberAsset);
})();

/* ── 주식 포트폴리오 / 섹터별 집계 ────────────────────────────── */
async function loadStockPortfolio() {
  const tbody = document.getElementById('holdStockTableBody');
  try {
    const res = await apiFetch('/api/stocks/positions');
    if (!res.ok) throw new Error('stock positions unavailable');
    const { positions = [] } = await res.json();

    const totalEval = positions.reduce((sum, pos) => sum + Number(pos.evalAmount || 0), 0);
    const totalPnl = positions.reduce((sum, pos) => sum + Number(pos.pnl || 0), 0);
    setText('stockPositionCount', positions.length);
    setText('stockPortfolioEval', fmt(totalEval));
    setColorText('stockPortfolioPnl', totalPnl >= 0 ? '+' + fmt(totalPnl) : fmt(totalPnl), totalPnl);

    renderStockSectorSummary(positions, totalEval);
    renderStockPortfolioCharts(positions, totalEval);
    if (!positions.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="px-4 py-6 text-center" style="color:var(--muted);">보유 주식이 없습니다.</td></tr>';
      return;
    }

    tbody.innerHTML = positions.map(pos => {
      const pnl = Number(pos.pnl || 0);
      const color = pnl >= 0 ? '#E11D48' : '#2563EB';
      const tradeUrl = `/trade/stock.html?symbol=${encodeURIComponent(pos.symbol)}`;
      return `<tr>
        <td><a href="${tradeUrl}" title="${pos.name} 매수·매도" style="display:inline-block;text-decoration:none;">
          <div class="font-bold" style="color:var(--fg);">${pos.name} <span style="font-size:10px;color:var(--accent);">매매하기 ↗</span></div>
          <div class="text-xs" style="color:var(--accent);">${pos.symbol}</div>
        </a></td>
        <td><span class="badge badge-muted" style="font-size:10px;">${pos.sector || '기타'}</span></td>
        <td class="text-right font-semibold" style="color:var(--fg);">${Number(pos.quantity).toLocaleString('ko-KR')}주</td>
        <td class="text-right" style="color:var(--fg);">${fmt(pos.avgPrice)}원</td>
        <td class="text-right" style="color:var(--fg);">${fmt(pos.currentPrice)}원</td>
        <td class="text-right font-bold" style="color:var(--accent);">${fmt(pos.evalAmount)}원</td>
        <td class="text-right font-bold" style="color:${color};">${pnl >= 0 ? '+' : ''}${fmt(pnl)}원</td>
      </tr>`;
    }).join('');
  } catch {
    if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="px-4 py-6 text-center" style="color:var(--muted);">주식 포트폴리오를 불러올 수 없습니다.</td></tr>';
  }
}

/* ── 선물·옵션·금속·부동산 포지션 ─────────────────────────────── */
async function loadAlternativePortfolio() {
  const tbody = document.getElementById('alternativePositionBody');
  if (!tbody) return;
  try {
    const res = await apiFetch('/api/alternatives/positions');
    if (!res.ok) throw new Error('alternative positions unavailable');
    const { positions = [] } = await res.json();
    if (!positions.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="px-4 py-6 text-center" style="color:var(--muted);">보유한 대체자산이 없습니다.</td></tr>';
      return;
    }
    tbody.innerHTML = positions.map(pos => {
      const pnl = Number(pos.pnl || 0);
      return `<tr><td><div class="font-bold" style="color:var(--fg);">${pos.name}</div><div class="text-xs" style="color:var(--accent);">${pos.symbol}</div></td><td><span class="badge badge-muted">${pos.category}</span></td><td class="text-right" style="color:var(--fg);">${Number(pos.quantity).toLocaleString('ko-KR')}${pos.unit}</td><td class="text-right" style="color:var(--fg);">${fmt(pos.avgPrice)}원</td><td class="text-right font-bold" style="color:var(--accent);">${fmt(pos.evalAmount)}원</td><td class="text-right font-bold" style="color:${pnl >= 0 ? '#E11D48' : '#2563EB'};">${pnl >= 0 ? '+' : ''}${fmt(pnl)}원</td></tr>`;
    }).join('');
  } catch {
    tbody.innerHTML = '<tr><td colspan="6" class="px-4 py-6 text-center" style="color:var(--muted);">대체자산 포트폴리오를 불러올 수 없습니다.</td></tr>';
  }
}

/* ── 포트폴리오 분석 모달 (어드바이저 리포트) ───────────────────────────────────── */
const CHECK_STATUS_STYLE = {
  good: { icon: '✓', color: '#059669', bg: '#ECFDF5', border: '#A7F3D0' },
  warn: { icon: '⚠', color: '#92400E', bg: '#FFFBEB', border: '#FDE68A' },
  risk: { icon: '✕', color: '#B91C1C', bg: '#FEF2F2', border: '#FECACA' },
};
function healthColor(score) {
  if (score >= 80) return '#059669';
  if (score >= 60) return '#2563EB';
  if (score >= 40) return '#D97706';
  return '#DC2626';
}
function pnlColor(rate) { return rate >= 0 ? '#E11D48' : '#2563EB'; }
function signed(n, digits = 2) { return `${n >= 0 ? '+' : ''}${n.toFixed(digits)}`; }

async function openPortfolioAnalysis() {
  const modal = document.getElementById('portfolioAnalysisModal');
  const content = document.getElementById('portfolioAnalysisContent');
  modal.style.display = 'flex';
  content.innerHTML = '<p class="text-sm" style="color:var(--muted);">분석 정보를 불러오는 중입니다.</p>';
  try {
    const res = await apiFetch('/api/member/portfolio-analysis');
    if (!res.ok) throw new Error('analysis unavailable');
    const data = await res.json();
    const allocation = data.allocation || [];
    const checks = data.checks || [];
    const stats = data.positionStats;
    const leverage = data.leverage || {};
    const color = healthColor(data.healthScore || 0);

    content.innerHTML = `
      <div class="flex flex-wrap items-center gap-4 rounded-xl p-4" style="background:linear-gradient(135deg,#EEF4FF,#F8FAFC);border:1px solid #D7E3FC;">
        <div style="width:72px;height:72px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;background:${color}1A;border:3px solid ${color};">
          <span style="font-size:22px;font-weight:900;color:${color};">${data.healthScore ?? '-'}</span>
        </div>
        <div>
          <div class="text-xs font-bold" style="color:var(--muted);">포트폴리오 건강도 · <span style="color:${color};">${data.healthLabel || '-'}</span></div>
          <div class="mt-1 text-2xl font-black" style="color:var(--fg);">${fmt(data.totalAsset)}원</div>
          <div class="mt-1 text-xs" style="color:var(--muted);">분산도 ${data.diversification?.score ?? '-'}점(${data.diversification?.label || '-'}) 등 여러 기법을 종합한 점수입니다.</div>
        </div>
      </div>

      <div class="mt-5"><h3 class="text-sm font-black" style="color:var(--fg);">자산 배분</h3><div class="mt-3 space-y-3">${allocation.map(item => `<div><div class="flex items-center justify-between text-sm"><span class="font-bold" style="color:var(--fg);"><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${item.color};margin-right:6px;"></span>${item.name}</span><span style="color:var(--muted);">${fmt(item.value)}원 · <strong style="color:var(--fg);">${item.weight}%</strong></span></div><div style="height:8px;margin-top:7px;border-radius:999px;background:var(--surface-2);overflow:hidden;"><div style="width:${item.weight}%;height:100%;border-radius:inherit;background:${item.color};"></div></div></div>`).join('')}</div></div>

      ${stats || leverage.value || data.topSector ? `<div class="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
        ${stats ? `<div class="rounded-lg p-3" style="background:var(--surface-2);"><div class="text-xs font-bold" style="color:var(--muted);">승률 · 평균수익률</div><div class="mt-1 text-base font-black" style="color:var(--fg);">${stats.winRate}%</div><div class="text-xs" style="color:${pnlColor(stats.avgPnlRate)};">${signed(stats.avgPnlRate)}% 평균</div></div>` : ''}
        ${stats ? `<div class="rounded-lg p-3" style="background:var(--surface-2);"><div class="text-xs font-bold" style="color:var(--muted);">최고 · 최저 포지션</div><div class="mt-1 text-sm font-bold" style="color:${pnlColor(stats.best.pnlRate)};">${stats.best.name} ${signed(stats.best.pnlRate)}%</div><div class="text-sm font-bold" style="color:${pnlColor(stats.worst.pnlRate)};">${stats.worst.name} ${signed(stats.worst.pnlRate)}%</div></div>` : ''}
        ${leverage.value ? `<div class="rounded-lg p-3" style="background:var(--surface-2);"><div class="text-xs font-bold" style="color:var(--muted);">레버리지 노출 · 현금버퍼</div><div class="mt-1 text-base font-black" style="color:var(--fg);">${leverage.ratio}%</div><div class="text-xs" style="color:var(--muted);">현금/노출 ${leverage.cashBufferRatio}%</div></div>` : (data.topSector ? `<div class="rounded-lg p-3" style="background:var(--surface-2);"><div class="text-xs font-bold" style="color:var(--muted);">최대 업종 비중</div><div class="mt-1 text-base font-black" style="color:var(--fg);">${data.topSector.name}</div><div class="text-xs" style="color:var(--muted);">주식 내 ${data.topSector.weight}%</div></div>` : '')}
      </div>` : ''}

      <div class="mt-6"><h3 class="text-sm font-black" style="color:var(--fg);">✦ 어드바이저 체크리스트</h3><div class="mt-3 space-y-2">${checks.map(item => {
        const style = CHECK_STATUS_STYLE[item.status] || CHECK_STATUS_STYLE.good;
        return `<div class="rounded-xl p-3" style="border:1px solid ${style.border};background:${style.bg};"><div class="flex items-center gap-2 text-sm font-black" style="color:${style.color};"><span>${style.icon}</span><span>${item.title}</span></div><p class="mt-1 text-sm leading-relaxed" style="color:${style.color};opacity:.9;">${item.message}</p></div>`;
      }).join('')}</div></div>
      <p class="mt-4 text-xs" style="color:var(--muted);">${data.notice || ''}</p>`;
  } catch {
    content.innerHTML = '<p class="text-sm" style="color:#E11D48;">분석 정보를 불러올 수 없습니다. 잠시 후 다시 시도해주세요.</p>';
  }
}
function closePortfolioAnalysis() { document.getElementById('portfolioAnalysisModal').style.display = 'none'; }
document.getElementById('portfolioAnalysisModal')?.addEventListener('click', event => { if (event.target.id === 'portfolioAnalysisModal') closePortfolioAnalysis(); });
document.addEventListener('keydown', event => { if (event.key === 'Escape') closePortfolioAnalysis(); });

function renderStockSectorSummary(positions, totalEval) {
  const container = document.getElementById('stockSectorSummary');
  if (!container) return;
  if (!positions.length) {
    container.innerHTML = '<p class="text-xs" style="color:var(--muted);">섹터별 집계는 주식 보유 후 표시됩니다.</p>';
    return;
  }
  const sectors = positions.reduce((result, pos) => {
    const name = pos.sector || '기타';
    const group = result[name] || { count: 0, evalAmount: 0 };
    group.count += 1;
    group.evalAmount += Number(pos.evalAmount || 0);
    result[name] = group;
    return result;
  }, {});
  const palette = ['#2563EB', '#7C3AED', '#059669', '#EA580C', '#DB2777', '#0891B2'];
  const items = Object.entries(sectors).sort((a, b) => b[1].evalAmount - a[1].evalAmount);
  container.innerHTML = `<div style="font-size:11px;font-weight:800;color:var(--muted);margin-bottom:8px;">섹터별 평가 비중</div><div class="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">${items.map(([sector, data], index) => {
    const pct = totalEval ? data.evalAmount / totalEval * 100 : 0;
    const color = palette[index % palette.length];
    return `<div style="border:1px solid var(--border);border-radius:8px;padding:9px 10px;background:var(--surface-2);">
      <div style="display:flex;justify-content:space-between;gap:8px;font-size:11px;font-weight:800;color:var(--fg);"><span>${sector}</span><span>${pct.toFixed(1)}%</span></div>
      <div style="height:5px;border-radius:99px;background:var(--border);overflow:hidden;margin:7px 0 5px;"><div style="width:${pct}%;height:100%;background:${color};"></div></div>
      <div style="font-size:10px;color:var(--muted);">${data.count}종목 · ${fmt(data.evalAmount)}원</div>
    </div>`;
  }).join('')}</div>`;
}

/* ── 주식 포트폴리오 차트 ─────────────────────────────────────── */
function renderStockPortfolioCharts(positions, totalEval) {
  const allocationEl = document.getElementById('stockAllocationChart');
  const sectorEl = document.getElementById('stockSectorChart');
  if (!allocationEl || !sectorEl || typeof Highcharts === 'undefined') return;

  if (!positions.length || totalEval <= 0) {
    const empty = '<div class="flex h-[270px] items-center justify-center text-sm" style="color:var(--muted);">보유 주식이 있으면 차트가 표시됩니다.</div>';
    allocationEl.innerHTML = empty;
    sectorEl.innerHTML = empty;
    return;
  }

  const palette = ['#2563EB', '#7C3AED', '#059669', '#EA580C', '#DB2777', '#0891B2', '#65A30D', '#D97706'];
  const sortedPositions = [...positions].sort((a, b) => Number(b.evalAmount || 0) - Number(a.evalAmount || 0));
  const topPositions = sortedPositions.slice(0, 6);
  const otherEval = sortedPositions.slice(6).reduce((sum, pos) => sum + Number(pos.evalAmount || 0), 0);
  const allocationData = topPositions.map((pos, index) => ({
    name: pos.name,
    y: Number(pos.evalAmount || 0),
    color: palette[index % palette.length],
  }));
  if (otherEval > 0) allocationData.push({ name: '기타 종목', y: otherEval, color: '#94A3B8' });

  const sectors = positions.reduce((result, pos) => {
    const name = pos.sector || '기타';
    result[name] = (result[name] || 0) + Number(pos.evalAmount || 0);
    return result;
  }, {});
  const sectorData = Object.entries(sectors).sort((a, b) => b[1] - a[1]);
  const sharedTooltip = {
    backgroundColor: '#FFFFFF',
    borderColor: '#CBD5E1',
    style: { color: '#1E293B' },
    valueSuffix: '원',
  };

  Highcharts.chart('stockAllocationChart', {
    chart: { type: 'pie', backgroundColor: 'transparent', height: 270, style: { fontFamily: "'Pretendard', sans-serif" } },
    title: { text: null },
    tooltip: { ...sharedTooltip, pointFormat: '<b>{point.y:,.0f}원</b><br/>전체의 {point.percentage:.1f}%' },
    plotOptions: { pie: {
      innerSize: '58%', borderWidth: 2, borderColor: '#FFFFFF',
      dataLabels: { enabled: true, format: '<b>{point.name}</b><br/>{point.percentage:.1f}%', distance: 14,
        style: { color: '#334155', fontSize: '11px', fontWeight: '700', textOutline: 'none' },
        filter: { property: 'percentage', operator: '>', value: 4 } },
    } },
    credits: { enabled: false },
    series: [{ name: '평가금액', data: allocationData }],
  });

  Highcharts.chart('stockSectorChart', {
    chart: { type: 'bar', backgroundColor: 'transparent', height: 270, style: { fontFamily: "'Pretendard', sans-serif" }, marginLeft: 105 },
    title: { text: null },
    xAxis: { categories: sectorData.map(([name]) => name), lineColor: '#CBD5E1', tickLength: 0,
      labels: { style: { color: '#475569', fontSize: '11px', fontWeight: '700' } } },
    yAxis: { min: 0, title: { text: null }, gridLineColor: '#E2E8F0',
      labels: { style: { color: '#64748B', fontSize: '10px' }, formatter() { return Highcharts.numberFormat(this.value, 0, '.', ','); } } },
    tooltip: { ...sharedTooltip, pointFormat: '<b>{point.y:,.0f}원</b><br/>전체의 {point.percentage:.1f}%' },
    legend: { enabled: false },
    plotOptions: { series: { borderRadius: 4, pointPadding: 0.12, groupPadding: 0.08,
      dataLabels: { enabled: true, format: '{point.percentage:.1f}%', align: 'right', inside: false,
        style: { color: '#475569', fontSize: '10px', fontWeight: '700', textOutline: 'none' } } } },
    credits: { enabled: false },
    series: [{ name: '평가금액', colorByPoint: true, data: sectorData.map(([name, value], index) => ({
      name, y: value, percentage: value / totalEval * 100, color: palette[index % palette.length],
    })) }],
  });
}

/* ── 보유 코인 테이블 렌더 ────────────────────────────────────── */
function renderHoldTable(holdCryptoList) {
  const tbody = document.getElementById('holdCryptoTableBody');
  if (!holdCryptoList.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="px-4 py-6 text-center" style="color:var(--muted);">보유 코인이 없습니다.</td></tr>';
    return;
  }
  tbody.innerHTML = holdCryptoList.map(h => `
    <tr>
      <td>
        <div class="flex items-center gap-3">
          <img src="https://static.upbit.com/logos/${h.marketCodeOnlySymbol}.png" alt="" class="h-9 w-9 rounded-full" style="border:1px solid var(--border);">
          <div>
            <p class="font-bold" style="color:var(--fg);">${h.koreanName}</p>
            <p class="text-xs font-semibold" style="color:var(--accent);">${h.marketCodeOnlySymbol}</p>
          </div>
        </div>
      </td>
      <td class="text-right">
        <span class="font-semibold" style="color:var(--fg);" id="${h.marketCode}-hold-count">${fmtDec(h.holdCount, 8)}</span>
        <span class="ml-1 text-xs" style="color:var(--muted);">${h.marketCodeOnlySymbol}</span>
      </td>
      <td class="text-right">
        <span class="font-semibold" style="color:var(--fg);" id="${h.marketCode}-buy-average">${fmtDec(h.buyAverage, 4)}</span>
        <span class="ml-1 text-xs" style="color:var(--muted);">KRW</span>
      </td>
      <td class="text-right">
        <span class="font-semibold" style="color:var(--fg);" id="${h.marketCode}-buy-total-krw">${fmt(h.buyTotalKrw)}</span>
        <span class="ml-1 text-xs" style="color:var(--muted);">KRW</span>
      </td>
      <td class="text-right" style="background:var(--accent-light);">
        <span class="font-bold" style="color:var(--accent);" id="${h.marketCode}-evaluation-krw">-</span>
        <span class="ml-1 text-xs" style="color:var(--muted);">KRW</span>
      </td>
      <td class="text-right">
        <p class="mb-1">
          <span class="font-bold" id="${h.marketCode}-krw-of-return">-</span>
          <span class="ml-1 text-xs" style="color:var(--muted);">KRW</span>
        </p>
        <p>
          <span class="font-black text-base" id="${h.marketCode}-rate-of-return">-</span>
          <span class="ml-1 text-xs" style="color:var(--muted);">%</span>
        </p>
      </td>
    </tr>`).join('');
}

/* ── 업비트 웹소켓 (실시간 평가금액) ──────────────────────────── */
function initWebSocket(marketArrayList, memberAsset, totalBuyKrw) {
  const evalMap = {};
  const socket = new WebSocket(upbitWebSocketUrl());

  socket.onopen = () => {
    socket.send(JSON.stringify([
      { ticket: 'edumgt-hold' },
      { type: 'ticker', codes: marketArrayList },
    ]));
  };

  socket.onmessage = async (e) => {
    try {
      const result = JSON.parse(await e.data.text());
      if (result.type !== 'ticker') return;

      const code      = result.code;
      const nowPrice  = result.trade_price;
      const holdCount = parseFloat(document.getElementById(code + '-hold-count')?.textContent.replaceAll(',', '') || '0');
      const evalKrw   = Math.round(nowPrice * holdCount);
      evalMap[code]   = evalKrw;

      const totalEval = Object.values(evalMap).reduce((a, b) => a + b, 0);
      const totalAsset = memberAsset + totalEval;

      setText('total_evaluation_krw', fmt(totalEval));
      setText('total_member_asset',   fmt(totalAsset));

      const totalReturn = totalEval - totalBuyKrw;
      setColorText('total_krw_of_return', totalReturn > 0 ? '+' + fmt(totalReturn) : fmt(totalReturn), totalReturn);

      const rate = totalBuyKrw > 0 ? (totalEval / totalBuyKrw) * 100 - 100 : 0;
      setColorText('total_evaluation_rate_of_return', rate > 0 ? '+' + rate.toFixed(2) : rate.toFixed(2), rate);

      // 개별 코인 평가
      const buyKrwEl = document.getElementById(code + '-buy-total-krw');
      const buyKrw   = parseFloat(buyKrwEl?.textContent.replaceAll(',', '') || '0');

      setText(code + '-evaluation-krw', fmt(evalKrw));

      const krwReturn = evalKrw - buyKrw;
      setColorText(code + '-krw-of-return', krwReturn > 0 ? '+' + fmt(krwReturn) : fmt(krwReturn), krwReturn);

      const coinRate = buyKrw > 0 ? (evalKrw / buyKrw) * 100 - 100 : 0;
      const coinRateStr = coinRate > 0 ? '+' + coinRate.toFixed(2) : coinRate.toFixed(2);
      setColorText(code + '-rate-of-return', coinRateStr, coinRate);
    } catch {}
  };

  socket.onerror = () => console.warn('업비트 웹소켓 연결 실패');
}

/* ── 포트폴리오 차트 (Highcharts) ──────────────────────────────── */
async function renderPortfolioChart(holdCryptoList, marketArrayList, memberAsset) {
  try {
    let upbitData = [];
    if (marketArrayList.length) {
      const marketListStr = marketArrayList.join(',');
      const upbitRes = await fetch('/upbit-api/ticker?markets=' + encodeURIComponent(marketListStr));
      if (upbitRes.ok) upbitData = await upbitRes.json();
    }

    const priceMap = {};
    upbitData.forEach(d => { priceMap[d.market.split('-')[1]] = d.trade_price; });

    let totalEval = 0;
    const evalMap = {};
    holdCryptoList.forEach(h => {
      const price = priceMap[h.marketCodeOnlySymbol] || 0;
      const eval_ = Math.round(price * h.holdCount);
      evalMap[h.marketCodeOnlySymbol] = eval_;
      totalEval += eval_;
    });

    const totalAsset = memberAsset + totalEval;
    const chartData = holdCryptoList.map(h => ({
      name: h.marketCodeOnlySymbol,
      y: totalAsset > 0 ? (evalMap[h.marketCodeOnlySymbol] / totalAsset) * 100 : 0,
    }));
    chartData.push({ name: 'KRW', y: totalAsset > 0 ? (memberAsset / totalAsset) * 100 : 100 });

    const accentPalette = ['#7C5CFC','#5865F2','#A78BFA','#E11D48','#2563EB','#059669','#F59E0B','#8B5CF6'];
    Highcharts.chart('hold_asset_chart', {
      chart: { plotBackgroundColor:'transparent', backgroundColor:'transparent', type:'pie',
               style:{ fontFamily:"'Pretendard', sans-serif" } },
      title: { text:'보유 비중', align:'center', style:{ color:'#334155', fontSize:'14px', fontWeight:'800' } },
      tooltip: { backgroundColor:'#1A1A2E', borderColor:'rgba(124,92,252,0.3)', style:{ color:'#fff' }, pointFormat:'{series.name}: <b>{point.percentage:.1f}%</b>' },
      plotOptions: { pie: { cursor:'pointer', colors:accentPalette, borderWidth:2, borderColor:'rgba(255,255,255,0.06)', borderRadius:4,
        dataLabels:{ enabled:true, format:'<b style="color:rgba(255,255,255,0.85)">{point.name}</b><br><span style="color:#A78BFA">{point.percentage:.1f}%</span>',
          distance:-45, style:{ fontSize:'12px', fontWeight:'700', textOutline:'none' }, filter:{ property:'percentage', operator:'>', value:4 } } } },
      credits: { enabled:false },
      series: [{ name:'비중', data:chartData }],
    });
  } catch {}
}

/* ── 유틸 ────────────────────────────────────────────────────── */
function setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }
function setColorText(id, val, numericVal) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = val;
  el.style.color = numericVal > 0 ? '#F87171' : numericVal < 0 ? '#60A5FA' : 'rgba(255,255,255,0.7)';
}
function fmt(n)          { return new Intl.NumberFormat('ko-KR').format(n); }
function fmtDec(n, dec)  { return new Intl.NumberFormat('ko-KR', { maximumFractionDigits: dec }).format(n); }
