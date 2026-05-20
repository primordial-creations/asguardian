"""
Heimdall Architecture - Generic Hexagonal Architecture Checks

Regex-based hexagonal architecture checks for non-Python languages.
Detects domain-to-infrastructure coupling and adapters missing port references.
"""

import re
from pathlib import Path
from typing import List

from Asgard.Bragi.Architecture.models.architecture_models import (
    HexagonalViolation,
    HexagonalZone,
    ViolationSeverity,
)

# Folder name segments that indicate "domain" layer
_DOMAIN_PATH_SEGMENTS = frozenset({"domain", "core", "entities", "model", "models"})

# Import keywords / phrases that indicate infrastructure
_INFRA_TERMS = frozenset({
    "database", "db", "sql", "http", "repository", "repositories",
    "infrastructure", "infra", "persistence", "jdbc", "orm", "redis",
    "mongo", "elastic", "rabbitmq", "kafka", "messaging",
})

# Per-language regex to capture the imported module/package string
_IMPORT_PATTERNS: dict = {
    # Java/Kotlin: import com.example.database.Foo;
    "java":       re.compile(r"^\s*import\s+([\w.]+)\s*;"),
    "kotlin":     re.compile(r"^\s*import\s+([\w.]+)"),
    # C#: using Company.Infrastructure.Repo;
    "csharp":     re.compile(r"^\s*using\s+([\w.]+)\s*;"),
    # Go: import "myapp/infrastructure/db"
    "go":         re.compile(r'^\s*"([\w./]+)"'),
    # PHP: use App\Infrastructure\Repo;
    "php":        re.compile(r"^\s*use\s+([\w\\]+)\s*;"),
    # Ruby: require 'app/infrastructure/repo'
    "ruby":       re.compile(r"""^\s*require(?:_relative)?\s+['"]([^'"]+)['"]\s*$"""),
    # JS/TS: import ... from 'infrastructure/repo'
    "javascript": re.compile(r"""from\s+['"]([^'"]+)['"]\s*;?"""),
    "typescript": re.compile(r"""from\s+['"]([^'"]+)['"]\s*;?"""),
    # Python (fallback, though Python has its own AST-based checker)
    "python":     re.compile(r"^\s*(?:from|import)\s+([\w.]+)"),
}


def _is_domain_file(file_path: str) -> bool:
    """Return True if the file is inside a 'domain' layer directory."""
    parts = {p.lower() for p in Path(file_path).parts}
    return bool(parts & _DOMAIN_PATH_SEGMENTS)


def _import_touches_infra(import_str: str) -> bool:
    """Return True if the import path/package references infrastructure terms."""
    parts = re.split(r"[./\\]", import_str.lower())
    return bool(set(parts) & _INFRA_TERMS)


def check_domain_imports_infrastructure(
    file_path: str,
    lines: List[str],
    language: str,
) -> List[HexagonalViolation]:
    """
    Detect domain files importing from infrastructure packages.

    Args:
        file_path: Absolute or relative path of the file being checked.
        lines: Source lines of the file.
        language: Language key (e.g. "java", "go", "typescript").

    Returns:
        List of HexagonalViolation, one per offending import line.
    """
    if not _is_domain_file(file_path):
        return []

    pattern = _IMPORT_PATTERNS.get(language.lower())
    if pattern is None:
        return []

    violations: List[HexagonalViolation] = []
    for i, line in enumerate(lines, start=1):
        m = pattern.search(line)
        if m:
            imported = m.group(1)
            if _import_touches_infra(imported):
                violations.append(
                    HexagonalViolation(
                        file_path=file_path,
                        line_number=i,
                        source_zone=HexagonalZone.DOMAIN,
                        target_zone=HexagonalZone.INFRASTRUCTURE,
                        class_name="<domain file>",
                        message=(
                            f"Domain file imports infrastructure module '{imported}'. "
                            "Domain/core must not depend on infrastructure details."
                        ),
                        severity=ViolationSeverity.HIGH,
                    )
                )
    return violations


# Folder name segments that indicate "adapters" layer
_ADAPTER_PATH_SEGMENTS = frozenset({"adapters", "adapter"})

# Per-language patterns for referencing a port interface/protocol type
_PORT_REFERENCE_PATTERNS: dict = {
    "java":       re.compile(r"\bimplements\s+\w+Port\b|\bimplements\s+I\w+\b"),
    "kotlin":     re.compile(r"\s*:\s*\w+Port\b"),
    "csharp":     re.compile(r"\s*:\s*I[A-Z]\w+\b"),
    "go":         re.compile(r"\b\w+Port\b|\binterface\b"),
    "php":        re.compile(r"\bimplements\s+\w+Interface\b|\bimplements\s+\w+Port\b"),
    "ruby":       re.compile(r"\binclude\s+\w+Port\b|\binclude\s+\w+Interface\b"),
    "typescript": re.compile(r"\bimplements\s+\w+Port\b|\bimplements\s+I[A-Z]\w+\b"),
    "javascript": re.compile(r"@implements|@interface"),
}


def _is_adapter_file(file_path: str) -> bool:
    """Return True if the file is inside an 'adapters' layer directory."""
    parts = {p.lower() for p in Path(file_path).parts}
    return bool(parts & _ADAPTER_PATH_SEGMENTS)


def check_missing_port_reference(
    file_path: str,
    lines: List[str],
    language: str,
) -> List[HexagonalViolation]:
    """
    Detect adapter files that do not reference any port interface.

    Args:
        file_path: Absolute or relative path of the file being checked.
        lines: Source lines of the file.
        language: Language key.

    Returns:
        List of HexagonalViolation (zero or one entry).
    """
    if not _is_adapter_file(file_path):
        return []

    pattern = _PORT_REFERENCE_PATTERNS.get(language.lower())
    if pattern is None:
        return []

    full_source = "\n".join(lines)
    if pattern.search(full_source):
        return []  # port reference found — OK

    return [
        HexagonalViolation(
            file_path=file_path,
            line_number=1,
            source_zone=HexagonalZone.ADAPTER,
            target_zone=HexagonalZone.PORT,
            class_name="<adapter file>",
            message=(
                "Adapter file does not appear to implement or reference any port interface. "
                "Adapters should implement a port (interface/protocol) to honour hexagonal boundaries."
            ),
            severity=ViolationSeverity.MODERATE,
        )
    ]
