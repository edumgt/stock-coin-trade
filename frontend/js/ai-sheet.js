const form = document.querySelector('#crawl-form');
const sectorForm = document.querySelector('#sector-form');
const sectorSelect = document.querySelector('#sector-select');
const statusEl = document.querySelector('#sheet-status');
const workspace = document.querySelector('#sheet-workspace');
const table = document.querySelector('#data-sheet');
let model = { columns: [], rows: [] };
let quantActive = false; // true while the M-1 예측/실제 columns are inserted at index 1,2

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

function parsePrice(value) {
  const number = parseFloat(String(value ?? '').replace(/,/g, ''));
  return Number.isFinite(number) ? number : null;
}
function fmtPrice(value) { return value == null ? '' : Math.round(value).toLocaleString('ko-KR'); }

function linearRegression(xs, ys) {
  const n = xs.length;
  const sumX = xs.reduce((a, x) => a + x, 0);
  const sumY = ys.reduce((a, y) => a + y, 0);
  const sumXY = xs.reduce((a, x, i) => a + x * ys[i], 0);
  const sumXX = xs.reduce((a, x) => a + x * x, 0);
  const denom = n * sumXX - sumX * sumX;
  if (!denom) return { slope: 0, intercept: sumY / n };
  const slope = (n * sumXY - sumX * sumY) / denom;
  return { slope, intercept: (sumY - slope * sumX) / n };
}

function runQuantAnalysis() {
  readModel();
  if (quantActive) { model.columns.splice(1, 2); model.rows.forEach(row => row.splice(1, 2)); quantActive = false; }

  const monthColumns = model.columns.slice(1);
  const n = monthColumns.length;
  if (n < 4 || !/^\d{4}-\d{2}$/.test(monthColumns[0])) {
    draw();
    statusEl.className = 'sheet-status error';
    statusEl.textContent = '퀀트분석은 "섹터별 월별 종가" 탭에서 만든, yyyy-mm 월별 종가 시트에서만 사용할 수 있습니다.';
    return;
  }

  const idxM1 = n - 2; // 지난달(M-1) — 학습 결과를 검증할 실제 값
  const idxM2 = n - 3; // 그 이전 달(M-2) — 여기까지의 데이터로 학습
  const m1Label = monthColumns[idxM1];
  const predLabel = `M-1 예측(${m1Label})`;
  const actualLabel = `M-1 실제(${m1Label})`;

  model.rows.forEach(row => {
    const series = monthColumns.map((_, i) => parsePrice(row[1 + i]));
    const trainX = []; const trainY = [];
    for (let i = 0; i <= idxM2; i++) {
      if (series[i] != null) { trainX.push(i); trainY.push(series[i]); }
    }
    let predicted = null;
    if (trainX.length >= 2) {
      const { slope, intercept } = linearRegression(trainX, trainY);
      predicted = slope * idxM1 + intercept;
    } else if (trainX.length === 1) {
      predicted = trainY[0];
    }
    row.splice(1, 0, fmtPrice(predicted), fmtPrice(series[idxM1]));
  });
  model.columns.splice(1, 0, predLabel, actualLabel);
  quantActive = true;
  draw();
  statusEl.className = 'sheet-status';
  statusEl.textContent = `${m1Label} 기준 M-2까지의 월별 종가로 학습한 선형 추세 예측(M-1 예측)과 실제 종가(M-1 실제)를 종목명 옆에 고정했습니다. 학습용 참고 지표이며 투자 판단에 그대로 사용하지 마세요.`;
}

function renderSheet(data) {
  model = { columns: data.columns, rows: data.rows }; quantActive = false; draw();
  document.querySelector('#sheet-title').textContent = data.title;
  const source = document.querySelector('#sheet-source');
  if (data.sourceUrl) { source.hidden = false; source.href = data.sourceUrl; source.textContent = `${data.sourceType} 원문 열기 ↗`; }
  else { source.hidden = true; source.removeAttribute('href'); }
  statusEl.className = 'sheet-status'; statusEl.textContent = `${data.rows.length}행 · ${data.columns.length}열을 가져왔습니다. ${data.notice}`; workspace.hidden = false;
}

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
document.querySelector('#add-row').addEventListener('click', () => { readModel(); model.rows.push(Array(model.columns.length).fill('')); draw(); table.querySelector('tbody tr:last-child input')?.focus(); });
document.querySelector('#download-csv').addEventListener('click', () => { readModel(); const csv = [model.columns, ...model.rows].map(row => row.map(csvCell).join(',')).join('\r\n'); const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob(['\ufeff' + csv], {type:'text/csv;charset=utf-8'})); link.download = 'ai-sheet.csv'; link.click(); URL.revokeObjectURL(link.href); });
