document.addEventListener('DOMContentLoaded', () => {
  const code = document.getElementById('fred-series');
  const limit = document.getElementById('fred-limit');
  const status = document.getElementById('fred-status');
  const output = document.getElementById('fred-result');
  const summary = document.getElementById('fred-summary');
  const buttons = [...document.querySelectorAll('[data-fred]')];
  document.getElementById('fred-preset').addEventListener('change', event => { code.value = event.target.value; });
  buttons.forEach(button => button.addEventListener('click', async () => {
    const series = code.value.trim().toUpperCase();
    if (!/^[A-Z0-9_]{1,40}$/.test(series) || !limit.checkValidity() || !limit.value) {
      status.textContent = '지표 코드는 영문·숫자·밑줄 1~40자리, 조회 개수는 1~200 정수로 입력하세요.';
      return;
    }
    buttons.forEach(b => { b.disabled = true; });
    status.textContent = 'FRED에 조회 중입니다…';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 25000);
    try {
      const params = new URLSearchParams({series_id: series});
      if (button.dataset.fred === 'observations') params.set('limit', limit.value);
      const response = await fetch('/api/fred-test/' + button.dataset.fred + '?' + params, {signal: controller.signal});
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.message || '요청을 확인하거나 잠시 후 다시 시도하세요.');
      const result = data.result;
      status.textContent = '조회 성공 · ' + result.source + ' · 조회 시각: ' + new Date(result.fetched_at).toLocaleString('ko-KR', {timeZone:'Asia/Seoul'}) + ' KST · 상태: ' + result.status;
      summary.textContent = result.series ? result.series.title + ' · 단위: ' + result.series.units + ' · 주기: ' + result.series.frequency : result.latest ? '최신 유효 관측: ' + result.latest.date + ' / ' + result.latest.value + ' (단위는 지표 정보에서 확인)' : '조회 구간에 유효한 관측값이 없습니다.';
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
