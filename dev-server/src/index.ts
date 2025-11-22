/**
 * RevitPy Development Server
 * High-performance hot-reload development server for RevitPy
 *
 * Features:
 * - <500ms Python module reload
 * - <200ms UI component hot-reload
 * - WebSocket communication with Revit, VS Code, and WebView2
 * - Dependency tracking and state preservation
 * - Error recovery and rollback
 * - Performance monitoring and optimization
 */

export { DevServer } from './core/DevServer.js';
export { FileWatcherService } from './watchers/FileWatcher.js';
export { CommunicationService } from './communication/WebSocketManager.js';
export { ModuleReloaderService } from './python/ModuleReloader.js';
export { UIReloaderService } from './ui/UIReloader.js';
export { BuildService } from './build/BuildSystem.js';
export { PerformanceService } from './performance/PerformanceMonitor.js';
export { ErrorRecoveryService } from './recovery/ErrorRecovery.js';
export { AssetProcessor } from './processors/AssetProcessor.js';

// Connectors
export { RevitConnector } from './connectors/RevitConnector.js';
export { VSCodeConnector } from './connectors/VSCodeConnector.js';
export { WebViewConnector } from './connectors/WebViewConnector.js';

// Utilities
export { ConfigValidator } from './utils/ConfigValidator.js';
export { Logger, PerformanceTimer, PerformanceProfiler } from './utils/Logger.js';

// Types
export type * from './types/index.js';

// Default export
export { DevServer as default } from './core/DevServer.js';
