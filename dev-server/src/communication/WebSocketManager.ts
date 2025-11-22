/**
 * WebSocket Communication Service
 * High-performance multi-client WebSocket manager with message routing
 */

import { EventEmitter } from 'events';
import { WebSocketServer, WebSocket } from 'ws';
import { IncomingMessage } from 'http';
import { performance } from 'perf_hooks';
import pino from 'pino';
import { v4 as uuidv4 } from 'uuid';

import type {
  Client,
  ClientType,
  ClientCapability,
  WebSocketMessage,
  MessageType
} from '../types/index.js';

interface MessageHandler {
  type: MessageType;
  handler: (client: Client, message: WebSocketMessage) => Promise<void>;
}

interface ClientSubscription {
  clientId: string;
  channels: Set<string>;
  filters: Set<string>;
}

interface MessageQueue {
  [clientId: string]: {
    messages: WebSocketMessage[];
    processing: boolean;
  };
}

interface ConnectionStats {
  totalConnections: number;
  activeConnections: number;
  messagesSent: number;
  messagesReceived: number;
  bytesTransferred: number;
  averageLatency: number;
}

export class CommunicationService extends EventEmitter {
  private wss: WebSocketServer;
  private logger: pino.Logger;
  private clients = new Map<string, Client>();
  private subscriptions = new Map<string, ClientSubscription>();
  private messageHandlers = new Map<MessageType, MessageHandler>();
  private messageQueue: MessageQueue = {};
  private connectionStats: ConnectionStats;
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private cleanupInterval: NodeJS.Timeout | null = null;

  // Performance optimization
  private batchSize = 100;
  private batchTimeout = 50; // ms
  private maxQueueSize = 1000;
  private connectionTimeout = 30000; // 30 seconds
  private heartbeatInterval_ms = 10000; // 10 seconds

  constructor(wss: WebSocketServer, logger?: pino.Logger) {
    super();
    this.wss = wss;
    this.logger = logger || pino({ name: 'WebSocketManager' });

    this.connectionStats = {
      totalConnections: 0,
      activeConnections: 0,
      messagesSent: 0,
      messagesReceived: 0,
      bytesTransferred: 0,
      averageLatency: 0
    };

    this.registerDefaultHandlers();
    this.logger.info('WebSocket communication service initialized');
  }

  /**
   * Initialize WebSocket server with connection handling
   */
  initialize(): void {
    this.setupConnectionHandling();
    this.startHeartbeat();
    this.startCleanupTimer();

    this.logger.info('WebSocket communication service started');
  }

  /**
   * Dispose of resources
   */
  async dispose(): Promise<void> {
    this.logger.info('Disposing WebSocket communication service...');

    // Stop timers
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
    }
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
    }

    // Close all connections gracefully
    const closePromises = Array.from(this.clients.values()).map(client =>
      this.disconnectClient(client.id, 1000, 'Server shutdown')
    );

    await Promise.allSettled(closePromises);

    this.clients.clear();
    this.subscriptions.clear();
    this.messageQueue = {};

    this.logger.info('WebSocket communication service disposed');
  }

  /**
   * Broadcast message to all connected clients
   */
  async broadcast(message: WebSocketMessage): Promise<void> {
    const startTime = performance.now();
    const clients = Array.from(this.clients.values());

    if (clients.length === 0) {
      this.logger.debug('No clients to broadcast to', { messageType: message.type });
      return;
    }

    this.logger.debug('Broadcasting message', {
      type: message.type,
      clientCount: clients.length
    });

    // Send to all clients in parallel
    const sendPromises = clients.map(client => this.send(client.id, message));
    const results = await Promise.allSettled(sendPromises);

    // Count successful sends
    const successCount = results.filter(result => result.status === 'fulfilled').length;
    const failCount = results.length - successCount;

    const duration = Math.round(performance.now() - startTime);
    this.connectionStats.messagesSent += successCount;
    this.connectionStats.bytesTransferred += JSON.stringify(message).length * successCount;

    this.logger.debug('Broadcast completed', {
      type: message.type,
      success: successCount,
      failed: failCount,
      duration
    });

    if (failCount > 0) {
      this.logger.warn('Some broadcast sends failed', {
        type: message.type,
        failCount
      });
    }
  }

  /**
   * Send message to specific client
   */
  async send(clientId: string, message: WebSocketMessage): Promise<void> {
    const client = this.clients.get(clientId);
    if (!client) {
      throw new Error(`Client ${clientId} not found`);
    }

    if (client.websocket.readyState !== WebSocket.OPEN) {
      this.logger.warn('Cannot send to client, connection not open', { clientId });
      return;
    }

    try {
      // Add message to client's queue for batching
      await this.queueMessage(clientId, message);

      // Update client activity
      client.lastActivity = new Date();

    } catch (error) {
      this.logger.error('Error sending message to client', {
        clientId,
        messageType: message.type,
        error: error.message
      });
      throw error;
    }
  }

  /**
   * Subscribe client to specific channels
   */
  subscribe(clientId: string, channel: string): void {
    let subscription = this.subscriptions.get(clientId);
    if (!subscription) {
      subscription = {
        clientId,
        channels: new Set(),
        filters: new Set()
      };
      this.subscriptions.set(clientId, subscription);
    }

    subscription.channels.add(channel);
    this.logger.debug('Client subscribed to channel', { clientId, channel });
  }

  /**
   * Unsubscribe client from channel
   */
  unsubscribe(clientId: string, channel: string): void {
    const subscription = this.subscriptions.get(clientId);
    if (subscription) {
      subscription.channels.delete(channel);
      this.logger.debug('Client unsubscribed from channel', { clientId, channel });
    }
  }

  /**
   * Add message filter for client
   */
  addFilter(clientId: string, filter: string): void {
    let subscription = this.subscriptions.get(clientId);
    if (!subscription) {
      subscription = {
        clientId,
        channels: new Set(),
        filters: new Set()
      };
      this.subscriptions.set(clientId, subscription);
    }

    subscription.filters.add(filter);
    this.logger.debug('Filter added for client', { clientId, filter });
  }

  /**
   * Remove message filter for client
   */
  removeFilter(clientId: string, filter: string): void {
    const subscription = this.subscriptions.get(clientId);
    if (subscription) {
      subscription.filters.delete(filter);
      this.logger.debug('Filter removed for client', { clientId, filter });
    }
  }

  /**
   * Get all connected clients
   */
  getClients(): Client[] {
    return Array.from(this.clients.values());
  }

  /**
   * Get specific client
   */
  getClient(clientId: string): Client | undefined {
    return this.clients.get(clientId);
  }

  /**
   * Get clients by type
   */
  getClientsByType(type: ClientType): Client[] {
    return Array.from(this.clients.values()).filter(client => client.type === type);
  }

  /**
   * Get clients by capability
   */
  getClientsByCapability(capability: ClientCapability): Client[] {
    return Array.from(this.clients.values()).filter(client =>
      client.capabilities.includes(capability)
    );
  }

  /**
   * Register message handler
   */
  registerHandler(type: MessageType, handler: (client: Client, message: WebSocketMessage) => Promise<void>): void {
    this.messageHandlers.set(type, { type, handler });
    this.logger.debug('Message handler registered', { type });
  }

  /**
   * Unregister message handler
   */
  unregisterHandler(type: MessageType): void {
    this.messageHandlers.delete(type);
    this.logger.debug('Message handler unregistered', { type });
  }

  /**
   * Get connection statistics
   */
  getStats(): ConnectionStats {
    return { ...this.connectionStats };
  }

  /**
   * Disconnect specific client
   */
  async disconnectClient(clientId: string, code: number = 1000, reason: string = 'Normal closure'): Promise<void> {
    const client = this.clients.get(clientId);
    if (!client) return;

    this.logger.info('Disconnecting client', { clientId, code, reason });

    try {
      client.websocket.close(code, reason);
    } catch (error) {
      this.logger.warn('Error closing client connection', { clientId, error: error.message });
    }

    this.cleanupClient(clientId);
  }

  // Private Methods

  private setupConnectionHandling(): void {
    this.wss.on('connection', (ws: WebSocket, request: IncomingMessage) => {
      this.handleNewConnection(ws, request);
    });

    this.wss.on('error', (error) => {
      this.logger.error('WebSocket server error', { error: error.message });
      this.emit('error', error);
    });
  }

  private handleNewConnection(ws: WebSocket, request: IncomingMessage): void {
    const clientId = uuidv4();
    const clientType = this.determineClientType(request);
    const capabilities = this.determineClientCapabilities(request);

    const client: Client = {
      id: clientId,
      type: clientType,
      websocket: ws,
      request,
      connectedAt: new Date(),
      lastActivity: new Date(),
      subscriptions: [],
      capabilities
    };

    this.clients.set(clientId, client);
    this.connectionStats.totalConnections++;
    this.connectionStats.activeConnections++;

    this.logger.info('New client connected', {
      clientId,
      type: clientType,
      capabilities,
      ip: request.socket.remoteAddress,
      userAgent: request.headers['user-agent']
    });

    // Set up client event handlers
    this.setupClientHandlers(client);

    // Send welcome message
    this.sendWelcomeMessage(client);

    // Emit connection event
    this.emit('client-connected', client);
  }

  private setupClientHandlers(client: Client): void {
    const { websocket, id } = client;

    websocket.on('message', async (data) => {
      await this.handleClientMessage(client, data);
    });

    websocket.on('close', (code, reason) => {
      this.handleClientDisconnection(id, code, reason?.toString());
    });

    websocket.on('error', (error) => {
      this.logger.error('Client WebSocket error', {
        clientId: id,
        error: error.message
      });
    });

    websocket.on('pong', () => {
      client.lastActivity = new Date();
    });
  }

  private async handleClientMessage(client: Client, data: any): Promise<void> {
    const startTime = performance.now();

    try {
      const message: WebSocketMessage = JSON.parse(data.toString());

      // Validate message structure
      if (!message.type || typeof message.timestamp !== 'number') {
        throw new Error('Invalid message format');
      }

      this.connectionStats.messagesReceived++;
      this.connectionStats.bytesTransferred += data.length;
      client.lastActivity = new Date();

      this.logger.debug('Received message from client', {
        clientId: client.id,
        type: message.type,
        size: data.length
      });

      // Find and execute handler
      const handler = this.messageHandlers.get(message.type);
      if (handler) {
        await handler.handler(client, message);
      } else {
        this.logger.warn('No handler for message type', {
          clientId: client.id,
          type: message.type
        });

        // Send error response
        await this.send(client.id, {
          id: uuidv4(),
          type: 'error' as MessageType,
          timestamp: Date.now(),
          error: `Unknown message type: ${message.type}`
        });
      }

      const duration = Math.round(performance.now() - startTime);
      this.updateLatencyStats(duration);

    } catch (error) {
      this.logger.error('Error handling client message', {
        clientId: client.id,
        error: error.message,
        data: data.toString().substring(0, 200)
      });

      // Send error response
      try {
        await this.send(client.id, {
          id: uuidv4(),
          type: 'error' as MessageType,
          timestamp: Date.now(),
          error: 'Message processing error'
        });
      } catch {
        // Ignore send errors during error handling
      }
    }
  }

  private handleClientDisconnection(clientId: string, code: number, reason?: string): void {
    this.logger.info('Client disconnected', { clientId, code, reason });

    this.cleanupClient(clientId);
    this.connectionStats.activeConnections = Math.max(0, this.connectionStats.activeConnections - 1);

    this.emit('client-disconnected', clientId);
  }

  private cleanupClient(clientId: string): void {
    this.clients.delete(clientId);
    this.subscriptions.delete(clientId);
    delete this.messageQueue[clientId];
  }

  private determineClientType(request: IncomingMessage): ClientType {
    const userAgent = request.headers['user-agent'] || '';
    const origin = request.headers.origin || '';

    if (userAgent.includes('Revit')) return 'revit';
    if (userAgent.includes('Code')) return 'vscode';
    if (origin.includes('webview')) return 'webview';
    if (userAgent.includes('CLI')) return 'cli';
    return 'browser';
  }

  private determineClientCapabilities(request: IncomingMessage): ClientCapability[] {
    const capabilities: ClientCapability[] = [];
    const userAgent = request.headers['user-agent'] || '';

    if (userAgent.includes('Revit')) {
      capabilities.push('python-execution');
    }
    if (userAgent.includes('webview') || userAgent.includes('browser')) {
      capabilities.push('ui-rendering');
    }
    if (userAgent.includes('Code')) {
      capabilities.push('file-operations', 'debugging');
    }

    return capabilities;
  }

  private async sendWelcomeMessage(client: Client): Promise<void> {
    const message: WebSocketMessage = {
      id: uuidv4(),
      type: 'client-connected',
      timestamp: Date.now(),
      data: {
        clientId: client.id,
        serverInfo: {
          name: 'RevitPy Development Server',
          version: process.env.npm_package_version || '1.0.0',
          capabilities: ['hot-reload', 'python-modules', 'ui-components']
        }
      }
    };

    await this.send(client.id, message);
  }

  private async queueMessage(clientId: string, message: WebSocketMessage): Promise<void> {
    if (!this.messageQueue[clientId]) {
      this.messageQueue[clientId] = {
        messages: [],
        processing: false
      };
    }

    const queue = this.messageQueue[clientId];

    // Check queue size limit
    if (queue.messages.length >= this.maxQueueSize) {
      this.logger.warn('Message queue full for client', { clientId });
      queue.messages.shift(); // Remove oldest message
    }

    queue.messages.push(message);

    // Process queue if not already processing
    if (!queue.processing) {
      await this.processMessageQueue(clientId);
    }
  }

  private async processMessageQueue(clientId: string): Promise<void> {
    const queue = this.messageQueue[clientId];
    if (!queue || queue.processing) return;

    queue.processing = true;

    try {
      while (queue.messages.length > 0) {
        const batch = queue.messages.splice(0, this.batchSize);
        await this.sendMessageBatch(clientId, batch);

        // Small delay between batches to prevent overwhelming
        if (queue.messages.length > 0) {
          await new Promise(resolve => setTimeout(resolve, this.batchTimeout));
        }
      }
    } catch (error) {
      this.logger.error('Error processing message queue', { clientId, error: error.message });
    } finally {
      queue.processing = false;
    }
  }

  private async sendMessageBatch(clientId: string, messages: WebSocketMessage[]): Promise<void> {
    const client = this.clients.get(clientId);
    if (!client || client.websocket.readyState !== WebSocket.OPEN) {
      return;
    }

    for (const message of messages) {
      try {
        const data = JSON.stringify(message);
        client.websocket.send(data);
        this.connectionStats.messagesSent++;
        this.connectionStats.bytesTransferred += data.length;
      } catch (error) {
        this.logger.error('Error sending message', {
          clientId,
          messageType: message.type,
          error: error.message
        });
      }
    }
  }

  private startHeartbeat(): void {
    this.heartbeatInterval = setInterval(() => {
      this.performHeartbeat();
    }, this.heartbeatInterval_ms);
  }

  private performHeartbeat(): void {
    const now = new Date();
    const deadClients: string[] = [];

    for (const [clientId, client] of this.clients) {
      const timeSinceActivity = now.getTime() - client.lastActivity.getTime();

      if (timeSinceActivity > this.connectionTimeout) {
        deadClients.push(clientId);
      } else if (client.websocket.readyState === WebSocket.OPEN) {
        // Send ping
        try {
          client.websocket.ping();
        } catch (error) {
          this.logger.warn('Error sending ping to client', { clientId, error: error.message });
          deadClients.push(clientId);
        }
      }
    }

    // Clean up dead clients
    deadClients.forEach(clientId => {
      this.logger.info('Cleaning up inactive client', { clientId });
      this.disconnectClient(clientId, 1001, 'Connection timeout');
    });
  }

  private startCleanupTimer(): void {
    this.cleanupInterval = setInterval(() => {
      this.performCleanup();
    }, 60000); // Run every minute
  }

  private performCleanup(): void {
    // Clean up empty subscriptions
    for (const [clientId, subscription] of this.subscriptions) {
      if (subscription.channels.size === 0 && subscription.filters.size === 0) {
        this.subscriptions.delete(clientId);
      }
    }

    // Clean up empty message queues
    for (const clientId of Object.keys(this.messageQueue)) {
      if (!this.clients.has(clientId)) {
        delete this.messageQueue[clientId];
      }
    }
  }

  private updateLatencyStats(duration: number): void {
    // Simple moving average for latency
    this.connectionStats.averageLatency =
      (this.connectionStats.averageLatency * 0.9) + (duration * 0.1);
  }

  private registerDefaultHandlers(): void {
    // Ping handler
    this.registerHandler('ping' as MessageType, async (client, message) => {
      await this.send(client.id, {
        id: uuidv4(),
        type: 'pong' as MessageType,
        timestamp: Date.now()
      });
    });

    // Subscribe handler
    this.registerHandler('subscribe' as MessageType, async (client, message) => {
      const { channel } = message.data || {};
      if (channel) {
        this.subscribe(client.id, channel);
      }
    });

    // Unsubscribe handler
    this.registerHandler('unsubscribe' as MessageType, async (client, message) => {
      const { channel } = message.data || {};
      if (channel) {
        this.unsubscribe(client.id, channel);
      }
    });
  }
}
