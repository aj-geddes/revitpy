import { promises as fs } from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  DiscoveryError,
  LiveServerNotRunningError,
  START_HINT,
  defaultDiscoveryPath,
  parseDiscovery,
  readDiscovery,
  type DiscoveryInfo,
} from '../src/discovery';

const VALID = {
  protocol: 1,
  url: 'ws://127.0.0.1:8766',
  token: 'abc',
  pid: 12345,
  revit_version: '2025',
  started_at: '2026-09-25T10:00:00+00:00',
};

describe('defaultDiscoveryPath', () => {
  it('uses REVITPY_LIVE_DISCOVERY when set', () => {
    expect(defaultDiscoveryPath({ REVITPY_LIVE_DISCOVERY: '/custom/live.json' }, '/home/u')).toBe('/custom/live.json');
  });

  it('falls back to ~/.revitpy/live.json when the variable is empty or unset', () => {
    const expected = path.join('/home/u', '.revitpy', 'live.json');
    expect(defaultDiscoveryPath({ REVITPY_LIVE_DISCOVERY: '' }, '/home/u')).toBe(expected);
    expect(defaultDiscoveryPath({}, '/home/u')).toBe(expected);
  });
});

describe('parseDiscovery', () => {
  const parse = (value: unknown) => parseDiscovery(JSON.stringify(value), '/fake/live.json');

  it('parses the file the Live Server writes', () => {
    const expected: DiscoveryInfo = {
      protocol: 1,
      url: 'ws://127.0.0.1:8766',
      token: 'abc',
      pid: 12345,
      revitVersion: '2025',
      startedAt: '2026-09-25T10:00:00+00:00',
      path: '/fake/live.json',
    };
    expect(parse(VALID)).toEqual(expected);
  });

  it('accepts a numeric revit_version and a missing protocol', () => {
    const { protocol: _protocol, ...rest } = VALID;
    const info = parse({ ...rest, revit_version: 2025 });
    expect(info.revitVersion).toBe('2025');
    expect(info.protocol).toBe(1);
  });

  it('omits optional fields that are absent or null', () => {
    expect(parse({ url: 'ws://h:1', token: 't', revit_version: null })).toEqual({
      url: 'ws://h:1',
      token: 't',
      protocol: 1,
      path: '/fake/live.json',
    });
  });

  it('rejects an unsupported protocol', () => {
    expect(() => parse({ ...VALID, protocol: 2 })).toThrow(DiscoveryError);
    expect(() => parse({ ...VALID, protocol: 2 })).toThrow(/protocol 2/);
  });

  it.each([
    ['invalid JSON', 'not json'],
    ['an array', '[]'],
    ['a missing token', JSON.stringify({ url: 'ws://h:1' })],
    ['an empty token', JSON.stringify({ url: 'ws://h:1', token: '' })],
    ['an http URL', JSON.stringify({ url: 'http://h:1', token: 't' })],
  ])('rejects %s', (_name, text) => {
    expect(() => parseDiscovery(text, '/fake/live.json')).toThrow(DiscoveryError);
  });
});

describe('readDiscovery', () => {
  let dir: string;

  beforeEach(async () => {
    dir = await fs.mkdtemp(path.join(os.tmpdir(), 'revitpy-discovery-'));
  });

  afterEach(async () => {
    await fs.rm(dir, { recursive: true, force: true });
  });

  it('reads a discovery file', async () => {
    const file = path.join(dir, 'live.json');
    await fs.writeFile(file, JSON.stringify(VALID));
    expect(await readDiscovery(file)).toMatchObject({ url: VALID.url, token: 'abc', path: file });
  });

  it('reports a missing file as "not running" with the start hint', async () => {
    const file = path.join(dir, 'missing.json');
    const error = await readDiscovery(file).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(LiveServerNotRunningError);
    expect((error as Error).message).toContain(file);
    expect((error as Error).message).toContain(START_HINT);
  });

  it('reports an unreadable path as a DiscoveryError', async () => {
    await expect(readDiscovery(dir)).rejects.toBeInstanceOf(DiscoveryError);
  });

  it('does not describe a protocol mismatch as unreadable', async () => {
    const file = path.join(dir, 'live.json');
    await fs.writeFile(file, JSON.stringify({ ...VALID, protocol: 2 }));
    const error = await readDiscovery(file).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(DiscoveryError);
    expect((error as Error).message).toContain('protocol 2');
    expect((error as Error).message).not.toMatch(/^Unreadable/);
  });
});
