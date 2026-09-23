'use strict';

const { spawn } = require('node:child_process');
const path = require('node:path');

class McpClient {
  constructor(root, kind) {
    this.root = root;
    this.kind = kind;
    this.nextId = 1;
    this.pending = new Map();
    this.buffer = '';
    this.stderr = '';
    this.process = null;
    this.starting = null;
  }

  async start() {
    if (this.process && this.process.exitCode === null && this.starting === null) return;
    if (this.starting) return this.starting;
    this.starting = this.connect();
    try {
      await this.starting;
    } catch (error) {
      this.dispose();
      throw error;
    } finally {
      this.starting = null;
    }
  }

  async connect() {
    const script = path.join(this.root, 'scripts', 'kis_mcp.py');
    const child = spawn('python3', [script, this.kind], {
      cwd: this.root,
      env: process.env,
      stdio: ['pipe', 'pipe', 'pipe']
    });
    this.process = child;
    this.buffer = '';
    this.stderr = '';
    child.stdout.setEncoding('utf8');
    child.stderr.setEncoding('utf8');
    child.stdout.on('data', chunk => this.receive(chunk));
    child.stderr.on('data', chunk => { this.stderr = (this.stderr + chunk).slice(-2000); });
    child.on('error', error => this.fail(error));
    child.on('exit', code => this.fail(new Error(`MCP 서버가 종료됐습니다 (${code ?? 'unknown'}). ${this.stderr.slice(-500)}`)));

    await this.request('initialize', {
      protocolVersion: '2025-03-26',
      capabilities: {},
      clientInfo: { name: 'kis-mcp-explorer', version: '0.1.0' }
    });
    this.notify('notifications/initialized', {});
  }

  receive(chunk) {
    this.buffer += chunk;
    if (this.buffer.length > 8 * 1024 * 1024) {
      this.fail(new Error('MCP 응답이 너무 큽니다.'));
      return;
    }
    let index;
    while ((index = this.buffer.indexOf('\n')) !== -1) {
      const line = this.buffer.slice(0, index).trim();
      this.buffer = this.buffer.slice(index + 1);
      if (!line) continue;
      let message;
      try { message = JSON.parse(line); }
      catch { this.fail(new Error(`MCP 응답 형식이 올바르지 않습니다: ${line.slice(0, 100)}`)); return; }
      if (message.id === undefined) continue;
      const pending = this.pending.get(message.id);
      if (!pending) continue;
      this.pending.delete(message.id);
      clearTimeout(pending.timer);
      if (message.error) pending.reject(new Error(message.error.message || 'MCP 오류'));
      else pending.resolve(message.result);
    }
  }

  request(method, params) {
    if (!this.process || this.process.exitCode !== null) return Promise.reject(new Error('MCP 서버가 실행 중이지 않습니다.'));
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`${method} 호출 시간이 초과됐습니다.`));
      }, method === 'tools/call' ? 90000 : 30000);
      this.pending.set(id, { resolve, reject, timer });
      this.process.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n', error => {
        if (error) {
          clearTimeout(timer);
          this.pending.delete(id);
          reject(error);
        }
      });
    });
  }

  notify(method, params) {
    this.process.stdin.write(JSON.stringify({ jsonrpc: '2.0', method, params }) + '\n');
  }

  async listTools() {
    await this.start();
    const response = await this.request('tools/list', {});
    return response.tools || [];
  }

  async callTool(name, args) {
    await this.start();
    return this.request('tools/call', { name, arguments: args });
  }

  fail(error) {
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(error);
    }
    this.pending.clear();
    if (this.process && this.process.exitCode === null) this.process.kill();
    this.process = null;
  }

  dispose() {
    this.fail(new Error('MCP 연결이 닫혔습니다.'));
  }
}

module.exports = { McpClient };
