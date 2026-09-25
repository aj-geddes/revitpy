/**
 * In-process stand-in for the RevitPy Live Server: same handshake rules
 * (bearer token required, browser Origin rejected) and JSON-RPC framing.
 */
import type { IncomingMessage } from 'node:http';
import type { AddressInfo } from 'node:net';
import { WebSocket, WebSocketServer, type RawData } from 'ws';

export type Handler = (
  params: Record<string, unknown>,
  context: { socket: WebSocket },
) => unknown | Promise<unknown>;

export class HandlerError extends Error {
  constructor(
    readonly code: number,
    message: string,
  ) {
    super(message);
    this.name = 'HandlerError';
  }
}

export interface ReceivedRequest {
  method: string;
  params: Record<string, unknown>;
  headers: IncomingMessage['headers'];
}

function defaultHandlers(): Record<string, Handler> {
  const ok = () => ({ success: true, output: '', error: null, duration_ms: 1 });
  return {
    'live/status': () => ({
      protocol: 1,
      revitpy_version: '0.0.0-test',
      python_version: '3.12.0',
      revit_version: '2025',
      document: 'Project1.rvt',
      debug: { listening: false, port: null },
      analyses: [],
    }),
    'live/execute': ok,
    'live/runFile': ok,
    'live/reload': () => ({ reloaded: [], errors: {} }),
    'debug/start': (params) => ({ listening: true, port: typeof params.port === 'number' ? params.port : 5678 }),
    'bridge/listAnalyses': () => ({ analyses: [] }),
  };
}

export class FakeLiveServer {
  readonly requests: ReceivedRequest[] = [];
  handlers: Record<string, Handler>;
  private readonly sockets = new Set<WebSocket>();

  private constructor(
    private readonly wss: WebSocketServer,
    readonly token: string,
    handlers: Record<string, Handler>,
    /** Headers of every handshake attempt, accepted or not. */
    readonly handshakes: IncomingMessage['headers'][],
  ) {
    this.handlers = { ...defaultHandlers(), ...handlers };
    wss.on('connection', (socket: WebSocket, req: IncomingMessage) => {
      this.sockets.add(socket);
      socket.on('close', () => this.sockets.delete(socket));
      socket.on('message', (data: RawData) => void this.handle(socket, req, data));
    });
  }

  static async start(options: { token?: string; handlers?: Record<string, Handler> } = {}): Promise<FakeLiveServer> {
    const token = options.token ?? 'test-token';
    const handshakes: IncomingMessage['headers'][] = [];
    const wss = new WebSocketServer({
      host: '127.0.0.1',
      port: 0,
      verifyClient: (info, callback) => {
        handshakes.push(info.req.headers);
        if (info.req.headers.origin) {
          callback(false, 403, 'Forbidden');
        } else if (info.req.headers.authorization !== `Bearer ${token}`) {
          callback(false, 401, 'Unauthorized');
        } else {
          callback(true);
        }
      },
    });
    await new Promise<void>((resolve, reject) => {
      wss.once('listening', resolve);
      wss.once('error', reject);
    });
    return new FakeLiveServer(wss, token, options.handlers ?? {}, handshakes);
  }

  get port(): number {
    return (this.wss.address() as AddressInfo).port;
  }

  get url(): string {
    return `ws://127.0.0.1:${this.port}`;
  }

  get connectionCount(): number {
    return this.sockets.size;
  }

  setHandler(method: string, handler: Handler): void {
    this.handlers[method] = handler;
  }

  /** Simulate Revit (or the Live Server) going away. */
  dropAllConnections(): void {
    for (const socket of this.sockets) {
      socket.terminate();
    }
  }

  async stop(): Promise<void> {
    this.dropAllConnections();
    await new Promise<void>((resolve) => this.wss.close(() => resolve()));
  }

  private async handle(socket: WebSocket, req: IncomingMessage, data: RawData): Promise<void> {
    let request: { id?: unknown; method?: unknown; params?: unknown };
    try {
      request = JSON.parse(data.toString()) as typeof request;
    } catch {
      return;
    }
    const method = String(request.method);
    const params =
      typeof request.params === 'object' && request.params !== null
        ? (request.params as Record<string, unknown>)
        : {};
    this.requests.push({ method, params, headers: req.headers });

    const reply = (body: Record<string, unknown>): void => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ jsonrpc: '2.0', id: request.id, ...body }));
      }
    };
    const handler = this.handlers[method];
    if (!handler) {
      reply({ error: { code: -32601, message: `Method not found: ${method}` } });
      return;
    }
    try {
      reply({ result: await handler(params, { socket }) });
    } catch (error) {
      if (error instanceof HandlerError) {
        reply({ error: { code: error.code, message: error.message } });
      } else {
        reply({ error: { code: -32603, message: error instanceof Error ? error.message : String(error) } });
      }
    }
  }
}
