(async () => {
  const user = await initPage({ requireAuth: true });
  if (!user) return;
  const apiBase = window.APP_CONFIG?.apiBase || '';
  const confirm = document.getElementById('confirm');
  const run = document.getElementById('run');
  const result = document.getElementById('result');
  if (!confirm || !run || !result) return;
  // Check the broker's calendar on entry (holidays and DST included).
  async function notifyMarketStatus() {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch(`${apiBase}/api/alpaca-test/market/clock`, {
        credentials: 'include', cache: 'no-store', signal: controller.signal,
      });
      const data = await response.json();
      if (!response.ok || !data.ok || typeof data.result?.isOpen !== 'boolean') {
        throw new Error('시장 상태 조회 실패');
      }
      if (!data.result.isOpen) {
        window.showToast?.('현재 미장 개장시간이 아닙니다.', { type: 'warn', duration: 5000 });
      }
    } catch (_) {
      window.showToast?.('미장 개장 여부를 확인하지 못했습니다. 잠시 후 다시 확인해 주세요.', { type: 'warn', duration: 5000 });
    } finally {
      clearTimeout(timeout);
    }
  }
  notifyMarketStatus();
  confirm.addEventListener('change', () => { run.disabled = !confirm.checked; });
  run.addEventListener('click', async () => {
    if (!confirm.checked) return;
    run.disabled = true; result.classList.remove('error');
    result.textContent = 'Alpaca Paper 주문과 자동 취소를 점검하는 중…';
    try {
      const response = await fetch(`${apiBase}/api/alpaca-test/paper/order-flow-test`, { method: 'POST', credentials: 'include' });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        if (data.code === 'MARKET_CLOSED' || data.code === 'NO_SAFE_PRICE') {
          window.showToast?.(data.message, { type: 'warn' });
        }
        throw new Error(data.message || '주문 흐름 테스트에 실패했습니다.');
      }
      const test = data.result;
      result.textContent = ['성공', `환경: ${test.environment}`, `종목: ${test.symbol}`, `매도호가: $${test.askPrice}`, `테스트 지정가: $${test.testLimitPrice}`, `수량: ${test.quantity}주`, `주문: ${test.order}`, `취소: ${test.cancel}`].join('\n');
    } catch (error) { result.classList.add('error'); result.textContent = `점검 결과: 실패\n${error.message}`; }
    finally { run.disabled = !confirm.checked; }
  });
})();
