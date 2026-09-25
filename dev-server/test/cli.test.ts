import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { main, VERSION } from '../src/cli.js';
import { Capture, startFakeLiveServer, waitFor } from './helpers/fakeLiveServer.js';
import type { FakeLiveServer } from './helpers/fakeLiveServer.js';

const settle = (ms = 150): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));

describe('revitpy-dev-server CLI', () => {
  let dir: string;
  let server: FakeLiveServer;
  let stdout: Capture;
  let stderr: Capture;
  let stops: AbortController[];

  beforeEach(async () => {
    dir = await mkdtemp(path.join(os.tmpdir(), 'revitpy-cli-'));
    server = await startFakeLiveServer({ dir });
    await server.writeDiscovery();
    await writeFile(path.join(dir, 'helper.py'), 'VALUE = 1\n');
    await writeFile(path.join(dir, 'main.py'), 'import helper\nprint(helper.VALUE)\n');
    stdout = new Capture();
    stderr = new Capture();
    stops = [];
  });

  afterEach(async () => {
    for (const stop of stops) {
      stop.abort();
    }
    await server.close();
    await rm(dir, { recursive: true, force: true });
  });

  const run = (args: string[], signal?: AbortSignal): Promise<number> =>
    main(['node', 'revitpy-dev-server', ...args], {
      stdout,
      stderr,
      env: { NO_COLOR: '1' },
      cwd: dir,
      ...(signal ? { signal } : {}),
    });

  const startWatch = (args: string[]): { stop: AbortController; done: Promise<number> } => {
    const stop = new AbortController();
    stops.push(stop);
    return { stop, done: run(['watch', ...args], stop.signal) };
  };

  const calls = (method: string) => server.calls.filter((call) => call.method === method);

  it('prints its version', async () => {
    expect(await run(['--version'])).toBe(0);
    expect(stdout.text.trim()).toBe(VERSION);
    expect(VERSION).toMatch(/^\d+\.\d+\.\d+/);
  });

  describe('status', () => {
    it('prints the session status', async () => {
      expect(await run(['--discovery', server.discoveryFile, 'status'])).toBe(0);
      expect(stdout.text).toContain(server.url);
      expect(stdout.text).toMatch(/Document\s+Fake\.rvt/);
    });

    it('uses REVITPY_LIVE_DISCOVERY', async () => {
      const code = await main(['node', 'x', 'status'], {
        stdout,
        stderr,
        env: { REVITPY_LIVE_DISCOVERY: server.discoveryFile },
        cwd: dir,
      });
      expect(code).toBe(0);
    });

    it('fails fast when the server is not running', async () => {
      expect(await run(['--discovery', 'missing.json', 'status'])).toBe(1);
      expect(stderr.text).toMatch(/not running/);
    });
  });

  describe('run', () => {
    it('prints the script output', async () => {
      expect(await run(['--discovery', server.discoveryFile, 'run', 'main.py'])).toBe(0);
      expect(calls('live/runFile')[0]?.params).toEqual({ path: path.join(dir, 'main.py') });
      expect(stdout.text).toMatch(/run {5}main\.py ok in \d+ ms \(Revit 2 ms\)/);
      expect(stdout.text).toContain('  | ran main');
    });

    it('prints the traceback and exits 1 when the script fails', async () => {
      server.handlers.set('live/runFile', () => ({
        success: false,
        output: 'partial\n',
        error: 'Traceback (most recent call last):\nZeroDivisionError: division by zero\n',
        duration_ms: 2,
      }));
      expect(await run(['--discovery', server.discoveryFile, 'run', 'main.py'])).toBe(1);
      expect(stdout.text).toContain('FAILED');
      expect(stdout.text).toContain('  | partial');
      expect(stdout.text).toContain('  ZeroDivisionError: division by zero');
    });

    it('exits 2 for a missing file', async () => {
      expect(await run(['--discovery', server.discoveryFile, 'run', 'missing.py'])).toBe(2);
      expect(stderr.text).toMatch(/does not exist/);
      expect(server.calls).toEqual([]);
    });
  });

  describe('watch argument checks', () => {
    it.each([
      [[], /--reload-only/],
      [['--run', 'main.py', '--reload-only'], /--reload-only/],
      [['--run', 'missing.py'], /existing \.py file/],
      [['--run', 'helper.txt'], /existing \.py file/],
      [['--reload-only', '--debounce', 'abc'], /--debounce/],
      [['--reload-only', '--debounce', '-5'], /--debounce/],
      [['nope', '--reload-only'], /does not exist/],
    ])('watch %j exits 2', async (args, message) => {
      expect(await run(['watch', ...args])).toBe(2);
      expect(stderr.text).toMatch(message);
    });
  });

  describe('watch', () => {
    it('reloads changed files and re-runs the entry script', async () => {
      const { stop, done } = startWatch(['--discovery', server.discoveryFile, '--run', 'main.py', '--debounce', '50']);
      await waitFor(() => stdout.text.includes('connected'), 5000, 'connection');
      expect(stdout.text).toContain('Watching . for .py changes; running main.py after each reload');
      await settle();

      const helper = path.join(dir, 'helper.py');
      await writeFile(helper, 'VALUE = 2\n');
      await waitFor(() => calls('live/runFile').length === 1, 5000, 'the first run');
      expect(calls('live/reload')[0]?.params).toEqual({ modules: [], paths: [helper] });
      expect(calls('live/runFile')[0]?.params).toEqual({ path: path.join(dir, 'main.py') });
      expect(server.calls.map((call) => call.method)).toEqual(['live/reload', 'live/runFile']);
      expect(stdout.text).toMatch(/changed helper\.py/);
      expect(stdout.text).toMatch(/reload {2}1 module \(helper\)/);
      expect(stdout.text).toContain('  | ran main');

      // A burst of saves is debounced into one cycle.
      const other = path.join(dir, 'other.py');
      await writeFile(helper, 'VALUE = 3\n');
      await writeFile(helper, 'VALUE = 4\n');
      await writeFile(other, 'X = 1\n');
      await writeFile(helper, 'VALUE = 5\n');
      await waitFor(() => calls('live/runFile').length === 2, 5000, 'the second run');
      await settle(300);
      expect(calls('live/reload')).toHaveLength(2);
      expect(new Set(calls('live/reload')[1]?.params.paths as string[])).toEqual(new Set([helper, other]));

      stop.abort();
      expect(await done).toBe(0);
      expect(stdout.text).toContain('Stopped.');
      expect(stderr.text).toBe('');
    });

    it('--reload-only never runs anything', async () => {
      const { stop, done } = startWatch(['--discovery', server.discoveryFile, '--reload-only', '--debounce', '20']);
      await waitFor(() => stdout.text.includes('connected'), 5000, 'connection');
      await settle();
      await writeFile(path.join(dir, 'helper.py'), 'VALUE = 2\n');
      await waitFor(() => calls('live/reload').length === 1, 5000, 'the reload');
      await settle(200);
      expect(calls('live/runFile')).toHaveLength(0);
      stop.abort();
      expect(await done).toBe(0);
    });

    it('waits for a Live Server that is not running yet, and survives a restart', async () => {
      const discovery = path.join(dir, 'later', 'live.json');
      await mkdir(path.dirname(discovery));
      const { stop, done } = startWatch(['--discovery', discovery, '--run', 'main.py', '--debounce', '20']);
      await waitFor(() => stdout.text.includes('waiting'), 5000, 'the waiting message');
      expect(stdout.text).toMatch(/not running/);

      // Revit starts.
      const first = await startFakeLiveServer({ dir: path.dirname(discovery) });
      try {
        await first.writeDiscovery();
        await waitFor(() => stdout.text.includes('connected'), 10_000, 'connection');
        await settle();
        await writeFile(path.join(dir, 'helper.py'), 'VALUE = 2\n');
        await waitFor(() => first.calls.some((call) => call.method === 'live/runFile'), 5000, 'a run');
      } finally {
        await first.close(); // Revit exits (the fake leaves a stale discovery file behind)
      }

      // A save while Revit is down is reported and does not kill the watcher. (Wait first:
      // chokidar coalesces changes to one file less than ~50 ms apart into one event.)
      await settle();
      await writeFile(path.join(dir, 'helper.py'), 'VALUE = 3\n');
      await waitFor(() => /waiting .*Cannot reach/.test(stdout.text), 10_000, 'the reconnect attempt');

      // Revit comes back on a new port with a new token; the queued change is delivered.
      const second = await startFakeLiveServer({ dir: path.dirname(discovery), token: 'second' });
      try {
        await second.writeDiscovery();
        await waitFor(() => second.calls.some((call) => call.method === 'live/runFile'), 10_000, 'the run after restart');
        expect(second.calls[0]?.method).toBe('live/reload');
      } finally {
        stop.abort();
        expect(await done).toBe(0);
        await second.close();
      }
    });
  });
});
