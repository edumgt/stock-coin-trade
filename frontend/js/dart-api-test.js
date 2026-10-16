document.addEventListener('DOMContentLoaded', () => {
  const code = document.getElementById('dart-code');
  const year = document.getElementById('dart-year');
  const reprt = document.getElementById('dart-reprt');
  const status = document.getElementById('dart-status');
  const output = document.getElementById('dart-result');
  const summary = document.getElementById('dart-summary');
  const buttons = [...document.querySelectorAll('[data-dart]')];
  const won = v => v == null ? '-' : Number(v).toLocaleString('ko-KR') + '원';
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  document.getElementById('dart-preset').addEventListener('change', event => { code.value = event.target.value; });
  buttons.forEach(button => button.addEventListener('click', async () => {
    const stockCode = code.value.trim();
    if (!/^\d{6}$/.test(stockCode) || !year.checkValidity() || !year.value) {
      status.textContent = '종목코드는 숫자 6자리, 사업연도는 2015 이상 정수로 입력하세요.';
      return;
    }
    buttons.forEach(b => { b.disabled = true; });
    status.textContent = 'DART에 조회 중입니다… (첫 조회는 고유번호 목록을 내려받아 10초 안팎 걸릴 수 있습니다)';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 40000);
    try {
      const kind = button.dataset.dart;
      const params = new URLSearchParams({stock_code: stockCode});
      if (kind === 'financials') { params.set('bsns_year', year.value); params.set('reprt_code', reprt.value); }
      const response = await fetch('/api/dart-test/' + kind + '?' + params, {signal: controller.signal});
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.message || '요청을 확인하거나 잠시 후 다시 시도하세요.');
      const r = data.result;
      status.textContent = '조회 성공 · ' + r.source + ' · ' + r.corp_name + (r.is_preferred ? ' (보통주 ' + r.resolved_stock_code + ' 기준)' : '') + ' · 조회 시각: ' + new Date(r.fetched_at).toLocaleString('ko-KR', {timeZone:'Asia/Seoul'}) + ' KST · 상태: ' + r.status;
      if (kind === 'company') {
        const c = r.company;
        summary.innerHTML = '<table><tbody>' + [['회사명', c.corp_name + (c.corp_name_eng ? ' / ' + c.corp_name_eng : '')], ['시장구분', c.corp_cls_name], ['대표자', c.ceo_nm], ['설립일', c.est_dt], ['결산월', c.acc_mt + '월'], ['업종코드', c.induty_code], ['홈페이지', c.hm_url]].map(([k, v]) => '<tr><th>' + esc(k) + '</th><td>' + esc(v || '-') + '</td></tr>').join('') + '</tbody></table>';
      } else if (kind === 'disclosures') {
        summary.innerHTML = r.disclosures.length ? '<p>최근 ' + r.window_days + '일 공시 ' + r.total_count + '건 중 ' + r.disclosures.length + '건</p><table><thead><tr><th>접수일</th><th>보고서명</th><th>제출인</th></tr></thead><tbody>' + r.disclosures.map(d => '<tr><td>' + esc(d.rcept_dt) + '</td><td><a href="' + esc(d.viewer_url) + '" target="_blank" rel="noopener">' + esc(d.report_nm) + '</a></td><td>' + esc(d.flr_nm) + '</td></tr>').join('') + '</tbody></table>' : '<p>조회 구간에 공시가 없습니다.</p>';
      } else {
        const s = r.summary;
        summary.innerHTML = '<p>' + esc(r.bsns_year + '년 ' + r.report_name + ' · ' + r.fs_div + ' 재무제표') + '</p><table><tbody>' + [['자산총계', s.assets], ['부채총계', s.liabilities], ['자본총계', s.equity], ['매출액', s.revenue], ['영업이익', s.operating_income], ['당기순이익', s.net_income]].map(([k, v]) => '<tr><th>' + k + '</th><td>' + won(v) + '</td></tr>').join('') + '</tbody></table>';
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
