/**
 * Core type definitions for RevitPy Development Server
 */

import { EventEmitter } from 'events';
import { WebSocket } from 'ws';
import { IncomingMessage } from 'http';

// Server Configuration
export interface DevServerConfig {
  // Network
  host: string;
  port: number;
  websocketPort: number;

  // Paths
  projectRoot: string;
  watchPaths: string[];
  buildOutputPath: string;

  // Performance
  debounceMs: number;
  maxReloadTime: number;
  parallelProcesses: number;

  // Features
  hotReload: HotReloadConfig;
  moduleReloader: ModuleReloaderConfig;
  uiReload: UIReloadConfig;
  errorRecovery: ErrorRecoveryConfig;
  performance: PerformanceConfig;

  // Integrations
  revit: RevitIntegrationConfig;
  vscode: VSCodeIntegrationConfig;
  webview: WebViewConfig;
}

export interface HotReloadConfig {
  enabled: boolean;
  pythonModules: boolean;
  uiComponents: boolean;
  staticAssets: boolean;
  excludePatterns: string[];
  includePatterns: string[];
  preserveState: boolean;
}

export interface ModuleReloaderConfig {
  enabled: boolean;
  safeReload: boolean;
  dependencyTracking: boolean;
  statePreservation: boolean;
  rollbackOnError: boolean;
  preReloadHooks: string[];
  postReloadHooks: string[];
}

export interface UIReloadConfig {
  enabled: boolean;
  webview2Integration: boolean;
  hmrPort: number;
  reactRefresh: boolean;
  vueHmr: boolean;
  cssHotReload: boolean;
  assetPipeline: boolean;
}

export interface ErrorRecoveryConfig {
  enabled: boolean;
  maxRetries: number;
  rollbackTimeout: number;
  syntaxErrorHandling: boolean;
  runtimeErrorHandling: boolean;
  automaticRecovery: boolean;
  userPrompting: boolean;
}

export interface PerformanceConfig {
  monitoring: boolean;
  metrics: boolean;
  profiling: boolean;
  benchmarking: boolean;
  optimization: boolean;
  caching: boolean;
  memoryManagement: boolean;
}

export interface RevitIntegrationConfig {
  enabled: boolean;
  host: string;
  port: number;
  autoConnect: boolean;
  reconnectInterval: number;
  commandTimeout: number;
}

export interface VSCodeIntegrationConfig {
  enabled: boolean;
  port: number;
  debugAdapter: boolean;
  problemMatcher: boolean;
}

export interface WebViewConfig {
  enabled: boolean;
  port: number;
  devTools: boolean;
  securityDisabled: boolean;
}

// File System Events
export interface FileChangeEvent {
  path: string;
  type: FileChangeType;
  timestamp: number;
  size?: number;
  hash?: string;
  dependencies?: string[];
  metadata?: FileMetadata;
}

export type FileChangeType = 'add' | 'change' | 'unlink' | 'addDir' | 'unlinkDir';

export interface FileMetadata {
  isDirectory: boolean;
  isFile: boolean;
  extension: string;
  mimeType: string;
  encoding?: string;
}

// Build System
export interface BuildResult {
  success: boolean;
  duration: number;
  outputFiles: BuildOutputFile[];
  errors: BuildError[];
  warnings: BuildWarning[];
  stats: BuildStats;
  sourceMap?: string;
  dependencies?: string[];
}

export interface BuildOutputFile {
  path: string;
  size: number;
  hash: string;
  type: 'js' | 'css' | 'html' | 'asset' | 'python';
  sourcePath?: string;
}

export interface BuildError {
  message: string;
  file?: string;
  line?: number;
  column?: number;
  severity: 'error' | 'warning';
  code?: string;
  stack?: string;
}

export interface BuildWarning {
  message: string;
  file?: string;
  line?: number;
  column?: number;
  code?: string;
}

export interface BuildStats {
  totalFiles: number;
  totalSize: number;
  buildTime: number;
  bundleSize?: number;
  assetCount: number;
  warnings: number;
  errors: number;
}

// Module System
export interface PythonModule {
  name: string;
  path: string;
  dependencies: string[];
  dependents: string[];
  lastModified: number;
  hash: string;
  state?: any;
  exports?: Record<string, any>;
}

export interface ModuleReloadResult {
  success: boolean;
  module: string;
  duration: number;
  statePreserved: boolean;
  dependenciesReloaded: string[];
  errors?: ReloadError[];
}

export interface ReloadError {
  type: 'syntax' | 'runtime' | 'dependency';
  message: string;
  file?: string;
  line?: number;
  stack?: string;
}

// Communication
export interface WebSocketMessage {
  id: string;
  type: MessageType;
  timestamp: number;
  data?: any;
  error?: string;
  clientId?: string;
}

export type MessageType =
  | 'file-changed'
  | 'build-start'
  | 'build-complete'
  | 'build-error'
  | 'module-reload'
  | 'ui-reload'
  | 'error-recovery'
  | 'performance-metrics'
  | 'client-connected'
  | 'client-disconnected'
  | 'revit-command'
  | 'revit-response'
  | 'vscode-message';

export interface Client {
  id: string;
  type: ClientType;
  websocket: WebSocket;
  request: IncomingMessage;
  connectedAt: Date;
  lastActivity: Date;
  subscriptions: string[];
  capabilities: ClientCapability[];
}

export type ClientType = 'revit' | 'vscode' | 'webview' | 'browser' | 'cli';

export type ClientCapability =
  | 'python-execution'
  | 'ui-rendering'
  | 'file-operations'
  | 'debugging'
  | 'profiling';

// UI System
export interface UIComponent {
  id: string;
  path: string;
  type: ComponentType;
  dependencies: string[];
  state?: ComponentState;
  lastRender?: Date;
}

export type ComponentType = 'react' | 'vue' | 'svelte' | 'html' | 'webview';

export interface ComponentState {
  props?: Record<string, any>;
  state?: Record<string, any>;
  context?: Record<string, any>;
}

export interface UIReloadResult {
  success: boolean;
  component: string;
  type: ReloadType;
  duration: number;
  statePreserved: boolean;
  affectedComponents: string[];
}

export type ReloadType = 'hot' | 'full' | 'refresh';

// Performance Monitoring
export interface PerformanceMetrics {
  timestamp: number;
  buildTime: number;
  reloadTime: number;
  memoryUsage: MemoryUsage;
  cpuUsage: CPUUsage;
  networkLatency: number;
  fileSystemLatency: number;
  clientCount: number;
  errorRate: number;
}

export interface MemoryUsage {
  rss: number;
  heapUsed: number;
  heapTotal: number;
  external: number;
}

export interface CPUUsage {
  user: number;
  system: number;
  percent: number;
}

// Error Recovery
export interface RecoveryAction {
  id: string;
  type: RecoveryType;
  description: string;
  automatic: boolean;
  timeoutMs: number;
  execute: () => Promise<boolean>;
  rollback?: () => Promise<void>;
}

export type RecoveryType =
  | 'reload-module'
  | 'restart-server'
  | 'clear-cache'
  | 'restore-backup'
  | 'skip-file'
  | 'prompt-user';

export interface ErrorContext {
  error: Error;
  file?: string;
  operation: string;
  timestamp: Date;
  clientId?: string;
  attempts: number;
  resolved: boolean;
}

// Asset Processing
export interface Asset {
  path: string;
  type: AssetType;
  size: number;
  hash: string;
  dependencies: string[];
  processed: boolean;
  optimized: boolean;
}

export type AssetType = 'javascript' | 'typescript' | 'css' | 'html' | 'image' | 'font' | 'other';

export interface ProcessingResult {
  success: boolean;
  originalSize: number;
  processedSize: number;
  optimizations: string[];
  sourceMaps: boolean;
  duration: number;
}

// Events
export interface DevServerEvents {
  'server-started': () => void;
  'server-stopped': () => void;
  'client-connected': (client: Client) => void;
  'client-disconnected': (clientId: string) => void;
  'file-changed': (event: FileChangeEvent) => void;
  'build-started': (files: string[]) => void;
  'build-completed': (result: BuildResult) => void;
  'module-reloaded': (result: ModuleReloadResult) => void;
  'ui-reloaded': (result: UIReloadResult) => void;
  'error-occurred': (context: ErrorContext) => void;
  'recovery-executed': (action: RecoveryAction) => void;
  'performance-update': (metrics: PerformanceMetrics) => void;
}

// Service Interfaces
export interface FileWatcherService extends EventEmitter {
  start(): Promise<void>;
  stop(): Promise<void>;
  addPath(path: string): void;
  removePath(path: string): void;
  isWatching(): boolean;
  getStats(): WatcherStats;
}

export interface WatcherStats {
  watchedFiles: number;
  ignoredFiles: number;
  queuedChanges: number;
  processingTime: number;
}

export interface BuildService extends EventEmitter {
  build(files?: string[]): Promise<BuildResult>;
  rebuild(): Promise<BuildResult>;
  getBuildStats(): BuildStats;
  clearCache(): Promise<void>;
}

export interface ModuleReloaderService extends EventEmitter {
  reloadModule(path: string): Promise<ModuleReloadResult>;
  reloadDependencies(path: string): Promise<ModuleReloadResult[]>;
  preserveState(module: string, state: any): void;
  restoreState(module: string): any;
  getDependencyGraph(): Record<string, string[]>;
}

export interface UIReloaderService extends EventEmitter {
  reloadComponent(path: string): Promise<UIReloadResult>;
  hotReplaceModule(path: string): Promise<UIReloadResult>;
  refreshPage(): Promise<void>;
  injectScript(script: string): Promise<void>;
}

export interface CommunicationService extends EventEmitter {
  broadcast(message: WebSocketMessage): Promise<void>;
  send(clientId: string, message: WebSocketMessage): Promise<void>;
  subscribe(clientId: string, channel: string): void;
  unsubscribe(clientId: string, channel: string): void;
  getClients(): Client[];
  getClient(id: string): Client | undefined;
}

export interface PerformanceService extends EventEmitter {
  startMonitoring(): void;
  stopMonitoring(): void;
  getMetrics(): PerformanceMetrics;
  benchmark(operation: string, fn: () => Promise<void>): Promise<number>;
  profile(name: string): ProfileSession;
}

export interface ProfileSession {
  end(): PerformanceReport;
}

export interface PerformanceReport {
  name: string;
  duration: number;
  memoryDelta: number;
  cpuUsage: number;
  details: Record<string, any>;
}

// Configuration validation
export interface ConfigValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

// Cache System
export interface CacheEntry<T = any> {
  key: string;
  value: T;
  timestamp: number;
  ttl: number;
  size: number;
  hits: number;
}

export interface CacheOptions {
  maxSize: number;
  maxAge: number;
  cleanupInterval: number;
}

// Plugin System
export interface Plugin {
  name: string;
  version: string;
  initialize(server: DevServer): Promise<void>;
  dispose(): Promise<void>;
}

export interface DevServer extends EventEmitter {
  start(): Promise<void>;
  stop(): Promise<void>;
  getConfig(): DevServerConfig;
  getServices(): Record<string, any>;
  broadcast(message: WebSocketMessage): Promise<void>;
}
