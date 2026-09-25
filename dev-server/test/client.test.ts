import path from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { LiveClient } from '../src/client.js';
import type { LiveConnectionInfo } from '../src/discovery.js';
import { LiveAuthError, LiveServerError, LiveTimeoutError, LiveUnavailableError } from '../src/errors.js';
import { RpcError, startFakeLiveServer, waitFor } from './helpers/fakeLiveServer.js';
import type { FakeLiveServer } from './helpers/fakeLiveServer.js';

const infoFor = (server: FakeLiveServer, token = server.token): LiveConnectionInfo => ({
  url: server.url,
  token,
  protocol: 1,
  revitVersion: '2026',
  pid: null,
});

const never = (): Promise<never> => new Promise<never>(() => undefined);

describe('LiveClient', () => {
  let server: FakeLiveServer;
  let client: LiveClient | undefined;

  beforeEach(async () => {
    server = await startFakeLiveServer();
    client = undefined;
  });

  afterEach(async () => {
    await client?.close();
    await server.close();
  });

  const connect = async (options?: Parameters<typeof LiveClient.connect>[1]): Promise<LiveClient> => {
    client = await LiveClient.connect(infoFor(server), options);
    return client;
  };

  it('authenticates with the bearer token and reads the status', async () => {
    const c = await connect();
    expect(c.isOpen).toBe(true);
    expect(server.rejected).toEqual([]);
    const status = await c.status();
    expect(status.document).toBe('Fake.rvt');
    expect(server.calls).toEqual([{ method: 'live/status', params: {} }]);
  });

  it('sends absolute paths to live/reload', async () => {
    const c = await connect();
    const result = await c.reload({ paths: ['rel/helper.py'] });
    expect(result).toEqual({ reloaded: ['helper'], errors: {} });
    expect(server.calls[0]).toEqual({
      method: 'live/reload',
      params: { modules: [], paths: [path.resolve('rel/helper.py')] },
    });
  });

  it('sends an absolute path to live/runFile', async () => {
    const c = await connect();
    const result = await c.runFile('scripts/main.py');
    expect(result).toEqual({ success: true, output: 'ran main\n', error: null, duration_ms: 1.5 });
    expect(server.calls[0]?.params).toEqual({ path: path.resolve('scripts/main.py') });
  });

  it('sends live/execute parameters', async () => {
    server.handlers.set('live/execute', () => ({ success: true, output: '', error: null, duration_ms: 0 }));
    const c = await connect();
    await c.execute('print(1)');
    await c.execute('print(2)', 'x.py', '/tmp');
    expect(server.calls.map((call) => call.params)).toEqual([
      { code: 'print(1)', filename: '<live>' },
      { code: 'print(2)', filename: 'x.py', cwd: '/tmp' },
    ]);
  });

  it('rejects a wrong token with LiveAuthError (HTTP 401)', async () => {
    const error: unknown = await LiveClient.connect(infoFor(server, 'wrong')).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(LiveAuthError);
    expect((error as LiveAuthError).statusCode).toBe(401);
    expect(server.rejected).toEqual(['Bearer wrong']);
  });

  it('reports an unreachable server as LiveUnavailableError', async () => {
    const info = infoFor(server);
    await server.close();
    server = await startFakeLiveServer(); // for afterEach
    await expect(LiveClient.connect(info)).rejects.toSatisfy(
      (e) => e instanceof LiveUnavailableError && /Cannot reach/.test(e.message),
    );
  });

  it('turns JSON-RPC errors into LiveServerError', async () => {
    server.handlers.set('live/runFile', () => {
      throw new RpcError(-32602, 'File not found: x');
    });
    const c = await connect();
    const error: unknown = await c.runFile('x.py').catch((e: unknown) => e);
    expect(error).toBeInstanceOf(LiveServerError);
    expect(error).toMatchObject({ code: -32602, rpcMessage: 'File not found: x' });
    await expect(c.call('live/nope')).rejects.toMatchObject({ code: -32601 });
  });

  it('times out requests that get no answer', async () => {
    server.handlers.set('live/runFile', never);
    const c = await connect({ requestTimeoutMs: 100 });
    await expect(c.runFile('slow.py')).rejects.toBeInstanceOf(LiveTimeoutError);
    // The connection stays usable afterwards.
    await expect(c.status()).resolves.toMatchObject({ protocol: 1 });
  });

  it('fails pending requests when the connection drops', async () => {
    server.handlers.set('live/runFile', never);
    const c = await connect();
    const pending = c.runFile('main.py');
    await waitFor(() => server.calls.length === 1, 5000, 'the request to arrive');
    server.dropConnections();
    await expect(pending).rejects.toBeInstanceOf(LiveUnavailableError);
    expect(c.isOpen).toBe(false);
    await expect(c.status()).rejects.toBeInstanceOf(LiveUnavailableError);
  });

  it('matches concurrent answers to their requests by id', async () => {
    server.handlers.set(
      'test/echo',
      (params) =>
        new Promise((resolve) => {
          setTimeout(() => {
            resolve(params.value);
          }, Number(params.delay));
        }),
    );
    const c = await connect();
    const results = await Promise.all([
      c.call('test/echo', { value: 'slow', delay: 60 }),
      c.call('test/echo', { value: 'fast', delay: 0 }),
    ]);
    expect(results).toEqual(['slow', 'fast']);
  });

  it('closes cleanly, twice', async () => {
    const c = await connect();
    await c.close();
    expect(c.isOpen).toBe(false);
    await c.close();
    await waitFor(() => server.connections.size === 0, 5000, 'the server to see the close');
  });
});
