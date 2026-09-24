"""
Compatibility layer for optional Speckle dependencies.

This module handles the optional specklepy dependency, providing
clear error messages when it is not installed, plus small helpers for
the legacy stream/branch/commit -> project/model/version renames.
"""

from __future__ import annotations

import warnings

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


def warn_deprecated(old: str, new: str, *, stacklevel: int = 3) -> None:
    """Emit a ``DeprecationWarning`` for a renamed argument or method."""
    warnings.warn(
        f"'{old}' is deprecated; use '{new}' instead "
        "(Speckle renamed streams/branches/commits to "
        "projects/models/versions).",
        DeprecationWarning,
        stacklevel=stacklevel,
    )


def resolve_renamed(
    new_value: str | None,
    old_value: str | None,
    *,
    new_name: str,
    old_name: str,
    default: str | None = None,
) -> str:
    """Resolve a value that may be passed under its new or legacy name.

    Args:
        new_value: Value passed under the current name.
        old_value: Value passed under the deprecated name.
        new_name: Current argument name (for messages).
        old_name: Deprecated argument name (for messages).
        default: Fallback when neither value is supplied.

    Returns:
        The resolved value.

    Raises:
        TypeError: If both names are supplied, or neither is supplied
            and there is no default.
    """
    if old_value is not None:
        if new_value is not None:
            raise TypeError(f"Pass either '{new_name}' or '{old_name}', not both")
        warn_deprecated(old_name, new_name, stacklevel=4)
        return old_value
    if new_value is not None:
        return new_value
    if default is not None:
        return default
    raise TypeError(f"Missing required argument: '{new_name}'")
