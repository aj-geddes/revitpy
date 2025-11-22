"""Pytest configuration for builder/publisher tests (standalone)."""

import pytest

# This is a minimal conftest that doesn't import the full API
# to avoid SQLAlchemy issues when testing CLI functionality


@pytest.fixture
def cli_test_marker():
    """Marker for CLI tests that don't need database."""
    return True
