/* ── 물타기 계산기 ───────────────────────────────────────────────────────── */
const fmtNum = (n) => Number.isFinite(n) ? new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 4 }).format(n) : '-';

function parseNum(id) {
  const raw = document.getElementById(id).value.replaceAll(',', '').trim();
  if (raw === '') return NaN;
  const n = Number(raw);
  return Number.isFinite(n) ? n : NaN;
}

function onBuyInputModeChange() {
  const mode = document.querySelector('input[name="buyInputMode"]:checked').value;
  document.getElementById('buyQty').style.display    = mode === 'qty'    ? '' : 'none';
  document.getElementById('buyAmount').style.display  = mode === 'amount' ? '' : 'none';
  recalc();
}

function recalc() {
  const holdQty   = parseNum('holdQty');
  const holdAvg   = parseNum('holdAvgPrice');
  const buyPrice  = parseNum('buyPrice');
  const mode      = document.querySelector('input[name="buyInputMode"]:checked').value;

  let buyQty = NaN, buyAmount = NaN;
  if (mode === 'qty') {
    buyQty = parseNum('buyQty');
    if (Number.isFinite(buyQty) && Number.isFinite(buyPrice)) buyAmount = buyQty * buyPrice;
  } else {
    buyAmount = parseNum('buyAmount');
    if (Number.isFinite(buyAmount) && Number.isFinite(buyPrice) && buyPrice > 0) buyQty = buyAmount / buyPrice;
  }

  document.getElementById('r_buyAmount').textContent = Number.isFinite(buyAmount) ? fmtNum(Math.round(buyAmount)) + ' KRW' : '-';
  document.getElementById('r_buyQty').textContent     = Number.isFinite(buyQty)    ? fmtNum(buyQty) : '-';

  const valid = [holdQty, holdAvg, buyPrice, buyQty, buyAmount].every(Number.isFinite) && holdQty >= 0 && buyQty >= 0;
  if (!valid) {
    document.getElementById('r_totalQty').textContent    = '-';
    document.getElementById('r_totalAmount').textContent = '-';
    document.getElementById('r_newAvg').textContent       = '-';
    document.getElementById('r_avgChange').textContent    = '-';
  } else {
    const totalQty    = holdQty + buyQty;
    const totalAmount = holdQty * holdAvg + buyAmount;
    const newAvg       = totalQty > 0 ? totalAmount / totalQty : NaN;
    const avgChangeRate = holdAvg > 0 ? ((newAvg - holdAvg) / holdAvg) * 100 : NaN;

    document.getElementById('r_totalQty').textContent    = fmtNum(totalQty);
    document.getElementById('r_totalAmount').textContent = fmtNum(Math.round(totalAmount)) + ' KRW';
    document.getElementById('r_newAvg').textContent       = fmtNum(Math.round(newAvg)) + ' KRW';

    const changeEl = document.getElementById('r_avgChange');
    if (Number.isFinite(avgChangeRate)) {
      const sign  = avgChangeRate > 0 ? '+' : '';
      changeEl.textContent = `${sign}${avgChangeRate.toFixed(2)}%`;
      changeEl.style.color = avgChangeRate < 0 ? '#2563EB' : avgChangeRate > 0 ? '#E11D48' : 'var(--muted)';
    } else {
      changeEl.textContent = '-';
      changeEl.style.color = 'var(--fg)';
    }
  }

  recalcReverse(holdQty, holdAvg, buyPrice);
}

function recalcReverse(holdQty, holdAvg, buyPrice) {
  const box = document.getElementById('reverseResult');
  const targetAvg = parseNum('targetAvgPrice');

  if (!Number.isFinite(targetAvg)) {
    box.innerHTML = '<p style="color:var(--muted);font-size:13px;">목표 평균 매수가를 입력하면 추가 매수가 기준으로 필요한 매수 수량과 금액을 계산합니다.</p>';
    return;
  }
  if (![holdQty, holdAvg, buyPrice].every(Number.isFinite) || holdQty <= 0 || buyPrice <= 0) {
    box.innerHTML = '<p style="color:#E11D48;font-size:13px;">보유 수량 · 보유 평균가 · 추가 매수가를 먼저 입력하세요.</p>';
    return;
  }

  const denom = targetAvg - buyPrice;
  if (denom === 0) {
    box.innerHTML = '<p style="color:#E11D48;font-size:13px;">목표 평균가가 추가 매수가와 같아 계산할 수 없습니다.</p>';
    return;
  }

  const requiredQty = holdQty * (holdAvg - targetAvg) / denom;

  if (requiredQty <= 0) {
    box.innerHTML = '<p style="color:#E11D48;font-size:13px;">입력하신 추가 매수가로는 해당 목표 평균가에 도달할 수 없습니다. 목표 평균가가 보유 평균가와 추가 매수가 사이의 값인지 확인하세요.</p>';
    return;
  }

  const requiredAmount = requiredQty * buyPrice;
  box.innerHTML = `
    <div class="result-row"><span class="result-label">필요한 추가 매수 수량</span><span class="result-value">${fmtNum(requiredQty)}</span></div>
    <div class="result-row"><span class="result-label">필요한 추가 매수 금액</span><span class="result-value">${fmtNum(Math.round(requiredAmount))} KRW</span></div>
    <div class="result-row"><span class="result-label">도달 시 총 보유 수량</span><span class="result-value">${fmtNum(holdQty + requiredQty)}</span></div>
  `;
}

(async () => {
  await initPage();
  ['holdQty', 'holdAvgPrice', 'buyPrice', 'buyQty', 'buyAmount', 'targetAvgPrice'].forEach(id => {
    document.getElementById(id).addEventListener('input', recalc);
  });
  recalc();
})();
