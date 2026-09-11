(() => {
  const apiBase = window.APP_CONFIG?.apiBase || '';
  const button = document.getElementById('run-test');
  const result = document.getElementById('result');
  if (button && result) {
    button.addEventListener('click', async () => {
      button.disabled = true;
      result.classList.remove('result--error');
      result.textContent = 'AWS SSM Parameter Store에서 키를 읽어 Alpaca Paper API에 읽기 전용 요청을 보내는 중…';
      try {
        const response = await fetch(`${apiBase}/api/aws-alpaca-test/paper/account`);
        const data = await response.json();
        if (!data.ok) {
          result.classList.add('result--error');
          result.textContent = `점검 결과: 실패\n${data.message || '알 수 없는 오류'}`;
          return;
        }
        const info = data.result;
        result.textContent = [
          '점검 결과: 성공', `환경: ${info.environment}`, `연결: ${info.connection}`,
          `계정 상태: ${info.accountStatus || '-'}`, `통화: ${info.currency || '-'}`,
          `거래 차단: ${info.tradingBlocked ? '예' : '아니오'}`,
          `계정 차단: ${info.accountBlocked ? '예' : '아니오'}`,
        ].join('\n');
      } catch (error) {
        result.classList.add('result--error');
        result.textContent = `요청 실패\n${error.message}`;
      } finally { button.disabled = false; }
    });
  }

  const testBuilders = {
    positions: () => '/api/aws-alpaca-test/paper/positions',
    clock: () => '/api/aws-alpaca-test/paper/clock',
    asset: () => {
      const symbol = document.getElementById('asset-symbol')?.value.trim().toUpperCase();
      if (!/^[A-Z]{1,10}$/.test(symbol)) throw new Error('종목 심볼은 영문 1~10자로 입력하세요.');
      return `/api/aws-alpaca-test/paper/asset?symbol=${encodeURIComponent(symbol)}`;
    },
  };

  document.querySelectorAll('.run-sm[data-test]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const testId = btn.dataset.test;
      const box = document.getElementById(`${testId}-result`);
      let path;
      try {
        path = testBuilders[testId]();
      } catch (error) {
        box.textContent = error.message;
        return;
      }
      btn.disabled = true;
      box.classList.remove('result--error');
      box.textContent = 'AWS SSM Parameter Store에서 키를 읽어 서버가 읽기 전용 API를 호출하는 중…';
      try {
        const response = await fetch(`${apiBase}${path}`);
        const data = await response.json();
        box.textContent = JSON.stringify(data, null, 2);
        box.classList.toggle('result--error', !data.ok);
      } catch (error) {
        box.textContent = `요청 실패\n${error.message}`;
        box.classList.add('result--error');
      } finally { btn.disabled = false; }
    });
  });
})();
