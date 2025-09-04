# RevitPy VS Code Extension

A comprehensive Visual Studio Code extension for RevitPy development that provides a world-class developer experience.

## Features

### 🎯 Syntax Highlighting & IntelliSense
- Custom language support for RevitPy scripts (.rvtpy files)
- Full Revit API auto-completion with type information
- Context-aware suggestions and documentation
- **Sub-500ms response time** for IntelliSense requests

### 🐛 Integrated Debugging
- Step-through debugging of RevitPy scripts running in Revit
- Breakpoint support with conditional breakpoints
- Variable inspection and evaluation
- Real-time connection to Revit environment

### 🔗 Hot-Reload Integration
- Live connection to RevitPy development server
- Automatic script execution on file changes
- Visual feedback for connection status
- WebSocket-based real-time communication

### 📦 Package Management
- Browse and search RevitPy package registry
- Install/uninstall packages directly from VS Code
- Package dependency management
- Integration with project configuration

### 🚀 Project Management
- Multiple project templates (Basic Script, Add-in, Export Tool, Test Suite)
- Project scaffolding with best practices
- Integrated build and deployment tools
- RevitPy project configuration (revitpy.json)

### 🎨 User Interface
- Custom tree views for connection status and packages
- Status bar indicators for connection and package status
- Command palette integration
- Context menus for script execution

## Quick Start

1. **Install the Extension**
   ```bash
   # From VS Code Marketplace (when published)
   code --install-extension revitpy.revitpy-vscode
   
   # Or install from VSIX
   code --install-extension revitpy-vscode-1.0.0.vsix
   ```

2. **Create a New Project**
   - Press `Ctrl+Shift+P` and select "RevitPy: Create Project"
   - Choose from available templates
   - Select project location and enter name

3. **Connect to Revit**
   - Ensure RevitPy is running in Revit
   - Click "Connect to Revit" in status bar or use Command Palette
   - Configure connection settings if needed

4. **Start Developing**
   - Write your RevitPy scripts with full IntelliSense
   - Use F5 to run scripts in Revit
   - Set breakpoints for debugging

## Configuration

The extension can be configured through VS Code settings:

```json
{
  "revitpy.host": "localhost",
  "revitpy.port": 8080,
  "revitpy.enableHotReload": true,
  "revitpy.enableIntelliSense": true,
  "revitpy.stubsPath": "/path/to/revit/stubs",
  "revitpy.logLevel": "info"
}
```

## Project Structure

RevitPy projects use a `revitpy.json` configuration file:

```json
{
  "name": "my-revit-project",
  "version": "1.0.0",
  "description": "My RevitPy project",
  "entryPoint": "main.py",
  "revitVersions": ["2022", "2023", "2024"],
  "dependencies": {
    "revitpy-utils": "latest"
  }
}
```

## Commands

| Command | Description | Keybinding |
|---------|-------------|------------|
| `RevitPy: Create Project` | Create new RevitPy project | |
| `RevitPy: Connect to Revit` | Connect to Revit instance | |
| `RevitPy: Run Script` | Execute current script in Revit | `F5` |
| `RevitPy: Debug Script` | Debug current script | `Ctrl+F5` |
| `RevitPy: Open Package Manager` | Open package manager UI | |
| `RevitPy: Generate Stubs` | Generate Revit API stubs | |

## Language Features

### Syntax Highlighting
- RevitPy-specific constructs
- Revit API classes and namespaces
- Transaction patterns
- Built-in categories and parameters

### Code Snippets
- `revitpy-basic` - Basic script template
- `transaction` - Transaction block
- `collector` - Element collector
- `dialog` - Task dialog
- And many more...

### IntelliSense Features
- Auto-completion for Revit API classes and methods
- Parameter information and documentation
- Type information and signatures
- Context-aware suggestions
- Import statement completion

## Debugging

The extension provides comprehensive debugging support:

1. **Set Breakpoints** - Click in the gutter to set breakpoints
2. **Start Debugging** - Use F5 or "Debug Script" command
3. **Step Through Code** - Use standard VS Code debugging controls
4. **Inspect Variables** - View locals and globals in debug panel
5. **Evaluate Expressions** - Use debug console to evaluate code

## Package Management

The integrated package manager allows you to:

- **Browse Packages** - Discover available RevitPy packages
- **Search Registry** - Find packages by name or keywords
- **Install/Uninstall** - Manage project dependencies
- **View Updates** - Check for package updates
- **Dependency Resolution** - Automatic dependency management

## Development

To contribute to this extension:

1. **Clone Repository**
   ```bash
   git clone https://github.com/revitpy/vscode-extension
   cd vscode-extension
   ```

2. **Install Dependencies**
   ```bash
   npm install
   ```

3. **Compile TypeScript**
   ```bash
   npm run compile
   ```

4. **Run Extension**
   - Press F5 in VS Code to launch Extension Development Host

5. **Run Tests**
   ```bash
   npm test
   ```

## Architecture

The extension consists of several key components:

- **Language Server** - Provides IntelliSense and diagnostics
- **Debug Adapter** - Handles debugging communication with Revit
- **Connection Manager** - Manages WebSocket connection to Revit
- **Package Manager** - Handles package operations and UI
- **Project Manager** - Project templates and scaffolding

## Performance

The extension is optimized for performance:

- **IntelliSense**: < 500ms response time
- **Connection**: WebSocket for real-time communication
- **Caching**: Intelligent caching of API documentation
- **Memory**: Efficient memory usage for large projects

## Requirements

- Visual Studio Code 1.80.0 or higher
- RevitPy runtime environment
- Autodesk Revit 2022 or later (for debugging and execution)

## Troubleshooting

### Connection Issues
- Ensure RevitPy is running in Revit
- Check firewall settings for port 8080
- Verify host/port configuration

### IntelliSense Issues
- Check if stubs are properly loaded
- Verify Python environment configuration
- Try regenerating API stubs

### Debugging Issues
- Ensure Revit is connected
- Check debug configuration
- Verify script syntax

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please see CONTRIBUTING.md for guidelines.

## Support

- Documentation: https://docs.revitpy.com
- Issues: https://github.com/revitpy/vscode-extension/issues
- Discord: https://discord.gg/revitpy