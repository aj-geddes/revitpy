/**
 * WebView2 Integration Connector
 * Handles communication with WebView2 panels
 */

import { EventEmitter } from 'events';
import pino from 'pino';

import type { WebViewConfig } from '../types/index.js';

export class WebViewConnector extends EventEmitter {
  private config: WebViewConfig;
  private logger: pino.Logger;
  private connected = false;

  constructor(config: WebViewConfig, logger?: pino.Logger) {
    super();
    this.config = config;
    this.logger = logger || pino({ name: 'WebViewConnector' });
  }

  async connect(): Promise<void> {
    if (!this.config.enabled) return;

    this.logger.info('Connecting to WebView2...', { port: this.config.port });

    // Simulate connection
    this.connected = true;
    this.emit('connected');
    this.logger.info('Connected to WebView2');
  }

  async disconnect(): Promise<void> {
    if (!this.connected) return;

    this.logger.info('Disconnecting from WebView2...');
    this.connected = false;
    this.emit('disconnected');
    this.logger.info('Disconnected from WebView2');
  }

  isConnected(): boolean {
    return this.connected;
  }
}
