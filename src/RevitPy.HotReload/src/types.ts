export interface ServerConfig {
  port?: number;
  host?: string;
  watchPaths?: string[];
  buildConfig?: BuildConfig;
  hotReload?: HotReloadConfig;
  revit?: RevitConfig;
  logging?: LoggingConfig;
}

export interface BuildConfig {
  entry: string;
  outDir: string;
  sourceMaps?: boolean;
  minify?: boolean;
  target?: string;
  external?: string[];
  define?: Record<string, string>;
  plugins?: string[];
}

export interface HotReloadConfig {
  enabled: boolean;
  debounceMs?: number;
  includeNodeModules?: boolean;
  excludePatterns?: string[];
  port?: number;
}

export interface RevitConfig {
  enabled: boolean;
  port: number;
  host?: string;
  autoConnect?: boolean;
  reconnectInterval?: number;
  timeout?: number;
}

export interface LoggingConfig {
  level: 'debug' | 'info' | 'warn' | 'error';
  timestamp?: boolean;
  colorize?: boolean;
  file?: string;
}

export interface BuildResult {
  success: boolean;
  outputFiles?: OutputFile[];
  errors?: BuildError[];
  warnings?: BuildWarning[];
  stats?: BuildStats;
  time?: number;
}

export interface OutputFile {
  path: string;
  contents: Buffer;
  size: number;
  hash?: string;
}

export interface BuildError {
  message: string;
  file?: string;
  line?: number;
  column?: number;
  stack?: string;
}

export interface BuildWarning {
  message: string;
  file?: string;
  line?: number;
  column?: number;
}

export interface BuildStats {
  totalTime: number;
  bundleSize: number;
  assetCount: number;
  chunkCount: number;
}

export interface HotReloadMessage {
  type: string;
  timestamp: number;
  [key: string]: any;
}

export interface FileChangeEvent {
  path: string;
  type: 'add' | 'change' | 'unlink' | 'addDir' | 'unlinkDir';
  stats?: import('fs').Stats;
}

export interface RevitMessage {
  id: string;
  type: string;
  command?: string;
  data?: any;
  error?: string;
  timestamp: number;
}

export interface Client {
  id: string;
  ws: import('ws').WebSocket;
  lastSeen: Date;
  subscriptions: string[];
}

export interface ProcessResult {
  success: boolean;
  output?: any;
  error?: string;
  time?: number;
}

export interface AssetInfo {
  path: string;
  size: number;
  hash: string;
  type: 'script' | 'style' | 'asset' | 'html';
  dependencies?: string[];
}

export interface WatcherOptions {
  paths: string[];
  ignored?: string[];
  debounceMs?: number;
  followSymlinks?: boolean;
  usePolling?: boolean;
  interval?: number;
}

export interface DevMiddlewareOptions {
  publicPath?: string;
  writeToDisk?: boolean;
  index?: string | boolean;
  headers?: Record<string, string>;
  stats?: boolean;
}

export interface RevitConnectionInfo {
  connected: boolean;
  version?: string;
  processId?: number;
  lastActivity?: Date;
  capabilities?: string[];
}

export interface PluginConfig {
  name: string;
  enabled: boolean;
  options?: Record<string, any>;
}

export interface BuildPlugin {
  name: string;
  setup?: (build: any) => void | Promise<void>;
  transform?: (code: string, id: string) => string | Promise<string>;
  resolveId?: (id: string, importer?: string) => string | Promise<string | null>;
  load?: (id: string) => string | Promise<string | null>;
  generateBundle?: (options: any, bundle: any) => void | Promise<void>;
}

export interface HotReloadPlugin {
  name: string;
  handleUpdate?: (update: HotReloadMessage) => boolean | Promise<boolean>;
  handleError?: (error: BuildError) => void | Promise<void>;
  dispose?: () => void | Promise<void>;
}

export interface CacheEntry<T = any> {
  key: string;
  value: T;
  timestamp: number;
  size: number;
  dependencies?: string[];
}

export interface CacheOptions {
  maxSize?: number;
  maxAge?: number;
  checkPeriod?: number;
}

export interface PerformanceMetrics {
  buildTime: number;
  bundleSize: number;
  memoryUsage: NodeJS.MemoryUsage;
  cpuUsage?: NodeJS.CpuUsage;
  filesProcessed: number;
  cacheHitRate: number;
}

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

export interface Logger {
  debug(message: string, ...args: any[]): void;
  info(message: string, ...args: any[]): void;
  warn(message: string, ...args: any[]): void;
  error(message: string, ...args: any[]): void;
  setLevel(level: LogLevel): void;
}