/**
 * Owns the single connection to the RevitPy Live Server. Connects on demand
 * (re-reading the discovery file each time, since the token changes on every
 * server start) and tracks the last `live/status` for the status bar.
 *
 * Events: `stateChanged` (ConnectionState), `statusChanged` (LiveStatus |
 * undefined), `disconnected` (reason) when an established connection drops.
 */
import { EventEmitter } from 'node:events';
import { defaultDiscoveryPath, readDiscovery, type DiscoveryInfo } from './discovery';
import { LiveClient, type ConnectOptions } from './liveClient';
import type { LiveStatus } from './protocol';

export type ConnectionState = 'disconnected' | 'connecting' | 'connected';

export interface ConnectionSettings {
  discoveryFile?: string;
  requestTimeoutMs: number;
  connectTimeoutMs?: number;
}

export interface ConnectionDeps {
  readDiscovery: (filePath: string) => Promise<DiscoveryInfo>;
  connect: (url: string, token: string, options: ConnectOptions) => Promise<LiveClient>;
}

const defaultDeps: ConnectionDeps = {
  readDiscovery,
  connect: (url, token, options) => LiveClient.connect(url, token, options),
};

export class ConnectionManager extends EventEmitter {
  private currentState: ConnectionState = 'disconnected';
  private client: LiveClient | undefined;
  private lastStatus: LiveStatus | undefined;
  private discovery: DiscoveryInfo | undefined;
  private connecting: Promise<LiveClient> | undefined;

  constructor(
    private readonly getSettings: () => ConnectionSettings,
    private readonly deps: ConnectionDeps = defaultDeps,
  ) {
    super();
  }

  get state(): ConnectionState {
    return this.currentState;
  }

  get status(): LiveStatus | undefined {
    return this.lastStatus;
  }

  get info(): DiscoveryInfo | undefined {
    return this.discovery;
  }

  get isConnected(): boolean {
    return this.currentState === 'connected' && this.client !== undefined && this.client.isOpen;
  }

  /** Return the open client, connecting first if needed. Concurrent callers share one attempt. */
  connect(): Promise<LiveClient> {
    if (this.client?.isOpen) {
      return Promise.resolve(this.client);
    }
    if (!this.connecting) {
      this.connecting = this.open().finally(() => {
        this.connecting = undefined;
      });
    }
    return this.connecting;
  }

  /** Reconnect on demand: every command goes through here. */
  ensureClient(): Promise<LiveClient> {
    return this.connect();
  }

  async refreshStatus(): Promise<LiveStatus | undefined> {
    const client = this.client;
    if (!client?.isOpen) {
      return undefined;
    }
    const status = await client.status();
    if (this.client === client) {
      this.lastStatus = status;
      this.emit('statusChanged', status);
    }
    return status;
  }

  async disconnect(): Promise<void> {
    const client = this.client;
    this.client = undefined;
    this.discovery = undefined;
    const hadStatus = this.lastStatus !== undefined;
    this.lastStatus = undefined;
    if (client) {
      await client.close();
    }
    this.setState('disconnected');
    if (hadStatus || client) {
      this.emit('statusChanged', undefined);
    }
  }

  dispose(): void {
    this.disconnect().catch(() => undefined);
    this.removeAllListeners();
  }

  private async open(): Promise<LiveClient> {
    this.setState('connecting');
    try {
      const settings = this.getSettings();
      const info = await this.deps.readDiscovery(settings.discoveryFile || defaultDiscoveryPath());
      const client = await this.deps.connect(info.url, info.token, {
        requestTimeoutMs: settings.requestTimeoutMs,
        connectTimeoutMs: settings.connectTimeoutMs ?? 10_000,
      });
      this.client = client;
      this.discovery = info;
      client.once('close', (code: number) => {
        if (this.client !== client) {
          return; // closed by disconnect() or already replaced
        }
        this.client = undefined;
        this.discovery = undefined;
        this.lastStatus = undefined;
        this.setState('disconnected');
        this.emit('statusChanged', undefined);
        this.emit('disconnected', `Connection to Revit closed (code ${code})`);
      });
      this.setState('connected');
      try {
        await this.refreshStatus();
      } catch {
        // The connection works; status is refreshed again later.
      }
      return client;
    } catch (error) {
      this.setState('disconnected');
      throw error;
    }
  }

  private setState(state: ConnectionState): void {
    if (this.currentState !== state) {
      this.currentState = state;
      this.emit('stateChanged', state);
    }
  }
}
