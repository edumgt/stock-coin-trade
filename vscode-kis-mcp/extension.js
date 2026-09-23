'use strict';

const vscode = require('vscode');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { McpClient } = require('./mcp-client');

const VIEW_ID = 'kisMcp.panel';
const SERVER_NAMES = { code: 'Code Assistant', trade: 'Trading (모의)' };
const SAFE_TRADE_APIS = new Set(['find_api_detail', 'find_stock_code', 'inquire_price', 'price']);

class KisMcpViewProvider {
  constructor(context) {
    this.context = context;
    this.root = null;
    this.clients = {};
    this.view = null;
    this.tools = { code: [], trade: [] };
    this.status = { code: '대기 중', trade: '대기 중' };
  }

  resolveWebviewView(view) {
    this.view = view;
    view.webview.options = {
      enableScripts: true,
      localResourceRoots: [vscode.Uri.joinPath(this.context.extensionUri, 'media')]
    };
    view.webview.html = this.html(view.webview);
    view.webview.onDidReceiveMessage(message => {
      if (message?.type === 'ready' || message?.type === 'refresh') {
        void this.refresh();
      } else if (message?.type === 'run') {
        void this.run(message);
      }
    });
    view.onDidDispose(() => { this.view = null; });
    this.sendState();
  }

  html(webview) {
    const nonce = crypto.randomBytes(16).toString('hex');
    const css = webview.asWebviewUri(vscode.Uri.joinPath(this.context.extensionUri, 'media', 'panel.css'));
    const js = webview.asWebviewUri(vscode.Uri.joinPath(this.context.extensionUri, 'media', 'panel.js'));
    return `<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource}; script-src 'nonce-${nonce}'">
<link rel="stylesheet" href="${css}"><title>KIS MCP</title></head>
<body>
  <header class="hero"><span class="eyebrow">KOREA INVESTMENT · MCP</span><h1>투자 API 작업실</h1><p>공식 KIS MCP 도구를 탐색기에서 바로 사용합니다.</p></header>
  <section class="server-card" aria-label="서버 상태">
    <div class="section-head"><strong>연결 상태</strong><button type="button" id="refresh" class="icon-button" title="서버 새로고침" aria-label="서버 새로고침">↻</button></div>
    <div class="server-row"><span class="server-name">Code Assistant</span><span id="status-code" class="status">대기 중</span></div>
    <div class="server-row"><span class="server-name">Trading <small>모의투자</small></span><span id="status-trade" class="status">대기 중</span></div>
  </section>
  <section class="workspace" aria-label="MCP 도구 실행">
    <div class="section-head"><strong>도구 실행</strong><span class="step">01 / 03</span></div>
    <div class="presets"><button type="button" id="preset-search">API 검색 예시</button><button type="button" id="preset-quote">삼성전자 시세</button></div>
    <label for="server">서버</label><select id="server"><option value="code">Code Assistant</option><option value="trade">Trading · 모의투자</option></select>
    <label for="tool">도구</label><select id="tool"><option value="">서버 연결 중…</option></select><p id="tool-help" class="hint">도구를 선택하면 설명을 볼 수 있습니다.</p>
    <label for="args">인자 <span>JSON</span></label><textarea id="args" spellcheck="false" rows="8" aria-describedby="args-help">{}</textarea>
    <p id="args-help" class="hint">Trading 도구는 모의투자 환경으로 고정됩니다.</p>
    <button type="button" id="run" class="primary">도구 실행 <span>↗</span></button>
  </section>
  <section class="result-section" aria-label="실행 결과"><div class="section-head"><strong>응답</strong><button type="button" id="copy" class="text-button" disabled>복사</button></div><div id="result" class="result empty" role="status">도구를 실행하면 결과가 여기에 표시됩니다.</div></section>
  <footer>연결: 이 작업공간의 공식 KIS MCP 서버</footer>
<script nonce="${nonce}" src="${js}"></script>
</body></html>`;
  }

  workspaceRoot() {
    for (const folder of vscode.workspace.workspaceFolders || []) {
      const script = path.join(folder.uri.fsPath, 'scripts', 'kis_mcp.py');
      if (fs.existsSync(script)) return folder.uri.fsPath;
    }
    return null;
  }

  ensureClients() {
    const root = this.workspaceRoot();
    if (!root) throw new Error('scripts/kis_mcp.py가 있는 작업공간을 열어주세요.');
    if (root !== this.root) {
      this.disposeClients();
      this.root = root;
      this.clients = { code: new McpClient(root, 'code'), trade: new McpClient(root, 'trade') };
    }
  }

  sendState() {
    void this.view?.webview.postMessage({ type: 'state', status: this.status, tools: this.tools });
  }

  async refresh() {
    try { this.ensureClients(); }
    catch (error) {
      this.status = { code: error.message, trade: error.message };
      this.sendState();
      return;
    }
    await Promise.all(['code', 'trade'].map(async kind => {
      this.status[kind] = '연결 중…';
      this.sendState();
      try {
        this.tools[kind] = (await this.clients[kind].listTools()).map(tool => ({
          name: tool.name, description: tool.description || '', inputSchema: tool.inputSchema || {}
        }));
        this.status[kind] = `${this.tools[kind].length}개 도구 연결`;
      } catch (error) {
        this.tools[kind] = [];
        this.status[kind] = `연결 실패: ${error.message}`;
      }
      this.sendState();
    }));
  }

  async run(message) {
    const { server, tool, rawArgs } = message;
    if (!Object.hasOwn(SERVER_NAMES, server) || !this.tools[server].some(item => item.name === tool)) {
      this.sendError('먼저 연결된 서버와 도구를 선택하세요.');
      return;
    }
    if (typeof rawArgs !== 'string' || rawArgs.length > 20000) {
      this.sendError('인자는 20,000자 이하의 JSON 객체여야 합니다.');
      return;
    }
    let args;
    try { args = JSON.parse(rawArgs); }
    catch { this.sendError('인자 JSON 문법을 확인하세요.'); return; }
    if (!args || Array.isArray(args) || typeof args !== 'object') {
      this.sendError('인자는 JSON 객체여야 합니다.');
      return;
    }
    if (server === 'trade') {
      const apiType = String(args.api_type || '');
      if (args.params !== undefined && (!args.params || Array.isArray(args.params) || typeof args.params !== 'object')) {
        this.sendError('Trading 도구의 params는 JSON 객체여야 합니다.');
        return;
      }
      if (args.params?.env_dv === 'real') {
        this.sendError('이 패널에서는 실전투자를 사용할 수 없습니다. env_dv를 demo로 설정하세요.');
        return;
      }
      if (apiType && !apiType.startsWith('find_')) args.params = { ...(args.params || {}), env_dv: 'demo' };
      if (!SAFE_TRADE_APIS.has(apiType)) {
        const approval = await vscode.window.showWarningMessage(
          `${SERVER_NAMES[server]}의 ${tool}/${apiType || '인증'} 호출을 모의투자 환경에서 실행할까요? 주문 도구는 계좌에 영향을 줄 수 있습니다.`,
          { modal: true }, '실행'
        );
        if (approval !== '실행') return;
      }
    }
    void this.view?.webview.postMessage({ type: 'busy', busy: true });
    try {
      const result = await this.clients[server].callTool(tool, args);
      const body = result.structuredContent || result.content || result;
      this.sendResult(body, Boolean(result.isError));
    } catch (error) {
      this.sendError(error.message);
    } finally {
      void this.view?.webview.postMessage({ type: 'busy', busy: false });
    }
  }

  sendResult(body, isError) {
    void this.view?.webview.postMessage({ type: 'result', body, isError });
  }

  sendError(message) {
    this.sendResult({ error: message }, true);
  }

  disposeClients() {
    for (const client of Object.values(this.clients)) client.dispose();
    this.clients = {};
  }

  dispose() {
    this.disposeClients();
  }
}

function activate(context) {
  const provider = new KisMcpViewProvider(context);
  context.subscriptions.push(vscode.window.registerWebviewViewProvider(VIEW_ID, provider, {
    webviewOptions: { retainContextWhenHidden: true }
  }));
  context.subscriptions.push(vscode.commands.registerCommand('kisMcp.open', async () => {
    await vscode.commands.executeCommand('workbench.view.explorer');
    await vscode.commands.executeCommand(`${VIEW_ID}.focus`);
  }));
  context.subscriptions.push(vscode.commands.registerCommand('kisMcp.refresh', () => provider.refresh()));
  context.subscriptions.push(provider);
}

module.exports = { activate };
