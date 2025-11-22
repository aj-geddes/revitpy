#!/usr/bin/env node

/**
 * RevitPy Development Server CLI
 * Command-line interface for starting and managing the development server
 */

import { program } from 'commander';
import path from 'path';
import { fileURLToPath } from 'url';
import { promises as fs } from 'fs';
import chalk from 'chalk';
import { performance } from 'perf_hooks';

import { DevServer } from './core/DevServer.js';
import type { DevServerConfig } from './types/index.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Package info
let packageInfo: any = {};
try {
  const packagePath = path.join(__dirname, '..', 'package.json');
  const packageData = await fs.readFile(packagePath, 'utf-8');
  packageInfo = JSON.parse(packageData);
} catch {
  packageInfo = { version: '1.0.0', name: 'revitpy-dev-server' };
}

program
  .name('revitpy-dev-server')
  .description('High-performance hot-reload development server for RevitPy')
  .version(packageInfo.version);

/**
 * Start command - Launch the development server
 */
program
  .command('start')
  .description('Start the RevitPy development server')
  .option('-p, --port <port>', 'HTTP server port', '3000')
  .option('-w, --ws-port <port>', 'WebSocket server port', '3001')
  .option('-h, --host <host>', 'Host to bind to', 'localhost')
  .option('-r, --root <path>', 'Project root directory', process.cwd())
  .option('-o, --output <path>', 'Build output directory', 'dist')
  .option('--watch <paths...>', 'Directories to watch for changes', ['src'])
  .option('--debounce <ms>', 'File change debounce delay (ms)', '300')
  .option('--no-hot-reload', 'Disable hot module replacement')
  .option('--no-python-reload', 'Disable Python module reloading')
  .option('--no-ui-reload', 'Disable UI hot reloading')
  .option('--no-error-recovery', 'Disable automatic error recovery')
  .option('--no-performance', 'Disable performance monitoring')
  .option('--no-revit', 'Disable Revit integration')
  .option('--no-vscode', 'Disable VS Code integration')
  .option('--no-webview', 'Disable WebView2 integration')
  .option('--config <path>', 'Configuration file path')
  .option('--log-level <level>', 'Log level (debug, info, warn, error)', 'info')
  .option('--max-reload-time <ms>', 'Maximum reload time before timeout (ms)', '5000')
  .option('--parallel-processes <count>', 'Number of parallel processes', '4')
  .option('--profile', 'Enable performance profiling')
  .option('--benchmark', 'Enable benchmarking mode')
  .action(async (options) => {
    const startTime = performance.now();

    try {
      console.log(chalk.blue.bold(`🚀 Starting RevitPy Development Server v${packageInfo.version}`));
      console.log(chalk.gray('High-performance hot-reload server with <500ms Python and <200ms UI reload times\n'));

      // Load configuration
      const config = await loadConfiguration(options);

      // Validate configuration
      await validateConfiguration(config);

      // Create and start server
      const server = new DevServer(config);

      // Set up graceful shutdown
      setupGracefulShutdown(server);

      // Start the server
      await server.start();

      const startupTime = Math.round(performance.now() - startTime);
      console.log(chalk.green(`\n✅ Server started successfully in ${startupTime}ms`));

      // Display connection info
      displayServerInfo(config);

      // Display feature status
      displayFeatureStatus(config);

      if (options.benchmark) {
        await runBenchmarks(server);
      }

    } catch (error) {
      console.error(chalk.red('❌ Failed to start server:'));
      console.error(chalk.red(error.message));

      if (options.logLevel === 'debug') {
        console.error(chalk.gray(error.stack));
      }

      process.exit(1);
    }
  });

/**
 * Status command - Check server status
 */
program
  .command('status')
  .description('Check the status of running development server')
  .option('-p, --port <port>', 'Server port to check', '3000')
  .option('-h, --host <host>', 'Server host', 'localhost')
  .action(async (options) => {
    try {
      const response = await fetch(`http://${options.host}:${options.port}/health`);
      const data = await response.json();

      console.log(chalk.green('✅ Server is running'));
      console.log(chalk.blue('Server Information:'));
      console.log(`  Status: ${data.status}`);
      console.log(`  Uptime: ${Math.round(data.uptime)}s`);
      console.log(`  Version: ${data.version}`);
      console.log(`  Clients: ${data.clients}`);
      console.log(`  Reload Count: ${data.reloadCount}`);

      if (data.metrics) {
        console.log(chalk.blue('\nPerformance Metrics:'));
        console.log(`  Build Time: ${Math.round(data.metrics.buildTime)}ms`);
        console.log(`  Memory Usage: ${Math.round(data.metrics.memoryUsage.heapUsed / 1024 / 1024)}MB`);
        console.log(`  CPU Usage: ${data.metrics.cpuUsage?.percent?.toFixed(1) || 'N/A'}%`);
      }

    } catch (error) {
      if (error.code === 'ECONNREFUSED') {
        console.log(chalk.yellow('⚠️  Server is not running'));
      } else {
        console.error(chalk.red('❌ Error checking server status:'));
        console.error(chalk.red(error.message));
      }
      process.exit(1);
    }
  });

/**
 * Stop command - Stop running server
 */
program
  .command('stop')
  .description('Stop the running development server')
  .option('-p, --port <port>', 'Server port', '3000')
  .option('-h, --host <host>', 'Server host', 'localhost')
  .action(async (options) => {
    try {
      const response = await fetch(`http://${options.host}:${options.port}/api/shutdown`, {
        method: 'POST'
      });

      if (response.ok) {
        console.log(chalk.green('✅ Server stopped successfully'));
      } else {
        throw new Error(`Server returned ${response.status}`);
      }
    } catch (error) {
      if (error.code === 'ECONNREFUSED') {
        console.log(chalk.yellow('⚠️  Server is not running'));
      } else {
        console.error(chalk.red('❌ Error stopping server:'));
        console.error(chalk.red(error.message));
      }
      process.exit(1);
    }
  });

/**
 * Config command - Generate or validate configuration
 */
program
  .command('config')
  .description('Generate or validate configuration file')
  .option('--init', 'Create a new configuration file')
  .option('--validate [path]', 'Validate configuration file')
  .option('--output <path>', 'Output path for generated config', 'revitpy.config.json')
  .action(async (options) => {
    if (options.init) {
      await generateConfigFile(options.output);
    } else if (options.validate) {
      await validateConfigFile(options.validate || 'revitpy.config.json');
    } else {
      program.help();
    }
  });

/**
 * Benchmark command - Run performance benchmarks
 */
program
  .command('benchmark')
  .description('Run performance benchmarks')
  .option('-p, --port <port>', 'Server port', '3000')
  .option('-h, --host <host>', 'Server host', 'localhost')
  .option('--iterations <count>', 'Number of benchmark iterations', '10')
  .option('--concurrent <count>', 'Concurrent connections', '5')
  .action(async (options) => {
    console.log(chalk.blue.bold('🏃 Running RevitPy DevServer Benchmarks\n'));

    try {
      await runPerformanceBenchmarks(options);
    } catch (error) {
      console.error(chalk.red('❌ Benchmark failed:'));
      console.error(chalk.red(error.message));
      process.exit(1);
    }
  });

// Parse command line arguments
program.parse();

// Helper Functions

async function loadConfiguration(options: any): Promise<DevServerConfig> {
  let config: Partial<DevServerConfig> = {};

  // Load from config file if specified
  if (options.config) {
    try {
      const configData = await fs.readFile(options.config, 'utf-8');
      config = JSON.parse(configData);
      console.log(chalk.green(`📄 Loaded configuration from ${options.config}`));
    } catch (error) {
      console.warn(chalk.yellow(`⚠️  Could not load config file: ${error.message}`));
    }
  }

  // Override with command line options
  const cliConfig: Partial<DevServerConfig> = {
    host: options.host,
    port: parseInt(options.port),
    websocketPort: parseInt(options.wsPort),
    projectRoot: path.resolve(options.root),
    watchPaths: options.watch,
    buildOutputPath: options.output,
    debounceMs: parseInt(options.debounce),
    maxReloadTime: parseInt(options.maxReloadTime),
    parallelProcesses: parseInt(options.parallelProcesses),

    hotReload: {
      enabled: options.hotReload,
      pythonModules: options.pythonReload,
      uiComponents: options.uiReload,
      staticAssets: true,
      excludePatterns: [],
      includePatterns: [],
      preserveState: true
    },

    moduleReloader: {
      enabled: options.pythonReload,
      safeReload: true,
      dependencyTracking: true,
      statePreservation: true,
      rollbackOnError: true,
      preReloadHooks: [],
      postReloadHooks: []
    },

    uiReload: {
      enabled: options.uiReload,
      webview2Integration: options.webview,
      hmrPort: parseInt(options.wsPort) + 1,
      reactRefresh: true,
      vueHmr: true,
      cssHotReload: true,
      assetPipeline: true
    },

    errorRecovery: {
      enabled: options.errorRecovery,
      maxRetries: 3,
      rollbackTimeout: 5000,
      syntaxErrorHandling: true,
      runtimeErrorHandling: true,
      automaticRecovery: true,
      userPrompting: false
    },

    performance: {
      monitoring: options.performance,
      metrics: options.performance,
      profiling: options.profile,
      benchmarking: options.benchmark,
      optimization: true,
      caching: true,
      memoryManagement: true
    },

    revit: {
      enabled: options.revit,
      host: 'localhost',
      port: 5678,
      autoConnect: true,
      reconnectInterval: 5000,
      commandTimeout: 10000
    },

    vscode: {
      enabled: options.vscode,
      port: parseInt(options.wsPort) + 2,
      debugAdapter: true,
      problemMatcher: true
    },

    webview: {
      enabled: options.webview,
      port: parseInt(options.wsPort) + 3,
      devTools: true,
      securityDisabled: true
    }
  };

  // Merge configurations (CLI options override config file)
  return { ...config, ...cliConfig } as DevServerConfig;
}

async function validateConfiguration(config: DevServerConfig): Promise<void> {
  const issues: string[] = [];

  // Check project root
  try {
    const stats = await fs.stat(config.projectRoot);
    if (!stats.isDirectory()) {
      issues.push(`Project root is not a directory: ${config.projectRoot}`);
    }
  } catch {
    issues.push(`Project root does not exist: ${config.projectRoot}`);
  }

  // Check watch paths
  for (const watchPath of config.watchPaths) {
    const fullPath = path.isAbsolute(watchPath)
      ? watchPath
      : path.join(config.projectRoot, watchPath);

    try {
      await fs.access(fullPath);
    } catch {
      console.warn(chalk.yellow(`⚠️  Watch path does not exist: ${watchPath}`));
    }
  }

  if (issues.length > 0) {
    console.error(chalk.red('❌ Configuration validation failed:'));
    issues.forEach(issue => console.error(chalk.red(`  • ${issue}`)));
    process.exit(1);
  }

  console.log(chalk.green('✅ Configuration validated'));
}

function setupGracefulShutdown(server: DevServer): void {
  const shutdown = async (signal: string) => {
    console.log(chalk.yellow(`\n⚠️  Received ${signal}, shutting down gracefully...`));

    try {
      await server.stop();
      console.log(chalk.green('✅ Server stopped gracefully'));
      process.exit(0);
    } catch (error) {
      console.error(chalk.red('❌ Error during shutdown:'));
      console.error(chalk.red(error.message));
      process.exit(1);
    }
  };

  process.on('SIGINT', () => shutdown('SIGINT'));
  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGUSR2', () => shutdown('SIGUSR2')); // For nodemon

  process.on('uncaughtException', (error) => {
    console.error(chalk.red('❌ Uncaught exception:'));
    console.error(chalk.red(error.message));
    console.error(chalk.gray(error.stack));
    shutdown('uncaughtException');
  });

  process.on('unhandledRejection', (reason, promise) => {
    console.error(chalk.red('❌ Unhandled rejection at:'), promise);
    console.error(chalk.red('Reason:'), reason);
    shutdown('unhandledRejection');
  });
}

function displayServerInfo(config: DevServerConfig): void {
  console.log(chalk.blue.bold('\n🌐 Server Information:'));
  console.log(`  Local:     ${chalk.cyan(`http://${config.host}:${config.port}`)}`);
  console.log(`  WebSocket: ${chalk.cyan(`ws://${config.host}:${config.websocketPort}`)}`);
  console.log(`  Root:      ${chalk.gray(config.projectRoot)}`);
  console.log(`  Output:    ${chalk.gray(config.buildOutputPath)}`);
  console.log(`  Watch:     ${chalk.gray(config.watchPaths.join(', '))}`);
}

function displayFeatureStatus(config: DevServerConfig): void {
  console.log(chalk.blue.bold('\n⚙️  Feature Status:'));
  console.log(`  Hot Reload:        ${config.hotReload.enabled ? '✅' : '❌'}`);
  console.log(`  Python Modules:    ${config.moduleReloader.enabled ? '✅' : '❌'}`);
  console.log(`  UI Components:     ${config.uiReload.enabled ? '✅' : '❌'}`);
  console.log(`  Error Recovery:    ${config.errorRecovery.enabled ? '✅' : '❌'}`);
  console.log(`  Performance:       ${config.performance.monitoring ? '✅' : '❌'}`);

  console.log(chalk.blue.bold('\n🔌 Integrations:'));
  console.log(`  Revit:             ${config.revit.enabled ? '✅' : '❌'}`);
  console.log(`  VS Code:           ${config.vscode.enabled ? '✅' : '❌'}`);
  console.log(`  WebView2:          ${config.webview.enabled ? '✅' : '❌'}`);
}

async function generateConfigFile(outputPath: string): Promise<void> {
  const defaultConfig: DevServerConfig = {
    host: 'localhost',
    port: 3000,
    websocketPort: 3001,
    projectRoot: process.cwd(),
    watchPaths: ['src'],
    buildOutputPath: 'dist',
    debounceMs: 300,
    maxReloadTime: 5000,
    parallelProcesses: 4,
    hotReload: {
      enabled: true,
      pythonModules: true,
      uiComponents: true,
      staticAssets: true,
      excludePatterns: ['**/*.pyc', '**/node_modules/**', '**/.git/**'],
      includePatterns: [],
      preserveState: true
    },
    moduleReloader: {
      enabled: true,
      safeReload: true,
      dependencyTracking: true,
      statePreservation: true,
      rollbackOnError: true,
      preReloadHooks: [],
      postReloadHooks: []
    },
    uiReload: {
      enabled: true,
      webview2Integration: true,
      hmrPort: 3002,
      reactRefresh: true,
      vueHmr: true,
      cssHotReload: true,
      assetPipeline: true
    },
    errorRecovery: {
      enabled: true,
      maxRetries: 3,
      rollbackTimeout: 5000,
      syntaxErrorHandling: true,
      runtimeErrorHandling: true,
      automaticRecovery: true,
      userPrompting: false
    },
    performance: {
      monitoring: true,
      metrics: true,
      profiling: false,
      benchmarking: false,
      optimization: true,
      caching: true,
      memoryManagement: true
    },
    revit: {
      enabled: true,
      host: 'localhost',
      port: 5678,
      autoConnect: true,
      reconnectInterval: 5000,
      commandTimeout: 10000
    },
    vscode: {
      enabled: true,
      port: 3003,
      debugAdapter: true,
      problemMatcher: true
    },
    webview: {
      enabled: true,
      port: 3004,
      devTools: true,
      securityDisabled: true
    }
  };

  try {
    await fs.writeFile(outputPath, JSON.stringify(defaultConfig, null, 2));
    console.log(chalk.green(`✅ Configuration file generated: ${outputPath}`));
  } catch (error) {
    console.error(chalk.red('❌ Failed to generate config file:'));
    console.error(chalk.red(error.message));
    process.exit(1);
  }
}

async function validateConfigFile(configPath: string): Promise<void> {
  try {
    const configData = await fs.readFile(configPath, 'utf-8');
    const config = JSON.parse(configData);

    // Basic validation
    const requiredFields = ['host', 'port', 'projectRoot', 'watchPaths'];
    const missing = requiredFields.filter(field => !(field in config));

    if (missing.length > 0) {
      console.error(chalk.red(`❌ Missing required fields: ${missing.join(', ')}`));
      process.exit(1);
    }

    console.log(chalk.green(`✅ Configuration file is valid: ${configPath}`));
  } catch (error) {
    if (error.code === 'ENOENT') {
      console.error(chalk.red(`❌ Configuration file not found: ${configPath}`));
    } else if (error instanceof SyntaxError) {
      console.error(chalk.red(`❌ Configuration file has invalid JSON: ${error.message}`));
    } else {
      console.error(chalk.red(`❌ Error validating config: ${error.message}`));
    }
    process.exit(1);
  }
}

async function runBenchmarks(server: DevServer): Promise<void> {
  console.log(chalk.blue.bold('\n🏃 Running Performance Benchmarks...\n'));

  // Warmup
  console.log(chalk.gray('Warming up...'));
  await new Promise(resolve => setTimeout(resolve, 2000));

  // File change benchmark
  console.log(chalk.blue('📁 File Change Performance:'));
  const fileChangeResults = await benchmarkFileChanges(server, 10);
  console.log(`  Average: ${fileChangeResults.average}ms`);
  console.log(`  Min: ${fileChangeResults.min}ms`);
  console.log(`  Max: ${fileChangeResults.max}ms`);
  console.log(`  Target: <500ms (Python), <200ms (UI)`);

  // Memory usage
  console.log(chalk.blue('\n💾 Memory Usage:'));
  const memoryUsage = process.memoryUsage();
  console.log(`  RSS: ${Math.round(memoryUsage.rss / 1024 / 1024)}MB`);
  console.log(`  Heap Used: ${Math.round(memoryUsage.heapUsed / 1024 / 1024)}MB`);
  console.log(`  Heap Total: ${Math.round(memoryUsage.heapTotal / 1024 / 1024)}MB`);

  // WebSocket performance
  console.log(chalk.blue('\n🔌 WebSocket Performance:'));
  const clients = server.getClients();
  console.log(`  Connected Clients: ${clients.length}`);

  const metrics = server.getPerformanceMetrics();
  console.log(`  Messages/sec: ${Math.round(60000 / (metrics.buildTime || 1))}`);
  console.log(`  Network Latency: ${metrics.networkLatency || 0}ms`);
}

async function benchmarkFileChanges(server: DevServer, iterations: number): Promise<{
  average: number;
  min: number;
  max: number;
}> {
  const times: number[] = [];

  for (let i = 0; i < iterations; i++) {
    const startTime = performance.now();

    // Simulate file change by triggering rebuild
    await server.rebuild();

    const duration = Math.round(performance.now() - startTime);
    times.push(duration);

    // Small delay between iterations
    await new Promise(resolve => setTimeout(resolve, 100));
  }

  return {
    average: Math.round(times.reduce((sum, time) => sum + time, 0) / times.length),
    min: Math.min(...times),
    max: Math.max(...times)
  };
}

async function runPerformanceBenchmarks(options: any): Promise<void> {
  const iterations = parseInt(options.iterations);
  const concurrent = parseInt(options.concurrent);
  const serverUrl = `http://${options.host}:${options.port}`;

  console.log(chalk.gray(`Testing against ${serverUrl} with ${iterations} iterations and ${concurrent} concurrent connections\n`));

  // Test server response time
  console.log(chalk.blue('🚀 Server Response Time:'));
  const responseTimes: number[] = [];

  for (let i = 0; i < iterations; i++) {
    const startTime = performance.now();

    try {
      await fetch(`${serverUrl}/health`);
      const responseTime = Math.round(performance.now() - startTime);
      responseTimes.push(responseTime);
    } catch (error) {
      console.error(chalk.red(`  Error in iteration ${i + 1}: ${error.message}`));
    }
  }

  if (responseTimes.length > 0) {
    const avgResponse = Math.round(responseTimes.reduce((sum, time) => sum + time, 0) / responseTimes.length);
    console.log(`  Average: ${avgResponse}ms`);
    console.log(`  Min: ${Math.min(...responseTimes)}ms`);
    console.log(`  Max: ${Math.max(...responseTimes)}ms`);
  }

  console.log(chalk.green('\n✅ Benchmark completed'));
}

export { DevServer, DevServerConfig };
