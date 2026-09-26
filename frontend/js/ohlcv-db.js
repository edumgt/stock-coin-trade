(() => {
  const PAGE_SIZE = 100;
  let gridApi;
  const number = value => Number(value || 0).toLocaleString('ko-KR');
  const dateText = value => value ? String(value).slice(0, 10) : '–';
  const won = value => value == null ? '–' : Math.round(Number(value)).toLocaleString('ko-KR');

  function today() {
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    return now.toISOString().slice(0, 10);
  }

  async function loadSummary() {
    const response = await apiFetch('/api/ohlcv-db/summary');
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || 'OHLCV 집계 조회 실패');
    const { totals, yearly, quality, markets, sync } = data;
    document.getElementById('ohlcv-total-tickers').textContent = `${number(totals.ticker_count)}개`;
    document.getElementById('ohlcv-total-rows').textContent = `${number(totals.ohlcv_rows)}건`;
    document.getElementById('ohlcv-average-rows').textContent = totals.ticker_count
      ? `${(Number(totals.ohlcv_rows) / Number(totals.ticker_count)).toFixed(1)}건`
      : '–';
    const firstYear = dateText(totals.first_date).slice(0, 4);
    const lastYear = dateText(totals.last_date).slice(0, 4);
    document.getElementById('ohlcv-data-year').textContent = firstYear === lastYear ? `${lastYear}년` : `${firstYear}–${lastYear}`;
    document.getElementById('ohlcv-data-range').textContent = `${dateText(totals.first_date)} ~ ${dateText(totals.last_date)}`;
    document.getElementById('ohlcv-year-summary').innerHTML = yearly.map(row => `
      <tr><td>${row.year}</td><td>${number(row.row_count)}</td><td>${number(row.ticker_count)}</td>
      <td>${Number(row.average_rows).toFixed(1)}</td><td>${dateText(row.first_date)} ~ ${dateText(row.last_date)}</td></tr>
    `).join('');
    const marketText = markets.map(row => `${row.market || '미분류'} ${number(row.ticker_count)}종목`).join(' · ');
    const syncText = sync?.last_completed_at
      ? `자동 수집 ${number(sync.success_ranges)}/${number(sync.tracked_ranges)} 구간 완료 · 최근 ${dateText(sync.last_completed_at)}`
      : '자동 수집 이력 대기 중';
    document.getElementById('ohlcv-quality-note').textContent =
      `검증 격리 ${number(quality.quarantined_rows)}건 (${number(quality.affected_tickers)}종목) · ${syncText} · ${marketText}`;
  }

  function filterParams() {
    const fields = {
      q: 'ohlcv-query', market: 'ohlcv-market', date_from: 'ohlcv-date-from', date_to: 'ohlcv-date-to',
      min_close: 'ohlcv-min-close', max_close: 'ohlcv-max-close',
      min_volume: 'ohlcv-min-volume', max_volume: 'ohlcv-max-volume',
    };
    const params = new URLSearchParams();
    Object.entries(fields).forEach(([key, id]) => {
      const value = document.getElementById(id)?.value?.trim();
      if (value) params.set(key, value);
    });
    return params;
  }

  function createDatasource() {
    return {
      async getRows(params) {
        const query = filterParams();
        query.set('offset', params.startRow);
        query.set('limit', params.endRow - params.startRow);
        const sort = params.sortModel?.[0];
        if (sort) {
          query.set('sort', sort.colId);
          query.set('order', sort.sort);
        }
        const status = document.getElementById('ohlcv-grid-status');
        status.textContent = '데이터 조회 중…';
        try {
          const response = await apiFetch(`/api/ohlcv-db/rows?${query}`);
          const data = await response.json();
          if (!response.ok) throw new Error(data.message || '상세 데이터 조회 실패');
          params.successCallback(data.rows, data.total);
          const start = data.total ? data.offset + 1 : 0;
          const end = Math.min(data.offset + data.rows.length, data.total);
          status.textContent = `${number(data.total)}건 중 ${number(start)}–${number(end)}건`;
        } catch (error) {
          params.failCallback();
          status.textContent = error.message || '조회 중 오류가 발생했습니다.';
        }
      },
    };
  }

  function refreshGrid() {
    gridApi?.setGridOption('datasource', createDatasource());
  }

  function buildGrid() {
    if (!window.agGrid) throw new Error('AG Grid Community를 불러오지 못했습니다.');
    if (agGrid.ModuleRegistry && agGrid.AllCommunityModule) {
      agGrid.ModuleRegistry.registerModules([agGrid.AllCommunityModule]);
    }
    const columns = [
      { field: 'trade_date', headerName: '거래일', width: 112, pinned: 'left' },
      { field: 'ticker_code', headerName: '종목 코드', width: 105, pinned: 'left' },
      { field: 'name', headerName: '종목명', minWidth: 145, pinned: 'left' },
      { field: 'market', headerName: '시장', width: 115 },
      { field: 'open', headerName: '시가', width: 110, type: 'numericColumn', valueFormatter: p => won(p.value) },
      { field: 'high', headerName: '고가', width: 110, type: 'numericColumn', valueFormatter: p => won(p.value) },
      { field: 'low', headerName: '저가', width: 110, type: 'numericColumn', valueFormatter: p => won(p.value) },
      { field: 'close', headerName: '종가', width: 110, type: 'numericColumn', valueFormatter: p => won(p.value) },
      { field: 'adj_close', headerName: '수정종가', width: 115, type: 'numericColumn', valueFormatter: p => won(p.value) },
      {
        field: 'change_rate', headerName: '일중 등락률', width: 120, type: 'numericColumn',
        valueFormatter: p => p.value == null ? '–' : `${Number(p.value).toFixed(2)}%`,
        cellClassRules: { 'ohlcv-positive': p => p.value > 0, 'ohlcv-negative': p => p.value < 0 },
      },
      { field: 'volume', headerName: '거래량', width: 125, type: 'numericColumn', valueFormatter: p => number(p.value) },
      { field: 'traded_value', headerName: '거래대금(원)', width: 155, type: 'numericColumn', valueFormatter: p => won(p.value) },
    ];
    gridApi = agGrid.createGrid(document.getElementById('ohlcv-grid'), {
      theme: agGrid.themeQuartz,
      columnDefs: columns,
      defaultColDef: { sortable: true, resizable: true, suppressHeaderMenuButton: true },
      rowModelType: 'infinite',
      datasource: createDatasource(),
      cacheBlockSize: PAGE_SIZE,
      maxBlocksInCache: 5,
      pagination: true,
      paginationPageSize: PAGE_SIZE,
      paginationPageSizeSelector: false,
      rowHeight: 38,
      headerHeight: 42,
      animateRows: false,
      localeText: { noRowsToShow: '검색 결과가 없습니다.', loadingOoo: '불러오는 중…' },
      getRowId: params => `${params.data.ticker_code}-${params.data.trade_date}`,
    });
  }

  function bindControls() {
    document.getElementById('ohlcv-date-to').value = today();
    document.getElementById('ohlcv-search-form').addEventListener('submit', event => {
      event.preventDefault();
      refreshGrid();
    });
    document.getElementById('ohlcv-search-reset').addEventListener('click', () => {
      document.getElementById('ohlcv-search-form').reset();
      document.getElementById('ohlcv-date-from').value = '2020-01-01';
      document.getElementById('ohlcv-date-to').value = today();
      refreshGrid();
    });
    document.getElementById('ohlcv-export-csv').addEventListener('click', () => {
      gridApi?.exportDataAsCsv({ fileName: `ohlcv-${today()}.csv` });
    });
  }

  document.addEventListener('DOMContentLoaded', async () => {
    await initPage();
    bindControls();
    try {
      buildGrid();
      await loadSummary();
    } catch (error) {
      document.getElementById('ohlcv-grid-status').textContent = error.message || 'OHLCV 화면 초기화 실패';
    }
  });
})();
