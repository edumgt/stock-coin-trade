let usageGridApi;
const usage$ = id => document.getElementById(id);
const dateText = value => value ? new Date(value).toLocaleString('ko-KR', { hour12:false }) : '-';

function createUsageGrid() {
  if (!window.agGrid) return null;
  return agGrid.createGrid(usage$('usageGrid'), {
    columnDefs: [
      { headerName:'호출 시각', field:'calledAt', minWidth:175, sort:'desc', valueFormatter:p => dateText(p.value) },
      { headerName:'제공사', field:'provider', minWidth:110, filter:true },
      { headerName:'작업', field:'operation', minWidth:150, flex:1, filter:true },
      { headerName:'HTTP', field:'method', width:82 },
      { headerName:'상태', field:'status', width:82, type:'rightAligned' },
      { headerName:'결과', field:'success', width:92, cellRenderer:p => `<b style="color:${p.value ? '#15803D' : '#E11D48'}">${p.value ? '성공' : '실패'}</b>` },
      { headerName:'소요시간', field:'durationMs', minWidth:100, type:'rightAligned', valueFormatter:p => p.value == null ? '-' : `${p.value.toLocaleString('ko-KR')} ms` },
      { headerName:'API 경로', field:'path', minWidth:270, flex:1.4, tooltipField:'path' },
      { headerName:'요약', field:'summary', minWidth:210, flex:1.2, tooltipField:'summary' },
    ],
    rowData: [], defaultColDef:{ sortable:true, filter:true, resizable:true, suppressHeaderMenuButton:true },
    pagination:true, paginationPageSize:25, paginationPageSizeSelector:[25,50,100],
    overlayNoRowsTemplate:'<span style="padding:16px;color:#64748B">아직 기록된 API 호출이 없습니다. API 테스트를 실행한 뒤 새로고침하세요.</span>',
    onRowClicked:event => loadDetail(event.data.id),
  });
}

async function loadDetail(id) {
  usage$('usageDetail').textContent = '상세 응답을 불러오는 중…';
  try {
    const response = await apiFetch(`/api/api-usage/history/${id}`); const data = await response.json();
    if (!response.ok) throw new Error(data.error || '상세 정보를 불러오지 못했습니다.');
    const row = data.log;
    usage$('usageDetail').textContent = JSON.stringify({ requestMeta: row.requestMeta ? JSON.parse(row.requestMeta) : null, response: row.responseBody ? JSON.parse(row.responseBody) : null }, null, 2);
  } catch (error) { usage$('usageDetail').textContent = `상세 조회 실패\n${error.message}`; }
}

async function loadUsage() {
  usage$('usageStatus').textContent = 'API 사용이력을 불러오는 중…';
  try {
    const response = await apiFetch('/api/api-usage/history?limit=500'); const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'API 사용이력을 불러오지 못했습니다.');
    usageGridApi.setGridOption('rowData', data.history || []);
    usage$('usageStatus').textContent = `${(data.history || []).length.toLocaleString('ko-KR')}건 · 로그인한 내 테스트 호출만 표시`;
  } catch (error) { usage$('usageStatus').textContent = error.message; }
}

(async () => { const user = await initPage({ requireAuth:true }); if (!user) return; usageGridApi = createUsageGrid(); if (!usageGridApi) { usage$('usageStatus').textContent = 'AG Grid를 불러오지 못했습니다.'; return; } usage$('usageFilter').addEventListener('input', e => usageGridApi.setGridOption('quickFilterText', e.target.value)); usage$('usageRefresh').addEventListener('click', loadUsage); await loadUsage(); })();
