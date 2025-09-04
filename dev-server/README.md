# RevitPy Development Server

A high-performance hot-reload development server for RevitPy with instant feedback during development.

## 🚀 Features

### Performance Targets
- **<500ms** Python module reload time
- **<200ms** UI component hot-reload time
- **<100ms** file change detection
- **10+** concurrent development sessions

### Core Capabilities
- **File Watching**: Intelligent file monitoring with debouncing and filtering
- **WebSocket Communication**: Real-time communication with Revit, VS Code, and browsers
- **Hot Module Replacement**: Update running code without losing application state
- **UI Hot-Reload**: Instant updates for WebView2-based panels with React/Vue support
- **Error Recovery**: Graceful handling of syntax errors with automatic rollback
- **Performance Monitoring**: Real-time metrics and optimization recommendations

### Integration Points
- **RevitPy Host Application**: Direct code execution in Revit
- **VS Code Extension**: Editor integration with problem matching
- **CLI Tools**: Command-line development workflow
- **WebView2 Panels**: Hot-reload for embedded web UIs
- **Package System**: Automatic dependency updates

## 📦 Installation

```bash
npm install @revitpy/dev-server
```

Or install globally for CLI usage:

```bash
npm install -g @revitpy/dev-server
```

## 🔧 Usage

### CLI Usage

Start the development server:

```bash
revitpy-dev-server start --port 3000 --watch src --root ./my-project
```

Check server status:

```bash
revitpy-dev-server status
```

Generate configuration file:

```bash
revitpy-dev-server config --init
```

Run performance benchmarks:

```bash
revitpy-dev-server benchmark
```

### Programmatic Usage

```typescript
import { DevServer } from '@revitpy/dev-server';

const config = {
  host: 'localhost',
  port: 3000,
  projectRoot: '/path/to/project',
  watchPaths: ['src', 'components'],
  hotReload: {
    enabled: true,
    pythonModules: true,
    uiComponents: true
  },
  revit: {
    enabled: true,
    autoConnect: true
  }
};

const server = new DevServer(config);

// Start server
await server.start();

// Listen for events
server.on('client-connected', (client) => {
  console.log(`Client connected: ${client.type}`);
});

server.on('module-reloaded', (result) => {
  console.log(`Module reloaded: ${result.module} in ${result.duration}ms`);
});

// Stop server
await server.stop();
```

## ⚙️ Configuration

### Default Configuration

```json
{
  "host": "localhost",
  "port": 3000,
  "websocketPort": 3001,
  "projectRoot": "./",
  "watchPaths": ["src"],
  "buildOutputPath": "dist",
  "debounceMs": 300,
  "maxReloadTime": 5000,
  "hotReload": {
    "enabled": true,
    "pythonModules": true,
    "uiComponents": true,
    "preserveState": true
  },
  "moduleReloader": {
    "enabled": true,
    "safeReload": true,
    "dependencyTracking": true,
    "statePreservation": true,
    "rollbackOnError": true
  },
  "uiReload": {
    "enabled": true,
    "webview2Integration": true,
    "reactRefresh": true,
    "vueHmr": true,
    "cssHotReload": true
  },
  "errorRecovery": {
    "enabled": true,
    "automaticRecovery": true,
    "maxRetries": 3
  },
  "performance": {
    "monitoring": true,
    "metrics": true,
    "optimization": true
  },
  "revit": {
    "enabled": true,
    "autoConnect": true,
    "port": 5678
  },
  "vscode": {
    "enabled": true,
    "debugAdapter": true
  },
  "webview": {
    "enabled": true,
    "devTools": true
  }
}
```

### Environment Variables

- `LOG_LEVEL`: Set logging level (debug, info, warn, error)
- `NODE_ENV`: Environment mode (development, production)
- `REVITPY_DEV_PORT`: Override default port
- `REVITPY_DEV_HOST`: Override default host

## 🏗️ Architecture

### Core Services

```
┌─────────────────┐
│   DevServer     │  ← Main orchestrator
├─────────────────┤
│ FileWatcher     │  ← High-perf file monitoring
│ WebSocket Mgr   │  ← Multi-client communication
│ Module Reloader │  ← Python hot-reload
│ UI Reloader     │  ← WebView2 HMR
│ Build System    │  ← Asset processing
│ Error Recovery  │  ← Graceful error handling
│ Performance     │  ← Metrics & optimization
└─────────────────┘
```

### Communication Flow

```
┌─────────┐   WebSocket   ┌─────────────┐   Python   ┌───────┐
│ VS Code │◄─────────────►│ Dev Server  │◄───────────►│ Revit │
└─────────┘               └─────────────┘             └───────┘
                               │
                          WebSocket
                               │
                          ┌─────────┐
                          │WebView2 │
                          │ Panels  │
                          └─────────┘
```

### File Change Pipeline

```
File Change → Debounce → Filter → Analyze → Strategy
     │                                        │
     └─ Python? → Module Reloader ───────────┘
     │                                        │
     └─ UI? → Component HMR ─────────────────┘
     │                                        │
     └─ Asset? → Build System ───────────────┘
     │                                        │
     └─ Error? → Recovery System ────────────┘
```

## 🔌 Integrations

### Revit Host Application

The development server communicates with Revit through:

- **Python Bridge**: Direct execution of Python code in Revit context
- **WebSocket Connection**: Real-time command/response communication
- **Module Reloader**: Safe reloading of Python modules with state preservation

### VS Code Extension

Integration features:

- **Problem Matcher**: Automatic error detection and highlighting
- **Debug Adapter**: Debugging support for Python code
- **File Operations**: Synchronized file operations between editor and server

### WebView2 Panels

UI development features:

- **Hot Module Replacement**: React/Vue component updates without page refresh
- **CSS Hot Reload**: Instant style updates
- **State Preservation**: Maintain component state during updates
- **Error Boundaries**: Graceful error handling in UI components

## 📊 Performance

### Benchmarks

Target performance metrics:

```
File Change Detection: < 100ms
Python Module Reload:  < 500ms
UI Component Update:   < 200ms
WebSocket Latency:     < 50ms
Memory Usage:          < 200MB
CPU Usage:             < 10%
```

### Optimization Features

- **Intelligent Caching**: Multi-layer caching for build artifacts
- **Incremental Builds**: Only rebuild changed components
- **Parallel Processing**: Concurrent file processing
- **Memory Management**: Automatic cleanup and optimization
- **Network Optimization**: Efficient WebSocket message batching

## 🛠️ Development

### Building from Source

```bash
git clone https://github.com/revitpy/dev-server.git
cd dev-server
npm install
npm run build
```

### Running Tests

```bash
npm test
npm run test:watch
npm run test:performance
```

### Performance Profiling

```bash
npm run perf
clinic doctor -- npm start
```

## 🐛 Troubleshooting

### Common Issues

**Server won't start:**
- Check port availability
- Verify project root path exists
- Check Node.js version (>= 18.0.0)

**Hot reload not working:**
- Verify WebSocket connection
- Check file patterns in configuration
- Ensure files are within watched paths

**Python modules not reloading:**
- Check Python interpreter path
- Verify module dependencies
- Check for syntax errors in Python files

**Performance issues:**
- Enable performance monitoring
- Check memory usage
- Verify file patterns aren't too broad

### Debug Mode

Enable debug logging:

```bash
LOG_LEVEL=debug revitpy-dev-server start
```

### Health Check

Monitor server health:

```bash
curl http://localhost:3000/health
```

## 📝 API Reference

### REST API

- `GET /health` - Server health status
- `POST /api/build` - Trigger manual build
- `POST /api/reload/module` - Reload specific Python module
- `POST /api/reload/ui` - Reload UI component
- `GET /api/metrics` - Performance metrics
- `GET /api/clients` - Connected clients

### WebSocket Messages

**Client → Server:**
- `ping` - Heartbeat
- `subscribe` - Subscribe to channel
- `build` - Request build
- `revit-command` - Send command to Revit

**Server → Client:**
- `pong` - Heartbeat response
- `file-changed` - File change notification
- `build-complete` - Build completion
- `module-reload` - Python module reloaded
- `ui-reload` - UI component reloaded
- `error-recovery` - Error recovery action

## 📄 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📞 Support

- GitHub Issues: [Report bugs or request features](https://github.com/revitpy/dev-server/issues)
- Documentation: [Full documentation](https://revitpy.dev/docs/dev-server)
- Community: [Discord server](https://discord.gg/revitpy)