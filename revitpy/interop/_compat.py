"""
Compatibility layer for optional Speckle dependencies.

This module handles the optional specklepy dependency, providing
clear error messages when it is not installed.
"""

from __future__ import annotations

try:
    import specklepy  # noqa: F401

    _HAS_SPECKLEPY = True
except ImportError:
    _HAS_SPECKLEPY = False


def require_specklepy() -> None:
    """Raise ImportError if specklepy is not installed.

    Raises:
        ImportError: If specklepy is not available.
    """
    if not _HAS_SPECKLEPY:
        raise ImportError(
            "specklepy is required for Speckle operations. "
            "Install it with: pip install revitpy[interop]"
        )
