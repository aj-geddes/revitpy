# RevitPy Desktop Package Registry

A simplified, high-performance package registry optimized for desktop framework distribution rather than web service deployment.

## Overview

This refactored package registry has been optimized specifically for desktop development workflows with RevitPy. It removes unnecessary microservices complexity and focuses on fast package distribution, offline capabilities, and seamless CLI integration.

## Key Features

### 🖥️ Desktop-Optimized Architecture
- **Single web application** instead of microservices
- **SQLite database** for minimal infrastructure requirements
- **File-based storage** with optional CDN support
- **Simplified deployment** with Docker or standalone

### 📦 Enhanced Package Format (.rpyx)
- **RevitPy-specific package format** optimized for desktop add-ins
- **Comprehensive metadata** including Revit version compatibility
- **Security scanning** built into package validation
- **Performance impact assessment** for desktop execution

### ⚡ Offline Development Support
- **Client-side caching** with 90%+ cache hit rate target
- **Offline package search** using cached metadata
- **Background synchronization** with registry
- **Smart cache management** with automatic cleanup

### 🔒 Desktop Security Focus
- **Package security scanning** for .rpyx files
- **Revit-specific validation** for desktop execution
- **Digital signature support** for package verification
- **Performance impact assessment** before installation

### 🚀 Performance Optimizations
- **<2 second search response** time target
- **Bulk package operations** for faster workflows
- **Compression and bundling** optimizations
- **CDN-ready static file serving**

## Architecture Comparison

### Before (Microservices)
```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   Registry  │  │   Storage   │  │  Monitoring │
│   Service   │  │   Service   │  │   Service   │
└─────────────┘  └─────────────┘  └─────────────┘
       │                 │                 │
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ PostgreSQL  │  │   MinIO/S3  │  │ Prometheus  │
│  Database   │  │   Storage   │  │  + Grafana  │
└─────────────┘  └─────────────┘  └─────────────┘
```

### After (Desktop-Optimized)
```
┌─────────────────────────────────────────────┐
│         Desktop Registry Service            │
│  ┌─────────────┐  ┌─────────────┐          │
│  │   FastAPI   │  │   SQLite    │          │
│  │    App      │  │  Database   │          │
│  └─────────────┘  └─────────────┘          │
└─────────────────────────────────────────────┘
                     │
┌─────────────────────────────────────────────┐
│           Client-Side Cache                 │
│  ┌─────────────┐  ┌─────────────┐          │
│  │  Package    │  │  Metadata   │          │
│  │   Cache     │  │    Cache    │          │
│  └─────────────┘  └─────────────┘          │
└─────────────────────────────────────────────┘
```

## Installation

### Quick Start (Docker)
```bash
# Clone the repository
git clone <repository-url>
cd revitpy-package-manager

# Start with simplified Docker Compose
docker-compose -f docker-compose.desktop.yml up -d

# Registry will be available at http://localhost:8000
```

### Standalone Installation
```bash
# Install dependencies
pip install -r requirements.desktop.txt

# Run the registry
python scripts/desktop_entrypoint.py
```

## Usage

### CLI Commands

The desktop registry integrates seamlessly with the RevitPy CLI:

```bash
# Search for packages
revitpy-install registry search "geometry" --revit-version 2024

# Install a package with compatibility check
revitpy-install registry install my-addon --revit-version 2024

# Build a package from source
revitpy-install registry build ./my-addon-source --output my-addon-1.0.0.rpyx

# Sync registry for offline use
revitpy-install registry sync

# Validate a package
revitpy-install registry validate my-addon-1.0.0.rpyx --security-scan

# Manage cache
revitpy-install registry cache --stats
revitpy-install registry cache --cleanup --max-size 500
```

### API Endpoints

The registry provides optimized REST endpoints:

```
GET /api/packages/search?q=geometry&revit_version=2024
GET /api/packages/{package_name}
GET /api/packages/{package_name}/compatibility
GET /api/packages/{package_name}/{version}/download
POST /api/packages/upload
GET /api/stats
```

### Package Format (.rpyx)

Create packages optimized for desktop distribution:

```python
# Build a package
from revitpy_package_manager.builder.rpyx_format import RPYXBuilder

builder = RPYXBuilder("./my-addon-source")
builder.load_manifest()  # From revitpy.toml or pyproject.toml
build_info = builder.build_package("my-addon-1.0.0.rpyx")
```

Example manifest (revitpy.toml):
```toml
[package]
name = "my-revit-addon"
version = "1.0.0"
description = "A sample RevitPy add-in"
author = "Developer Name"
license = "MIT"

[package.revit_compatibility]
min_version = "2022"
tested_versions = ["2022", "2023", "2024"]

[package.desktop]
package_type = "addon"
performance_impact = "low"
requires_admin = false
```

## Performance Targets

The desktop registry is optimized for these performance characteristics:

- **Search Response Time**: <2 seconds for typical queries
- **Cache Hit Rate**: 90%+ for repeated package access
- **Package Install Time**: <30 seconds for typical packages
- **Offline Operation**: Full functionality without internet
- **Memory Usage**: <100MB base footprint
- **Storage Efficiency**: 60%+ compression for packages

## Security

### Package Security Scanning

All packages undergo security scanning:

```python
from revitpy_package_manager.security.desktop_scanner import SecurityScanner

scanner = SecurityScanner()
result = await scanner.scan_package_file("package.rpyx")

if not result.is_safe:
    print(f"Security issues: {result.issues}")
```

### Security Features

- **Automated scanning** for malicious code patterns
- **Revit API validation** for desktop compatibility
- **Digital signature verification** (when available)
- **Network access detection** for transparency
- **File system operation analysis** for safety

## Deployment

### Production Deployment

```bash
# With Nginx (recommended for production)
docker-compose -f docker-compose.desktop.yml --profile production up -d

# Direct deployment
export JWT_SECRET_KEY="your-secret-key"
export ADMIN_TOKEN="your-admin-token"
python scripts/desktop_entrypoint.py
```

### Configuration Options

```bash
# Environment variables
DATABASE_URL=sqlite:///data/registry.db
STORAGE_TYPE=file
STORAGE_PATH=/data/packages
REDIS_URL=redis://localhost:6379/0  # Optional
LOG_LEVEL=INFO
JWT_SECRET_KEY=your-secret-key
```

## Migration from Microservices

To migrate from the existing microservices architecture:

1. **Export existing data** from PostgreSQL
2. **Convert to SQLite** using provided migration scripts
3. **Update client configurations** to point to new registry
4. **Test package operations** with the new system
5. **Decommission old services** once migration is verified

## Development

### Project Structure

```
revitpy_package_manager/
├── registry/
│   ├── desktop_registry.py    # Main registry application
│   └── api/                   # Original API (legacy)
├── installer/
│   ├── cache_manager.py       # Client-side caching
│   └── cli/
│       ├── desktop_cli.py     # Desktop CLI commands
│       └── main.py            # Main CLI entry point
├── builder/
│   └── rpyx_format.py         # .rpyx package format
├── security/
│   └── desktop_scanner.py     # Security scanning
└── scripts/
    └── desktop_entrypoint.py  # Docker entrypoint
```

### Adding New Features

1. **Registry Features**: Add to `desktop_registry.py`
2. **CLI Commands**: Add to `desktop_cli.py`
3. **Package Validation**: Extend `rpyx_format.py`
4. **Security Rules**: Update `desktop_scanner.py`
5. **Caching**: Modify `cache_manager.py`

## Monitoring

### Health Checks

```bash
# Check registry health
curl http://localhost:8000/api/stats

# Check cache status
revitpy-install registry cache --stats
```

### Metrics

The simplified registry provides essential metrics:
- Package download counts
- Search performance
- Cache hit rates
- Error rates
- Security scan results

## Troubleshooting

### Common Issues

1. **Slow search performance**
   ```bash
   # Rebuild search indexes
   revitpy-install registry sync --rebuild-index
   ```

2. **Cache corruption**
   ```bash
   # Clear and rebuild cache
   revitpy-install registry cache --cleanup --max-age 0
   revitpy-install registry sync
   ```

3. **Package compatibility issues**
   ```bash
   # Validate package compatibility
   revitpy-install registry validate package.rpyx --revit-version 2024
   ```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

---

**Note**: This desktop-optimized registry replaces the complex microservices architecture with a focused solution for RevitPy desktop development. For web-scale deployments, consider the original microservices architecture.