/**
 * Enhanced Logger utility
 * High-performance logging with development server optimizations
 */

import pino from 'pino';
import { performance } from 'perf_hooks';

export class Logger {
  /**
   * Create a logger instance with development server optimizations
   */
  static create(name: string, monitoring: boolean = true): pino.Logger {
    const logLevel = process.env.LOG_LEVEL || 'info';
    const isDevelopment = process.env.NODE_ENV !== 'production';
    
    const options: pino.LoggerOptions = {
      name,
      level: logLevel,
      
      // Transport for pretty printing in development
      ...(isDevelopment && {
        transport: {
          target: 'pino-pretty',
          options: {
            colorize: true,
            translateTime: 'yyyy-mm-dd HH:MM:ss.l',
            ignore: 'pid,hostname',
            messageFormat: '[{name}] {msg}',
            levelFirst: true,
            crlf: false
          }
        }
      }),
      
      // Base configuration
      formatters: {
        level: (label) => {
          return { level: label };
        },
        log: (obj) => {
          // Add performance timing if available
          if (monitoring && obj.duration !== undefined) {
            obj.perf = `${obj.duration}ms`;
          }
          return obj;
        }
      },
      
      // Custom serializers
      serializers: {
        error: (error: Error) => ({
          type: error.constructor.name,
          message: error.message,
          stack: error.stack,
          ...(error.cause && { cause: error.cause })
        }),
        
        // Serialize performance metrics
        metrics: (metrics: any) => ({
          memory: metrics.memoryUsage && {
            rss: `${Math.round(metrics.memoryUsage.rss / 1024 / 1024)}MB`,
            heapUsed: `${Math.round(metrics.memoryUsage.heapUsed / 1024 / 1024)}MB`,
            heapTotal: `${Math.round(metrics.memoryUsage.heapTotal / 1024 / 1024)}MB`
          },
          cpu: metrics.cpuUsage && `${metrics.cpuUsage.percent?.toFixed(1)}%`,
          duration: metrics.buildTime && `${Math.round(metrics.buildTime)}ms`
        }),
        
        // Serialize file changes
        fileChange: (change: any) => ({
          path: change.path,
          type: change.type,
          size: change.size && `${Math.round(change.size / 1024)}KB`,
          hash: change.hash && change.hash.substring(0, 8)
        }),
        
        // Serialize client information
        client: (client: any) => ({
          id: client.id,
          type: client.type,
          connected: client.connectedAt && 
            `${Math.round((Date.now() - client.connectedAt.getTime()) / 1000)}s ago`,
          capabilities: client.capabilities
        })
      },
      
      // Timestamp
      timestamp: pino.stdTimeFunctions.isoTime,
      
      // Additional base fields
      base: {
        pid: process.pid,
        version: process.env.npm_package_version || 'dev'
      }
    };

    const logger = pino(options);

    // Add custom methods for development server specific logging
    const enhancedLogger = logger.child({}) as any;

    // File change logging
    enhancedLogger.fileChange = (path: string, type: string, duration?: number) => {
      logger.info({
        fileChange: { path, type },
        duration
      }, `File ${type}: ${path}`);
    };

    // Performance logging
    enhancedLogger.perf = (operation: string, duration: number, details?: any) => {
      const level = duration > 1000 ? 'warn' : 'debug';
      logger[level]({
        operation,
        duration,
        ...details
      }, `${operation} took ${duration}ms`);
    };

    // Build logging
    enhancedLogger.build = (result: any) => {
      const level = result.success ? 'info' : 'error';
      logger[level]({
        buildResult: {
          success: result.success,
          duration: result.duration,
          errors: result.errors?.length || 0,
          warnings: result.warnings?.length || 0
        }
      }, `Build ${result.success ? 'completed' : 'failed'} in ${result.duration}ms`);
    };

    // Reload logging
    enhancedLogger.reload = (module: string, type: 'python' | 'ui', result: any) => {
      const level = result.success ? 'info' : 'error';
      logger[level]({
        reloadResult: {
          module,
          type,
          success: result.success,
          duration: result.duration,
          statePreserved: result.statePreserved
        }
      }, `${type} reload ${result.success ? 'completed' : 'failed'}: ${module}`);
    };

    // Client logging
    enhancedLogger.client = (action: string, client: any) => {
      logger.info({
        client,
        action
      }, `Client ${action}: ${client.id} (${client.type})`);
    };

    // Error with recovery logging
    enhancedLogger.errorRecovery = (error: Error, recovery: any) => {
      logger.warn({
        error,
        recovery: {
          type: recovery.type,
          automatic: recovery.automatic,
          success: recovery.success
        }
      }, `Error recovered: ${error.message}`);
    };

    // WebSocket message logging
    enhancedLogger.ws = (direction: 'in' | 'out', clientId: string, messageType: string, size?: number) => {
      logger.debug({
        websocket: {
          direction,
          clientId,
          messageType,
          size: size && `${size}B`
        }
      }, `WebSocket ${direction}: ${messageType} (${clientId})`);
    };

    return enhancedLogger;
  }

  /**
   * Create a timer for performance measurements
   */
  static timer(name: string): PerformanceTimer {
    return new PerformanceTimer(name);
  }

  /**
   * Create a profiler for detailed performance analysis
   */
  static profiler(name: string): PerformanceProfiler {
    return new PerformanceProfiler(name);
  }
}

/**
 * Performance timer for measuring operation duration
 */
export class PerformanceTimer {
  private startTime: number;
  private name: string;
  private marks: Map<string, number> = new Map();

  constructor(name: string) {
    this.name = name;
    this.startTime = performance.now();
  }

  /**
   * Mark a checkpoint in the timer
   */
  mark(label: string): void {
    this.marks.set(label, performance.now());
  }

  /**
   * End the timer and return duration
   */
  end(): number {
    const endTime = performance.now();
    const duration = Math.round(endTime - this.startTime);
    return duration;
  }

  /**
   * Get duration between marks
   */
  between(start: string, end: string): number {
    const startTime = this.marks.get(start);
    const endTime = this.marks.get(end);
    
    if (!startTime || !endTime) {
      throw new Error(`Mark not found: ${!startTime ? start : end}`);
    }
    
    return Math.round(endTime - startTime);
  }

  /**
   * Get all marks with durations from start
   */
  getAllMarks(): Record<string, number> {
    const result: Record<string, number> = {};
    
    for (const [label, time] of this.marks) {
      result[label] = Math.round(time - this.startTime);
    }
    
    return result;
  }

  /**
   * Log timer results to logger
   */
  log(logger: pino.Logger, level: pino.Level = 'debug'): void {
    const duration = this.end();
    const marks = this.getAllMarks();
    
    logger[level]({
      timer: {
        name: this.name,
        duration,
        marks: Object.keys(marks).length > 0 ? marks : undefined
      }
    }, `Timer ${this.name}: ${duration}ms`);
  }
}

/**
 * Advanced performance profiler with memory tracking
 */
export class PerformanceProfiler {
  private name: string;
  private startTime: number;
  private startMemory: NodeJS.MemoryUsage;
  private measurements: Array<{
    label: string;
    time: number;
    memory: NodeJS.MemoryUsage;
  }> = [];

  constructor(name: string) {
    this.name = name;
    this.startTime = performance.now();
    this.startMemory = process.memoryUsage();
  }

  /**
   * Take a measurement
   */
  measure(label: string): void {
    this.measurements.push({
      label,
      time: performance.now(),
      memory: process.memoryUsage()
    });
  }

  /**
   * End profiling and return detailed report
   */
  end(): PerformanceReport {
    const endTime = performance.now();
    const endMemory = process.memoryUsage();
    
    const totalDuration = Math.round(endTime - this.startTime);
    const memoryDelta = {
      rss: endMemory.rss - this.startMemory.rss,
      heapUsed: endMemory.heapUsed - this.startMemory.heapUsed,
      heapTotal: endMemory.heapTotal - this.startMemory.heapTotal,
      external: endMemory.external - this.startMemory.external
    };

    // Process measurements
    const segments: Array<{
      label: string;
      duration: number;
      memoryDelta: number;
    }> = [];

    let previousTime = this.startTime;
    let previousMemory = this.startMemory.heapUsed;

    for (const measurement of this.measurements) {
      segments.push({
        label: measurement.label,
        duration: Math.round(measurement.time - previousTime),
        memoryDelta: measurement.memory.heapUsed - previousMemory
      });
      
      previousTime = measurement.time;
      previousMemory = measurement.memory.heapUsed;
    }

    return {
      name: this.name,
      totalDuration,
      memoryDelta,
      segments,
      summary: {
        avgSegmentDuration: segments.length > 0 ? 
          Math.round(segments.reduce((sum, s) => sum + s.duration, 0) / segments.length) : 0,
        maxMemoryUsage: Math.max(...this.measurements.map(m => m.memory.heapUsed)),
        minMemoryUsage: Math.min(...this.measurements.map(m => m.memory.heapUsed))
      }
    };
  }

  /**
   * Log profiler results
   */
  log(logger: pino.Logger, level: pino.Level = 'debug'): PerformanceReport {
    const report = this.end();
    
    logger[level]({
      profiler: {
        name: report.name,
        duration: report.totalDuration,
        memoryDelta: {
          rss: `${Math.round(report.memoryDelta.rss / 1024)}KB`,
          heap: `${Math.round(report.memoryDelta.heapUsed / 1024)}KB`
        },
        segments: report.segments.length,
        summary: report.summary
      }
    }, `Profile ${report.name}: ${report.totalDuration}ms`);
    
    return report;
  }
}

/**
 * Performance report interface
 */
interface PerformanceReport {
  name: string;
  totalDuration: number;
  memoryDelta: {
    rss: number;
    heapUsed: number;
    heapTotal: number;
    external: number;
  };
  segments: Array<{
    label: string;
    duration: number;
    memoryDelta: number;
  }>;
  summary: {
    avgSegmentDuration: number;
    maxMemoryUsage: number;
    minMemoryUsage: number;
  };
}

export type { PerformanceReport };