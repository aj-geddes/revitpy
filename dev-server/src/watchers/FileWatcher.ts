/**
 * High-Performance File Watcher Service
 * Optimized for <100ms change detection with intelligent filtering
 */

import { EventEmitter } from 'events';
import chokidar from 'chokidar';
import { performance } from 'perf_hooks';
import path from 'path';
import { promises as fs } from 'fs';
import { createHash } from 'crypto';
import { debounce } from 'debounce';
import pino from 'pino';

import type {
  DevServerConfig,
  FileChangeEvent,
  FileMetadata,
  WatcherStats
} from '../types/index.js';

interface WatchedFile {
  path: string;
  hash: string;
  size: number;
  lastModified: number;
  dependencies?: string[];
}

interface ChangeQueue {
  [filePath: string]: {
    event: FileChangeEvent;
    timer: NodeJS.Timeout;
    attempts: number;
  };
}

export class FileWatcherService extends EventEmitter {
  private config: DevServerConfig;
  private logger: pino.Logger;
  private watcher: chokidar.FSWatcher | null = null;
  private isWatching = false;
  private watchedFiles = new Map<string, WatchedFile>();
  private changeQueue: ChangeQueue = {};
  private stats: WatcherStats;
  private dependencyGraph = new Map<string, Set<string>>();

  // Performance optimization
  private debouncedProcessQueue: () => void;
  private fileHashCache = new Map<string, { hash: string; mtime: number }>();
  private ignoredPatterns: Set<string>;

  constructor(config: DevServerConfig, logger?: pino.Logger) {
    super();
    this.config = config;
    this.logger = logger || pino({ name: 'FileWatcher' });

    this.stats = {
      watchedFiles: 0,
      ignoredFiles: 0,
      queuedChanges: 0,
      processingTime: 0
    };

    this.ignoredPatterns = new Set(this.buildIgnorePatterns());
    this.debouncedProcessQueue = debounce(
      this.processChangeQueue.bind(this),
      this.config.debounceMs
    );

    this.logger.info('FileWatcher service initialized', {
      watchPaths: this.config.watchPaths,
      debounceMs: this.config.debounceMs,
      ignoredPatterns: this.ignoredPatterns.size
    });
  }

  /**
   * Start watching files with high-performance monitoring
   */
  async start(): Promise<void> {
    if (this.isWatching) {
      throw new Error('FileWatcher is already running');
    }

    const startTime = performance.now();
    this.logger.info('Starting file watcher...');

    try {
      const watchOptions: chokidar.WatchOptions = {
        ignored: Array.from(this.ignoredPatterns),
        persistent: true,
        ignoreInitial: false, // We'll handle initial scan
        followSymlinks: false,
        depth: 20,
        awaitWriteFinish: {
          stabilityThreshold: 50, // Faster than default
          pollInterval: 10 // More frequent polling
        },
        usePolling: false, // Use native events for better performance
        interval: 100,
        binaryInterval: 300,
        alwaysStat: true, // Get file stats immediately
        atomic: true // Handle atomic writes properly
      };

      // Create watcher for all configured paths
      this.watcher = chokidar.watch(this.config.watchPaths, watchOptions);

      // Set up event listeners with performance optimization
      this.setupWatcherEvents();

      // Wait for initial scan to complete
      await this.waitForReady();

      // Build initial dependency graph
      await this.buildDependencyGraph();

      const startupTime = Math.round(performance.now() - startTime);
      this.isWatching = true;

      this.logger.info('File watcher started', {
        watchedFiles: this.stats.watchedFiles,
        startupTime,
        watchPaths: this.config.watchPaths
      });

      this.emit('ready');

    } catch (error) {
      this.logger.error('Failed to start file watcher', { error: error.message });
      throw error;
    }
  }

  /**
   * Stop file watching
   */
  async stop(): Promise<void> {
    if (!this.isWatching || !this.watcher) {
      return;
    }

    this.logger.info('Stopping file watcher...');

    // Clear all pending changes
    Object.values(this.changeQueue).forEach(({ timer }) => {
      clearTimeout(timer);
    });
    this.changeQueue = {};

    // Close watcher
    await this.watcher.close();
    this.watcher = null;
    this.isWatching = false;

    // Clear caches
    this.watchedFiles.clear();
    this.fileHashCache.clear();
    this.dependencyGraph.clear();

    this.logger.info('File watcher stopped');
    this.emit('stopped');
  }

  /**
   * Add a new path to watch
   */
  addPath(filePath: string): void {
    if (this.watcher && this.isWatching) {
      this.watcher.add(filePath);
      this.logger.debug('Added watch path', { path: filePath });
    }
  }

  /**
   * Remove a path from watching
   */
  removePath(filePath: string): void {
    if (this.watcher && this.isWatching) {
      this.watcher.unwatch(filePath);
      this.watchedFiles.delete(filePath);
      this.logger.debug('Removed watch path', { path: filePath });
    }
  }

  /**
   * Check if file is being watched
   */
  isFileWatched(filePath: string): boolean {
    return this.watchedFiles.has(path.resolve(filePath));
  }

  /**
   * Get current watcher statistics
   */
  getStats(): WatcherStats {
    return {
      ...this.stats,
      watchedFiles: this.watchedFiles.size,
      queuedChanges: Object.keys(this.changeQueue).length
    };
  }

  /**
   * Get dependency graph for a file
   */
  getDependencies(filePath: string): string[] {
    const resolvedPath = path.resolve(filePath);
    return Array.from(this.dependencyGraph.get(resolvedPath) || []);
  }

  /**
   * Force rebuild of dependency graph
   */
  async rebuildDependencyGraph(): Promise<void> {
    this.logger.info('Rebuilding dependency graph...');
    const startTime = performance.now();

    await this.buildDependencyGraph();

    const duration = Math.round(performance.now() - startTime);
    this.logger.info('Dependency graph rebuilt', { duration });
  }

  // Private Methods

  private setupWatcherEvents(): void {
    if (!this.watcher) return;

    // Optimized event handlers
    this.watcher
      .on('add', (filePath, stats) => {
        this.handleFileEvent(filePath, 'add', stats);
      })
      .on('change', (filePath, stats) => {
        this.handleFileEvent(filePath, 'change', stats);
      })
      .on('unlink', (filePath) => {
        this.handleFileEvent(filePath, 'unlink');
      })
      .on('addDir', (dirPath) => {
        this.handleFileEvent(dirPath, 'addDir');
      })
      .on('unlinkDir', (dirPath) => {
        this.handleFileEvent(dirPath, 'unlinkDir');
      })
      .on('error', (error) => {
        this.logger.error('File watcher error', { error: error.message });
        this.emit('error', error);
      })
      .on('ready', () => {
        this.logger.debug('Initial file scan complete');
      });
  }

  private handleFileEvent(filePath: string, eventType: string, stats?: any): void {
    const resolvedPath = path.resolve(filePath);

    // Skip if file should be ignored
    if (this.shouldIgnoreFile(resolvedPath)) {
      this.stats.ignoredFiles++;
      return;
    }

    // Create file change event
    const event: FileChangeEvent = {
      path: resolvedPath,
      type: eventType as any,
      timestamp: Date.now(),
      size: stats?.size,
      metadata: this.createFileMetadata(resolvedPath, stats)
    };

    // Add/update watched file info
    if (eventType !== 'unlink' && eventType !== 'unlinkDir' && stats) {
      this.updateWatchedFile(resolvedPath, stats);
    } else if (eventType === 'unlink') {
      this.watchedFiles.delete(resolvedPath);
      this.fileHashCache.delete(resolvedPath);
    }

    // Queue the change for debounced processing
    this.queueChange(resolvedPath, event);
  }

  private queueChange(filePath: string, event: FileChangeEvent): void {
    // Clear existing timer for this file
    if (this.changeQueue[filePath]) {
      clearTimeout(this.changeQueue[filePath].timer);
    }

    // Create new queued change
    this.changeQueue[filePath] = {
      event,
      timer: setTimeout(() => {
        this.processFileChange(filePath);
      }, this.config.debounceMs),
      attempts: (this.changeQueue[filePath]?.attempts || 0) + 1
    };

    this.stats.queuedChanges = Object.keys(this.changeQueue).length;
  }

  private async processFileChange(filePath: string): Promise<void> {
    const queuedChange = this.changeQueue[filePath];
    if (!queuedChange) return;

    const startTime = performance.now();

    try {
      const { event } = queuedChange;

      // Calculate file hash for change detection
      if (event.type === 'change' && await this.fileExists(filePath)) {
        const currentHash = await this.calculateFileHash(filePath);
        const cachedHash = this.fileHashCache.get(filePath);

        // Skip if file hasn't actually changed
        if (cachedHash && cachedHash.hash === currentHash) {
          this.logger.debug('File hash unchanged, skipping', { path: filePath });
          delete this.changeQueue[filePath];
          return;
        }

        event.hash = currentHash;
        this.fileHashCache.set(filePath, {
          hash: currentHash,
          mtime: Date.now()
        });
      }

      // Update dependency graph if needed
      if (this.isSourceFile(filePath)) {
        await this.updateFileDependencies(filePath);
      }

      // Emit the file change event
      this.emit('file-changed', event);

      const duration = Math.round(performance.now() - startTime);
      this.stats.processingTime += duration;

      this.logger.debug('File change processed', {
        path: filePath,
        type: event.type,
        duration,
        hash: event.hash
      });

    } catch (error) {
      this.logger.error('Error processing file change', {
        path: filePath,
        error: error.message,
        attempts: queuedChange.attempts
      });

      // Retry on error (up to 3 times)
      if (queuedChange.attempts < 3) {
        this.queueChange(filePath, queuedChange.event);
        return;
      }
    }

    // Remove from queue
    delete this.changeQueue[filePath];
    this.stats.queuedChanges = Object.keys(this.changeQueue).length;
  }

  private async processChangeQueue(): Promise<void> {
    const filePaths = Object.keys(this.changeQueue);
    if (filePaths.length === 0) return;

    this.logger.debug('Processing change queue', { count: filePaths.length });

    // Process changes in parallel for better performance
    await Promise.all(
      filePaths.map(filePath => this.processFileChange(filePath))
    );
  }

  private updateWatchedFile(filePath: string, stats: any): void {
    const watchedFile: WatchedFile = {
      path: filePath,
      hash: '', // Will be calculated lazily
      size: stats.size || 0,
      lastModified: stats.mtimeMs || Date.now(),
      dependencies: []
    };

    this.watchedFiles.set(filePath, watchedFile);
    this.stats.watchedFiles = this.watchedFiles.size;
  }

  private createFileMetadata(filePath: string, stats?: any): FileMetadata {
    const ext = path.extname(filePath).toLowerCase();
    const isDir = stats ? stats.isDirectory() : false;

    return {
      isDirectory: isDir,
      isFile: !isDir,
      extension: ext,
      mimeType: this.getMimeType(ext),
      encoding: this.getFileEncoding(ext)
    };
  }

  private getMimeType(extension: string): string {
    const mimeTypes: Record<string, string> = {
      '.py': 'text/x-python',
      '.js': 'application/javascript',
      '.ts': 'text/typescript',
      '.jsx': 'text/jsx',
      '.tsx': 'text/tsx',
      '.css': 'text/css',
      '.scss': 'text/scss',
      '.html': 'text/html',
      '.json': 'application/json',
      '.yaml': 'application/yaml',
      '.yml': 'application/yaml'
    };

    return mimeTypes[extension] || 'text/plain';
  }

  private getFileEncoding(extension: string): string {
    const textExtensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.css', '.scss', '.html', '.json', '.yaml', '.yml', '.txt', '.md'];
    return textExtensions.includes(extension) ? 'utf-8' : 'binary';
  }

  private shouldIgnoreFile(filePath: string): boolean {
    const relativePath = path.relative(this.config.projectRoot, filePath);
    const fileName = path.basename(filePath);

    // Check against ignore patterns
    for (const pattern of this.ignoredPatterns) {
      if (this.matchesPattern(relativePath, pattern) ||
          this.matchesPattern(fileName, pattern)) {
        return true;
      }
    }

    // Additional performance-based filtering
    if (fileName.startsWith('.') && !fileName.startsWith('.env')) return true;
    if (fileName.endsWith('.tmp') || fileName.endsWith('.temp')) return true;
    if (filePath.includes('__pycache__')) return true;
    if (filePath.includes('node_modules')) return true;

    return false;
  }

  private matchesPattern(filePath: string, pattern: string): boolean {
    // Simple glob pattern matching
    const regex = new RegExp(
      pattern
        .replace(/\*\*/g, '.*')
        .replace(/\*/g, '[^/]*')
        .replace(/\?/g, '[^/]')
    );

    return regex.test(filePath);
  }

  private buildIgnorePatterns(): string[] {
    return [
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
      '**/out/**',

      // Cache directories
      '**/.cache/**',
      '**/__pycache__/**',
      '**/.pytest_cache/**',
      '**/coverage/**',
      '**/.nyc_output/**',

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

      // Lock files
      '**/package-lock.json',
      '**/yarn.lock',
      '**/poetry.lock',
      '**/Pipfile.lock',

      // User-defined patterns
      ...(this.config.hotReload.excludePatterns || [])
    ];
  }

  private async calculateFileHash(filePath: string): Promise<string> {
    try {
      const content = await fs.readFile(filePath);
      return createHash('md5').update(content).digest('hex');
    } catch (error) {
      this.logger.warn('Failed to calculate file hash', { path: filePath, error: error.message });
      return '';
    }
  }

  private async fileExists(filePath: string): Promise<boolean> {
    try {
      await fs.access(filePath);
      return true;
    } catch {
      return false;
    }
  }

  private isSourceFile(filePath: string): boolean {
    const sourceExtensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.vue', '.svelte'];
    return sourceExtensions.some(ext => filePath.endsWith(ext));
  }

  private async buildDependencyGraph(): Promise<void> {
    // This is a simplified dependency graph builder
    // In a real implementation, you'd parse import/require statements
    const startTime = performance.now();

    for (const [filePath] of this.watchedFiles) {
      if (this.isSourceFile(filePath)) {
        try {
          const dependencies = await this.extractDependencies(filePath);
          this.dependencyGraph.set(filePath, new Set(dependencies));
        } catch (error) {
          this.logger.warn('Failed to extract dependencies', {
            path: filePath,
            error: error.message
          });
        }
      }
    }

    const duration = Math.round(performance.now() - startTime);
    this.logger.debug('Dependency graph built', {
      files: this.dependencyGraph.size,
      duration
    });
  }

  private async extractDependencies(filePath: string): Promise<string[]> {
    // Simplified dependency extraction
    // Real implementation would use AST parsing
    try {
      const content = await fs.readFile(filePath, 'utf-8');
      const dependencies: string[] = [];

      // Python imports
      if (filePath.endsWith('.py')) {
        const importRegex = /^(?:from\s+(\S+)\s+import|import\s+(\S+))/gm;
        let match;
        while ((match = importRegex.exec(content)) !== null) {
          const module = match[1] || match[2];
          if (module && !module.startsWith('.')) {
            dependencies.push(module);
          }
        }
      }

      // JavaScript/TypeScript imports
      if (filePath.match(/\.(js|ts|jsx|tsx)$/)) {
        const importRegex = /^import.*from\s+['"]([^'"]+)['"]/gm;
        let match;
        while ((match = importRegex.exec(content)) !== null) {
          if (match[1].startsWith('./') || match[1].startsWith('../')) {
            const resolvedPath = path.resolve(path.dirname(filePath), match[1]);
            dependencies.push(resolvedPath);
          }
        }
      }

      return dependencies;
    } catch (error) {
      return [];
    }
  }

  private async updateFileDependencies(filePath: string): Promise<void> {
    try {
      const dependencies = await this.extractDependencies(filePath);
      this.dependencyGraph.set(filePath, new Set(dependencies));
    } catch (error) {
      this.logger.warn('Failed to update file dependencies', {
        path: filePath,
        error: error.message
      });
    }
  }

  private async waitForReady(): Promise<void> {
    if (!this.watcher) throw new Error('Watcher not initialized');

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('File watcher startup timeout'));
      }, 30000); // 30 second timeout

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
}
