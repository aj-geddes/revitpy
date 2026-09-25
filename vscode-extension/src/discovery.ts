/**
 * The discovery file the RevitPy Live Server writes when it starts
 * (`~/.revitpy/live.json`, or `REVITPY_LIVE_DISCOVERY`). It carries the
 * server URL and the bearer token, which changes on every server start.
 */
import { promises as fs } from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { SUPPORTED_PROTOCOL } from './protocol';

export interface DiscoveryInfo {
  url: string;
  token: string;
  protocol: number;
  pid?: number;
  revitVersion?: string;
  startedAt?: string;
  path: string;
}

/** No discovery file: the Live Server is not running. */
export class LiveServerNotRunningError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'LiveServerNotRunningError';
  }
}

/** The discovery file exists but is unreadable, invalid or from an incompatible server. */
export class DiscoveryError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'DiscoveryError';
  }
}

export const START_HINT =
  'Start it from the RevitPy ribbon in Revit (Live Server button), or set start_live_server = true in %APPDATA%\\RevitPy\\settings.ini.';

export function defaultDiscoveryPath(
  env: NodeJS.ProcessEnv = process.env,
  home: string = os.homedir(),
): string {
  const override = env.REVITPY_LIVE_DISCOVERY;
  if (override && override.trim() !== '') {
    return override;
  }
  return path.join(home, '.revitpy', 'live.json');
}

export function parseDiscovery(text: string, filePath: string): DiscoveryInfo {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : String(e);
    throw new DiscoveryError(`Unreadable Live Server discovery file ${filePath}: ${message}`);
  }

  if (typeof data !== 'object' || data === null || Array.isArray(data)) {
    throw new DiscoveryError(`Invalid Live Server discovery file ${filePath}: expected a JSON object`);
  }

  const { url, token, protocol, pid, revit_version, started_at } = data as Record<string, unknown>;

  if (typeof url !== 'string' || !(url.startsWith('ws://') || url.startsWith('wss://'))) {
    throw new DiscoveryError(`Invalid Live Server discovery file ${filePath}: "url" must be a ws:// or wss:// URL`);
  }
  if (typeof token !== 'string' || token === '') {
    throw new DiscoveryError(`Invalid Live Server discovery file ${filePath}: "token" must be a non-empty string`);
  }

  const version = protocol === undefined ? SUPPORTED_PROTOCOL : protocol;
  if (version !== SUPPORTED_PROTOCOL) {
    throw new DiscoveryError(
      `Live Server speaks protocol ${String(version)}; this extension supports ${SUPPORTED_PROTOCOL}. ` +
        'Update the RevitPy extension or the revitpy package in Revit.',
    );
  }

  const info: DiscoveryInfo = { url, token, protocol: SUPPORTED_PROTOCOL, path: filePath };
  if (typeof pid === 'number') {
    info.pid = pid;
  }
  if (typeof revit_version === 'string') {
    info.revitVersion = revit_version;
  } else if (typeof revit_version === 'number') {
    info.revitVersion = String(revit_version);
  }
  if (typeof started_at === 'string') {
    info.startedAt = started_at;
  }
  return info;
}

export async function readDiscovery(filePath: string = defaultDiscoveryPath()): Promise<DiscoveryInfo> {
  let text: string;
  try {
    text = await fs.readFile(filePath, 'utf8');
  } catch (err: unknown) {
    if ((err as NodeJS.ErrnoException | undefined)?.code === 'ENOENT') {
      throw new LiveServerNotRunningError(`RevitPy Live Server is not running (no ${filePath}). ${START_HINT}`);
    }
    const message = err instanceof Error ? err.message : String(err);
    throw new DiscoveryError(`Unreadable Live Server discovery file ${filePath}: ${message}`);
  }
  return parseDiscovery(text, filePath);
}
