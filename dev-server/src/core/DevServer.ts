/**
 * RevitPy Development Server - Core Server Implementation
 * High-performance hot-reload server with <500ms Python and <200ms UI reload times
 */

import { EventEmitter } from 'events';
import { createServer, Server as HttpServer } from 'http';
import { WebSocketServer } from 'ws';
import express, { Application } from 'express';
import cors from 'cors';
import helmet from 'helmet';
import compression from 'compression';
import { RateLimiterMemory } from 'rate-limiter-flexible';
import pino from 'pino';
import { performance } from 'perf_hooks';

import type {
  DevServerConfig,
  DevServerEvents,
  Client,
  WebSocketMessage,
  PerformanceMetrics,
  BuildResult,
  ModuleReloadResult,
  UIReloadResult
} from '../types/index.js';

import { FileWatcherService } from '../watchers/FileWatcher.js';
import { CommunicationService } from '../communication/WebSocketManager.js';
import { BuildService } from '../build/BuildSystem.js';
import { ModuleReloaderService } from '../python/ModuleReloader.js';
import { UIReloaderService } from '../ui/UIReloader.js';
import { PerformanceService } from '../performance/PerformanceMonitor.js';
import { ErrorRecoveryService } from '../recovery/ErrorRecovery.js';
import { AssetProcessor } from '../processors/AssetProcessor.js';
import { RevitConnector } from '../connectors/RevitConnector.js';
import { VSCodeConnector } from '../connectors/VSCodeConnector.js';
import { WebViewConnector } from '../connectors/WebViewConnector.js';
import { ConfigValidator } from '../utils/ConfigValidator.js';
import { Logger } from '../utils/Logger.js';

export class DevServer extends EventEmitter {
  private config: DevServerConfig;
  private logger: pino.Logger;
  private app: Application;
  private server: HttpServer;
  private wss: WebSocketServer;
  private rateLimiter: RateLimiterMemory;

  // Core Services
  private fileWatcher: FileWatcherService;
  private communication: CommunicationService;
  private buildService: BuildService;
  private moduleReloader: ModuleReloaderService;
  private uiReloader: UIReloaderService;
  private performance: PerformanceService;
  private errorRecovery: ErrorRecoveryService;
  private assetProcessor: AssetProcessor;

  // Connectors
  private revitConnector: RevitConnector;
  private vscodeConnector: VSCodeConnector;
  private webviewConnector: WebViewConnector;

  // State
  private isRunning = false;
  private startTime: number = 0;
  private lastReloadTime: number = 0;
  private reloadCount = 0;

  constructor(config: DevServerConfig) {
    super();
    this.config = this.validateAndNormalizeConfig(config);
    this.logger = Logger.create('DevServer', this.config.performance.monitoring);

    this.setupExpress();
    this.setupWebSocket();
    this.setupRateLimiting();
    this.initializeServices();
    this.setupEventHandlers();

    this.logger.info('RevitPy Development Server initialized', {
      config: {
        host: this.config.host,
        port: this.config.port,
        hotReload: this.config.hotReload.enabled,
        modules: this.config.moduleReloader.enabled,
        ui: this.config.uiReload.enabled
      }
    });
  }

  /**
   * Start the development server
   */
  async start(): Promise<void> {
    if (this.isRunning) {
      throw new Error('DevServer is already running');
    }

    this.startTime = performance.now();
    this.logger.info('Starting RevitPy Development Server...');

    try {
      // Start performance monitoring first
      if (this.config.performance.monitoring) {
        await this.performance.startMonitoring();
        this.logger.debug('Performance monitoring started');
      }

      // Initialize error recovery
      await this.errorRecovery.initialize();
      this.logger.debug('Error recovery system initialized');

      // Start file watcher
      await this.fileWatcher.start();
      this.logger.info(`File watcher started for paths: ${this.config.watchPaths.join(', ')}`);

      // Start build system
      await this.buildService.initialize();
      this.logger.debug('Build system initialized');

      // Initialize module reloader
      if (this.config.moduleReloader.enabled) {
        await this.moduleReloader.initialize();
        this.logger.debug('Python module reloader initialized');
      }

      // Initialize UI reloader
      if (this.config.uiReload.enabled) {
        await this.uiReloader.initialize();
        this.logger.debug('UI hot-reload system initialized');
      }

      // Start connectors
      await this.startConnectors();

      // Start HTTP server
      await this.startHttpServer();

      // Start WebSocket server
      await this.startWebSocketServer();

      const startupTime = Math.round(performance.now() - this.startTime);
      this.isRunning = true;

      this.logger.info(`🚀 RevitPy Development Server started in ${startupTime}ms`, {
        local: `http://${this.config.host}:${this.config.port}`,
        websocket: `ws://${this.config.host}:${this.config.websocketPort}`,
        features: {
          hotReload: this.config.hotReload.enabled,
          pythonModules: this.config.moduleReloader.enabled,
          uiComponents: this.config.uiReload.enabled,
          errorRecovery: this.config.errorRecovery.enabled,
          performance: this.config.performance.monitoring
        },
        connectors: {
          revit: this.config.revit.enabled,
          vscode: this.config.vscode.enabled,
          webview: this.config.webview.enabled
        }
      });

      this.emit('server-started');
      await this.broadcast({
        id: this.generateId(),
        type: 'server-started',
        timestamp: Date.now(),
        data: { startupTime }
      });

    } catch (error) {
      this.logger.error('Failed to start server', { error: error.message, stack: error.stack });
      await this.stop();
      throw error;
    }
  }

  /**
   * Stop the development server
   */
  async stop(): Promise<void> {
    if (!this.isRunning) return;

    this.logger.info('Stopping RevitPy Development Server...');
    const stopStart = performance.now();

    try {
      // Notify clients of shutdown
      await this.broadcast({
        id: this.generateId(),
        type: 'server-stopping',
        timestamp: Date.now()
      });

      // Stop services in reverse order
      await Promise.allSettled([
        this.stopConnectors(),
        this.performance?.stopMonitoring(),
        this.uiReloader?.dispose(),
        this.moduleReloader?.dispose(),
        this.buildService?.dispose(),
        this.fileWatcher?.stop()
      ]);

      // Close WebSocket connections
      if (this.wss) {
        this.wss.clients.forEach(ws => ws.close(1000, 'Server shutdown'));
        this.wss.close();
      }

      // Close HTTP server
      if (this.server) {
        await new Promise<void>((resolve) => {
          this.server.close(() => resolve());
        });
      }

      const stopTime = Math.round(performance.now() - stopStart);
      this.isRunning = false;

      this.logger.info(`Server stopped in ${stopTime}ms`);
      this.emit('server-stopped');

    } catch (error) {
      this.logger.error('Error during shutdown', { error: error.message });
      throw error;
    }
  }

  /**
   * Get server configuration
   */
  getConfig(): DevServerConfig {
    return { ...this.config };
  }

  /**
   * Get all services
   */
  getServices(): Record<string, any> {
    return {
      fileWatcher: this.fileWatcher,
      communication: this.communication,
      build: this.buildService,
      moduleReloader: this.moduleReloader,
      uiReloader: this.uiReloader,
      performance: this.performance,
      errorRecovery: this.errorRecovery,
      assetProcessor: this.assetProcessor
    };
  }

  /**
   * Broadcast message to all clients
   */
  async broadcast(message: WebSocketMessage): Promise<void> {
    await this.communication.broadcast(message);
  }

  /**
   * Get connected clients
   */
  getClients(): Client[] {
    return this.communication.getClients();
  }

  /**
   * Get performance metrics
   */
  getPerformanceMetrics(): PerformanceMetrics {
    return this.performance.getMetrics();
  }

  /**
   * Manual rebuild trigger
   */
  async rebuild(files?: string[]): Promise<BuildResult> {
    this.logger.info('Manual rebuild triggered', { files });
    return await this.buildService.build(files);
  }

  /**
   * Manual module reload trigger
   */
  async reloadModule(path: string): Promise<ModuleReloadResult> {
    this.logger.info('Manual module reload triggered', { path });
    return await this.moduleReloader.reloadModule(path);
  }

  /**
   * Manual UI reload trigger
   */
  async reloadUI(path?: string): Promise<UIReloadResult> {
    this.logger.info('Manual UI reload triggered', { path });
    if (path) {
      return await this.uiReloader.reloadComponent(path);
    } else {
      await this.uiReloader.refreshPage();
      return {
        success: true,
        component: 'all',
        type: 'full',
        duration: 0,
        statePreserved: false,
        affectedComponents: []
      };
    }
  }

  // Private Methods

  private validateAndNormalizeConfig(config: DevServerConfig): DevServerConfig {
    const validator = new ConfigValidator();
    const result = validator.validate(config);

    if (!result.valid) {
      const error = new Error(`Invalid configuration: ${result.errors.join(', ')}`);
      this.logger?.error('Configuration validation failed', { errors: result.errors });
      throw error;
    }

    if (result.warnings.length > 0) {
      this.logger?.warn('Configuration warnings', { warnings: result.warnings });
    }

    return validator.normalize(config);
  }

  private setupExpress(): void {
    this.app = express();

    // Security middleware
    this.app.use(helmet({
      contentSecurityPolicy: false, // Allow inline scripts for hot reload
      crossOriginResourcePolicy: { policy: 'cross-origin' }
    }));

    // Basic middleware
    this.app.use(compression());
    this.app.use(cors({
      origin: true,
      credentials: true
    }));

    this.app.use(express.json({ limit: '10mb' }));
    this.app.use(express.urlencoded({ extended: true, limit: '10mb' }));

    // Setup routes
    this.setupRoutes();
  }

  private setupWebSocket(): void {
    this.server = createServer(this.app);
    this.wss = new WebSocketServer({
      server: this.server,
      path: '/ws',
      clientTracking: true
    });
  }

  private setupRateLimiting(): void {
    this.rateLimiter = new RateLimiterMemory({
      keyGenerator: (req) => req.ip,
      points: 100, // Number of requests
      duration: 60, // Per 60 seconds
    });
  }

  private initializeServices(): void {
    this.fileWatcher = new FileWatcherService(this.config);
    this.communication = new CommunicationService(this.wss, this.logger);
    this.buildService = new BuildService(this.config, this.logger);
    this.assetProcessor = new AssetProcessor(this.config, this.logger);
    this.performance = new PerformanceService(this.config, this.logger);
    this.errorRecovery = new ErrorRecoveryService(this.config, this.logger);

    if (this.config.moduleReloader.enabled) {
      this.moduleReloader = new ModuleReloaderService(this.config, this.logger);
    }

    if (this.config.uiReload.enabled) {
      this.uiReloader = new UIReloaderService(this.config, this.logger);
    }

    // Initialize connectors
    if (this.config.revit.enabled) {
      this.revitConnector = new RevitConnector(this.config.revit, this.logger);
    }

    if (this.config.vscode.enabled) {
      this.vscodeConnector = new VSCodeConnector(this.config.vscode, this.logger);
    }

    if (this.config.webview.enabled) {
      this.webviewConnector = new WebViewConnector(this.config.webview, this.logger);
    }
  }

  private setupEventHandlers(): void {
    // File change events
    this.fileWatcher.on('file-changed', async (event) => {
      await this.handleFileChange(event);
    });

    // Build events
    this.buildService.on('build-started', (files) => {
      this.broadcast({
        id: this.generateId(),
        type: 'build-start',
        timestamp: Date.now(),
        data: { files }
      });
    });

    this.buildService.on('build-completed', async (result) => {
      await this.handleBuildComplete(result);
    });

    // Module reload events
    if (this.moduleReloader) {
      this.moduleReloader.on('module-reloaded', async (result) => {
        await this.handleModuleReload(result);
      });
    }

    // UI reload events
    if (this.uiReloader) {
      this.uiReloader.on('ui-reloaded', async (result) => {
        await this.handleUIReload(result);
      });
    }

    // Error events
    this.errorRecovery.on('error-recovered', (action) => {
      this.broadcast({
        id: this.generateId(),
        type: 'error-recovery',
        timestamp: Date.now(),
        data: action
      });
    });

    // Performance events
    this.performance.on('performance-update', (metrics) => {
      this.broadcast({
        id: this.generateId(),
        type: 'performance-metrics',
        timestamp: Date.now(),
        data: metrics
      });
    });

    // Communication events
    this.communication.on('client-connected', (client) => {
      this.logger.info('Client connected', {
        id: client.id,
        type: client.type,
        capabilities: client.capabilities
      });
      this.emit('client-connected', client);
    });

    this.communication.on('client-disconnected', (clientId) => {
      this.logger.info('Client disconnected', { id: clientId });
      this.emit('client-disconnected', clientId);
    });
  }

  private setupRoutes(): void {
    // Health check
    this.app.get('/health', (req, res) => {
      const metrics = this.performance?.getMetrics();
      res.json({
        status: 'healthy',
        uptime: process.uptime(),
        version: process.env.npm_package_version || '1.0.0',
        isRunning: this.isRunning,
        startTime: this.startTime,
        reloadCount: this.reloadCount,
        clients: this.communication?.getClients()?.length || 0,
        metrics
      });
    });

    // API routes
    this.app.post('/api/build', async (req, res) => {
      try {
        const result = await this.buildService.build(req.body.files);
        res.json(result);
      } catch (error) {
        res.status(500).json({ error: error.message });
      }
    });

    this.app.post('/api/reload/module', async (req, res) => {
      try {
        const result = await this.moduleReloader.reloadModule(req.body.path);
        res.json(result);
      } catch (error) {
        res.status(500).json({ error: error.message });
      }
    });

    this.app.post('/api/reload/ui', async (req, res) => {
      try {
        const result = await this.uiReloader.reloadComponent(req.body.path);
        res.json(result);
      } catch (error) {
        res.status(500).json({ error: error.message });
      }
    });

    this.app.get('/api/metrics', (req, res) => {
      res.json(this.performance.getMetrics());
    });

    this.app.get('/api/clients', (req, res) => {
      res.json(this.communication.getClients());
    });
  }

  private async startHttpServer(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.server.listen(this.config.port, this.config.host, (error?: Error) => {
        if (error) {
          reject(error);
        } else {
          resolve();
        }
      });
    });
  }

  private async startWebSocketServer(): Promise<void> {
    return new Promise((resolve) => {
      this.communication.initialize();
      resolve();
    });
  }

  private async startConnectors(): Promise<void> {
    const promises: Promise<void>[] = [];

    if (this.revitConnector) {
      promises.push(this.revitConnector.connect());
    }

    if (this.vscodeConnector) {
      promises.push(this.vscodeConnector.connect());
    }

    if (this.webviewConnector) {
      promises.push(this.webviewConnector.connect());
    }

    await Promise.allSettled(promises);
  }

  private async stopConnectors(): Promise<void> {
    const promises: Promise<void>[] = [];

    if (this.revitConnector) {
      promises.push(this.revitConnector.disconnect());
    }

    if (this.vscodeConnector) {
      promises.push(this.vscodeConnector.disconnect());
    }

    if (this.webviewConnector) {
      promises.push(this.webviewConnector.disconnect());
    }

    await Promise.allSettled(promises);
  }

  private async handleFileChange(event: any): Promise<void> {
    const startTime = performance.now();

    try {
      this.logger.debug('File change detected', { path: event.path, type: event.type });

      // Determine reload strategy based on file type
      const reloadStrategy = this.determineReloadStrategy(event.path);

      switch (reloadStrategy) {
        case 'python-module':
          if (this.moduleReloader) {
            await this.moduleReloader.reloadModule(event.path);
          }
          break;

        case 'ui-component':
          if (this.uiReloader) {
            await this.uiReloader.reloadComponent(event.path);
          }
          break;

        case 'static-asset':
          await this.buildService.build([event.path]);
          break;

        case 'full-rebuild':
          await this.buildService.rebuild();
          break;
      }

      const duration = Math.round(performance.now() - startTime);
      this.lastReloadTime = duration;
      this.reloadCount++;

      this.logger.debug('File change processed', {
        path: event.path,
        strategy: reloadStrategy,
        duration
      });

    } catch (error) {
      this.logger.error('Error handling file change', {
        path: event.path,
        error: error.message
      });

      await this.errorRecovery.handleError(error, {
        operation: 'file-change',
        file: event.path
      });
    }
  }

  private determineReloadStrategy(filePath: string): string {
    if (filePath.endsWith('.py')) return 'python-module';
    if (filePath.match(/\.(tsx?|jsx?|vue|svelte)$/)) return 'ui-component';
    if (filePath.match(/\.(css|scss|sass|less)$/)) return 'ui-component';
    if (filePath.match(/\.(html|json|yaml|yml)$/)) return 'static-asset';
    return 'full-rebuild';
  }

  private async handleBuildComplete(result: BuildResult): Promise<void> {
    await this.broadcast({
      id: this.generateId(),
      type: 'build-complete',
      timestamp: Date.now(),
      data: result
    });
  }

  private async handleModuleReload(result: ModuleReloadResult): Promise<void> {
    await this.broadcast({
      id: this.generateId(),
      type: 'module-reload',
      timestamp: Date.now(),
      data: result
    });
  }

  private async handleUIReload(result: UIReloadResult): Promise<void> {
    await this.broadcast({
      id: this.generateId(),
      type: 'ui-reload',
      timestamp: Date.now(),
      data: result
    });
  }

  private generateId(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }
}
