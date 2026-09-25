/**
 * End-to-end against the REAL Python Live Server (revitpy.revit.live), started
 * outside Revit by test/fixtures/real_live_server.py with a fake dispatcher.
 *
 * Needs a Python with revitpy installed: $REVITPY_PYTHON, else `python3`
 * (`python` on Windows). Skipped with a message when that is not available,
 * unless REVITPY_REQUIRE_REAL_SERVER=1 (set in CI) makes that an error.
 */
import { spawn, spawnSync } from 'node:child_process';
import type { ChildProcess } from 'node:child_process';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { main } from '../src/cli.js';
import { LiveClient } from '../src/client.js';
import { readDiscovery } from '../src/discovery.js';
import { Capture, waitFor } from './helpers/fakeLiveServer.js';

const python = process.env.REVITPY_PYTHON ?? (process.platform === 'win32' ? 'python' : 'python3');
const fixture = fileURLToPath(new URL('./fixtures/real_live_server.py', import.meta.url));

function probe(): string | undefined {
  const result = spawnSync(python, ['-c', 'import revitpy.revit.live'], { encoding: 'utf8' });
  if (result.error) {
    return `${python} not found (${result.error.message})`;
  }
  if (result.status !== 0) {
    return `revitpy is not importable with ${python}: ${result.stderr.trim().split('\n').pop() ?? ''}`;
  }
  return undefined;
}

const skipReason = probe();
if (skipReason !== undefined && process.env.REVITPY_REQUIRE_REAL_SERVER === '1') {
  // CI sets this so a broken Python setup fails loudly instead of skipping.
  throw new Error(`REVITPY_REQUIRE_REAL_SERVER=1 but ${skipReason}`);
}
const suiteName =
  skipReason === undefined
    ? 'real RevitPy Live Server'
    : `real RevitPy Live Server (SKIPPED: ${skipReason}; set REVITPY_PYTHON to a Python with revitpy installed)`;

describe.skipIf(skipReason !== undefined)(suiteName, () => {
  let dir: string;
  let discoveryFile: string;
  let server: ChildProcess | undefined;
  let serverLog = '';

  beforeAll(async () => {
    dir = await mkdtemp(path.join(os.tmpdir(), 'revitpy-real-live-'));
    discoveryFile = path.join(dir, 'live.json');
    const child = spawn(python, [fixture], {
      env: { ...process.env, REVITPY_LIVE_DISCOVERY: discoveryFile, REVITPY_LIVE_TOKEN: 'real-test-token' },
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    server = child;
    child.stdout.on('data', (chunk: Buffer) => (serverLog += chunk.toString('utf8')));
    child.stderr.on('data', (chunk: Buffer) => (serverLog += chunk.toString('utf8')));
    await waitFor(() => serverLog.includes('READY') || child.exitCode !== null, 15_000, 'the Live Server to start');
    if (!serverLog.includes('READY')) {
      throw new Error(`Live Server fixture failed to start:\n${serverLog}`);
    }
  });

  afterAll(async () => {
    if (server && server.exitCode === null) {
      const exited = new Promise((resolve) => server?.once('exit', resolve));
      server.stdin?.end();
      const timer = setTimeout(() => server?.kill(), 5000);
      await exited;
      clearTimeout(timer);
    }
    await rm(dir, { recursive: true, force: true });
  });

  it('answers live/status through the client', async () => {
    const info = await readDiscovery(discoveryFile);
    expect(info.token).toBe('real-test-token');
    const client = await LiveClient.connect(info);
    try {
      const status = await client.status();
      expect(status.protocol).toBe(1);
      expect(status.revit_version).toBe('2026');
      expect(status.document).toBe('DevServer.rvt');
    } finally {
      await client.close();
    }
  });

  it('rejects a wrong token', async () => {
    const info = await readDiscovery(discoveryFile);
    await expect(LiveClient.connect({ ...info, token: 'wrong' })).rejects.toMatchObject({ statusCode: 401 });
  });

  it('run reports script output and tracebacks', async () => {
    const good = path.join(dir, 'good.py');
    const bad = path.join(dir, 'bad.py');
    await writeFile(good, 'print("hello from revit", __revit__.ActiveUIDocument.Document.Title)\n');
    await writeFile(bad, '1 / 0\n');
    const stdout = new Capture();
    const stderr = new Capture();
    const io = { stdout, stderr, env: { NO_COLOR: '1' }, cwd: dir };

    expect(await main(['node', 'cli', '--discovery', discoveryFile, 'run', 'good.py'], io)).toBe(0);
    expect(stdout.text).toContain('  | hello from revit DevServer.rvt');

    expect(await main(['node', 'cli', '--discovery', discoveryFile, 'run', 'bad.py'], io)).toBe(1);
    expect(stdout.text).toContain('FAILED');
    expect(stdout.text).toContain('ZeroDivisionError');
  });

  it('watch reloads a changed module and re-runs the entry script', async () => {
    const project = path.join(dir, 'project');
    await mkdir(project);
    const helper = path.join(project, 'devserver_helper_mod.py');
    const entry = path.join(project, 'main.py');
    await writeFile(helper, 'VALUE = 1\n');
    await writeFile(entry, 'import devserver_helper_mod\nprint("value", devserver_helper_mod.VALUE)\n');

    const stdout = new Capture();
    const stderr = new Capture();
    const stop = new AbortController();
    const done = main(
      ['node', 'cli', '--discovery', discoveryFile, 'watch', '.', '--run', 'main.py', '--debounce', '50'],
      { stdout, stderr, env: { NO_COLOR: '1' }, cwd: project, signal: stop.signal },
    );
    try {
      await waitFor(() => stdout.text.includes('connected'), 10_000, 'watch to connect');
      await new Promise((resolve) => setTimeout(resolve, 200));

      // Saving the entry script runs it; that imports the helper for the first time.
      await writeFile(entry, 'import devserver_helper_mod\nprint("value", devserver_helper_mod.VALUE)\n\n');
      await waitFor(() => stdout.text.includes('value 1'), 10_000, 'the first run');

      // Saving the helper reloads it in the server process, so the re-run sees the new value.
      await writeFile(helper, 'VALUE = 2\n');
      await waitFor(() => stdout.text.includes('value 2'), 10_000, `the re-run after reload:\n${stdout.text}`);
      expect(stdout.text).toContain('devserver_helper_mod');
      expect(stdout.text).toMatch(/reload {2}1 module \(devserver_helper_mod\)/);

      // A syntax error is reported by the reload and the run is skipped.
      await writeFile(helper, 'VALUE = (\n');
      await waitFor(() => stdout.text.includes('skipped'), 10_000, 'the skipped run');
      expect(stdout.text).toContain('SyntaxError');
    } finally {
      stop.abort();
    }
    expect(await done).toBe(0);
    expect(stderr.text).toBe('');
  });
});
