import { describe, expect, it } from 'vitest';
import {
  dedent,
  formatDuration,
  formatExecutionResult,
  formatReloadResult,
  isValidProjectName,
  lastErrorLine,
  mergeExtraPaths,
  removeExtraPath,
  shellQuote,
  statusBarText,
  statusSummary,
} from '../src/format';
import type { LiveStatus } from '../src/protocol';

const STATUS: LiveStatus = {
  protocol: 1,
  revitpy_version: '1.0.0',
  python_version: '3.12.0',
  revit_version: '2025',
  document: 'Project1.rvt',
  debug: { listening: false, port: null },
  analyses: [],
};

describe('dedent', () => {
  it('removes common indentation and keeps relative indentation', () => {
    expect(dedent('    a = 1\n    if a:\n        b = 2\n')).toBe('a = 1\nif a:\n    b = 2\n');
  });

  it('handles CRLF and whitespace-only lines', () => {
    expect(dedent('    a = 1\r\n      \r\n    b = 2\r\n')).toBe('a = 1\n\nb = 2\n');
  });

  it('uses the least indented line', () => {
    expect(dedent('    a = 1\n  b = 2\n    c = 3')).toBe('  a = 1\nb = 2\n  c = 3\n');
  });

  it('strips surrounding blank lines', () => {
    expect(dedent('\n\n  x = 1\n\n')).toBe('x = 1\n');
    expect(dedent('  \n')).toBe('');
    expect(dedent('')).toBe('');
  });
});

describe('formatDuration / lastErrorLine', () => {
  it('formats durations', () => {
    expect(formatDuration(12.4)).toBe('12 ms');
    expect(formatDuration(0)).toBe('0 ms');
    expect(formatDuration(1234)).toBe('1.23 s');
  });

  it('finds the exception line of a traceback', () => {
    expect(lastErrorLine('Traceback (most recent call last):\n  File "x"\nValueError: boom\n\n')).toBe('ValueError: boom');
    expect(lastErrorLine(null)).toBe('Unknown error');
    expect(lastErrorLine(undefined)).toBe('Unknown error');
    expect(lastErrorLine('\n \n')).toBe('Unknown error');
  });
});

describe('formatExecutionResult', () => {
  it('formats a failure with output and traceback', () => {
    expect(
      formatExecutionResult('run.py', {
        success: false,
        output: 'partial\n',
        error: 'Traceback (most recent call last):\n  File "x", line 1\nValueError: boom\n',
        duration_ms: 5,
      }),
    ).toEqual([
      'partial',
      '--- Error ---',
      'Traceback (most recent call last):',
      '  File "x", line 1',
      'ValueError: boom',
      '\u2716 run.py failed after 5 ms',
    ]);
  });

  it('formats a silent success', () => {
    expect(formatExecutionResult('run.py', { success: true, output: '', error: null, duration_ms: 5 })).toEqual([
      '\u2714 run.py finished in 5 ms',
    ]);
  });

  it('handles a failure without an error message', () => {
    expect(formatExecutionResult('x', { success: false, output: '', error: null, duration_ms: 1500 })).toEqual([
      '--- Error ---',
      'Unknown error',
      '\u2716 x failed after 1.50 s',
    ]);
  });
});

describe('formatReloadResult', () => {
  it('separates real failures from modules that are not imported', () => {
    expect(
      formatReloadResult({
        reloaded: ['a', 'b'],
        errors: { c: 'not imported', d: 'Traceback...\nImportError: nope\n' },
      }),
    ).toEqual({
      lines: ['Reloaded: a, b', 'Not imported yet (nothing to reload): c', 'Reload failed for d: ImportError: nope'],
      failed: ['d'],
    });
  });

  it('says when nothing matched', () => {
    expect(formatReloadResult({ reloaded: [], errors: {} })).toEqual({
      lines: ['No imported modules matched; nothing to reload.'],
      failed: [],
    });
  });
});

describe('status formatting', () => {
  it('builds the status bar text', () => {
    expect(statusBarText(STATUS, false)).toBe('$(debug-disconnect) Revit');
    expect(statusBarText(undefined, true)).toBe('$(plug) Revit');
    expect(statusBarText(STATUS, true)).toBe('$(plug) Revit 2025 \u00b7 Project1.rvt');
    expect(statusBarText({ ...STATUS, document: null, revit_version: null }, true)).toBe('$(plug) Revit ?');
    expect(statusBarText({ ...STATUS, debug: { listening: true, port: 5678 } }, true)).toBe(
      '$(plug) Revit 2025 \u00b7 Project1.rvt $(debug)',
    );
  });

  it('summarises the status', () => {
    expect(statusSummary(STATUS, 'ws://127.0.0.1:8766')).toEqual([
      'Server:     ws://127.0.0.1:8766',
      'Revit:      2025',
      'Document:   Project1.rvt',
      'RevitPy:    1.0.0',
      'Python:     3.12.0',
      'Debugger:   not started',
      'Analyses:   (none registered)',
    ]);
    const other = statusSummary(
      { ...STATUS, revit_version: null, document: null, debug: { listening: true, port: 5678 }, analyses: ['a', 'b'] },
      'ws://h',
    );
    expect(other).toContain('Revit:      unknown');
    expect(other).toContain('Document:   (no active document)');
    expect(other).toContain('Debugger:   listening on port 5678');
    expect(other).toContain('Analyses:   a, b');
  });
});

describe('isValidProjectName', () => {
  it('accepts valid names', () => {
    for (const name of ['abc', 'a123', 'a-b_c', 'A' + 'b'.repeat(99)]) {
      expect(isValidProjectName(name)).toBeUndefined();
    }
  });

  it('rejects invalid names', () => {
    expect(isValidProjectName('')).toBe('Enter a project name.');
    expect(isValidProjectName('   ')).toBe('Enter a project name.');
    for (const name of ['1abc', '-abc', 'a.b', 'a b', '../x', 'a' + 'b'.repeat(100)]) {
      expect(isValidProjectName(name)).toEqual(expect.any(String));
    }
  });
});

describe('shellQuote', () => {
  it('leaves safe arguments alone', () => {
    expect(shellQuote('/home/u/projects', 'linux')).toBe('/home/u/projects');
    expect(shellQuote('C:\\projects', 'win32')).toBe('C:\\projects');
  });

  it('quotes for Windows shells', () => {
    expect(shellQuote('C:\\Program Files\\x', 'win32')).toBe('"C:\\Program Files\\x"');
    expect(shellQuote('a"b', 'win32')).toBe('"a""b"');
  });

  it('quotes for POSIX shells', () => {
    expect(shellQuote("it's", 'linux')).toBe(`'it'\\''s'`);
    expect(shellQuote('', 'linux')).toBe("''");
  });
});

describe('extraPaths helpers', () => {
  it('merges without duplicates and drops non-strings', () => {
    expect(mergeExtraPaths(['a', 3, 'b'], 'b')).toEqual(['a', 'b']);
    expect(mergeExtraPaths(['a'], 'c')).toEqual(['a', 'c']);
    expect(mergeExtraPaths(undefined, 'x')).toEqual(['x']);
    expect(mergeExtraPaths('oops', 'x')).toEqual(['x']);
  });

  it('removes a path', () => {
    expect(removeExtraPath(['a', 'b'], 'a')).toEqual(['b']);
    expect(removeExtraPath(['a'], 'c')).toEqual(['a']);
    expect(removeExtraPath(null, 'a')).toEqual([]);
  });
});
