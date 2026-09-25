/** Watching Python sources with chokidar. */
import type { Stats } from 'node:fs';
import path from 'node:path';
import { watch } from 'chokidar';
import picomatch from 'picomatch';

/** Always ignored, matched relative to each watched root. */
export const DEFAULT_IGNORES = [
  '**/__pycache__',
  '**/__pycache__/**',
  '**/.*',
  '**/.*/**',
  '**/node_modules',
  '**/node_modules/**',
];

export interface PythonWatcherOptions {
  /** Files or directories to watch (recursively). */
  paths: string[];
  /** Extra globs to ignore, relative to a watched root (or to the current directory). */
  ignore?: string[];
  /** Called with the absolute path of every added or changed `.py` file. */
  onChange: (file: string) => void;
  onError?: (error: unknown) => void;
}

export interface PythonWatcher {
  close(): Promise<void>;
}

const toPosix = (file: string): string => file.replace(/\\/g, '/');

function inside(root: string, file: string): string | undefined {
  const relative = path.relative(root, file);
  if (relative === '' || relative.startsWith('..') || path.isAbsolute(relative)) {
    return undefined;
  }
  return toPosix(relative);
}

/** Start watching; resolves once the initial scan is done (existing files do not fire). */
export async function watchPython(options: PythonWatcherOptions): Promise<PythonWatcher> {
  const roots = options.paths.map((file) => path.resolve(file));
  const userIgnores = options.ignore ?? [];
  const ignoredInRoot = picomatch([...DEFAULT_IGNORES, ...userIgnores], { dot: true });
  const ignoredInCwd = userIgnores.length > 0 ? picomatch(userIgnores, { dot: true }) : undefined;

  const ignored = (file: string, stats?: Stats): boolean => {
    const absolute = path.resolve(file);
    for (const root of roots) {
      const relative = inside(root, absolute);
      if (relative !== undefined && ignoredInRoot(relative)) {
        return true;
      }
    }
    if (ignoredInCwd) {
      const relative = inside(process.cwd(), absolute);
      if (relative !== undefined && ignoredInCwd(relative)) {
        return true;
      }
    }
    return stats?.isFile() === true && !absolute.endsWith('.py');
  };

  const watcher = watch(roots, { ignoreInitial: true, ignored, atomic: true, persistent: true });
  const report = (file: string): void => {
    if (file.endsWith('.py')) {
      options.onChange(path.resolve(file));
    }
  };
  watcher.on('add', report);
  watcher.on('change', report);
  watcher.on('error', (error: unknown) => {
    options.onError?.(error);
  });
  await new Promise<void>((resolve) => {
    watcher.once('ready', () => {
      resolve();
    });
  });
  return { close: () => watcher.close() };
}
