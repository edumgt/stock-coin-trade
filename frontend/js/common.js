const API_BASE = window.APP_CONFIG?.apiBase ?? '';

/* ── API fetch wrapper ───────────────────────────────────────────────────── */
async function apiFetch(path, options = {}) {
  return fetch(API_BASE + path, { credentials: 'include', ...options });
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
  const navLinks = [
    { href: '/index.html',       label: '홈',      icon: '🏠' },
    { href: '/trade/order.html', label: '코인',    icon: '💹' },
    { href: '/trade/stock.html', label: '주식',    icon: '📈' },
    { href: '/trade/hold.html',  label: '보유자산', icon: '💼' },
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

  const ocNavItems = navLinks.map(n =>
    `<a href="${n.href}" class="oc-nav-item"><span style="font-size:16px;">${n.icon}</span> ${n.label}</a>`).join('');

  const html = `
    <!-- 왼쪽 오프캔버스 오버레이 -->
    <div id="oc-overlay" onclick="closeOffcanvas()"></div>

    <!-- 왼쪽 오프캔버스 — 네비게이션 메뉴 -->
    <aside id="oc-panel">
      <div class="oc-header">
        <span class="brand-logo-text" style="font-size:17px;letter-spacing:1.5px;">EDUMGT</span>
        <button class="oc-close-btn" onclick="closeOffcanvas()">✕</button>
      </div>
      <nav class="oc-nav">
        ${ocNavItems}
        <div class="oc-divider"></div>
        <a href="javascript:void(0)" class="oc-nav-item" onclick="closeOffcanvas();openAiPanel()">
          <span style="font-size:16px;">✨</span> AI 시장 분석
        </a>
      </nav>
      <div class="oc-footer" style="font-size:11px;color:var(--muted);">
        <div>(주)에듀엠지티</div>
        <a href="https://www.edumgt.co.kr" target="_blank" style="color:var(--accent-dark);text-decoration:none;font-weight:600;">www.edumgt.co.kr</a>
      </div>
    </aside>

    <!-- 슬림 헤더 — 로고 + 유저 섹션만 -->
    <header id="site-header">
      <div class="mx-auto flex w-full max-w-[1640px] items-center justify-between px-4 py-2">
        <a href="/index.html" style="text-decoration:none;display:flex;align-items:center;">
          <span class="brand-logo-text">EDUMGT</span>
        </a>
        ${userSection}
      </div>
    </header>

    <!-- 콘텐츠 영역 내 플로팅 컨트롤 바 (햄버거 ← 왼쪽, AI → 오른쪽) -->
    <div id="content-ctrl-bar" style="position:sticky;top:44px;z-index:90;display:flex;justify-content:space-between;align-items:center;padding:4px 12px;background:var(--surface);border-bottom:1px solid var(--border);box-shadow:0 1px 4px rgba(0,0,0,0.04);">
      <!-- 왼쪽 오프캔버스 트리거 (≡ 메뉴) -->
      <button onclick="openOffcanvas()" aria-label="메뉴 열기"
        style="display:flex;align-items:center;gap:6px;background:transparent;border:none;cursor:pointer;padding:4px 6px;border-radius:6px;transition:background .12s;color:var(--fg-2);font-size:14px;font-weight:600;"
        onmouseover="this.style.background='var(--accent-light)'" onmouseout="this.style.background='transparent'">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <rect x="2" y="5"  width="16" height="2" rx="1" fill="currentColor"/>
          <rect x="2" y="9"  width="16" height="2" rx="1" fill="currentColor"/>
          <rect x="2" y="13" width="16" height="2" rx="1" fill="currentColor"/>
        </svg>
        <span class="hidden md:inline">메뉴</span>
      </button>

      <!-- 오른쪽 오프캔버스 트리거 (AI 분석 →) -->
      <button onclick="openAiPanel()" aria-label="AI 분석 열기"
        style="display:flex;align-items:center;gap:6px;background:var(--accent-light);border:1.5px solid rgba(41,98,255,0.18);cursor:pointer;padding:4px 12px;border-radius:6px;transition:background .12s;color:var(--accent-dark);font-size:13px;font-weight:700;"
        onmouseover="this.style.background='rgba(41,98,255,0.15)'" onmouseout="this.style.background='var(--accent-light)'">
        ✨ AI 분석
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M3 7h8M7 3l4 4-4 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
    </div>

    <!-- 오른쪽 오프캔버스 오버레이 -->
    <div id="ai-overlay" onclick="closeAiPanel()" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.35);z-index:399;backdrop-filter:blur(3px);"></div>

    <!-- 오른쪽 오프캔버스 — AI 분석 패널 -->
    <aside id="ai-panel" style="position:fixed;top:0;right:0;height:100vh;width:420px;max-width:92vw;background:#FFFFFF;border-left:1px solid var(--border);box-shadow:-4px 0 24px rgba(0,0,0,0.08);z-index:400;transform:translateX(100%);transition:transform 0.28s cubic-bezier(0.4,0,0.2,1);display:flex;flex-direction:column;">
      <div style="display:flex;align-items:center;justify-content:space-between;padding:1rem 1.25rem;border-bottom:1px solid var(--border);">
        <div style="display:flex;align-items:center;gap:8px;">
          <span style="font-size:18px;">✨</span>
          <span style="font-size:16px;font-weight:800;color:var(--fg);">AI 시장 분석</span>
        </div>
        <button onclick="closeAiPanel()" style="background:var(--surface-2);border:1px solid var(--border);border-radius:6px;padding:4px 10px;font-size:13px;color:var(--muted);cursor:pointer;">✕</button>
      </div>
      <div style="padding:1rem 1.25rem;border-bottom:1px solid var(--border);">
        <p style="font-size:13px;color:var(--muted);margin-bottom:.7rem;">현재 화면의 시세 데이터를 기반으로 Claude AI가 시장 조언을 제공합니다.</p>
        <select id="aiContextSelect" style="background:var(--surface-2);border:1.5px solid var(--border);color:var(--fg);border-radius:6px;padding:.4rem .7rem;font-size:14px;width:100%;outline:none;margin-bottom:.7rem;">
          <option value="crypto">코인 시장</option>
          <option value="stock">주식 시장</option>
          <option value="general">전체 시장 개요</option>
        </select>
        <button onclick="runAiAnalysis()" id="aiRunBtn"
          style="width:100%;background:var(--accent);color:#fff;border:none;border-radius:6px;padding:.6rem 1rem;font-size:15px;font-weight:700;cursor:pointer;box-shadow:0 2px 10px rgba(41,98,255,0.28);transition:opacity .15s;">
          분석 시작
        </button>
      </div>
      <div id="aiContent" style="flex:1;overflow-y:auto;padding:1.25rem;font-size:14px;line-height:1.8;color:var(--fg);">
        <p style="color:var(--muted);text-align:center;margin-top:3rem;">버튼을 눌러 AI 분석을 시작하세요.</p>
      </div>
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

/* ── AI 사이드패널 ───────────────────────────────────────────────────────── */
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

function collectMarketContext(type) {
  const rows = [];
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

async function runAiAnalysis() {
  const btn  = document.getElementById('aiRunBtn');
  const box  = document.getElementById('aiContent');
  const type = document.getElementById('aiContextSelect')?.value ?? 'general';

  btn.disabled = true;
  btn.textContent = '분석 중...';
  box.innerHTML = '<div style="text-align:center;padding:2rem 0;"><span style="color:var(--muted);">✨ AI가 분석 중입니다...</span></div>';

  const context = collectMarketContext(type);

  try {
    const res = await apiFetch('/api/ai/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ context, type }),
    });

    if (!res.ok) throw new Error('분석 서비스 오류');

    const reader = res.body?.getReader();
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
    box.innerHTML = `<p style="color:#F87171;">오류: ${err.message}</p>`;
  } finally {
    btn.disabled = false;
    btn.textContent = '다시 분석';
  }
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
async function initPage({ requireAuth = false } = {}) {
  const user = await getCurrentUser();
  if (requireAuth && !user?.loggedIn) {
    location.href = '/member/login.html';
    return null;
  }
  renderHeader(user);
  return user;
}
