# RevitPy Developer Tools & UI Components

A comprehensive suite of developer tools and UI components for RevitPy, providing a modern development experience for Revit automation.

## Overview

This monorepo contains all the developer tools and UI components needed to build exceptional RevitPy applications:

- **🎨 React Dashboard** - Developer dashboard with package browser, project manager, REPL, and monitoring
- **🔧 VS Code Extension** - Full-featured IDE extension with IntelliSense, debugging, and project templates
- **📦 Package Registry UI** - Web interface for discovering and installing RevitPy packages
- **⚡ Hot Reload Server** - Development server with real-time communication and hot module replacement
- **🧩 UI Component Library** - Reusable React components with theme support and accessibility
- **🌐 WebView2 Host** - .NET integration for custom panels with bi-directional data binding

## Architecture

```
RevitPy Developer Tools
├── apps/
│   ├── dashboard/          # React developer dashboard
│   └── package-registry/   # Package discovery interface
├── packages/
│   ├── types/             # TypeScript type definitions
│   └── ui/                # Reusable UI components
├── src/
│   ├── RevitPy.WebHost/   # .NET WebView2 integration
│   ├── RevitPy.VSCodeExtension/  # VS Code extension
│   └── RevitPy.HotReload/ # Development server
└── docs/                  # Documentation
```

## Quick Start

### Prerequisites

- **Node.js** 18.0.0 or higher
- **npm** 8.0.0 or higher  
- **.NET 6.0** or higher
- **VS Code** (for extension development)
- **Revit 2021+** (for testing)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/revitpy/revitpy-devtools.git
   cd revitpy-devtools
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Build all packages:**
   ```bash
   npm run build
   ```

4. **Start development server:**
   ```bash
   npm run dev
   ```

## Components

### 🎨 React Dashboard

A comprehensive developer dashboard providing:

- **Project Management** - Create, open, and manage RevitPy projects
- **Package Browser** - Discover and install community packages
- **Interactive REPL** - Test Python code with live Revit connection
- **Performance Monitoring** - Real-time system metrics and profiling
- **Extension Marketplace** - Browse and manage VS Code extensions

**Usage:**
```bash
cd apps/dashboard
npm run dev
```

**Features:**
- Modern React 18 with TypeScript
- TanStack Query for data fetching
- Zustand for state management
- Framer Motion for animations
- Tailwind CSS for styling
- Radix UI for accessibility

### 🔧 VS Code Extension

Full-featured IDE extension for RevitPy development:

- **Syntax Highlighting** - Custom language support for RevitPy
- **IntelliSense** - Auto-completion for Revit API
- **Integrated Debugger** - Debug RevitPy scripts with breakpoints
- **Project Templates** - Scaffolding for different project types
- **Extension Testing** - Built-in test runner

**Installation:**
```bash
cd src/RevitPy.VSCodeExtension
npm run compile
code --install-extension .
```

**Features:**
- Language server protocol integration
- Real-time error checking and linting
- Code formatting and refactoring
- Integrated terminal with RevitPy CLI
- Project explorer with Revit connection status

### 📦 Package Registry UI

Web interface for the RevitPy package ecosystem:

- **Package Discovery** - Search and filter packages
- **Installation Manager** - One-click package installation
- **Version Management** - Handle package updates and dependencies
- **Community Features** - Ratings, reviews, and discussions

**Usage:**
```bash
cd apps/package-registry
npm run dev
```

**Features:**
- Advanced search with filters and sorting
- Package comparison tools
- Dependency visualization
- Offline-first architecture with service worker
- Progressive web app (PWA) support

### ⚡ Hot Reload Server

Development server with real-time communication:

- **File Watching** - Monitor source files for changes
- **Hot Module Replacement** - Update code without page refresh
- **Revit Integration** - Bi-directional communication with Revit
- **Build System** - Integrated TypeScript and Python compilation

**Usage:**
```bash
cd src/RevitPy.HotReload
npm run build
npm start
```

**Features:**
- WebSocket-based real-time communication
- Intelligent file watching with debouncing
- Multi-target build support
- Performance monitoring and profiling
- Plugin architecture for extensibility

### 🧩 UI Component Library

Reusable React components with theme support:

- **Design System** - Consistent visual language
- **Accessibility** - WCAG 2.1 AA compliance
- **Theme Support** - Light, dark, and custom themes
- **TypeScript** - Full type safety
- **Storybook** - Interactive component documentation

**Usage:**
```bash
npm install @revitpy/ui
```

```tsx
import { Button, ConnectionStatus } from '@revitpy/ui';

function App() {
  return (
    <div>
      <ConnectionStatus status="connected" />
      <Button variant="primary">Click me</Button>
    </div>
  );
}
```

**Components:**
- Form controls (Button, Input, Select, etc.)
- Layout components (Card, Tabs, Dialog, etc.)
- RevitPy-specific components (ConnectionStatus, PerformanceChart, etc.)
- Data visualization (Charts, metrics, etc.)

### 🌐 WebView2 Host Integration

.NET component for hosting web UI in Revit:

- **WebView2 Integration** - Modern web engine in .NET
- **Bi-directional Data Binding** - Sync data between .NET and JavaScript
- **Hot Module Replacement** - Development-time code updates
- **Security** - Sandboxed execution with controlled permissions

**Usage:**
```csharp
var config = new WebViewConfiguration
{
    Id = "my-panel",
    Title = "My RevitPy Panel", 
    Url = "http://localhost:3000",
    Type = PanelType.Dockable
};

var host = new WebViewHost(logger);
await host.InitializeAsync(config);
await host.ShowAsync();
```

**Features:**
- Multiple panel management
- Custom URI scheme handlers
- Performance monitoring
- Error handling and recovery
- Memory management

## Development

### Setting up Development Environment

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Start development servers:**
   ```bash
   # Start all development servers
   npm run dev
   
   # Or start individual components
   npm run dev:dashboard
   npm run dev:registry
   npm run dev:server
   ```

3. **Build for production:**
   ```bash
   npm run build
   ```

4. **Run tests:**
   ```bash
   npm run test
   npm run test:ui  # Visual test runner
   npm run test:e2e # End-to-end tests
   ```

### Project Structure

```
├── apps/
│   ├── dashboard/
│   │   ├── src/
│   │   │   ├── components/    # React components
│   │   │   ├── pages/         # Application pages  
│   │   │   ├── hooks/         # Custom React hooks
│   │   │   ├── stores/        # Zustand stores
│   │   │   └── providers/     # Context providers
│   │   ├── public/            # Static assets
│   │   └── package.json
│   └── package-registry/
│       ├── src/
│       │   ├── components/    # UI components
│       │   ├── pages/         # Registry pages
│       │   └── hooks/         # Package management hooks
│       └── package.json
├── packages/
│   ├── types/
│   │   └── src/
│   │       ├── core.ts        # Core type definitions
│   │       ├── api.ts         # API types
│   │       ├── ui.ts          # UI component types
│   │       └── devtools.ts    # Developer tool types
│   └── ui/
│       ├── src/
│       │   ├── components/    # Reusable UI components
│       │   ├── hooks/         # Custom hooks
│       │   ├── providers/     # Context providers
│       │   └── lib/           # Utility functions
│       ├── stories/           # Storybook stories
│       └── __tests__/         # Component tests
└── src/
    ├── RevitPy.WebHost/
    │   ├── Models/            # Data models
    │   ├── Services/          # Business logic
    │   └── Properties/        # Assembly info
    ├── RevitPy.VSCodeExtension/
    │   ├── src/
    │   │   ├── providers/     # Tree data providers
    │   │   ├── commands/      # VS Code commands
    │   │   ├── debug/         # Debug adapter
    │   │   └── language/      # Language server
    │   ├── syntaxes/          # Syntax highlighting
    │   └── snippets/          # Code snippets
    └── RevitPy.HotReload/
        ├── src/
        │   ├── watchers/      # File watchers
        │   ├── build/         # Build system
        │   ├── communication/ # WebSocket handling
        │   └── connectors/    # Revit integration
        └── package.json
```

### Coding Standards

- **TypeScript** - Strict mode enabled with comprehensive type checking
- **ESLint** - Code linting with React and accessibility rules
- **Prettier** - Consistent code formatting
- **Conventional Commits** - Standardized commit messages
- **Testing** - Comprehensive test coverage with Vitest and Testing Library

### Building and Testing

```bash
# Build all packages
npm run build

# Run type checking
npm run type-check

# Run linting
npm run lint

# Run tests with coverage
npm run test:coverage

# Visual regression testing
npm run test:visual

# End-to-end testing
npm run test:e2e

# Performance testing
npm run test:perf
```

## Deployment

### Production Build

```bash
# Build all packages for production
npm run build:prod

# Optimize and compress assets
npm run optimize

# Generate documentation
npm run docs:build
```

### Docker Deployment

```bash
# Build Docker image
docker build -t revitpy-devtools .

# Run container
docker run -p 3000:3000 revitpy-devtools
```

### CI/CD Pipeline

The project uses GitHub Actions for continuous integration:

- **Build verification** on all PRs
- **Automated testing** including unit, integration, and E2E tests
- **Security scanning** with CodeQL and dependency checks
- **Performance benchmarks** to prevent regressions
- **Automated releases** with semantic versioning

## Configuration

### Environment Variables

Create a `.env.local` file in the project root:

```env
# Development server
VITE_DEV_SERVER_PORT=3000
VITE_HOT_RELOAD_PORT=3001

# Package registry
VITE_PACKAGE_REGISTRY_URL=https://packages.revitpy.dev
VITE_API_BASE_URL=https://api.revitpy.dev

# Authentication
VITE_AUTH_PROVIDER=github
VITE_AUTH_CLIENT_ID=your_client_id

# Analytics (optional)
VITE_ANALYTICS_ID=your_analytics_id
```

### Configuration Files

- **`turbo.json`** - Turborepo configuration for monorepo builds
- **`tsconfig.json`** - TypeScript configuration
- **`tailwind.config.js`** - Tailwind CSS configuration
- **`vite.config.ts`** - Vite build configuration
- **`vitest.config.ts`** - Test configuration

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Getting Started

1. **Fork the repository**
2. **Create a feature branch:** `git checkout -b feature/amazing-feature`
3. **Make your changes** with proper tests and documentation
4. **Run the test suite:** `npm test`
5. **Commit your changes:** `git commit -m 'feat: add amazing feature'`
6. **Push to the branch:** `git push origin feature/amazing-feature`
7. **Open a Pull Request**

### Development Workflow

1. **Issue Creation** - Create an issue describing the feature or bug
2. **Branch Creation** - Create a feature branch from `main`
3. **Development** - Implement changes with tests and documentation
4. **Review** - Submit PR for code review
5. **Testing** - Automated tests must pass
6. **Merge** - Approved PRs are merged to `main`
7. **Release** - Automated release process creates new versions

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Documentation:** [https://docs.revitpy.dev](https://docs.revitpy.dev)
- **Discord:** [https://discord.gg/revitpy](https://discord.gg/revitpy)
- **Issues:** [GitHub Issues](https://github.com/revitpy/revitpy-devtools/issues)
- **Discussions:** [GitHub Discussions](https://github.com/revitpy/revitpy-devtools/discussions)

## Acknowledgments

- **Radix UI** - Accessible component primitives
- **Tailwind CSS** - Utility-first CSS framework
- **Framer Motion** - Animation library
- **TanStack Query** - Data synchronization
- **Vite** - Build tool and development server
- **Vitest** - Testing framework

---

Built with ❤️ by the RevitPy team