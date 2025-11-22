"""Pytest configuration for registry/API tests.

This conftest is separate from the main conftest to provide isolated
test fixtures for statistics and API tests.
"""

import pytest


@pytest.fixture
def registry_test():
    """Marker that indicates this is a registry/API test."""
    return True
