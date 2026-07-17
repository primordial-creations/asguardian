"""
Heimdall Test Configuration

Shared pytest configuration and fixtures for all Heimdall tests.
"""

import os
import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "requires_filesystem: marks tests that require filesystem access"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""
    for item in items:
        # Add integration marker to L1 tests
        if "L1_Integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(params=["regex", "ast"])
def dual_engine_mode(request, monkeypatch):
    """Dual-engine fixture: run a test under both scanning engines.

    - "regex": forces ``ast_engine.TS_AVAILABLE = False`` so the regex
      implementations run even when tree-sitter is installed.
    - "ast": skips when the optional tree-sitter extra is not installed.
    """
    from Asgard.Heimdall.treesitter import ast_engine

    if request.param == "ast":
        if not ast_engine.is_engine_enabled("python"):
            pytest.skip("tree-sitter not installed — AST engine unavailable")
    else:
        monkeypatch.setattr(ast_engine, "TS_AVAILABLE", False)
    return request.param


@pytest.fixture(scope="session")
def project_root():
    """Return the project root directory."""
    return Path(__file__).parent.parent.parent


@pytest.fixture(scope="session")
def heimdall_root():
    """Return the Heimdall package root directory."""
    return Path(__file__).parent.parent
