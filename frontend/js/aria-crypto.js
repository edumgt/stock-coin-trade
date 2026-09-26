(() => {
  const apiBase = window.APP_CONFIG?.apiBase || '';
  const $ = (id) => document.getElementById(id);

  const keyOptions = () => ({
    passphrase: $('aria-passphrase').value,
    key_bits: Number($('aria-key-bits').value),
  });

  const setResult = (el, text, isError = false) => {
    el.textContent = text;
    el.classList.toggle('result--error', isError);
  };

  const callApi = async (path, body) => {
    const response = await fetch(`${apiBase}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return response.json();
  };

  // 1) 평문 -> API 암호화 -> base64 암호문
  const encrypt = async () => {
    const text = $('aria-plain').value;
    const out = $('aria-cipher');
    if (!text) { setResult($('aria-encrypt-result'), '암호화할 문자열을 입력하세요.', true); return; }
    $('aria-encrypt-btn').disabled = true;
    setResult($('aria-encrypt-result'), '서버에서 ARIA-CBC로 암호화하는 중…');
    try {
      const data = await callApi('/api/aria/encrypt', { text, ...keyOptions() });
      if (!data.ok) { setResult($('aria-encrypt-result'), `실패: ${data.message}`, true); return; }
      out.value = data.cipher;
      $('aria-cipher-in').value = data.cipher;
      setResult($('aria-encrypt-result'), [
        '성공',
        `알고리즘: ${data.algorithm} / ${data.padding}`,
        `키 출처: ${data.key_source === 'passphrase' ? '입력한 비밀번호(SHA-256 유도)' : '서버 기본 키(ARIA_DEMO_KEY)'}`,
        `인코딩: ${data.encoding} · ${data.cipher_length}자`,
        'IV가 매번 랜덤이라 같은 평문도 암호문은 매번 달라집니다.',
      ].join('\n'));
      renderScenario(text, data.cipher);
    } catch (error) {
      setResult($('aria-encrypt-result'), `요청 실패\n${error.message}`, true);
    } finally { $('aria-encrypt-btn').disabled = false; }
  };

  // 2) base64 암호문 -> API 복호화 -> 평문
  const decrypt = async () => {
    const cipher = $('aria-cipher-in').value.trim();
    if (!cipher) { setResult($('aria-decrypt-result'), '복호화할 base64 암호문을 붙여넣으세요.', true); return; }
    $('aria-decrypt-btn').disabled = true;
    setResult($('aria-decrypt-result'), '서버에서 복호화하는 중…');
    try {
      const data = await callApi('/api/aria/decrypt', { cipher, ...keyOptions() });
      if (!data.ok) { setResult($('aria-decrypt-result'), `실패: ${data.message}`, true); $('aria-decrypted').value = ''; return; }
      $('aria-decrypted').value = data.text;
      setResult($('aria-decrypt-result'), `성공 · ${data.algorithm} · 키 출처: ${data.key_source}`);
    } catch (error) {
      setResult($('aria-decrypt-result'), `요청 실패\n${error.message}`, true);
    } finally { $('aria-decrypt-btn').disabled = false; }
  };

  // 3) 웹앱 시나리오: 저장 필드가 평문 -> 암호문으로 바뀌는 과정을 표로 보여준다.
  const renderScenario = (plain, cipher) => {
    const tbody = $('aria-scenario-body');
    if (!tbody) return;
    const short = cipher.length > 44 ? `${cipher.slice(0, 44)}…` : cipher;
    tbody.innerHTML = '';
    [
      ['브라우저 입력값', plain, '사용자가 폼에 적은 원문'],
      ['POST /api/aria/encrypt', short, '서버가 반환한 base64(IV‖암호문)'],
      ['DB 저장 컬럼 (phone_enc)', short, '원문 대신 이 값을 저장'],
      ['화면 표시 (복호화 후)', plain, 'POST /api/aria/decrypt 결과를 렌더링'],
    ].forEach(([step, value, note]) => {
      const tr = document.createElement('tr');
      [step, value, note].forEach((cell, i) => {
        const td = document.createElement('td');
        if (i === 1) { const code = document.createElement('code'); code.textContent = cell; td.appendChild(code); }
        else td.textContent = cell;
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    $('aria-scenario').hidden = false;
  };

  const loadInfo = async () => {
    const el = $('aria-info-result');
    try {
      const response = await fetch(`${apiBase}/api/aria/info`);
      const data = await response.json();
      const t = data.self_test || {};
      setResult(el, [
        `RFC 5794 자체 검증: ${t.passed ? '통과' : '실패'}`,
        `키: ${t.key}`, `평문: ${t.plaintext}`, `기대 암호문: ${t.expected}`, `서버 계산: ${t.actual}`,
        `서버 기본 키 설정(ARIA_DEMO_KEY): ${data.server_key_configured ? '설정됨' : '미설정(데모 고정 키 사용)'}`,
      ].join('\n'), !t.passed);
    } catch (error) {
      setResult(el, `서버 정보를 불러오지 못했습니다\n${error.message}`, true);
    }
  };

  const copy = async (sourceId, button) => {
    const value = $(sourceId).value;
    if (!value) return;
    try { await navigator.clipboard.writeText(value); button.textContent = '복사됨'; }
    catch { button.textContent = '복사 실패'; }
    setTimeout(() => { button.textContent = '복사'; }, 1200);
  };

  document.addEventListener('DOMContentLoaded', async () => {
    await initPage();
    $('aria-encrypt-btn').addEventListener('click', encrypt);
    $('aria-decrypt-btn').addEventListener('click', decrypt);
    document.querySelectorAll('[data-copy]').forEach((b) => b.addEventListener('click', () => copy(b.dataset.copy, b)));
    $('aria-info-btn').addEventListener('click', loadInfo);
    loadInfo();
  });
})();
