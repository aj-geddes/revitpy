# RevitPy Package Manager API Documentation

This directory contains comprehensive API documentation for the RevitPy Package Manager system.

## Overview

The RevitPy Package Manager provides a complete package management solution with the following components:

- **Registry API**: REST API for package metadata, user management, and downloads
- **Package Installer**: Command-line tool for managing packages and environments
- **Package Builder**: Tools for creating, validating, and publishing packages
- **Security System**: Package signing, verification, and vulnerability scanning

## API Documentation Structure

```
docs/api/
├── README.md                 # This file
├── registry/                 # Registry API documentation
│   ├── authentication.md    # Auth endpoints and flows
│   ├── packages.md          # Package management endpoints
│   ├── users.md            # User management endpoints
│   ├── admin.md            # Administrative endpoints
│   └── schemas.md          # Request/response schemas
├── installer/               # Installer CLI documentation
│   ├── commands.md         # CLI command reference
│   ├── configuration.md    # Configuration options
│   └── examples.md         # Usage examples
├── builder/                # Builder tools documentation
│   ├── validation.md       # Package validation rules
│   ├── signing.md          # Package signing process
│   └── publishing.md       # Publishing workflow
└── examples/               # Complete API examples
    ├── python-client.md    # Python client examples
    ├── curl-examples.md    # cURL command examples
    └── workflows.md        # Common workflows
```

## Quick Start

### 1. Registry API

The registry provides a RESTful API for package management:

**Base URL**: `https://registry.revitpy.dev/api/v1`

**Authentication**: Bearer token (JWT)

```bash
# Get package list
curl https://registry.revitpy.dev/api/v1/packages/

# Search packages
curl "https://registry.revitpy.dev/api/v1/packages/search?q=geometry"

# Get package details
curl https://registry.revitpy.dev/api/v1/packages/revitpy-geometry
```

### 2. Package Installer

Install and manage RevitPy packages:

```bash
# Install the package manager
pip install revitpy-package-manager

# Create a new environment
revitpy-install env create myproject --python-version 3.11 --revit-version 2025

# Install packages
revitpy-install install revitpy-geometry --environment myproject

# List installed packages
revitpy-install list --environment myproject
```

### 3. Package Builder

Build and publish packages:

```bash
# Validate a package
revitpy-build validate ./my-package/

# Build a package
revitpy-build build ./my-package/ --output-dir ./dist/

# Sign a package
revitpy-build sign ./dist/my-package-1.0.0.tar.gz --key ./signing-key.pem

# Publish to registry
revitpy-build publish ./dist/my-package-1.0.0.tar.gz --token <your-token>
```

## Core Concepts

### Package Metadata

RevitPy packages include comprehensive metadata:

```toml
[project]
name = "my-revitpy-package"
version = "1.0.0"
description = "A sample RevitPy package"
authors = [{name = "Your Name", email = "you@example.com"}]
license = {text = "MIT"}
requires-python = ">=3.11"
dependencies = [
    "revitpy-core>=1.0.0",
    "numpy>=1.21.0"
]

[project.urls]
Homepage = "https://github.com/you/my-revitpy-package"
Repository = "https://github.com/you/my-revitpy-package"
Documentation = "https://my-revitpy-package.readthedocs.io"

# RevitPy-specific metadata
[revitpy]
supported_revit_versions = ["2024", "2025"]
entry_points = {commands = ["my_command = my_package.commands:main_command"]}
categories = ["geometry", "utilities"]

[revitpy.dependencies.optional]
dev = ["pytest>=6.0", "black>=22.0"]
extra_features = ["matplotlib>=3.5.0"]
```

### Version Compatibility

The package manager handles complex version compatibility:

- **Python Version**: Supports Python 3.11+
- **Revit Version**: Per-package Revit version compatibility
- **Dependency Constraints**: Full PEP 508 version specifiers
- **Optional Dependencies**: Extra features and development dependencies

### Security Features

Comprehensive security system:

- **Package Signing**: Ed25519 or RSA-PSS digital signatures
- **Vulnerability Scanning**: Automated security scanning
- **Dependency Analysis**: Check for vulnerable dependencies
- **Code Analysis**: Static analysis for security issues
- **Trusted Publishers**: Verified package sources

## API Endpoints Overview

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Authenticate user
- `GET /api/v1/auth/me` - Get current user info
- `POST /api/v1/auth/refresh` - Refresh access token

### Packages
- `GET /api/v1/packages/` - List packages
- `GET /api/v1/packages/search` - Search packages
- `GET /api/v1/packages/{name}` - Get package details
- `POST /api/v1/packages/` - Create new package
- `PUT /api/v1/packages/{name}` - Update package
- `DELETE /api/v1/packages/{name}` - Delete package

### Package Versions
- `GET /api/v1/packages/{name}/versions` - List package versions
- `POST /api/v1/packages/{name}/versions` - Upload new version
- `GET /api/v1/packages/{name}/versions/{version}` - Get version details

### Users
- `GET /api/v1/users/me` - Get user profile
- `PUT /api/v1/users/me` - Update user profile
- `GET /api/v1/users/{username}` - Get public user profile
- `GET /api/v1/users/me/api-keys` - List API keys
- `POST /api/v1/users/me/api-keys` - Create API key
- `DELETE /api/v1/users/me/api-keys/{id}` - Delete API key

### Health and Monitoring
- `GET /api/v1/health/` - Health check
- `GET /api/v1/health/ready` - Readiness probe
- `GET /api/v1/health/live` - Liveness probe
- `GET /metrics` - Prometheus metrics

## Response Formats

All API responses use consistent JSON formatting:

### Success Response
```json
{
  "id": "uuid",
  "name": "package-name",
  "version": "1.0.0",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Error Response
```json
{
  "error": "validation_error",
  "message": "Invalid package name format",
  "details": {
    "field": "name",
    "code": "invalid_format"
  }
}
```

### List Response
```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "per_page": 20,
  "has_next": true,
  "has_prev": false
}
```

## Rate Limiting

API endpoints are rate-limited to ensure fair usage:

- **Authenticated users**: 1000 requests/hour
- **Unauthenticated users**: 100 requests/hour
- **Package uploads**: 50 uploads/day per user
- **Search queries**: 500 searches/hour

Rate limit headers:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1609459200
```

## Error Codes

Standard HTTP status codes with specific error codes:

### 4xx Client Errors
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `409 Conflict`: Resource already exists
- `422 Unprocessable Entity`: Validation errors
- `429 Too Many Requests`: Rate limit exceeded

### 5xx Server Errors
- `500 Internal Server Error`: Unexpected server error
- `502 Bad Gateway`: Upstream service error
- `503 Service Unavailable`: Temporary service outage

## SDKs and Libraries

### Python SDK
```python
from revitpy_package_manager import RegistryClient

client = RegistryClient("https://registry.revitpy.dev")
client.authenticate("username", "password")

# Search packages
packages = client.search("geometry")

# Install package
client.install("revitpy-geometry", environment="myproject")
```

### JavaScript/TypeScript SDK
```typescript
import { RevitPyRegistryClient } from '@revitpy/registry-client';

const client = new RevitPyRegistryClient('https://registry.revitpy.dev');
await client.authenticate('username', 'password');

// Get package info
const package = await client.getPackage('revitpy-geometry');
```

## Best Practices

### Package Development
1. **Follow semantic versioning** (SemVer)
2. **Include comprehensive metadata** in pyproject.toml
3. **Write good documentation** and examples
4. **Add tests** for your package functionality
5. **Use type hints** for better development experience

### API Usage
1. **Use API keys** for programmatic access
2. **Implement exponential backoff** for retries
3. **Cache responses** when appropriate
4. **Handle rate limits** gracefully
5. **Validate responses** on the client side

### Security
1. **Keep API keys secure** and rotate them regularly
2. **Verify package signatures** before installation
3. **Review dependencies** for security issues
4. **Use HTTPS** for all API communications
5. **Report security issues** responsibly

## Support and Resources

- **API Documentation**: https://docs.revitpy.dev/api/
- **Community Forum**: https://forum.revitpy.dev/
- **Discord**: https://discord.gg/revitpy
- **GitHub Issues**: https://github.com/highvelocitysolutions/revitpy/issues
- **Email Support**: support@revitpy.dev

## Contributing

We welcome contributions to the RevitPy Package Manager:

1. **Report bugs** and feature requests
2. **Submit pull requests** for improvements
3. **Write documentation** and examples
4. **Share packages** with the community
5. **Provide feedback** on the API design

See our [Contributing Guide](https://github.com/highvelocitysolutions/revitpy/blob/main/CONTRIBUTING.md) for more details.

---

*Last updated: January 2024*
