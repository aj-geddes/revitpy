/** Locating a running Live Server through the discovery file it writes on start. */
import { readFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { LiveProtocolError, LiveUnavailableError } from './errors.js';

/** Live Server protocol version this client speaks. */
export const SUPPORTED_PROTOCOL = 1;

/** Connection details read from the discovery file. */
export interface LiveConnectionInfo {
  url: string;
  token: string;
  protocol: number;
  revitVersion: string | null;
  pid: number | null;
}

/** `$REVITPY_LIVE_DISCOVERY`, or `~/.revitpy/live.json`. */
export function discoveryPath(env: NodeJS.ProcessEnv = process.env): string {
  const override = env.REVITPY_LIVE_DISCOVERY;
  if (override !== undefined && override.trim() !== '') {
    return override;
  }
  return path.join(os.homedir(), '.revitpy', 'live.json');
}

/**
 * Read and validate the discovery file.
 *
 * @throws LiveUnavailableError when the file is missing, unreadable or invalid (the server is not running).
 * @throws LiveProtocolError when the server speaks an unsupported protocol version.
 */
export async function readDiscovery(file: string = discoveryPath()): Promise<LiveConnectionInfo> {
  let content: string;
  try {
    content = await readFile(file, 'utf8');
  } catch (error: unknown) {
    if (error instanceof Error && 'code' in error && error.code === 'ENOENT') {
      throw new LiveUnavailableError(
        `RevitPy Live Server is not running (no ${file}). Start it with the Live Server button ` +
          'on the RevitPy ribbon in Revit, or set start_live_server = true in ' +
          '%APPDATA%\\RevitPy\\settings.ini.',
      );
    }
    throw new LiveUnavailableError(`Unreadable Live Server discovery file ${file}: ${message(error)}`);
  }

  let data: unknown;
  try {
    data = JSON.parse(content);
  } catch (error: unknown) {
    throw new LiveUnavailableError(`Unreadable Live Server discovery file ${file}: ${message(error)}`);
  }

  const invalid = new LiveUnavailableError(`Invalid Live Server discovery file ${file}`);
  if (typeof data !== 'object' || data === null || Array.isArray(data)) {
    throw invalid;
  }
  const { url, token, protocol, revit_version: revitVersion, pid } = data as Record<string, unknown>;
  if (typeof url !== 'string' || !/^wss?:\/\/./.test(url)) {
    throw invalid;
  }
  if (typeof token !== 'string' || token === '') {
    throw invalid;
  }
  if (protocol !== undefined && typeof protocol !== 'number') {
    throw invalid;
  }
  const version = protocol ?? SUPPORTED_PROTOCOL;
  if (version !== SUPPORTED_PROTOCOL) {
    throw new LiveProtocolError(
      `Live Server speaks protocol ${version}; this client supports ${SUPPORTED_PROTOCOL}. ` +
        'Update @revitpy/dev-server or revitpy so they match.',
    );
  }
  return {
    url,
    token,
    protocol: version,
    revitVersion: typeof revitVersion === 'string' ? revitVersion : null,
    pid: typeof pid === 'number' ? pid : null,
  };
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
