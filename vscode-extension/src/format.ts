/** Pure helpers (no `vscode` import) shared by the commands. */
import type { ExecutionResult, LiveStatus, ReloadResult } from './protocol';

/** Remove common leading indentation, like Python's textwrap.dedent. */
export function dedent(code: string): string {
  const lines = code.replace(/\r\n/g, '\n').split('\n');
  let start = 0;
  while (start < lines.length && lines[start].trim() === '') {
    start++;
  }
  let end = lines.length;
  while (end > start && lines[end - 1].trim() === '') {
    end--;
  }
  const body = lines.slice(start, end);
  if (body.length === 0) {
    return '';
  }

  let indent: string | undefined;
  for (const line of body) {
    if (line.trim() === '') {
      continue;
    }
    const own = /^[ \t]*/.exec(line)?.[0] ?? '';
    if (indent === undefined) {
      indent = own;
      continue;
    }
    let i = 0;
    while (i < indent.length && i < own.length && indent[i] === own[i]) {
      i++;
    }
    indent = indent.slice(0, i);
  }
  const prefix = indent ?? '';
  return body.map((line) => (line.trim() === '' ? '' : line.slice(prefix.length))).join('\n') + '\n';
}

export function formatDuration(ms: number): string {
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(2)} s`;
}

/** Last non-empty line of a Python traceback (the exception message). */
export function lastErrorLine(error: string | null | undefined): string {
  const lines = (error ?? '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line !== '');
  return lines.length > 0 ? lines[lines.length - 1] : 'Unknown error';
}

export function formatExecutionResult(label: string, result: ExecutionResult): string[] {
  const lines: string[] = [];
  if (result.output) {
    lines.push(...result.output.replace(/\r?\n$/, '').split(/\r?\n/));
  }
  if (!result.success) {
    lines.push('--- Error ---');
    lines.push(...(result.error ?? 'Unknown error').replace(/\r?\n$/, '').split(/\r?\n/));
  }
  const duration = formatDuration(result.duration_ms);
  lines.push(result.success ? `✔ ${label} finished in ${duration}` : `✖ ${label} failed after ${duration}`);
  return lines;
}

export function formatReloadResult(result: ReloadResult): { lines: string[]; failed: string[] } {
  const lines: string[] = [];
  const failed: string[] = [];
  if (result.reloaded.length > 0) {
    lines.push(`Reloaded: ${result.reloaded.join(', ')}`);
  }
  const errors = Object.entries(result.errors);
  for (const [name, message] of errors) {
    if (message === 'not imported') {
      lines.push(`Not imported yet (nothing to reload): ${name}`);
    } else {
      lines.push(`Reload failed for ${name}: ${lastErrorLine(message)}`);
      failed.push(name);
    }
  }
  if (result.reloaded.length === 0 && errors.length === 0) {
    lines.push('No imported modules matched; nothing to reload.');
  }
  return { lines, failed };
}

export function statusBarText(status: LiveStatus | undefined, connected: boolean): string {
  if (!connected) {
    return '$(debug-disconnect) Revit';
  }
  if (!status) {
    return '$(plug) Revit';
  }
  let text = `$(plug) Revit ${status.revit_version ?? '?'}`;
  if (status.document) {
    text += ` · ${status.document}`;
  }
  if (status.debug.listening) {
    text += ' $(debug)';
  }
  return text;
}

export function statusSummary(status: LiveStatus, url: string): string[] {
  const { debug, analyses } = status;
  return [
    `Server:     ${url}`,
    `Revit:      ${status.revit_version ?? 'unknown'}`,
    `Document:   ${status.document ?? '(no active document)'}`,
    `RevitPy:    ${status.revitpy_version}`,
    `Python:     ${status.python_version}`,
    `Debugger:   ${debug.listening ? `listening on port ${debug.port}` : 'not started'}`,
    `Analyses:   ${analyses.length ? analyses.join(', ') : '(none registered)'}`,
  ];
}

/** Returns an error message, or undefined when the name is valid. */
export function isValidProjectName(name: string): string | undefined {
  if (name.trim() === '') {
    return 'Enter a project name.';
  }
  if (name.length > 100 || !/^[A-Za-z][A-Za-z0-9_-]*$/.test(name)) {
    return 'Use letters, digits, - and _, starting with a letter (at most 100 characters).';
  }
  return undefined;
}

/** Quote one argument for the integrated terminal's shell. */
export function shellQuote(arg: string, platform: NodeJS.Platform = process.platform): string {
  if (/^[A-Za-z0-9_\-.,:/\\=@+]+$/.test(arg)) {
    return arg;
  }
  if (platform === 'win32') {
    return `"${arg.replace(/"/g, '""')}"`;
  }
  return `'${arg.replace(/'/g, `'\\''`)}'`;
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
}

export function mergeExtraPaths(existing: unknown, add: string): string[] {
  const paths = stringArray(existing);
  return paths.includes(add) ? paths : [...paths, add];
}

export function removeExtraPath(existing: unknown, remove: string): string[] {
  return stringArray(existing).filter((entry) => entry !== remove);
}
