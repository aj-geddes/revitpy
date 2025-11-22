/**
 * Configuration Validator
 * Validates and normalizes DevServer configuration
 */

import path from 'path';
import { promises as fs } from 'fs';
import type { DevServerConfig, ConfigValidationResult } from '../types/index.js';

export class ConfigValidator {
  /**
   * Validate configuration object
   */
  validate(config: Partial<DevServerConfig>): ConfigValidationResult {
    const errors: string[] = [];
    const warnings: string[] = [];

    // Required fields
    if (!config.projectRoot) {
      errors.push('projectRoot is required');
    } else if (!path.isAbsolute(config.projectRoot)) {
      errors.push('projectRoot must be an absolute path');
    }

    if (!config.watchPaths || config.watchPaths.length === 0) {
      errors.push('watchPaths must be provided and non-empty');
    }

    // Network configuration
    if (config.port !== undefined) {
      if (!Number.isInteger(config.port) || config.port < 1 || config.port > 65535) {
        errors.push('port must be a valid port number (1-65535)');
      }
    }

    if (config.websocketPort !== undefined) {
      if (!Number.isInteger(config.websocketPort) || config.websocketPort < 1 || config.websocketPort > 65535) {
        errors.push('websocketPort must be a valid port number (1-65535)');
      }
    }

    // Performance configuration
    if (config.debounceMs !== undefined) {
      if (!Number.isInteger(config.debounceMs) || config.debounceMs < 0) {
        errors.push('debounceMs must be a non-negative integer');
      }
    }

    if (config.maxReloadTime !== undefined) {
      if (!Number.isInteger(config.maxReloadTime) || config.maxReloadTime < 100) {
        errors.push('maxReloadTime must be at least 100ms');
      }
    }

    // Feature validation
    this.validateHotReloadConfig(config.hotReload, errors, warnings);
    this.validateModuleReloaderConfig(config.moduleReloader, errors, warnings);
    this.validateUIReloadConfig(config.uiReload, errors, warnings);
    this.validateErrorRecoveryConfig(config.errorRecovery, errors, warnings);
    this.validatePerformanceConfig(config.performance, errors, warnings);

    // Integration validation
    this.validateRevitConfig(config.revit, errors, warnings);
    this.validateVSCodeConfig(config.vscode, errors, warnings);
    this.validateWebViewConfig(config.webview, errors, warnings);

    return {
      valid: errors.length === 0,
      errors,
      warnings
    };
  }

  /**
   * Normalize configuration with defaults
   */
  normalize(config: Partial<DevServerConfig>): DevServerConfig {
    return {
      // Network
      host: config.host || 'localhost',
      port: config.port || 3000,
      websocketPort: config.websocketPort || 3001,

      // Paths
      projectRoot: config.projectRoot || process.cwd(),
      watchPaths: config.watchPaths || ['src'],
      buildOutputPath: config.buildOutputPath || 'dist',

      // Performance
      debounceMs: config.debounceMs || 300,
      maxReloadTime: config.maxReloadTime || 5000,
      parallelProcesses: config.parallelProcesses || 4,

      // Features
      hotReload: this.normalizeHotReloadConfig(config.hotReload),
      moduleReloader: this.normalizeModuleReloaderConfig(config.moduleReloader),
      uiReload: this.normalizeUIReloadConfig(config.uiReload),
      errorRecovery: this.normalizeErrorRecoveryConfig(config.errorRecovery),
      performance: this.normalizePerformanceConfig(config.performance),

      // Integrations
      revit: this.normalizeRevitConfig(config.revit),
      vscode: this.normalizeVSCodeConfig(config.vscode),
      webview: this.normalizeWebViewConfig(config.webview)
    };
  }

  /**
   * Validate configuration against file system
   */
  async validateFileSystem(config: DevServerConfig): Promise<ConfigValidationResult> {
    const errors: string[] = [];
    const warnings: string[] = [];

    // Check if project root exists
    try {
      const projectStats = await fs.stat(config.projectRoot);
      if (!projectStats.isDirectory()) {
        errors.push('projectRoot must be a directory');
      }
    } catch {
      errors.push('projectRoot directory does not exist');
    }

    // Check watch paths
    for (const watchPath of config.watchPaths) {
      const fullPath = path.isAbsolute(watchPath)
        ? watchPath
        : path.join(config.projectRoot, watchPath);

      try {
        const watchStats = await fs.stat(fullPath);
        if (!watchStats.isDirectory()) {
          warnings.push(`Watch path is not a directory: ${watchPath}`);
        }
      } catch {
        warnings.push(`Watch path does not exist: ${watchPath}`);
      }
    }

    // Check build output path
    const buildPath = path.isAbsolute(config.buildOutputPath)
      ? config.buildOutputPath
      : path.join(config.projectRoot, config.buildOutputPath);

    try {
      await fs.mkdir(buildPath, { recursive: true });
    } catch {
      errors.push('Cannot create build output directory');
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings
    };
  }

  // Private validation methods

  private validateHotReloadConfig(config: any, errors: string[], warnings: string[]): void {
    if (!config) return;

    if (typeof config.enabled !== 'boolean') {
      errors.push('hotReload.enabled must be a boolean');
    }

    if (config.excludePatterns && !Array.isArray(config.excludePatterns)) {
      errors.push('hotReload.excludePatterns must be an array');
    }

    if (config.includePatterns && !Array.isArray(config.includePatterns)) {
      errors.push('hotReload.includePatterns must be an array');
    }
  }

  private validateModuleReloaderConfig(config: any, errors: string[], warnings: string[]): void {
    if (!config) return;

    if (typeof config.enabled !== 'boolean') {
      errors.push('moduleReloader.enabled must be a boolean');
    }

    if (config.preReloadHooks && !Array.isArray(config.preReloadHooks)) {
      errors.push('moduleReloader.preReloadHooks must be an array');
    }

    if (config.postReloadHooks && !Array.isArray(config.postReloadHooks)) {
      errors.push('moduleReloader.postReloadHooks must be an array');
    }
  }

  private validateUIReloadConfig(config: any, errors: string[], warnings: string[]): void {
    if (!config) return;

    if (typeof config.enabled !== 'boolean') {
      errors.push('uiReload.enabled must be a boolean');
    }

    if (config.hmrPort !== undefined) {
      if (!Number.isInteger(config.hmrPort) || config.hmrPort < 1 || config.hmrPort > 65535) {
        errors.push('uiReload.hmrPort must be a valid port number');
      }
    }
  }

  private validateErrorRecoveryConfig(config: any, errors: string[], warnings: string[]): void {
    if (!config) return;

    if (typeof config.enabled !== 'boolean') {
      errors.push('errorRecovery.enabled must be a boolean');
    }

    if (config.maxRetries !== undefined) {
      if (!Number.isInteger(config.maxRetries) || config.maxRetries < 0) {
        errors.push('errorRecovery.maxRetries must be a non-negative integer');
      }
    }

    if (config.rollbackTimeout !== undefined) {
      if (!Number.isInteger(config.rollbackTimeout) || config.rollbackTimeout < 0) {
        errors.push('errorRecovery.rollbackTimeout must be a non-negative integer');
      }
    }
  }

  private validatePerformanceConfig(config: any, errors: string[], warnings: string[]): void {
    if (!config) return;

    if (typeof config.monitoring !== 'boolean') {
      errors.push('performance.monitoring must be a boolean');
    }
  }

  private validateRevitConfig(config: any, errors: string[], warnings: string[]): void {
    if (!config) return;

    if (typeof config.enabled !== 'boolean') {
      errors.push('revit.enabled must be a boolean');
    }

    if (config.port !== undefined) {
      if (!Number.isInteger(config.port) || config.port < 1 || config.port > 65535) {
        errors.push('revit.port must be a valid port number');
      }
    }

    if (config.commandTimeout !== undefined) {
      if (!Number.isInteger(config.commandTimeout) || config.commandTimeout < 1000) {
        errors.push('revit.commandTimeout must be at least 1000ms');
      }
    }
  }

  private validateVSCodeConfig(config: any, errors: string[], warnings: string[]): void {
    if (!config) return;

    if (typeof config.enabled !== 'boolean') {
      errors.push('vscode.enabled must be a boolean');
    }

    if (config.port !== undefined) {
      if (!Number.isInteger(config.port) || config.port < 1 || config.port > 65535) {
        errors.push('vscode.port must be a valid port number');
      }
    }
  }

  private validateWebViewConfig(config: any, errors: string[], warnings: string[]): void {
    if (!config) return;

    if (typeof config.enabled !== 'boolean') {
      errors.push('webview.enabled must be a boolean');
    }

    if (config.port !== undefined) {
      if (!Number.isInteger(config.port) || config.port < 1 || config.port > 65535) {
        errors.push('webview.port must be a valid port number');
      }
    }
  }

  // Private normalization methods

  private normalizeHotReloadConfig(config: any) {
    return {
      enabled: config?.enabled ?? true,
      pythonModules: config?.pythonModules ?? true,
      uiComponents: config?.uiComponents ?? true,
      staticAssets: config?.staticAssets ?? true,
      excludePatterns: config?.excludePatterns ?? [],
      includePatterns: config?.includePatterns ?? [],
      preserveState: config?.preserveState ?? true
    };
  }

  private normalizeModuleReloaderConfig(config: any) {
    return {
      enabled: config?.enabled ?? true,
      safeReload: config?.safeReload ?? true,
      dependencyTracking: config?.dependencyTracking ?? true,
      statePreservation: config?.statePreservation ?? true,
      rollbackOnError: config?.rollbackOnError ?? true,
      preReloadHooks: config?.preReloadHooks ?? [],
      postReloadHooks: config?.postReloadHooks ?? []
    };
  }

  private normalizeUIReloadConfig(config: any) {
    return {
      enabled: config?.enabled ?? true,
      webview2Integration: config?.webview2Integration ?? true,
      hmrPort: config?.hmrPort ?? 3002,
      reactRefresh: config?.reactRefresh ?? true,
      vueHmr: config?.vueHmr ?? true,
      cssHotReload: config?.cssHotReload ?? true,
      assetPipeline: config?.assetPipeline ?? true
    };
  }

  private normalizeErrorRecoveryConfig(config: any) {
    return {
      enabled: config?.enabled ?? true,
      maxRetries: config?.maxRetries ?? 3,
      rollbackTimeout: config?.rollbackTimeout ?? 5000,
      syntaxErrorHandling: config?.syntaxErrorHandling ?? true,
      runtimeErrorHandling: config?.runtimeErrorHandling ?? true,
      automaticRecovery: config?.automaticRecovery ?? true,
      userPrompting: config?.userPrompting ?? false
    };
  }

  private normalizePerformanceConfig(config: any) {
    return {
      monitoring: config?.monitoring ?? true,
      metrics: config?.metrics ?? true,
      profiling: config?.profiling ?? false,
      benchmarking: config?.benchmarking ?? false,
      optimization: config?.optimization ?? true,
      caching: config?.caching ?? true,
      memoryManagement: config?.memoryManagement ?? true
    };
  }

  private normalizeRevitConfig(config: any) {
    return {
      enabled: config?.enabled ?? true,
      host: config?.host ?? 'localhost',
      port: config?.port ?? 5678,
      autoConnect: config?.autoConnect ?? true,
      reconnectInterval: config?.reconnectInterval ?? 5000,
      commandTimeout: config?.commandTimeout ?? 10000
    };
  }

  private normalizeVSCodeConfig(config: any) {
    return {
      enabled: config?.enabled ?? true,
      port: config?.port ?? 3003,
      debugAdapter: config?.debugAdapter ?? true,
      problemMatcher: config?.problemMatcher ?? true
    };
  }

  private normalizeWebViewConfig(config: any) {
    return {
      enabled: config?.enabled ?? true,
      port: config?.port ?? 3004,
      devTools: config?.devTools ?? true,
      securityDisabled: config?.securityDisabled ?? true
    };
  }
}
