import { mkdtemp, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { LiveServerError } from '../src/errors.js';
import { DevLoop } from '../src/loop.js';
import type { Reporter } from '../src/loop.js';
import { LiveSession } from '../src/session.js';
import { RpcError, startFakeLiveServer, waitFor } from './helpers/fakeLiveServer.js';
import type { FakeLiveServer } from './helpers/fakeLiveServer.js';

function recordingReporter() {
  return {
    changed: vi.fn<Reporter['changed']>(),
    reloaded: vi.fn<Reporter['reloaded']>(),
    ran: vi.fn<Reporter['ran']>(),
    skipped: vi.fn<Reporter['skipped']>(),
    failed: vi.fn<Reporter['failed']>(),
  };
}

describe('DevLoop', () => {
  let dir: string;
  let server: FakeLiveServer;
  let session: LiveSession;
  let helper: string;
  let entry: string;

  beforeEach(async () => {
    dir = await mkdtemp(path.join(os.tmpdir(), 'revitpy-loop-'));
    server = await startFakeLiveServer({ dir });
    await server.writeDiscovery();
    session = new LiveSession({ discoveryFile: server.discoveryFile, initialDelayMs: 10, maxDelayMs: 50 });
    helper = path.join(dir, 'helper.py');
    entry = path.join(dir, 'main.py');
  });

  afterEach(async () => {
    await session.close();
    await server.close();
    await rm(dir, { recursive: true, force: true });
  });

  it('reloads the changed files, then runs the entry script', async () => {
    const reporter = recordingReporter();
    const loop = new DevLoop({ session, entry, reporter });
    const result = await loop.runCycle([helper]);

    expect(server.calls).toEqual([
      { method: 'live/reload', params: { modules: [], paths: [helper] } },
      { method: 'live/runFile', params: { path: entry } },
    ]);
    expect(result.reload).toEqual({ reloaded: ['helper'], errors: {} });
    expect(result.run).toMatchObject({ success: true, output: 'ran main\n' });
    expect(result.error).toBeUndefined();
    expect(reporter.changed).toHaveBeenCalledWith([helper]);
    expect(reporter.reloaded).toHaveBeenCalledTimes(1);
    expect(reporter.ran).toHaveBeenCalledWith(entry, result.run, expect.any(Number));
    expect(reporter.failed).not.toHaveBeenCalled();
    expect(loop.cycles).toEqual([result]);
  });

  it('only reloads without an entry script', async () => {
    const reporter = recordingReporter();
    await new DevLoop({ session, reporter }).runCycle([helper]);
    expect(server.calls.map((call) => call.method)).toEqual(['live/reload']);
    expect(reporter.ran).not.toHaveBeenCalled();
  });

  it('skips the run when the reload failed', async () => {
    server.handlers.set('live/reload', () => ({ reloaded: [], errors: { helper: 'SyntaxError: bad' } }));
    const reporter = recordingReporter();
    const result = await new DevLoop({ session, entry, reporter }).runCycle([helper]);
    expect(server.calls.map((call) => call.method)).toEqual(['live/reload']);
    expect(result.run).toBeUndefined();
    expect(reporter.skipped).toHaveBeenCalledWith(entry, expect.stringContaining('helper'));
  });

  it('reports JSON-RPC errors without throwing', async () => {
    server.handlers.set('live/runFile', () => {
      throw new RpcError(-32602, 'File not found');
    });
    const reporter = recordingReporter();
    const result = await new DevLoop({ session, entry, reporter }).runCycle([helper]);
    expect(result.error).toBeInstanceOf(LiveServerError);
    expect(reporter.failed).toHaveBeenCalledTimes(1);
  });

  it('merges changes made during a cycle into one follow-up cycle', async () => {
    let release = (): void => undefined;
    let first = true;
    server.handlers.set('live/reload', (params) => {
      const reply = { reloaded: [], errors: {}, paths: params.paths };
      if (!first) {
        return reply;
      }
      first = false;
      return new Promise((resolve) => {
        release = () => {
          resolve(reply);
        };
      });
    });
    const loop = new DevLoop({ session, reporter: recordingReporter() });
    loop.enqueue(['/p/a.py']);
    await waitFor(() => server.calls.length === 1, 5000, 'the first reload');
    loop.enqueue(['/p/b.py']);
    loop.enqueue(['/p/c.py']);
    loop.enqueue(['/p/b.py']);
    release();
    await loop.idle();

    expect(loop.cycles.map((cycle) => cycle.paths.map((p) => path.basename(p)))).toEqual([['a.py'], ['b.py', 'c.py']]);
    expect(server.calls.filter((call) => call.method === 'live/reload')).toHaveLength(2);
    await expect(loop.idle()).resolves.toBeUndefined();
  });

  it('records an error when the session is closed', async () => {
    await session.close();
    const reporter = recordingReporter();
    const result = await new DevLoop({ session, entry, reporter }).runCycle([helper]);
    expect(result.error).toBeInstanceOf(Error);
    expect(server.calls).toEqual([]);
  });
});
