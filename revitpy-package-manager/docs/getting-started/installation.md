# Installation Guide

This guide will help you install RevitPy Package Manager and get it configured for your development environment.

## System Requirements

### Minimum Requirements
- **Autodesk Revit**: 2021 or later
- **Python**: 3.11+ (Python 3.11 or 3.12 recommended)
- **Operating System**: Windows 10/11 (64-bit)
- **RAM**: 8GB minimum, 16GB recommended
- **Disk Space**: 2GB free space for package cache

### Supported Revit Versions
- Autodesk Revit 2021 ✅
- Autodesk Revit 2022 ✅
- Autodesk Revit 2023 ✅
- Autodesk Revit 2024 ✅
- Autodesk Revit 2025 ✅

## Installation Methods

=== "Method 1: PyPI (Recommended)"

    Install the latest stable release from PyPI:

    ```bash
    # Install RevitPy Package Manager
    pip install revitpy-package-manager

    # Verify installation
    revitpy-install --version
    ```

=== "Method 2: From Source"

    Install the latest development version:

    ```bash
    # Clone the repository
    git clone https://github.com/highvelocitysolutions/revitpy.git
    cd revitpy/revitpy-package-manager

    # Install in development mode
    pip install -e .

    # Verify installation
    revitpy-install --version
    ```

=== "Method 3: Binary Installer"

    Download the pre-built installer:

    1. Visit [releases page](https://github.com/highvelocitysolutions/revitpy/releases)
    2. Download `revitpy-package-manager-installer.exe`
    3. Run the installer with administrator privileges
    4. Follow the setup wizard

## Initial Configuration

After installation, configure RevitPy Package Manager:

### 1. Initialize Configuration

```bash
# Create initial configuration
revitpy-install init

# This creates ~/.revitpy/config.toml with default settings
```

### 2. Configure Registry Settings

Edit `~/.revitpy/config.toml`:

```toml
[registry]
# Default public registry
url = "https://registry.revitpy.dev"
timeout = 30
verify_ssl = true

[security]
# Enable package signature verification
verify_signatures = true
scan_vulnerabilities = true
trust_pypi = false

[installer]
# Package cache settings
cache_dir = "~/.revitpy/cache"
max_cache_size = "1GB"
parallel_downloads = 4

[environments]
# Virtual environment settings
base_dir = "~/.revitpy/envs"
python_version = "3.11"
```

### 3. Verify Revit Integration

Check that RevitPy can detect your Revit installations:

```bash
# List detected Revit versions
revitpy-install revit list

# Expected output:
# Found Revit installations:
# - Revit 2024: C:\Program Files\Autodesk\Revit 2024\Revit.exe
# - Revit 2025: C:\Program Files\Autodesk\Revit 2025\Revit.exe
```

## Environment Setup

### Create Your First Environment

Virtual environments keep your projects isolated and conflict-free:

```bash
# Create a new environment for Revit 2024
revitpy-install env create my-first-project --revit-version 2024

# Activate the environment
revitpy-install env activate my-first-project

# List available environments
revitpy-install env list
```

### Install Core Packages

Install essential packages for Revit development:

```bash
# Install core RevitPy framework
revitpy-install install revitpy-core

# Install common utilities
revitpy-install install revitpy-geometry revitpy-ui

# List installed packages
revitpy-install list
```

## Verification

Verify your installation is working correctly:

### 1. Command Line Tools

Test all CLI commands are available:

```bash
# Package manager
revitpy-install --help

# Package builder
revitpy-build --help

# Registry server (for development)
revitpy-registry --help
```

### 2. Python Import Test

Test Python integration:

```python
# test_installation.py
try:
    import revitpy_package_manager
    print(f"✅ RevitPy Package Manager v{revitpy_package_manager.__version__}")

    from revitpy_package_manager.installer import resolver
    print("✅ Dependency resolver available")

    from revitpy_package_manager.builder import validator
    print("✅ Package validator available")

    print("🎉 Installation successful!")

except ImportError as e:
    print(f"❌ Installation issue: {e}")
```

Run the test:

```bash
python test_installation.py
```

### 3. Registry Connection Test

Verify connectivity to the package registry:

```bash
# Test registry connection
revitpy-install search revitpy

# Should return available packages
```

## Troubleshooting Common Issues

### Python Version Issues

!!! warning "Python 3.11+ Required"
    RevitPy requires Python 3.11 or later. Check your version:

    ```bash
    python --version  # Should show 3.11.x or higher
    ```

If you have an older Python version:

1. Download Python 3.11+ from [python.org](https://www.python.org/downloads/)
2. Install with "Add to PATH" option enabled
3. Restart your command prompt
4. Verify: `python --version`

### Permission Issues

If you get permission errors during installation:

=== "Windows"

    ```bash
    # Run command prompt as Administrator
    # Then install:
    pip install --user revitpy-package-manager
    ```

=== "Alternative"

    ```bash
    # Use virtual environment (recommended)
    python -m venv revitpy-env
    revitpy-env\Scripts\activate
    pip install revitpy-package-manager
    ```

### Revit Detection Issues

If RevitPy can't find your Revit installation:

1. **Check installation paths**: Ensure Revit is installed in standard locations
2. **Manual configuration**: Edit config file to specify paths:

```toml
[revit]
installations = [
    {version = "2024", path = "C:\\Program Files\\Autodesk\\Revit 2024\\Revit.exe"},
    {version = "2025", path = "C:\\Program Files\\Autodesk\\Revit 2025\\Revit.exe"}
]
```

### Network/Firewall Issues

If you can't connect to the registry:

1. **Check firewall**: Ensure ports 80 and 443 are open
2. **Proxy settings**: Configure proxy if needed:

```toml
[network]
proxy_http = "http://proxy.company.com:8080"
proxy_https = "https://proxy.company.com:8080"
```

3. **Corporate networks**: May need to add registry.revitpy.dev to allowlist

## Next Steps

Great! Now that RevitPy Package Manager is installed:

1. **[Quick Start](quickstart.md)** - Create your first package in 5 minutes
2. **[Development Setup](development-setup.md)** - Configure your IDE and tools
3. **[Basic Scripting Tutorial](../tutorials/basic-scripting.md)** - Learn the fundamentals

## Need More Help?

- 📖 [Troubleshooting Guide](../guides/troubleshooting.md)
- 💬 [Community Forum](https://forum.revitpy.dev)
- 💭 [Discord Chat](https://discord.gg/revitpy)
- 📧 [Email Support](mailto:support@revitpy.dev)
