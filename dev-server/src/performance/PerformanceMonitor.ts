/**
 * Performance Monitoring Service
 * Real-time metrics and optimization for development server
 */

import { EventEmitter } from 'events';
import { performance } from 'perf_hooks';
import pino from 'pino';

import type { 
  DevServerConfig, 
  PerformanceMetrics, 
  MemoryUsage, 
  CPUUsage 
} from '../types/index.js';

export class PerformanceService extends EventEmitter {
  private config: DevServerConfig;
  private logger: pino.Logger;
  private metrics: PerformanceMetrics;
  private monitoringInterval: NodeJS.Timeout | null = null;
  private isMonitoring = false;

  constructor(config: DevServerConfig, logger?: pino.Logger) {
    super();
    this.config = config;
    this.logger = logger || pino({ name: 'PerformanceMonitor' });
    
    this.metrics = {
      timestamp: Date.now(),
      buildTime: 0,
      reloadTime: 0,
      memoryUsage: process.memoryUsage(),
      cpuUsage: { user: 0, system: 0, percent: 0 },
      networkLatency: 0,
      fileSystemLatency: 0,
      clientCount: 0,
      errorRate: 0
    };
  }

  async startMonitoring(): Promise<void> {
    if (this.isMonitoring) return;

    this.isMonitoring = true;
    this.monitoringInterval = setInterval(() => {
      this.updateMetrics();
    }, 1000);

    this.logger.info('Performance monitoring started');
  }

  async stopMonitoring(): Promise<void> {
    if (!this.isMonitoring) return;

    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval);
      this.monitoringInterval = null;
    }

    this.isMonitoring = false;
    this.logger.info('Performance monitoring stopped');
  }

  getMetrics(): PerformanceMetrics {
    return { ...this.metrics };
  }

  async benchmark(operation: string, fn: () => Promise<void>): Promise<number> {
    const startTime = performance.now();
    await fn();
    const duration = Math.round(performance.now() - startTime);
    
    this.logger.debug('Benchmark completed', { operation, duration });
    return duration;
  }

  profile(name: string): any {
    return {
      end: () => ({
        name,
        duration: 0,
        memoryDelta: 0,
        cpuUsage: 0,
        details: {}
      })
    };
  }

  private updateMetrics(): void {
    this.metrics = {
      ...this.metrics,
      timestamp: Date.now(),
      memoryUsage: process.memoryUsage(),
      cpuUsage: this.getCPUUsage()
    };

    this.emit('performance-update', this.metrics);
  }

  private getCPUUsage(): CPUUsage {
    const usage = process.cpuUsage();
    return {
      user: usage.user,
      system: usage.system,
      percent: 0 // Would calculate actual percentage
    };
  }
}