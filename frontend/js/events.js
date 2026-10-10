/* 공시 레이더 화면. 서버 /api/disclosures가 저장해 둔 DART 공시와 판정(규칙·Jev)을 그린다.
   교육용 분류이며 투자 권유가 아니다. 주문 기능은 없다. */

const DISC_POLL_MS = 60_000;

const disc = {
  day: '',          // YYYY-MM-DD, 비우면 서버가 오늘(KST)을 쓴다
  symbol: '',
  watch: false,     // 내 관심 종목 모아 보기(브라우저의 stockWatchlist, 서버에 저장하지 않음)
  kind: '',
  riskOnly: false,
  kinds: {},        // 유형 id → 화면 이름(서버가 준다)
  items: [],
  range: null,      // 서버가 답한 {date, from, to}. date가 null이면 종목 최근 30일 모드
  backtestable: new Set(),  // 퀀트 랩에 시세가 있는 종목(/api/quant/overview). 이 종목에만 백테스트 링크를 단다
};

/** 서버가 한 번에 주는 최대 건수(discQuery의 limit). 이만큼 받으면 더 있을 수 있다고 알린다. */
const DISC_LIMIT = 500;
let discTimer = null;

const discEsc = escapeHtml;
const pct = p => typeof p === 'number' && Number.isFinite(p) ? `${Math.round(p * 100)}%` : '';

/**
 * 오늘 날짜(KST)를 YYYY-MM-DD로 돌려준다.
 * @returns {string}
 */
function kstToday() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul' }).format(new Date());
}

/**
 * 주식 화면에서 ★로 고른 관심 종목(브라우저 저장소). 서버에 보내지 않고 조회 조건으로만 쓴다.
 * @returns {string[]} 6자리 종목코드, 최대 20개
 */
function watchedSymbols() {
  try {
    const list = JSON.parse(localStorage.getItem('stockWatchlist') || '[]');
    return (Array.isArray(list) ? list : []).filter(code => /^\d{6}$/.test(code)).slice(0, 20);
  } catch (_) { return []; }
}

/**
 * 현재 필터로 API 주소를 만든다. 유형은 화면에서 거르므로 보내지 않는다(유형별 건수를 함께 보여 주려고).
 * @returns {string}
 */
function discQuery() {
  const params = new URLSearchParams();
  if (disc.day) params.set('date', disc.day);
  if (disc.watch) params.set('symbols', watchedSymbols().join(','));
  else if (/^\d{6}$/.test(disc.symbol)) params.set('symbol', disc.symbol);
  if (disc.riskOnly) params.set('risk', '1');
  params.set('limit', String(DISC_LIMIT));
  return `/api/disclosures?${params}`;
}

/**
 * 서버에서 공시를 읽어 다시 그린다.
 * @returns {Promise<void>}
 */
async function loadDisclosures() {
  const live = document.getElementById('discLive');
  if (disc.watch && !watchedSymbols().length) {
    disc.items = [];
    disc.range = null;
    renderDisclosures('관심 종목이 없습니다. 주식 화면에서 ★를 눌러 관심 종목을 추가하세요.');
    return;
  }
  try {
    const res = await apiFetch(discQuery());
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.message || `HTTP ${res.status}`);
    disc.items = Array.isArray(body.items) ? body.items : [];
    disc.kinds = body.kinds || disc.kinds;
    disc.range = { date: body.date ?? null, from: body.from, to: body.to };
    document.getElementById('day').value = body.date || '';
    if (body.attribution) document.getElementById('discSource').textContent = body.attribution;
    live?.classList.remove('is-off');
    renderKindOptions();
    renderDisclosures();
  } catch (err) {
    live?.classList.add('is-off');
    document.getElementById('discBody').innerHTML =
      `<tr><td class="empty" colspan="7">공시를 불러오지 못했습니다: ${discEsc(err.message)}</td></tr>`;
  }
}

/** 유형 선택 상자를 서버가 준 유형 목록으로 채운다. */
function renderKindOptions() {
  const select = document.getElementById('kind');
  if (select.options.length > 1) return;
  for (const [key, label] of Object.entries(disc.kinds)) select.add(new Option(label, key));
  select.value = disc.kind;
}

/**
 * 판정 칸: 규칙이면 '규칙', 모델이면 '모델'과 모델 판단 확률.
 * @param {object} item API 항목
 * @returns {string} HTML
 */
function judgedCell(item) {
  if (item.judgedBy !== 'jev') return '<span class="by">규칙</span>';
  const probs = [item.kindProb != null ? `유형 ${pct(item.kindProb)}` : '', item.riskProb != null ? `위험 ${pct(item.riskProb)}` : '']
    .filter(Boolean).join(' · ');
  return `<span class="by" title="판정 모델 판단 확률">모델 ${discEsc(probs)}</span>`;
}

/**
 * 목록과 유형별 건수를 그린다.
 * @param {string} [emptyText] 목록이 비었을 때 보여 줄 안내
 * @returns {void}
 */
function renderDisclosures(emptyText = '조건에 맞는 공시가 없습니다. 휴일이거나 수집기가 아직 돌지 않았을 수 있습니다.') {
  const rows = disc.kind ? disc.items.filter(item => item.kind === disc.kind) : disc.items;
  const riskCount = disc.items.filter(item => item.risk).length;
  document.getElementById('discCount').textContent =
    `${rows.length}건 표시 · 전체 ${disc.items.length}건${disc.items.length >= DISC_LIMIT ? '(최대 500건까지만 받음)' : ''} · 위험 ${riskCount}건`;
  // 날짜 없이 종목만 고르면 서버가 최근 30일을 준다(주말·휴일에도 비지 않게). 그때는 접수일 열을 보인다.
  const spanMode = Boolean(disc.range && !disc.range.date);
  document.getElementById('colDate').hidden = !spanMode;
  document.getElementById('discTitle').textContent = disc.watch
    ? `내 관심 종목 ${watchedSymbols().length}개 최근 30일 공시${disc.range?.from ? ` (${disc.range.from} ~ ${disc.range.to})` : ''}`
    : spanMode
    ? `${disc.symbol} 최근 30일 공시 (${disc.range.from} ~ ${disc.range.to})`
    : `${disc.range?.date || disc.day || kstToday()} 공시${disc.symbol ? ` · ${disc.symbol}` : ''}`;

  document.getElementById('discBody').innerHTML = rows.length ? rows.map(item => {
    const code = /^\d{6}$/.test(item.stockCode || '') ? item.stockCode : '';
    // 원문 링크는 서버 문자열 대신 접수번호로 다시 만든다(같은 DART 주소만 연다).
    const link = /^\d{14}$/.test(item.rceptNo || '') ? `https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${item.rceptNo}` : '';
    const title = link
      ? `<a href="${link}" target="_blank" rel="noopener noreferrer">${discEsc(item.reportName)}</a>`
      : discEsc(item.reportName);
    return `<tr class="${item.risk ? 'is-risk' : ''}">
      ${spanMode ? `<td>${discEsc(item.date || '-')}</td>` : ''}
      <td>${discEsc(item.firstSeenKst || '-')}</td>
      <td class="txt who">${discEsc(item.corpName)}<small>${discEsc(item.market || '')}${code ? ` · <a href="/events.html?symbol=${code}">${code}</a>${disc.backtestable.has(code) ? ` · <a href="/quant.html?symbol=${code}" title="이 종목으로 백테스트(공개 사이트는 합성 학습 데이터)">백테스트</a>` : ''}` : ''}</small></td>
      <td class="txt">${title}${item.corrected ? '<small>정정 공시</small>' : ''}</td>
      <td class="txt">${discEsc(item.kindLabel || item.kind)}</td>
      <td>${item.risk ? '<span class="flag">⚠ 위험</span>' : '-'}</td>
      <td>${judgedCell(item)}</td>
    </tr>`;
  }).join('') : `<tr><td class="empty" colspan="7">${discEsc(emptyText)}</td></tr>`;

  const counts = {};
  for (const item of disc.items) counts[item.kind] = (counts[item.kind] || 0) + 1;
  const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  document.getElementById('kindBody').innerHTML = sorted.length ? sorted.map(([key, n]) =>
    `<tr data-kind="${discEsc(key)}" class="${key === disc.kind ? 'is-selected' : ''}" tabindex="0" role="button" aria-pressed="${key === disc.kind}">
      <td>${discEsc(disc.kinds[key] || key)}</td><td>${n}</td></tr>`).join('')
    : '<tr><td class="empty">-</td></tr>';
}

/** 현재 필터를 주소창에 남긴다(새로 고침·공유용). */
function syncUrl() {
  const params = new URLSearchParams();
  if (disc.day) params.set('date', disc.day);
  if (disc.watch) params.set('watch', '1');
  else if (disc.symbol) params.set('symbol', disc.symbol);
  if (disc.kind) params.set('kind', disc.kind);
  if (disc.riskOnly) params.set('risk', '1');
  const query = params.toString();
  history.replaceState(null, '', `${location.pathname}${query ? `?${query}` : ''}`);
}

/** 필터·유형 요약의 이벤트를 연결한다. */
function bindDiscEvents() {
  const day = document.getElementById('day');
  const symbol = document.getElementById('symbol');
  const kind = document.getElementById('kind');
  const riskOnly = document.getElementById('riskOnly');
  day.value = disc.day;
  symbol.value = disc.symbol;
  riskOnly.checked = disc.riskOnly;

  // 날짜를 비우면 오늘(종목이 있으면 최근 30일), 고르면 그날만.
  day.addEventListener('change', () => { disc.day = day.value; syncUrl(); loadDisclosures(); });
  symbol.addEventListener('input', () => {
    const value = symbol.value.replace(/\D/g, '').slice(0, 6);
    symbol.value = value;
    if (value.length === 0 || value.length === 6) { disc.symbol = value; setWatch(false); syncUrl(); loadDisclosures(); }
  });
  const watch = document.getElementById('watchOnly');
  const setWatch = on => { disc.watch = on; watch.setAttribute('aria-pressed', String(on)); };
  setWatch(disc.watch);
  watch.addEventListener('click', () => {
    setWatch(!disc.watch);
    if (disc.watch) { disc.symbol = ''; symbol.value = ''; }
    syncUrl();
    loadDisclosures();
  });
  kind.addEventListener('change', () => { disc.kind = kind.value; syncUrl(); renderDisclosures(); });
  riskOnly.addEventListener('change', () => { disc.riskOnly = riskOnly.checked; syncUrl(); loadDisclosures(); });
  document.getElementById('discFilters').addEventListener('submit', event => event.preventDefault());

  const pickKind = row => {
    disc.kind = disc.kind === row.dataset.kind ? '' : row.dataset.kind;
    kind.value = disc.kind;
    syncUrl();
    renderDisclosures();
  };
  const kindBody = document.getElementById('kindBody');
  kindBody.addEventListener('click', event => { const row = event.target.closest('tr[data-kind]'); if (row) pickKind(row); });
  kindBody.addEventListener('keydown', event => {
    const row = event.target.closest('tr[data-kind]');
    if (row && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); pickKind(row); }
  });
}

/** 1분마다 다시 읽는다(수집기는 5분마다 돈다). */
function startDiscPolling() {
  clearInterval(discTimer);
  discTimer = setInterval(loadDisclosures, DISC_POLL_MS);
}

document.addEventListener('visibilitychange', () => {
  if (document.hidden) { clearInterval(discTimer); return; }
  loadDisclosures();
  startDiscPolling();
});

document.addEventListener('DOMContentLoaded', async () => {
  const params = new URLSearchParams(location.search);
  const symbol = params.get('symbol') || '';
  const day = params.get('date') || '';
  if (/^\d{6}$/.test(symbol)) disc.symbol = symbol;
  if (/^\d{4}-\d{2}-\d{2}$/.test(day)) disc.day = day;
  disc.kind = /^[a-z_]{2,30}$/.test(params.get('kind') || '') ? params.get('kind') : '';
  disc.riskOnly = params.get('risk') === '1';
  disc.watch = params.get('watch') === '1';
  await initPage();
  bindDiscEvents();
  // 백테스트 링크는 시세가 있는 종목에만 단다(없으면 퀀트 랩에서 '시세가 부족합니다'로 끝난다).
  try {
    const res = await fetch('/api/quant/overview', { credentials: 'same-origin' });
    if (res.ok) {
      const overview = await res.json();
      // 백테스트 기간(최근 3년)에 시세가 충분한 종목만(backtestable). 옛 서버면 symbols로 대신한다.
      disc.backtestable = new Set((overview.backtestable || overview.symbols || []).filter(code => /^\d{6}$/.test(code)));
    }
  } catch (_) { /* 퀀트 DB가 없으면 링크를 달지 않는다 */ }
  await loadDisclosures();
  startDiscPolling();
});
