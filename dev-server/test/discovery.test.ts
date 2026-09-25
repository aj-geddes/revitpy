import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { readDiscovery, discoveryPath } from '../src/discovery.js';
import { LiveUnavailableError, LiveProtocolError } from '../src/errors.js';
import { mkdtempSync, rmSync, writeFileSync, existsSync } from 'node:fs';
import { homedir, tmpdir } from 'node:os';
import { join } from 'node:path';

describe('discovery', () => {
  let tempDir: string;

  beforeEach(() => {
    tempDir = mkdtempSync(join(tmpdir(), 'revitpy-test-'));
  });

  afterEach(() => {
    if (existsSync(tempDir)) {
      rmSync(tempDir, { recursive: true, force: true });
    }
  });

  describe('discoveryPath', () => {
    it('uses REVITPY_LIVE_DISCOVERY when set', () => {
      const customPath = '/custom/path/discovery.json';
      const result = discoveryPath({ REVITPY_LIVE_DISCOVERY: customPath });
      expect(result).toBe(customPath);
    });

    it('uses REVITPY_LIVE_DISCOVERY when non-blank', () => {
      const customPath = '/another/path/file.json';
      const result = discoveryPath({ REVITPY_LIVE_DISCOVERY: '  ' + customPath + '  ' });
      expect(result).toBe('  ' + customPath + '  ');
    });

    it('falls back to ~/.revitpy/live.json when env is undefined', () => {
      const result = discoveryPath(undefined);
      expect(result).toBe(join(homedir(), '.revitpy', 'live.json'));
    });

    it('falls back to ~/.revitpy/live.json when env value is blank', () => {
      const result = discoveryPath({ REVITPY_LIVE_DISCOVERY: '' });
      expect(result).toBe(join(homedir(), '.revitpy', 'live.json'));
    });

    it('falls back to ~/.revitpy/live.json when env value is whitespace-only', () => {
      const result = discoveryPath({ REVITPY_LIVE_DISCOVERY: '   ' });
      expect(result).toBe(join(homedir(), '.revitpy', 'live.json'));
    });
  });

  describe('readDiscovery', () => {
    it('returns valid discovery data', async () => {
      const discoveryFile = join(tempDir, 'valid.json');
      const data = {
        url: 'wss://example.com/live',
        token: 'secret-token',
        protocol: 1,
        revit_version: '2026',
        pid: 12345,
      };
      writeFileSync(discoveryFile, JSON.stringify(data), 'utf8');

      const result = await readDiscovery(discoveryFile);
      expect(result).toEqual({
        url: 'wss://example.com/live',
        token: 'secret-token',
        protocol: 1,
        revitVersion: '2026',
        pid: 12345,
      });
    });

    it('defaults protocol to 1 when missing', async () => {
      const discoveryFile = join(tempDir, 'no-protocol.json');
      const data = {
        url: 'wss://example.com/live',
        token: 'secret-token',
        revit_version: '2026',
        pid: 12345,
      };
      writeFileSync(discoveryFile, JSON.stringify(data), 'utf8');

      const result = await readDiscovery(discoveryFile);
      expect(result.protocol).toBe(1);
    });

    it('handles missing optional fields (revitVersion, pid)', async () => {
      const discoveryFile = join(tempDir, 'minimal.json');
      const data = {
        url: 'ws://localhost:8080',
        token: 'abc123',
      };
      writeFileSync(discoveryFile, JSON.stringify(data), 'utf8');

      const result = await readDiscovery(discoveryFile);
      expect(result.revitVersion).toBeNull();
      expect(result.pid).toBeNull();
    });

    it('throws LiveUnavailableError with /not running/ for missing file', async () => {
      const missingFile = join(tempDir, 'missing.json');
      await expect(readDiscovery(missingFile)).rejects
        .toBeInstanceOf(LiveUnavailableError);
      await expect(readDiscovery(missingFile)).rejects
        .toThrow('not running');
    });

    it('throws LiveUnavailableError with /Unreadable/ for invalid JSON', async () => {
      const discoveryFile = join(tempDir, 'invalid.json');
      writeFileSync(discoveryFile, '{ invalid json }', 'utf8');

      await expect(readDiscovery(discoveryFile)).rejects
        .toBeInstanceOf(LiveUnavailableError);
      await expect(readDiscovery(discoveryFile)).rejects
        .toThrow('Unreadable');
    });

    it('throws LiveUnavailableError with /Invalid/ for array', async () => {
      const discoveryFile = join(tempDir, 'array.json');
      writeFileSync(discoveryFile, '[1, 2, 3]', 'utf8');

      await expect(readDiscovery(discoveryFile)).rejects
        .toBeInstanceOf(LiveUnavailableError);
      await expect(readDiscovery(discoveryFile)).rejects
        .toThrow('Invalid');
    });

    it('throws LiveUnavailableError with /Invalid/ for missing token', async () => {
      const discoveryFile = join(tempDir, 'no-token.json');
      const data = { url: 'ws://localhost:8080' };
      writeFileSync(discoveryFile, JSON.stringify(data), 'utf8');

      await expect(readDiscovery(discoveryFile)).rejects
        .toBeInstanceOf(LiveUnavailableError);
      await expect(readDiscovery(discoveryFile)).rejects
        .toThrow('Invalid');
    });

    it('throws LiveUnavailableError with /Invalid/ for empty token', async () => {
      const discoveryFile = join(tempDir, 'empty-token.json');
      const data = { url: 'ws://localhost:8080', token: '' };
      writeFileSync(discoveryFile, JSON.stringify(data), 'utf8');

      await expect(readDiscovery(discoveryFile)).rejects
        .toBeInstanceOf(LiveUnavailableError);
      await expect(readDiscovery(discoveryFile)).rejects
        .toThrow('Invalid');
    });

    it('throws LiveUnavailableError with /Invalid/ for http:// url', async () => {
      const discoveryFile = join(tempDir, 'http-url.json');
      const data = { url: 'http://localhost:8080', token: 'abc' };
      writeFileSync(discoveryFile, JSON.stringify(data), 'utf8');

      await expect(readDiscovery(discoveryFile)).rejects
        .toBeInstanceOf(LiveUnavailableError);
      await expect(readDiscovery(discoveryFile)).rejects
        .toThrow('Invalid');
    });

    it('throws LiveUnavailableError with /Invalid/ for string protocol', async () => {
      const discoveryFile = join(tempDir, 'string-protocol.json');
      const data = { url: 'ws://localhost:8080', token: 'abc', protocol: '1' };
      writeFileSync(discoveryFile, JSON.stringify(data), 'utf8');

      await expect(readDiscovery(discoveryFile)).rejects
        .toBeInstanceOf(LiveUnavailableError);
      await expect(readDiscovery(discoveryFile)).rejects
        .toThrow('Invalid');
    });

    it('throws LiveProtocolError for protocol 2', async () => {
      const discoveryFile = join(tempDir, 'protocol2.json');
      const data = { url: 'wss://example.com', token: 'abc', protocol: 2 };
      writeFileSync(discoveryFile, JSON.stringify(data), 'utf8');

      await expect(readDiscovery(discoveryFile)).rejects
        .toBeInstanceOf(LiveProtocolError);
    });
  });
});
