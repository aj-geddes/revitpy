import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { LiveAuthError, LiveServerError, LiveUnavailableError } from '../src/errors.js';
import { LiveSession } from '../src/session.js';
import type { SessionOptions } from '../src/session.js';
import { RpcError, startFakeLiveServer, waitFor } from './helpers/fakeLiveServer.js';
import type { FakeLiveServer } from './helpers/fakeLiveServer.js';

describe('LiveSession', () => {
  let dir: string;
  let servers: FakeLiveServer[];
  let sessions: LiveSession[];

  beforeEach(async () => {
    dir = await mkdtemp(path.join(os.tmpdir(), 'revitpy-session-'));
    servers = [];
    sessions = [];
  });

  afterEach(async () => {
    await Promise.all(sessions.map((s) => s.close()));
    await Promise.all(servers.map((s) => s.close()));
    await rm(dir, { recursive: true, force: true });
  });

  const server = async (token?: string): Promise<FakeLiveServer> => {
    const s = await startFakeLiveServer({ dir, ...(token === undefined ? {} : { token }) });
    servers.push(s);
    return s;
  };
  const session = (options: SessionOptions = {}): LiveSession => {
    const s = new LiveSession({
      discoveryFile: path.join(dir, 'live.json'),
      initialDelayMs: 10,
      maxDelayMs: 50,
      ...options,
    });
    sessions.push(s);
    return s;
  };

  it('connects through the discovery file and caches the client', async () => {
    const fake = await server();
    await fake.writeDiscovery();
    const onConnect = vi.fn();
    const s = session({ onConnect });
    const [a, b] = await Promise.all([s.client(), s.client()]);
    const c = await s.client();
    expect(a).toBe(b);
    expect(a).toBe(c);
    expect(a.info.url).toBe(fake.url);
    expect(onConnect).toHaveBeenCalledTimes(1);
    expect(fake.connections.size).toBe(1);
  });

  it('waits for a server that is not running yet', async () => {
    const fake = await server();
    const onRetry = vi.fn((_error: unknown, attempt: number) => {
      if (attempt === 2) {
        void fake.writeDiscovery();
      }
    });
    const client = await session({ onRetry }).client();
    expect(client.isOpen).toBe(true);
    const [firstError] = onRetry.mock.calls[0] ?? [];
    expect(firstError).toBeInstanceOf(LiveUnavailableError);
    expect((firstError as Error).message).toMatch(/not running/);
  });

  it('retries a stale token until the discovery file is updated', async () => {
    const fake = await server();
    await fake.writeDiscovery({ token: 'stale' });
    const errors: unknown[] = [];
    const client = await session({
      onRetry: (error, attempt) => {
        errors.push(error);
        if (attempt === 2) {
          void fake.writeDiscovery();
        }
      },
    }).client();
    expect(client.info.token).toBe(fake.token);
    expect(errors[0]).toBeInstanceOf(LiveAuthError);
    expect(fake.rejected[0]).toBe('Bearer stale');
  });

  it('follows the server to a new port and token after a restart', async () => {
    const first = await server('first');
    await first.writeDiscovery();
    const s = session();
    const before = await s.client();
    await first.close();
    await waitFor(() => !before.isOpen, 5000, 'the old connection to close');

    const second = await server('second');
    await second.writeDiscovery();
    const after = await s.client();
    expect(after).not.toBe(before);
    expect(after.info).toMatchObject({ url: second.url, token: 'second' });
    await expect(s.use((c) => c.status())).resolves.toMatchObject({ document: 'Fake.rvt' });
  });

  it('does not re-send a request cut off by a disconnect, but reconnects next time', async () => {
    const fake = await server();
    await fake.writeDiscovery();
    fake.handlers.set('live/runFile', () => new Promise(() => undefined));
    const s = session();
    const pending = s.use((c) => c.runFile('/x/main.py'));
    await waitFor(() => fake.calls.length === 1, 5000, 'live/runFile');
    const before = await s.client();
    fake.dropConnections();
    await expect(pending).rejects.toBeInstanceOf(LiveUnavailableError);
    expect(fake.calls.filter((call) => call.method === 'live/runFile')).toHaveLength(1);

    const after = await s.client();
    expect(after).not.toBe(before);
    expect(after.isOpen).toBe(true);
  });

  it('keeps the connection after a JSON-RPC error', async () => {
    const fake = await server();
    await fake.writeDiscovery();
    fake.handlers.set('live/runFile', () => {
      throw new RpcError(-32602, 'File not found');
    });
    const s = session();
    const before = await s.client();
    await expect(s.use((c) => c.runFile('/missing.py'))).rejects.toBeInstanceOf(LiveServerError);
    expect(await s.client()).toBe(before);
  });

  it('close() stops a pending connection attempt', async () => {
    const onRetry = vi.fn();
    const s = session({ onRetry });
    const pending = s.client();
    await waitFor(() => onRetry.mock.calls.length > 0, 5000, 'a retry');
    await s.close();
    await expect(pending).rejects.toBeInstanceOf(Error);
    await expect(s.client()).rejects.toBeInstanceOf(LiveUnavailableError);
  });

  it('reports protocol mismatches without retrying', async () => {
    await writeFile(path.join(dir, 'live.json'), JSON.stringify({ protocol: 99, url: 'ws://127.0.0.1:1', token: 't' }));
    const onRetry = vi.fn();
    await expect(session({ onRetry }).client()).rejects.toThrow(/protocol 99/);
    expect(onRetry).not.toHaveBeenCalled();
  });
});
