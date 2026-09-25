/** The `revitpy-dev-server` command line (no side effects on import; see bin.ts). */
import { existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { performance } from 'node:perf_hooks';
import { Command, CommanderError } from 'commander';
import { ChangeBatcher } from './batcher.js';
import { LiveClient } from './client.js';
import { discoveryPath, readDiscovery } from './discovery.js';
import type { Output } from './format.js';
import { ConsoleReporter, describeError, formatStatus, useColor } from './format.js';
import { DevLoop } from './loop.js';
import { isAbortError } from './retry.js';
import { LiveSession } from './session.js';
import { watchPython } from './watcher.js';

/** Where the CLI reads and writes; injectable for tests. */
export interface CliIO {
  stdout: Output;
  stderr: Output;
  env: NodeJS.ProcessEnv;
  cwd: string;
  /** Aborting stops `watch` (Ctrl+C). */
  signal?: AbortSignal;
}

export const VERSION = (createRequire(import.meta.url)('../package.json') as { version: string }).version;

interface WatchOptions {
  run?: string;
  reloadOnly?: boolean;
  debounce: string;
  ignore: string[];
}

/** Build the commander program; actions report their exit code through `setExitCode`. */
export function createProgram(io: CliIO, setExitCode: (code: number) => void): Command {
  const program = new Command('revitpy-dev-server')
    .description(
      'Edit-save-see loop for RevitPy: reload changed Python modules in a running Revit and re-run your script',
    )
    .version(VERSION)
    .option('--discovery <file>', 'Live Server discovery file (default: $REVITPY_LIVE_DISCOVERY or ~/.revitpy/live.json)')
    .exitOverride()
    .configureOutput({
      writeOut: (text) => io.stdout.write(text),
      writeErr: (text) => io.stderr.write(text),
    });

  const discoveryFile = (): string => {
    const { discovery } = program.opts<{ discovery?: string }>();
    return discovery ? path.resolve(io.cwd, discovery) : discoveryPath(io.env);
  };
  const fail = (code: number, message: string): void => {
    io.stderr.write(`error: ${message}\n`);
    setExitCode(code);
  };
  const reporter = (): ConsoleReporter =>
    new ConsoleReporter(io.stdout, { color: useColor(io.stdout, io.env), cwd: io.cwd });

  /** Connect once (no retries: one-shot commands should fail fast), run `fn`, close. */
  async function once(fn: (client: LiveClient) => Promise<void>): Promise<void> {
    let client: LiveClient | undefined;
    try {
      client = await LiveClient.connect(await readDiscovery(discoveryFile()));
      await fn(client);
    } catch (error: unknown) {
      fail(1, describeError(error));
    } finally {
      await client?.close();
    }
  }

  program
    .command('status')
    .description('Show the Live Server and Revit session status')
    .action(async () => {
      await once(async (client) => {
        io.stdout.write(formatStatus(await client.status(), client.info.url));
        setExitCode(0);
      });
    });

  program
    .command('run <file>')
    .description('Run a Python file in Revit once and print its output (exit code 1 if it fails)')
    .action(async (file: string) => {
      const script = path.resolve(io.cwd, file);
      if (!existsSync(script)) {
        fail(2, `${script} does not exist`);
        return;
      }
      await once(async (client) => {
        const started = performance.now();
        const result = await client.runFile(script);
        reporter().ran(script, result, performance.now() - started);
        setExitCode(result.success ? 0 : 1);
      });
    });

  program
    .command('watch [paths...]')
    .description('Watch Python files; on save reload them in Revit and optionally re-run an entry script')
    .option('--run <entry>', 'script to run after every reload')
    .option('--reload-only', 'only reload changed modules, run nothing')
    .option('--debounce <ms>', 'quiet period before acting on changes', '150')
    .option(
      '--ignore <glob>',
      'glob (relative to a watched path) to ignore; repeatable',
      (value: string, previous: string[]) => [...previous, value],
      [] as string[],
    )
    .action(async (paths: string[], options: WatchOptions) => {
      await watchCommand(paths, options);
    });

  async function watchCommand(paths: string[], options: WatchOptions): Promise<void> {
    if (Boolean(options.run) === Boolean(options.reloadOnly)) {
      fail(2, 'pass --run <entry.py> to re-run a script after each reload, or --reload-only');
      return;
    }
    const entry = options.run === undefined ? undefined : path.resolve(io.cwd, options.run);
    if (entry !== undefined && (!entry.endsWith('.py') || !existsSync(entry))) {
      fail(2, `--run needs an existing .py file: ${entry}`);
      return;
    }
    const debounce = Number(options.debounce);
    if (options.debounce.trim() === '' || !Number.isFinite(debounce) || debounce < 0) {
      fail(2, `--debounce must be a non-negative number of milliseconds, got '${options.debounce}'`);
      return;
    }
    const roots = paths.length > 0 ? paths.map((file) => path.resolve(io.cwd, file)) : [io.cwd];
    const missing = roots.find((root) => !existsSync(root));
    if (missing !== undefined) {
      fail(2, `${missing} does not exist`);
      return;
    }

    const output = reporter();
    const stop = new AbortController();
    if (io.signal?.aborted) {
      stop.abort();
    } else {
      io.signal?.addEventListener(
        'abort',
        () => {
          stop.abort();
        },
        { once: true },
      );
    }
    const session = new LiveSession({
      discoveryFile: discoveryFile(),
      signal: stop.signal,
      onRetry: (error, attempt, delayMs) => {
        output.retrying(error, attempt, delayMs);
      },
      onConnect: (client) => {
        output.connected(client);
      },
    });
    const loop = new DevLoop({ session, entry, reporter: output });
    const batcher = new ChangeBatcher(debounce, (changed) => {
      loop.enqueue(changed);
    });
    const watcher = await watchPython({
      paths: roots,
      ignore: options.ignore,
      onChange: (file) => {
        batcher.add(file);
      },
      onError: (error) => {
        output.warn(`watch error: ${describeError(error)}`);
      },
    });

    const shown = roots.map((root) => path.relative(io.cwd, root) || '.').join(', ');
    const action = entry === undefined ? ' (reload only)' : `; running ${path.relative(io.cwd, entry)} after each reload`;
    output.info(`Watching ${shown} for .py changes${action}. Press Ctrl+C to stop.`);

    // Connect now so problems show up before the first save.
    session.client().catch((error: unknown) => {
      if (!isAbortError(error) && !stop.signal.aborted) {
        output.failed(error);
      }
    });

    await new Promise<void>((resolve) => {
      if (stop.signal.aborted) {
        resolve();
      } else {
        stop.signal.addEventListener(
          'abort',
          () => {
            resolve();
          },
          { once: true },
        );
      }
    });

    batcher.cancel();
    await watcher.close();
    await session.close();
    let timer: ReturnType<typeof setTimeout> | undefined;
    await Promise.race([
      loop.idle(),
      new Promise<void>((resolve) => {
        timer = setTimeout(resolve, 2000);
      }),
    ]);
    clearTimeout(timer);
    output.info('Stopped.');
    setExitCode(0);
  }

  return program;
}

/** Run the CLI; resolves to the process exit code. */
export async function main(argv: string[] = process.argv, io?: CliIO): Promise<number> {
  let cleanup = (): void => undefined;
  if (io === undefined) {
    const stop = new AbortController();
    const onSignal = (): void => {
      if (stop.signal.aborted) {
        process.exit(130); // second Ctrl+C: give up on a clean shutdown
      }
      stop.abort();
    };
    process.on('SIGINT', onSignal);
    process.on('SIGTERM', onSignal);
    cleanup = () => {
      process.off('SIGINT', onSignal);
      process.off('SIGTERM', onSignal);
    };
    io = { stdout: process.stdout, stderr: process.stderr, env: process.env, cwd: process.cwd(), signal: stop.signal };
  }

  let exitCode = 0;
  const program = createProgram(io, (code) => {
    exitCode = code;
  });
  try {
    await program.parseAsync(argv);
    return exitCode;
  } catch (error: unknown) {
    if (error instanceof CommanderError) {
      return error.exitCode; // 0 for --help / --version
    }
    io.stderr.write(`error: ${describeError(error)}\n`);
    return 1;
  } finally {
    cleanup();
  }
}
