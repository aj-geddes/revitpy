---
layout: default
title: Getting Started
description: Install RevitPy and build your first Revit automation script in under 10 minutes. Complete setup guide with prerequisites, installation, and your first project.
permalink: /getting-started/
---

<div class="container" markdown="1">
<div class="main-content" markdown="1">

<div class="page-header">
      <h1 class="page-title">Getting Started with RevitPy</h1>
      <p class="page-description">
        Get up and running with RevitPy in under 10 minutes. This guide covers installation, prerequisites, and creating your first project.
      </p>
    </div>

## Prerequisites

Before installing RevitPy, ensure you have:

- **Autodesk Revit** 2021 or later installed
- **Windows 10/11** (64-bit)
- **Python 3.11+** (recommended) or Python 3.9+
- **Visual Studio Code** (recommended for development)

<div class="callout callout-info">
  <div class="callout-title">Python Installation</div>
  <p>Download Python from <a href="https://python.org/downloads" target="_blank">python.org</a>. During installation, check "Add Python to PATH".</p>
</div>

## Installation

### Option 1: MSI Installer (Recommended)

Download and run the MSI installer for a guided installation:

```bash
# Download from GitHub releases
# Run the installer
msiexec /i RevitPy-Installer.msi
```

The MSI installer:
- Installs RevitPy and all dependencies
- Configures Revit integration automatically
- Adds the `revitpy` CLI to your PATH
- Supports silent installation for enterprise deployment

### Option 2: pip Install

Install directly with pip:

```bash
pip install revitpy
```

Then configure Revit integration:

```bash
revitpy doctor --install
```

### Option 3: Development Install

For contributing or development:

```bash
git clone https://github.com/revitpy/revitpy.git
cd revitpy
pip install -e ".[dev]"
```

## Verify Installation

Check that RevitPy is installed correctly:

```bash
revitpy --version
# RevitPy v1.0.0

revitpy doctor
# ✓ Python 3.11.5
# ✓ RevitPy installed
# ✓ Revit 2024 detected
# ✓ VS Code extension installed
```

## Your First Project

### Create a New Project

Use the CLI to create a project from a template:

```bash
revitpy create my-first-project --template basic-script
cd my-first-project
```

This creates:

```
my-first-project/
├── src/
│   └── main.py          # Your main script
├── tests/
│   └── test_main.py     # Test file
├── pyproject.toml       # Project configuration
└── README.md            # Documentation
```

### Write Your First Script

Edit `src/main.py`:

```python
from revitpy import RevitContext

def main():
    """Query and display wall information."""
    with RevitContext() as context:
        # Get all walls in the document
        walls = context.elements.of_category('Walls')

        print(f"Found {len(walls)} walls in the model\n")

        # Display first 5 walls
        for wall in walls.take(5):
            height = wall.get_parameter('Unconnected Height')
            print(f"- {wall.Name}")
            print(f"  Height: {height.value} {height.unit}")
            print()

if __name__ == "__main__":
    main()
```

### Run in Development Mode

Start the development server with hot reload:

```bash
revitpy dev --watch
```

This will:
1. Connect to Revit
2. Run your script
3. Watch for file changes
4. Automatically reload when you save

### Run Tests

Execute your test suite:

```bash
revitpy test
```

## Project Configuration

Configure your project in `pyproject.toml`:

```toml
[project]
name = "my-first-project"
version = "0.1.0"
description = "My first RevitPy project"
requires-python = ">=3.11"

[tool.revitpy]
revit_versions = ["2024", "2025"]
entry_point = "src/main.py"

[tool.revitpy.dev]
hot_reload = true
auto_connect = true
```

## VS Code Integration

### Install the Extension

1. Open VS Code
2. Go to Extensions (Ctrl+Shift+X)
3. Search for "RevitPy"
4. Click Install

### Features

The VS Code extension provides:

- **IntelliSense**: Auto-complete for RevitPy API
- **Debugging**: Set breakpoints, inspect variables
- **Hot Reload**: Automatic code reload on save
- **Snippets**: Common code patterns
- **Documentation**: Hover for API docs

### Debugging

Add a debug configuration in `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "RevitPy: Debug Script",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/src/main.py",
      "console": "integratedTerminal",
      "revitpy": {
        "connectToRevit": true,
        "hotReload": true
      }
    }
  ]
}
```

Press F5 to start debugging.

## CLI Commands

Common RevitPy CLI commands:

| Command | Description |
|---------|-------------|
| `revitpy create` | Create a new project |
| `revitpy dev` | Start development server |
| `revitpy build` | Build for production |
| `revitpy test` | Run tests |
| `revitpy install` | Install dependencies |
| `revitpy publish` | Publish to registry |
| `revitpy doctor` | Check installation |

## Next Steps

Now that you have RevitPy set up, explore these resources:

<div class="examples-grid" style="margin-top: var(--space-6);">
  <a href="{{ '/examples/' | relative_url }}" class="example-card">
    <div class="example-icon">&#128214;</div>
    <h3 class="example-title">Examples</h3>
    <p class="example-description">Real-world examples covering energy analysis, ML, IoT integration, and more.</p>
  </a>

  <a href="{{ '/documentation/' | relative_url }}" class="example-card">
    <div class="example-icon">&#128218;</div>
    <h3 class="example-title">API Reference</h3>
    <p class="example-description">Complete API documentation with detailed type information and examples.</p>
  </a>

  <a href="{{ '/pyrevit-integration/' | relative_url }}" class="example-card">
    <div class="example-icon">&#128279;</div>
    <h3 class="example-title">PyRevit Integration</h3>
    <p class="example-description">Learn how to use RevitPy alongside PyRevit for hybrid workflows.</p>
  </a>
</div>

## Troubleshooting

### Common Issues

<div class="callout callout-warning">
  <div class="callout-title">Revit Not Detected</div>
  <p>Run <code>revitpy doctor --verbose</code> to see detailed diagnostic information. Ensure Revit is installed in the default location or set <code>REVIT_PATH</code> environment variable.</p>
</div>

<div class="callout callout-warning">
  <div class="callout-title">Permission Errors</div>
  <p>Run the installer or CLI as Administrator if you encounter permission issues during installation.</p>
</div>

### Get Help

- **Documentation**: [revitpy.org/documentation]({{ '/documentation/' | relative_url }})
- **GitHub Issues**: [github.com/revitpy/revitpy/issues](https://github.com/revitpy/revitpy/issues)
- **Discussions**: [github.com/revitpy/revitpy/discussions](https://github.com/revitpy/revitpy/discussions)

</div>
</div>
