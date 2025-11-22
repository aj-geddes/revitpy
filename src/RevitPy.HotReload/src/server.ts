import express from 'express';
import { createServer } from 'http';
import { WebSocketServer } from 'ws';
import cors from 'cors';
import chalk from 'chalk';
import { FileWatcher } from './watchers/fileWatcher.js';
import { BuildSystem } from './build/buildSystem.js';
import { MessageBroker } from './communication/messageBroker.js';
import { RevitConnector } from './connectors/revitConnector.js';
import { DevMiddleware } from './middleware/devMiddleware.js';
import { AssetProcessor } from './processors/assetProcessor.js';
import type { ServerConfig, HotReloadMessage, BuildResult } from './types.js';

export class HotReloadServer {
  private app: express.Application;
  private server: import('http').Server;
  private wss: WebSocketServer;
  private fileWatcher: FileWatcher;
  private buildSystem: BuildSystem;
  private messageBroker: MessageBroker;
  private revitConnector: RevitConnector;
  private assetProcessor: AssetProcessor;
  private config: ServerConfig;
  private isRunning = false;

  constructor(config: ServerConfig) {
    this.config = {
      port: 3000,
      host: 'localhost',
      watchPaths: ['src'],
      buildConfig: {
        entry: 'src/main.py',
        outDir: 'dist',
        sourceMaps: true,
        minify: false,
        target: 'es2020'
      },
      hotReload: {
        enabled: true,
        debounceMs: 300,
        includeNodeModules: false
      },
      revit: {
        enabled: true,
        port: 5678,
        autoConnect: true
      },
      logging: {
        level: 'info',
        timestamp: true
      },
      ...config
    };

    this.setupExpress();
    this.setupWebSocket();
    this.setupServices();
  }

  private setupExpress(): void {
    this.app = express();
    this.server = createServer(this.app);

    // Middleware
    this.app.use(cors({
      origin: true,
      credentials: true
    }));
    this.app.use(express.json());
    this.app.use(express.static('public'));

    // Dev middleware for serving files with hot reload injection
    const devMiddleware = new DevMiddleware(this.config);
    this.app.use(devMiddleware.handler());

    // API routes
    this.setupRoutes();
  }

  private setupWebSocket(): void {
    this.wss = new WebSocketServer({
      server: this.server,
      path: '/ws'
    });

    this.wss.on('connection', (ws, request) => {
      const clientId = this.generateClientId();
      console.log(chalk.green(`Client connected: ${clientId}`));

      ws.on('message', async (data) => {
        try {
          const message = JSON.parse(data.toString());
          await this.handleWebSocketMessage(ws, message, clientId);
        } catch (error) {
          console.error(chalk.red('WebSocket message error:'), error);
          ws.send(JSON.stringify({
            type: 'error',
            error: 'Invalid message format'
          }));
        }
      });

      ws.on('close', () => {
        console.log(chalk.yellow(`Client disconnected: ${clientId}`));
        this.messageBroker.removeClient(clientId);
      });

      ws.on('error', (error) => {
        console.error(chalk.red(`WebSocket error for ${clientId}:`), error);
      });

      // Register client with message broker
      this.messageBroker.addClient(clientId, ws);

      // Send initial connection message
      ws.send(JSON.stringify({
        type: 'connected',
        clientId,
        timestamp: Date.now()
      }));
    });
  }

  private setupServices(): void {
    // Initialize services
    this.messageBroker = new MessageBroker();
    this.assetProcessor = new AssetProcessor(this.config);
    this.buildSystem = new BuildSystem(this.config, this.assetProcessor);
    this.fileWatcher = new FileWatcher(this.config);
    this.revitConnector = new RevitConnector(this.config.revit);

    // Set up event handlers
    this.setupEventHandlers();
  }

  private setupEventHandlers(): void {
    // File change events
    this.fileWatcher.on('change', async (filePath: string, changeType: string) => {
      console.log(chalk.blue(`File ${changeType}: ${filePath}`));

      try {
        // Determine what needs to be rebuilt
        const shouldRebuild = this.shouldTriggerRebuild(filePath, changeType);

        if (shouldRebuild) {
          const buildResult = await this.buildSystem.build();
          await this.handleBuildResult(filePath, changeType, buildResult);
        } else {
          // Just notify clients of file change
          await this.notifyClients({
            type: 'file-changed',
            file: filePath,
            changeType,
            timestamp: Date.now()
          });
        }
      } catch (error) {
        console.error(chalk.red('Build error:'), error);
        await this.notifyClients({
          type: 'build-error',
          error: error instanceof Error ? error.message : String(error),
          timestamp: Date.now()
        });
      }
    });

    // Build system events
    this.buildSystem.on('build-start', () => {
      this.notifyClients({
        type: 'build-start',
        timestamp: Date.now()
      });
    });

    this.buildSystem.on('build-complete', (result: BuildResult) => {
      this.notifyClients({
        type: 'build-complete',
        result,
        timestamp: Date.now()
      });
    });

    // Revit connector events
    this.revitConnector.on('connected', () => {
      console.log(chalk.green('Connected to Revit'));
      this.notifyClients({
        type: 'revit-connected',
        timestamp: Date.now()
      });
    });

    this.revitConnector.on('disconnected', () => {
      console.log(chalk.yellow('Disconnected from Revit'));
      this.notifyClients({
        type: 'revit-disconnected',
        timestamp: Date.now()
      });
    });

    this.revitConnector.on('message', (message: any) => {
      this.notifyClients({
        type: 'revit-message',
        data: message,
        timestamp: Date.now()
      });
    });
  }

  private setupRoutes(): void {
    // Health check
    this.app.get('/health', (req, res) => {
      res.json({
        status: 'healthy',
        uptime: process.uptime(),
        version: process.env.npm_package_version || '1.0.0',
        config: {
          hotReload: this.config.hotReload?.enabled,
          revit: this.config.revit?.enabled
        }
      });
    });

    // Build endpoint
    this.app.post('/api/build', async (req, res) => {
      try {
        const result = await this.buildSystem.build();
        res.json(result);
      } catch (error) {
        res.status(500).json({
          error: error instanceof Error ? error.message : String(error)
        });
      }
    });

    // Revit communication endpoint
    this.app.post('/api/revit/:command', async (req, res) => {
      const { command } = req.params;
      const { data } = req.body;

      try {
        const result = await this.revitConnector.sendCommand(command, data);
        res.json(result);
      } catch (error) {
        res.status(500).json({
          error: error instanceof Error ? error.message : String(error)
        });
      }
    });

    // File operations
    this.app.get('/api/files/*', async (req, res) => {
      const filePath = req.params[0];
      try {
        const content = await this.assetProcessor.processFile(filePath);
        res.setHeader('Content-Type', this.assetProcessor.getMimeType(filePath));
        res.send(content);
      } catch (error) {
        res.status(404).json({
          error: 'File not found'
        });
      }
    });
  }

  public async start(): Promise<void> {
    if (this.isRunning) {
      throw new Error('Server is already running');
    }

    try {
      // Start file watcher
      await this.fileWatcher.start();
      console.log(chalk.blue(`Watching files in: ${this.config.watchPaths?.join(', ')}`));

      // Connect to Revit if enabled
      if (this.config.revit?.enabled && this.config.revit?.autoConnect) {
        try {
          await this.revitConnector.connect();
        } catch (error) {
          console.warn(chalk.yellow('Could not connect to Revit:'), error);
        }
      }

      // Start HTTP server
      await new Promise<void>((resolve, reject) => {
        this.server.listen(this.config.port, this.config.host, (error?: Error) => {
          if (error) {
            reject(error);
          } else {
            resolve();
          }
        });
      });

      this.isRunning = true;

      console.log(chalk.green(`
🚀 RevitPy Hot Reload Server running!

   Local:    http://${this.config.host}:${this.config.port}
   WebSocket: ws://${this.config.host}:${this.config.port}/ws

   Hot reload: ${this.config.hotReload?.enabled ? '✅' : '❌'}
   Revit integration: ${this.config.revit?.enabled ? '✅' : '❌'}
      `));

    } catch (error) {
      console.error(chalk.red('Failed to start server:'), error);
      throw error;
    }
  }

  public async stop(): Promise<void> {
    if (!this.isRunning) return;

    console.log(chalk.yellow('Stopping server...'));

    // Stop services
    await Promise.all([
      this.fileWatcher.stop(),
      this.revitConnector.disconnect()
    ]);

    // Close WebSocket connections
    this.wss.clients.forEach(client => client.close());
    this.wss.close();

    // Close HTTP server
    await new Promise<void>((resolve) => {
      this.server.close(() => resolve());
    });

    this.isRunning = false;
    console.log(chalk.green('Server stopped'));
  }

  private async handleWebSocketMessage(
    ws: import('ws').WebSocket,
    message: any,
    clientId: string
  ): Promise<void> {
    switch (message.type) {
      case 'ping':
        ws.send(JSON.stringify({ type: 'pong', timestamp: Date.now() }));
        break;

      case 'build':
        try {
          const result = await this.buildSystem.build();
          ws.send(JSON.stringify({
            type: 'build-result',
            result,
            timestamp: Date.now()
          }));
        } catch (error) {
          ws.send(JSON.stringify({
            type: 'build-error',
            error: error instanceof Error ? error.message : String(error),
            timestamp: Date.now()
          }));
        }
        break;

      case 'revit-command':
        try {
          const result = await this.revitConnector.sendCommand(
            message.command,
            message.data
          );
          ws.send(JSON.stringify({
            type: 'revit-response',
            result,
            requestId: message.id,
            timestamp: Date.now()
          }));
        } catch (error) {
          ws.send(JSON.stringify({
            type: 'revit-error',
            error: error instanceof Error ? error.message : String(error),
            requestId: message.id,
            timestamp: Date.now()
          }));
        }
        break;

      default:
        ws.send(JSON.stringify({
          type: 'error',
          error: `Unknown message type: ${message.type}`,
          timestamp: Date.now()
        }));
    }
  }

  private async handleBuildResult(
    filePath: string,
    changeType: string,
    result: BuildResult
  ): Promise<void> {
    if (result.success) {
      // Determine hot reload strategy
      const reloadType = this.getReloadType(filePath, changeType);

      await this.notifyClients({
        type: 'hot-reload',
        file: filePath,
        changeType,
        reloadType,
        result,
        timestamp: Date.now()
      });

      // If connected to Revit, send reload command
      if (this.revitConnector.isConnected() && reloadType === 'full') {
        try {
          await this.revitConnector.sendCommand('reload', {
            file: filePath,
            buildResult: result
          });
        } catch (error) {
          console.warn(chalk.yellow('Failed to reload in Revit:'), error);
        }
      }
    } else {
      await this.notifyClients({
        type: 'build-error',
        file: filePath,
        error: result.error,
        timestamp: Date.now()
      });
    }
  }

  private shouldTriggerRebuild(filePath: string, changeType: string): boolean {
    // Skip rebuilds for certain file types
    const skipExtensions = ['.md', '.txt', '.log'];
    if (skipExtensions.some(ext => filePath.endsWith(ext))) {
      return false;
    }

    // Skip temporary files
    if (filePath.includes('__pycache__') || filePath.includes('.tmp')) {
      return false;
    }

    return true;
  }

  private getReloadType(filePath: string, changeType: string): 'hot' | 'full' {
    // CSS changes can use hot reload
    if (filePath.endsWith('.css') || filePath.endsWith('.scss')) {
      return 'hot';
    }

    // JavaScript/TypeScript in development can use hot reload
    if ((filePath.endsWith('.js') || filePath.endsWith('.ts')) &&
        !filePath.includes('.config.')) {
      return 'hot';
    }

    // Python changes require full reload
    if (filePath.endsWith('.py')) {
      return 'full';
    }

    // Default to hot reload for other files
    return 'hot';
  }

  private async notifyClients(message: HotReloadMessage): Promise<void> {
    await this.messageBroker.broadcast(message);
  }

  private generateClientId(): string {
    return Math.random().toString(36).substr(2, 9);
  }
}
