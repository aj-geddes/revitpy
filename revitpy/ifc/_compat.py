"""
Compatibility layer for optional IFC dependencies.

This module handles the optional ifcopenshell dependency, providing
clear error messages when it is not installed and version checking
utilities.
"""

from __future__ import annotations

try:
    import ifcopenshell

    _HAS_IFCOPENSHELL = True
except ImportError:
    _HAS_IFCOPENSHELL = False
    ifcopenshell = None  # type: ignore[assignment]


def require_ifcopenshell() -> None:
    """Raise ImportError if ifcopenshell is not installed.

    Raises:
        ImportError: If ifcopenshell is not available.
    """
    if not _HAS_IFCOPENSHELL:
        raise ImportError(
            "ifcopenshell is required for IFC operations. "
            "Install it with: pip install revitpy[ifc]"
        )


def get_ifcopenshell_version() -> str | None:
    """Return the installed ifcopenshell version, or None if not installed."""
    if not _HAS_IFCOPENSHELL:
        return None
    return getattr(ifcopenshell, "version", "unknown")


def check_ifcopenshell_version(minimum: str = "0.7.0") -> bool:
    """Check whether the installed ifcopenshell meets the minimum version.

    Args:
        minimum: Minimum required version string (e.g. ``"0.7.0"``).

    Returns:
        True if the installed version is sufficient, False otherwise.
    """
    if not _HAS_IFCOPENSHELL:
        return False

    installed = get_ifcopenshell_version()
    if installed is None or installed == "unknown":
        # Cannot determine version; assume it is sufficient.
        return True

    try:
        installed_parts = [int(p) for p in str(installed).split(".")]
        minimum_parts = [int(p) for p in minimum.split(".")]
        return installed_parts >= minimum_parts
    except (ValueError, AttributeError):
        return True
