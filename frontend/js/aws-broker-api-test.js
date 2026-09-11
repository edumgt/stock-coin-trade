(() => {
  const apiBase = window.APP_CONFIG?.apiBase || '';
  const formatQuote = (data) => {
    if (!data.ok) return `점검 결과: 실패\n${data.message || '알 수 없는 오류'}`;
    const q = data.quote;
    return [
      '성공', `증권사: ${q.broker}`, `종목코드: ${q.symbol}`,
      `현재가: ${Number(q.price ?? 0).toLocaleString()}원`,
      `전일대비: ${q.change ?? '-'}`, `등락률: ${q.changeRate ?? '-'}%`,
      `누적거래량: ${q.volume ?? '-'}`, `체결시각: ${q.tradeTime || '-'}`,
    ].join('\n');
  };
  const formatTokenCheck = (data) => {
    if (!data.ok) return `점검 결과: 실패\n${data.message || '알 수 없는 오류'}`;
    const c = data.check;
    return [
      '성공', `증권사: ${c.broker}`, `토큰 유형: ${c.tokenType}`,
      `유효기간: ${c.expiresIn}초`,
    ].join('\n');
  };
  const runQuoteOrToken = async (button) => {
    const broker = button.dataset.broker;
    const result = document.getElementById(`${broker}-result`);
    let url;
    if (broker === 'kb') {
      url = `${apiBase}/api/aws-broker-test/kb/token`;
    } else {
      const symbol = document.getElementById(`${broker}-symbol`).value.trim();
      if (!/^\d{6}$/.test(symbol)) { result.textContent = '종목코드는 6자리 숫자로 입력하세요.'; return; }
      url = `${apiBase}/api/aws-broker-test/${broker}/quote?symbol=${encodeURIComponent(symbol)}`;
    }
    button.disabled = true;
    result.classList.remove('result--error');
    result.textContent = 'AWS SSM Parameter Store에서 키를 읽어 서버가 읽기 전용 API를 호출하는 중…';
    try {
      const response = await fetch(url);
      const data = await response.json();
      result.textContent = broker === 'kb' ? formatTokenCheck(data) : formatQuote(data);
      result.classList.toggle('result--error', !data.ok);
    } catch (error) {
      result.textContent = `요청 실패\n${error.message}`;
      result.classList.add('result--error');
    } finally { button.disabled = false; }
  };

  const testBuilders = {
    'ssm-status': () => '/api/aws-broker-test/ssm/status',
    'kis-balance': () => '/api/aws-broker-test/kis/balance',
    'kb-quote': () => {
      const symbol = document.getElementById('kb-symbol').value.trim();
      if (!/^\d{6}$/.test(symbol)) throw new Error('종목코드는 6자리 숫자로 입력하세요.');
      return `/api/aws-broker-test/kb/quote?symbol=${encodeURIComponent(symbol)}`;
    },
  };

  const runGenericTest = async (button) => {
    const testId = button.dataset.test;
    const result = document.getElementById(`${testId}-result`);
    let path;
    try {
      path = testBuilders[testId]();
    } catch (error) {
      result.textContent = error.message;
      return;
    }
    button.disabled = true;
    result.classList.remove('result--error');
    result.textContent = 'AWS SSM Parameter Store에서 키를 읽어 서버가 읽기 전용 API를 호출하는 중…';
    try {
      const response = await fetch(`${apiBase}${path}`);
      const data = await response.json();
      result.textContent = JSON.stringify(data, null, 2);
      result.classList.toggle('result--error', !data.ok);
    } catch (error) {
      result.textContent = `요청 실패\n${error.message}`;
      result.classList.add('result--error');
    } finally { button.disabled = false; }
  };

  document.querySelectorAll('.run[data-broker]').forEach((button) => {
    button.addEventListener('click', () => runQuoteOrToken(button));
  });
  document.querySelectorAll('.run-sm[data-test]').forEach((button) => {
    button.addEventListener('click', () => runGenericTest(button));
  });
})();
