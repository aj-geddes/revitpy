/** Terminal output for the CLI. */
import path from 'node:path';
import type { ExecResult, LiveClient, LiveStatus, ReloadResult } from './client.js';
import { LiveServerError } from './errors.js';
import type { Reporter } from './loop.js';

/** Minimal writable stream (process.stdout, or a test buffer). */
export interface Output {
  write(chunk: string): unknown;
  isTTY?: boolean;
}

type Paint = (text: string) => string;

function palette(color: boolean): Record<'red' | 'green' | 'yellow' | 'cyan' | 'dim' | 'bold', Paint> {
  const style =
    (code: string): Paint =>
    (text) =>
      color ? `\u001b[${code}m${text}\u001b[0m` : text;
  return { red: style('31'), green: style('32'), yellow: style('33'), cyan: style('36'), dim: style('2'), bold: style('1') };
}

/** Colors unless `NO_COLOR` is set; forced by `FORCE_COLOR` (other than `0`); otherwise only on a TTY. */
export function useColor(stream: Output, env: NodeJS.ProcessEnv = process.env): boolean {
  if (env.NO_COLOR !== undefined && env.NO_COLOR !== '') {
    return false;
  }
  if (env.FORCE_COLOR !== undefined && env.FORCE_COLOR !== '0') {
    return true;
  }
  return stream.isTTY === true;
}

/** `123 ms` below one second, `1.23 s` above. */
export function formatDuration(ms: number): string {
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(2)} s`;
}

function indent(text: string, prefix: string): string {
  const trimmed = text.replace(/\r?\n$/, '');
  if (trimmed === '') {
    return '';
  }
  return trimmed
    .split(/\r?\n/)
    .map((line) => prefix + line)
    .join('\n');
}

/** Script output (prefixed `  | `) followed by the traceback, if any. */
export function formatExecResult(result: ExecResult, color: boolean): string {
  const { dim, red } = palette(color);
  const parts: string[] = [];
  const output = indent(result.output, dim('  | '));
  if (output) {
    parts.push(output);
  }
  if (result.error) {
    parts.push(red(indent(result.error, '  ')));
  }
  return parts.length > 0 ? `${parts.join('\n')}\n` : '';
}

/** Human-readable `live/status`. */
export function formatStatus(status: LiveStatus, url: string): string {
  const debug = status.debug.listening ? `listening on port ${String(status.debug.port)}` : 'not started';
  return (
    [
      `Live Server   ${url}`,
      `Revit         ${status.revit_version ?? 'unknown'}`,
      `Document      ${status.document ?? '(none open)'}`,
      `RevitPy       ${status.revitpy_version}`,
      `Python        ${status.python_version}`,
      `Debugger      ${debug}`,
      `Analyses      ${status.analyses.length > 0 ? status.analyses.join(', ') : '(none registered)'}`,
    ].join('\n') + '\n'
  );
}

/** One-line description of any error. */
export function describeError(error: unknown): string {
  if (error instanceof LiveServerError) {
    return `Live Server error ${error.code}: ${error.rpcMessage}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

export interface ConsoleReporterOptions {
  color?: boolean;
  /** Paths are shown relative to this directory (default: `process.cwd()`). */
  cwd?: string;
  now?: () => Date;
}

/** Prints each cycle as a short, timestamped block. */
export class ConsoleReporter implements Reporter {
  private readonly paint: ReturnType<typeof palette>;
  private readonly color: boolean;
  private readonly cwd: string;
  private readonly now: () => Date;
  private lastRetryMessage: string | undefined;

  constructor(
    private readonly out: Output,
    options: ConsoleReporterOptions = {},
  ) {
    this.color = options.color ?? useColor(out);
    this.paint = palette(this.color);
    this.cwd = options.cwd ?? process.cwd();
    this.now = options.now ?? (() => new Date());
  }

  changed(paths: string[]): void {
    const { cyan, dim } = this.paint;
    const time = this.now().toTimeString().slice(0, 8);
    this.line(`\n${dim(`[${time}]`)} ${cyan('changed')} ${paths.map((file) => this.rel(file)).join(', ')}`);
  }

  reloaded(result: ReloadResult, elapsedMs: number): void {
    const { green, dim, red, bold } = this.paint;
    const count = result.reloaded.length;
    if (count > 0) {
      const modules = `${String(count)} module${count === 1 ? '' : 's'}`;
      this.line(`  reload  ${green(modules)} (${result.reloaded.join(', ')}) in ${formatDuration(elapsedMs)}`);
    } else {
      this.line(`  reload  ${dim('no imported module matched')} (${formatDuration(elapsedMs)})`);
    }
    for (const [name, message] of Object.entries(result.errors)) {
      this.line(`  ${red('reload error')} in ${bold(name)}:`);
      this.line(red(indent(message, '    ')));
    }
  }

  ran(entry: string, result: ExecResult, elapsedMs: number): void {
    const { green, red, dim } = this.paint;
    const outcome = result.success ? green('ok') : red('FAILED');
    const inRevit = dim(`(Revit ${formatDuration(result.duration_ms)})`);
    this.line(`  run     ${this.rel(entry)} ${outcome} in ${formatDuration(elapsedMs)} ${inRevit}`);
    this.out.write(formatExecResult(result, this.color));
  }

  skipped(entry: string, reason: string): void {
    this.line(`  run     ${this.rel(entry)} ${this.paint.yellow('skipped')}: ${reason}`);
  }

  failed(error: unknown): void {
    this.line(`  ${this.paint.red('error')}   ${describeError(error)}`);
  }

  info(message: string): void {
    this.line(message);
  }

  warn(message: string): void {
    this.line(this.paint.yellow(message));
  }

  /** Reports a failed connection attempt; repeats of the same message are suppressed. */
  retrying(error: unknown, attempt: number, delayMs: number): void {
    const message = describeError(error);
    if (attempt === 1 || message !== this.lastRetryMessage) {
      this.line(`${this.paint.yellow('waiting')} ${message} (next try in ${formatDuration(delayMs)}; retrying until it is up)`);
    }
    this.lastRetryMessage = message;
  }

  connected(client: LiveClient): void {
    this.lastRetryMessage = undefined;
    const revit = client.info.revitVersion ? ` (Revit ${client.info.revitVersion})` : '';
    this.line(`${this.paint.green('connected')} to the RevitPy Live Server at ${client.info.url}${revit}`);
  }

  private line(text: string): void {
    this.out.write(`${text}\n`);
  }

  private rel(file: string): string {
    const relative = path.relative(this.cwd, file);
    return relative === '' || relative.startsWith('..') || path.isAbsolute(relative) ? file : relative;
  }
}
