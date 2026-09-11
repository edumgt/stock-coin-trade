(() => {
  const apiBase = window.APP_CONFIG?.apiBase || '';
  const exchange = document.body.dataset.exchange;
  const symbolInput = document.getElementById('symbol');
  const result = document.getElementById('result');
  const run = async (kind) => {
    const symbol = symbolInput.value.trim();
    if (!symbol) { result.textContent = '거래쌍을 입력하세요.'; return; }
    const button = document.querySelector(`[data-test="${kind}"]`);
    button.disabled = true; result.classList.remove('error'); result.textContent = '거래소 공개 API를 조회하는 중…';
    try {
      const response = await fetch(`${apiBase}/api/crypto-exchange-test/${exchange}/${kind}?symbol=${encodeURIComponent(symbol)}`);
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.message || '조회에 실패했습니다.');
      result.textContent = JSON.stringify(data.result, null, 2);
    } catch (error) { result.classList.add('error'); result.textContent = `조회 실패\n${error.message}`; }
    finally { button.disabled = false; }
  };
  document.querySelectorAll('[data-test]').forEach((button) => button.addEventListener('click', () => run(button.dataset.test)));
})();
