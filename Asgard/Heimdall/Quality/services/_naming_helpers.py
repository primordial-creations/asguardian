import ast
import re
from typing import List

from Asgard.Heimdall.Quality.models.naming_models import (
    NamingConfig,
    NamingConvention,
    NamingViolation,
)

# Regex patterns for naming conventions
_RE_SNAKE_CASE = re.compile(r"^_*[a-z][a-z0-9_]*$|^_+$")
_RE_PASCAL_CASE = re.compile(r"^_*[A-Z][a-zA-Z0-9]*$")
_RE_UPPER_CASE = re.compile(r"^_*[A-Z][A-Z0-9_]*$")
_RE_TYPE_ALIAS = re.compile(r"^[A-Z][A-Z0-9]?$|^T_[A-Z]|^TypeVar")


def _is_snake_case(name: str) -> bool:
    """Return True if name follows snake_case convention."""
    return bool(_RE_SNAKE_CASE.match(name))


def _is_pascal_case(name: str) -> bool:
    """Return True if name follows PascalCase convention."""
    return bool(_RE_PASCAL_CASE.match(name))


def _is_upper_case(name: str) -> bool:
    """Return True if name follows UPPER_CASE convention."""
    return bool(_RE_UPPER_CASE.match(name))


def _is_dunder(name: str) -> bool:
    """Return True if name is a dunder (double underscore on both sides)."""
    return name.startswith("__") and name.endswith("__")


def _is_type_alias(name: str) -> bool:
    """Return True if name looks like a type alias (single uppercase letter, etc.)."""
    return bool(_RE_TYPE_ALIAS.match(name))


def _looks_like_constant(name: str) -> bool:
    """
    Determine whether a module-level assignment target looks like a constant.

    A name is treated as a constant if it is entirely uppercase (with optional
    underscores and digits), indicating an intentional constant per PEP 8.
    """
    return bool(re.match(r"^[A-Z][A-Z0-9_]*$", name))


def check_assignment_name(
    name: str,
    line_number: int,
    file_path: str,
    violations: List[NamingViolation],
    config: NamingConfig,
) -> None:
    """Check a single assignment target name against naming rules."""
    if name in config.allow_list:
        return

    if _is_dunder(name):
        return

    if _is_type_alias(name):
        return

    if _looks_like_constant(name):
        if config.check_constants and not _is_upper_case(name):
            violations.append(NamingViolation(
                file_path=file_path,
                line_number=line_number,
                element_type="constant",
                element_name=name,
                expected_convention=NamingConvention.UPPER_CASE,
                description=f"Constant '{name}' does not follow UPPER_CASE convention",
            ))
    else:
        if config.check_variables and not _is_snake_case(name):
            violations.append(NamingViolation(
                file_path=file_path,
                line_number=line_number,
                element_type="variable",
                element_name=name,
                expected_convention=NamingConvention.SNAKE_CASE,
                description=f"Variable '{name}' does not follow snake_case convention",
            ))


def check_module_assignment(
    node: ast.Assign,
    file_path: str,
    violations: List[NamingViolation],
    config: NamingConfig,
) -> None:
    """Check module-level assignment targets for naming compliance."""
    for target in node.targets:
        if isinstance(target, ast.Name):
            check_assignment_name(
                target.id, target.lineno if hasattr(target, 'lineno') else node.lineno,
                file_path, violations, config
            )


def check_ann_assignment(
    node: ast.AnnAssign,
    file_path: str,
    violations: List[NamingViolation],
    config: NamingConfig,
) -> None:
    """Check annotated module-level assignment targets for naming compliance."""
    target = node.target
    if isinstance(target, ast.Name):
        check_assignment_name(
            target.id, target.lineno if hasattr(target, 'lineno') else node.lineno,
            file_path, violations, config
        )
