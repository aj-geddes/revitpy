"""Pytest configuration for builder/publisher tests.

This conftest is separate from the main conftest to avoid importing
database dependencies that aren't needed for CLI-only tests.
"""

import pytest


@pytest.fixture
def cli_test():
    """Marker that indicates this is a CLI-only test."""
    return True
