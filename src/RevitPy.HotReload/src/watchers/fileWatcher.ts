import { EventEmitter } from 'events';
import chokidar from 'chokidar';
import path from 'path';
import chalk from 'chalk';
import type { ServerConfig, FileChangeEvent, WatcherOptions } from '../types.js';

export class FileWatcher extends EventEmitter {
  private watcher: chokidar.FSWatcher | null = null;
  private config: ServerConfig;
  private changeQueue = new Map<string, NodeJS.Timeout>();
  private isWatching = false;

  constructor(config: ServerConfig) {
    super();
    this.config = config;
  }

  async start(): Promise<void> {
    if (this.isWatching) {
      throw new Error('File watcher is already running');
    }

    const watchPaths = this.config.watchPaths || ['src'];
    const debounceMs = this.config.hotReload?.debounceMs || 300;

    const watchOptions: chokidar.WatchOptions = {
      ignored: this.getIgnorePatterns(),
      persistent: true,
      ignoreInitial: true,
      followSymlinks: false,
      depth: 99,
      awaitWriteFinish: {
        stabilityThreshold: 100,
        pollInterval: 100
      }
    };

    console.log(chalk.blue(`Starting file watcher for: ${watchPaths.join(', ')}`));

    this.watcher = chokidar.watch(watchPaths, watchOptions);

    // Set up event handlers
    this.watcher
      .on('add', (filePath) => this.handleChange(filePath, 'add', debounceMs))
      .on('change', (filePath) => this.handleChange(filePath, 'change', debounceMs))
      .on('unlink', (filePath) => this.handleChange(filePath, 'unlink', debounceMs))
      .on('addDir', (dirPath) => this.handleChange(dirPath, 'addDir', debounceMs))
      .on('unlinkDir', (dirPath) => this.handleChange(dirPath, 'unlinkDir', debounceMs))
      .on('error', (error) => {
        console.error(chalk.red('File watcher error:'), error);
        this.emit('error', error);
      })
      .on('ready', () => {
        this.isWatching = true;
        console.log(chalk.green('File watcher ready'));
        this.emit('ready');
      });

    // Wait for watcher to be ready
    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('File watcher startup timeout'));
      }, 10000);

      this.watcher!.on('ready', () => {
        clearTimeout(timeout);
        resolve();
      });

      this.watcher!.on('error', (error) => {
        clearTimeout(timeout);
        reject(error);
      });
    });
  }

  async stop(): Promise<void> {
    if (!this.isWatching || !this.watcher) {
      return;
    }

    console.log(chalk.yellow('Stopping file watcher...'));

    // Clear pending changes
    this.changeQueue.forEach(timeout => clearTimeout(timeout));
    this.changeQueue.clear();

    // Close watcher
    await this.watcher.close();
    this.watcher = null;
    this.isWatching = false;

    console.log(chalk.green('File watcher stopped'));
    this.emit('stopped');
  }

  addPath(filePath: string): void {
    if (this.watcher) {
      this.watcher.add(filePath);
      console.log(chalk.blue(`Added watch path: ${filePath}`));
    }
  }

  removePath(filePath: string): void {
    if (this.watcher) {
      this.watcher.unwatch(filePath);
      console.log(chalk.blue(`Removed watch path: ${filePath}`));
    }
  }

  getWatchedPaths(): string[] {
    if (!this.watcher) return [];
    return Object.keys(this.watcher.getWatched());
  }

  isFileWatched(filePath: string): boolean {
    if (!this.watcher) return false;
    const watched = this.watcher.getWatched();
    const dir = path.dirname(filePath);
    const fileName = path.basename(filePath);
    return watched[dir]?.includes(fileName) || false;
  }

  private handleChange(filePath: string, changeType: string, debounceMs: number): void {
    // Skip if file should be ignored
    if (this.shouldIgnoreFile(filePath)) {
      return;
    }

    const normalizedPath = path.normalize(filePath);

    // Debounce changes to the same file
    const existingTimeout = this.changeQueue.get(normalizedPath);
    if (existingTimeout) {
      clearTimeout(existingTimeout);
    }

    const timeout = setTimeout(() => {
      this.changeQueue.delete(normalizedPath);
      this.processChange(normalizedPath, changeType);
    }, debounceMs);

    this.changeQueue.set(normalizedPath, timeout);
  }

  private processChange(filePath: string, changeType: string): void {
    const event: FileChangeEvent = {
      path: filePath,
      type: changeType as any
    };

    // Add file stats if available
    try {
      const stats = require('fs').statSync(filePath);
      event.stats = stats;
    } catch {
      // File might have been deleted
    }

    console.log(chalk.cyan(`File ${changeType}: ${filePath}`));
    this.emit('change', filePath, changeType, event);
  }

  private getIgnorePatterns(): string[] {
    const defaultIgnored = [
      // Version control
      '**/.git/**',
      '**/.svn/**',
      '**/.hg/**',

      // Dependencies
      '**/node_modules/**',
      '**/venv/**',
      '**/.venv/**',
      '**/env/**',
      '**/.env/**',

      // Build outputs
      '**/dist/**',
      '**/build/**',
      '**/.next/**',
      '**/.nuxt/**',

      // Cache directories
      '**/.cache/**',
      '**/__pycache__/**',
      '**/.pytest_cache/**',
      '**/coverage/**',

      // IDE files
      '**/.vscode/**',
      '**/.idea/**',
      '**/*.swp',
      '**/*.swo',
      '**/*~',

      // OS files
      '**/Thumbs.db',
      '**/.DS_Store',

      // Log files
      '**/*.log',
      '**/logs/**',

      // Temporary files
      '**/*.tmp',
      '**/*.temp',
      '**/tmp/**',

      // Package files
      '**/*.pyc',
      '**/*.pyo',
      '**/*.pyd',
      '**/*.egg-info/**',

      // Config files that shouldn't trigger rebuilds
      '**/package-lock.json',
      '**/yarn.lock',
      '**/poetry.lock'
    ];

    // Add user-defined ignore patterns
    const userIgnored = this.config.hotReload?.excludePatterns || [];

    return [...defaultIgnored, ...userIgnored];
  }

  private shouldIgnoreFile(filePath: string): boolean {
    const normalizedPath = path.normalize(filePath);

    // Skip node_modules unless explicitly enabled
    if (!this.config.hotReload?.includeNodeModules &&
        normalizedPath.includes('node_modules')) {
      return true;
    }

    // Check file extension whitelist
    const allowedExtensions = [
      '.py', '.js', '.ts', '.jsx', '.tsx',
      '.css', '.scss', '.sass', '.less',
      '.html', '.htm', '.vue', '.svelte',
      '.json', '.yaml', '.yml', '.toml',
      '.md', '.txt', '.xml'
    ];

    const ext = path.extname(normalizedPath).toLowerCase();
    if (ext && !allowedExtensions.includes(ext)) {
      return true;
    }

    return false;
  }

  // Public methods for programmatic control
  pauseWatching(): void {
    if (this.watcher) {
      this.watcher.close();
    }
  }

  resumeWatching(): void {
    if (!this.isWatching) {
      this.start().catch(error => {
        console.error(chalk.red('Failed to resume watching:'), error);
      });
    }
  }

  getStats(): {
    isWatching: boolean;
    watchedFiles: number;
    queuedChanges: number;
  } {
    const watchedPaths = this.getWatchedPaths();
    let watchedFiles = 0;

    if (this.watcher) {
      const watched = this.watcher.getWatched();
      watchedFiles = Object.values(watched).reduce((sum, files) => sum + files.length, 0);
    }

    return {
      isWatching: this.isWatching,
      watchedFiles,
      queuedChanges: this.changeQueue.size
    };
  }
}

export default FileWatcher;
