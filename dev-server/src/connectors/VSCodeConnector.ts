/**
 * VS Code Integration Connector
 * Handles communication with VS Code extension
 */

import { EventEmitter } from 'events';
import pino from 'pino';

import type { VSCodeIntegrationConfig } from '../types/index.js';

export class VSCodeConnector extends EventEmitter {
  private config: VSCodeIntegrationConfig;
  private logger: pino.Logger;
  private connected = false;

  constructor(config: VSCodeIntegrationConfig, logger?: pino.Logger) {
    super();
    this.config = config;
    this.logger = logger || pino({ name: 'VSCodeConnector' });
  }

  async connect(): Promise<void> {
    if (!this.config.enabled) return;
    
    this.logger.info('Connecting to VS Code...', { port: this.config.port });
    
    // Simulate connection
    this.connected = true;
    this.emit('connected');
    this.logger.info('Connected to VS Code');
  }

  async disconnect(): Promise<void> {
    if (!this.connected) return;
    
    this.logger.info('Disconnecting from VS Code...');
    this.connected = false;
    this.emit('disconnected');
    this.logger.info('Disconnected from VS Code');
  }

  isConnected(): boolean {
    return this.connected;
  }
}