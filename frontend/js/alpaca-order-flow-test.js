(() => {
  const apiBase = window.APP_CONFIG?.apiBase || '';
  const confirm = document.getElementById('confirm');
  const run = document.getElementById('run');
  const result = document.getElementById('result');
  if (!confirm || !run || !result) return;
  confirm.addEventListener('change', () => { run.disabled = !confirm.checked; });
  run.addEventListener('click', async () => {
    if (!confirm.checked) return;
    run.disabled = true; result.classList.remove('error');
    result.textContent = 'Alpaca Paper 주문과 자동 취소를 점검하는 중…';
    try {
      const response = await fetch(`${apiBase}/api/alpaca-test/paper/order-flow-test`, { method: 'POST', credentials: 'include' });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.message || '주문 흐름 테스트에 실패했습니다.');
      const test = data.result;
      result.textContent = ['성공', `환경: ${test.environment}`, `종목: ${test.symbol}`, `매도호가: $${test.askPrice}`, `테스트 지정가: $${test.testLimitPrice}`, `수량: ${test.quantity}주`, `주문: ${test.order}`, `취소: ${test.cancel}`].join('\n');
    } catch (error) { result.classList.add('error'); result.textContent = `점검 결과: 실패\n${error.message}`; }
    finally { run.disabled = !confirm.checked; }
  });
})();
