let kisHistoryGrid;
let kisHistoryRows = [];
const kh = id => document.getElementById(id);
const khDate = value => value ? new Date(value).toLocaleString('ko-KR', { hour12:false }) : '-';

function resultBadge(value) {
  const color = value ? '#15803D' : '#E11D48';
  return `<b style="color:${color}">${value ? '성공' : '실패'}</b>`;
}

/* ── 컬럼별 검색(플로팅 필터) ──────────────────────────────────────────────────
   헤더 아래 칸에 컬럼 타입에 맞는 필터가 붙는다: 호출 시각=날짜(같음·이전·이후·범위), 시도·HTTP·소요시간=숫자(같음·초과·미만·범위),
   결과=성공/실패 텍스트, 나머지=텍스트 부분 일치. 필터 상태는 sessionStorage 에 남겨 새로고침 뒤에도 유지한다. */
const KH_FILTER_KEY = 'kisApiHistory.filters.v1';
const khText = { filter:'agTextColumnFilter', floatingFilter:true, filterParams:{ buttons:['clear'], debounceMs:200, trimInput:true, caseSensitive:false } };
const khNumber = { filter:'agNumberColumnFilter', floatingFilter:true, filterParams:{ buttons:['clear'], debounceMs:200 } };
const khDateFilter = {
  filter:'agDateColumnFilter', floatingFilter:true,
  filterParams:{
    buttons:['clear'], debounceMs:200, browserDatePicker:true, minValidYear:2020, maxValidYear:2100,
    // 셀 값은 ISO 문자열이므로 날짜(시각 제외)로 바꿔 필터의 자정 기준 날짜와 비교한다.
    comparator:(filterDate, cellValue) => {
      if (!cellValue) return -1;
      const cell = new Date(cellValue); if (Number.isNaN(cell.valueOf())) return -1;
      const day = new Date(cell.getFullYear(), cell.getMonth(), cell.getDate()).valueOf();
      const target = filterDate.valueOf();
      return day === target ? 0 : day < target ? -1 : 1;
    },
  },
};

function createGrid() {
  return agGrid.createGrid(kh('grid'), {
    columnDefs: [
      { headerName:'호출 시각', field:'calledAt', minWidth:190, sort:'desc', valueFormatter:p => khDate(p.value), ...khDateFilter },
      { headerName:'계층', field:'layer', minWidth:130, ...khText },
      { headerName:'TR ID', field:'trId', minWidth:135, valueFormatter:p => p.value || '-', ...khText },
      { headerName:'시도', field:'attempt', width:92, type:'rightAligned', valueFormatter:p => p.value || '-', ...khNumber },
      { headerName:'작업', field:'operation', minWidth:175, flex:1, tooltipField:'operation', ...khText },
      { headerName:'방식', field:'method', width:96, ...khText },
      { headerName:'HTTP', field:'status', width:100, type:'rightAligned', ...khNumber },
      { headerName:'결과', field:'success', width:100, cellRenderer:p => resultBadge(p.value), filterValueGetter:p => (p.data?.success ? '성공' : '실패'), ...khText },
      { headerName:'소요시간', field:'durationMs', minWidth:120, type:'rightAligned', valueFormatter:p => p.value == null ? '-' : `${Number(p.value).toLocaleString()} ms`, ...khNumber },
      { headerName:'API 경로', field:'path', minWidth:260, flex:1.35, tooltipField:'path', ...khText },
      { headerName:'요약·오류', field:'summary', minWidth:230, flex:1.2, tooltipField:'summary', ...khText },
    ],
    rowData: [],
    defaultColDef:{ sortable:true, filter:true, floatingFilter:true, resizable:true, suppressHeaderMenuButton:true },
    onFilterChanged:() => { updateStatus(); saveFilters(); },
    onFirstDataRendered:() => restoreFilters(),
    pagination:true, paginationPageSize:25, paginationPageSizeSelector:[25,50,100],
    rowSelection:{ mode:'singleRow', enableClickSelection:true, checkboxes:false, headerCheckbox:false },
    overlayNoRowsTemplate:'<span style="padding:16px;color:#64748B">아직 KIS API 호출 기록이 없습니다.</span>',
    onRowClicked:event => loadDetail(event.data.id),
  });
}

function visibleRowCount() {
  let count = 0;
  kisHistoryGrid.forEachNodeAfterFilter(() => { count += 1; });
  return count;
}

function updateStatus() {
  if (!kisHistoryGrid) return;
  const shown = visibleRowCount();
  const total = kisHistoryRows.length;
  const filtered = shown !== total || Boolean(kh('filter').value) || Object.keys(kisHistoryGrid.getFilterModel() || {}).length > 0;
  kh('status').textContent = `${shown.toLocaleString()}건 표시${filtered ? ` / 전체 ${total.toLocaleString()}건` : ''} · 로그인한 내 호출만 조회`;
}

function saveFilters() {
  if (!kisHistoryGrid) return;
  try {
    sessionStorage.setItem(KH_FILTER_KEY, JSON.stringify({
      quick: kh('filter').value, layer: kh('layer').value, result: kh('result').value, columns: kisHistoryGrid.getFilterModel() || {},
    }));
  } catch {}
}

let khRestored = false;
function restoreFilters() {
  if (khRestored || !kisHistoryGrid) return;
  khRestored = true;
  try {
    const saved = JSON.parse(sessionStorage.getItem(KH_FILTER_KEY) || 'null');
    if (!saved) return;
    kh('filter').value = saved.quick || '';
    kh('layer').value = saved.layer || '';
    kh('result').value = saved.result || '';
    if (saved.columns && Object.keys(saved.columns).length) kisHistoryGrid.setFilterModel(saved.columns);
    applyFilters();
  } catch {}
}

function resetFilters() {
  kh('filter').value = ''; kh('layer').value = ''; kh('result').value = '';
  kisHistoryGrid.setFilterModel(null);
  try { sessionStorage.removeItem(KH_FILTER_KEY); } catch {}
  applyFilters();
}

function applyFilters() {
  const layer = kh('layer').value;
  const result = kh('result').value;
  const rows = kisHistoryRows.filter(row => (!layer || row.layer === layer) && (!result || row.success === (result === 'success')));
  kisHistoryGrid.setGridOption('rowData', rows);
  kisHistoryGrid.setGridOption('quickFilterText', kh('filter').value);
  updateStatus();
  saveFilters();
}

async function loadDetail(id) {
  kh('detail').textContent = '상세 기록을 불러오는 중…';
  try {
    const response = await apiFetch(`/api/api-usage/history/${id}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || '상세 기록을 불러오지 못했습니다.');
    const row = data.log;
    let requestMeta = row.requestMeta;
    let responseBody = row.responseBody;
    try { requestMeta = requestMeta ? JSON.parse(requestMeta) : null; } catch {}
    try { responseBody = responseBody ? JSON.parse(responseBody) : null; } catch {}
    kh('detail').textContent = JSON.stringify({
      calledAt: row.calledAt, layer: row.layer, operation: row.operation,
      method: row.method, path: row.path, httpStatus: row.status,
      success: row.success, durationMs: row.durationMs,
      request: requestMeta, response: responseBody,
    }, null, 2);
  } catch (error) {
    kh('detail').textContent = `상세 조회 실패\n${error.message}`;
  }
}

async function loadHistory() {
  kh('status').textContent = 'KIS 호출 이력을 불러오는 중…';
  try {
    const response = await apiFetch('/api/api-usage/kis-history?limit=1000');
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'KIS 호출 이력을 불러오지 못했습니다.');
    kisHistoryRows = data.history || [];
    const summary = data.summary || {};
    kh('total').textContent = Number(summary.total || 0).toLocaleString();
    kh('outbound').textContent = Number(summary.outbound || 0).toLocaleString();
    kh('success').textContent = Number(summary.success || 0).toLocaleString();
    kh('failure').textContent = Number(summary.failure || 0).toLocaleString();
    kh('average').textContent = summary.averageMs == null ? '-' : `${Number(summary.averageMs).toLocaleString()} ms`;
    applyFilters();
  } catch (error) {
    kh('status').textContent = error.message;
  }
}

(async () => {
  const user = await initPage({ requireAuth:true });
  if (!user) return;
  if (!window.agGrid) { kh('status').textContent = 'Grid 라이브러리를 불러오지 못했습니다.'; return; }
  kisHistoryGrid = createGrid();
  kh('filter').addEventListener('input', applyFilters);
  kh('layer').addEventListener('change', applyFilters);
  kh('result').addEventListener('change', applyFilters);
  kh('reset').addEventListener('click', resetFilters);
  kh('refresh').addEventListener('click', loadHistory);
  await loadHistory();
})();
