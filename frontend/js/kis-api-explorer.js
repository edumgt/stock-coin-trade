// KIS API 탐색기: 카탈로그 목록 → 파라미터 폼 → 서버 경유 Testbed 호출 → 응답 JSON 시각화.
(() => {
  const apiBase = window.APP_CONFIG?.apiBase || '';
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  let catalog = { apis: [] };
  let user = null;
  let filter = 'demo';
  let query = '';
  let current = null;
  let lastResult = null;
  let view = 'table';

  // ── 목록 ────────────────────────────────────────────────────────────
  const badge = (api) => {
    if (api.method === 'POST') return '<span class="badge b-post">주문 POST</span>';
    return api.demoSupported ? '<span class="badge b-demo">모의</span>' : '<span class="badge b-real">실전전용</span>';
  };
  const matches = (api) => {
    if (filter === 'demo' && !api.demoSupported) return false;
    if (!query) return true;
    const hay = `${api.title} ${api.apiId} ${api.url} ${api.trIdDemo.join(' ')} ${api.trIdReal.join(' ')} ${api.id}`.toLowerCase();
    return hay.includes(query);
  };
  function renderList() {
    const groups = new Map();
    catalog.apis.filter(matches).forEach((api) => {
      if (!groups.has(api.category)) groups.set(api.category, []);
      groups.get(api.category).push(api);
    });
    if (!groups.size) { $('list').innerHTML = '<div class="empty" style="margin-top:12px">검색 결과가 없습니다.</div>'; return; }
    $('list').innerHTML = [...groups].map(([cat, apis]) => `
      <details class="x-cat" open><summary>${esc(cat)}<small>${apis.length}</small></summary>
        ${apis.map((a) => `<button class="x-item${current?.id === a.id ? ' on' : ''}" data-id="${esc(a.id)}"><span class="t">${esc(a.title)}</span>${badge(a)}</button>`).join('')}
      </details>`).join('');
  }
  function renderStats() {
    const demo = catalog.apis.filter((a) => a.demoSupported);
    const post = demo.filter((a) => a.method === 'POST').length;
    $('stats').innerHTML = [
      `분석한 REST API ${catalog.apis.length}개`,
      `Testbed 지원 ${demo.length}개 (조회 ${demo.length - post} · 주문 ${post})`,
      `분류 ${new Set(catalog.apis.map((a) => a.category)).size}개`,
      user?.loggedIn ? `로그인: ${esc(user.username)} (계좌 API 호출 가능)` : '계좌 API: 로그인한 회원만 호출 가능',
    ].map((t) => `<span>${t}</span>`).join('');
  }

  // ── 상세 + 폼 ────────────────────────────────────────────────────────
  const githubUrl = (api) => `https://github.com/koreainvestment/open-trading-api/blob/main/${api.source}`;
  function fieldHtml(p) {
    if (p.source === 'server') {
      return `<div class="x-field server"><label>${esc(p.label)}<code>${esc(p.key)}</code></label><input value="서버 .env 설정 사용" readonly><div class="hint">${esc(p.desc)}</div></div>`;
    }
    if (p.source !== 'user') return '';
    const descClean = (p.desc || '').replace(/\s*\(ex\..*\)\s*$/, '').trim();
    const hint = [p.example ? `예: ${p.example}` : '', descClean && descClean !== p.label ? descClean : ''].filter(Boolean).join(' · ');
    return `<div class="x-field"><label>${esc(p.label)}${p.required ? '<span class="req">*</span>' : ''}<code>${esc(p.key)}</code></label>
      <input name="${esc(p.key)}" value="${esc(p.default)}" placeholder="${esc(p.example || '')}" ${p.required ? 'required' : ''} maxlength="40">
      ${hint ? `<div class="hint">${esc(hint)}</div>` : ''}</div>`;
  }
  function selectorHtml(api) {
    if (!api.trSelector) return '';
    const opts = Object.entries(api.trSelector.map).map(([k, tr]) => `<option value="${esc(k)}">${esc(k)} → ${esc(tr)}</option>`).join('');
    return `<div class="x-field"><label>거래 ID 분기<code>${esc(api.trSelector.arg)}</code></label><select name="__variant">${opts}</select><div class="hint">예제 코드가 이 값에 따라 tr_id 를 고릅니다.</div></div>`;
  }
  function renderDetail(api) {
    current = api;
    lastResult = null;
    renderList();
    const fixed = api.params.filter((p) => p.source === 'fixed' || p.source === 'blank');
    const callable = api.demoSupported && api.method === 'GET' && (api.category !== '주문/계좌' || user?.loggedIn);
    let gate = '';
    if (api.method === 'POST') gate = `<div class="danger"><strong>주문성 API 입니다.</strong> 탐색기는 주문·정정·취소를 직접 보내지 않습니다. 파라미터 구조만 확인하고, 실행은 로그인 후 <a href="/kis-order-flow-test.html" style="text-decoration:underline">모의 주문 흐름 테스트</a>(주문 → 정정 → 취소, 안전장치 포함)에서만 합니다.</div>`;
    else if (!api.demoSupported) gate = `<div class="notice"><strong>모의투자(Testbed) 미지원 API 입니다.</strong> 공식 예제에 모의 분기(demo)가 없어 실전 계좌·실전 키가 필요합니다. 이 웹앱은 Testbed 만 호출하므로 목록과 파라미터 구조만 제공합니다.</div>`;
    else if (api.category === '주문/계좌' && !user?.loggedIn) gate = `<div class="notice">계좌 관련 API 는 이 웹앱에 로그인한 회원만 호출할 수 있습니다.</div>`;

    $('main').innerHTML = `
      <div class="kicker">${esc(api.category)} · ${esc(api.apiId || '국내주식')}</div>
      <h2 class="x-title">${esc(api.title)} ${badge(api)}</h2>
      <div class="x-meta">
        <span><span class="badge ${api.method === 'GET' ? 'b-get' : 'b-post'}">${api.method}</span> <code>${esc(api.url)}</code></span>
        <span>모의 tr_id: <code>${esc(api.trIdDemo.join(', ') || '없음')}</code></span>
        <span>실전 tr_id: <code>${esc(api.trIdReal.join(', ') || '-')}</code></span>
        <span><a href="${githubUrl(api)}" target="_blank" rel="noopener noreferrer" style="color:var(--accent-dark);text-decoration:underline">공식 예제 코드 ↗</a></span>
      </div>
      ${api.summary ? `<div class="x-summary">${esc(api.summary)}</div>` : ''}
      ${gate}
      <div class="x-sec"><h3>요청 파라미터</h3>
        <form id="form" class="x-form">${selectorHtml(api)}${api.params.map(fieldHtml).join('')}</form>
        ${fixed.length ? `<details style="margin-top:8px"><summary style="cursor:pointer;font-size:12px;color:var(--muted)">고정·공란 파라미터 ${fixed.length}개</summary><div class="x-meta" style="margin-top:6px">${fixed.map((p) => `<span><code>${esc(p.key)}</code> = "${esc(p.value ?? '')}" <small>(${esc(p.label)})</small></span>`).join('')}</div></details>` : ''}
        <div class="x-actions">
          <button class="btn" id="run" ${callable ? '' : 'disabled'}>${callable ? 'Testbed 호출' : '호출 불가'}</button>
          <button class="btn-alt" id="reset" type="button">기본값 복원</button>
          <span style="font-size:12px;color:var(--muted)">Testbed 초당 호출 제한이 있어 연속 클릭은 서버가 간격을 둡니다.</span>
        </div>
      </div>
      <div class="x-sec" id="resultSec"><h3>응답</h3><div class="empty">아직 호출하지 않았습니다.</div></div>`;
    $('run').addEventListener('click', runCall);
    $('reset').addEventListener('click', () => renderDetail(api));
    $('form').addEventListener('submit', (e) => { e.preventDefault(); runCall(); });
  }

  // ── 호출 ────────────────────────────────────────────────────────────
  async function runCall() {
    if (!current) return;
    const form = $('form');
    const params = {};
    let variant;
    form.querySelectorAll('input[name],select[name]').forEach((el) => {
      if (el.name === '__variant') variant = el.value; else params[el.name] = el.value.trim();
    });
    const run = $('run');
    run.disabled = true;
    $('resultSec').innerHTML = '<h3>응답</h3><div class="empty">서버가 KIS Testbed 를 호출하는 중…</div>';
    try {
      const response = await fetch(`${apiBase}/api/kis-explorer/call`, {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': user?.csrfToken || '' },
        body: JSON.stringify({ id: current.id, params, variant }),
      });
      const text = await response.text();
      let data;
      try { data = JSON.parse(text); } catch { throw new Error(`서버 응답을 해석할 수 없습니다 (HTTP ${response.status}).`); }
      if (data.body === undefined) throw new Error(data.message || `호출 실패 (HTTP ${response.status})`);
      lastResult = data;
      view = 'table';
      renderResult();
    } catch (error) {
      $('resultSec').innerHTML = `<h3>응답</h3><div class="danger">${esc(error.message)}</div>`;
    } finally { run.disabled = false; }
  }

  // ── 응답 시각화 ───────────────────────────────────────────────────────
  const NUM_RE = /^-?\d+(\.\d+)?$/;
  const RAW_KEY_RE = /(dt|date|time|hour|tm|cd|code|no|iscd|pdno|odno|brno|dvsn|yn|name|nm|tel|idx|ymd)$/i;
  const fmtValue = (key, v) => {
    const s = String(v ?? '');
    if (NUM_RE.test(s) && !RAW_KEY_RE.test(key) && !/^0\d/.test(s)) {
      const n = Number(s);
      return { text: n.toLocaleString(undefined, { maximumFractionDigits: 4 }), num: true };
    }
    return { text: s, num: false };
  };
  const label = (key) => lastResult.columns[key] || '';
  const outputs = () => Object.entries(lastResult.body).filter(([k, v]) => /^output/.test(k) && v !== null && typeof v === 'object');

  function tableHtml(key, rows) {
    if (!rows.length) return `<div class="x-block"><h4>${esc(key)}<small>0건</small></h4><div class="empty">데이터가 없습니다.</div></div>`;
    const cols = [...new Set(rows.flatMap((r) => Object.keys(r)))];
    const head = cols.map((c) => `<th>${esc(label(c) || c)}${label(c) ? `<small>${esc(c)}</small>` : ''}</th>`).join('');
    const body = rows.map((r) => `<tr>${cols.map((c) => { const f = fmtValue(c, r[c]); return `<td class="${f.num ? 'num' : ''}">${esc(f.text)}</td>`; }).join('')}</tr>`).join('');
    return `<div class="x-block"><h4>${esc(key)}<small>${rows.length}건 · ${cols.length}필드</small></h4><div class="tbl-wrap"><table class="tbl"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div></div>`;
  }
  function fieldsHtml(key, obj) {
    const entries = Object.entries(obj);
    if (!entries.length) return `<div class="x-block"><h4>${esc(key)}</h4><div class="empty">데이터가 없습니다.</div></div>`;
    const rows = entries.map(([k, v]) => { const f = fmtValue(k, v); return `<tr><td>${esc(label(k) || '-')}</td><td class="key">${esc(k)}</td><td class="${f.num ? 'num' : ''}">${esc(f.text)}</td></tr>`; }).join('');
    return `<div class="x-block"><h4>${esc(key)}<small>${entries.length}필드</small></h4><div class="tbl-wrap"><table class="tbl"><thead><tr><th>한글명</th><th>필드</th><th>값</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
  }
  function jsonHtml(obj) {
    const s = esc(JSON.stringify(obj, null, 2));
    return `<pre class="json">${s.replace(/("(?:[^"\\]|\\.)*")(\s*:)?|\b(-?\d+(?:\.\d+)?)\b|\b(true|false|null)\b/g, (m, str, colon, num, kw) => {
      if (str) return colon ? `<span class="k">${str}</span>${colon}` : `<span class="s">${str}</span>`;
      if (num) return `<span class="n">${num}</span>`;
      return `<span class="b">${kw}</span>`;
    })}</pre>`;
  }
  function renderResult() {
    const r = lastResult;
    const status = `<div class="x-status">
      <span class="badge ${r.ok ? 'b-ok' : 'b-err'}">${r.ok ? '성공' : '실패'}</span>
      <span>rt_cd <b>${esc(r.rtCd ?? '-')}</b></span><span>msg_cd <b>${esc(r.msgCd ?? '-')}</b></span><span>msg1 <b>${esc(r.msg1 || '-')}</b></span>
      <span>HTTP <b>${r.http}</b></span><span>tr_id <b>${esc(r.trId)}</b></span><span><b>${r.elapsedMs}ms</b></span>
      <span>요청: ${Object.entries(r.request).filter(([, v]) => v !== '').map(([k, v]) => `<code>${esc(k)}=${esc(v)}</code>`).join(' ')}</span>
    </div>`;
    const tabs = `<div class="x-tabs">${[['table', '표 / 필드'], ['json', 'JSON 원문']].map(([v, t]) => `<button data-v="${v}" class="${view === v ? 'on' : ''}">${t}</button>`).join('')}<button id="copy" style="margin-left:auto">JSON 복사</button></div>`;
    let body = '';
    if (view === 'json') body = jsonHtml(r.body);
    else {
      const outs = outputs();
      body = outs.length ? outs.map(([k, v]) => (Array.isArray(v) ? tableHtml(k, v) : fieldsHtml(k, v))).join('') : `<div class="empty">output 이 없는 응답입니다. JSON 원문을 확인하세요.</div>`;
    }
    $('resultSec').innerHTML = `<h3>응답</h3>${status}${tabs}<div class="x-view">${body}</div>`;
    $('resultSec').querySelectorAll('.x-tabs button[data-v]').forEach((b) => b.addEventListener('click', () => { view = b.dataset.v; renderResult(); }));
    $('copy').addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(JSON.stringify(r.body, null, 2)); $('copy').textContent = '복사됨'; setTimeout(() => { $('copy').textContent = 'JSON 복사'; }, 1500); } catch { /* clipboard 미지원 */ }
    });
  }

  // ── 초기화 ────────────────────────────────────────────────────────────
  $('search').addEventListener('input', (e) => { query = e.target.value.trim().toLowerCase(); renderList(); });
  $('filters').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-f]'); if (!b) return;
    filter = b.dataset.f; $('filters').querySelectorAll('button').forEach((x) => x.classList.toggle('on', x === b)); renderList();
  });
  $('list').addEventListener('click', (e) => {
    const b = e.target.closest('.x-item'); if (!b) return;
    const api = catalog.apis.find((a) => a.id === b.dataset.id); if (api) { renderDetail(api); $('main').scrollIntoView({ block: 'start', behavior: 'smooth' }); }
  });

  document.addEventListener('DOMContentLoaded', async () => {
    user = await initPage();
    try {
      const res = await fetch(`${apiBase}/api/kis-explorer/catalog`, { credentials: 'include' });
      catalog = await res.json();
    } catch (error) {
      $('main').innerHTML = `<div class="danger">카탈로그를 불러오지 못했습니다: ${esc(error.message)}</div>`;
      return;
    }
    renderStats();
    renderList();
    const first = catalog.apis.find((a) => a.id === 'inquire_price') || catalog.apis[0];
    if (first) renderDetail(first);
  });
})();
