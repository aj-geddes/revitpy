import { promises as fs } from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ConnectionManager, type ConnectionDeps, type ConnectionState } from '../src/connection';
import { LiveServerNotRunningError, type DiscoveryInfo } from '../src/discovery';
import { ConnectionError, type LiveClient } from '../src/liveClient';
import type { LiveStatus } from '../src/protocol';
import { FakeLiveServer } from './helpers/fakeLiveServer';

async function writeDiscovery(file: string, server: FakeLiveServer, token = server.token): Promise<void> {
  await fs.writeFile(
    file,
    JSON.stringify({
      protocol: 1,
      url: server.url,
      token,
      pid: 1,
      revit_version: '2025',
      started_at: new Date().toISOString(),
    }),
  );
}

describe('ConnectionManager', () => {
  let dir: string;
  let file: string;
  const servers: FakeLiveServer[] = [];
  let manager: ConnectionManager;

  const startServer = async (token?: string) => {
    const server = await FakeLiveServer.start({ token });
    servers.push(server);
    return server;
  };

  beforeEach(async () => {
    dir = await fs.mkdtemp(path.join(os.tmpdir(), 'revitpy-conn-'));
    file = path.join(dir, 'live.json');
    manager = new ConnectionManager(() => ({ discoveryFile: file, requestTimeoutMs: 2000, connectTimeoutMs: 2000 }));
  });

  afterEach(async () => {
    await manager.disconnect();
    await Promise.all(servers.splice(0).map((server) => server.stop()));
    await fs.rm(dir, { recursive: true, force: true });
  });

  it('reports a missing discovery file as "not running"', async () => {
    await expect(manager.connect()).rejects.toBeInstanceOf(LiveServerNotRunningError);
    expect(manager.state).toBe('disconnected');
  });

  it('connects, fetches the status and emits state changes', async () => {
    const server = await startServer();
    await writeDiscovery(file, server);
    const states: ConnectionState[] = [];
    const statuses: Array<LiveStatus | undefined> = [];
    manager.on('stateChanged', (state: ConnectionState) => states.push(state));
    manager.on('statusChanged', (status: LiveStatus | undefined) => statuses.push(status));

    const client = await manager.connect();

    expect(client.url).toBe(server.url);
    expect(manager.state).toBe('connected');
    expect(manager.isConnected).toBe(true);
    expect(manager.status?.revit_version).toBe('2025');
    expect(manager.status?.document).toBe('Project1.rvt');
    expect(manager.info?.url).toBe(server.url);
    expect(states).toEqual(['connecting', 'connected']);
    expect(statuses).toEqual([manager.status]);
  });

  it('shares one connection between concurrent callers', async () => {
    const server = await startServer();
    await writeDiscovery(file, server);

    const [a, b] = await Promise.all([manager.connect(), manager.connect()]);
    expect(a).toBe(b);
    expect(await manager.connect()).toBe(a);
    expect(server.handshakes).toHaveLength(1);
  });

  it('reports a stale token', async () => {
    const server = await startServer();
    await writeDiscovery(file, server, 'old');

    const error = await manager.connect().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ConnectionError);
    expect((error as Error).message).toContain('HTTP 401');
    expect(manager.state).toBe('disconnected');
  });

  it('notices a dropped connection and reconnects on demand with the new token', async () => {
    const first = await startServer();
    await writeDiscovery(file, first);
    await manager.connect();

    const disconnected = new Promise<string>((resolve) => manager.once('disconnected', resolve));
    first.dropAllConnections();
    expect(await disconnected).toContain('closed');
    expect(manager.state).toBe('disconnected');
    expect(manager.status).toBeUndefined();

    await first.stop();
    const second = await startServer('second');
    await writeDiscovery(file, second);

    const client = await manager.ensureClient();
    expect(client.url).toBe(second.url);
    expect(manager.isConnected).toBe(true);
  });

  it('does not emit "disconnected" for a user disconnect', async () => {
    const server = await startServer();
    await writeDiscovery(file, server);
    await manager.connect();
    const spy = vi.fn();
    manager.on('disconnected', spy);

    await manager.disconnect();

    expect(spy).not.toHaveBeenCalled();
    expect(manager.state).toBe('disconnected');
    expect(manager.isConnected).toBe(false);
  });

  it('refreshStatus returns undefined while disconnected', async () => {
    expect(await manager.refreshStatus()).toBeUndefined();
  });

  it('tolerates a failing status call while connecting', async () => {
    const server = await startServer();
    server.setHandler('live/status', () => {
      throw new Error('busy');
    });
    await writeDiscovery(file, server);

    await manager.connect();

    expect(manager.state).toBe('connected');
    expect(manager.status).toBeUndefined();
  });

  it('uses the configured discovery file and request timeout', async () => {
    const info: DiscoveryInfo = { url: 'ws://x', token: 't', protocol: 1, path: 'p' };
    const deps: ConnectionDeps = {
      readDiscovery: vi.fn(async () => info),
      connect: vi.fn(async (): Promise<LiveClient> => {
        throw new ConnectionError('nope');
      }),
    };
    const custom = new ConnectionManager(() => ({ discoveryFile: 'p-file', requestTimeoutMs: 1000 }), deps);

    await expect(custom.connect()).rejects.toThrow('nope');
    expect(deps.readDiscovery).toHaveBeenCalledWith('p-file');
    expect(deps.connect).toHaveBeenCalledWith('ws://x', 't', expect.objectContaining({ requestTimeoutMs: 1000 }));
  });
});
