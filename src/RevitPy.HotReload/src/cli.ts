#!/usr/bin/env node

import { Command } from 'commander';
import chalk from 'chalk';
import { existsSync, readFileSync } from 'fs';
import path from 'path';
import { HotReloadServer } from './server.js';
import type { ServerConfig } from './types.js';

const program = new Command();

// Package info
const packageJson = JSON.parse(
  readFileSync(new URL('../package.json', import.meta.url), 'utf-8')
);

program
  .name('revitpy-dev')
  .description('RevitPy Hot Reload Development Server')
  .version(packageJson.version);

program
  .command('start')
  .description('Start the development server')
  .option('-p, --port <port>', 'Server port', '3000')
  .option('-h, --host <host>', 'Server host', 'localhost')
  .option('--watch <paths...>', 'Paths to watch for changes', ['src'])
  .option('--no-hot-reload', 'Disable hot reload')
  .option('--no-revit', 'Disable Revit integration')
  .option('--revit-port <port>', 'Revit connection port', '5678')
  .option('--config <file>', 'Configuration file path')
  .option('--log-level <level>', 'Log level (debug, info, warn, error)', 'info')
  .option('--build-dir <dir>', 'Build output directory', 'dist')
  .option('--entry <file>', 'Entry file path', 'src/main.py')
  .option('--no-source-maps', 'Disable source maps')
  .option('--minify', 'Minify output')
  .action(async (options) => {
    try {
      const config = await loadConfig(options);
      const server = new HotReloadServer(config);
      
      // Handle graceful shutdown
      process.on('SIGINT', async () => {
        console.log(chalk.yellow('\nShutting down server...'));
        await server.stop();
        process.exit(0);
      });

      process.on('SIGTERM', async () => {
        await server.stop();
        process.exit(0);
      });

      await server.start();
    } catch (error) {
      console.error(chalk.red('Failed to start server:'), error);
      process.exit(1);
    }
  });

program
  .command('build')
  .description('Build the project')
  .option('--config <file>', 'Configuration file path')
  .option('--watch', 'Watch mode')
  .option('--minify', 'Minify output')
  .option('--source-maps', 'Generate source maps')
  .option('--out-dir <dir>', 'Output directory', 'dist')
  .option('--entry <file>', 'Entry file path', 'src/main.py')
  .action(async (options) => {
    try {
      const config = await loadConfig(options);
      const { BuildSystem } = await import('./build/buildSystem.js');
      const { AssetProcessor } = await import('./processors/assetProcessor.js');
      
      const assetProcessor = new AssetProcessor(config);
      const buildSystem = new BuildSystem(config, assetProcessor);
      
      if (options.watch) {
        console.log(chalk.blue('Starting build in watch mode...'));
        // Implement watch mode
      } else {
        console.log(chalk.blue('Building project...'));
        const result = await buildSystem.build();
        
        if (result.success) {
          console.log(chalk.green('Build completed successfully!'));
          if (result.stats) {
            console.log(chalk.gray(`Time: ${result.stats.totalTime}ms`));
            console.log(chalk.gray(`Size: ${formatBytes(result.stats.bundleSize)}`));
            console.log(chalk.gray(`Assets: ${result.stats.assetCount}`));
          }
        } else {
          console.error(chalk.red('Build failed:'));
          result.errors?.forEach(error => {
            console.error(chalk.red(`  ${error.message}`));
            if (error.file) {
              console.error(chalk.gray(`    at ${error.file}:${error.line}:${error.column}`));
            }
          });
          process.exit(1);
        }
      }
    } catch (error) {
      console.error(chalk.red('Build error:'), error);
      process.exit(1);
    }
  });

program
  .command('init')
  .description('Initialize a new RevitPy project')
  .option('--template <name>', 'Project template', 'basic')
  .option('--name <name>', 'Project name')
  .option('--author <author>', 'Project author')
  .action(async (options) => {
    try {
      const { ProjectGenerator } = await import('./generators/projectGenerator.js');
      const generator = new ProjectGenerator();
      
      const projectConfig = {
        name: options.name || path.basename(process.cwd()),
        template: options.template,
        author: options.author || process.env.USER || process.env.USERNAME,
        directory: process.cwd()
      };
      
      console.log(chalk.blue('Initializing RevitPy project...'));
      await generator.generate(projectConfig);
      
      console.log(chalk.green('Project initialized successfully!'));
      console.log(chalk.gray('Next steps:'));
      console.log(chalk.gray('  1. Install dependencies: npm install'));
      console.log(chalk.gray('  2. Start development: revitpy-dev start'));
      
    } catch (error) {
      console.error(chalk.red('Initialization failed:'), error);
      process.exit(1);
    }
  });

program
  .command('config')
  .description('Show current configuration')
  .option('--config <file>', 'Configuration file path')
  .action(async (options) => {
    try {
      const config = await loadConfig(options);
      console.log(chalk.blue('Current configuration:'));
      console.log(JSON.stringify(config, null, 2));
    } catch (error) {
      console.error(chalk.red('Configuration error:'), error);
      process.exit(1);
    }
  });

program
  .command('doctor')
  .description('Check system requirements and configuration')
  .action(async () => {
    console.log(chalk.blue('RevitPy Development Environment Check\n'));
    
    // Check Node.js version
    const nodeVersion = process.version;
    const requiredNode = '18.0.0';
    console.log(`Node.js version: ${nodeVersion}`);
    
    // Check Python
    try {
      const { execSync } = await import('child_process');
      const pythonVersion = execSync('python --version', { encoding: 'utf-8' });
      console.log(`Python version: ${pythonVersion.trim()}`);
    } catch {
      console.log(chalk.yellow('Python not found in PATH'));
    }
    
    // Check Revit installation
    const revitPaths = [
      'C:\\Program Files\\Autodesk\\Revit 2024',
      'C:\\Program Files\\Autodesk\\Revit 2023',
      'C:\\Program Files\\Autodesk\\Revit 2022'
    ];
    
    const revitInstalled = revitPaths.find(existsSync);
    if (revitInstalled) {
      console.log(`Revit installation: ${revitInstalled}`);
    } else {
      console.log(chalk.yellow('Revit installation not detected'));
    }
    
    // Check configuration
    try {
      const config = await loadConfig({});
      console.log(chalk.green('\nConfiguration loaded successfully'));
    } catch (error) {
      console.log(chalk.red(`\nConfiguration error: ${error}`));
    }
    
    console.log(chalk.green('\nSystem check completed'));
  });

async function loadConfig(options: any): Promise<ServerConfig> {
  const configFile = options.config || 'revitpy.config.js';
  const configPath = path.resolve(configFile);
  
  let fileConfig: Partial<ServerConfig> = {};
  
  // Try to load configuration file
  if (existsSync(configPath)) {
    try {
      console.log(chalk.blue(`Loading config from ${configPath}`));
      const configModule = await import(configPath);
      fileConfig = configModule.default || configModule;
    } catch (error) {
      console.warn(chalk.yellow(`Failed to load config file: ${error}`));
    }
  }
  
  // Merge with command line options
  const config: ServerConfig = {
    port: parseInt(options.port) || fileConfig.port || 3000,
    host: options.host || fileConfig.host || 'localhost',
    watchPaths: options.watch || fileConfig.watchPaths || ['src'],
    buildConfig: {
      entry: options.entry || fileConfig.buildConfig?.entry || 'src/main.py',
      outDir: options.buildDir || fileConfig.buildConfig?.outDir || 'dist',
      sourceMaps: options.sourceMaps !== false && fileConfig.buildConfig?.sourceMaps !== false,
      minify: options.minify || fileConfig.buildConfig?.minify || false,
      target: fileConfig.buildConfig?.target || 'es2020',
      ...fileConfig.buildConfig
    },
    hotReload: {
      enabled: options.hotReload !== false && fileConfig.hotReload?.enabled !== false,
      debounceMs: fileConfig.hotReload?.debounceMs || 300,
      includeNodeModules: fileConfig.hotReload?.includeNodeModules || false,
      ...fileConfig.hotReload
    },
    revit: {
      enabled: options.revit !== false && fileConfig.revit?.enabled !== false,
      port: parseInt(options.revitPort) || fileConfig.revit?.port || 5678,
      host: fileConfig.revit?.host || 'localhost',
      autoConnect: fileConfig.revit?.autoConnect !== false,
      ...fileConfig.revit
    },
    logging: {
      level: options.logLevel || fileConfig.logging?.level || 'info',
      timestamp: fileConfig.logging?.timestamp !== false,
      colorize: fileConfig.logging?.colorize !== false,
      ...fileConfig.logging
    },
    ...fileConfig
  };
  
  return config;
}

function formatBytes(bytes: number): string {
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = bytes;
  let unitIndex = 0;
  
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }
  
  return `${size.toFixed(1)} ${units[unitIndex]}`;
}

// Handle unhandled errors
process.on('unhandledRejection', (error) => {
  console.error(chalk.red('Unhandled rejection:'), error);
  process.exit(1);
});

process.on('uncaughtException', (error) => {
  console.error(chalk.red('Uncaught exception:'), error);
  process.exit(1);
});

program.parse();