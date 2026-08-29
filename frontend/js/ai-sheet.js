const form = document.querySelector('#crawl-form');
const sectorForm = document.querySelector('#sector-form');
const sectorSelect = document.querySelector('#sector-select');
const statusEl = document.querySelector('#sheet-status');
const workspace = document.querySelector('#sheet-workspace');
const table = document.querySelector('#data-sheet');
let model = { columns: [], rows: [] };

initPage();
loadSectors();

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
}
function draw() {
  table.innerHTML = `<thead><tr>${model.columns.map((column, i) => `<th><input aria-label="${i + 1}번째 열 제목" value="${esc(column)}"></th>`).join('')}</tr></thead><tbody>${model.rows.map(row => `<tr>${model.columns.map((_, i) => `<td><input value="${esc(row[i] ?? '')}"></td>`).join('')}</tr>`).join('')}</tbody>`;
}
function readModel() {
  model.columns = [...table.querySelectorAll('thead input')].map(input => input.value.trim() || '열');
  model.rows = [...table.querySelectorAll('tbody tr')].map(row => [...row.querySelectorAll('input')].map(input => input.value));
}
function csvCell(value) { return `"${String(value).replaceAll('"', '""')}"`; }

function renderSheet(data) {
  model = { columns: data.columns, rows: data.rows }; draw();
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
document.querySelector('#add-row').addEventListener('click', () => { readModel(); model.rows.push(Array(model.columns.length).fill('')); draw(); table.querySelector('tbody tr:last-child input')?.focus(); });
document.querySelector('#download-csv').addEventListener('click', () => { readModel(); const csv = [model.columns, ...model.rows].map(row => row.map(csvCell).join(',')).join('\r\n'); const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob(['\ufeff' + csv], {type:'text/csv;charset=utf-8'})); link.download = 'ai-sheet.csv'; link.click(); URL.revokeObjectURL(link.href); });
