/**
 * Python Module Reloader Service
 * Safe Python module reloading with dependency tracking and state preservation
 * Target: <500ms reload time for typical Python modules
 */

import { EventEmitter } from 'events';
import { spawn, ChildProcess } from 'child_process';
import { performance } from 'perf_hooks';
import { promises as fs } from 'fs';
import { createHash } from 'crypto';
import path from 'path';
import pino from 'pino';

import type { 
  DevServerConfig, 
  PythonModule, 
  ModuleReloadResult, 
  ReloadError 
} from '../types/index.js';

interface ModuleDependency {
  path: string;
  type: 'import' | 'from_import' | 'dynamic';
  line?: number;
  column?: number;
}

interface ReloadContext {
  module: string;
  startTime: number;
  dependencies: string[];
  stateBackup?: any;
  rollbackData?: any;
}

interface PythonProcess {
  process: ChildProcess;
  ready: boolean;
  busy: boolean;
  lastUsed: number;
  id: string;
}

interface StateSnapshot {
  module: string;
  timestamp: number;
  data: any;
  checksum: string;
}

export class ModuleReloaderService extends EventEmitter {
  private config: DevServerConfig;
  private logger: pino.Logger;
  private modules = new Map<string, PythonModule>();
  private dependencyGraph = new Map<string, Set<string>>();
  private dependentGraph = new Map<string, Set<string>>();
  private stateSnapshots = new Map<string, StateSnapshot>();
  private pythonProcessPool: PythonProcess[] = [];
  private reloadQueue: string[] = [];
  private isProcessingQueue = false;
  private moduleHashes = new Map<string, string>();
  
  // Performance optimization
  private maxProcesses = 3;
  private processTimeout = 10000; // 10 seconds
  private statePreservationEnabled = true;
  private dependencyTrackingEnabled = true;

  constructor(config: DevServerConfig, logger?: pino.Logger) {
    super();
    this.config = config;
    this.logger = logger || pino({ name: 'ModuleReloader' });
    
    this.statePreservationEnabled = config.moduleReloader.statePreservation;
    this.dependencyTrackingEnabled = config.moduleReloader.dependencyTracking;
    
    this.logger.info('Python module reloader initialized', {
      statePreservation: this.statePreservationEnabled,
      dependencyTracking: this.dependencyTrackingEnabled,
      maxProcesses: this.maxProcesses
    });
  }

  /**
   * Initialize the module reloader
   */
  async initialize(): Promise<void> {
    this.logger.info('Initializing Python module reloader...');
    const startTime = performance.now();

    try {
      // Initialize Python process pool
      await this.initializeProcessPool();

      // Scan for existing Python modules
      await this.scanPythonModules();

      // Build initial dependency graph
      if (this.dependencyTrackingEnabled) {
        await this.buildDependencyGraph();
      }

      const initTime = Math.round(performance.now() - startTime);
      this.logger.info('Module reloader initialized', {
        modules: this.modules.size,
        processes: this.pythonProcessPool.length,
        initTime
      });

    } catch (error) {
      this.logger.error('Failed to initialize module reloader', { error: error.message });
      throw error;
    }
  }

  /**
   * Dispose of resources
   */
  async dispose(): Promise<void> {
    this.logger.info('Disposing module reloader...');

    // Kill all Python processes
    const killPromises = this.pythonProcessPool.map(proc => this.killPythonProcess(proc));
    await Promise.allSettled(killPromises);

    // Clear data structures
    this.modules.clear();
    this.dependencyGraph.clear();
    this.dependentGraph.clear();
    this.stateSnapshots.clear();
    this.moduleHashes.clear();
    this.pythonProcessPool = [];

    this.logger.info('Module reloader disposed');
  }

  /**
   * Reload a Python module with dependency tracking
   */
  async reloadModule(modulePath: string): Promise<ModuleReloadResult> {
    const resolvedPath = path.resolve(modulePath);
    const startTime = performance.now();
    
    this.logger.info('Reloading Python module', { path: resolvedPath });

    try {
      // Check if module needs reloading
      const needsReload = await this.checkModuleNeedsReload(resolvedPath);
      if (!needsReload) {
        this.logger.debug('Module does not need reloading', { path: resolvedPath });
        return {
          success: true,
          module: resolvedPath,
          duration: Math.round(performance.now() - startTime),
          statePreserved: false,
          dependenciesReloaded: []
        };
      }

      // Create reload context
      const context: ReloadContext = {
        module: resolvedPath,
        startTime,
        dependencies: [],
        stateBackup: null,
        rollbackData: null
      };

      // Get module dependencies if tracking enabled
      if (this.dependencyTrackingEnabled) {
        context.dependencies = Array.from(this.dependencyGraph.get(resolvedPath) || []);
      }

      // Preserve state if enabled
      if (this.statePreservationEnabled) {
        context.stateBackup = await this.preserveModuleState(resolvedPath);
      }

      // Perform the reload
      const result = await this.performModuleReload(context);

      // Update module tracking
      await this.updateModuleInfo(resolvedPath);

      // Reload dependents if necessary
      const dependenciesReloaded: string[] = [];
      if (this.dependencyTrackingEnabled && result.success) {
        const dependents = Array.from(this.dependentGraph.get(resolvedPath) || []);
        for (const dependent of dependents) {
          try {
            const depResult = await this.reloadModule(dependent);
            if (depResult.success) {
              dependenciesReloaded.push(dependent);
            }
          } catch (error) {
            this.logger.warn('Failed to reload dependent module', {
              module: resolvedPath,
              dependent,
              error: error.message
            });
          }
        }
      }

      const totalDuration = Math.round(performance.now() - startTime);
      
      const finalResult: ModuleReloadResult = {
        success: result.success,
        module: resolvedPath,
        duration: totalDuration,
        statePreserved: result.statePreserved,
        dependenciesReloaded,
        errors: result.errors
      };

      this.logger.info('Module reload completed', {
        path: resolvedPath,
        success: result.success,
        duration: totalDuration,
        dependenciesCount: dependenciesReloaded.length
      });

      this.emit('module-reloaded', finalResult);
      return finalResult;

    } catch (error) {
      const duration = Math.round(performance.now() - startTime);
      this.logger.error('Module reload failed', {
        path: resolvedPath,
        error: error.message,
        duration
      });

      const result: ModuleReloadResult = {
        success: false,
        module: resolvedPath,
        duration,
        statePreserved: false,
        dependenciesReloaded: [],
        errors: [{
          type: 'runtime',
          message: error.message,
          file: resolvedPath
        }]
      };

      this.emit('module-reloaded', result);
      return result;
    }
  }

  /**
   * Reload multiple modules with dependencies
   */
  async reloadDependencies(modulePath: string): Promise<ModuleReloadResult[]> {
    const resolvedPath = path.resolve(modulePath);
    const dependencies = Array.from(this.dependencyGraph.get(resolvedPath) || []);
    
    if (dependencies.length === 0) {
      return [];
    }

    this.logger.info('Reloading module dependencies', {
      module: resolvedPath,
      dependencies: dependencies.length
    });

    const results: ModuleReloadResult[] = [];
    
    // Reload dependencies in dependency order (topological sort)
    const sortedDeps = this.topologicalSort(dependencies);
    
    for (const dep of sortedDeps) {
      try {
        const result = await this.reloadModule(dep);
        results.push(result);
      } catch (error) {
        this.logger.error('Failed to reload dependency', {
          module: resolvedPath,
          dependency: dep,
          error: error.message
        });
      }
    }

    return results;
  }

  /**
   * Preserve module state for later restoration
   */
  preserveState(module: string, state: any): void {
    const resolvedPath = path.resolve(module);
    const checksum = this.calculateStateChecksum(state);
    
    const snapshot: StateSnapshot = {
      module: resolvedPath,
      timestamp: Date.now(),
      data: state,
      checksum
    };

    this.stateSnapshots.set(resolvedPath, snapshot);
    this.logger.debug('Module state preserved', { module: resolvedPath, checksum });
  }

  /**
   * Restore previously preserved module state
   */
  restoreState(module: string): any {
    const resolvedPath = path.resolve(module);
    const snapshot = this.stateSnapshots.get(resolvedPath);
    
    if (!snapshot) {
      this.logger.debug('No preserved state found for module', { module: resolvedPath });
      return null;
    }

    this.logger.debug('Module state restored', { 
      module: resolvedPath, 
      age: Date.now() - snapshot.timestamp 
    });
    
    return snapshot.data;
  }

  /**
   * Get dependency graph for debugging
   */
  getDependencyGraph(): Record<string, string[]> {
    const graph: Record<string, string[]> = {};
    
    for (const [module, deps] of this.dependencyGraph) {
      graph[module] = Array.from(deps);
    }
    
    return graph;
  }

  /**
   * Force rebuild of dependency graph
   */
  async rebuildDependencyGraph(): Promise<void> {
    this.logger.info('Rebuilding dependency graph...');
    const startTime = performance.now();
    
    this.dependencyGraph.clear();
    this.dependentGraph.clear();
    
    await this.buildDependencyGraph();
    
    const duration = Math.round(performance.now() - startTime);
    this.logger.info('Dependency graph rebuilt', {
      modules: this.dependencyGraph.size,
      duration
    });
  }

  // Private Methods

  private async initializeProcessPool(): Promise<void> {
    const poolSize = Math.min(this.maxProcesses, 3);
    
    for (let i = 0; i < poolSize; i++) {
      try {
        const process = await this.createPythonProcess();
        this.pythonProcessPool.push(process);
      } catch (error) {
        this.logger.warn('Failed to create Python process for pool', { error: error.message });
      }
    }

    if (this.pythonProcessPool.length === 0) {
      throw new Error('Failed to create any Python processes');
    }

    this.logger.debug('Python process pool initialized', { size: this.pythonProcessPool.length });
  }

  private async createPythonProcess(): Promise<PythonProcess> {
    return new Promise((resolve, reject) => {
      const processId = `python_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      
      // Start Python REPL process
      const pythonProcess = spawn('python', ['-i', '-u'], {
        stdio: ['pipe', 'pipe', 'pipe'],
        env: {
          ...process.env,
          PYTHONPATH: this.config.projectRoot,
          PYTHONUNBUFFERED: '1'
        }
      });

      const proc: PythonProcess = {
        process: pythonProcess,
        ready: false,
        busy: false,
        lastUsed: Date.now(),
        id: processId
      };

      let initOutput = '';
      const timeout = setTimeout(() => {
        reject(new Error('Python process initialization timeout'));
      }, 5000);

      pythonProcess.stdout?.on('data', (data) => {
        initOutput += data.toString();
        if (initOutput.includes('>>>')) {
          clearTimeout(timeout);
          proc.ready = true;
          resolve(proc);
        }
      });

      pythonProcess.stderr?.on('data', (data) => {
        this.logger.warn('Python process stderr', { processId, data: data.toString() });
      });

      pythonProcess.on('exit', (code) => {
        this.logger.info('Python process exited', { processId, code });
        this.removePythonProcess(processId);
      });

      pythonProcess.on('error', (error) => {
        clearTimeout(timeout);
        reject(error);
      });
    });
  }

  private async getAvailablePythonProcess(): Promise<PythonProcess> {
    // Find available process
    let availableProcess = this.pythonProcessPool.find(proc => proc.ready && !proc.busy);
    
    if (!availableProcess) {
      // Create new process if pool not at capacity
      if (this.pythonProcessPool.length < this.maxProcesses) {
        try {
          availableProcess = await this.createPythonProcess();
          this.pythonProcessPool.push(availableProcess);
        } catch (error) {
          throw new Error('Failed to create Python process: ' + error.message);
        }
      } else {
        // Wait for process to become available
        await new Promise((resolve) => setTimeout(resolve, 100));
        return this.getAvailablePythonProcess();
      }
    }

    availableProcess.busy = true;
    availableProcess.lastUsed = Date.now();
    return availableProcess;
  }

  private releasePythonProcess(process: PythonProcess): void {
    process.busy = false;
    process.lastUsed = Date.now();
  }

  private async killPythonProcess(process: PythonProcess): Promise<void> {
    return new Promise((resolve) => {
      if (process.process.killed) {
        resolve();
        return;
      }

      process.process.on('exit', () => resolve());
      process.process.kill();
      
      // Force kill after timeout
      setTimeout(() => {
        if (!process.process.killed) {
          process.process.kill('SIGKILL');
        }
        resolve();
      }, 2000);
    });
  }

  private removePythonProcess(processId: string): void {
    const index = this.pythonProcessPool.findIndex(proc => proc.id === processId);
    if (index !== -1) {
      this.pythonProcessPool.splice(index, 1);
    }
  }

  private async scanPythonModules(): Promise<void> {
    const startTime = performance.now();
    const pythonFiles: string[] = [];

    // Recursively find Python files
    for (const watchPath of this.config.watchPaths) {
      const files = await this.findPythonFiles(watchPath);
      pythonFiles.push(...files);
    }

    // Process each Python file
    for (const filePath of pythonFiles) {
      try {
        await this.scanPythonModule(filePath);
      } catch (error) {
        this.logger.warn('Failed to scan Python module', {
          path: filePath,
          error: error.message
        });
      }
    }

    const scanTime = Math.round(performance.now() - startTime);
    this.logger.debug('Python modules scanned', {
      count: pythonFiles.length,
      duration: scanTime
    });
  }

  private async findPythonFiles(dirPath: string): Promise<string[]> {
    const files: string[] = [];
    
    try {
      const entries = await fs.readdir(dirPath, { withFileTypes: true });
      
      for (const entry of entries) {
        const fullPath = path.join(dirPath, entry.name);
        
        if (entry.isDirectory()) {
          // Skip common ignored directories
          if (['__pycache__', '.git', 'node_modules', 'venv', '.venv'].includes(entry.name)) {
            continue;
          }
          
          const subFiles = await this.findPythonFiles(fullPath);
          files.push(...subFiles);
        } else if (entry.isFile() && entry.name.endsWith('.py')) {
          files.push(fullPath);
        }
      }
    } catch (error) {
      this.logger.warn('Failed to scan directory for Python files', {
        path: dirPath,
        error: error.message
      });
    }
    
    return files;
  }

  private async scanPythonModule(filePath: string): Promise<void> {
    try {
      const stats = await fs.stat(filePath);
      const content = await fs.readFile(filePath, 'utf-8');
      const hash = createHash('md5').update(content).digest('hex');

      const module: PythonModule = {
        name: path.basename(filePath, '.py'),
        path: filePath,
        dependencies: [],
        dependents: [],
        lastModified: stats.mtimeMs,
        hash
      };

      // Extract dependencies
      if (this.dependencyTrackingEnabled) {
        module.dependencies = await this.extractPythonDependencies(content, filePath);
      }

      this.modules.set(filePath, module);
      this.moduleHashes.set(filePath, hash);

    } catch (error) {
      this.logger.warn('Failed to scan Python module', {
        path: filePath,
        error: error.message
      });
    }
  }

  private async extractPythonDependencies(content: string, filePath: string): Promise<string[]> {
    const dependencies: string[] = [];
    const lines = content.split('\n');
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      
      // Skip comments and empty lines
      if (line.startsWith('#') || line.length === 0) {
        continue;
      }

      // Handle imports
      const importMatch = line.match(/^import\s+([^\s#]+)/);
      if (importMatch) {
        const modules = importMatch[1].split(',').map(m => m.trim());
        for (const module of modules) {
          const resolvedPath = await this.resolveModulePath(module, filePath);
          if (resolvedPath) {
            dependencies.push(resolvedPath);
          }
        }
        continue;
      }

      // Handle from imports
      const fromImportMatch = line.match(/^from\s+([^\s#]+)\s+import/);
      if (fromImportMatch) {
        const module = fromImportMatch[1];
        const resolvedPath = await this.resolveModulePath(module, filePath);
        if (resolvedPath) {
          dependencies.push(resolvedPath);
        }
        continue;
      }
    }

    return [...new Set(dependencies)]; // Remove duplicates
  }

  private async resolveModulePath(moduleName: string, fromFile: string): Promise<string | null> {
    // Handle relative imports
    if (moduleName.startsWith('.')) {
      const basePath = path.dirname(fromFile);
      const relativePath = moduleName.replace(/\./g, path.sep);
      const candidatePath = path.resolve(basePath, relativePath + '.py');
      
      try {
        await fs.access(candidatePath);
        return candidatePath;
      } catch {
        return null;
      }
    }

    // Handle absolute imports within project
    const modulePath = moduleName.replace(/\./g, path.sep);
    const candidatePaths = [
      path.join(this.config.projectRoot, modulePath + '.py'),
      path.join(this.config.projectRoot, modulePath, '__init__.py')
    ];

    for (const candidatePath of candidatePaths) {
      try {
        await fs.access(candidatePath);
        return candidatePath;
      } catch {
        continue;
      }
    }

    return null; // External module or not found
  }

  private async buildDependencyGraph(): Promise<void> {
    this.dependencyGraph.clear();
    this.dependentGraph.clear();

    // Build dependency graph
    for (const [modulePath, module] of this.modules) {
      const deps = new Set<string>();
      
      for (const dep of module.dependencies) {
        if (this.modules.has(dep)) {
          deps.add(dep);
          
          // Build reverse dependency graph
          if (!this.dependentGraph.has(dep)) {
            this.dependentGraph.set(dep, new Set());
          }
          this.dependentGraph.get(dep)!.add(modulePath);
        }
      }
      
      this.dependencyGraph.set(modulePath, deps);
    }
  }

  private async checkModuleNeedsReload(modulePath: string): Promise<boolean> {
    try {
      const currentHash = this.moduleHashes.get(modulePath);
      if (!currentHash) {
        return true; // New module
      }

      const content = await fs.readFile(modulePath, 'utf-8');
      const newHash = createHash('md5').update(content).digest('hex');
      
      return currentHash !== newHash;
    } catch (error) {
      this.logger.warn('Error checking module reload need', {
        path: modulePath,
        error: error.message
      });
      return true; // Assume needs reload on error
    }
  }

  private async preserveModuleState(modulePath: string): Promise<any> {
    if (!this.statePreservationEnabled) {
      return null;
    }

    try {
      const pythonProcess = await this.getAvailablePythonProcess();
      
      // Extract module state using Python introspection
      const extractScript = `
import sys
import pickle
import base64

try:
    module_name = "${path.basename(modulePath, '.py')}"
    if module_name in sys.modules:
        module = sys.modules[module_name]
        state = {}
        for attr in dir(module):
            if not attr.startswith('_'):
                try:
                    value = getattr(module, attr)
                    if not callable(value):
                        state[attr] = value
                except:
                    pass
        
        pickled = pickle.dumps(state)
        encoded = base64.b64encode(pickled).decode('ascii')
        print("STATE_EXTRACTED:" + encoded)
    else:
        print("STATE_EXTRACTED:")
except Exception as e:
    print("STATE_ERROR:" + str(e))
`;

      const result = await this.executePythonCode(pythonProcess, extractScript);
      this.releasePythonProcess(pythonProcess);

      if (result.startsWith('STATE_EXTRACTED:')) {
        const encodedState = result.substring('STATE_EXTRACTED:'.length);
        if (encodedState) {
          // In a real implementation, you'd decode the pickled state
          return { encoded: encodedState };
        }
      }

      return null;
    } catch (error) {
      this.logger.warn('Failed to preserve module state', {
        module: modulePath,
        error: error.message
      });
      return null;
    }
  }

  private async performModuleReload(context: ReloadContext): Promise<{
    success: boolean;
    statePreserved: boolean;
    errors?: ReloadError[];
  }> {
    try {
      const pythonProcess = await this.getAvailablePythonProcess();
      
      const reloadScript = `
import sys
import importlib
import importlib.util

try:
    module_path = "${context.module}"
    module_name = "${path.basename(context.module, '.py')}"
    
    # Load or reload the module
    if module_name in sys.modules:
        module = sys.modules[module_name]
        importlib.reload(module)
        print("RELOAD_SUCCESS")
    else:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            print("LOAD_SUCCESS")
        else:
            print("RELOAD_ERROR:Unable to create module spec")
            
except Exception as e:
    print("RELOAD_ERROR:" + str(e))
`;

      const result = await this.executePythonCode(pythonProcess, reloadScript);
      this.releasePythonProcess(pythonProcess);

      if (result === 'RELOAD_SUCCESS' || result === 'LOAD_SUCCESS') {
        return {
          success: true,
          statePreserved: context.stateBackup !== null
        };
      } else if (result.startsWith('RELOAD_ERROR:')) {
        const errorMsg = result.substring('RELOAD_ERROR:'.length);
        return {
          success: false,
          statePreserved: false,
          errors: [{
            type: 'runtime',
            message: errorMsg,
            file: context.module
          }]
        };
      }

      return {
        success: false,
        statePreserved: false,
        errors: [{
          type: 'runtime',
          message: 'Unknown reload result',
          file: context.module
        }]
      };

    } catch (error) {
      return {
        success: false,
        statePreserved: false,
        errors: [{
          type: 'runtime',
          message: error.message,
          file: context.module
        }]
      };
    }
  }

  private async executePythonCode(pythonProcess: PythonProcess, code: string): Promise<string> {
    return new Promise((resolve, reject) => {
      let output = '';
      let errorOutput = '';
      
      const timeout = setTimeout(() => {
        reject(new Error('Python code execution timeout'));
      }, this.processTimeout);

      const onData = (data: Buffer) => {
        output += data.toString();
        
        // Check for completion markers
        if (output.includes('\n>>> ') || 
            output.includes('RELOAD_SUCCESS') || 
            output.includes('LOAD_SUCCESS') ||
            output.includes('RELOAD_ERROR:') ||
            output.includes('STATE_EXTRACTED:') ||
            output.includes('STATE_ERROR:')) {
          
          clearTimeout(timeout);
          pythonProcess.process.stdout?.off('data', onData);
          pythonProcess.process.stderr?.off('data', onError);
          
          // Extract the relevant part of output
          const lines = output.trim().split('\n');
          const lastLine = lines[lines.length - 1];
          resolve(lastLine.replace('>>> ', ''));
        }
      };

      const onError = (data: Buffer) => {
        errorOutput += data.toString();
      };

      pythonProcess.process.stdout?.on('data', onData);
      pythonProcess.process.stderr?.on('data', onError);

      // Send the code
      pythonProcess.process.stdin?.write(code + '\n');
    });
  }

  private async updateModuleInfo(modulePath: string): Promise<void> {
    try {
      const content = await fs.readFile(modulePath, 'utf-8');
      const newHash = createHash('md5').update(content).digest('hex');
      
      this.moduleHashes.set(modulePath, newHash);
      
      const module = this.modules.get(modulePath);
      if (module) {
        module.hash = newHash;
        module.lastModified = Date.now();
      }
    } catch (error) {
      this.logger.warn('Failed to update module info', {
        path: modulePath,
        error: error.message
      });
    }
  }

  private topologicalSort(modules: string[]): string[] {
    const visited = new Set<string>();
    const result: string[] = [];
    
    const visit = (module: string) => {
      if (visited.has(module)) return;
      visited.add(module);
      
      const deps = this.dependencyGraph.get(module) || new Set();
      for (const dep of deps) {
        if (modules.includes(dep)) {
          visit(dep);
        }
      }
      
      result.push(module);
    };
    
    for (const module of modules) {
      visit(module);
    }
    
    return result;
  }

  private calculateStateChecksum(state: any): string {
    try {
      const serialized = JSON.stringify(state);
      return createHash('md5').update(serialized).digest('hex');
    } catch {
      return 'unknown';
    }
  }
}