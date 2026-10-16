document.addEventListener('DOMContentLoaded', () => {
  const code = document.getElementById('krx-code');
  const market = document.getElementById('krx-market');
  const date = document.getElementById('krx-date');
  const indexSel = document.getElementById('krx-index');
  const status = document.getElementById('krx-status');
  const output = document.getElementById('krx-result');
  const summary = document.getElementById('krx-summary');
  const buttons = [...document.querySelectorAll('[data-krx]')];
  const num = (v, unit) => v == null ? '-' : Number(v).toLocaleString('ko-KR') + (unit || '');
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const row = (k, v) => '<tr><th>' + esc(k) + '</th><td>' + v + '</td></tr>';
  document.getElementById('krx-preset').addEventListener('change', event => {
    const [symbol, mkt] = event.target.value.split('|');
    code.value = symbol; market.value = mkt;
  });
  buttons.forEach(button => button.addEventListener('click', async () => {
    const symbol = code.value.trim();
    const basDd = date.value.trim();
    if (!/^\d{6}$/.test(symbol) || (basDd && !/^\d{8}$/.test(basDd))) {
      status.textContent = '종목코드는 숫자 6자리, 기준일은 YYYYMMDD 8자리(또는 빈칸)로 입력하세요.';
      return;
    }
    buttons.forEach(b => { b.disabled = true; });
    status.textContent = 'KRX에 조회 중입니다… (시장 전 종목 응답을 받으므로 첫 조회는 몇 초 걸립니다)';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 40000);
    try {
      const kind = button.dataset.krx;
      const params = new URLSearchParams();
      if (basDd) params.set('bas_dd', basDd);
      if (kind === 'index') params.set('service', indexSel.value);
      else { params.set('market', market.value); if (kind !== 'market') params.set('symbol', symbol); }
      const response = await fetch('/api/krx-test/' + kind + '?' + params, {signal: controller.signal});
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.message || '요청을 확인하거나 잠시 후 다시 시도하세요.');
      const r = data.result;
      status.textContent = '조회 성공 · ' + r.source + ' · 기준일 ' + r.bas_dd + ' · 조회 시각: ' + new Date(r.fetched_at).toLocaleString('ko-KR', {timeZone:'Asia/Seoul'}) + ' KST · 상태: ' + r.status;
      if (kind === 'stock') {
        const s = r.stock;
        summary.innerHTML = '<table><tbody>' + row('종목', esc(s.ISU_NM + ' (' + s.ISU_CD + ') · ' + (s.MKT_NM || r.market))) + row('종가', num(s.TDD_CLSPRC, '원')) + row('전일 대비 / 등락률', num(s.CMPPREVDD_PRC, '원') + ' / ' + num(s.FLUC_RT, '%')) + row('시가 / 고가 / 저가', num(s.TDD_OPNPRC, '원') + ' / ' + num(s.TDD_HGPRC, '원') + ' / ' + num(s.TDD_LWPRC, '원')) + row('거래량 / 거래대금', num(s.ACC_TRDVOL, '주') + ' / ' + num(s.ACC_TRDVAL, '원')) + row('시가총액 / 상장주식수', num(s.MKTCAP, '원') + ' / ' + num(s.LIST_SHRS, '주')) + '</tbody></table>';
      } else if (kind === 'market') {
        summary.innerHTML = '<p>' + esc(r.market) + ' ' + r.total_rows + '종목 중 ' + r.sort + ' 상위 ' + r.stocks.length + '종목</p><table><thead><tr><th>#</th><th>종목</th><th>종가</th><th>등락률</th><th>시가총액</th></tr></thead><tbody>' + r.stocks.map((s, i) => '<tr><td>' + (i + 1) + '</td><td>' + esc(s.ISU_NM) + ' (' + esc(s.ISU_CD) + ')</td><td>' + num(s.TDD_CLSPRC, '원') + '</td><td>' + num(s.FLUC_RT, '%') + '</td><td>' + num(s.MKTCAP, '원') + '</td></tr>').join('') + '</tbody></table>';
      } else if (kind === 'base-info') {
        const s = r.info;
        summary.innerHTML = '<table><tbody>' + row('종목', esc((s.ISU_ABBRV || s.ISU_NM) + ' (' + s.ISU_SRT_CD + ') · ' + (s.ISU_ENG_NM || ''))) + row('표준코드', esc(s.ISU_CD)) + row('시장 / 증권구분 / 소속부', esc((s.MKT_TP_NM || '-') + ' / ' + (s.SECUGRP_NM || '-') + ' / ' + (s.SECT_TP_NM || '-'))) + row('상장일', esc(s.LIST_DD)) + row('주식종류', esc(s.KIND_STKCERT_TP_NM || '-')) + row('액면가 / 상장주식수', num(s.PARVAL, '원') + ' / ' + num(s.LIST_SHRS, '주')) + '</tbody></table>';
      } else {
        const h = r.headline;
        summary.innerHTML = '<p>' + esc(r.service) + ' 계열 ' + r.indices.length + '개 지수 · 대표: ' + esc(h.IDX_NM) + ' ' + num(h.CLSPRC_IDX) + ' (' + num(h.CMPPREVDD_IDX) + ' / ' + num(h.FLUC_RT, '%') + ')</p><table><thead><tr><th>지수</th><th>종가</th><th>전일 대비</th><th>등락률</th><th>거래대금</th></tr></thead><tbody>' + r.indices.slice(0, 30).map(s => '<tr><td>' + esc(s.IDX_NM) + '</td><td>' + num(s.CLSPRC_IDX) + '</td><td>' + num(s.CMPPREVDD_IDX) + '</td><td>' + num(s.FLUC_RT, '%') + '</td><td>' + num(s.ACC_TRDVAL, '원') + '</td></tr>').join('') + '</tbody></table>';
      }
      output.textContent = JSON.stringify(data, null, 2);
    } catch (error) {
      status.textContent = '조회 실패 · ' + (error.name === 'AbortError' ? '응답 시간이 초과되었습니다. 다시 시도하세요.' : error.message);
      summary.textContent = '';
      output.textContent = '이번 요청의 결과가 없습니다.';
    } finally {
      clearTimeout(timeout);
      buttons.forEach(b => { b.disabled = false; });
    }
  }));
});
