(() => {
  'use strict';
  const vscode = acquireVsCodeApi();
  const $ = id => document.getElementById(id);
  const state = { status: {}, tools: { code: [], trade: [] }, busy: false, text: '' };

  function selectedTool() {
    return state.tools[$('server').value].find(item => item.name === $('tool').value);
  }

  function updateTools(preferred) {
    const select = $('tool');
    const tools = state.tools[$('server').value] || [];
    const previous = preferred || select.value;
    select.replaceChildren();
    if (!tools.length) {
      const option = document.createElement('option');
      option.value = '';
      option.textContent = '연결된 도구 없음';
      select.append(option);
    } else {
      for (const tool of tools) {
        const option = document.createElement('option');
        option.value = tool.name;
        option.textContent = tool.name.replaceAll('_', ' ');
        select.append(option);
      }
      select.value = tools.some(item => item.name === previous) ? previous : tools[0].name;
    }
    updateHelp();
  }

  function updateHelp() {
    const tool = selectedTool();
    $('tool-help').textContent = tool
      ? tool.description.replace(/\s+/g, ' ').slice(0, 240) || '도구 설명이 없습니다.'
      : '서버를 연결하면 도구 설명을 볼 수 있습니다.';
    $('run').disabled = state.busy || !tool;
  }

  function updateStatus(kind) {
    const element = $(`status-${kind}`);
    const value = state.status[kind] || '대기 중';
    element.textContent = value;
    element.classList.toggle('connected', value.includes('개 도구 연결'));
    element.classList.toggle('failed', value.startsWith('연결 실패'));
    element.title = value;
  }

  function showResult(body, isError) {
    let value = body;
    if (Array.isArray(body) && body.length === 1 && body[0].type === 'text') {
      try { value = JSON.parse(body[0].text); }
      catch { value = body[0].text; }
    }
    state.text = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
    const result = $('result');
    result.classList.remove('empty');
    result.classList.toggle('error', isError);
    result.textContent = state.text || '(빈 응답)';
    $('copy').disabled = !state.text;
  }

  function preset(server, tool, args) {
    $('server').value = server;
    updateTools(tool);
    $('args').value = JSON.stringify(args, null, 2);
    $('args').focus();
  }

  $('server').addEventListener('change', () => { updateTools(); $('args').value = '{}'; });
  $('tool').addEventListener('change', () => { updateHelp(); $('args').value = '{}'; });
  $('refresh').addEventListener('click', () => vscode.postMessage({ type: 'refresh' }));
  $('preset-search').addEventListener('click', () => preset('code', 'search_domestic_stock_api', {
    query: '삼성전자 현재가 API', function_name: 'inquire_price'
  }));
  $('preset-quote').addEventListener('click', () => preset('trade', 'domestic_stock', {
    api_type: 'inquire_price', params: { env_dv: 'demo', fid_cond_mrkt_div_code: 'J', fid_input_iscd: '005930' }
  }));
  $('run').addEventListener('click', () => vscode.postMessage({
    type: 'run', server: $('server').value, tool: $('tool').value, rawArgs: $('args').value
  }));
  $('copy').addEventListener('click', () => {
    if (state.text) navigator.clipboard.writeText(state.text);
  });
  window.addEventListener('message', event => {
    const message = event.data;
    if (message.type === 'state') {
      state.status = message.status || {};
      state.tools = message.tools || { code: [], trade: [] };
      updateStatus('code');
      updateStatus('trade');
      updateTools();
    } else if (message.type === 'busy') {
      state.busy = Boolean(message.busy);
      $('run').textContent = state.busy ? '실행 중…' : '도구 실행 ↗';
      updateHelp();
    } else if (message.type === 'result') {
      showResult(message.body, message.isError);
    }
  });
  vscode.postMessage({ type: 'ready' });
})();
