# Getting Started with RevitPy Developer Tools

This guide will help you get up and running with the RevitPy Developer Tools suite.

## Prerequisites

Before you begin, ensure you have the following installed:

### Required Software

- **Node.js** 18.0.0 or higher
- **npm** 8.0.0 or higher
- **.NET 6.0** SDK or higher
- **Git** for version control

### For Extension Development

- **Visual Studio Code** 1.85.0 or higher
- **VS Code Extension Manager** (vsce)

### For Revit Integration

- **Autodesk Revit** 2021 or higher
- **Windows 10/11** (64-bit)

## Quick Setup

### 1. Clone and Install

```bash
# Clone the repository
git clone https://github.com/revitpy/revitpy-devtools.git
cd revitpy-devtools

# Install dependencies
npm install

# Build all packages
npm run build
```

### 2. Verify Installation

```bash
# Run system check
npm run doctor

# Start development server
npm run dev
```

Your browser should open to `http://localhost:3000` showing the RevitPy Dashboard.

## Development Workflow

### Starting Development

```bash
# Start all development servers
npm run dev

# Or start individual components:
npm run dev:dashboard      # React dashboard
npm run dev:registry       # Package registry
npm run dev:server         # Hot reload server
npm run dev:storybook      # Component library
```

### Building for Production

```bash
# Build everything
npm run build

# Build specific packages
npm run build:dashboard
npm run build:ui
npm run build:server
```

### Testing

```bash
# Run all tests
npm run test

# Run tests with coverage
npm run test:coverage

# Run visual tests
npm run test:ui

# Run end-to-end tests
npm run test:e2e
```

## Component Overview

### 1. React Dashboard (`apps/dashboard`)

The main developer interface providing:

- **Project Management** - Create, open, and manage projects
- **Package Browser** - Discover and install packages
- **REPL Interface** - Interactive Python console
- **Performance Monitoring** - Real-time metrics

**Key Files:**
- `src/pages/dashboard/` - Main dashboard page
- `src/components/layout/` - Layout components
- `src/stores/` - State management
- `src/providers/` - Context providers

### 2. Package Registry (`apps/package-registry`)

Web interface for package discovery:

- **Package Search** - Advanced filtering and search
- **Package Details** - Documentation, versions, dependencies
- **Installation** - One-click package installation
- **Community Features** - Ratings and reviews

**Key Files:**
- `src/pages/index.tsx` - Main registry page
- `src/components/package-card.tsx` - Package display
- `src/hooks/use-package-search.ts` - Search functionality

### 3. UI Component Library (`packages/ui`)

Reusable React components:

- **Core Components** - Button, Input, Card, etc.
- **RevitPy Components** - ConnectionStatus, PerformanceChart
- **Layout Components** - AppShell, Sidebar, Header
- **Theme System** - Light, dark, and custom themes

**Key Files:**
- `src/components/ui/` - Core UI components  
- `src/components/revitpy/` - RevitPy-specific components
- `src/components/layout/` - Layout components
- `src/providers/theme-provider.tsx` - Theme management

### 4. VS Code Extension (`src/RevitPy.VSCodeExtension`)

IDE integration for RevitPy development:

- **Language Support** - Syntax highlighting, IntelliSense
- **Project Management** - Create, build, deploy projects
- **Debugging** - Integrated debugger with breakpoints
- **Revit Integration** - Direct connection to Revit

**Key Files:**
- `src/extension.ts` - Main extension entry point
- `src/providers/` - Tree data providers
- `syntaxes/revitpy.tmLanguage.json` - Syntax highlighting
- `snippets/revitpy-snippets.json` - Code snippets

### 5. Hot Reload Server (`src/RevitPy.HotReload`)

Development server with real-time updates:

- **File Watching** - Monitor source changes
- **Build System** - Compile TypeScript, Python
- **WebSocket Communication** - Real-time updates
- **Revit Integration** - Bi-directional communication

**Key Files:**
- `src/server.ts` - Main server implementation
- `src/watchers/fileWatcher.ts` - File monitoring
- `src/communication/messageBroker.ts` - WebSocket handling
- `src/cli.ts` - Command-line interface

### 6. WebView2 Host (`src/RevitPy.WebHost`)

.NET integration for custom panels:

- **WebView2 Integration** - Host web UI in Revit
- **Panel Management** - Dockable, modal, modeless panels
- **Data Binding** - Sync between .NET and JavaScript
- **Event Handling** - User interactions and Revit events

**Key Files:**
- `Services/WebViewHost.cs` - Main host implementation
- `Services/WebViewHostManager.cs` - Multi-panel management
- `Models/WebViewConfiguration.cs` - Configuration options
- `Models/MessageModels.cs` - Communication types

## Creating Your First Component

### 1. UI Component

Create a new component in `packages/ui/src/components/ui/`:

```tsx
// packages/ui/src/components/ui/my-component.tsx
import * as React from 'react';
import { cn } from '../../lib/utils';

interface MyComponentProps {
  children: React.ReactNode;
  variant?: 'default' | 'secondary';
  className?: string;
}

export const MyComponent = React.forwardRef<
  HTMLDivElement,
  MyComponentProps
>(({ children, variant = 'default', className, ...props }, ref) => {
  return (
    <div
      ref={ref}
      className={cn(
        'p-4 rounded-lg',
        variant === 'default' && 'bg-primary text-primary-foreground',
        variant === 'secondary' && 'bg-secondary text-secondary-foreground',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
});

MyComponent.displayName = 'MyComponent';
```

### 2. Add Tests

Create tests in `packages/ui/src/components/ui/my-component.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '../../test/test-utils';
import { MyComponent } from './my-component';

describe('MyComponent', () => {
  it('renders children correctly', () => {
    render(<MyComponent>Hello World</MyComponent>);
    expect(screen.getByText('Hello World')).toBeInTheDocument();
  });

  it('applies variant styles', () => {
    render(<MyComponent variant="secondary">Test</MyComponent>);
    expect(screen.getByText('Test')).toHaveClass('bg-secondary');
  });
});
```

### 3. Export Component

Add to `packages/ui/src/index.ts`:

```ts
export * from './components/ui/my-component';
```

### 4. Create Storybook Story

Create `packages/ui/src/stories/MyComponent.stories.tsx`:

```tsx
import type { Meta, StoryObj } from '@storybook/react';
import { MyComponent } from '../components/ui/my-component';

const meta: Meta<typeof MyComponent> = {
  title: 'UI/MyComponent',
  component: MyComponent,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    children: 'Hello World',
  },
};

export const Secondary: Story = {
  args: {
    children: 'Secondary variant',
    variant: 'secondary',
  },
};
```

## Configuration

### Environment Variables

Create `.env.local` files for local development:

**Root `.env.local`:**
```env
# Development ports
VITE_DEV_SERVER_PORT=3000
VITE_HOT_RELOAD_PORT=3001
VITE_STORYBOOK_PORT=6006

# API endpoints
VITE_API_BASE_URL=http://localhost:8000
VITE_PACKAGE_REGISTRY_URL=http://localhost:3002

# Feature flags
VITE_ENABLE_DEBUG=true
VITE_ENABLE_ANALYTICS=false
```

**Dashboard `.env.local`:**
```env
# Dashboard specific config
VITE_DASHBOARD_TITLE="RevitPy Development Dashboard"
VITE_DEFAULT_THEME=system
VITE_ENABLE_HOT_RELOAD=true
```

### TypeScript Configuration

The project uses a shared TypeScript configuration with path mapping:

```json
// tsconfig.json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"],
      "@revitpy/ui": ["./packages/ui/src"],
      "@revitpy/types": ["./packages/types/src"]
    }
  }
}
```

### Tailwind CSS Configuration

Shared Tailwind configuration with design tokens:

```js
// tailwind.config.js
module.exports = {
  content: [
    './apps/**/*.{ts,tsx}',
    './packages/ui/src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: 'hsl(var(--primary))',
        secondary: 'hsl(var(--secondary))',
        // ... custom color palette
      },
    },
  },
};
```

## Common Tasks

### Adding a New Page

1. Create page component in `apps/dashboard/src/pages/`
2. Add route to `apps/dashboard/src/routes.tsx`
3. Update navigation in `apps/dashboard/src/components/layout/sidebar.tsx`

### Creating a VS Code Command

1. Add command to `src/RevitPy.VSCodeExtension/package.json`
2. Implement handler in `src/RevitPy.VSCodeExtension/src/extension.ts`
3. Register command in activation function

### Adding WebView2 Panel

1. Create React component for panel content
2. Configure panel in `WebViewConfiguration`
3. Initialize with `WebViewHost.InitializeAsync()`
4. Handle communication via message passing

### Building Custom Themes

1. Create theme definition in `packages/ui/src/themes/`
2. Add CSS custom properties
3. Export theme from theme provider
4. Document theme usage

## Debugging

### Browser Developer Tools

- **Dashboard**: Open DevTools in browser (`F12`)
- **Package Registry**: Use React DevTools extension
- **Storybook**: Built-in debugging with Controls addon

### VS Code Extension Debugging

1. Open `src/RevitPy.VSCodeExtension` in VS Code
2. Press `F5` to launch Extension Development Host
3. Set breakpoints in TypeScript code
4. Use Debug Console for logging

### .NET WebHost Debugging

1. Open `src/RevitPy.WebHost` in Visual Studio
2. Set breakpoints in C# code
3. Attach to Revit process for testing
4. Use Output window for debug logs

### Hot Reload Server Debugging

```bash
# Start server with debug logging
cd src/RevitPy.HotReload
npm run dev -- --log-level debug

# View WebSocket messages
npm run dev -- --verbose
```

## Performance Optimization

### Bundle Analysis

```bash
# Analyze bundle size
npm run analyze

# Lighthouse audit
npm run lighthouse

# Performance testing
npm run test:perf
```

### Code Splitting

Use dynamic imports for large components:

```tsx
// Lazy load heavy components
const PerformanceChart = lazy(() => 
  import('@revitpy/ui').then(m => ({ 
    default: m.PerformanceChart 
  }))
);
```

### Memory Management

- Use React.memo for expensive components
- Implement proper cleanup in useEffect
- Monitor WebView2 memory usage
- Use virtual scrolling for large lists

## Troubleshooting

### Common Issues

**Node.js Version Mismatch**
```bash
# Check version
node --version  # Should be 18+

# Use nvm to switch versions
nvm install 18
nvm use 18
```

**Port Already in Use**
```bash
# Find process using port
lsof -i :3000  # macOS/Linux
netstat -ano | findstr :3000  # Windows

# Kill process or change port in .env.local
```

**VS Code Extension Not Loading**
```bash
# Rebuild extension
cd src/RevitPy.VSCodeExtension
npm run compile
code --install-extension .
```

**WebView2 Runtime Missing**
- Download from [Microsoft Edge WebView2](https://developer.microsoft.com/microsoft-edge/webview2/)
- Install redistributable package

### Getting Help

- **Documentation**: [https://docs.revitpy.dev](https://docs.revitpy.dev)
- **Discord Community**: [https://discord.gg/revitpy](https://discord.gg/revitpy)
- **GitHub Issues**: [https://github.com/revitpy/revitpy-devtools/issues](https://github.com/revitpy/revitpy-devtools/issues)
- **Stack Overflow**: Tag questions with `revitpy`

## Next Steps

Now that you have the development environment set up:

1. **Explore the Dashboard** - Familiarize yourself with the interface
2. **Create a Simple Component** - Follow the component creation guide
3. **Build a Sample Project** - Use the project templates
4. **Join the Community** - Connect with other developers
5. **Contribute** - Check out the contributing guidelines

Happy coding! 🚀