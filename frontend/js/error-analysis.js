const ea = id => document.getElementById(id);
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
let gridApi;
let allLogs = [];
let visibleRows = [];
let viewMode = 'detail';

const dateTime = value => value ? new Date(value).toLocaleString('ko-KR', {hour12:false}) : '-';
const dateOnly = value => value ? new Date(value).toLocaleDateString('sv-SE') : '-';
const statusGroup = status => Number(status) >= 500 ? '5xx' : Number(status) >= 400 ? '4xx' : '기타';
const countText = value => Number(value || 0).toLocaleString('ko-KR');

async function errorFetch(path) {
  const response = await fetch((window.APP_CONFIG?.apiBase || '') + path, {credentials:'include'});
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.message || data.error || '오류 로그를 불러오지 못했습니다.');
  return data;
}

function sourceBadge(params) {
  if (params.node.rowPinned) return `<b>${escapeHtml(params.value || '')}</b>`;
  const source = params.value === 'CLIENT' ? 'CLIENT' : 'SERVER';
  return `<span class="badge badge-${source.toLowerCase()}">${source === 'CLIENT' ? '브라우저' : '서버'}</span>`;
}

function statusBadge(params) {
  if (params.node.rowPinned) return `<b>${escapeHtml(params.value || '')}</b>`;
  const group = statusGroup(params.value);
  return `<span class="badge badge-${group === '기타' ? 'other' : group}">${escapeHtml(params.value ?? '-')}</span>`;
}

const detailColumns = [
  {headerName:'발생 시각',field:'occurredAt',pinned:'left',lockPinned:true,minWidth:168,sort:'desc',valueFormatter:p => p.node.rowPinned ? p.value : dateTime(p.value)},
  {headerName:'주체',field:'source',pinned:'left',lockPinned:true,width:100,filter:true,cellRenderer:sourceBadge},
  {headerName:'HTTP',field:'status',width:86,filter:'agNumberColumnFilter',cellRenderer:statusBadge},
  {headerName:'방식',field:'method',width:82,valueFormatter:p => p.value || '-'},
  {headerName:'API 경로',field:'path',minWidth:240,flex:1.15,tooltipField:'path',valueFormatter:p => p.value || '-'},
  {headerName:'오류 유형',field:'type',minWidth:175,filter:true,tooltipField:'type',valueFormatter:p => p.value || '-'},
  {headerName:'원인 설명',field:'reason',minWidth:280,flex:1.25,tooltipField:'reason',valueFormatter:p => p.value || '-'},
  {headerName:'메시지',field:'message',minWidth:300,flex:1.3,tooltipField:'message'},
];

const pivotColumns = [
  {headerName:'발생일',field:'date',pinned:'left',lockPinned:true,minWidth:125,sort:'desc'},
  {headerName:'상태군',field:'statusGroup',pinned:'left',lockPinned:true,width:100},
  {headerName:'서버',field:'SERVER',type:'rightAligned',width:110,valueFormatter:p => countText(p.value)},
  {headerName:'브라우저',field:'CLIENT',type:'rightAligned',width:110,valueFormatter:p => countText(p.value)},
  {headerName:'합계',field:'total',type:'rightAligned',width:110,valueFormatter:p => countText(p.value),cellStyle:{fontWeight:'800'}},
  {headerName:'비율',field:'ratio',minWidth:180,flex:1,valueFormatter:p => p.value == null ? '-' : `${Number(p.value).toFixed(1)}%`},
];

function createGrid() {
  gridApi = agGrid.createGrid(ea('grid'), {
    theme:'legacy',
    columnDefs:detailColumns,
    rowData:[],
    defaultColDef:{sortable:true,filter:true,resizable:true,floatingFilter:true,suppressHeaderMenuButton:true},
    pagination:true,paginationPageSize:25,paginationPageSizeSelector:[25,50,100,200],
    rowSelection:{mode:'singleRow',enableClickSelection:true,checkboxes:false,headerCheckbox:false},
    animateRows:false,
    tooltipShowDelay:350,
    overlayNoRowsTemplate:'<span style="padding:16px;color:#64748b">조건에 맞는 오류 로그가 없습니다.</span>',
    onRowClicked:event => { if (viewMode === 'detail' && !event.node.rowPinned && event.data?.id) openDetail(event.data.id); },
  });
}

function filterLogs() {
  const source = ea('source').value;
  const status = ea('status').value;
  return allLogs.filter(log => (!source || log.source === source) && (!status || statusGroup(log.status) === status));
}

function pivotRows(rows) {
  const groups = new Map();
  rows.forEach(log => {
    const date = dateOnly(log.occurredAt);
    const group = statusGroup(log.status);
    const key = `${date}|${group}`;
    const row = groups.get(key) || {date,statusGroup:group,SERVER:0,CLIENT:0,total:0};
    row[log.source === 'CLIENT' ? 'CLIENT' : 'SERVER'] += 1;
    row.total += 1;
    groups.set(key,row);
  });
  const total = rows.length || 1;
  return [...groups.values()].map(row => ({...row,ratio:row.total / total * 100}));
}

function pinnedSummary(rows) {
  if (viewMode === 'pivot') {
    return [{date:'전체 합계',statusGroup:'',SERVER:rows.reduce((sum,row) => sum + row.SERVER,0),CLIENT:rows.reduce((sum,row) => sum + row.CLIENT,0),total:rows.reduce((sum,row) => sum + row.total,0),ratio:100}];
  }
  return [{occurredAt:`표시 ${countText(rows.length)}건`,source:'합계',status:'',method:'',path:'',type:'',reason:'',message:''}];
}

function updateKpis(rows) {
  ea('total').textContent = countText(rows.length);
  ea('serverError').textContent = countText(rows.filter(row => Number(row.status) >= 500).length);
  ea('clientError').textContent = countText(rows.filter(row => Number(row.status) >= 400 && Number(row.status) < 500).length);
  ea('browserError').textContent = countText(rows.filter(row => row.source === 'CLIENT').length);
  ea('uniqueError').textContent = countText(new Set(rows.map(row => row.fingerprint || row.type || row.message)).size);
}

function renderGrid() {
  const filtered = filterLogs();
  visibleRows = viewMode === 'pivot' ? pivotRows(filtered) : filtered;
  gridApi.setGridOption('columnDefs', viewMode === 'pivot' ? pivotColumns : detailColumns);
  gridApi.setGridOption('rowData', visibleRows);
  gridApi.setGridOption('pinnedBottomRowData', pinnedSummary(visibleRows));
  gridApi.setGridOption('quickFilterText', ea('search').value.trim());
  updateKpis(filtered);
  ea('loadStatus').textContent = `${countText(visibleRows.length)}개 행 · 최대 ${countText(allLogs.length)}건 조회`;
}

function setView(mode) {
  viewMode = mode;
  ea('detailView').classList.toggle('active', mode === 'detail');
  ea('pivotView').classList.toggle('active', mode === 'pivot');
  ea('pivotHelp').classList.toggle('show', mode === 'pivot');
  renderGrid();
}

async function loadLogs() {
  ea('loadStatus').textContent = '진단 로그를 불러오는 중…';
  try {
    const data = await errorFetch('/api/error-analysis/logs?limit=1000');
    allLogs = data.logs || [];
    renderGrid();
  } catch (error) {
    allLogs = [];
    renderGrid();
    ea('loadStatus').textContent = error.message;
  }
}

async function openDetail(id) {
  ea('detail').innerHTML = '<dt>상태</dt><dd>상세 기록을 불러오는 중…</dd>';
  ea('modal').classList.add('open');
  try {
    const {log} = await errorFetch(`/api/error-analysis/logs/${id}`);
    const meta = log.requestMeta ? JSON.stringify(log.requestMeta,null,2) : '-';
    ea('detail').innerHTML = `<dt>발생 시각</dt><dd>${escapeHtml(dateTime(log.occurredAt))}</dd><dt>주체 · 상태</dt><dd>${escapeHtml(log.source)} · HTTP ${escapeHtml(log.status ?? '-')}</dd><dt>원인 설명</dt><dd>${escapeHtml(log.reason || '-')}</dd><dt>오류 유형 · 메시지</dt><dd><b>${escapeHtml(log.type || '-')}</b><br>${escapeHtml(log.message)}</dd><dt>요청</dt><dd>${escapeHtml(log.method || '')} ${escapeHtml(log.path || '-')}</dd><dt>요청 메타데이터</dt><dd><pre>${escapeHtml(meta)}</pre></dd><dt>스택 추적</dt><dd><pre>${escapeHtml(log.stackTrace || '서버가 처리한 HTTP 오류에는 스택이 없을 수 있습니다.')}</pre></dd>`;
  } catch (error) {
    ea('detail').innerHTML = `<dt>조회 실패</dt><dd>${escapeHtml(error.message)}</dd>`;
  }
}

function exportCsv() {
  gridApi.exportDataAsCsv({
    fileName:`error-analysis-${dateOnly(new Date())}.csv`,
    processCellCallback:params => {
      const value = params.value == null ? '' : String(params.value);
      return /^[=+\-@]/.test(value) ? `'${value}` : value;
    },
  });
}

document.addEventListener('DOMContentLoaded', async () => {
  const user = await initPage({requireAuth:true});
  if (!user) return;
  if (!window.agGrid) { ea('loadStatus').textContent = 'AG Grid Community를 불러오지 못했습니다.'; return; }
  createGrid();
  ea('search').addEventListener('input', () => gridApi.setGridOption('quickFilterText', ea('search').value.trim()));
  ea('source').addEventListener('change', renderGrid);
  ea('status').addEventListener('change', renderGrid);
  ea('detailView').addEventListener('click', () => setView('detail'));
  ea('pivotView').addEventListener('click', () => setView('pivot'));
  ea('resetColumns').addEventListener('click', () => { gridApi.resetColumnState(); gridApi.setFilterModel(null); ea('search').value=''; gridApi.setGridOption('quickFilterText',''); });
  ea('exportCsv').addEventListener('click', exportCsv);
  ea('reload').addEventListener('click', loadLogs);
  ea('close').addEventListener('click', () => ea('modal').classList.remove('open'));
  ea('modal').addEventListener('click', event => { if (event.target === ea('modal')) ea('modal').classList.remove('open'); });
  document.addEventListener('keydown', event => { if (event.key === 'Escape') ea('modal').classList.remove('open'); });
  await loadLogs();
});
