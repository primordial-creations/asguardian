"""
Heimdall Hexagonal Architecture — Anemic Domain Model & Infrastructure Leak

Per ``_Docs/Planning/Heimdall/03_Architecture_Enforcement.md`` §4, these are
the two hexagonal anti-pattern detectors not yet implemented alongside
Missing Ports (``_generic_hexagonal_checks.py`` / ``_hexagonal_validators.py``):

- **Anemic Domain Model**: a domain-zone class that is pure data (has
  fields) but exposes no behaviour — every method is a constructor,
  dunder, or trivial accessor/mutator. This is the classic "domain model
  as bag of getters/setters" smell: business logic has leaked into
  services, leaving the entity anemic.
- **Infrastructure Leak**: a domain-zone class whose *declaration itself*
  (base classes, decorators, or class-body calls) binds it to a specific
  persistence/web framework (SQLAlchemy declarative models, Django ORM
  models, JPA-style ``@Entity``/``@Table``/``@Column`` annotations). This is
  distinct from ``check_domain_imports_infrastructure`` (which flags the
  *import* statement) — a class can leak infrastructure via inheritance or
  decoration even when the import itself is aliased or wildcarded.

Python-only for now (AST-based, consistent with the rest of the Python
zone-assignment/domain-isolation checks in this package); CIR-based
multi-language support is a natural follow-up once the anti-pattern
signatures are ported into ``evaluators/``.
"""

import ast
from pathlib import Path
from typing import Dict, List

from Asgard.Bragi.Architecture.models.architecture_models import (
    HexagonalViolation,
    HexagonalZone,
    ViolationSeverity,
)
from Asgard.Bragi.Architecture.utilities.ast_utils import (
    extract_classes,
    get_class_bases,
    get_class_decorators,
    get_class_methods,
)
from Asgard.Bragi.Quality.utilities.file_utils import scan_directory

_TRIVIAL_METHOD_NAMES = frozenset({
    "__init__", "__repr__", "__eq__", "__hash__", "__str__", "__lt__",
    "__le__", "__gt__", "__ge__", "__ne__", "__post_init__",
})

_ORM_BASE_NAMES = frozenset({
    "Model", "Base", "declarative_base", "Document", "EmbeddedDocument",
})
_ORM_DECORATOR_NAMES = frozenset({"Entity", "Table", "Document", "dataclass_json"})
_ORM_COLUMN_CALL_NAMES = frozenset({"Column", "relationship", "ForeignKey", "mapped_column"})


def _is_trivial_accessor(method: ast.FunctionDef) -> bool:
    """A getter/setter that does nothing but read/write a single attribute,
    or a bare ``pass``/docstring-only stub."""
    body = [
        s for s in method.body
        if not (isinstance(s, ast.Expr) and isinstance(getattr(s, "value", None), ast.Constant))
    ]
    if not body or all(isinstance(s, ast.Pass) for s in body):
        return True
    if len(body) == 1:
        stmt = body[0]
        # return self.x
        if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Attribute):
            if isinstance(stmt.value.value, ast.Name) and stmt.value.value.id == "self":
                return True
        # self.x = value  (setter)
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            tgt = stmt.targets[0]
            if isinstance(tgt, ast.Attribute) and isinstance(tgt.value, ast.Name) and tgt.value.id == "self":
                return True
    return False


def _has_fields(cls: ast.ClassDef) -> bool:
    for node in ast.walk(cls):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self":
                    return True
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Attribute):
            if isinstance(node.target.value, ast.Name) and node.target.value.id == "self":
                return True
    return False


def detect_anemic_domain_models(
    root_path: Path,
    zone_assignments: Dict[str, str],
    exclude_patterns: List[str],
    include_extensions: List[str],
    path_to_module_fn,
) -> List[HexagonalViolation]:
    """Flag domain-zone classes that hold data but expose no behaviour."""
    violations: List[HexagonalViolation] = []

    for file_path in scan_directory(root_path, exclude_patterns=exclude_patterns, include_extensions=include_extensions):
        module_name = path_to_module_fn(file_path, root_path)
        if not module_name or zone_assignments.get(module_name) != HexagonalZone.DOMAIN.value:
            continue
        if file_path.suffix != ".py":
            continue

        try:
            source = file_path.read_text(encoding="utf-8", errors="ignore")
            classes = extract_classes(source)
        except (SyntaxError, OSError):
            continue

        for cls in classes:
            if not _has_fields(cls):
                continue

            methods = [
                m for m in get_class_methods(cls)
                if m.name not in _TRIVIAL_METHOD_NAMES
            ]
            behavioural = [m for m in methods if not _is_trivial_accessor(m)]
            if behavioural:
                continue

            field_count = sum(
                1 for n in ast.walk(cls)
                if isinstance(n, (ast.Assign, ast.AnnAssign))
            )
            violations.append(HexagonalViolation(
                file_path=str(file_path),
                line_number=cls.lineno,
                source_zone=HexagonalZone.DOMAIN,
                target_zone=HexagonalZone.DOMAIN,
                class_name=cls.name,
                message=(
                    f"Class '{cls.name}' is an Anemic Domain Model: it holds state "
                    f"(~{field_count} field assignment(s)) but every method is a "
                    "constructor, dunder, or trivial accessor/mutator. Business "
                    "logic likely leaked into services — consider moving behaviour "
                    "that operates on this data back onto the entity."
                ),
                severity=ViolationSeverity.LOW,
            ))

    return violations


def detect_infrastructure_leaks(
    root_path: Path,
    zone_assignments: Dict[str, str],
    exclude_patterns: List[str],
    include_extensions: List[str],
    path_to_module_fn,
) -> List[HexagonalViolation]:
    """Flag domain-zone classes bound to a persistence/web framework via
    base class, decorator, or ORM column declaration — even when the
    triggering import itself wasn't caught by the plain import-scan check."""
    violations: List[HexagonalViolation] = []

    for file_path in scan_directory(root_path, exclude_patterns=exclude_patterns, include_extensions=include_extensions):
        module_name = path_to_module_fn(file_path, root_path)
        if not module_name or zone_assignments.get(module_name) != HexagonalZone.DOMAIN.value:
            continue
        if file_path.suffix != ".py":
            continue

        try:
            source = file_path.read_text(encoding="utf-8", errors="ignore")
            classes = extract_classes(source)
        except (SyntaxError, OSError):
            continue

        for cls in classes:
            reasons: List[str] = []

            bases = get_class_bases(cls)
            for base in bases:
                simple = base.split(".")[-1]
                if simple in _ORM_BASE_NAMES:
                    reasons.append(f"inherits from ORM base '{base}'")

            decorators = get_class_decorators(cls)
            for dec in decorators:
                simple = dec.split(".")[-1].split("(")[0]
                if simple in _ORM_DECORATOR_NAMES:
                    reasons.append(f"decorated with '@{dec}'")

            for node in ast.walk(cls):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in _ORM_COLUMN_CALL_NAMES:
                        reasons.append(f"uses ORM field declaration '{node.func.id}(...)'")
                        break

            if not reasons:
                continue

            violations.append(HexagonalViolation(
                file_path=str(file_path),
                line_number=cls.lineno,
                source_zone=HexagonalZone.DOMAIN,
                target_zone=HexagonalZone.INFRASTRUCTURE,
                class_name=cls.name,
                message=(
                    f"Class '{cls.name}' is a domain entity but leaks infrastructure "
                    f"concerns: {', '.join(sorted(set(reasons)))}. Domain entities "
                    "should be plain objects; move ORM/framework binding to an "
                    "adapter that maps to/from this entity."
                ),
                severity=ViolationSeverity.HIGH,
            ))

    return violations
