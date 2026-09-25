/** A long-lived connection that follows the Live Server across Revit restarts. */
import { LiveClient } from './client.js';
import type { LiveConnectionInfo } from './discovery.js';
import { discoveryPath, readDiscovery } from './discovery.js';
import { LiveUnavailableError } from './errors.js';
import type { RetryOptions } from './retry.js';
import { retry } from './retry.js';

export interface SessionOptions extends RetryOptions {
  /** Discovery file to read (default: {@link discoveryPath}). */
  discoveryFile?: string;
  /** Injectable for tests (default: `LiveClient.connect`). */
  connect?: (info: LiveConnectionInfo) => Promise<LiveClient>;
  /** Called after every successful (re)connection. */
  onConnect?: (client: LiveClient) => void;
}

/**
 * Keeps one connection to the Live Server. Whenever it needs a new connection it
 * re-reads the discovery file (a restarted server has a new port and token) and
 * retries with backoff until the server is reachable or the session is closed.
 */
export class LiveSession {
  private current: LiveClient | undefined;
  private connecting: Promise<LiveClient> | undefined;
  private closed = false;
  private readonly abort = new AbortController();

  constructor(private readonly options: SessionOptions = {}) {
    const { signal } = options;
    if (signal?.aborted) {
      this.abort.abort();
    } else {
      signal?.addEventListener(
        'abort',
        () => {
          this.abort.abort();
        },
        { once: true },
      );
    }
  }

  /** An open client, connecting (with retries) if necessary. Rejects once the session is closed. */
  client(): Promise<LiveClient> {
    if (this.closed) {
      return Promise.reject(new LiveUnavailableError('Live session is closed'));
    }
    if (this.current?.isOpen) {
      return Promise.resolve(this.current);
    }
    this.connecting ??= this.connect().finally(() => {
      this.connecting = undefined;
    });
    return this.connecting;
  }

  /**
   * Run `fn` with an open client. If the connection drops during `fn` it is
   * discarded (the next call reconnects) and the error is rethrown: the request
   * is not retried because it may already have run in Revit.
   */
  async use<T>(fn: (client: LiveClient) => Promise<T>): Promise<T> {
    const client = await this.client();
    try {
      return await fn(client);
    } catch (error: unknown) {
      if (error instanceof LiveUnavailableError) {
        if (this.current === client) {
          this.current = undefined;
        }
        await client.close();
      }
      throw error;
    }
  }

  /** Stop reconnecting and close the connection. */
  async close(): Promise<void> {
    this.closed = true;
    this.abort.abort();
    const client = this.current;
    this.current = undefined;
    await client?.close();
  }

  private async connect(): Promise<LiveClient> {
    const file = this.options.discoveryFile ?? discoveryPath();
    const open = this.options.connect ?? ((info: LiveConnectionInfo) => LiveClient.connect(info));
    const client = await retry(async () => open(await readDiscovery(file)), {
      ...this.options,
      signal: this.abort.signal,
    });
    if (this.closed) {
      await client.close();
      throw new LiveUnavailableError('Live session is closed');
    }
    const previous = this.current;
    this.current = client;
    await previous?.close();
    this.options.onConnect?.(client);
    return client;
  }
}
