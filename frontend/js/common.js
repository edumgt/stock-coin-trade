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

    <!-- 오른쪽 오프캔버스 — AI + Qdrant RAG 패널 -->
    <aside id="ai-panel" style="position:fixed;top:0;right:0;height:100vh;width:460px;max-width:94vw;background:#FFFFFF;border-left:1px solid var(--border);box-shadow:-4px 0 24px rgba(0,0,0,0.08);z-index:400;transform:translateX(100%);transition:transform 0.28s cubic-bezier(0.4,0,0.2,1);display:flex;flex-direction:column;">

      <!-- 패널 헤더 -->
      <div style="display:flex;align-items:center;justify-content:space-between;padding:.85rem 1.1rem;border-bottom:1px solid var(--border);flex-shrink:0;">
        <div style="display:flex;align-items:center;gap:8px;">
          <span style="font-size:17px;">✨</span>
          <span style="font-size:15px;font-weight:800;color:var(--fg);">AI 시장 분석</span>
          <span style="font-size:10px;font-weight:700;background:linear-gradient(135deg,#6366F1,#8B5CF6);color:#fff;padding:2px 7px;border-radius:99px;letter-spacing:.04em;">Qdrant RAG</span>
        </div>
        <button onclick="closeAiPanel()" style="background:var(--surface-2);border:1px solid var(--border);border-radius:6px;padding:3px 10px;font-size:12px;color:var(--muted);cursor:pointer;">✕</button>
      </div>

      <!-- 탭 바 -->
      <div style="display:flex;border-bottom:1px solid var(--border);flex-shrink:0;background:var(--surface);">
        <button id="ai-tab-btn-analyze"  onclick="switchAiTab('analyze')"  class="ai-tab-btn ai-tab-active"  style="flex:1;padding:.6rem .4rem;font-size:12px;font-weight:700;border:none;cursor:pointer;border-bottom:2px solid #6366F1;color:#6366F1;background:transparent;transition:all .15s;">🤖 AI 분석</button>
        <button id="ai-tab-btn-search"   onclick="switchAiTab('search')"   class="ai-tab-btn"                style="flex:1;padding:.6rem .4rem;font-size:12px;font-weight:700;border:none;cursor:pointer;border-bottom:2px solid transparent;color:var(--muted);background:transparent;transition:all .15s;">🔍 지식 검색</button>
        <button id="ai-tab-btn-dataset"  onclick="switchAiTab('dataset')"  class="ai-tab-btn"                style="flex:1;padding:.6rem .4rem;font-size:12px;font-weight:700;border:none;cursor:pointer;border-bottom:2px solid transparent;color:var(--muted);background:transparent;transition:all .15s;">📚 데이터셋</button>
      </div>

      <!-- ══ 탭 1: AI 분석 ══ -->
      <div id="ai-tab-content-analyze" style="flex:1;display:flex;flex-direction:column;overflow:hidden;">

        <!-- ▲ 상단: AI 분석 영역 (flex:1) -->
        <div style="flex:1;min-height:0;display:flex;flex-direction:column;overflow:hidden;">
          <!-- 컨트롤 영역 -->
          <div style="padding:.75rem 1.1rem;border-bottom:1px solid var(--border);flex-shrink:0;">
            <p style="font-size:11.5px;color:var(--muted);margin-bottom:.55rem;line-height:1.5;">현재 화면의 시세 데이터와 <strong style="color:#6366F1;">Qdrant 지식 베이스</strong>를 결합해 Claude AI가 시장 분석을 제공합니다.</p>
            <div style="display:flex;gap:6px;margin-bottom:.55rem;">
              <select id="aiContextSelect" style="flex:1;background:var(--surface-2);border:1.5px solid var(--border);color:var(--fg);border-radius:6px;padding:.35rem .6rem;font-size:12.5px;outline:none;">
                <option value="crypto">코인 시장</option>
                <option value="stock">주식 시장</option>
                <option value="general">전체 시장 개요</option>
              </select>
              <select id="aiRagLimit" style="width:74px;background:var(--surface-2);border:1.5px solid var(--border);color:var(--fg);border-radius:6px;padding:.35rem .4rem;font-size:11.5px;outline:none;" title="Qdrant 참조 문서 수">
                <option value="3">참조 3</option>
                <option value="5" selected>참조 5</option>
                <option value="8">참조 8</option>
              </select>
            </div>
            <button onclick="runAiAnalysis()" id="aiRunBtn"
              style="width:100%;background:linear-gradient(135deg,#6366F1,#8B5CF6);color:#fff;border:none;border-radius:7px;padding:.5rem 1rem;font-size:13.5px;font-weight:700;cursor:pointer;box-shadow:0 2px 10px rgba(99,102,241,0.28);transition:opacity .15s;">
              ✨ 분석 시작
            </button>
          </div>

          <!-- Qdrant 검색된 근거 (접기/펼치기) -->
          <div id="ai-rag-block" style="display:none;border-bottom:1px solid var(--border);flex-shrink:0;">
            <button onclick="toggleRagBlock()" style="width:100%;display:flex;align-items:center;justify-content:space-between;padding:.5rem 1.1rem;background:linear-gradient(90deg,#EEF2FF,#F5F3FF);border:none;cursor:pointer;font-size:11.5px;font-weight:700;color:#4F46E5;">
              <span>📚 Qdrant 검색된 근거 <span id="rag-hit-count" style="background:#6366F1;color:#fff;border-radius:99px;padding:1px 6px;font-size:10px;">0</span></span>
              <span id="rag-chevron" style="font-size:10px;transition:transform .2s;">▼</span>
            </button>
            <div id="rag-context-list" style="display:none;max-height:160px;overflow-y:auto;padding:.45rem 1.1rem .6rem;background:#F8F7FF;"></div>
          </div>

          <!-- AI 분석 결과 -->
          <div id="aiContent" style="flex:1;overflow-y:auto;padding:.85rem 1.1rem;font-size:13px;line-height:1.85;color:var(--fg);">
            <p style="color:var(--muted);text-align:center;margin-top:2rem;font-size:13px;">버튼을 눌러 AI 분석을 시작하세요.</p>
          </div>
        </div>

        <!-- ▼ 하단: KRX 보도자료 뉴스 (고정 높이) -->
        <div style="height:260px;min-height:260px;display:flex;flex-direction:column;border-top:2px solid #E0E7FF;background:#F8F9FF;">
          <!-- 뉴스 헤더 -->
          <div style="display:flex;align-items:center;justify-content:space-between;padding:.5rem 1rem .45rem;flex-shrink:0;background:linear-gradient(90deg,#EEF2FF,#F5F3FF);border-bottom:1px solid #C7D2FE;">
            <div style="display:flex;align-items:center;gap:6px;">
              <span style="font-size:13px;">📰</span>
              <span style="font-size:11.5px;font-weight:800;color:#3730A3;">KRX 보도자료</span>
              <span id="krx-total-badge" style="font-size:10px;color:#6366F1;background:#EEF2FF;border:1px solid #C7D2FE;border-radius:99px;padding:0 6px;"></span>
            </div>
            <button onclick="loadKrxNews()" id="krx-refresh-btn" style="font-size:10.5px;color:#6366F1;background:none;border:none;cursor:pointer;padding:2px 4px;">↻ 새로고침</button>
          </div>
          <!-- 뉴스 목록 (스크롤) -->
          <div id="krx-news-list" style="flex:1;overflow-y:auto;padding:.3rem 0;">
            <p style="color:var(--muted);text-align:center;font-size:12px;margin-top:1.5rem;">뉴스를 불러오는 중...</p>
          </div>
        </div>

      </div>

      <!-- ══ 탭 2: 지식 검색 ══ -->
      <div id="ai-tab-content-search" style="flex:1;display:none;flex-direction:column;overflow:hidden;">
        <div style="padding:.85rem 1.1rem;border-bottom:1px solid var(--border);flex-shrink:0;">
          <p style="font-size:12px;color:var(--muted);margin-bottom:.65rem;line-height:1.5;">Qdrant 벡터 DB에서 관련 투자 지식을 시맨틱 검색합니다.</p>
          <div style="display:flex;gap:6px;">
            <input id="qdrant-search-input" type="text" placeholder="예: RSI 과매수, 하락장 대응, 반도체 투자..."
              style="flex:1;background:var(--surface-2);border:1.5px solid var(--border);color:var(--fg);border-radius:6px;padding:.4rem .7rem;font-size:13px;outline:none;"
              onkeydown="if(event.key==='Enter') runQdrantSearch()"/>
            <button onclick="runQdrantSearch()" id="qdrant-search-btn"
              style="background:linear-gradient(135deg,#6366F1,#8B5CF6);color:#fff;border:none;border-radius:6px;padding:.4rem .9rem;font-size:13px;font-weight:700;cursor:pointer;white-space:nowrap;">검색</button>
          </div>
        </div>
        <div id="qdrant-search-results" style="flex:1;overflow-y:auto;padding:.8rem 1.1rem;">
          <p style="color:var(--muted);text-align:center;margin-top:2rem;font-size:13px;">검색어를 입력하면 유사한 금융 지식을 찾아드립니다.</p>
        </div>
      </div>

      <!-- ══ 탭 3: 데이터셋 ══ -->
      <div id="ai-tab-content-dataset" style="flex:1;display:none;flex-direction:column;overflow:hidden;">
        <div style="flex:1;overflow-y:auto;padding:.85rem 1.1rem;">

          <!-- 통계 카드 -->
          <div id="qdrant-stats-card" style="background:linear-gradient(135deg,#EEF2FF,#F5F3FF);border:1px solid #C7D2FE;border-radius:10px;padding:.85rem 1rem;margin-bottom:.85rem;">
            <div style="display:flex;align-items:center;gap:6px;margin-bottom:.5rem;">
              <span style="font-size:14px;">🗄️</span>
              <span style="font-size:13px;font-weight:800;color:#4338CA;">Qdrant Collection</span>
            </div>
            <div id="qdrant-stats-body" style="font-size:12px;color:#6B7280;">불러오는 중...</div>
          </div>

          <!-- 문서 목록 -->
          <div style="margin-bottom:.85rem;">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.5rem;">
              <span style="font-size:12px;font-weight:700;color:var(--fg);">📄 지식 문서 목록</span>
              <button onclick="loadDataset()" style="font-size:11px;color:#6366F1;background:none;border:none;cursor:pointer;text-decoration:underline;">새로고침</button>
            </div>
            <div id="qdrant-doc-list" style="font-size:11.5px;"></div>
          </div>

          <!-- 새 지식 추가 폼 -->
          <div style="border:1.5px solid #C7D2FE;border-radius:10px;padding:.85rem;background:#FAFAFE;">
            <p style="font-size:12px;font-weight:800;color:#4338CA;margin-bottom:.6rem;">➕ 새 지식 추가</p>
            <input id="new-doc-title" type="text" placeholder="제목 (예: POSCO홀딩스 분석)"
              style="width:100%;box-sizing:border-box;background:white;border:1.5px solid var(--border);color:var(--fg);border-radius:6px;padding:.38rem .65rem;font-size:12px;outline:none;margin-bottom:.45rem;"/>
            <select id="new-doc-category"
              style="width:100%;box-sizing:border-box;background:white;border:1.5px solid var(--border);color:var(--fg);border-radius:6px;padding:.38rem .65rem;font-size:12px;outline:none;margin-bottom:.45rem;">
              <option value="technical_analysis">기술적 분석</option>
              <option value="fundamental_analysis">기본적 분석</option>
              <option value="sector_analysis">섹터 분석</option>
              <option value="market_structure">시장 구조</option>
              <option value="investment_strategy">투자 전략</option>
              <option value="risk_management">리스크 관리</option>
              <option value="custom">기타</option>
            </select>
            <textarea id="new-doc-text" placeholder="지식 내용을 입력하세요 (최대 2000자)..."
              rows="5" style="width:100%;box-sizing:border-box;background:white;border:1.5px solid var(--border);color:var(--fg);border-radius:6px;padding:.4rem .65rem;font-size:12px;outline:none;resize:vertical;margin-bottom:.55rem;line-height:1.6;"></textarea>
            <button onclick="addQdrantDoc()" id="add-doc-btn"
              style="width:100%;background:linear-gradient(135deg,#6366F1,#8B5CF6);color:#fff;border:none;border-radius:6px;padding:.5rem;font-size:13px;font-weight:700;cursor:pointer;">
              Qdrant에 추가
            </button>
            <div id="add-doc-msg" style="display:none;font-size:12px;margin-top:.5rem;text-align:center;"></div>
          </div>
        </div>
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
  // 패널 열릴 때 뉴스 자동 로드 (캐시 있으면 즉시)
  loadKrxNews();
}
function closeAiPanel() {
  const panel   = document.getElementById('ai-panel');
  const overlay = document.getElementById('ai-overlay');
  if (panel)   { panel.style.transform   = 'translateX(100%)'; }
  if (overlay) { overlay.style.display   = 'none'; }
}

/* ── 탭 전환 ─────────────────────────────────────────────────────────────── */
let _activeAiTab = 'analyze';
function switchAiTab(tab) {
  _activeAiTab = tab;
  ['analyze','search','dataset'].forEach(t => {
    const content = document.getElementById('ai-tab-content-' + t);
    const btn     = document.getElementById('ai-tab-btn-' + t);
    const active  = t === tab;
    if (content) {
      content.style.display = active ? 'flex' : 'none';
      if (active) content.style.flexDirection = 'column';
    }
    if (btn) {
      btn.style.borderBottom = active ? '2px solid #6366F1' : '2px solid transparent';
      btn.style.color        = active ? '#6366F1' : 'var(--muted)';
    }
  });
  if (tab === 'dataset') loadDataset();
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
        <div><span style="color:#9CA3AF;">컬렉션</span><br><strong style="color:#4338CA;font-size:13px;">${data.collection}</strong></div>
        <div><span style="color:#9CA3AF;">문서 수</span><br><strong style="color:#4338CA;font-size:13px;">${data.count}개</strong></div>
        <div style="grid-column:1/-1;"><span style="color:#9CA3AF;">임베딩 모델</span><br><code style="font-size:10px;color:#6B7280;">${data.model}</code></div>
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
          <span style="font-size:9px;font-weight:700;background:#EEF2FF;color:#4F46E5;padding:1px 5px;border-radius:99px;white-space:nowrap;">${_catLabel(d.category)}</span>
          <span style="font-size:11.5px;font-weight:600;color:#1F2937;flex:1;">${d.title}</span>
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
async function initPage({ requireAuth = false } = {}) {
  const user = await getCurrentUser();
  if (requireAuth && !user?.loggedIn) {
    location.href = '/member/login.html';
    return null;
  }
  renderHeader(user);
  return user;
}
