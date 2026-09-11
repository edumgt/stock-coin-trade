(() => {
  const apiBase = window.APP_CONFIG?.apiBase || '';
  const confirm = document.getElementById('confirm');
  const run = document.getElementById('run');
  const result = document.getElementById('result');

  confirm.addEventListener('change', () => { run.disabled = !confirm.checked; });
  run.addEventListener('click', async () => {
    run.disabled = true;
    result.classList.remove('error');
    result.textContent = 'KIS Testbed에서 모의 주문 → 정정 → 취소를 실행하는 중…';
    try {
      const response = await fetch(`${apiBase}/api/broker-test/kis/order-flow-test`, {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
      });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.message || '테스트를 완료하지 못했습니다.');
      const test = data.test;
      result.textContent = [
        '테스트 성공', `환경: ${test.environment}`, `종목: ${test.symbol}`,
        `안전 확인 현재가: ${Number(test.currentPrice).toLocaleString()}원`,
        `주문: 성공 (${Number(test.testPrice).toLocaleString()}원)`,
        `정정: 성공 (${Number(test.amendedPrice).toLocaleString()}원)`, '취소: 성공',
      ].join('\n');
    } catch (error) {
      result.textContent = `테스트 실패\n${error.message}`;
      result.classList.add('error');
    } finally {
      run.disabled = !confirm.checked;
    }
  });
})();
