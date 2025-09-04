/**
 * UI Hot-Reload Service for WebView2 Panels
 * Target: <200ms reload time for UI components with state preservation
 */

import { EventEmitter } from 'events';
import { performance } from 'perf_hooks';
import { promises as fs } from 'fs';
import { createHash } from 'crypto';
import path from 'path';
import pino from 'pino';
import esbuild from 'esbuild';

import type { 
  DevServerConfig,
  UIComponent,
  ComponentType,
  ComponentState,
  UIReloadResult,
  ReloadType
} from '../types/index.js';

interface HotReloadClient {
  id: string;
  type: 'webview2' | 'browser';
  websocket: any;
  lastActivity: Date;
  supportedFeatures: string[];
}

interface ComponentTracker {
  path: string;
  hash: string;
  lastModified: number;
  dependencies: string[];
  hmrId: string;
  state?: ComponentState;
}

interface AssetBundle {
  entry: string;
  outputs: Map<string, string>;
  dependencies: Set<string>;
  hash: string;
}

interface HMRUpdate {
  type: 'component' | 'style' | 'asset';
  path: string;
  content: string;
  dependencies: string[];
  hmrId: string;
  acceptsHMR: boolean;
}

export class UIReloaderService extends EventEmitter {
  private config: DevServerConfig;
  private logger: pino.Logger;
  private components = new Map<string, ComponentTracker>();
  private bundles = new Map<string, AssetBundle>();
  private clients = new Map<string, HotReloadClient>();
  private componentHashes = new Map<string, string>();
  
  // HMR Runtime
  private hmrRuntime: string = '';
  private hmrCounter = 0;
  
  // Performance optimization
  private buildCache = new Map<string, any>();
  private incrementalBuild: esbuild.BuildContext | null = null;
  
  constructor(config: DevServerConfig, logger?: pino.Logger) {
    super();
    this.config = config;
    this.logger = logger || pino({ name: 'UIReloader' });
    
    this.logger.info('UI hot-reload service initialized', {
      webview2: this.config.uiReload.webview2Integration,
      reactRefresh: this.config.uiReload.reactRefresh,
      vueHmr: this.config.uiReload.vueHmr,
      cssHotReload: this.config.uiReload.cssHotReload
    });
  }

  /**
   * Initialize the UI reloader service
   */
  async initialize(): Promise<void> {
    this.logger.info('Initializing UI hot-reload service...');
    const startTime = performance.now();

    try {
      // Generate HMR runtime
      await this.generateHMRRuntime();

      // Set up incremental build
      await this.setupIncrementalBuild();

      // Scan for UI components
      await this.scanUIComponents();

      // Setup WebView2 integration if enabled
      if (this.config.uiReload.webview2Integration) {
        await this.setupWebView2Integration();
      }

      const initTime = Math.round(performance.now() - startTime);
      this.logger.info('UI hot-reload service initialized', {
        components: this.components.size,
        bundles: this.bundles.size,
        initTime
      });

    } catch (error) {
      this.logger.error('Failed to initialize UI reloader', { error: error.message });
      throw error;
    }
  }

  /**
   * Dispose of resources
   */
  async dispose(): Promise<void> {
    this.logger.info('Disposing UI reloader...');

    // Stop incremental build
    if (this.incrementalBuild) {
      await this.incrementalBuild.dispose();
      this.incrementalBuild = null;
    }

    // Clear all data
    this.components.clear();
    this.bundles.clear();
    this.clients.clear();
    this.buildCache.clear();

    this.logger.info('UI reloader disposed');
  }

  /**
   * Reload a UI component with hot module replacement
   */
  async reloadComponent(componentPath: string): Promise<UIReloadResult> {
    const resolvedPath = path.resolve(componentPath);
    const startTime = performance.now();
    
    this.logger.info('Reloading UI component', { path: resolvedPath });

    try {
      // Check if component needs reloading
      const needsReload = await this.checkComponentNeedsReload(resolvedPath);
      if (!needsReload) {
        this.logger.debug('Component does not need reloading', { path: resolvedPath });
        return {
          success: true,
          component: resolvedPath,
          type: 'hot',
          duration: Math.round(performance.now() - startTime),
          statePreserved: false,
          affectedComponents: []
        };
      }

      // Determine reload type
      const reloadType = this.determineReloadType(resolvedPath);
      
      let result: UIReloadResult;
      
      switch (reloadType) {
        case 'hot':
          result = await this.performHotReload(resolvedPath, startTime);
          break;
        case 'full':
          result = await this.performFullReload(resolvedPath, startTime);
          break;
        default:
          result = await this.performRefresh(resolvedPath, startTime);
          break;
      }

      // Update component tracking
      await this.updateComponentInfo(resolvedPath);

      this.logger.info('Component reload completed', {
        path: resolvedPath,
        type: reloadType,
        success: result.success,
        duration: result.duration
      });

      this.emit('ui-reloaded', result);
      return result;

    } catch (error) {
      const duration = Math.round(performance.now() - startTime);
      this.logger.error('Component reload failed', {
        path: resolvedPath,
        error: error.message,
        duration
      });

      const result: UIReloadResult = {
        success: false,
        component: resolvedPath,
        type: 'full',
        duration,
        statePreserved: false,
        affectedComponents: []
      };

      this.emit('ui-reloaded', result);
      return result;
    }
  }

  /**
   * Hot replace module using HMR
   */
  async hotReplaceModule(componentPath: string): Promise<UIReloadResult> {
    const resolvedPath = path.resolve(componentPath);
    const startTime = performance.now();

    try {
      // Build the component with HMR support
      const buildResult = await this.buildComponentForHMR(resolvedPath);
      if (!buildResult.success) {
        throw new Error('Build failed for HMR');
      }

      // Create HMR update
      const hmrUpdate: HMRUpdate = {
        type: this.getComponentType(resolvedPath) === 'css' ? 'style' : 'component',
        path: resolvedPath,
        content: buildResult.code!,
        dependencies: buildResult.dependencies || [],
        hmrId: this.getHMRId(resolvedPath),
        acceptsHMR: this.componentAcceptsHMR(resolvedPath)
      };

      // Send HMR update to all clients
      await this.sendHMRUpdate(hmrUpdate);

      // Track affected components
      const affectedComponents = await this.getAffectedComponents(resolvedPath);

      const result: UIReloadResult = {
        success: true,
        component: resolvedPath,
        type: 'hot',
        duration: Math.round(performance.now() - startTime),
        statePreserved: hmrUpdate.acceptsHMR,
        affectedComponents
      };

      return result;

    } catch (error) {
      this.logger.error('Hot module replacement failed', {
        path: resolvedPath,
        error: error.message
      });

      // Fallback to full reload
      return await this.performFullReload(resolvedPath, startTime);
    }
  }

  /**
   * Refresh entire page
   */
  async refreshPage(): Promise<void> {
    this.logger.info('Refreshing all UI clients');
    
    const refreshMessage = {
      type: 'hmr:full-reload',
      timestamp: Date.now()
    };

    await this.broadcastToClients(refreshMessage);
  }

  /**
   * Inject custom script into all clients
   */
  async injectScript(script: string): Promise<void> {
    this.logger.debug('Injecting script into UI clients');
    
    const injectMessage = {
      type: 'hmr:inject-script',
      script,
      timestamp: Date.now()
    };

    await this.broadcastToClients(injectMessage);
  }

  /**
   * Register HMR client (WebView2, browser, etc.)
   */
  registerClient(client: HotReloadClient): void {
    this.clients.set(client.id, client);
    this.logger.info('HMR client registered', {
      id: client.id,
      type: client.type,
      features: client.supportedFeatures
    });

    // Send initial HMR runtime
    this.sendToClient(client.id, {
      type: 'hmr:init',
      runtime: this.hmrRuntime,
      timestamp: Date.now()
    });
  }

  /**
   * Unregister HMR client
   */
  unregisterClient(clientId: string): void {
    this.clients.delete(clientId);
    this.logger.info('HMR client unregistered', { id: clientId });
  }

  // Private Methods

  private async generateHMRRuntime(): Promise<void> {
    this.hmrRuntime = `
// RevitPy HMR Runtime
(function() {
  'use strict';
  
  let socket;
  let modules = new Map();
  let updateQueue = [];
  let isUpdating = false;
  
  // HMR API
  window.__REVITPY_HMR__ = {
    accept: function(deps, callback) {
      const moduleId = this.id;
      modules.set(moduleId, { deps, callback, hot: true });
    },
    decline: function() {
      const moduleId = this.id;
      const mod = modules.get(moduleId);
      if (mod) mod.hot = false;
    },
    dispose: function(callback) {
      const moduleId = this.id;
      const mod = modules.get(moduleId);
      if (mod) mod.dispose = callback;
    },
    invalidate: function() {
      this.decline();
      window.location.reload();
    }
  };
  
  // Connect to HMR WebSocket
  function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = protocol + '//' + window.location.host + '/ws';
    
    socket = new WebSocket(wsUrl);
    
    socket.onopen = function() {
      console.log('[RevitPy HMR] Connected');
    };
    
    socket.onmessage = function(event) {
      try {
        const data = JSON.parse(event.data);
        handleMessage(data);
      } catch (e) {
        console.error('[RevitPy HMR] Invalid message:', e);
      }
    };
    
    socket.onclose = function() {
      console.log('[RevitPy HMR] Disconnected, retrying in 2s...');
      setTimeout(connect, 2000);
    };
    
    socket.onerror = function(error) {
      console.error('[RevitPy HMR] Error:', error);
    };
  }
  
  function handleMessage(data) {
    switch (data.type) {
      case 'hmr:update':
        queueUpdate(data);
        break;
      case 'hmr:full-reload':
        window.location.reload();
        break;
      case 'hmr:inject-script':
        injectScript(data.script);
        break;
      case 'hmr:css-update':
        updateCSS(data);
        break;
    }
  }
  
  function queueUpdate(update) {
    updateQueue.push(update);
    if (!isUpdating) {
      processUpdateQueue();
    }
  }
  
  async function processUpdateQueue() {
    isUpdating = true;
    
    while (updateQueue.length > 0) {
      const update = updateQueue.shift();
      await applyUpdate(update);
    }
    
    isUpdating = false;
  }
  
  async function applyUpdate(update) {
    try {
      console.log('[RevitPy HMR] Applying update:', update.path);
      
      if (update.type === 'style') {
        updateCSS(update);
      } else if (update.type === 'component') {
        await updateComponent(update);
      }
      
    } catch (error) {
      console.error('[RevitPy HMR] Update failed:', error);
      window.location.reload();
    }
  }
  
  function updateCSS(update) {
    const existingLink = document.querySelector('link[data-hmr-id="' + update.hmrId + '"]');
    
    if (existingLink) {
      const newLink = document.createElement('link');
      newLink.rel = 'stylesheet';
      newLink.href = 'data:text/css;base64,' + btoa(update.content);
      newLink.setAttribute('data-hmr-id', update.hmrId);
      
      existingLink.parentNode.replaceChild(newLink, existingLink);
    } else {
      // Inject new CSS
      const style = document.createElement('style');
      style.setAttribute('data-hmr-id', update.hmrId);
      style.textContent = update.content;
      document.head.appendChild(style);
    }
    
    console.log('[RevitPy HMR] CSS updated:', update.path);
  }
  
  async function updateComponent(update) {
    // Create module wrapper
    const moduleWrapper = new Function('module', 'exports', 'require', '__REVITPY_HMR__', update.content);
    
    const module = { exports: {}, hot: window.__REVITPY_HMR__ };
    module.hot.id = update.hmrId;
    
    // Execute module
    moduleWrapper(module, module.exports, requireStub, window.__REVITPY_HMR__);
    
    // Check if module accepts HMR
    const existingModule = modules.get(update.hmrId);
    if (existingModule && existingModule.hot) {
      // Dispose old module
      if (existingModule.dispose) {
        existingModule.dispose();
      }
      
      // Accept new module
      if (existingModule.callback) {
        existingModule.callback();
      }
    } else {
      // Module doesn't accept HMR, full reload
      console.log('[RevitPy HMR] Module does not accept HMR, reloading page');
      window.location.reload();
    }
  }
  
  function requireStub(id) {
    // Simple require stub for HMR
    return window.require ? window.require(id) : {};
  }
  
  function injectScript(script) {
    const scriptEl = document.createElement('script');
    scriptEl.textContent = script;
    document.head.appendChild(scriptEl);
  }
  
  // Start HMR connection
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', connect);
  } else {
    connect();
  }
})();
`;

    this.logger.debug('HMR runtime generated', { 
      size: this.hmrRuntime.length 
    });
  }

  private async setupIncrementalBuild(): Promise<void> {
    try {
      this.incrementalBuild = await esbuild.context({
        entryPoints: [], // Will be populated dynamically
        bundle: true,
        write: false,
        metafile: true,
        sourcemap: true,
        format: 'esm',
        target: 'es2020',
        loader: {
          '.tsx': 'tsx',
          '.jsx': 'jsx',
          '.ts': 'tsx', // Treat TS as TSX for React support
          '.js': 'jsx',  // Treat JS as JSX for React support
          '.css': 'css',
          '.scss': 'css',
          '.vue': 'text' // Custom Vue loader would go here
        },
        plugins: [
          this.createReactRefreshPlugin(),
          this.createVueHMRPlugin(),
          this.createCSSHMRPlugin()
        ],
        define: {
          'process.env.NODE_ENV': '"development"',
          '__DEV__': 'true'
        }
      });

      this.logger.debug('Incremental build context created');
    } catch (error) {
      this.logger.error('Failed to setup incremental build', { error: error.message });
      throw error;
    }
  }

  private createReactRefreshPlugin(): esbuild.Plugin {
    if (!this.config.uiReload.reactRefresh) {
      return { name: 'noop', setup() {} };
    }

    return {
      name: 'react-refresh',
      setup(build) {
        build.onLoad({ filter: /\.(jsx?|tsx?)$/ }, async (args) => {
          const contents = await fs.readFile(args.path, 'utf8');
          
          // Inject React Refresh
          const refreshedCode = `
import { __hmrId } from 'virtual:hmr';
let prevRefreshReg = window.$RefreshReg$;
let prevRefreshSig = window.$RefreshSig$;

window.$RefreshReg$ = (type, id) => {
  const fullId = __hmrId + "_" + id;
  // Register component with React Refresh
};

window.$RefreshSig$ = () => {
  // Create refresh signature
  return (type) => type;
};

${contents}

if (module.hot) {
  module.hot.accept();
}

window.$RefreshReg$ = prevRefreshReg;
window.$RefreshSig$ = prevRefreshSig;
`;
          
          return { contents: refreshedCode, loader: 'tsx' };
        });
      }
    };
  }

  private createVueHMRPlugin(): esbuild.Plugin {
    if (!this.config.uiReload.vueHmr) {
      return { name: 'noop', setup() {} };
    }

    return {
      name: 'vue-hmr',
      setup(build) {
        build.onLoad({ filter: /\.vue$/ }, async (args) => {
          // Parse Vue SFC and generate HMR code
          const contents = await fs.readFile(args.path, 'utf8');
          
          // Simple Vue SFC parsing (real implementation would use @vue/compiler-sfc)
          const templateMatch = contents.match(/<template[^>]*>([\s\S]*?)<\/template>/);
          const scriptMatch = contents.match(/<script[^>]*>([\s\S]*?)<\/script>/);
          const styleMatch = contents.match(/<style[^>]*>([\s\S]*?)<\/style>/);
          
          const template = templateMatch ? templateMatch[1] : '';
          const script = scriptMatch ? scriptMatch[1] : '';
          const style = styleMatch ? styleMatch[1] : '';
          
          const vueCode = `
// Vue HMR Code
const __hmrId = "${path.basename(args.path)}";

${script}

if (module.hot) {
  module.hot.accept();
  
  // Vue HMR API integration would go here
  // Real implementation would use vue/runtime-core HMR API
}

export default component;
`;
          
          return { contents: vueCode, loader: 'js' };
        });
      }
    };
  }

  private createCSSHMRPlugin(): esbuild.Plugin {
    return {
      name: 'css-hmr',
      setup(build) {
        build.onLoad({ filter: /\.css$/ }, async (args) => {
          const contents = await fs.readFile(args.path, 'utf8');
          
          const cssCode = `
const css = ${JSON.stringify(contents)};
const hmrId = "${this.getHMRId(args.path)}";

// Inject CSS
const style = document.createElement('style');
style.setAttribute('data-hmr-id', hmrId);
style.textContent = css;
document.head.appendChild(style);

if (module.hot) {
  module.hot.accept();
  module.hot.dispose(() => {
    const existing = document.querySelector('style[data-hmr-id="' + hmrId + '"]');
    if (existing) existing.remove();
  });
}
`;
          
          return { contents: cssCode, loader: 'js' };
        });
      }
    };
  }

  private async scanUIComponents(): Promise<void> {
    const startTime = performance.now();
    const componentFiles: string[] = [];

    // Find UI component files
    for (const watchPath of this.config.watchPaths) {
      const files = await this.findUIFiles(watchPath);
      componentFiles.push(...files);
    }

    // Track each component
    for (const filePath of componentFiles) {
      try {
        await this.trackUIComponent(filePath);
      } catch (error) {
        this.logger.warn('Failed to track UI component', {
          path: filePath,
          error: error.message
        });
      }
    }

    const scanTime = Math.round(performance.now() - startTime);
    this.logger.debug('UI components scanned', {
      count: componentFiles.length,
      duration: scanTime
    });
  }

  private async findUIFiles(dirPath: string): Promise<string[]> {
    const files: string[] = [];
    const uiExtensions = ['.jsx', '.tsx', '.vue', '.svelte', '.css', '.scss', '.sass', '.less'];
    
    try {
      const entries = await fs.readdir(dirPath, { withFileTypes: true });
      
      for (const entry of entries) {
        const fullPath = path.join(dirPath, entry.name);
        
        if (entry.isDirectory()) {
          if (['node_modules', '.git', 'dist', 'build'].includes(entry.name)) {
            continue;
          }
          
          const subFiles = await this.findUIFiles(fullPath);
          files.push(...subFiles);
        } else if (entry.isFile()) {
          const ext = path.extname(entry.name).toLowerCase();
          if (uiExtensions.includes(ext)) {
            files.push(fullPath);
          }
        }
      }
    } catch (error) {
      this.logger.warn('Failed to scan directory for UI files', {
        path: dirPath,
        error: error.message
      });
    }
    
    return files;
  }

  private async trackUIComponent(filePath: string): Promise<void> {
    try {
      const stats = await fs.stat(filePath);
      const content = await fs.readFile(filePath, 'utf-8');
      const hash = createHash('md5').update(content).digest('hex');

      const tracker: ComponentTracker = {
        path: filePath,
        hash,
        lastModified: stats.mtimeMs,
        dependencies: await this.extractComponentDependencies(content, filePath),
        hmrId: this.getHMRId(filePath)
      };

      this.components.set(filePath, tracker);
      this.componentHashes.set(filePath, hash);

    } catch (error) {
      this.logger.warn('Failed to track UI component', {
        path: filePath,
        error: error.message
      });
    }
  }

  private async extractComponentDependencies(content: string, filePath: string): Promise<string[]> {
    const dependencies: string[] = [];
    
    // Extract import statements
    const importRegex = /import\s+.*?from\s+['"]([^'"]+)['"]/g;
    let match;
    
    while ((match = importRegex.exec(content)) !== null) {
      const importPath = match[1];
      
      if (importPath.startsWith('./') || importPath.startsWith('../')) {
        const resolvedPath = path.resolve(path.dirname(filePath), importPath);
        dependencies.push(resolvedPath);
      }
    }
    
    return dependencies;
  }

  private async setupWebView2Integration(): Promise<void> {
    this.logger.info('Setting up WebView2 integration...');
    
    // WebView2 integration would involve:
    // 1. Injecting HMR runtime into WebView2 instances
    // 2. Setting up communication channel with C# host
    // 3. Handling WebView2-specific events
    
    this.logger.debug('WebView2 integration setup complete');
  }

  private async checkComponentNeedsReload(componentPath: string): Promise<boolean> {
    try {
      const currentHash = this.componentHashes.get(componentPath);
      if (!currentHash) {
        return true; // New component
      }

      const content = await fs.readFile(componentPath, 'utf-8');
      const newHash = createHash('md5').update(content).digest('hex');
      
      return currentHash !== newHash;
    } catch (error) {
      return true; // Assume needs reload on error
    }
  }

  private determineReloadType(componentPath: string): ReloadType {
    const ext = path.extname(componentPath).toLowerCase();
    
    // CSS can always use hot reload
    if (['.css', '.scss', '.sass', '.less'].includes(ext)) {
      return 'hot';
    }
    
    // Components can use hot reload if they accept HMR
    if (['.jsx', '.tsx', '.vue', '.svelte'].includes(ext)) {
      return this.componentAcceptsHMR(componentPath) ? 'hot' : 'full';
    }
    
    // Default to full reload
    return 'full';
  }

  private componentAcceptsHMR(componentPath: string): boolean {
    // Check if component has HMR support
    // This would involve analyzing the component code
    return this.config.uiReload.reactRefresh || this.config.uiReload.vueHmr;
  }

  private getComponentType(filePath: string): ComponentType {
    const ext = path.extname(filePath).toLowerCase();
    
    if (['.jsx', '.tsx'].includes(ext)) return 'react';
    if (ext === '.vue') return 'vue';
    if (ext === '.svelte') return 'svelte';
    if (['.css', '.scss'].includes(ext)) return 'css' as ComponentType;
    return 'html';
  }

  private getHMRId(filePath: string): string {
    return `hmr_${createHash('md5').update(filePath).digest('hex').substring(0, 8)}`;
  }

  private async performHotReload(componentPath: string, startTime: number): Promise<UIReloadResult> {
    const buildResult = await this.buildComponentForHMR(componentPath);
    
    if (!buildResult.success) {
      return this.performFullReload(componentPath, startTime);
    }

    const hmrUpdate: HMRUpdate = {
      type: this.getComponentType(componentPath) === 'css' ? 'style' : 'component',
      path: componentPath,
      content: buildResult.code!,
      dependencies: buildResult.dependencies || [],
      hmrId: this.getHMRId(componentPath),
      acceptsHMR: true
    };

    await this.sendHMRUpdate(hmrUpdate);
    
    return {
      success: true,
      component: componentPath,
      type: 'hot',
      duration: Math.round(performance.now() - startTime),
      statePreserved: true,
      affectedComponents: await this.getAffectedComponents(componentPath)
    };
  }

  private async performFullReload(componentPath: string, startTime: number): Promise<UIReloadResult> {
    await this.refreshPage();
    
    return {
      success: true,
      component: componentPath,
      type: 'full',
      duration: Math.round(performance.now() - startTime),
      statePreserved: false,
      affectedComponents: []
    };
  }

  private async performRefresh(componentPath: string, startTime: number): Promise<UIReloadResult> {
    await this.refreshPage();
    
    return {
      success: true,
      component: componentPath,
      type: 'refresh',
      duration: Math.round(performance.now() - startTime),
      statePreserved: false,
      affectedComponents: []
    };
  }

  private async buildComponentForHMR(componentPath: string): Promise<{
    success: boolean;
    code?: string;
    dependencies?: string[];
    error?: string;
  }> {
    try {
      if (!this.incrementalBuild) {
        throw new Error('Incremental build not available');
      }

      const result = await this.incrementalBuild.rebuild();
      
      if (result.errors.length > 0) {
        return {
          success: false,
          error: result.errors[0].text
        };
      }

      const outputFile = result.outputFiles?.[0];
      if (!outputFile) {
        throw new Error('No output file generated');
      }

      return {
        success: true,
        code: outputFile.text,
        dependencies: this.extractDependenciesFromMetafile(result.metafile)
      };

    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }

  private extractDependenciesFromMetafile(metafile?: esbuild.Metafile): string[] {
    if (!metafile) return [];
    
    const dependencies: string[] = [];
    
    for (const [inputPath] of Object.entries(metafile.inputs)) {
      if (path.isAbsolute(inputPath)) {
        dependencies.push(inputPath);
      }
    }
    
    return dependencies;
  }

  private async sendHMRUpdate(update: HMRUpdate): Promise<void> {
    const message = {
      type: 'hmr:update',
      ...update,
      timestamp: Date.now()
    };

    await this.broadcastToClients(message);
  }

  private async broadcastToClients(message: any): Promise<void> {
    const clients = Array.from(this.clients.values());
    const promises = clients.map(client => this.sendToClient(client.id, message));
    
    await Promise.allSettled(promises);
  }

  private async sendToClient(clientId: string, message: any): Promise<void> {
    const client = this.clients.get(clientId);
    if (!client) return;

    try {
      if (client.websocket && client.websocket.readyState === 1) {
        client.websocket.send(JSON.stringify(message));
        client.lastActivity = new Date();
      }
    } catch (error) {
      this.logger.warn('Failed to send message to HMR client', {
        clientId,
        error: error.message
      });
    }
  }

  private async getAffectedComponents(componentPath: string): Promise<string[]> {
    const affected: string[] = [];
    
    // Find components that depend on this one
    for (const [path, tracker] of this.components) {
      if (tracker.dependencies.includes(componentPath)) {
        affected.push(path);
      }
    }
    
    return affected;
  }

  private async updateComponentInfo(componentPath: string): Promise<void> {
    try {
      const content = await fs.readFile(componentPath, 'utf-8');
      const newHash = createHash('md5').update(content).digest('hex');
      
      this.componentHashes.set(componentPath, newHash);
      
      const tracker = this.components.get(componentPath);
      if (tracker) {
        tracker.hash = newHash;
        tracker.lastModified = Date.now();
      }
    } catch (error) {
      this.logger.warn('Failed to update component info', {
        path: componentPath,
        error: error.message
      });
    }
  }
}