"""Pytest configuration for installer tests.

This conftest is separate from the main conftest to avoid importing
database dependencies that aren't needed for installer-only tests.
"""

import pytest


@pytest.fixture
def installer_test():
    """Marker that indicates this is an installer-only test."""
    return True
