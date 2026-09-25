/**
 * In-process stand-in for the RevitPy Live Server: same handshake rules
 * (bearer token -> 401, browser Origin -> 403) and JSON-RPC 2.0 framing.
 */
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import type { IncomingMessage } from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { WebSocketServer } from 'ws';
import type { WebSocket } from 'ws';

export interface RecordedCall {
  method: string;
  params: Record<string, unknown>;
}

export type Handler = (params: Record<string, unknown>) => unknown;

/** Throw this from a handler to answer with a JSON-RPC error. */
export class RpcError extends Error {
  constructor(
    readonly code: number,
    message: string,
  ) {
    super(message);
  }
}

export interface FakeLiveServer {
  url: string;
  port: number;
  token: string;
  /** Discovery file describing this server (written by `writeDiscovery`). */
  discoveryFile: string;
  calls: RecordedCall[];
  /** Authorization headers of rejected handshakes. */
  rejected: (string | undefined)[];
  handlers: Map<string, Handler>;
  connections: Set<WebSocket>;
  writeDiscovery(overrides?: Record<string, unknown>): Promise<void>;
  /** Drop every client connection (simulates Revit closing). */
  dropConnections(): void;
  close(): Promise<void>;
}

export interface FakeServerOptions {
  token?: string;
  /** Directory for the discovery file (default: a new temp dir, removed on close). */
  dir?: string;
  port?: number;
}

function moduleName(file: string): string {
  return path.basename(file).replace(/\.py$/, '');
}

export async function startFakeLiveServer(options: FakeServerOptions = {}): Promise<FakeLiveServer> {
  const token = options.token ?? 'fake-token';
  const ownDir = options.dir === undefined;
  const dir = options.dir ?? (await mkdtemp(path.join(os.tmpdir(), 'revitpy-fake-live-')));
  const calls: RecordedCall[] = [];
  const rejected: (string | undefined)[] = [];
  const connections = new Set<WebSocket>();

  const handlers = new Map<string, Handler>([
    [
      'live/status',
      () => ({
        protocol: 1,
        revitpy_version: '0.0.0-fake',
        python_version: '3.12.0',
        revit_version: '2026',
        document: 'Fake.rvt',
        debug: { listening: false, port: null },
        analyses: [],
      }),
    ],
    [
      'live/reload',
      (params) => {
        const paths = Array.isArray(params.paths) ? (params.paths as string[]) : [];
        return { reloaded: paths.map(moduleName), errors: {} };
      },
    ],
    [
      'live/runFile',
      (params) => {
        if (typeof params.path !== 'string') {
          throw new RpcError(-32602, "'path' must be a string");
        }
        return { success: true, output: `ran ${moduleName(params.path)}\n`, error: null, duration_ms: 1.5 };
      },
    ],
  ]);

  const wss = new WebSocketServer({
    host: '127.0.0.1',
    port: options.port ?? 0,
    verifyClient: (info: { req: IncomingMessage }, done: (ok: boolean, code?: number) => void) => {
      const auth = info.req.headers.authorization;
      if (info.req.headers.origin !== undefined) {
        rejected.push(auth);
        done(false, 403);
      } else if (auth !== `Bearer ${token}`) {
        rejected.push(auth);
        done(false, 401);
      } else {
        done(true);
      }
    },
  });
  await new Promise<void>((resolve, reject) => {
    wss.once('listening', resolve);
    wss.once('error', reject);
  });

  wss.on('connection', (socket) => {
    connections.add(socket);
    socket.on('close', () => connections.delete(socket));
    socket.on('message', (data) => {
      const request = JSON.parse((data as Buffer).toString('utf8')) as { id: number; method: string; params?: Record<string, unknown> };
      const params = request.params ?? {};
      calls.push({ method: request.method, params });
      const handler = handlers.get(request.method);
      void (async () => {
        let reply: Record<string, unknown>;
        try {
          if (!handler) {
            throw new RpcError(-32601, `Method not found: ${request.method}`);
          }
          reply = { jsonrpc: '2.0', id: request.id, result: await handler(params) };
        } catch (error: unknown) {
          const code = error instanceof RpcError ? error.code : -32603;
          const message = error instanceof Error ? error.message : String(error);
          reply = { jsonrpc: '2.0', id: request.id, error: { code, message } };
        }
        if (socket.readyState === socket.OPEN) {
          socket.send(JSON.stringify(reply));
        }
      })();
    });
  });

  const address = wss.address();
  if (typeof address !== 'object' || address === null) {
    throw new Error('unexpected server address');
  }
  const url = `ws://127.0.0.1:${String(address.port)}`;
  const discoveryFile = path.join(dir, 'live.json');

  return {
    url,
    port: address.port,
    token,
    discoveryFile,
    calls,
    rejected,
    handlers,
    connections,
    async writeDiscovery(overrides = {}) {
      const data = { protocol: 1, url, token, pid: process.pid, revit_version: '2026', ...overrides };
      await writeFile(discoveryFile, JSON.stringify(data), 'utf8');
    },
    dropConnections() {
      for (const socket of connections) {
        socket.terminate();
      }
    },
    async close() {
      for (const socket of connections) {
        socket.terminate();
      }
      await new Promise<void>((resolve) => {
        wss.close(() => {
          resolve();
        });
      });
      if (ownDir) {
        await rm(dir, { recursive: true, force: true });
      }
    },
  };
}

/** Poll `predicate` until it is true (real timers). */
export async function waitFor(predicate: () => boolean, timeoutMs = 5000, what = 'condition'): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (!predicate()) {
    if (Date.now() > deadline) {
      throw new Error(`Timed out waiting for ${what}`);
    }
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
}

/** Collects everything written to it. */
export class Capture {
  text = '';
  isTTY = false;
  write(chunk: string): boolean {
    this.text += chunk;
    return true;
  }
}
