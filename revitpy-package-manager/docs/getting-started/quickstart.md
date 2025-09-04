# Quick Start Guide

Get up and running with RevitPy Package Manager in under 5 minutes! This guide assumes you've already [installed RevitPy Package Manager](installation.md).

## 🚀 5-Minute Quick Start

### Step 1: Create Your First Environment (30 seconds)

```bash
# Create a new environment for your project
revitpy-install env create quickstart --revit-version 2024

# Activate the environment
revitpy-install env activate quickstart
```

### Step 2: Install a Package (1 minute)

```bash
# Search for available packages
revitpy-install search geometry

# Install a geometry utilities package
revitpy-install install revitpy-geometry

# Verify installation
revitpy-install list
```

### Step 3: Create Your First Package (2 minutes)

Create a simple package structure:

```bash
# Create package directory
mkdir my-revit-tools
cd my-revit-tools

# Initialize package
revitpy-build init --name my-revit-tools --author "Your Name"
```

This creates:

```
my-revit-tools/
├── pyproject.toml      # Package configuration
├── src/
│   └── my_revit_tools/
│       ├── __init__.py
│       └── main.py     # Your main code
├── tests/
│   └── test_main.py
└── README.md
```

### Step 4: Add Some Code (1 minute)

Edit `src/my_revit_tools/main.py`:

```python
"""My first RevitPy package."""

from revitpy.geometry import Point3D, Vector3D

def create_point_grid(count_x: int = 5, count_y: int = 5, spacing: float = 10.0):
    """Create a grid of points in 3D space.
    
    Args:
        count_x: Number of points in X direction
        count_y: Number of points in Y direction  
        spacing: Distance between points
        
    Returns:
        List of Point3D objects
    """
    points = []
    
    for x in range(count_x):
        for y in range(count_y):
            point = Point3D(x * spacing, y * spacing, 0)
            points.append(point)
    
    return points

def greet_revit():
    """Simple greeting function."""
    return "Hello from RevitPy Package Manager! 🎉"

if __name__ == "__main__":
    # Test the functions
    points = create_point_grid(3, 3, 5.0)
    print(f"Created {len(points)} points")
    print(greet_revit())
```

### Step 5: Build and Test (1 minute)

```bash
# Build the package
revitpy-build package --source .

# Run tests
python -m pytest tests/

# Install your package locally
revitpy-install install dist/my-revit-tools-0.1.0.tar.gz
```

### Step 6: Use in Revit (30 seconds)

Create a simple Revit script to test:

```python
# test_in_revit.py
from my_revit_tools.main import create_point_grid, greet_revit

# Test the functions
print(greet_revit())
points = create_point_grid(2, 2, 100.0)
print(f"Generated {len(points)} points for Revit model")

# In a real Revit script, you'd create model geometry here
# For now, just print the point coordinates  
for i, point in enumerate(points):
    print(f"Point {i+1}: ({point.x}, {point.y}, {point.z})")
```

## 🎯 What You Just Did

Congratulations! In 5 minutes you:

✅ **Created a virtual environment** for isolated package management  
✅ **Installed a package** from the RevitPy registry  
✅ **Built your first package** with proper structure and metadata  
✅ **Tested the package** works correctly  
✅ **Used it in a Revit context** (simulated)

## 📚 Common Commands Reference

Here are the most frequently used commands:

### Environment Management
```bash
# List all environments
revitpy-install env list

# Create new environment
revitpy-install env create PROJECT_NAME --revit-version YEAR

# Activate environment  
revitpy-install env activate PROJECT_NAME

# Delete environment
revitpy-install env remove PROJECT_NAME
```

### Package Installation
```bash
# Search packages
revitpy-install search KEYWORD

# Install package
revitpy-install install PACKAGE_NAME

# Install specific version
revitpy-install install PACKAGE_NAME==1.2.3

# Uninstall package
revitpy-install uninstall PACKAGE_NAME

# List installed packages
revitpy-install list
```

### Package Development
```bash
# Initialize new package
revitpy-build init --name PACKAGE_NAME

# Validate package structure
revitpy-build validate .

# Build package
revitpy-build package --source .

# Sign package (for publishing)
revitpy-build sign PACKAGE.tar.gz --key signing.pem
```

## 🎨 Package Templates

RevitPy provides several templates for different use cases:

### Basic Script Package
```bash
revitpy-build init --template basic-script --name my-script
```

Creates a simple script package with:
- Single Python module
- Basic configuration
- Simple tests

### UI Extension Package  
```bash
revitpy-build init --template ui-extension --name my-extension
```

Creates a full UI extension with:
- WPF/WinForms UI components
- Revit ribbon integration
- Event handlers
- Resource files

### Geometry Utilities Package
```bash
revitpy-build init --template geometry-utils --name my-geometry
```

Creates a geometry-focused package with:
- 3D math utilities
- Revit geometry helpers
- Performance optimizations
- Comprehensive tests

### Data Processing Package
```bash
revitpy-build init --template data-processing --name my-data-tools
```

Creates a data-centric package with:
- Excel/CSV import/export
- Database connectivity
- Data validation utilities
- Report generation

## 🔧 Configuration Customization

Customize your development experience by editing `~/.revitpy/config.toml`:

```toml
[development]
# Auto-reload packages during development
hot_reload = true

# Default template for new packages
default_template = "basic-script"

# Automatically run tests after build
auto_test = true

[ui]
# Terminal color theme
theme = "dark"  # or "light"

# Progress bars and animations
animations = true

# Rich terminal formatting
rich_output = true
```

## 🚨 Troubleshooting Quick Fixes

### Package Not Found
```bash
# Update package index
revitpy-install update

# Check spelling and search
revitpy-install search PACKAGE_NAME
```

### Import Errors
```bash  
# Verify environment is activated
revitpy-install env current

# Reinstall package
revitpy-install uninstall PACKAGE_NAME
revitpy-install install PACKAGE_NAME
```

### Build Failures
```bash
# Check package structure
revitpy-build validate .

# Clean build artifacts
rm -rf build/ dist/ *.egg-info/
revitpy-build package --source .
```

## ✨ Pro Tips

!!! tip "Development Workflow"
    1. **Always use virtual environments** - keeps projects isolated
    2. **Pin dependency versions** in production packages
    3. **Write tests first** - ensures code quality from the start
    4. **Use meaningful package names** - makes discovery easier

!!! tip "Performance"
    - Use `--parallel` flag for faster multi-package installations
    - Enable package caching to reduce download times
    - Use `--offline` mode when internet is unavailable

!!! tip "Collaboration"
    - Share `requirements.txt` files with your team
    - Use lock files (`revitpy.lock`) for reproducible builds
    - Document your package APIs with docstrings

## 🎯 Next Steps

Now that you've mastered the basics:

1. **[Build Your First Extension](first-extension.md)** - Create a complete Revit extension with UI
2. **[Development Setup](development-setup.md)** - Configure your IDE for maximum productivity  
3. **[Basic Scripting Tutorial](../tutorials/basic-scripting.md)** - Deep dive into RevitPy scripting
4. **[Package Management Tutorial](../tutorials/package-management.md)** - Advanced package management techniques

## 🤝 Need Help?

- 📖 [Full Tutorial Series](../tutorials/index.md)
- 🔍 [Troubleshooting Guide](../guides/troubleshooting.md)
- 💬 [Community Forum](https://forum.revitpy.dev)
- 💭 [Discord Chat](https://discord.gg/revitpy)

**Happy coding with RevitPy! 🎉**