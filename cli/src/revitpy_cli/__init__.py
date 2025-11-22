"""RevitPy CLI - Professional Development Tools for RevitPy Framework.

A comprehensive command-line interface that provides scaffolding, building,
development server, and package management capabilities for RevitPy projects.
"""

from importlib import metadata

try:
    __version__ = metadata.version("revitpy-cli")
except metadata.PackageNotFoundError:
    __version__ = "0.1.0"

__all__ = ["__version__"]
