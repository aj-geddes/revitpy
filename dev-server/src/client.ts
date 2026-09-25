/** JSON-RPC 2.0 client for the RevitPy Live Server (one WebSocket connection). */
import path from 'node:path';
import WebSocket from 'ws';
import type { LiveConnectionInfo } from './discovery.js';
import { LiveAuthError, LiveServerError, LiveTimeoutError, LiveUnavailableError } from './errors.js';

/** Result of `live/execute` and `live/runFile`. Script exceptions are `success: false`, not errors. */
export interface ExecResult {
  success: boolean;
  output: string;
  error: string | null;
  duration_ms: number;
}

/** Result of `live/reload`. */
export interface ReloadResult {
  reloaded: string[];
  errors: Record<string, string>;
}

/** Result of `live/status`. */
export interface LiveStatus {
  protocol: number;
  revitpy_version: string;
  python_version: string;
  revit_version: string | null;
  document: string | null;
  debug: { listening: boolean; port: number | null };
  analyses: string[];
}

export interface ClientOptions {
  /** WebSocket handshake timeout (default 10 s). */
  connectTimeoutMs?: number;
  /**
   * Per-request timeout (default 330 s). The server itself waits up to 300 s for
   * Revit's main thread (busy, or a modal dialog open) before answering.
   */
  requestTimeoutMs?: number;
}

interface Pending {
  resolve: (value: unknown) => void;
  reject: (reason: unknown) => void;
  timer: ReturnType<typeof setTimeout>;
}

const noop = (): void => undefined;

/** One authenticated connection to the Live Server. Create with {@link LiveClient.connect}. */
export class LiveClient {
  private readonly pending = new Map<number, Pending>();
  private nextId = 1;

  private constructor(
    private readonly ws: WebSocket,
    readonly info: LiveConnectionInfo,
    private readonly requestTimeoutMs: number,
  ) {
    ws.on('message', (data: WebSocket.RawData) => {
      this.onMessage(data);
    });
    ws.on('close', (code: number) => {
      const error = new LiveUnavailableError(`Connection to the Live Server closed (code ${code})`);
      for (const entry of this.pending.values()) {
        clearTimeout(entry.timer);
        entry.reject(error);
      }
      this.pending.clear();
    });
  }

  /**
   * Open a connection, authenticating with the discovery token.
   *
   * @throws LiveUnavailableError when nothing answers at `info.url`.
   * @throws LiveAuthError when the handshake is rejected (HTTP 401/403).
   */
  static connect(info: LiveConnectionInfo, options: ClientOptions = {}): Promise<LiveClient> {
    const { connectTimeoutMs = 10_000, requestTimeoutMs = 330_000 } = options;
    const { url } = info;
    return new Promise<LiveClient>((resolve, reject) => {
      const ws = new WebSocket(url, {
        headers: { Authorization: `Bearer ${info.token}` },
        handshakeTimeout: connectTimeoutMs,
        maxPayload: 256 * 1024 * 1024,
        perMessageDeflate: false,
      });
      // Always keep an 'error' listener: an unhandled 'error' event would crash the process.
      ws.on('error', noop);

      let settled = false;
      const fail = (error: Error): void => {
        if (!settled) {
          settled = true;
          reject(error);
        }
      };

      ws.once('unexpected-response', (request, response) => {
        const code = response.statusCode ?? 0;
        fail(
          code === 401 || code === 403
            ? new LiveAuthError(
                `Live Server at ${url} rejected the connection (HTTP ${code}): ` +
                  'the token in the discovery file is stale or wrong',
                code,
              )
            : new LiveUnavailableError(`Live Server at ${url} answered the handshake with HTTP ${code}`),
        );
        request.destroy();
        ws.terminate();
      });
      ws.once('error', (error: Error) => {
        fail(
          new LiveUnavailableError(
            `Cannot reach the RevitPy Live Server at ${url} (${error.message || error.name}). ` +
              'Is Revit running with the Live Server started?',
          ),
        );
      });
      ws.once('open', () => {
        if (settled) {
          ws.terminate();
          return;
        }
        settled = true;
        resolve(new LiveClient(ws, info, requestTimeoutMs));
      });
    });
  }

  /** True while the connection is usable. */
  get isOpen(): boolean {
    return this.ws.readyState === WebSocket.OPEN;
  }

  /**
   * Send one request and wait for its result.
   *
   * @throws LiveServerError for a JSON-RPC error answer.
   * @throws LiveUnavailableError when the connection is (or becomes) closed.
   * @throws LiveTimeoutError when no answer arrives in time.
   */
  call<T = unknown>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (!this.isOpen) {
      return Promise.reject(new LiveUnavailableError('Not connected to the Live Server'));
    }
    const id = this.nextId++;
    return new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => {
        if (this.pending.delete(id)) {
          const seconds = Math.round(this.requestTimeoutMs / 1000);
          reject(new LiveTimeoutError(`No answer to ${method} within ${seconds} s`));
        }
      }, this.requestTimeoutMs);
      this.pending.set(id, { resolve: resolve as (value: unknown) => void, reject, timer });
      this.ws.send(JSON.stringify({ jsonrpc: '2.0', id, method, params }), (error) => {
        if (error && this.pending.delete(id)) {
          clearTimeout(timer);
          reject(new LiveUnavailableError(`Failed to send ${method}: ${error.message}`));
        }
      });
    });
  }

  /** `live/status`. */
  status(): Promise<LiveStatus> {
    return this.call<LiveStatus>('live/status');
  }

  /** `live/execute`: run code as `__main__` in Revit. */
  execute(code: string, filename = '<live>', cwd?: string): Promise<ExecResult> {
    const params: Record<string, unknown> = { code, filename };
    if (cwd !== undefined) {
      params.cwd = cwd;
    }
    return this.call<ExecResult>('live/execute', params);
  }

  /** `live/runFile` with the absolute form of `file`. */
  runFile(file: string): Promise<ExecResult> {
    return this.call<ExecResult>('live/runFile', { path: path.resolve(file) });
  }

  /** `live/reload`: reload imported modules by name and/or source path (made absolute). */
  reload(request: { modules?: string[]; paths?: string[] }): Promise<ReloadResult> {
    return this.call<ReloadResult>('live/reload', {
      modules: request.modules ?? [],
      paths: (request.paths ?? []).map((file) => path.resolve(file)),
    });
  }

  /** Close the connection; pending requests fail with `LiveUnavailableError`. */
  close(): Promise<void> {
    if (this.ws.readyState === WebSocket.CLOSED) {
      return Promise.resolve();
    }
    return new Promise<void>((resolve) => {
      const fallback = setTimeout(() => {
        this.ws.terminate();
      }, 2000);
      this.ws.once('close', () => {
        clearTimeout(fallback);
        resolve();
      });
      this.ws.close(1000);
    });
  }

  private onMessage(data: WebSocket.RawData): void {
    let message: unknown;
    try {
      const text = Array.isArray(data)
        ? Buffer.concat(data).toString('utf8')
        : data instanceof ArrayBuffer
          ? Buffer.from(data).toString('utf8')
          : data.toString('utf8');
      message = JSON.parse(text);
    } catch {
      return;
    }
    if (typeof message !== 'object' || message === null) {
      return;
    }
    const { id, result, error } = message as { id?: unknown; result?: unknown; error?: unknown };
    if (typeof id !== 'number') {
      return;
    }
    const entry = this.pending.get(id);
    if (!entry) {
      return;
    }
    this.pending.delete(id);
    clearTimeout(entry.timer);
    if (typeof error === 'object' && error !== null) {
      const { code, message: text } = error as { code?: unknown; message?: unknown };
      entry.reject(
        new LiveServerError(typeof code === 'number' ? code : 0, typeof text === 'string' ? text : 'Unknown error'),
      );
    } else {
      entry.resolve(result);
    }
  }
}
