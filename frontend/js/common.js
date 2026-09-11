const API_BASE = window.APP_CONFIG?.apiBase ?? '';

// 모든 화면의 JavaScript 오류를 진단 API에 best-effort로 전달한다.
// 폼 값·쿠키·요청 헤더는 전송하지 않으며, 상세 열람은 관리자만 가능하다.
if (!window.__errorReporterInstalled) {
  window.__errorReporterInstalled = true;
  let reportedErrorCount = 0;
  const reportClientError = payload => {
    if (reportedErrorCount >= 20 || location.pathname === '/error-analysis.html') return;
    reportedErrorCount += 1;
    const body = JSON.stringify({ ...payload, url: location.href });
    const url = API_BASE + '/api/error-analysis/client';
    try {
      if (navigator.sendBeacon) navigator.sendBeacon(url, new Blob([body], { type: 'application/json' }));
      else fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body, credentials: 'include', keepalive: true }).catch(() => {});
    } catch (_) {}
  };
  window.addEventListener('error', event => reportClientError({
    type: event.error?.name || 'JavaScriptError',
    message: event.message || `리소스를 불러오지 못했습니다: ${event.target?.src || event.target?.href || 'unknown'}`,
    stack: event.error?.stack || '', line: event.lineno, column: event.colno,
  }), true);
  window.addEventListener('unhandledrejection', event => {
    const reason = event.reason;
    reportClientError({ type: reason?.name || 'UnhandledPromiseRejection', message: reason?.message || String(reason || '처리되지 않은 비동기 오류'), stack: reason?.stack || '' });
  });
}

// 공통 오프캔버스 메뉴에서 사용하는 Font Awesome 아이콘
if (!document.getElementById('fontawesome-css')) {
  const iconStylesheet = document.createElement('link');
  iconStylesheet.id = 'fontawesome-css';
  iconStylesheet.rel = 'stylesheet';
  iconStylesheet.href = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css';
  document.head.appendChild(iconStylesheet);
}

// 일부 기존 화면이 /css/style.css를 장기 캐시하더라도 GNB가 기본 HTML처럼
// 보이지 않도록, 헤더 핵심 규칙은 공통 스크립트와 함께 보장한다.
if (!document.getElementById('gnb-core-style')) {
  const gnbStyle = document.createElement('style');
  gnbStyle.id = 'gnb-core-style';
  gnbStyle.textContent = `
    #site-header{background:rgba(255,255,255,.96);border-bottom:1px solid #dce3ef;box-shadow:0 1px 4px rgba(0,0,0,.06);position:sticky;top:0;z-index:100}
    .gnb-shell{display:flex!important;align-items:center!important;gap:18px;min-height:58px;padding:0 22px}
    .gnb-brand{flex:0 0 auto;color:#0d47a1!important;text-decoration:none!important;font-size:18px!important;font-weight:900!important;white-space:nowrap}.gnb-brand i{margin-right:6px}
    .gnb-nav{display:flex!important;align-items:stretch!important;gap:2px;min-width:0;flex:1;overflow-x:auto;scrollbar-width:thin}
    .gnb-link,.gnb-group summary{display:flex!important;align-items:center!important;gap:6px;height:58px;padding:0 10px;color:#334155!important;text-decoration:none!important;font-size:13px!important;font-weight:750!important;white-space:nowrap;cursor:pointer;list-style:none}
    .gnb-group{position:relative;flex:0 0 auto}.gnb-group summary::-webkit-details-marker{display:none}.gnb-group summary i{font-size:10px}.gnb-link:hover,.gnb-group summary:hover{color:#0d47a1!important;background:#edf3ff}
    .gnb-dropdown{position:absolute;z-index:220;display:grid;min-width:210px;padding:6px;border:1px solid #dce3ef;border-radius:9px;background:#fff;box-shadow:0 10px 25px rgba(0,0,0,.12)}.gnb-dropdown a{display:flex;align-items:center;gap:8px;padding:9px 10px;border-radius:6px;color:#334155!important;text-decoration:none!important;font-size:13px!important;font-weight:650!important;white-space:nowrap}.gnb-dropdown a:hover{background:#edf3ff;color:#0d47a1!important}.gnb-user{flex:0 0 auto;white-space:nowrap}
    .gnb-shortcuts{display:flex;align-items:center;gap:3px;min-width:0;overflow-x:auto}.gnb-shortcuts a{padding:7px 9px;border-radius:6px;color:#1e53e5!important;text-decoration:none!important;font-size:12px!important;font-weight:800!important;white-space:nowrap}.gnb-shortcuts a:hover{background:#e3f0ff}
    .site-header-inner{display:grid!important;grid-template-columns:minmax(220px,1fr) auto minmax(220px,1fr);align-items:center!important;gap:16px;min-height:56px;padding:0 18px}.site-header-left,.site-header-actions{display:flex;align-items:center;gap:12px;min-width:0}.site-header-actions{justify-self:end}.header-menu-label{display:inline}
    #oc-panel .oc-group-toggle,#ai-panel .oc-group-toggle{font-size:14px!important;line-height:1.4!important}#oc-panel .oc-nav-item,#ai-panel .oc-nav-item{font-size:14px!important;line-height:1.4!important}#oc-panel .oc-nav-item--sub,#ai-panel .oc-nav-item--sub{font-size:13px!important}#oc-panel .oc-header,#ai-panel .oc-header{font-size:15px!important}#oc-panel .oc-footer,#ai-panel .oc-footer{font-size:11px!important}
    @media(max-width:760px){.site-header-inner{grid-template-columns:auto minmax(0,1fr) auto;gap:8px;padding:0 10px}.site-header-left,.site-header-actions{gap:6px}.header-menu-label{display:none}.gnb-shortcuts{justify-content:center}.gnb-shortcuts a{padding:6px 5px;font-size:11px!important}.site-header-actions button{padding-inline:7px!important}.site-header-actions span{display:none}}
    @media(max-width:900px){.gnb-shell{gap:10px;padding:0 12px;flex-wrap:wrap;padding-bottom:3px}.gnb-nav{order:3;flex-basis:100%;height:42px}.gnb-link,.gnb-group summary{height:40px;padding:0 8px;font-size:12px!important}.gnb-user span{display:none}.gnb-dropdown{position:fixed;left:12px;right:12px;min-width:0}}
  `;
  document.head.appendChild(gnbStyle);
}

/* ── API fetch wrapper ───────────────────────────────────────────────────── */
async function apiFetch(path, options = {}) {
  return fetch(API_BASE + path, { credentials: 'include', ...options });
}

function upbitWebSocketUrl() {
  const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${scheme}//${location.host}/upbit-websocket`;
}

/* ── Auth ────────────────────────────────────────────────────────────────── */
async function getCurrentUser() {
  try {
    const res = await apiFetch('/api/member/me');
    if (res.ok) return await res.json();
  } catch {}
  return { loggedIn: false };
}

async function logout() {
  await apiFetch('/api/member/logout', { method: 'POST' });
  location.href = '/index.html';
}

/* ── Header render ───────────────────────────────────────────────────────── */
function renderHeader(user) {
  const navGroups = [
    { type: 'single', href: '/index.html', label: '대시보드', icon: 'fa-solid fa-gauge-high' },
    { type: 'group', label: '거래', items: [
      { href: '/trade/order.html', label: '코인',          icon: 'fa-solid fa-coins' },
      { href: '/trade/stock.html', label: '주식',          icon: 'fa-solid fa-chart-line' },
      { href: '/trade/alternatives.html', label: '파생·금속·부동산', icon: 'fa-solid fa-landmark' },
    ]},
    { type: 'group', label: '자산관리', items: [
      { href: '/trade/hold.html',  label: '보유자산',       icon: 'fa-solid fa-wallet' },
      { href: '/trade/history.html', label: '내 거래이력',   icon: 'fa-solid fa-clock-rotate-left' },
      { href: '/trade/avg-down.html', label: '물타기 계산기', icon: 'fa-solid fa-calculator' },
    ]},
    { type: 'group', label: '실전연습', items: [
      { href: '/hts.html', label: 'HTS 시뮬레이션', icon: 'fa-solid fa-desktop' },
      { href: '/learning/tradingview-pine.html', label: 'TradingView(Pine)', icon: 'fa-solid fa-chart-column' },
      { href: '/pine-script-lab.html', label: 'Pine 간단 테스트', icon: 'fa-solid fa-code' },
    ]},
    { type: 'group', label: 'KIS 실전연습', items: [
      { href: '/learning/kis-module-guide.html', label: 'KIS 모듈 실습', icon: 'fa-solid fa-plug-circle-check' },
      { href: '/learning/kis-developers.html', label: 'KIS Developers 학습', icon: 'fa-solid fa-code' },
      { href: '/kis-order-flow-test.html', label: '모의 주문 흐름 테스트', icon: 'fa-solid fa-vial-circle-check' },
      { href: '/broker-api-test.html', label: 'KIS 연결 테스트', icon: 'fa-solid fa-chart-line' },
    ]},
    { type: 'group', label: 'KB증권 실전연습', items: [
      { href: '/learning/kb-securities.html', label: 'KB 모의투자 학습', icon: 'fa-solid fa-clipboard-check' },
      { href: '/kb-api-test.html', label: 'KB 연결 테스트', icon: 'fa-solid fa-plug-circle-check' },
    ]},
    { type: 'group', label: 'Alpaca 실전연습', items: [
      { href: '/learning/alpaca-api.html', label: 'Alpaca Paper 학습', icon: 'fa-solid fa-robot' },
      { href: '/alpaca-test.html', label: 'Paper 연결·조회', icon: 'fa-solid fa-chart-line' },
      { href: '/alpaca-order-flow-test.html', label: 'Paper 주문 흐름 테스트', icon: 'fa-solid fa-vial-circle-check' },
    ]},
    { type: 'group', label: 'Binance 실전연습', items: [
      { href: '/learning/binance-api.html', label: 'Binance Spot API 학습', icon: 'fa-brands fa-bitcoin' },
      { href: '/binance-api-test.html', label: 'Binance 공개 시세 테스트', icon: 'fa-solid fa-chart-line' },
    ]},
    { type: 'group', label: 'Korbit 실전연습', items: [
      { href: '/learning/korbit-api.html', label: 'Korbit Open API 학습', icon: 'fa-solid fa-coins' },
      { href: '/korbit-api-test.html', label: 'Korbit 공개 시세 테스트', icon: 'fa-solid fa-chart-line' },
    ]},
    { type: 'group', label: 'POSTGRESQL QUANT', items: [
      { href: '/quant.html?tab=schema', label: 'DB 스키마', icon: 'fa-solid fa-sitemap' },
      { href: '/quant.html?tab=algorithm', label: '알고리즘', icon: 'fa-solid fa-code-branch' },
      { href: '/quant.html?tab=simulation', label: '시뮬레이션', icon: 'fa-solid fa-flask-vial' },
      { href: '/ohlcv-db.html', label: 'OHLCV DB', icon: 'fa-brands fa-docker' },
    ]},
    { type: 'group', label: '분석 · 도구', items: [
      { href: '/analysis.html', label: '투자 분석 학습', icon: 'fa-solid fa-graduation-cap' },
      { href: '/ai-sheet.html', label: 'AI Sheet',       icon: 'fa-solid fa-table-cells-large' },
      { href: '/openapi.html',  label: 'Open API',       icon: 'fa-solid fa-key' },
      { href: '/api-usage-history.html', label: 'API 사용이력', icon: 'fa-solid fa-list-check' },
      { href: '/error-analysis.html', label: '에러분석', icon: 'fa-solid fa-bug' },
      { href: '/broker-api-test.html', label: '증권사 시세 테스트', icon: 'fa-solid fa-plug-circle-check' },
    ]},
    { type: 'group', label: 'AWS SSM 연동 트랙', items: [
      { href: '/learning/aws-ssm-key-management.html', label: 'AWS 키 관리 가이드', icon: 'fa-solid fa-shield-halved' },
      { href: '/aws-broker-api-test.html', label: '증권사 시세 테스트(AWS SSM)', icon: 'fa-brands fa-aws' },
      { href: '/aws-alpaca-test.html', label: 'Alpaca Test(AWS SSM)', icon: 'fa-brands fa-aws' },
    ]},
  ];

  const userSection = user?.loggedIn
    ? `<div style="display:flex;align-items:center;gap:8px;">
         <span style="font-size:14px;font-weight:700;color:var(--fg);">${user.username}님</span>
         <button onclick="logout()" style="background:rgba(225,29,72,0.06);color:#E11D48;border:1.5px solid rgba(225,29,72,0.2);border-radius:6px;padding:0.3rem 0.9rem;font-size:13px;font-weight:600;cursor:pointer;transition:all .15s;" onmouseover="this.style.background='rgba(225,29,72,0.12)'" onmouseout="this.style.background='rgba(225,29,72,0.06)'">로그아웃</button>
       </div>`
    : `<div style="display:flex;align-items:center;gap:6px;">
         <button onclick="location.href='/member/login.html'" style="background:transparent;color:var(--fg-2);border:1.5px solid var(--border);border-radius:6px;padding:0.3rem 0.9rem;font-size:13px;font-weight:600;cursor:pointer;transition:all .15s;" onmouseover="this.style.background='var(--accent-light)'" onmouseout="this.style.background='transparent'">로그인</button>
         <button onclick="location.href='/member/register.html'" style="background:var(--accent);color:#fff;border:none;border-radius:6px;padding:0.3rem 0.9rem;font-size:13px;font-weight:600;cursor:pointer;transition:opacity .15s;" onmouseover="this.style.opacity='.85'" onmouseout="this.style.opacity='1'">회원가입</button>
       </div>`;

  const isLoggedIn = !!user?.loggedIn;

  const ocNavItem = (n, sub) =>
    `<a href="${n.href}" class="oc-nav-item${sub ? ' oc-nav-item--sub' : ''}"><i class="${n.icon}" aria-hidden="true" style="width:16px;text-align:center;"></i> ${n.label}</a>`;

  // 좌측은 실전연습, 우측은 대시보드·거래·자산·분석·관리 메뉴로 나눈다.
  const rightMenuLabels = new Set(['대시보드', '거래', '자산관리', 'POSTGRESQL QUANT', '분석 · 도구', 'AWS SSM 연동 트랙']);
  const leftNavGroups = navGroups.filter(group => !rightMenuLabels.has(group.label));
  const rightPanelGroups = navGroups.filter(group => rightMenuLabels.has(group.label));
  const practiceItems = navGroups.find(group => group.label === '실전연습')?.items || [];

  let ocGroupIdx = -1;
  const ocNavItems = leftNavGroups.map(g => {
    if (g.type === 'single') return ocNavItem(g);
    ocGroupIdx++;
    return `
      <div class="oc-group">
        <button type="button" class="oc-group-toggle" onclick="toggleOcGroup(${ocGroupIdx})" aria-expanded="false">
          <span>${g.label}</span>
          <i class="fa-solid fa-chevron-down oc-group-chevron" aria-hidden="true"></i>
        </button>
        <div class="oc-group-body">
          ${g.items.map(n => ocNavItem(n, true)).join('')}
        </div>
      </div>`;
  }).join('');

  let rightGroupIdx = -1;
  const rightNavItems = rightPanelGroups.map(g => {
    if (g.type === 'single') return ocNavItem(g);
    rightGroupIdx++;
    return `
      <div class="oc-group">
        <button type="button" class="oc-group-toggle" onclick="toggleRightGroup(${rightGroupIdx})" aria-expanded="false">
          <span>${g.label}</span>
          <i class="fa-solid fa-chevron-down oc-group-chevron" aria-hidden="true"></i>
        </button>
        <div class="oc-group-body">
          ${g.items.map(n => ocNavItem(n, true)).join('')}
        </div>
      </div>`;
  }).join('');

  const ocNavAuthed = ocNavItems;

  const ocNavGuest = `
    <div class="oc-group open">
      <button type="button" class="oc-group-toggle" onclick="toggleOcGroup(0)" aria-expanded="true">
        <span>실전연습</span>
        <i class="fa-solid fa-chevron-down oc-group-chevron" aria-hidden="true"></i>
      </button>
      <div class="oc-group-body">
        ${practiceItems.map(item => ocNavItem(item, true)).join('')}
      </div>
    </div>
    <div class="oc-guest-lock">
      <i class="fa-solid fa-lock" aria-hidden="true"></i>
      <p>거래·자산관리·분석 도구는 로그인 후 이용할 수 있습니다.</p>
      <div class="oc-guest-actions">
        <button onclick="closeOffcanvas();location.href='/member/login.html'">로그인</button>
        <button onclick="closeOffcanvas();location.href='/member/register.html'">회원가입</button>
      </div>
    </div>`;

  const html = `
    <!-- 왼쪽 오프캔버스 오버레이 -->
    <div id="oc-overlay" onclick="closeOffcanvas()"></div>

    <!-- 왼쪽 오프캔버스 — 네비게이션 메뉴 -->
    <aside id="oc-panel">
      <div class="oc-header">
        <span class="brand-logo-text" style="font-size:17px;letter-spacing:1.5px;"><i class="fa-solid fa-chart-pie" aria-hidden="true" style="margin-right:6px;"></i>모의투자</span>
        <button class="oc-close-btn" onclick="closeOffcanvas()">✕</button>
      </div>
      <nav class="oc-nav" aria-label="실전연습 메뉴">
        ${isLoggedIn ? ocNavAuthed : ocNavGuest}
      </nav>
      <div class="oc-footer" style="font-size:11px;color:var(--muted);">
        <div>(주)에듀엠지티</div>
        <a href="https://www.edumgt.co.kr" target="_blank" style="color:var(--accent-dark);text-decoration:none;font-weight:600;">www.edumgt.co.kr</a>
      </div>
    </aside>

    <!-- 기존 오프캔버스를 유지하고, AI 3개 기능만 상단 GNB 바로가기로 제공한다. -->
    <header id="site-header">
      <div class="site-header-inner">
        <div class="site-header-left">
          <button onclick="openOffcanvas()" aria-label="메뉴 열기" style="display:flex;align-items:center;gap:6px;background:transparent;border:none;cursor:pointer;padding:4px 6px;border-radius:6px;transition:background .12s;color:var(--fg-2);font-size:14px;font-weight:600;"><i class="fa-solid fa-bars" aria-hidden="true"></i><span class="header-menu-label">메뉴</span></button>
          <a href="/index.html" style="text-decoration:none;display:flex;align-items:center;"><span class="brand-logo-text"><i class="fa-solid fa-chart-pie" aria-hidden="true" style="margin-right:6px;"></i>모의투자</span></a>
        </div>
        <nav class="gnb-shortcuts" aria-label="AI 기능 바로가기"><a href="/ai-analysis.html"><i class="fa-solid fa-robot" aria-hidden="true"></i> AI 분석</a><a href="/knowledge-search.html"><i class="fa-solid fa-magnifying-glass" aria-hidden="true"></i> 지식 검색</a><a href="/knowledge-dataset.html"><i class="fa-solid fa-book-open" aria-hidden="true"></i> 데이터셋</a></nav>
        <div class="site-header-actions"><button onclick="openAiPanel()" aria-label="분석 도구 메뉴 열기" style="border:1px solid var(--border);border-radius:6px;background:#fff;color:var(--accent-dark);padding:6px 9px;font-size:12px;font-weight:800;cursor:pointer;white-space:nowrap;"><i class="fa-solid fa-toolbox" aria-hidden="true"></i> 도구 메뉴</button>${userSection}</div>
      </div>
    </header>

    <!-- 오른쪽 오프캔버스 오버레이 -->
    <div id="ai-overlay" onclick="closeAiPanel()" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.35);z-index:399;backdrop-filter:blur(3px);"></div>

    <!-- 오른쪽 오프캔버스 — 대시보드·분석·연동 메뉴 -->
    <aside id="ai-panel" style="position:fixed;top:0;right:0;height:100vh;width:460px;max-width:94vw;background:#FFFFFF;border-left:1px solid var(--border);box-shadow:-4px 0 24px rgba(0,0,0,0.08);z-index:400;transform:translateX(100%);transition:transform 0.28s cubic-bezier(0.4,0,0.2,1);display:flex;flex-direction:column;">

      <!-- 패널 헤더 -->
      <div style="display:flex;align-items:center;justify-content:space-between;padding:.85rem 1.1rem;border-bottom:1px solid var(--border);flex-shrink:0;">
        <div style="display:flex;align-items:center;gap:8px;">
          <i class="fa-solid fa-toolbox" aria-hidden="true" style="font-size:16px;color:var(--accent);"></i>
          <span style="font-size:15px;font-weight:800;color:var(--fg);">빠른 메뉴</span>
        </div>
        <button onclick="closeAiPanel()" style="background:var(--surface-2);border:1px solid var(--border);border-radius:6px;padding:3px 10px;font-size:12px;color:var(--muted);cursor:pointer;">✕</button>
      </div>

      <nav class="oc-nav right-tool-nav" aria-label="대시보드 및 분석·연동 메뉴">
        ${rightNavItems}
      </nav>


    </aside>`;

  const mount = document.getElementById('header-mount');
  if (mount) mount.innerHTML = html;
}

/* ── Offcanvas ───────────────────────────────────────────────────────────── */
function openOffcanvas() {
  document.getElementById('oc-overlay')?.classList.add('open');
  document.getElementById('oc-panel')?.classList.add('open');
  document.body.style.overflow = 'hidden';
}
function closeOffcanvas() {
  document.getElementById('oc-overlay')?.classList.remove('open');
  document.getElementById('oc-panel')?.classList.remove('open');
  document.body.style.overflow = '';
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeOffcanvas(); closeAiPanel(); } });

function toggleOcGroup(idx) {
  document.querySelectorAll('#oc-panel .oc-group').forEach((el, i) => {
    const open = i === idx ? !el.classList.contains('open') : false;
    el.classList.toggle('open', open);
    el.querySelector('.oc-group-toggle')?.setAttribute('aria-expanded', String(open));
  });
}

function toggleRightGroup(idx) {
  const groups = document.querySelectorAll('#ai-panel .oc-nav .oc-group');
  groups.forEach((el, i) => {
    const open = i === idx ? !el.classList.contains('open') : false;
    el.classList.toggle('open', open);
    el.querySelector('.oc-group-toggle')?.setAttribute('aria-expanded', String(open));
  });
}

/* ── 우측 도구 메뉴 ─────────────────────────────────────────────────────── */
function openAiPanel() {
  const panel   = document.getElementById('ai-panel');
  const overlay = document.getElementById('ai-overlay');
  if (panel)   { panel.style.transform   = 'translateX(0)'; }
  if (overlay) { overlay.style.display   = 'block'; }
}
function closeAiPanel() {
  const panel   = document.getElementById('ai-panel');
  const overlay = document.getElementById('ai-overlay');
  if (panel)   { panel.style.transform   = 'translateX(100%)'; }
  if (overlay) { overlay.style.display   = 'none'; }
}

/* 지식 데이터셋의 작성 폼은 목록 화면과 분리한 모달에서 제공한다. */
function mountDatasetComposerModal() {
  const title = [...document.querySelectorAll('h2')].find(el => el.textContent.trim() === '새 지식 추가');
  if (!title || document.getElementById('dataset-composer-modal')) return;

  const card = title.closest('article');
  if (!card) return;
  const trigger = document.createElement('button');
  trigger.type = 'button';
  trigger.className = 'dataset-composer-open';
  trigger.innerHTML = '<i class="fa-solid fa-plus" aria-hidden="true"></i> 새 지식 추가';
  const modal = document.createElement('div');
  modal.id = 'dataset-composer-modal';
  modal.className = 'dataset-composer-modal';
  modal.innerHTML = '<section class="dataset-composer-dialog" role="dialog" aria-modal="true" aria-labelledby="dataset-composer-title"><header><h2 id="dataset-composer-title">새 지식 추가</h2><button type="button" class="dataset-composer-close" aria-label="팝업 닫기">×</button></header><div class="dataset-composer-body"></div></section>';
  const body = modal.querySelector('.dataset-composer-body');

  const divider = title.previousElementSibling;
  if (divider?.tagName === 'HR') divider.remove();
  let node = title.nextElementSibling;
  title.remove();
  while (node) {
    const next = node.nextElementSibling;
    body.appendChild(node);
    if (node.id === 'add-doc-msg') break;
    node = next;
  }
  card.appendChild(trigger);
  document.body.appendChild(modal);
  const close = () => modal.classList.remove('open');
  trigger.addEventListener('click', () => modal.classList.add('open'));
  modal.querySelector('.dataset-composer-close').addEventListener('click', close);
  modal.addEventListener('click', event => { if (event.target === modal) close(); });
  document.addEventListener('keydown', event => { if (event.key === 'Escape') close(); });
}

function collectMarketContext(type) {
  const rows = [];
  const manualContext = document.getElementById('marketContextInput')?.value?.trim();
  if (manualContext) rows.push(`사용자 입력 시장 맥락: ${manualContext}`);
  if (type === 'crypto' || type === 'general') {
    document.querySelectorAll('[id$="-trade_price"]').forEach(el => {
      const code  = el.id.replace('-trade_price', '');
      const price = el.textContent.trim();
      const rate  = document.getElementById(code + '-signed_change_rate')?.textContent?.trim() ?? '';
      if (price && price !== '-') rows.push(`${code}: ${price} (${rate})`);
    });
  }
  if (type === 'stock' || type === 'general') {
    const qp = document.getElementById('quotePrice')?.textContent?.trim();
    const sym = document.getElementById('stockSymbol')?.options[document.getElementById('stockSymbol')?.selectedIndex]?.text ?? '';
    const kospi = document.getElementById('kospiPrice')?.textContent?.trim();
    const kosdaq = document.getElementById('kosdaqPrice')?.textContent?.trim();
    if (qp) rows.push(`선택 종목: ${sym} ${qp}`);
    if (kospi)  rows.push(`KOSPI: ${kospi}`);
    if (kosdaq) rows.push(`KOSDAQ: ${kosdaq}`);
  }
  return rows.length ? rows.join('\n') : '시세 데이터를 수집할 수 없습니다.';
}

/* ── Qdrant RAG 근거 접기/펼치기 ─────────────────────────────────────────── */
function toggleRagBlock() {
  const list = document.getElementById('rag-context-list');
  const icon = document.getElementById('rag-chevron');
  if (!list) return;
  const isOpen = list.style.display !== 'none';
  list.style.display = isOpen ? 'none' : 'block';
  if (icon) icon.style.transform = isOpen ? 'rotate(0deg)' : 'rotate(180deg)';
}

/* ── AI 분석 (RAG + Claude streaming) ───────────────────────────────────── */
async function runAiAnalysis() {
  const btn      = document.getElementById('aiRunBtn');
  const box      = document.getElementById('aiContent');
  const ragBlock = document.getElementById('ai-rag-block');
  const type     = document.getElementById('aiContextSelect')?.value ?? 'general';
  const ragLimit = parseInt(document.getElementById('aiRagLimit')?.value ?? '5', 10);

  btn.disabled    = true;
  btn.textContent = '분석 중...';
  box.innerHTML   = '<div style="text-align:center;padding:2rem 0;color:var(--muted);font-size:13px;">🔍 Qdrant에서 관련 지식을 검색 중...</div>';
  if (ragBlock) ragBlock.style.display = 'none';

  const marketCtx = collectMarketContext(type);

  // ① Qdrant 시맨틱 검색
  let ragDocs = [];
  try {
    const r = await apiFetch('/api/stocks/ai/qdrant/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: marketCtx, limit: ragLimit }),
    });
    if (r.ok) {
      const d = await r.json();
      ragDocs = d.results ?? [];
    }
  } catch (_) {}

  // ② 검색된 근거 UI 표시
  if (ragBlock && ragDocs.length > 0) {
    ragBlock.style.display = 'block';
    const countEl = document.getElementById('rag-hit-count');
    if (countEl) countEl.textContent = ragDocs.length;
    const listEl = document.getElementById('rag-context-list');
    if (listEl) {
      listEl.innerHTML = ragDocs.map((doc, i) => `
        <div style="border-left:3px solid #6366F1;padding:.45rem .7rem;margin-bottom:.5rem;background:white;border-radius:0 6px 6px 0;">
          <div style="display:flex;align-items:center;gap:6px;margin-bottom:.2rem;">
            <span style="font-size:10px;font-weight:700;background:#EEF2FF;color:#4F46E5;padding:1px 6px;border-radius:99px;">${_catLabel(doc.category)}</span>
            <span style="font-size:11px;font-weight:700;color:#1F2937;">${doc.title}</span>
            <span style="font-size:10px;color:#9CA3AF;margin-left:auto;">유사도 ${(doc.score * 100).toFixed(0)}%</span>
          </div>
          <p style="font-size:11px;color:#6B7280;margin:0;line-height:1.5;">${doc.text.substring(0,120)}...</p>
        </div>`).join('');
    }
  }

  // ③ RAG 컨텍스트를 결합한 Claude 프롬프트 구성
  let augmented = marketCtx;
  if (ragDocs.length > 0) {
    const ragSection = ragDocs.map(d => `[${d.title}] ${d.text}`).join('\n');
    augmented = `${marketCtx}\n\n📚 Qdrant 지식 베이스에서 검색된 관련 지식:\n${ragSection}`;
  }

  box.innerHTML = '<div style="text-align:center;padding:1rem 0;color:var(--muted);font-size:13px;">✨ Claude AI가 분석 중입니다...</div>';

  // ④ Claude API (streaming)
  try {
    const res = await apiFetch('/api/ai/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ context: augmented, type }),
    });
    if (!res.ok) throw new Error('분석 서비스 오류');

    const reader  = res.body?.getReader();
    const decoder = new TextDecoder();
    box.innerHTML = '';
    if (reader) {
      let text = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        text += decoder.decode(value, { stream: true });
        box.innerHTML = markdownToHtml(text);
        box.scrollTop = box.scrollHeight;
      }
    } else {
      const data = await res.json();
      box.innerHTML = markdownToHtml(data.analysis ?? '분석 결과가 없습니다.');
    }
  } catch (err) {
    box.innerHTML = `<p style="color:#F87171;font-size:13px;">오류: ${err.message}</p>`;
  } finally {
    btn.disabled    = false;
    btn.textContent = '✨ 다시 분석';
  }
}

/* ── 지식 검색 탭 ────────────────────────────────────────────────────────── */
async function runQdrantSearch() {
  const input = document.getElementById('qdrant-search-input');
  const btn   = document.getElementById('qdrant-search-btn');
  const res   = document.getElementById('qdrant-search-results');
  const query = input?.value?.trim() ?? '';
  if (!query) return;

  if (btn) { btn.disabled = true; btn.textContent = '검색 중...'; }
  if (res) res.innerHTML = '<p style="color:var(--muted);text-align:center;font-size:13px;">검색 중...</p>';

  try {
    const r = await apiFetch('/api/stocks/ai/qdrant/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, limit: 8 }),
    });
    const data = await r.json();
    const hits = data.results ?? [];
    if (!hits.length) {
      res.innerHTML = '<p style="color:var(--muted);text-align:center;font-size:13px;margin-top:2rem;">관련 지식을 찾을 수 없습니다.</p>';
      return;
    }
    res.innerHTML = hits.map(h => `
      <div style="border:1px solid #E0E7FF;border-radius:10px;padding:.8rem .95rem;margin-bottom:.6rem;background:white;box-shadow:0 1px 4px rgba(99,102,241,.06);">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:.4rem;">
          <span style="font-size:10px;font-weight:700;background:#EEF2FF;color:#4F46E5;padding:1px 7px;border-radius:99px;">${_catLabel(h.category)}</span>
          <span style="font-size:12.5px;font-weight:800;color:#1F2937;flex:1;">${h.title}</span>
          <div style="font-size:10px;font-weight:700;color:white;background:${_scoreColor(h.score)};border-radius:99px;padding:1px 7px;">${(h.score*100).toFixed(0)}%</div>
        </div>
        <p style="font-size:12px;color:#4B5563;margin:0;line-height:1.65;">${h.text}</p>
      </div>`).join('');
  } catch (err) {
    if (res) res.innerHTML = `<p style="color:#F87171;font-size:13px;">오류: ${err.message}</p>`;
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '검색'; }
  }
}

/* ── 데이터셋 탭 ─────────────────────────────────────────────────────────── */
async function loadDataset() {
  const statsEl = document.getElementById('qdrant-stats-body');
  const listEl  = document.getElementById('qdrant-doc-list');

  // 통계
  try {
    const r    = await apiFetch('/api/stocks/ai/qdrant/stats');
    const data = await r.json();
    if (statsEl) statsEl.innerHTML = `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:.4rem;">
        <div><span style="color:var(--muted);">컬렉션</span><br><strong style="color:var(--accent-dark);font-size:14px;">${data.collection}</strong></div>
        <div><span style="color:var(--muted);">문서 수</span><br><strong style="color:var(--accent-dark);font-size:14px;">${data.count}개</strong></div>
        <div style="grid-column:1/-1;"><span style="color:var(--muted);">임베딩 모델</span><br><code style="font-size:11px;color:var(--fg-2);">${data.model}</code></div>
      </div>`;
  } catch (e) {
    if (statsEl) statsEl.innerHTML = `<span style="color:#F87171;font-size:12px;">통계 불러오기 실패</span>`;
  }

  // 문서 목록
  try {
    const r    = await apiFetch('/api/stocks/ai/qdrant/list?limit=40');
    const data = await r.json();
    const docs = data.documents ?? [];
    if (listEl) listEl.innerHTML = docs.length
      ? docs.map(d => `
        <div style="display:flex;align-items:baseline;gap:6px;padding:.35rem .5rem;border-radius:6px;margin-bottom:.2rem;background:white;border:1px solid #F3F4F6;">
          <span style="font-size:11px;font-weight:700;background:var(--accent-light);color:var(--accent-dark);padding:2px 6px;border-radius:99px;white-space:nowrap;">${_catLabel(d.category)}</span>
          <span style="font-size:13px;font-weight:600;color:var(--fg);flex:1;">${d.title}</span>
        </div>`).join('')
      : '<p style="color:var(--muted);font-size:12px;text-align:center;">문서가 없습니다.</p>';
  } catch (e) {
    if (listEl) listEl.innerHTML = `<span style="color:#F87171;font-size:12px;">목록 불러오기 실패</span>`;
  }
}

async function addQdrantDoc() {
  const title    = document.getElementById('new-doc-title')?.value?.trim() ?? '';
  const category = document.getElementById('new-doc-category')?.value ?? 'custom';
  const text     = document.getElementById('new-doc-text')?.value?.trim()  ?? '';
  const btn      = document.getElementById('add-doc-btn');
  const msg      = document.getElementById('add-doc-msg');

  if (!text) {
    if (msg) { msg.style.display='block'; msg.style.color='#F87171'; msg.textContent='내용을 입력하세요.'; }
    return;
  }
  if (btn) { btn.disabled = true; btn.textContent = '추가 중...'; }
  if (msg) msg.style.display = 'none';

  try {
    const r = await apiFetch('/api/stocks/ai/qdrant/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: title || '사용자 추가 지식', category, text }),
    });
    const data = await r.json();
    if (r.ok) {
      if (msg) { msg.style.display='block'; msg.style.color='#059669'; msg.textContent=`✓ 추가 완료 (ID: ${data.id?.substring(0,8)}...)`; }
      document.getElementById('new-doc-title').value = '';
      document.getElementById('new-doc-text').value  = '';
      setTimeout(() => loadDataset(), 600);
    } else {
      if (msg) { msg.style.display='block'; msg.style.color='#F87171'; msg.textContent=data.error ?? '추가 실패'; }
    }
  } catch (err) {
    if (msg) { msg.style.display='block'; msg.style.color='#F87171'; msg.textContent='오류: ' + err.message; }
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Qdrant에 추가'; }
  }
}

/* ── 카테고리 레이블 헬퍼 ────────────────────────────────────────────────── */
function _catLabel(cat) {
  return {
    technical_analysis:   '기술분석',
    fundamental_analysis: '기본분석',
    sector_analysis:      '섹터분석',
    market_structure:     '시장구조',
    investment_strategy:  '투자전략',
    risk_management:      '리스크',
    custom:               '사용자',
  }[cat] ?? cat;
}
function _scoreColor(s) {
  if (s >= 0.75) return '#059669';
  if (s >= 0.55) return '#D97706';
  return '#6B7280';
}

/* ── KRX 보도자료 뉴스 ───────────────────────────────────────────────────── */
let _krxNewsLoaded = false;

async function loadKrxNews() {
  const listEl    = document.getElementById('krx-news-list');
  const badgeEl   = document.getElementById('krx-total-badge');
  const refreshBtn= document.getElementById('krx-refresh-btn');

  if (!listEl) return;
  if (refreshBtn) { refreshBtn.disabled = true; refreshBtn.textContent = '↻ 로딩 중...'; }

  try {
    const r    = await apiFetch('/api/stocks/news/krx');
    const data = await r.json();
    const news = data.news ?? [];

    if (badgeEl) badgeEl.textContent = news.length ? `총 ${data.total}건` : '';

    if (!news.length) {
      listEl.innerHTML = '<p style="color:var(--muted);text-align:center;font-size:12px;margin-top:1.5rem;">뉴스가 없습니다.</p>';
      return;
    }

    listEl.innerHTML = news.map(n => {
      const href = n.pdf_url ?? n.page_url ?? '#';
      const dateStr = _krxFmtDate(n.date);
      return `
        <a href="${href}" target="_blank" rel="noopener noreferrer"
          style="display:block;padding:.45rem 1rem;border-bottom:1px solid #E0E7FF;text-decoration:none;transition:background .12s;"
          onmouseover="this.style.background='#EEF2FF'" onmouseout="this.style.background='transparent'">
          <div style="font-size:12px;font-weight:600;color:#1E1B4B;line-height:1.45;margin-bottom:3px;">${n.title}</div>
          <div style="display:flex;align-items:center;gap:6px;">
            <span style="font-size:10px;color:#6366F1;background:#EEF2FF;border-radius:99px;padding:0 5px;">PDF</span>
            <span style="font-size:10.5px;color:#9CA3AF;">${dateStr}</span>
            <span style="font-size:10px;color:#C4B5FD;margin-left:auto;">조회 ${n.view_cnt}</span>
          </div>
        </a>`;
    }).join('');

    _krxNewsLoaded = true;
  } catch (err) {
    listEl.innerHTML = `<p style="color:#F87171;text-align:center;font-size:12px;margin-top:1rem;">오류: ${err.message}</p>`;
  } finally {
    if (refreshBtn) { refreshBtn.disabled = false; refreshBtn.textContent = '↻ 새로고침'; }
  }
}

function _krxFmtDate(d) {
  if (!d) return '';
  // "2026/06/23" → "2026.06.23"
  return String(d).replace(/\//g, '.');
}

function markdownToHtml(md) {
  return md
    .replace(/^### (.+)$/gm, '<h3 style="font-size:14px;font-weight:800;color:#A78BFA;margin:1rem 0 .4rem;">$1</h3>')
    .replace(/^## (.+)$/gm,  '<h2 style="font-size:15px;font-weight:800;color:#818CF8;margin:1.2rem 0 .5rem;">$1</h2>')
    .replace(/^# (.+)$/gm,   '<h1 style="font-size:16px;font-weight:900;color:var(--fg);margin:1.4rem 0 .6rem;">$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong style="color:var(--fg);font-weight:700;">$1</strong>')
    .replace(/\*(.+?)\*/g,     '<em style="color:#C4B5FD;">$1</em>')
    .replace(/^- (.+)$/gm,    '<li style="margin:.25rem 0;padding-left:.5rem;">• $1</li>')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>');
}

/* ── Page init ───────────────────────────────────────────────────────────── */
function ensureSiteFooter() {
  // 화면별로 누락되지 않도록 공통 푸터를 한 번만 생성한다.
  if (document.body.querySelector(':scope > footer')) return;
  const footer = document.createElement('footer');
  footer.id = 'site-footer';
  footer.innerHTML = '<div>EDUMGT · 모의투자 교육 플랫폼 <span aria-hidden="true">·</span> 모든 거래 기능은 학습·테스트 용도입니다.</div>';
  document.body.appendChild(footer);
}

function mountApiTestGuide() {
  if (document.getElementById('api-test-guide')) return;
  const path = location.pathname;
  const guides = {
    '/broker-api-test.html': {
      title: '이 화면의 API 호출과 기대 결과',
      rate: '<strong>공식 한도(이 화면의 KIS Testbed): 분당 60건</strong> — 모의투자는 초당 1건(계좌·App Key 기준)입니다. 접근 토큰 발급도 초당 1건입니다. KB는 API별 고정 분당 한도를 공개하지 않아 아래 KB 호출은 연속 실행하지 말고 포털의 최신 명세를 확인하세요.',
      rows: [
        ['KIS 현재가', 'GET /api/broker-test/kis/quote?symbol=005930', 'symbol: 6자리 KRX 코드', 'ok: true, quote.price·changeRate·volume·tradeTime'],
        ['KIS 일봉', 'GET /api/broker-test/kis/chart?symbol=005930', 'symbol: 6자리 KRX 코드', 'ok: true, chart.data 배열(날짜·OHLC 가격)'],
        ['KIS 호가', 'GET /api/broker-test/kis/orderbook?symbol=005930', 'symbol: 6자리 KRX 코드', 'ok: true, orderbook 매도·매수 10단계'],
        ['KIS 잔고', 'GET /api/broker-test/kis/balance', '서버의 KIS_ACCOUNT_NO', 'ok: true, balance 현금·평가·보유종목 정보'],
        ['KIS 지수', 'GET /api/broker-test/kis/index?code=0001', '0001(코스피) 또는 1001(코스닥)', 'ok: true, index 현재 지수·등락 정보'],
        ['KB 토큰', 'GET /api/broker-test/kb/token', '서버의 kb.key 또는 환경변수', 'ok: true, check.tokenType·expiresIn'],
        ['KB 현재가', 'GET /api/broker-test/kb/quote?symbol=005930', 'symbol: 6자리 KRX 코드', 'ok: true, quote.price·changeRate·volume'],
        ['KB 추가 조회', 'GET /api/broker-test/kb/{base-info|orderbook|chart}?symbol=005930', 'symbol: 6자리 KRX 코드', 'ok: true, result 객체(기본정보·호가·일봉)'],
      ],
    },
    '/kb-api-test.html': {
      title: '이 화면의 API 호출과 기대 결과',
      rate: '<strong>KB증권: 고정 분당 호출 한도 미공개</strong> — 공식 포털은 API·운영 정책별 호출 제한이 적용된다고 안내합니다. 따라서 이 화면에서는 버튼을 연속 클릭하지 말고, 429 또는 제한 오류가 나면 잠시 기다린 뒤 재시도하세요.',
      rows: [
        ['Access Token', 'GET /api/broker-test/kb/token', '서버의 kb.key 또는 환경변수', 'ok: true, check.tokenType·expiresIn. 토큰 원문은 표시하지 않음'],
        ['현재가 (IVU10140)', 'GET /api/broker-test/kb/quote?symbol=005930', 'symbol: 6자리 KRX 코드', 'ok: true, quote.price·changeRate·volume'],
        ['종목 기본정보', 'GET /api/broker-test/kb/base-info?symbol=005930', 'symbol: 6자리 KRX 코드', 'ok: true, result 내 종목명·시장·상장 정보'],
        ['호가', 'GET /api/broker-test/kb/orderbook?symbol=005930', 'symbol: 6자리 KRX 코드', 'ok: true, result 내 매수·매도 호가 정보'],
        ['통합차트', 'GET /api/broker-test/kb/chart?symbol=005930', 'symbol: 6자리 KRX 코드', 'ok: true, result 내 일자별 가격 정보'],
      ],
    },
    '/kis-order-flow-test.html': {
      title: '이 화면의 API 호출과 기대 결과',
      rate: '<strong>KIS Testbed: 분당 60건</strong> — 모의투자 REST 기준 초당 1건입니다. 이 화면은 한 번 클릭에 주문·정정·취소를 순차 실행하므로 중복 클릭하지 마세요.',
      rows: [
        ['모의 주문 흐름', 'POST /api/broker-test/kis/order-flow-test', '로그인 세션 + 확인 체크 + 서버의 Testbed 계좌', 'ok: true, test.environment·symbol·currentPrice·testPrice·amendedPrice. 서버가 모의 주문→정정→취소까지 완료'],
      ],
      note: '이 호출만 상태를 변경합니다. 200,000원 지정가 1주 주문 후 199,500원으로 정정하고 취소합니다. 현재가가 220,000원을 넘으면 안전장치가 실행을 중단합니다.',
    },
    '/alpaca-test.html': {
      title: '이 화면의 API 호출과 기대 결과',
      rate: '<strong>Alpaca: 호출 종류·플랜별로 다름</strong> — 이 화면의 시세 데이터는 Basic 플랜 기준 분당 200건(Algo Trader Plus는 분당 10,000건)입니다. Paper 계정·포지션·주문 조회의 고정 분당 수치는 공개되지 않으며, 응답의 <code>X-RateLimit-*</code> 헤더를 기준으로 제한을 관리해야 합니다.',
      rows: [
        ['Paper 계정', 'GET /api/alpaca-test/paper/account', '서버의 Paper API Key·Secret', 'ok: true, result.environment=paper, accountStatus·currency, tradingBlocked=false 확인'],
        ['포지션', 'GET /api/alpaca-test/paper/positions', '동일 Paper 인증', 'ok: true, result.positions 배열(보유 수량·평가 정보)'],
        ['최근 주문', 'GET /api/alpaca-test/paper/orders', '동일 Paper 인증', 'ok: true, result.orders 배열(주문 상태·수량). 조회만 수행'],
        ['시장 시계', 'GET /api/alpaca-test/market/clock', 'Paper 인증', 'ok: true, result.isOpen·nextOpen·nextClose'],
        ['최근 호가·체결', 'GET /api/alpaca-test/market/quote?symbol=AAPL', 'symbol: 영문 1~5자리 티커', 'ok: true, result 내 bid·ask·last trade 등 시세 정보'],
      ],
    },
    '/alpaca-order-flow-test.html': {
      title: '이 화면의 API 호출과 기대 결과',
      rate: '<strong>Alpaca Paper 주문: 고정 분당 수치 미공개</strong> — 응답의 <code>X-RateLimit-Limit</code>·<code>Remaining</code>·<code>Reset</code> 헤더를 따릅니다. 이 화면은 안전을 위해 사용자가 한 번씩만 실행하도록 구성했습니다.',
      rows: [
        ['Paper 주문·취소', 'POST /api/alpaca-test/paper/order-flow-test', '로그인 세션 + 확인 체크 + Paper 인증', 'ok: true, result.environment=paper·symbol=AAPL·askPrice·testLimitPrice·quantity·order·cancel'],
      ],
      note: '상태 변경 테스트입니다. 서버는 매도호가가 $2를 초과할 때만 $1.00의 1주 지정가 주문을 만들고 즉시 취소합니다. Live 계정·Live URL은 사용하지 않습니다.',
    },
    '/binance-api-test.html': {
      title: '이 화면의 API 호출과 기대 결과',
      rate: '<strong>Binance Spot 공개 API: IP당 분당 6,000 request weight</strong> — “6,000회”가 아니라 엔드포인트별 가중치 합계입니다. 현재 사용량은 <code>X-MBX-USED-WEIGHT-1M</code> 응답 헤더에서 확인하며, 429가 나오면 <code>Retry-After</code>만큼 기다립니다.',
      rows: [
        ['24시간 시세', 'GET /api/crypto-exchange-test/binance/ticker?symbol=BTCUSDT', 'symbol: BTCUSDT 형식, 6~20자리 영문·숫자', 'ok: true, result 내 lastPrice·priceChangePercent·volume 등'],
        ['호가 10단계', 'GET /api/crypto-exchange-test/binance/orderbook?symbol=BTCUSDT', '동일 symbol', 'ok: true, result 내 bids·asks 배열 각 최대 10단계'],
      ],
      note: '서버가 Binance Spot의 공개 시세 API를 중계합니다. API Key·서명·주문·잔고·출금 호출은 없습니다.',
    },
    '/korbit-api-test.html': {
      title: '이 화면의 API 호출과 기대 결과',
      rate: '<strong>Korbit 공개 API: IP당 초당 50건 = 분당 최대 3,000건</strong> — 이 화면의 시세·호가 호출 모두 공개 API입니다. 실제 남은 양은 <code>Ratelimit</code> 헤더의 <code>remaining</code>과 <code>reset</code>으로 확인합니다.',
      rows: [
        ['24시간 시세', 'GET /api/crypto-exchange-test/korbit/ticker?symbol=btc_krw', 'symbol: btc_krw 형식(코인_krw)', 'ok: true, result 내 last·high·low·volume 등'],
        ['호가 10단계', 'GET /api/crypto-exchange-test/korbit/orderbook?symbol=btc_krw', '동일 symbol', 'ok: true, result 내 bids·asks 배열 각 최대 10단계'],
      ],
      note: '서버가 Korbit 공개 API를 중계합니다. 키 없이 동작하며 주문·잔고·입출금 API는 호출하지 않습니다.',
    },
    '/aws-broker-api-test.html': {
      title: 'AWS SSM 트랙: API 호출과 기대 결과',
      rate: '<strong>KIS Testbed: 분당 60건</strong> — SSM에서 키를 읽은 뒤에도 KIS 모의 REST 한도는 초당 1건입니다. <strong>KB: 고정 분당 한도 미공개</strong>으로 API별 최신 명세와 제한 응답을 따릅니다. SSM 상태 점검 자체는 AWS 계정의 SSM API 한도를 사용합니다.',
      rows: [
        ['SSM 준비 상태', 'GET /api/aws-broker-test/ssm/status', 'AWS_REGION, IAM GetParameters 권한, 7개 파라미터', 'ok: true, status 내 파라미터 존재 여부·타입. SecureString 값은 복호화·반환하지 않음'],
        ['KIS 현재가', 'GET /api/aws-broker-test/kis/quote?symbol=005930', 'SSM kis/app_key·secret + 6자리 symbol', 'ok: true, quote.price·changeRate·volume·tradeTime'],
        ['KIS 잔고', 'GET /api/aws-broker-test/kis/balance', 'SSM kis/account 포함 3개 파라미터', 'ok: true, balance 현금·평가·보유종목 정보'],
        ['KB 토큰', 'GET /api/aws-broker-test/kb/token', 'SSM kb/app_key·secret', 'ok: true, check.tokenType·expiresIn. 토큰 원문 미표시'],
        ['KB 현재가', 'GET /api/aws-broker-test/kb/quote?symbol=005930', 'SSM KB 키 + 6자리 symbol', 'ok: true, quote.price·changeRate·volume'],
      ],
      note: '모든 브로커 요청 전에 서버가 SSM SecureString을 읽습니다. 주문·정정·취소는 호출하지 않습니다.',
    },
    '/aws-alpaca-test.html': {
      title: 'AWS SSM 트랙: API 호출과 기대 결과',
      rate: '<strong>Alpaca 시세 데이터: Basic 플랜 분당 200건</strong> (Algo Trader Plus 분당 10,000건)입니다. 계정·포지션·종목 정보 API의 고정 분당 수치는 공개되지 않으므로 <code>X-RateLimit-*</code> 응답 헤더를 기준으로 관리하세요.',
      rows: [
        ['Paper 계정', 'GET /api/aws-alpaca-test/paper/account', 'SSM alpaca/api_key·secret_key', 'ok: true, result.environment=paper·accountStatus·tradingBlocked'],
        ['포지션', 'GET /api/aws-alpaca-test/paper/positions', '동일 SSM 인증값', 'ok: true, result.positions 배열'],
        ['시장 시계', 'GET /api/aws-alpaca-test/paper/clock', '동일 SSM 인증값', 'ok: true, result.isOpen·nextOpen·nextClose'],
        ['종목 정보', 'GET /api/aws-alpaca-test/paper/asset?symbol=AAPL', 'symbol: 영문 1~10자리', 'ok: true, result 내 tradable·fractionable·status 등'],
      ],
      note: '브라우저는 AWS 자격증명과 SecureString 원문을 받지 않습니다. Paper 주문·취소·포지션 변경은 호출하지 않습니다.',
    },
  };
  const guide = guides[path];
  if (!guide) return;
  const host = document.querySelector('main > section') || document.querySelector('main');
  if (!host) return;
  const rows = guide.rows.map(([name, endpoint, input, expected]) => `<tr><th>${name}</th><td><code>${endpoint}</code></td><td>${input}</td><td>${expected}</td></tr>`).join('');
  const element = document.createElement('details');
  element.id = 'api-test-guide';
  element.className = 'api-test-guide';
  element.open = true;
  element.innerHTML = `<summary>${guide.title}<span>호출 경로 · 입력값 · 성공 기준 보기</span></summary><p class="api-test-guide-rate">${guide.rate}</p><div class="api-test-guide-scroll"><table><thead><tr><th>테스트</th><th>이 웹앱 서버 호출</th><th>필요한 값</th><th>성공 시 확인할 값</th></tr></thead><tbody>${rows}</tbody></table></div>${guide.note ? `<p class="api-test-guide-note">${guide.note}</p>` : ''}<p class="api-test-guide-note">공통 성공 형식은 <code>ok: true</code>입니다. <code>ok: false</code> 또는 HTTP 4xx/5xx이면 결과창의 <code>message</code>를 확인하세요. Key·Secret·Access Token·계좌번호는 응답에 표시하지 않습니다.</p>`;
  host.appendChild(element);
}

async function initPage({ requireAuth = false } = {}) {
  const user = await getCurrentUser();
  if (requireAuth && !user?.loggedIn) {
    location.href = '/member/login.html';
    return null;
  }
  renderHeader(user);
  mountDatasetComposerModal();
  mountApiTestGuide();
  ensureSiteFooter();
  const hasMain = document.body.querySelector(':scope > main');
  const hasFooter = document.body.querySelector(':scope > footer');
  if (hasMain && hasFooter && !document.body.classList.contains('alternatives-layout')) {
    document.body.classList.add('app-shell-layout');
  }
  return user;
}
