/**
 * JSON-RPC 2.0 client for the RevitPy Live Server (WebSocket, bearer token).
 * Mirrors revitpy/live_client.py; see docs/developer/live-server.md.
 */
import { EventEmitter } from 'node:events';
import type { IncomingMessage } from 'node:http';
import WebSocket from 'ws';
import type { RawData } from 'ws';
import type { DebugStartResult, ExecutionResult, ListAnalysesResult, LiveStatus, ReloadResult } from './protocol';

/** The server answered a request with a JSON-RPC error. */
export class JsonRpcError extends Error {
  readonly code: number;
  readonly data?: unknown;
  readonly rpcMessage: string;

  constructor(code: number, message: string, data?: unknown) {
    super(`${message} (code ${code})`);
    this.name = 'JsonRpcError';
    this.code = code;
    this.data = data;
    this.rpcMessage = message;
  }
}

/** The server could not be reached, refused the handshake, or the socket closed. */
export class ConnectionError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ConnectionError';
  }
}

/** No response arrived within the request timeout. */
export class RequestTimeoutError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'RequestTimeoutError';
  }
}

export interface ConnectOptions {
  connectTimeoutMs?: number;
  requestTimeoutMs?: number;
}

interface Pending {
  resolve: (value: unknown) => void;
  reject: (error: Error) => void;
  timer: NodeJS.Timeout;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** One WebSocket connection to the Live Server. Emits `close` (code, reason) once. */
export class LiveClient extends EventEmitter {
  private nextId = 0;
  private readonly pending = new Map<number, Pending>();

  private constructor(
    private readonly socket: WebSocket,
    readonly url: string,
    private readonly requestTimeoutMs: number,
  ) {
    super();
    socket.on('message', (data: RawData) => this.handleMessage(data));
    socket.on('close', (code: number, reason: Buffer) => this.handleClose(code, reason.toString()));
  }

  static connect(url: string, token: string, options: ConnectOptions = {}): Promise<LiveClient> {
    const connectTimeoutMs = options.connectTimeoutMs ?? 30_000;
    const requestTimeoutMs = options.requestTimeoutMs ?? 330_000;

    return new Promise<LiveClient>((resolve, reject) => {
      // Node's `ws` sends no Origin header, which the Live Server requires.
      const socket = new WebSocket(url, {
        headers: { Authorization: `Bearer ${token}` },
        handshakeTimeout: connectTimeoutMs,
        maxPayload: 256 * 1024 * 1024,
      });
      let settled = false;

      const fail = (message: string): void => {
        if (settled) {
          return;
        }
        settled = true;
        socket.terminate();
        reject(new ConnectionError(message));
      };

      // Kept for the socket's lifetime so late errors never go unhandled.
      socket.on('error', (err: Error) => {
        fail(
          `Cannot reach the RevitPy Live Server at ${url} (${err.message}). ` +
            'Is Revit running with the Live Server started?',
        );
      });
      socket.on('unexpected-response', (_req: unknown, res: IncomingMessage) => {
        const status = res.statusCode ?? 0;
        if (status === 401) {
          fail(
            `RevitPy Live Server at ${url} rejected the token (HTTP 401). ` +
              'The discovery file may be stale; restart the Live Server or reconnect.',
          );
        } else {
          fail(`RevitPy Live Server at ${url} refused the connection (HTTP ${status}).`);
        }
      });
      socket.once('open', () => {
        if (settled) {
          return;
        }
        settled = true;
        resolve(new LiveClient(socket, url, requestTimeoutMs));
      });
    });
  }

  get isOpen(): boolean {
    return this.socket.readyState === WebSocket.OPEN;
  }

  call<T = unknown>(method: string, params: Record<string, unknown> = {}, timeoutMs?: number): Promise<T> {
    if (!this.isOpen) {
      return Promise.reject(new ConnectionError('Not connected to the RevitPy Live Server.'));
    }
    const id = ++this.nextId;
    const timeout = timeoutMs ?? this.requestTimeoutMs;

    return new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new RequestTimeoutError(`${method} timed out after ${Math.round(timeout / 1000)} s`));
      }, timeout);
      this.pending.set(id, { resolve: (value) => resolve(value as T), reject, timer });

      this.socket.send(JSON.stringify({ jsonrpc: '2.0', id, method, params }), (err?: Error) => {
        if (err && this.pending.delete(id)) {
          clearTimeout(timer);
          reject(new ConnectionError(`Could not send ${method}: ${err.message}`));
        }
      });
    });
  }

  status(): Promise<LiveStatus> {
    return this.call<LiveStatus>('live/status');
  }

  execute(code: string, filename?: string, cwd?: string): Promise<ExecutionResult> {
    const params: Record<string, unknown> = { code };
    if (filename !== undefined) {
      params.filename = filename;
    }
    if (cwd !== undefined) {
      params.cwd = cwd;
    }
    return this.call<ExecutionResult>('live/execute', params);
  }

  runFile(filePath: string): Promise<ExecutionResult> {
    return this.call<ExecutionResult>('live/runFile', { path: filePath });
  }

  reload(options: { modules?: string[]; paths?: string[] }): Promise<ReloadResult> {
    return this.call<ReloadResult>('live/reload', {
      modules: options.modules ?? [],
      paths: options.paths ?? [],
    });
  }

  startDebugger(port?: number): Promise<DebugStartResult> {
    return this.call<DebugStartResult>('debug/start', port === undefined ? {} : { port });
  }

  async listAnalyses(): Promise<string[]> {
    const result = await this.call<ListAnalysesResult>('bridge/listAnalyses');
    return result.analyses;
  }

  close(): Promise<void> {
    if (this.socket.readyState === WebSocket.CLOSED) {
      return Promise.resolve();
    }
    return new Promise<void>((resolve) => {
      const fallback = setTimeout(() => this.socket.terminate(), 2000);
      this.socket.once('close', () => {
        clearTimeout(fallback);
        resolve();
      });
      this.socket.close(1000, 'client closing');
    });
  }

  private handleMessage(data: RawData): void {
    let message: unknown;
    try {
      message = JSON.parse(data.toString());
    } catch {
      return;
    }
    if (!isRecord(message) || typeof message.id !== 'number') {
      return;
    }
    const pending = this.pending.get(message.id);
    if (!pending) {
      return;
    }
    this.pending.delete(message.id);
    clearTimeout(pending.timer);

    const error = message.error;
    if (error !== undefined && error !== null) {
      const details = isRecord(error) ? error : {};
      const code = typeof details.code === 'number' ? details.code : 0;
      const text = typeof details.message === 'string' ? details.message : 'Unknown error';
      pending.reject(new JsonRpcError(code, text, details.data));
    } else {
      pending.resolve(message.result);
    }
  }

  private handleClose(code: number, reason: string): void {
    const error = new ConnectionError(
      `Connection to the RevitPy Live Server closed (${code}${reason ? `: ${reason}` : ''}).`,
    );
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(error);
    }
    this.pending.clear();
    this.emit('close', code, reason);
  }
}
