const API_BASE = window.APP_CONFIG?.apiBase ?? '';

// 모든 화면의 JavaScript 오류를 진단 API에 best-effort로 전달한다.
// 폼 값·쿠키·요청 헤더는 전송하지 않으며, 상세 열람은 관리자만 가능하다.
// 주소의 쿼리·프래그먼트(메일 링크 토큰 등)는 보내지 않고 경로만 보낸다.
if (!window.__errorReporterInstalled) {
  window.__errorReporterInstalled = true;
  let reportedErrorCount = 0;
  const reportClientError = payload => {
    if (reportedErrorCount >= 20 || location.pathname === '/error-analysis.html') return;
    reportedErrorCount += 1;
    const body = JSON.stringify({ ...payload, url: location.origin + location.pathname });
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

// 공통 오프캔버스 메뉴에서 사용하는 Font Awesome 아이콘.
// 계정 화면(/member/)은 외부 자원을 불러오지 않는다(처리방침 5절, CSP). 아이콘만 빠지고 글자는 남는다.
if (!location.pathname.startsWith('/member/') && !document.getElementById('fontawesome-css')) {
  const iconStylesheet = document.createElement('link');
  iconStylesheet.id = 'fontawesome-css';
  iconStylesheet.rel = 'stylesheet';
  iconStylesheet.href = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css';
  document.head.appendChild(iconStylesheet);
}

// 일부 기존 화면이 /css/style.css를 장기 캐시하더라도 터미널 헤더가 기본
// HTML처럼 보이지 않도록, 헤더 골격 규칙은 공통 스크립트와 함께 보장한다.
if (!document.getElementById('gnb-core-style')) {
  const gnbStyle = document.createElement('style');
  gnbStyle.id = 'gnb-core-style';
  gnbStyle.textContent = `
    #site-header{position:sticky;top:0;z-index:100;background:#000;border-bottom:1px solid #3A4150;color:#E8E6E3}
    .term-cmdbar{display:flex;align-items:center;gap:8px;min-height:34px;padding:0 8px}
    .term-fkeys{display:flex;align-items:stretch;gap:1px;min-height:26px;padding:0 8px;overflow-x:auto;background:#0B0D11;border-top:1px solid #262B35}
    .term-fkey{display:inline-flex;align-items:center;gap:6px;padding:0 10px;color:#C9CDD4;text-decoration:none;white-space:nowrap}
    .term-tape{position:relative;overflow:hidden;height:24px;background:#050608;border-top:1px solid #262B35}
    #oc-panel,#ai-panel{background:#0B0D11;color:#E8E6E3}
    html:not([data-profile="local"]) [data-local-only]{display:none!important}
  `;
  document.head.appendChild(gnbStyle);
}

// AG Grid 기본 테마를 공식 dark 모드로 전환한다(themeQuartz의 colorSchemeVariable).
document.documentElement.dataset.agThemeMode = 'dark';

// 색각이상 대응 팔레트 선택은 브라우저별 편의 설정이다.
try { if (localStorage.getItem('term.cvd') === '1') document.documentElement.dataset.cvd = '1'; } catch (_) {}

/* ── Terminal theme helpers ─────────────────────────────────────────────── */
function termColors() {
  const css = getComputedStyle(document.documentElement);
  const read = (name, fallback) => css.getPropertyValue(name).trim() || fallback;
  return {
    bg: read('--bg', '#000000'),
    surface: read('--surface', '#0B0D11'),
    surface2: read('--surface-2', '#12151B'),
    border: read('--border', '#262B35'),
    borderStrong: read('--border-strong', '#3A4150'),
    fg: read('--fg', '#E8E6E3'),
    fg2: read('--fg-2', '#C9CDD4'),
    muted: read('--muted', '#8B919C'),
    accent: read('--accent', '#FF9F1A'),
    info: read('--info', '#4FC3F7'),
    up: read('--up', '#00D26A'),
    down: read('--down', '#FF4D4D'),
    flat: read('--flat', '#9AA0A6'),
    mono: read('--font-mono', 'monospace'),
  };
}

// 등락 값의 부호로 의미 색을 고른다. 인라인 style 문자열에 그대로 넣을 수 있다.
function priceColor(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n === 0) return 'var(--flat)';
  return n > 0 ? 'var(--up)' : 'var(--down)';
}

// lightweight-charts는 CSS 변수를 해석하지 못하므로 계산된 값을 넘긴다.
function termChartOptions(extra = {}) {
  const c = termColors();
  const base = {
    layout: { background: { type: 'solid', color: c.surface }, textColor: c.muted, fontFamily: c.mono, fontSize: 11 },
    grid: { vertLines: { color: '#161A21' }, horzLines: { color: '#161A21' } },
    crosshair: {
      mode: 0,
      vertLine: { color: c.accent, width: 1, style: 2, labelBackgroundColor: c.accent },
      horzLine: { color: c.accent, width: 1, style: 2, labelBackgroundColor: c.accent },
    },
    rightPriceScale: { borderColor: c.borderStrong },
    timeScale: { borderColor: c.borderStrong },
    // 브라우저 로캘과 무관하게 한국식 천 단위 구분으로 가격 축을 표시한다.
    localization: { locale: 'ko-KR', priceFormatter: p => Number(p).toLocaleString('ko-KR', { maximumFractionDigits: Math.abs(p) >= 100 ? 0 : 4 }) },
  };
  const merge = (target, source) => {
    Object.entries(source).forEach(([key, value]) => {
      if (value && typeof value === 'object' && !Array.isArray(value) && target[key] && typeof target[key] === 'object') merge(target[key], value);
      else target[key] = value;
    });
    return target;
  };
  return merge(base, extra);
}

function termCandleColors() {
  const c = termColors();
  return {
    upColor: c.up, downColor: c.down,
    borderUpColor: c.up, borderDownColor: c.down,
    wickUpColor: c.up, wickDownColor: c.down,
  };
}

// 범주형 차트 색(style.css의 --series-1~8과 같은 값). 차트 라이브러리는 CSS 변수를
// 읽지 못하므로 hex로 둔다. 상승·하락과 헷갈리지 않게 초록·빨강 계열은 뺐다.
const TERM_PALETTE = ['#FF9F1A', '#4FC3F7', '#B39DFF', '#5EEAD4', '#FF6FAE', '#FFD60A', '#90A4AE', '#F97316'];
// 이동평균 기간별 선 색. 주식·KIS 차트·Pine 화면이 같은 색을 쓴다.
const TERM_MA_COLORS = { 5: TERM_PALETTE[5], 20: TERM_PALETTE[1], 60: TERM_PALETTE[2], 120: TERM_PALETTE[4] };
// 현금·기타처럼 의미 없는 나머지 몫
const TERM_NEUTRAL = '#5B616C';

// 거래량 막대처럼 투명도가 필요한 곳을 위해 #RRGGBB를 rgba로 바꾼다.
function termAlpha(hex, alpha) {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(hex).trim());
  if (!m) return hex;
  const n = parseInt(m[1], 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
}

/* ── API fetch wrapper ───────────────────────────────────────────────────── */
/* 서버·사용자 값을 innerHTML 템플릿에 넣을 때는 반드시 이 함수를 거친다. */
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/* onclick="fn(${jsArg(value)})"처럼 인라인 핸들러의 인자로 값을 넣을 때 쓴다.
   JSON 문자열 리터럴로 만든 뒤 HTML 속성용으로 이스케이프한다. escapeHtml만 쓰면
   브라우저가 속성값의 &#39;를 '로 되돌린 뒤 JS로 해석하므로 막히지 않는다. */
function jsArg(value) {
  return escapeHtml(JSON.stringify(String(value ?? '')));
}

/* href에 넣을 주소: http·https만 허용하고, 그 밖(javascript: 등)은 '#'으로 바꾼다. */
function safeHttpUrl(value) {
  try {
    const url = new URL(String(value ?? ''), location.href);
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : '#';
  } catch (_) {
    return '#';
  }
}

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
    // 401 등 HTTP 응답이 왔다면 서버에는 연결된 상태다.
    return { loggedIn: false };
  } catch {}
  return { loggedIn: false, __apiReachable: false };
}

async function logout() {
  await apiFetch('/api/member/logout', { method: 'POST' });
  location.href = '/index.html';
}

/* ── Header render ───────────────────────────────────────────────────────── */
function renderHeader(user) {
  const navGroups = [
    { type: 'single', href: '/index.html', label: '대시보드', icon: 'fa-solid fa-gauge-high' },
    { type: 'group', label: 'NOAH 리서치', items: [
      { href: '/quant.html?tab=simulation', label: '퀀트 백테스트·영수증', icon: 'fa-solid fa-receipt' },
      { href: '/research-agent.html', label: 'AI 리서치(초대제)', icon: 'fa-solid fa-robot' },
      { href: '/events.html', label: '공시 레이더(DART)', icon: 'fa-solid fa-bullhorn' },
      { href: '/openapi.html', label: 'Open API·MCP', icon: 'fa-solid fa-plug' },
    ]},
    { type: 'group', label: '거래', items: [
      { href: '/trade/order.html', label: '코인',          icon: 'fa-solid fa-coins' },
      { href: '/arbitrage.html', label: '코인 차익·김프', icon: 'fa-solid fa-scale-unbalanced' },
      { href: '/trade/stock.html', label: '주식',          icon: 'fa-solid fa-chart-line' },
      { href: '/trade/alternatives.html', label: '파생·금속·부동산', icon: 'fa-solid fa-landmark' },
    ]},
    { type: 'group', label: '자산관리', items: [
      { href: '/trade/hold.html',  label: '보유자산',       icon: 'fa-solid fa-wallet' },
      { href: '/trade/history.html', label: '내 거래이력',   icon: 'fa-solid fa-clock-rotate-left' },
      { href: '/trade/avg-down.html', label: '물타기 계산기', icon: 'fa-solid fa-calculator' },
    ]},
    { type: 'group', label: 'KIS 모의투자 실습', items: [
      { href: '/learning/kis-regist.html', label: '1단계 · 가입', icon: 'fa-solid fa-user-plus' },
      { href: '/learning/kis-dev.html', label: '2단계 · 키 발급', icon: 'fa-solid fa-key' },
      { href: '/learning/kis-test.html', label: '3단계 · 테스트', icon: 'fa-solid fa-plug-circle-check' },
      { href: '/broker-api-test.html', label: 'KIS 연결 테스트', icon: 'fa-solid fa-chart-line' },
      { href: '/kis-order-flow-test.html', label: '모의 주문 흐름 테스트', icon: 'fa-solid fa-vial-circle-check' },
      { href: '/kis-real-trading-practice.html', label: 'KIS 실거래 연습', icon: 'fa-solid fa-arrow-right-arrow-left' },
      { href: '/kis-api-explorer.html', label: 'KIS API 탐색기', icon: 'fa-solid fa-compass' },
      { href: '/kis-chart.html', label: 'KIS 종목 차트', icon: 'fa-solid fa-chart-column' },
      { href: '/kis-api-history.html', label: 'KIS API 호출 이력', icon: 'fa-solid fa-table-list' },
    ]},
    { type: 'group', label: 'KB증권 Open API 실습', items: [
      { href: '/learning/kb-securities.html', label: '전체 · 2일차 과정', icon: 'fa-solid fa-book-open' },
      { href: '/learning/kb-signup.html', label: '1단계 · 가입·신청', icon: 'fa-solid fa-user-plus' },
      { href: '/learning/kb-key.html', label: '2단계 · Key 발급', icon: 'fa-solid fa-key' },
      { href: '/learning/kb-install.html', label: '3단계 · 설치', icon: 'fa-solid fa-download' },
      { href: '/learning/kb-setup.html', label: '4단계 · 설정', icon: 'fa-solid fa-gears' },
      { href: '/kb-api-test.html', label: '5단계 · API 테스트', icon: 'fa-solid fa-plug-circle-check' },
      { href: '/kb-chart.html', label: 'KB 종목 캔들 차트', icon: 'fa-solid fa-chart-column' },
      { href: '/kb-api-history.html', label: '6단계 · 호출 이력', icon: 'fa-solid fa-table-list' },
    ]},
    { type: 'group', label: 'Alpaca 실전연습', items: [
      { href: '/learning/alpaca-api.html', label: '전체 · 3일차 과정', icon: 'fa-solid fa-book-open' },
      { href: '/learning/alpaca-signup.html', label: '1단계 · 가입·Paper 계정', icon: 'fa-solid fa-user-plus' },
      { href: '/learning/alpaca-key.html', label: '2단계 · Paper Key 발급', icon: 'fa-solid fa-key' },
      { href: '/learning/alpaca-install.html', label: '3단계 · 설치', icon: 'fa-solid fa-download' },
      { href: '/learning/alpaca-setup.html', label: '4단계 · 설정', icon: 'fa-solid fa-gears' },
      { href: '/alpaca-test.html', label: '5단계 · 연결·조회', icon: 'fa-solid fa-chart-line' },
      { href: '/alpaca-order-flow-test.html', label: '6단계 · Paper 주문 흐름', icon: 'fa-solid fa-vial-circle-check' },
      { href: '/alpaca-api-history.html', label: '7단계 · 호출 이력', icon: 'fa-solid fa-table-list' },
    ]},
    { type: 'group', label: 'Binance 실전연습', items: [
      { href: '/learning/binance-api.html', label: 'Binance Spot API 학습', icon: 'fa-brands fa-bitcoin' },
      { href: '/binance-api-test.html', label: 'Binance 공개 시세 테스트', icon: 'fa-solid fa-chart-line' },
    ]},
    { type: 'group', label: 'Korbit 실전연습', items: [
      { href: '/learning/korbit-api.html', label: 'Korbit Open API 학습', icon: 'fa-solid fa-coins' },
      { href: '/korbit-api-test.html', label: 'Korbit 공개 시세 테스트', icon: 'fa-solid fa-chart-line' },
    ]},
    { type: 'group', label: 'TR 실전연습', items: [
      { href: '/learning/tradingview-pine.html', label: 'TradingView(Pine)', icon: 'fa-solid fa-chart-column' },
      { href: '/pine-script-lab.html', label: 'Pine 간단 테스트', icon: 'fa-solid fa-code' },
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
    ]},
    { type: 'group', label: 'AWS SSM 연동 트랙', items: [
      { href: '/learning/aws-ssm-key-management.html', label: 'AWS 키 관리 가이드', icon: 'fa-solid fa-shield-halved' },
      { href: '/aws-broker-api-test.html', label: '증권사 시세 테스트(AWS SSM)', icon: 'fa-brands fa-aws' },
      { href: '/aws-alpaca-test.html', label: 'Alpaca Test(AWS SSM)', icon: 'fa-brands fa-aws' },
    ]},
  ];

  const userSection = user?.loggedIn
    ? `<div class="term-user">
         <span class="term-user-name"><i class="fa-solid fa-user" aria-hidden="true"></i> ${escapeHtml(user.username)}</span>
         <button type="button" class="term-icon-btn term-btn-danger" data-action="logout">로그아웃</button>
       </div>`
    : `<div class="term-user">
         <button type="button" class="term-icon-btn" data-action="go" data-href="/member/login.html">로그인</button>
         ${user?.signupOpen === false ? '' : '<button type="button" class="term-icon-btn term-btn-primary" data-action="go" data-href="/member/register.html">회원가입</button>'}
       </div>`;

  const isLoggedIn = !!user?.loggedIn;

  const currentPath = location.pathname.replace(/\/$/, '') || '/index.html';
  const ocNavItem = (n, sub) => {
    const targetPath = n.href.split('?')[0].replace(/\/$/, '');
    const active = currentPath === targetPath || (currentPath === '/' && targetPath === '/index.html');
    return `<a href="${n.href}" class="oc-nav-item${sub ? ' oc-nav-item--sub' : ''}${active ? ' active' : ''}"${active ? ' aria-current="page"' : ''}><i class="${n.icon}" aria-hidden="true" style="width:16px;text-align:center;"></i> ${n.label}</a>`;
  };

  // 좌측은 TR·브로커 실전연습, 우측은 대시보드·거래·자산·분석·관리 메뉴로 나눈다.
  const rightMenuLabels = new Set(['대시보드', 'NOAH 리서치', '거래', '자산관리', 'POSTGRESQL QUANT', '분석 · 도구', 'AWS SSM 연동 트랙']);
  const visibleGroups = isPublicProfile(user) ? publicNavGroups(navGroups) : navGroups;
  const leftNavGroups = visibleGroups.filter(group => !rightMenuLabels.has(group.label));
  const rightPanelGroups = visibleGroups.filter(group => rightMenuLabels.has(group.label));
  const practiceItems = navGroups.find(group => group.label === 'TR 실전연습')?.items || [];

  let ocGroupIdx = -1;
  const ocNavItems = leftNavGroups.map(g => {
    if (g.type === 'single') return ocNavItem(g);
    ocGroupIdx++;
    return `
      <div class="oc-group">
        <button type="button" class="oc-group-toggle" data-action="toggle-oc" data-index="${ocGroupIdx}" aria-expanded="false">
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
        <button type="button" class="oc-group-toggle" data-action="toggle-right" data-index="${rightGroupIdx}" aria-expanded="false">
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
      <button type="button" class="oc-group-toggle" data-action="toggle-oc" data-index="0" aria-expanded="true">
        <span>TR 실전연습</span>
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
        <button type="button" data-action="go" data-href="/member/login.html">로그인</button>
        ${user?.signupOpen === false ? '' : '<button type="button" data-action="go" data-href="/member/register.html">회원가입</button>'}
      </div>
    </div>`;

  const html = `
    <!-- 왼쪽 오프캔버스 오버레이 -->
    <div id="oc-overlay" data-action="close-oc"></div>

    <!-- 왼쪽 오프캔버스 — 네비게이션 메뉴 -->
    <aside id="oc-panel">
      <div class="oc-header">
        <span class="brand-logo-text">Noah TD <small style="color:var(--muted);font-size:11px;">· 실전연습</small></span>
        <button type="button" class="oc-close-btn" data-action="close-oc" aria-label="메뉴 닫기">✕</button>
      </div>
      <nav class="oc-nav" aria-label="TR 실전연습 메뉴">
        ${isLoggedIn ? ocNavAuthed : ocNavGuest}
      </nav>
      <div class="oc-footer" style="font-size:11px;color:var(--muted);">
        <div>NOAH TRADING DESK</div>
        <div>모의투자·OpenAPI 실습</div>
      </div>
    </aside>

    <!-- 터미널 헤더: 명령줄 · 기능키 · 티커 테이프 -->
    <header id="site-header">
      <div class="term-cmdbar">
        <button type="button" class="term-icon-btn" data-action="open-oc" aria-label="실전연습 메뉴 열기"><i class="fa-solid fa-bars" aria-hidden="true"></i><span class="term-menu-label">실전연습</span></button>
        <a class="term-brand" href="/index.html" aria-label="Noah Trading Desk 대시보드">NOAH TD <small>TERMINAL</small></a>
        <form class="term-cmd" role="search">
          <span class="term-cmd-prompt" aria-hidden="true">&gt;</span>
          <input name="cmd" id="term-cmd-input" autocomplete="off" spellcheck="false" aria-label="명령 또는 종목 입력" placeholder="명령·종목 입력 (예: 005930, ${terminalIsPublic ? 'DISC' : 'BTC'}, HOLD, HELP) · / 키">
          <button type="submit" class="term-go">GO</button>
          <div class="term-cmd-help" id="term-cmd-help" role="listbox" aria-label="명령 목록"></div>
        </form>
        <div class="term-meta">
          <span class="term-clock" id="term-clock" aria-label="한국 시간">--:--:-- KST</span>
          <span class="term-mode" title="모든 주문은 모의투자입니다.">PAPER</span>
          <button type="button" class="term-icon-btn" data-action="open-ai" aria-label="도구 메뉴 열기"><i class="fa-solid fa-toolbox" aria-hidden="true"></i><span class="term-menu-label">도구</span></button>
          ${userSection}
        </div>
      </div>
      <nav class="term-fkeys" aria-label="기능 화면">
        ${TERMINAL_FKEYS.map(renderFkey).join('')}
        <span class="term-fkeys-sep" aria-hidden="true"></span>
        ${TERMINAL_SHORTCUTS.map(renderFkey).join('')}
      </nav>
      <div class="term-tape" id="term-tape" aria-label="시세 티커">
        <div class="term-tape-track" id="term-tape-track"><span class="term-tape-empty">시세 연결 중…</span></div>
      </div>
    </header>

    <!-- 오른쪽 오프캔버스 오버레이 -->
    <div id="ai-overlay" data-action="close-ai" style="display:none;position:fixed;inset:0;z-index:399;"></div>

    <!-- 오른쪽 오프캔버스 — 대시보드·분석·연동 메뉴 -->
    <aside id="ai-panel" style="position:fixed;top:0;right:0;height:100vh;width:420px;max-width:94vw;z-index:400;transform:translateX(100%);transition:transform 0.2s cubic-bezier(0.4,0,0.2,1);display:flex;flex-direction:column;">
      <div class="term-panel-head">
        <span><i class="fa-solid fa-toolbox" aria-hidden="true"></i> TOOLS · 빠른 메뉴</span>
        <button type="button" class="oc-close-btn" data-action="close-ai" aria-label="도구 메뉴 닫기">✕</button>
      </div>
      <nav class="oc-nav right-tool-nav" aria-label="대시보드 및 분석·연동 메뉴">
        ${rightNavItems}
      </nav>
    </aside>`;

  const mount = document.getElementById('header-mount');
  if (mount) mount.innerHTML = html;
  window.__termNavGroups = navGroups;
  startTerminalClock();
  startTickerTape();
}

/* ── public 프로필 메뉴 ──────────────────────────────────────────────────
   public 배포는 브로커 실습·코인 시세(업비트 약관 확인 전)·대체자산 등 일부 블루프린트를
   등록하지 않는다(python-stock-backend/app.py). 그 화면은 메뉴·기능키·명령에서 뺀다. */
const PUBLIC_HIDDEN_GROUPS = new Set([
  'KIS 모의투자 실습', 'KB증권 Open API 실습', 'Alpaca 실전연습', 'Binance 실전연습', 'Korbit 실전연습', 'AWS SSM 연동 트랙',
]);
const PUBLIC_HIDDEN_HREFS = new Set([
  '/trade/order.html', '/arbitrage.html', '/trade/alternatives.html', '/ohlcv-db.html', '/ai-sheet.html',
  '/ai-analysis.html', '/learning/kis-regist.html',
]);
const _hrefPath = href => String(href ?? '').split('?')[0];

// 프로필을 모르면(/me 실패) 공개 사이트로 다룬다(applyProfileToTerminal·[data-local-only]와 같은 규칙).
function isPublicProfile(user) {
  return user?.profile !== 'local';
}

function publicNavGroups(groups) {
  return groups
    .filter(group => !PUBLIC_HIDDEN_GROUPS.has(group.label))
    .map(group => group.type === 'group'
      ? { ...group, items: group.items.filter(item => !PUBLIC_HIDDEN_HREFS.has(_hrefPath(item.href))) }
      : group)
    .filter(group => group.type !== 'group' || group.items.length);
}

// 기능키·명령 목록을 제자리에서 고친다(다른 코드가 같은 배열을 참조한다).
let terminalIsPublic = false;
/**
 * initPage가 받은 /api/member/me 응답. 명령 바가 동의·Jev 상태를 확인하는 데 쓴다(없으면 null).
 * @type {object|null}
 */
let terminalMe = null;
function applyProfileToTerminal(user) {
  // 프로필을 모르면(/me 실패) 공개 사이트처럼 안전하게 다룬다(코인 명령·경로를 열지 않는다).
  if (user?.profile === 'local') return;
  terminalIsPublic = true;
  // AI가 꺼졌거나 모르면 AI 리서치는 "꺼져 있습니다"만 보이는 막다른 화면이다. 메뉴·기능키·명령·Jev 후보에서 뺀다.
  if (user?.aiEnabled !== true) PUBLIC_HIDDEN_HREFS.add('/research-agent.html');
  const keep = item => !PUBLIC_HIDDEN_HREFS.has(_hrefPath(item.href));
  const ai = TERMINAL_FKEYS.find(f => f.code === 'AI');
  if (ai) { ai.label = 'AI 리서치'; ai.href = '/research-agent.html'; }
  for (const list of [TERMINAL_FKEYS, TERMINAL_COMMANDS]) {
    const kept = list.filter(keep);
    list.splice(0, list.length, ...kept);
  }
}

/* ── Terminal: 기능키 · 명령줄 · 티커 ───────────────────────────────────── */
const TERMINAL_FKEYS = [
  { key: '1', code: 'DASH', label: '대시보드', href: '/index.html' },
  { key: '2', code: 'STK',  label: '주식',     href: '/trade/stock.html' },
  { key: '3', code: 'CRY',  label: '코인',     href: '/trade/order.html' },
  { key: '4', code: 'ALT',  label: '대체자산', href: '/trade/alternatives.html' },
  { key: '5', code: 'HOLD', label: '보유자산', href: '/trade/hold.html' },
  { key: '6', code: 'HIST', label: '거래이력', href: '/trade/history.html' },
  { key: '7', code: 'QNT',  label: '퀀트',     href: '/quant.html' },
  { key: '8', code: 'KIS',  label: 'KIS 실습', href: '/learning/kis-regist.html' },
  { key: '9', code: 'AI',   label: 'AI 분석',  href: '/ai-analysis.html' },
];
const TERMINAL_SHORTCUTS = [
  { code: 'SRCH', label: '지식 검색', href: '/knowledge-search.html', icon: 'fa-magnifying-glass' },
  { code: 'DSET', label: '데이터셋',  href: '/knowledge-dataset.html', icon: 'fa-book-open' },
];

// 명령줄 별칭 → 화면. 기능키와 같은 코드를 쓰고, 학습·도구 화면 코드를 더한다.
const TERMINAL_COMMANDS = [
  ...TERMINAL_FKEYS.map(f => ({ codes: [f.code], label: f.label, href: f.href })),
  { codes: ['MON', 'HOME'], label: '대시보드', href: '/index.html' },
  { codes: ['EQ', 'STOCK'], label: '주식 (예: STK 005930)', href: '/trade/stock.html' },
  { codes: ['COIN', 'CRYPTO'], label: '코인 (예: BTC, KRW-ETH)', href: '/trade/order.html' },
  { codes: ['ARB', 'KIMP'], label: '코인 차익·김프 (예: ARB ETH)', href: '/arbitrage.html', argParam: 'symbol' },
  { codes: ['DISC', 'DART'], label: '공시 레이더 (예: DISC 005930)', href: '/events.html', argParam: 'symbol' },
  { codes: ['PORT', 'PRT'], label: '보유자산', href: '/trade/hold.html' },
  { codes: ['AVG'], label: '물타기 계산기', href: '/trade/avg-down.html' },
  { codes: ['QUANT'], label: '퀀트 랩', href: '/quant.html' },
  { codes: ['RSCH', 'AGENT'], label: 'AI 리서치(영수증 답변)', href: '/research-agent.html' },
  { codes: ['OHLCV'], label: 'OHLCV DB', href: '/ohlcv-db.html' },
  { codes: ['SRCH', 'KNOW'], label: '지식 검색', href: '/knowledge-search.html' },
  { codes: ['DSET'], label: '지식 데이터셋', href: '/knowledge-dataset.html' },
  { codes: ['SHEET'], label: 'AI Sheet', href: '/ai-sheet.html' },
  { codes: ['ANL'], label: '투자 분석 학습', href: '/analysis.html' },
  { codes: ['API', 'OPENAPI'], label: '플랫폼 Open API', href: '/openapi.html' },
  { codes: ['KB'], label: 'KB증권 Open API 실습', href: '/learning/kb-securities.html' },
  { codes: ['ALP', 'ALPACA'], label: 'Alpaca 실전연습', href: '/learning/alpaca-api.html' },
  { codes: ['BNB', 'BINANCE'], label: 'Binance 실전연습', href: '/learning/binance-api.html' },
  { codes: ['KBT', 'KORBIT'], label: 'Korbit 실전연습', href: '/learning/korbit-api.html' },
  { codes: ['PINE', 'TV'], label: 'TradingView Pine', href: '/learning/tradingview-pine.html' },
  { codes: ['USAGE'], label: 'API 사용이력', href: '/api-usage-history.html' },
  { codes: ['ERR'], label: '에러분석', href: '/error-analysis.html' },
  { codes: ['KEYS'], label: '플랫폼 API 키', href: '/member/api-keys.html' },
  { codes: ['LOGIN'], label: '로그인', href: '/member/login.html' },
  // 증권사 HTS 화면번호. 옛 HTS 시뮬레이터 대신 같은 기능이 있는 주식 화면 패널로 연결한다.
  { codes: ['0130'], label: 'HTS 0130 관심종목', href: '/trade/stock.html?focus=watch' },
  { codes: ['0101'], label: 'HTS 0101 주식현재가·호가', href: '/trade/stock.html?focus=book' },
  { codes: ['0400'], label: 'HTS 0400 종합차트', href: '/trade/stock.html?focus=chart' },
  { codes: ['0600', '4990'], label: 'HTS 0600·4990 주식주문', href: '/trade/stock.html?focus=order' },
  { codes: ['0919'], label: 'HTS 0919 기업분석(재무제표 학습)', href: '/analysis.html?lesson=fundamental-financials' },
  { codes: ['RAW', 'BRKR'], label: 'KIS·KB 원본 조회(주식 도크)', href: '/trade/stock.html?dock=broker' },
  { codes: ['MEMO'], label: '종목 메모(주식 도크)', href: '/trade/stock.html?dock=memo' },
  { codes: ['HTS'], label: 'HTS 화면번호 목록(0130·0101·0400·0600·0919)', action: 'hts' },
  { codes: ['CVD'], label: '색각이상 팔레트 전환(상승 파랑)', action: 'cvd' },
  { codes: ['HELP', '?'], label: '명령 목록', action: 'help' },
];

function currentTerminalPath() {
  return location.pathname.replace(/\/$/, '') || '/index.html';
}

function renderFkey(f) {
  const target = f.href.split('?')[0];
  const path = currentTerminalPath();
  const active = path === target || (path === '/' && target === '/index.html');
  const badge = f.key ? `<kbd>${f.key}</kbd>` : `<i class="fa-solid ${f.icon}" aria-hidden="true"></i>`;
  const title = f.key ? ` title="Alt+${f.key}"` : '';
  return `<a class="term-fkey${f.key ? '' : ' term-fkey--ai'}${active ? ' active' : ''}" href="${f.href}"${title}${active ? ' aria-current="page"' : ''}>${badge}${f.code}<span>${f.label}</span></a>`;
}

function terminalScreenCode() {
  const path = currentTerminalPath();
  const hit = [...TERMINAL_FKEYS, ...TERMINAL_SHORTCUTS].find(f => f.href.split('?')[0] === path);
  if (hit) return hit.code;
  const file = path.split('/').pop().replace(/\.html$/, '');
  return (file || 'DASH').toUpperCase().slice(0, 14);
}

function toggleCvdPalette() {
  const root = document.documentElement;
  const on = !root.dataset.cvd;
  if (on) root.dataset.cvd = '1'; else delete root.dataset.cvd;
  try { localStorage.setItem('term.cvd', on ? '1' : '0'); } catch (_) {}
  document.dispatchEvent(new CustomEvent('term:palette'));
  return on;
}

function renderTerminalHelp(filter = '') {
  const box = document.getElementById('term-cmd-help');
  if (!box) return;
  const q = filter.trim().toUpperCase();
  const rows = TERMINAL_COMMANDS.filter(c => !q || c.codes.some(code => code.startsWith(q)) || c.label.toUpperCase().includes(q));
  box.innerHTML = rows.length
    ? rows.map(c => `<div data-cmd="${c.codes[0]}"><b>${c.codes.join(' · ')}</b><span>${c.label}</span></div>`).join('')
    : '<div><b>—</b><span>일치하는 명령이 없습니다. 6자리 종목코드' + (terminalIsPublic ? '' : '나 코인 심볼') + '도 입력할 수 있습니다.</span></div>';
  box.classList.add('open');
}

function closeTerminalHelp() {
  document.getElementById('term-cmd-help')?.classList.remove('open');
}

// Bloomberg의 "<코드> <GO>"처럼 짧은 명령으로 화면을 이동한다.
function runTerminalCommand(raw) {
  const text = String(raw || '').trim();
  if (!text) { renderTerminalHelp(); return; }
  const tokens = text.toUpperCase().split(/\s+/);
  const first = tokens[0];
  const command = TERMINAL_COMMANDS.find(c => c.codes.includes(first));
  // 인자를 받는 명령(ARB ETH, DISC 005930)은 아래 6자리 종목코드 검사보다 먼저 처리한다.
  const coinArg = tokens[1] && /^[A-Z0-9]{2,10}$/.test(tokens[1]) ? tokens[1] : '';
  if (command?.argParam && coinArg) { location.href = `${command.href}?${command.argParam}=${coinArg}`; return; }

  const stockCode = text.match(/\b\d{6}\b/)?.[0];
  if (stockCode) { location.href = `/trade/stock.html?symbol=${stockCode}`; return; }

  // 공개 사이트는 코인을 다루지 않으므로 KRW-마켓 입력도 코인 화면으로 보내지 않는다.
  const marketArg = !terminalIsPublic && tokens.find(t => /^KRW-[A-Z0-9]{2,10}$/.test(t));
  if (marketArg) { location.href = `/trade/order.html?market=${marketArg}`; return; }

  if (command) {
    if (command.action === 'help') { renderTerminalHelp(); return; }
    if (command.action === 'hts') { renderTerminalHelp('HTS'); return; }
    if (command.action === 'cvd') {
      const on = toggleCvdPalette();
      const input = document.getElementById('term-cmd-input');
      if (input) { input.value = ''; input.placeholder = on ? 'CVD 팔레트 켜짐 — 상승 파랑 / 하락 빨강' : 'CVD 팔레트 꺼짐 — 상승 초록 / 하락 빨강'; }
      return;
    }
    if (command.href === '/trade/order.html' && coinArg) { location.href = `/trade/order.html?market=KRW-${coinArg}`; return; }
    location.href = command.href;
    return;
  }

  // 한글 등 자유 입력은 메뉴 이름에서 먼저 찾는다.
  const groups = window.__termNavGroups || [];
  const items = groups.flatMap(g => g.type === 'single' ? [g] : g.items);
  const needle = text.toLowerCase();
  const menuHit = items.find(item => item.label.toLowerCase().includes(needle));
  if (menuHit) { location.href = menuHit.href; return; }

  // 한글이나 여러 단어로 된 문장은 Jev(TypeSafe)에 뜻을 물어본다. 꺼져 있거나 실패하면 아래 기존 동작.
  if (/[가-힣]/.test(text) || tokens.length > 1) { routeByIntent(text, first); return; }
  fallbackCommand(text, first);
}

function fallbackCommand(text, first) {
  if (!terminalIsPublic && /^[A-Z0-9]{2,10}$/.test(first)) { location.href = `/trade/order.html?market=KRW-${first}`; return; }
  location.href = `/trade/stock.html?q=${encodeURIComponent(text)}`;
}

/* ── 자연어 명령(Jev) ─────────────────────────────────────────────────────── */
// 화면 이름은 서버 문자열이 아니라 이 표에서 가져온다.
const INTENT_LABELS = {
  dashboard: '대시보드', stock: '주식', disclosures: '공시 레이더', coin: '코인', arbitrage: '코인 차익·김프', alternatives: '대체자산',
  holdings: '보유자산', history: '거래이력', avg_down: '물타기 계산기', quant: '퀀트 랩(백테스트)',
  research: 'AI 리서치', knowledge: '지식 검색', analysis: '투자 분석 학습', openapi: '플랫폼 Open API',
};

// 서버가 만든 주소라도 같은 사이트의 경로만 받는다.
function intentPath(href) {
  const path = String(href ?? '');
  // '//host'(외부 이동)와 '..'(브라우저가 정규화해 숨김 목록을 비껴가는 경로)는 거부
  if (!/^\/(?!\/)[\w\-./]*(\?[\w\-=&%]*)?$/.test(path) || path.includes('..')) return null;
  return terminalIsPublic && PUBLIC_HIDDEN_HREFS.has(_hrefPath(path)) ? null : path;
}

// 자연어 명령은 미국 TypeSafe로 가는 국외 이전이라, 처리방침 버전에 동의한 브라우저만 보낸다.
const JEV_CONSENT_KEY = 'jevConsentVersion';

function readJevConsent() {
  try { return localStorage.getItem(JEV_CONSENT_KEY) || ''; } catch (_) { return ''; }
}

function saveJevConsent(version) {
  try { localStorage.setItem(JEV_CONSENT_KEY, version); } catch (_) { /* 저장 못 하면 이번 한 번만 보낸다 */ }
}

/**
 * 명령 바 아래에 국외 이전 안내와 동의 버튼을 보여 준다(innerHTML 없이 DOM으로 만든다).
 * @param {string} text 사용자가 입력한 명령 문장
 * @param {string} first 첫 단어(대문자)
 * @param {string} version 서버가 요구한 처리방침 버전
 * @returns {void}
 */
function renderJevConsent(text, first, version) {
  const box = document.getElementById('term-cmd-help');
  if (!box) return;  // 동의를 물을 곳이 없으면 아무 데도 보내지 않는다(검색 주소로도 넘기지 않는다)
  const line = (label, body) => {
    const row = document.createElement('div');
    const b = document.createElement('b');
    b.textContent = label;
    const span = document.createElement('span');
    span.textContent = body;
    row.append(b, span);
    return row;
  };
  const agree = document.createElement('button');
  agree.type = 'button';
  agree.className = 'term-consent-btn';
  agree.textContent = '동의하고 보내기';
  agree.addEventListener('click', () => { saveJevConsent(version); closeTerminalHelp(); routeByIntent(text, first, version); });
  const decline = document.createElement('button');
  decline.type = 'button';
  decline.className = 'term-consent-btn';
  decline.textContent = '보내지 않기';
  decline.addEventListener('click', () => closeTerminalHelp());  // 거절하면 문장을 어디로도 보내지 않는다
  const policy = document.createElement('a');
  policy.href = '/privacy.html';
  policy.textContent = '개인정보 처리방침';
  const actions = document.createElement('div');
  actions.className = 'term-consent-actions';
  actions.append(agree, decline, policy);
  box.replaceChildren(
    line('국외 이전', '자연어 명령은 뜻을 해석하려고 미국 TypeSafe AI, Inc.로 보냅니다.'),
    line('보내는 것', '입력한 문장(최대 200자)만 보냅니다. 회원 정보는 보내지 않고, 이 서비스는 문장을 저장하지 않습니다.'),
    line('주의', '명령 바에 이름·연락처 같은 개인정보를 입력하지 마세요. 동의하지 않으면 문장을 보내지 않습니다. 메뉴 이름이나 종목코드는 동의 없이도 됩니다.'),
    actions,
  );
  box.classList.add('open');
}

async function routeByIntent(text, first, consent = readJevConsent()) {
  // 동의 전에는 문장을 이 서비스 서버로도 보내지 않는다(처리방침 4절 "어디로도 보내지 않습니다").
  // /me를 받지 못해 동의 버전을 알 수 없으면 보내지 않고 도움말만 보인다.
  if (!terminalMe?.privacyVersion) { renderTerminalHelp(); return; }
  // Jev가 꺼져 있으면 해외 전송 자체가 없다. 이때는 이 사이트의 주식 검색으로 넘긴다(접속 기록 대상).
  if (!terminalMe.jevEnabled) { fallbackCommand(text, first); return; }
  if (consent !== terminalMe.privacyVersion) {
    renderJevConsent(text, first, terminalMe.privacyVersion);
    return;
  }
  const input = document.getElementById('term-cmd-input');
  if (input) { input.disabled = true; input.placeholder = '명령을 해석하는 중…'; }
  let result = null;
  try {
    const res = await apiFetch('/api/intent', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, consent }),
    });
    if (res.ok) result = await res.json();
  } catch (_) { /* 기존 동작으로 */ }
  if (input) input.disabled = false;
  if (result?.consentRequired) { renderJevConsent(text, first, result.consentVersion); return; }
  if (!result?.enabled) { fallbackCommand(text, first); return; }

  const target = intentPath(result.href);
  if (result.action === 'go' && target) {
    // 목록에 없는 종목(예: 엔비디아)은 주식 화면의 검색어로 넘긴다.
    location.href = result.screen === 'stock' && !target.includes('symbol=') ? `/trade/stock.html?q=${encodeURIComponent(text)}` : target;
    return;
  }
  const options = (result.alternatives || []).map(alt => ({ ...alt, path: intentPath(alt.href) })).filter(alt => alt.path);
  if (result.action === 'suggest' && options.length) { renderIntentSuggestions(options); return; }
  renderTerminalHelp();
}

function renderIntentSuggestions(options) {
  const box = document.getElementById('term-cmd-help');
  if (!box) return;
  box.innerHTML = '<div><b>명령 해석</b><span>어느 화면을 찾으시나요? (모델 판단 확률)</span></div>' + options.map(alt =>
    `<div data-href="${escapeHtml(alt.path)}"><b>${escapeHtml(INTENT_LABELS[alt.screen] || alt.screen)}</b><span>${Math.round(alt.probability * 100)}%</span></div>`
  ).join('');
  box.classList.add('open');
}

function startTerminalClock() {
  const el = document.getElementById('term-clock');
  if (!el) return;
  const fmt = new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
  const tick = () => { el.textContent = `${fmt.format(new Date())} KST`; };
  tick();
  clearInterval(window.__termClockTimer);
  window.__termClockTimer = setInterval(tick, 1000);
}

const TAPE_COINS = ['KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-SOL', 'KRW-DOGE'];
/**
 * 실제 시세가 아닌 출처의 화면 이름표(서버 응답의 source 값). stock.js 배지와 같은 표기다.
 * @type {Record<string, string>}
 */
const DATA_SOURCE_LABELS = { synthetic: '합성 데이터', simulated: '시뮬레이션' };

const tapeState = { index: [], stocks: [], coins: [], sourceLabel: '' };

function tapeItem({ code, price, rate, digits = 0 }) {
  const n = Number(rate);
  const cls = !Number.isFinite(n) || n === 0 ? 'flat' : n > 0 ? 'up' : 'down';
  const arrow = cls === 'up' ? '▲' : cls === 'down' ? '▼' : '■';
  const px = Number(price).toLocaleString('ko-KR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
  const pct = Number.isFinite(n) ? `${n > 0 ? '+' : ''}${n.toFixed(2)}%` : '-';
  return `<span class="term-tape-item"><b>${code}</b><span class="px">${px}</span><span class="${cls}">${arrow} ${pct}</span></span>`;
}

function renderTickerTape() {
  const track = document.getElementById('term-tape-track');
  if (!track) return;
  const items = [...tapeState.index, ...tapeState.coins, ...tapeState.stocks];
  if (!items.length) return;
  // 합성 데이터면 띠 맨 앞에 알린다(실제 시세로 오해하지 않게).
  const note = tapeState.sourceLabel ? `<span class="badge badge-muted">${escapeHtml(tapeState.sourceLabel)} · 실제 시세 아님</span>` : '';
  const html = note + items.map(tapeItem).join('');
  track.innerHTML = html + html;
  track.style.setProperty('--tape-duration', `${Math.max(40, items.length * 5)}s`);
}

async function refreshTapeIndex() {
  try {
    const res = await apiFetch('/api/stocks/market');
    if (!res.ok) return;
    const data = await res.json();
    tapeState.index = ['KOSPI', 'KOSDAQ'].filter(k => data?.[k]).map(k => ({ code: k, price: data[k].price, rate: data[k].changeRate, digits: 2 }));
    tapeState.sourceLabel ||= ['KOSPI', 'KOSDAQ'].map(k => DATA_SOURCE_LABELS[data?.[k]?.source]).find(Boolean) || '';
    renderTickerTape();
  } catch (_) {}
}

async function refreshTapeStocks() {
  try {
    const res = await apiFetch('/api/stocks/prices');
    if (!res.ok) return;
    const data = await res.json();
    tapeState.sourceLabel ||= Object.values(data?.prices ?? {}).map(p => DATA_SOURCE_LABELS[p.source]).find(Boolean) || '';
    tapeState.stocks = Object.values(data?.prices ?? {}).slice(0, 12)
      .map(p => ({ code: p.name, price: p.price, rate: p.changeRate }));
    renderTickerTape();
  } catch (_) {}
}

async function refreshTapeCoins() {
  try {
    const res = await fetch(`/upbit-api/ticker?markets=${TAPE_COINS.join(',')}`);
    if (!res.ok) return;
    const rows = await res.json();
    tapeState.coins = (Array.isArray(rows) ? rows : []).map(r => ({
      code: r.market.replace('KRW-', ''), price: r.trade_price, rate: r.signed_change_rate * 100,
      digits: r.trade_price < 100 ? 2 : 0,
    }));
    renderTickerTape();
  } catch (_) {}
}

function startTickerTape() {
  if (!document.getElementById('term-tape') || window.__termTapeStarted) return;
  window.__termTapeStarted = true;
  refreshTapeIndex(); refreshTapeStocks();
  setInterval(refreshTapeIndex, 60_000);
  // 공개 사이트는 코인을 다루지 않는다(업비트 중계도 없다).
  if (!terminalIsPublic) { refreshTapeCoins(); setInterval(refreshTapeCoins, 10_000); }
  setInterval(refreshTapeStocks, 30_000);
}

// 명령줄 포커스(/)·기능키(Alt+1~9)·명령 도움말 키보드 동작.
document.addEventListener('keydown', event => {
  const tag = event.target?.tagName;
  const typing = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || event.target?.isContentEditable;
  if (event.key === '/' && !typing && !event.ctrlKey && !event.metaKey) {
    const input = document.getElementById('term-cmd-input');
    if (input) { event.preventDefault(); input.focus(); input.select(); }
    return;
  }
  if (event.altKey && !event.ctrlKey && !event.metaKey && /^[1-9]$/.test(event.key)) {
    const f = TERMINAL_FKEYS.find(item => item.key === event.key);
    if (f && document.getElementById('site-header')) { event.preventDefault(); location.href = f.href; }
  }
});
document.addEventListener('input', event => {
  if (event.target?.id === 'term-cmd-input') {
    const value = event.target.value;
    if (value.trim()) renderTerminalHelp(value.split(/\s+/)[0]); else closeTerminalHelp();
  }
});
document.addEventListener('click', event => {
  const row = event.target.closest?.('#term-cmd-help [data-cmd]');
  if (row) { runTerminalCommand(row.dataset.cmd); return; }
  const suggestion = event.target.closest?.('#term-cmd-help [data-href]');
  if (suggestion) { location.href = suggestion.dataset.href; return; }
  if (!event.target.closest?.('.term-cmd')) closeTerminalHelp();
});

/* ── 헤더 동작(인라인 onclick 대신 data-action 위임) ─────────────────────────
   인라인 핸들러를 쓰지 않아야 화면에 script-src 'self' CSP를 걸 수 있다. */
const HEADER_ACTIONS = {
  logout: () => logout(),
  go: el => { closeOffcanvas(); if (intentPath(el.dataset.href)) location.href = el.dataset.href; },
  'toggle-oc': el => toggleOcGroup(Number(el.dataset.index)),
  'toggle-right': el => toggleRightGroup(Number(el.dataset.index)),
  'open-oc': () => openOffcanvas(),
  'close-oc': () => closeOffcanvas(),
  'open-ai': () => openAiPanel(),
  'close-ai': () => closeAiPanel(),
};
document.addEventListener('click', event => {
  const el = event.target.closest?.('#header-mount [data-action]');
  const run = el && HEADER_ACTIONS[el.dataset.action];
  if (run) run(el);
});
document.addEventListener('submit', event => {
  const form = event.target.closest?.('form.term-cmd');
  if (!form) return;
  event.preventDefault();
  runTerminalCommand(form.elements.cmd.value);
});

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
document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeOffcanvas(); closeAiPanel(); closeTerminalHelp(); } });

function toggleOcGroup(idx) {
  document.querySelectorAll('#oc-panel .oc-group').forEach((el, i) => {
    const open = i === idx ? !el.classList.contains('open') : false;
    el.classList.toggle('open', open);
    el.querySelector('.oc-group-toggle')?.setAttribute('aria-expanded', String(open));
    const body = el.querySelector('.oc-group-body');
    if (body) {
      body.style.maxHeight = open ? `${body.scrollHeight}px` : '0px';
      body.style.overflow = open ? 'visible' : 'hidden';
    }
  });
}

function toggleRightGroup(idx) {
  const groups = document.querySelectorAll('#ai-panel .oc-nav .oc-group');
  groups.forEach((el, i) => {
    const open = i === idx ? !el.classList.contains('open') : false;
    el.classList.toggle('open', open);
    el.querySelector('.oc-group-toggle')?.setAttribute('aria-expanded', String(open));
    const body = el.querySelector('.oc-group-body');
    if (body) {
      body.style.maxHeight = open ? `${body.scrollHeight}px` : '0px';
      body.style.overflow = open ? 'visible' : 'hidden';
    }
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
        <div style="border-left:3px solid var(--info);padding:.45rem .7rem;margin-bottom:.5rem;background:var(--surface-2);border-radius:0 var(--radius-xs) var(--radius-xs) 0;">
          <div style="display:flex;align-items:center;gap:6px;margin-bottom:.2rem;">
            <span style="font-size:10px;font-weight:700;background:var(--info-bg);color:var(--info);padding:1px 6px;border-radius:var(--radius-xs);">${_catLabel(doc.category)}</span>
            <span style="font-size:11px;font-weight:700;color:var(--fg);">${escapeHtml(doc.title)}</span>
            <span style="font-size:10px;color:var(--muted);margin-left:auto;">유사도 ${(doc.score * 100).toFixed(0)}%</span>
          </div>
          <p style="font-size:11px;color:var(--fg-2);margin:0;line-height:1.5;">${escapeHtml(String(doc.text ?? '').substring(0,120))}...</p>
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
    if (res.status === 401) throw new Error('로그인 후 사용할 수 있습니다.');
    if (res.status === 429) throw new Error('요청이 많습니다. 잠시 후 다시 시도해주세요.');
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
    box.innerHTML = `<p style="color:var(--down);font-size:13px;">오류: ${escapeHtml(err.message)}</p>`;
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
      <div style="border:1px solid var(--border);border-left:3px solid var(--info);border-radius:var(--radius-xs);padding:.7rem .9rem;margin-bottom:.5rem;background:var(--surface);">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:.4rem;">
          <span style="font-size:10px;font-weight:700;background:var(--info-bg);color:var(--info);padding:1px 7px;border-radius:var(--radius-xs);">${_catLabel(h.category)}</span>
          <span style="font-size:12.5px;font-weight:800;color:var(--fg);flex:1;">${escapeHtml(h.title)}</span>
          <div style="font-size:10px;font-weight:800;color:#000;background:${_scoreColor(h.score)};border-radius:var(--radius-xs);padding:1px 7px;font-family:var(--font-mono);">${(h.score*100).toFixed(0)}%</div>
        </div>
        <p style="font-size:12px;color:var(--fg-2);margin:0;line-height:1.65;">${escapeHtml(h.text)}</p>
      </div>`).join('');
  } catch (err) {
    if (res) res.innerHTML = `<p style="color:var(--down);font-size:13px;">오류: ${escapeHtml(err.message)}</p>`;
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
        <div><span style="color:var(--muted);">컬렉션</span><br><strong style="color:var(--accent-dark);font-size:14px;">${escapeHtml(data.collection)}</strong></div>
        <div><span style="color:var(--muted);">문서 수</span><br><strong style="color:var(--accent-dark);font-size:14px;">${escapeHtml(data.count)}개</strong></div>
        <div style="grid-column:1/-1;"><span style="color:var(--muted);">임베딩 모델</span><br><code style="font-size:11px;color:var(--fg-2);">${escapeHtml(data.model)}</code></div>
      </div>`;
  } catch (e) {
    if (statsEl) statsEl.innerHTML = `<span style="color:var(--down);font-size:12px;">통계 불러오기 실패</span>`;
  }

  // 문서 목록
  try {
    const r    = await apiFetch('/api/stocks/ai/qdrant/list?limit=40');
    const data = await r.json();
    const docs = data.documents ?? [];
    if (listEl) listEl.innerHTML = docs.length
      ? docs.map(d => `
        <div style="display:flex;align-items:baseline;gap:6px;padding:.35rem .5rem;border-radius:var(--radius-xs);margin-bottom:.2rem;background:var(--surface);border:1px solid var(--border);">
          <span style="font-size:11px;font-weight:700;background:var(--accent-light);color:var(--accent-dark);padding:2px 6px;border-radius:var(--radius-xs);white-space:nowrap;">${_catLabel(d.category)}</span>
          <span style="font-size:13px;font-weight:600;color:var(--fg);flex:1;">${escapeHtml(d.title)}</span>
        </div>`).join('')
      : '<p style="color:var(--muted);font-size:12px;text-align:center;">문서가 없습니다.</p>';
  } catch (e) {
    if (listEl) listEl.innerHTML = `<span style="color:var(--down);font-size:12px;">목록 불러오기 실패</span>`;
  }
}

async function addQdrantDoc() {
  const title    = document.getElementById('new-doc-title')?.value?.trim() ?? '';
  const category = document.getElementById('new-doc-category')?.value ?? 'custom';
  const text     = document.getElementById('new-doc-text')?.value?.trim()  ?? '';
  const btn      = document.getElementById('add-doc-btn');
  const msg      = document.getElementById('add-doc-msg');

  if (!text) {
    if (msg) { msg.style.display='block'; msg.style.color='var(--down)'; msg.textContent='내용을 입력하세요.'; }
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
      if (msg) { msg.style.display='block'; msg.style.color='var(--up)'; msg.textContent=`✓ 추가 완료 (ID: ${data.id?.substring(0,8)}...)`; }
      document.getElementById('new-doc-title').value = '';
      document.getElementById('new-doc-text').value  = '';
      setTimeout(() => loadDataset(), 600);
    } else {
      if (msg) { msg.style.display='block'; msg.style.color='var(--down)'; msg.textContent=data.error ?? '추가 실패'; }
    }
  } catch (err) {
    if (msg) { msg.style.display='block'; msg.style.color='var(--down)'; msg.textContent='오류: ' + err.message; }
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
  }[cat] ?? escapeHtml(cat);
}
function _scoreColor(s) {
  if (s >= 0.75) return 'var(--up)';
  if (s >= 0.55) return 'var(--warn)';
  return 'var(--muted)';
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
      const href = escapeHtml(safeHttpUrl(n.pdf_url ?? n.page_url));
      const dateStr = _krxFmtDate(n.date);
      return `
        <a href="${href}" target="_blank" rel="noopener noreferrer"
          style="display:block;padding:.45rem 1rem;border-bottom:1px solid var(--border);text-decoration:none;"
          onmouseover="this.style.background='var(--surface-3)'" onmouseout="this.style.background='transparent'">
          <div style="font-size:12px;font-weight:600;color:var(--fg);line-height:1.45;margin-bottom:3px;">${escapeHtml(n.title)}</div>
          <div style="display:flex;align-items:center;gap:6px;">
            <span style="font-size:10px;color:var(--info);background:var(--info-bg);border-radius:var(--radius-xs);padding:0 5px;">PDF</span>
            <span style="font-size:10.5px;color:var(--muted);font-family:var(--font-mono);">${escapeHtml(dateStr)}</span>
            <span style="font-size:10px;color:var(--muted);margin-left:auto;">조회 ${escapeHtml(n.view_cnt)}</span>
          </div>
        </a>`;
    }).join('');

    _krxNewsLoaded = true;
  } catch (err) {
    listEl.innerHTML = `<p style="color:var(--down);text-align:center;font-size:12px;margin-top:1rem;">오류: ${escapeHtml(err.message)}</p>`;
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
  // 먼저 이스케이프하고, 그다음 제한된 마크다운(제목·굵게·기울임·목록)만 태그로 바꾼다.
  return escapeHtml(md)
    .replace(/^### (.+)$/gm, '<h3 style="font-size:14px;font-weight:800;color:var(--info);margin:1rem 0 .4rem;">$1</h3>')
    .replace(/^## (.+)$/gm,  '<h2 style="font-size:15px;font-weight:800;color:var(--accent);margin:1.2rem 0 .5rem;">$1</h2>')
    .replace(/^# (.+)$/gm,   '<h1 style="font-size:16px;font-weight:900;color:var(--fg);margin:1.4rem 0 .6rem;">$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong style="color:var(--fg);font-weight:700;">$1</strong>')
    .replace(/\*(.+?)\*/g,     '<em style="color:var(--warn);">$1</em>')
    .replace(/^- (.+)$/gm,    '<li style="margin:.25rem 0;padding-left:.5rem;">• $1</li>')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>');
}

/* ── Page init ───────────────────────────────────────────────────────────── */
function ensureSiteFooter(user) {
  // 화면별로 누락되지 않도록 공통 상태 바를 한 번만 만든다. 트레이딩 화면처럼
  // #site-footer가 body 바로 아래가 아니어도 기존 요소를 재사용한다.
  let footer = document.getElementById('site-footer');
  let note = '';
  if (!footer) {
    // 페이지가 따로 둔 설명 푸터는 상태 바로 바꾸고, 그 문구는 상태 바 메모로 남긴다.
    footer = document.body.querySelector(':scope > footer');
    if (footer) {
      note = footer.textContent.replace(/\s+/g, ' ').trim().replace(/^Noah Trading Desk\s*·\s*/i, '');
      footer.className = '';
    } else {
      footer = document.createElement('footer');
      document.body.appendChild(footer);
    }
    footer.id = 'site-footer';
  }
  const noteText = (note || '모든 거래 기능은 학습·테스트 용도입니다.').replace(/[&<>"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));
  footer.classList.add('term-status');
  footer.innerHTML = `
    <div class="term-status-row">
      <span><i class="term-dot" id="term-conn-dot" aria-hidden="true"></i><b id="term-conn-text">연결됨</b></span>
      <span>MODE <b>PAPER</b></span>
      <span>SCREEN <b>${terminalScreenCode()}</b></span>
      <span class="term-status-hide-sm">USER <b>${user?.loggedIn ? escapeHtml(user.username) : 'GUEST'}</b></span>
      <span class="term-status-hide-sm term-status-note">${noteText}</span>
      <a class="term-status-privacy" href="/privacy.html"><b>개인정보 처리방침</b></a>
      <span class="term-status-brand">NOAH TRADING DESK</span>
    </div>`;
  setTerminalConnection(user?.__apiReachable !== false);
}

function setTerminalConnection(ok) {
  document.getElementById('term-conn-dot')?.classList.toggle('off', !ok);
  const text = document.getElementById('term-conn-text');
  if (text) text.textContent = ok ? '연결됨' : '서버 응답 없음';
}

function mountApiTestGuide() {
  if (document.getElementById('api-test-guide')) return;
  const path = location.pathname;
  const guides = {
    '/broker-api-test.html': {
      title: '이 화면의 API 호출과 기대 결과',
      rate: '<strong>KIS Testbed 조회 전용 화면</strong> — 접근 토큰은 서버에서 캐시해 재사용합니다. 호출 제한을 피하려면 조회 버튼을 빠르게 연속 클릭하지 마세요.',
      rows: [
        ['KIS 현재가', 'GET /api/broker-test/kis/quote?symbol=005930', 'symbol: 6자리 KRX 코드', 'ok: true, quote.price·changeRate·volume·tradeTime'],
        ['KIS 일봉', 'GET /api/broker-test/kis/chart?symbol=005930', 'symbol: 6자리 KRX 코드', 'ok: true, chart.data 배열(날짜·OHLC 가격)'],
        ['KIS 호가', 'GET /api/broker-test/kis/orderbook?symbol=005930', 'symbol: 6자리 KRX 코드', 'ok: true, orderbook 매도·매수 10단계'],
        ['KIS 잔고', 'GET /api/broker-test/kis/balance', '서버의 KIS_ACCOUNT_NO', 'ok: true, balance 현금·평가·보유종목 정보'],
        ['KIS 지수', 'GET /api/broker-test/kis/index?code=0001', '0001(코스피) 또는 1001(코스닥)', 'ok: true, index 현재 지수·등락 정보'],
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
        ['모의 주문 흐름', 'POST 승인 → POST /api/broker-test/kis/order-flow-test', '로그인 회원 + CSRF + 1회 승인 + 서버 Testbed 계좌', 'ok: true, test.environment·symbol·currentPrice·testPrice·amendedPrice. 서버가 모의 주문→정정→취소까지 완료'],
      ],
      note: '이 호출만 상태를 변경합니다. 현재가의 90%(호가 단위 내림) 지정가로 1주 매수 주문 후 한 호가 아래로 정정하고 취소합니다. 정정·취소가 실패하면 미체결을 조회해 정리하며, 이미 실행 중이면 거부합니다.',
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
  // 새 레이아웃은 [data-api-guide-host] 자리에 접힌 상태로 두고, 옛 화면은 첫 섹션 끝에 펼쳐 둔다.
  const slot = document.querySelector('[data-api-guide-host]');
  const host = slot || document.querySelector('main > section') || document.querySelector('main');
  if (!host) return;
  const rows = guide.rows.map(([name, endpoint, input, expected]) => `<tr><th>${name}</th><td><code>${endpoint}</code></td><td>${input}</td><td>${expected}</td></tr>`).join('');
  const element = document.createElement('details');
  element.id = 'api-test-guide';
  element.className = 'api-test-guide';
  element.open = !slot;
  element.innerHTML = `<summary>${guide.title}<span>호출 경로 · 입력값 · 성공 기준 보기</span></summary><p class="api-test-guide-rate">${guide.rate}</p><div class="api-test-guide-scroll"><table><thead><tr><th>테스트</th><th>이 웹앱 서버 호출</th><th>필요한 값</th><th>성공 시 확인할 값</th></tr></thead><tbody>${rows}</tbody></table></div>${guide.note ? `<p class="api-test-guide-note">${guide.note}</p>` : ''}<p class="api-test-guide-note">공통 성공 형식은 <code>ok: true</code>입니다. <code>ok: false</code> 또는 HTTP 4xx/5xx이면 결과창의 <code>message</code>를 확인하세요. Key·Secret·Access Token·계좌번호는 응답에 표시하지 않습니다.</p>`;
  host.appendChild(element);
}

// 학습 문서(main.term-doc)의 섹션 제목으로 왼쪽 목차 레일을 만든다.
function mountDocToc() {
  const main = document.querySelector('body > main.term-doc');
  if (!main || main.querySelector(':scope > .term-toc')) return;
  const entries = [];
  let seq = 0;
  for (const section of main.querySelectorAll(':scope > section')) {
    if (section.classList.contains('term-hero')) continue;
    const heading = section.querySelector(':scope > :is(h2, .title, .lesson-title, .cur-title)') || section.querySelector('h2');
    if (!heading) continue;
    if (!section.id) section.id = `sec-${++seq}`;
    const kicker = (section.querySelector(':scope > :is(.kicker, .cur-kicker)')?.textContent || '').split('·')[0].trim();
    const subs = [...section.querySelectorAll(':scope > details.cur-sec > summary')].map((summary, i) => {
      const details = summary.parentElement;
      if (!details.id) details.id = `${section.id}-${i + 1}`;
      return { id: details.id, label: summary.textContent.trim() };
    });
    entries.push({ id: section.id, label: heading.textContent.trim(), kicker, subs });
  }
  if (entries.length < 2) return;
  const esc = text => text.replace(/[&<>"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));
  const items = entries.map(e => `<li><a href="#${e.id}" data-toc="${e.id}">${e.kicker ? `<small>${esc(e.kicker)}</small>` : ''}${esc(e.label)}</a>${
    e.subs.length ? `<ol class="term-toc-sub">${e.subs.map(s => `<li><a href="#${s.id}" data-toc="${s.id}">${esc(s.label)}</a></li>`).join('')}</ol>` : ''}</li>`).join('');
  const nav = document.createElement('nav');
  nav.className = 'term-toc';
  nav.setAttribute('aria-label', '이 문서의 목차');
  nav.innerHTML = `<details${matchMedia('(min-width: 1101px)').matches ? ' open' : ''}><summary>목차 · ${entries.length}개 절</summary><ol>${items}</ol></details>`;
  main.prepend(nav);

  // 접힌 과정표 절로 이동할 때는 먼저 펼친다.
  nav.addEventListener('click', event => {
    const id = event.target.closest('a[data-toc]')?.dataset.toc;
    const target = id && document.getElementById(id);
    if (target?.tagName === 'DETAILS') target.open = true;
  });

  const links = new Map([...nav.querySelectorAll('a[data-toc]')].map(a => [a.dataset.toc, a]));
  const observer = new IntersectionObserver(records => {
    for (const record of records) {
      if (!record.isIntersecting) continue;
      links.forEach(a => a.classList.remove('active'));
      links.get(record.target.id)?.classList.add('active');
    }
  }, { root: main, rootMargin: '0px 0px -75% 0px' });
  entries.forEach(e => observer.observe(document.getElementById(e.id)));
}

async function initPage({ requireAuth = false } = {}) {
  const user = await getCurrentUser();
  terminalMe = user;
  // 코인처럼 공개 사이트에서 뺀 요소([data-local-only])는 local로 확인될 때만 보인다(깜빡임 없이 숨김).
  document.documentElement.dataset.profile = user?.profile || 'unknown';
  if (requireAuth && !user?.loggedIn) {
    location.href = '/member/login.html';
    return null;
  }
  applyProfileToTerminal(user);
  renderHeader(user);
  mountDatasetComposerModal();
  mountApiTestGuide();
  mountDocToc();
  ensureSiteFooter(user);
  const hasMain = document.body.querySelector(':scope > main');
  const hasFooter = document.body.querySelector(':scope > footer');
  if (hasMain && hasFooter && !document.body.classList.contains('alternatives-layout')) {
    document.body.classList.add('app-shell-layout');
  }
  return user;
}
