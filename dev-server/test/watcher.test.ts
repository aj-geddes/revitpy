import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { watchPython } from '../src/watcher.js';
import type { PythonWatcher } from '../src/watcher.js';
import { waitFor } from './helpers/fakeLiveServer.js';

const settle = (ms = 150): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));

describe('watchPython', () => {
  let dir: string;
  let watcher: PythonWatcher | undefined;
  let changes: string[];

  beforeEach(async () => {
    dir = await mkdtemp(path.join(os.tmpdir(), 'revitpy-watch-'));
    changes = [];
    for (const sub of ['pkg/__pycache__', '.venv/lib', 'node_modules', 'build']) {
      await mkdir(path.join(dir, sub), { recursive: true });
    }
    await writeFile(path.join(dir, 'pkg', 'helper.py'), 'A = 1\n');
    await writeFile(path.join(dir, 'main.py'), 'print(1)\n');
  });

  afterEach(async () => {
    await watcher?.close();
    watcher = undefined;
    await rm(dir, { recursive: true, force: true });
  });

  const start = async (options: { paths?: string[]; ignore?: string[] } = {}): Promise<void> => {
    watcher = await watchPython({
      paths: options.paths ?? [dir],
      ...(options.ignore ? { ignore: options.ignore } : {}),
      onChange: (file) => changes.push(file),
    });
    await settle();
  };

  /** Write ignored files, then a sentinel; once the sentinel is seen nothing else may have fired. */
  const expectOnlySentinel = async (ignored: string[]): Promise<void> => {
    for (const file of ignored) {
      await writeFile(path.join(dir, file), 'x = 1\n');
    }
    const sentinel = path.join(dir, 'sentinel.py');
    await writeFile(sentinel, 'x = 1\n');
    await waitFor(() => changes.includes(sentinel), 5000, 'the sentinel');
    await settle();
    expect(changes).toEqual([sentinel]);
  };

  it('reports changed and added .py files with absolute paths', async () => {
    await start();
    const helper = path.join(dir, 'pkg', 'helper.py');
    await writeFile(helper, 'A = 2\n');
    await waitFor(() => changes.includes(helper), 5000, 'the change');
    const added = path.join(dir, 'new_mod.py');
    await writeFile(added, 'B = 1\n');
    await waitFor(() => changes.includes(added), 5000, 'the new file');
    expect(changes.every((file) => path.isAbsolute(file))).toBe(true);
  });

  it('ignores non-Python files, __pycache__, dot-directories and node_modules', async () => {
    await start();
    await expectOnlySentinel([
      'notes.txt',
      'pkg/__pycache__/helper.cpython-312.pyc',
      '.venv/lib/site.py',
      'node_modules/x.py',
    ]);
  });

  it('applies extra ignore globs relative to the watched directory', async () => {
    await start({ ignore: ['build/**'] });
    await expectOnlySentinel(['build/gen.py']);
  });

  it('watches a single file', async () => {
    const main = path.join(dir, 'main.py');
    await start({ paths: [main] });
    await writeFile(main, 'print(2)\n');
    await waitFor(() => changes.includes(main), 5000, 'the change');
    expect(new Set(changes)).toEqual(new Set([main]));
  });

  it('stops reporting after close()', async () => {
    await start();
    await watcher?.close();
    watcher = undefined;
    await writeFile(path.join(dir, 'main.py'), 'print(3)\n');
    await settle(300);
    expect(changes).toEqual([]);
  });
});
