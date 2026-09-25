/** The reload -> run cycle executed for each batch of changed files. */
import path from 'node:path';
import { performance } from 'node:perf_hooks';
import type { ExecResult, ReloadResult } from './client.js';
import { isAbortError } from './retry.js';
import type { LiveSession } from './session.js';

/** Receives the progress of each cycle (see `ConsoleReporter`). */
export interface Reporter {
  changed(paths: string[]): void;
  reloaded(result: ReloadResult, elapsedMs: number): void;
  ran(entry: string, result: ExecResult, elapsedMs: number): void;
  skipped(entry: string, reason: string): void;
  failed(error: unknown): void;
}

export interface DevLoopOptions {
  session: LiveSession;
  /** Script to run after every successful reload; omit to only reload. */
  entry?: string;
  reporter: Reporter;
}

/** What one cycle did. */
export interface CycleResult {
  paths: string[];
  reload?: ReloadResult;
  run?: ExecResult;
  error?: unknown;
}

/**
 * Runs cycles one at a time: `live/reload {paths}`, then `live/runFile {entry}`
 * unless the reload reported errors. Changes arriving while a cycle runs are
 * merged into a single follow-up cycle.
 */
export class DevLoop {
  /** Every completed cycle, oldest first. */
  readonly cycles: CycleResult[] = [];
  private readonly queued = new Set<string>();
  private running: Promise<void> | undefined;
  private readonly session: LiveSession;
  private readonly entry: string | undefined;
  private readonly reporter: Reporter;

  constructor(options: DevLoopOptions) {
    this.session = options.session;
    this.entry = options.entry === undefined ? undefined : path.resolve(options.entry);
    this.reporter = options.reporter;
  }

  /** Schedule a cycle for `paths` (merged into the next cycle if one is running). */
  enqueue(paths: string[]): void {
    for (const file of paths) {
      this.queued.add(file);
    }
    this.running ??= this.drain().finally(() => {
      this.running = undefined;
    });
  }

  /** Resolves once no cycle is running or queued. */
  idle(): Promise<void> {
    return this.running ?? Promise.resolve();
  }

  /** Run one cycle now. Never throws; failures are reported and recorded in the result. */
  async runCycle(paths: string[]): Promise<CycleResult> {
    const result: CycleResult = { paths };
    this.reporter.changed(paths);
    try {
      let started = performance.now();
      const reload = await this.session.use((client) => client.reload({ paths }));
      result.reload = reload;
      this.reporter.reloaded(reload, performance.now() - started);

      const entry = this.entry;
      if (entry !== undefined) {
        const failed = Object.keys(reload.errors);
        if (failed.length > 0) {
          this.reporter.skipped(entry, `reload failed for ${failed.join(', ')}`);
        } else {
          started = performance.now();
          const run = await this.session.use((client) => client.runFile(entry));
          result.run = run;
          this.reporter.ran(entry, run, performance.now() - started);
        }
      }
    } catch (error: unknown) {
      result.error = error;
      if (!isAbortError(error)) {
        this.reporter.failed(error);
      }
    }
    this.cycles.push(result);
    return result;
  }

  private async drain(): Promise<void> {
    while (this.queued.size > 0) {
      const batch = [...this.queued];
      this.queued.clear();
      await this.runCycle(batch);
    }
  }
}
