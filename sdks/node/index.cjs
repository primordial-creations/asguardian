'use strict';
const { spawn } = require('node:child_process');
const { isAbsolute } = require('node:path');
const { randomUUID } = require('node:crypto');
const { performance } = require('node:perf_hooks');

class ScanError extends Error {
  constructor(code, response) { super(code); this.name = 'ScanError'; this.code = code; this.response = response; }
}
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);

class Client {
  #command; #version; #timeout; #limit; #closed = false; #active = new Set();
  constructor(command, { engineVersion, timeoutMs = 120000, maxOutputBytes = 20 * 1024 * 1024 } = {}) {
    if (process.platform === 'win32') throw new TypeError('POSIX process groups required');
    if (!Array.isArray(command) || !command.length || !command.every(x => typeof x === 'string' && x && !x.includes('\0')) || !isAbsolute(command[0])) throw new TypeError('Explicit absolute executable argv required');
    if (typeof engineVersion !== 'string' || !engineVersion) throw new TypeError('Installed engine version pin required');
    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0 || timeoutMs > 2147483647) throw new TypeError('Invalid timeoutMs');
    if (!Number.isSafeInteger(maxOutputBytes) || maxOutputBytes < 1024) throw new TypeError('Invalid maxOutputBytes');
    this.#command = [...command]; this.#version = engineVersion; this.#timeout = timeoutMs; this.#limit = maxOutputBytes;
  }
  async close() {
    this.#closed = true;
    const active = [...this.#active];
    for (const operation of active) operation.stop('closed');
    await Promise.all(active.map(operation => operation.done));
  }
  #check(deadline, signal) {
    if (this.#closed) throw new ScanError('closed');
    if (signal?.aborted) throw new ScanError('cancelled');
    if (performance.now() >= deadline) throw new ScanError('timeout');
  }
  async #invoke(request, deadline, signal) {
    this.#check(deadline, signal);
    const raw = Buffer.from(JSON.stringify(request));
    if (raw.length > 65536) throw new ScanError('request_too_large');
    return new Promise((resolve, reject) => {
      let child;
      try { child = spawn(this.#command[0], this.#command.slice(1), { detached: true, stdio: ['pipe', 'pipe', 'pipe'], shell: false }); }
      catch { reject(new ScanError('engine_unavailable')); return; }
      let failure; const chunks = []; let stdout = 0; let stderr = 0;
      const kill = () => {
        if (child.pid) {
          try { process.kill(-child.pid, 'SIGKILL'); }
          catch (error) { if (error.code !== 'ESRCH') failure ??= new ScanError('process_cleanup_failed'); }
        }
      };
      let drained;
      const operation = { done: new Promise(done => { drained = done; }), stop: code => { failure ??= new ScanError(code); kill(); } };
      this.#active.add(operation);
      const abort = () => operation.stop('cancelled');
      signal?.addEventListener('abort', abort, { once: true });
      const timer = setTimeout(() => operation.stop('timeout'), Math.max(1, deadline - performance.now()));
      child.on('error', () => { failure ??= new ScanError('engine_unavailable'); });
      child.stdin.on('error', error => { if (error.code !== 'EPIPE') operation.stop('transport_error'); });
      child.stdout.on('error', () => operation.stop('transport_error'));
      child.stderr.on('error', () => operation.stop('transport_error'));
      child.stdout.on('data', chunk => { stdout += chunk.length; if (stdout > this.#limit) operation.stop('output_limit'); else chunks.push(chunk); });
      child.stderr.on('data', chunk => { stderr += chunk.length; if (stderr > this.#limit) operation.stop('output_limit'); });
      child.on('close', code => {
        clearTimeout(timer); signal?.removeEventListener('abort', abort); kill();
        this.#active.delete(operation); drained();
        try {
          if (failure) throw failure;
          this.#check(deadline, signal);
          resolve(this.#decode(Buffer.concat(chunks), code, request));
        } catch (error) { reject(error); }
      });
      // Cover cancellation between the initial check and listener installation.
      if (signal?.aborted) abort();
      child.stdin.end(raw);
    });
  }
  #decode(raw, code, request) {
    let result;
    try { result = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(raw)); }
    catch { throw new ScanError('malformed_response'); }
    if (!object(result)) throw new ScanError('malformed_response');
    if (result.protocol_version !== 1) throw new ScanError('version_mismatch');
    if (result.engine_version !== this.#version) throw new ScanError('engine_version_mismatch');
    if (result.correlation_id !== request.correlation_id || typeof result.scan_id !== 'string' || !result.scan_id ||
        typeof result.complete !== 'boolean' || typeof result.truncated !== 'boolean' ||
        !Array.isArray(result.findings) || !Array.isArray(result.errors) || ![...result.findings, ...result.errors].every(object)) throw new ScanError('malformed_response');
    if (result.state === 'error' && code === 2 && !result.complete && result.errors.length) throw new ScanError('engine_error', result);
    const valid = request.operation === 'handshake'
      ? result.state === 'ready' && code === 0 && result.complete && !result.truncated && !result.findings.length && !result.errors.length && object(result.capabilities) && Array.isArray(result.capabilities.profiles) && result.capabilities.transport === 'single-request-stdio'
      : (result.state === 'complete' && result.complete && !result.truncated && !result.errors.length && code === (result.findings.length ? 1 : 0)) ||
        (result.state === 'incomplete' && !result.complete && code === 1 && (result.truncated || result.errors.length));
    if (!valid) throw new ScanError('malformed_response');
    return result;
  }
  handshake({ signal } = {}) {
    return this.#invoke({ protocol_version: 1, operation: 'handshake', correlation_id: randomUUID() }, performance.now() + this.#timeout, signal);
  }
  async scan({ authorizedRoot, target, profile = 'quality.file-length', maxFindings = 1000, correlationId = randomUUID(), signal }) {
    const deadline = performance.now() + this.#timeout;
    if (typeof correlationId !== 'string' || !correlationId || [...correlationId].length > 256) throw new TypeError('Invalid correlationId');
    const hello = await this.#invoke({ protocol_version: 1, operation: 'handshake', correlation_id: correlationId }, deadline, signal);
    if (!hello.capabilities.profiles.includes(profile)) throw new ScanError('unsupported_operation');
    return this.#invoke({ protocol_version: 1, operation: 'scan', correlation_id: correlationId, profile, authorized_root: authorizedRoot, target, max_findings: maxFindings }, deadline, signal);
  }
}
module.exports = { Client, ScanError };
