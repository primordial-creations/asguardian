"""
Heimdall Init Module

Provides linter initialization for new projects.
Generates configuration files for Ruff, MyPy, ESLint, Prettier,
and pre-commit hooks based on GAIA coding standards.
"""

from Asgard.Shared.Init.linter_initializer import LinterInitializer

__all__ = ["LinterInitializer"]
