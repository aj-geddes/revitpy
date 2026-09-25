import { afterEach, describe, expect, it } from 'vitest';
import { ConnectionError, JsonRpcError, LiveClient, RequestTimeoutError } from '../src/liveClient';
import { FakeLiveServer, HandlerError, type Handler } from './helpers/fakeLiveServer';

describe('LiveClient', () => {
  let server: FakeLiveServer | undefined;
  let client: LiveClient | undefined;

  afterEach(async () => {
    await client?.close();
    await server?.stop();
    client = undefined;
    server = undefined;
  });

  async function connect(handlers: Record<string, Handler> = {}): Promise<{ server: FakeLiveServer; client: LiveClient }> {
    server = await FakeLiveServer.start({ handlers });
    client = await LiveClient.connect(server.url, server.token, { connectTimeoutMs: 2000 });
    return { server, client };
  }

  const params = (s: FakeLiveServer) => s.requests.map((r) => [r.method, r.params]);

  it('authenticates with a bearer token and sends no Origin header', async () => {
    const { server } = await connect();
    expect(server.handshakes).toHaveLength(1);
    expect(server.handshakes[0].authorization).toBe('Bearer test-token');
    expect(server.handshakes[0].origin).toBeUndefined();
  });

  it('reports a rejected token as HTTP 401', async () => {
    server = await FakeLiveServer.start();
    const error = await LiveClient.connect(server.url, 'wrong', { connectTimeoutMs: 2000 }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ConnectionError);
    expect((error as Error).message).toContain('HTTP 401');
  });

  it('reports an unreachable server', async () => {
    const stopped = await FakeLiveServer.start();
    const url = stopped.url;
    await stopped.stop();
    const error = await LiveClient.connect(url, 'test-token', { connectTimeoutMs: 2000 }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ConnectionError);
    expect((error as Error).message).toContain('Cannot reach');
  });

  it('calls live/status', async () => {
    const { server, client } = await connect();
    const status = await client.status();
    expect(status).toEqual({
      protocol: 1,
      revitpy_version: '0.0.0-test',
      python_version: '3.12.0',
      revit_version: '2025',
      document: 'Project1.rvt',
      debug: { listening: false, port: null },
      analyses: [],
    });
    expect(params(server)).toEqual([['live/status', {}]]);
  });

  it('sends the documented params for every method', async () => {
    const { server, client } = await connect({ 'bridge/listAnalyses': () => ({ analyses: ['a', 'b'] }) });
    await client.execute('print(1)', '<selection>', '/tmp/x');
    await client.execute('x');
    await client.runFile('/scripts/a.py');
    await client.reload({ paths: ['/a.py'] });
    expect(await client.startDebugger(5679)).toEqual({ listening: true, port: 5679 });
    await client.startDebugger();
    expect(await client.listAnalyses()).toEqual(['a', 'b']);

    expect(params(server)).toEqual([
      ['live/execute', { code: 'print(1)', filename: '<selection>', cwd: '/tmp/x' }],
      ['live/execute', { code: 'x' }],
      ['live/runFile', { path: '/scripts/a.py' }],
      ['live/reload', { modules: [], paths: ['/a.py'] }],
      ['debug/start', { port: 5679 }],
      ['debug/start', {}],
      ['bridge/listAnalyses', {}],
    ]);
  });

  it('returns script failures as results, not errors', async () => {
    const failure = { success: false, output: 'partial', error: 'Traceback...\nValueError: boom', duration_ms: 3 };
    const { client } = await connect({ 'live/execute': () => failure });
    expect(await client.execute('x')).toEqual(failure);
  });

  it('turns JSON-RPC errors into JsonRpcError', async () => {
    const { client } = await connect({
      'live/runFile': () => {
        throw new HandlerError(-32602, 'Invalid params: File not found: x');
      },
    });
    const invalid = await client.runFile('x').catch((e: unknown) => e);
    expect(invalid).toBeInstanceOf(JsonRpcError);
    expect((invalid as JsonRpcError).code).toBe(-32602);
    expect((invalid as JsonRpcError).rpcMessage).toBe('Invalid params: File not found: x');

    const unknown = await client.call('nope/x').catch((e: unknown) => e);
    expect((unknown as JsonRpcError).code).toBe(-32601);
    expect((unknown as JsonRpcError).rpcMessage).toBe('Method not found: nope/x');
  });

  it('matches out-of-order responses by id', async () => {
    const { client } = await connect({
      'live/execute': async (p) => {
        await new Promise((resolve) => setTimeout(resolve, p.code === 'slow' ? 50 : 0));
        return { success: true, output: p.code, error: null, duration_ms: 0 };
      },
    });
    const [slow, fast] = await Promise.all([client.execute('slow'), client.execute('fast')]);
    expect(slow.output).toBe('slow');
    expect(fast.output).toBe('fast');
  });

  it('times out requests', async () => {
    const { client } = await connect({ 'live/execute': () => new Promise(() => undefined) });
    await expect(client.call('live/execute', { code: 'x' }, 100)).rejects.toBeInstanceOf(RequestTimeoutError);
  });

  it('fails pending calls and emits close when the server goes away', async () => {
    const { server, client } = await connect({ 'live/execute': () => new Promise(() => undefined) });
    const closed = new Promise<number>((resolve) => client.once('close', (code: number) => resolve(code)));
    const pending = client.execute('x');
    await new Promise((resolve) => setTimeout(resolve, 20)); // let the request reach the server
    server.dropAllConnections();

    await expect(pending).rejects.toBeInstanceOf(ConnectionError);
    await closed;
    expect(client.isOpen).toBe(false);
    await expect(client.status()).rejects.toBeInstanceOf(ConnectionError);
  });

  it('closes cleanly and idempotently', async () => {
    const { client } = await connect();
    await client.close();
    expect(client.isOpen).toBe(false);
    await client.close();
  });
});
