const form = document.querySelector('#crawl-form');
const sectorForm = document.querySelector('#sector-form');
const sectorSelect = document.querySelector('#sector-select');
const statusEl = document.querySelector('#sheet-status');
const workspace = document.querySelector('#sheet-workspace');
const table = document.querySelector('#data-sheet');
const STORAGE_KEY = 'ai-sheet:v1';
let model = { columns: [], rows: [] };
let quantActive = false; // true while the M-1 예측/실제 columns are inserted at index 1,2
let currentMeta = { title: '', sourceUrl: '', sourceType: '' };

const tabs = [
  { button: document.querySelector('#tab-crawl'), panel: document.querySelector('#panel-crawl') },
  { button: document.querySelector('#tab-sector'), panel: document.querySelector('#panel-sector') },
];
function activateTab(target) {
  for (const { button, panel } of tabs) {
    const active = button === target;
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', String(active));
    panel.hidden = !active;
  }
}
for (const { button } of tabs) button.addEventListener('click', () => activateTab(button));

initPage();
loadSectors();
restoreFromStorage();

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
}
function draw() {
  const quantCols = quantActive ? [1, 2] : [];
  table.innerHTML = `<thead><tr>${model.columns.map((column, i) => `<th><input aria-label="${i + 1}번째 열 제목" value="${esc(column)}"></th>`).join('')}</tr></thead><tbody>${model.rows.map(row => `<tr>${model.columns.map((_, i) => `<td${quantCols.includes(i) ? ' class="quant-col"' : ''}><input value="${esc(row[i] ?? '')}"></td>`).join('')}</tr>`).join('')}</tbody>`;
  applyPinning(quantActive ? 3 : 1);
}
function readModel() {
  model.columns = [...table.querySelectorAll('thead input')].map(input => input.value.trim() || '열');
  model.rows = [...table.querySelectorAll('tbody tr')].map(row => [...row.querySelectorAll('input')].map(input => input.value));
}
function csvCell(value) { return `"${String(value).replaceAll('"', '""')}"`; }

function applyPinning(pinCount) {
  const headerCells = [...table.querySelectorAll('thead th')];
  const bodyRows = [...table.querySelectorAll('tbody tr')];
  let left = 0;
  for (let col = 0; col < pinCount && col < headerCells.length; col++) {
    const isLast = col === pinCount - 1;
    const th = headerCells[col];
    th.classList.add('pinned'); th.classList.toggle('pinned-last', isLast);
    th.style.left = `${left}px`;
    bodyRows.forEach(row => {
      const td = row.children[col];
      if (!td) return;
      td.classList.add('pinned'); td.classList.toggle('pinned-last', isLast);
      td.style.left = `${left}px`;
    });
    left += th.getBoundingClientRect().width;
  }
}

function showConfirmModal(message) {
  return new Promise(resolve => {
    const overlay = document.querySelector('#confirm-modal');
    const okBtn = document.querySelector('#confirm-modal-ok');
    const cancelBtn = document.querySelector('#confirm-modal-cancel');
    document.querySelector('#confirm-modal-message').textContent = message;
    overlay.hidden = false;
    okBtn.focus();
    const cleanup = result => {
      overlay.hidden = true;
      okBtn.removeEventListener('click', onOk);
      cancelBtn.removeEventListener('click', onCancel);
      overlay.removeEventListener('click', onOverlay);
      resolve(result);
    };
    const onOk = () => cleanup(true);
    const onCancel = () => cleanup(false);
    const onOverlay = event => { if (event.target === overlay) cleanup(false); };
    okBtn.addEventListener('click', onOk);
    cancelBtn.addEventListener('click', onCancel);
    overlay.addEventListener('click', onOverlay);
  });
}

function startLoadingStatus(label) {
  statusEl.className = 'sheet-status loading';
  const startedAt = Date.now();
  const render = () => {
    const elapsed = Math.floor((Date.now() - startedAt) / 1000);
    statusEl.innerHTML = `<span class="hourglass-spin" aria-hidden="true">⏳</span> ${esc(label)} (경과 ${elapsed}초)`;
  };
  render();
  const timer = setInterval(render, 1000);
  return () => clearInterval(timer);
}

function applySheetMeta() {
  document.querySelector('#sheet-title').textContent = currentMeta.title;
  const source = document.querySelector('#sheet-source');
  if (currentMeta.sourceUrl) { source.hidden = false; source.href = currentMeta.sourceUrl; source.textContent = `${currentMeta.sourceType} 원문 열기 ↗`; }
  else { source.hidden = true; source.removeAttribute('href'); }
}

function saveToStorage() {
  try {
    readModel();
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      model, quantActive, meta: currentMeta,
      activeTab: document.querySelector('#tab-sector').classList.contains('active') ? 'sector' : 'crawl',
    }));
  } catch (error) { /* localStorage 사용 불가(비공개 모드 등) — 메모리 상의 시트는 계속 동작 */ }
}

function restoreFromStorage() {
  let saved;
  try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null'); } catch (error) { saved = null; }
  if (!saved || !saved.model || !Array.isArray(saved.model.columns) || !saved.model.rows.length) return;
  model = saved.model;
  quantActive = !!saved.quantActive;
  currentMeta = saved.meta || { title: '', sourceUrl: '', sourceType: '' };
  draw();
  applySheetMeta();
  workspace.hidden = false;
  statusEl.className = 'sheet-status';
  statusEl.textContent = `${model.rows.length}행 · ${model.columns.length}열 — 브라우저에 저장된 이전 시트를 불러왔습니다.`;
  if (saved.activeTab === 'sector') activateTab(document.querySelector('#tab-sector'));
}

async function runQuantAnalysis() {
  readModel();
  if (quantActive) { model.columns.splice(1, 2); model.rows.forEach(row => row.splice(1, 2)); quantActive = false; }

  const monthColumns = model.columns.slice(1);
  if (monthColumns.length < 4 || !/^\d{4}-\d{2}$/.test(monthColumns[0])) {
    draw();
    statusEl.className = 'sheet-status error';
    statusEl.textContent = '퀀트분석은 "섹터별 월별 종가" 탭에서 만든, yyyy-mm 월별 종가 시트에서만 사용할 수 있습니다.';
    return;
  }

  const confirmed = await showConfirmModal('퀀트분석은 상당한 시간이 소요되는 작업입니다. 계속하시겠습니까?');
  if (!confirmed) { draw(); return; }

  const button = document.querySelector('#quant-analyze');
  button.disabled = true;
  const stopLoading = startLoadingStatus('퀀트분석 중입니다… (scikit-learn 회귀 모델 학습)');
  try {
    const response = await apiFetch('/api/ai-sheet/quant-analyze', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ columns: model.columns, rows: model.rows }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || '퀀트분석에 실패했습니다.');
    model = { columns: data.columns, rows: data.rows };
    quantActive = true;
    draw();
    saveToStorage();
    stopLoading(); statusEl.className = 'sheet-status'; statusEl.textContent = data.notice;
  } catch (error) {
    draw();
    stopLoading(); statusEl.className = 'sheet-status error'; statusEl.textContent = error.message;
  } finally { button.disabled = false; }
}

async function runLeanBacktest() {
  readModel();
  const offset = model.columns.findIndex((column, i) => i >= 1 && /^\d{4}-\d{2}$/.test(column));
  if (offset === -1 || model.columns.length - offset < 2 || !model.rows.length) {
    statusEl.className = 'sheet-status error';
    statusEl.textContent = 'LEAN 백테스트는 "섹터별 월별 종가" 시트(yyyy-mm 칼럼)에서만 사용할 수 있습니다.';
    return;
  }

  const rowIndex = 0;
  const stockName = model.rows[rowIndex]?.[0] || '첫 번째 종목';
  const confirmed = await showConfirmModal('LEAN 백테스트는 상당한 시간이 소요되는 작업입니다. 계속하시겠습니까?');
  if (!confirmed) return;

  const button = document.querySelector('#lean-backtest');
  button.disabled = true;
  const stopLoading = startLoadingStatus(`${stockName} 종목으로 QuantConnect LEAN 백테스트를 실행하는 중입니다… (Docker 컨테이너 실행)`);
  try {
    const response = await apiFetch('/api/ai-sheet/lean-backtest', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ columns: model.columns, rows: model.rows, rowIndex }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || 'LEAN 백테스트에 실패했습니다.');
    const summary = Object.entries(data.statistics || {}).map(([key, value]) => `${key} ${value}`).join(' · ');
    stopLoading(); statusEl.className = 'sheet-status';
    statusEl.textContent = `${data.notice} (${data.startDate} ~ ${data.endDate}) ${summary}`;
  } catch (error) {
    stopLoading(); statusEl.className = 'sheet-status error'; statusEl.textContent = error.message;
  } finally { button.disabled = false; }
}

function renderSheet(data) {
  model = { columns: data.columns, rows: data.rows };
  quantActive = false;
  currentMeta = { title: data.title || '', sourceUrl: data.sourceUrl || '', sourceType: data.sourceType || '' };
  draw();
  applySheetMeta();
  statusEl.className = 'sheet-status'; statusEl.textContent = `${data.rows.length}행 · ${data.columns.length}열을 가져왔습니다. ${data.notice}`; workspace.hidden = false;
  saveToStorage();
}

table.addEventListener('input', () => { clearTimeout(table._saveTimer); table._saveTimer = setTimeout(saveToStorage, 400); });

async function loadSectors() {
  try {
    const response = await apiFetch('/api/ai-sheet/sectors');
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || '섹터 목록을 가져오지 못했습니다.');
    sectorSelect.innerHTML = data.sectors.length
      ? data.sectors.map(item => `<option value="${esc(item.sector)}">${esc(item.sector)} (${item.count}종목)</option>`).join('')
      : '<option value="">사용 가능한 섹터가 없습니다</option>';
  } catch (error) { sectorSelect.innerHTML = '<option value="">섹터 목록을 가져오지 못했습니다</option>'; }
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  const button = document.querySelector('#crawl-button'); const url = document.querySelector('#source-url').value.trim();
  button.disabled = true; statusEl.className = 'sheet-status loading'; statusEl.textContent = '페이지를 읽고 시트를 만드는 중입니다…'; workspace.hidden = true;
  try {
    const response = await apiFetch('/api/ai-sheet/crawl', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({url}) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || '시트를 만들지 못했습니다.');
    renderSheet(data);
  } catch (error) { statusEl.className = 'sheet-status error'; statusEl.textContent = error.message; }
  finally { button.disabled = false; }
});

sectorForm.addEventListener('submit', async event => {
  event.preventDefault();
  const button = document.querySelector('#sector-button'); const sector = sectorSelect.value;
  if (!sector) return;
  button.disabled = true; statusEl.className = 'sheet-status loading'; statusEl.textContent = `${sector} 섹터의 월별 종가를 가져오는 중입니다… (종목이 많으면 다소 시간이 걸릴 수 있습니다)`; workspace.hidden = true;
  try {
    const response = await apiFetch('/api/ai-sheet/sector-sheet', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({sector}) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || '섹터 시트를 만들지 못했습니다.');
    renderSheet(data);
  } catch (error) { statusEl.className = 'sheet-status error'; statusEl.textContent = error.message; }
  finally { button.disabled = false; }
});
document.querySelector('#quant-analyze').addEventListener('click', runQuantAnalysis);
document.querySelector('#lean-backtest').addEventListener('click', runLeanBacktest);
document.querySelector('#add-row').addEventListener('click', () => { readModel(); model.rows.push(Array(model.columns.length).fill('')); draw(); table.querySelector('tbody tr:last-child input')?.focus(); saveToStorage(); });
document.querySelector('#download-csv').addEventListener('click', () => { readModel(); const csv = [model.columns, ...model.rows].map(row => row.map(csvCell).join(',')).join('\r\n'); const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob(['\ufeff' + csv], {type:'text/csv;charset=utf-8'})); link.download = 'ai-sheet.csv'; link.click(); URL.revokeObjectURL(link.href); });
