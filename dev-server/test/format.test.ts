import { describe, expect, it } from 'vitest';
import type { LiveClient } from '../src/client.js';
import { LiveServerError } from '../src/errors.js';
import { ConsoleReporter, describeError, formatDuration, formatExecResult, formatStatus, useColor } from '../src/format.js';
import { Capture } from './helpers/fakeLiveServer.js';

const ESC = '\u001b[';

describe('useColor', () => {
  it.each([
    [{}, true, true],
    [{}, false, false],
    [{ NO_COLOR: '1' }, true, false],
    [{ FORCE_COLOR: '1' }, false, true],
    [{ FORCE_COLOR: '0' }, true, true],
    [{ FORCE_COLOR: '0' }, false, false],
    [{ NO_COLOR: '1', FORCE_COLOR: '1' }, true, false],
  ])('env %j on tty=%s -> %s', (env, isTTY, expected) => {
    expect(useColor({ write: () => true, isTTY }, env)).toBe(expected);
  });
});

describe('formatting', () => {
  it('formats durations', () => {
    expect(formatDuration(0.4)).toBe('0 ms');
    expect(formatDuration(999)).toBe('999 ms');
    expect(formatDuration(1234)).toBe('1.23 s');
  });

  it('prefixes output lines and appends the traceback', () => {
    const text = formatExecResult({ success: false, output: 'a\nb\n', error: 'Traceback\nValueError: x\n', duration_ms: 1 }, false);
    expect(text).toBe('  | a\n  | b\n  Traceback\n  ValueError: x\n');
    expect(formatExecResult({ success: true, output: '', error: null, duration_ms: 1 }, false)).toBe('');
    expect(formatExecResult({ success: true, output: 'x', error: null, duration_ms: 1 }, true)).toContain(ESC);
  });

  it('formats the status', () => {
    const text = formatStatus(
      {
        protocol: 1,
        revitpy_version: '1.0',
        python_version: '3.12',
        revit_version: null,
        document: null,
        debug: { listening: true, port: 5678 },
        analyses: ['a', 'b'],
      },
      'ws://x',
    );
    expect(text).toContain('Revit         unknown');
    expect(text).toContain('Document      (none open)');
    expect(text).toContain('listening on port 5678');
    expect(text).toContain('Analyses      a, b');
  });

  it('describes errors', () => {
    expect(describeError(new LiveServerError(-32602, 'bad'))).toBe('Live Server error -32602: bad');
    expect(describeError(new Error('boom'))).toBe('boom');
    expect(describeError('text')).toBe('text');
  });
});

describe('ConsoleReporter', () => {
  const reporter = (color = false) => {
    const out = new Capture();
    return { out, r: new ConsoleReporter(out, { color, cwd: '/proj', now: () => new Date(2026, 0, 1, 9, 5, 7) }) };
  };

  it('prints a cycle without color codes', () => {
    const { out, r } = reporter();
    r.changed(['/proj/pkg/a.py', '/elsewhere/b.py']);
    r.reloaded({ reloaded: ['pkg.a'], errors: { b: 'SyntaxError: x' } }, 12.4);
    r.skipped('/proj/main.py', 'reload failed for b');
    r.ran('/proj/main.py', { success: true, output: 'hi\n', error: null, duration_ms: 3 }, 20);
    r.failed(new Error('boom'));
    expect(out.text).not.toContain(ESC);
    expect(out.text).toContain('[09:05:07] changed pkg/a.py, /elsewhere/b.py');
    expect(out.text).toContain('  reload  1 module (pkg.a) in 12 ms');
    expect(out.text).toContain('  reload error in b:\n    SyntaxError: x');
    expect(out.text).toContain('  run     main.py skipped: reload failed for b');
    expect(out.text).toContain('  run     main.py ok in 20 ms (Revit 3 ms)\n  | hi\n');
    expect(out.text).toContain('  error   boom');
  });

  it('reports when nothing was reloaded', () => {
    const { out, r } = reporter();
    r.reloaded({ reloaded: [], errors: {} }, 5);
    expect(out.text).toBe('  reload  no imported module matched (5 ms)\n');
  });

  it('uses color when asked', () => {
    const { out, r } = reporter(true);
    r.failed(new Error('boom'));
    expect(out.text).toContain(`${ESC}31m`);
  });

  it('prints each distinct retry reason once', () => {
    const { out, r } = reporter();
    const down = new Error('not running');
    r.retrying(down, 1, 250);
    r.retrying(down, 2, 500);
    r.retrying(new Error('Cannot reach'), 3, 1000);
    r.connected({ info: { url: 'ws://127.0.0.1:1', token: 't', protocol: 1, revitVersion: '2025', pid: null } } as LiveClient);
    r.retrying(down, 1, 250);
    const lines = out.text.trim().split('\n');
    expect(lines).toEqual([
      'waiting not running (next try in 250 ms; retrying until it is up)',
      'waiting Cannot reach (next try in 1.00 s; retrying until it is up)',
      'connected to the RevitPy Live Server at ws://127.0.0.1:1 (Revit 2025)',
      'waiting not running (next try in 250 ms; retrying until it is up)',
    ]);
  });
});
