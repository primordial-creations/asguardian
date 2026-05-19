"""
Heimdall Architecture - Generic SOLID Checks

Regex/token heuristic SOLID checks for non-Python languages.
These checks work on raw source lines and are language-agnostic
with per-language pattern dictionaries.
"""

import re
from typing import List

from Asgard.Heimdall.Architecture.models.architecture_models import (
    SOLIDPrinciple,
    SOLIDViolation,
    ViolationSeverity,
)

# ---------------------------------------------------------------------------
# SRP: count public method definitions per language
# ---------------------------------------------------------------------------

_METHOD_PATTERNS: dict = {
    "python":     re.compile(r"^\s{4,}def [a-zA-Z][a-zA-Z0-9_]*\s*\("),
    "java":       re.compile(r"\bpublic\s+\w[\w<>\[\]]*\s+\w+\s*\("),
    "csharp":     re.compile(r"\bpublic\s+\w[\w<>\[\]]*\s+\w+\s*\("),
    "go":         re.compile(r"^func\s+\(\s*\w+\s+\*?\w+\s*\)\s+\w+\s*\("),
    "ruby":       re.compile(r"^\s+def\s+[a-z_][a-zA-Z0-9_]*"),
    "javascript": re.compile(r"^\s+(?:\w+)\s*\(.*\)\s*\{|^\s+\w+\s*=\s*(?:async\s*)?\(.*\)\s*=>"),
    "typescript": re.compile(r"^\s+(?:\w+)\s*\(.*\)\s*\{|^\s+\w+\s*=\s*(?:async\s*)?\(.*\)\s*=>"),
    "php":        re.compile(r"\bpublic\s+function\s+\w+\s*\("),
}


def check_srp_method_count(
    file_path: str,
    lines: List[str],
    language: str,
    threshold: int = 10,
) -> List[SOLIDViolation]:
    """
    Detect SRP violations by counting public method definitions.

    Args:
        file_path: Path of the source file (used in the violation).
        lines: Source lines of the file.
        language: Language key (e.g. "java", "go").
        threshold: Maximum number of public methods before flagging.

    Returns:
        List of SOLIDViolation (zero or one entry).
    """
    pattern = _METHOD_PATTERNS.get(language.lower())
    if pattern is None:
        return []

    count = sum(1 for line in lines if pattern.search(line))
    if count > threshold:
        return [
            SOLIDViolation(
                principle=SOLIDPrinciple.SRP,
                class_name="<file>",
                file_path=file_path,
                line_number=1,
                message=(
                    f"File has {count} public method definitions "
                    f"(threshold: {threshold}). "
                    "Consider splitting into smaller, focused classes/modules."
                ),
                severity=ViolationSeverity.MODERATE,
                suggestion="Split responsibilities into separate classes or modules.",
            )
        ]
    return []


# ---------------------------------------------------------------------------
# ISP: count methods inside interface / abstract blocks
# ---------------------------------------------------------------------------

_INTERFACE_START: dict = {
    "java":       re.compile(r"\binterface\s+\w+"),
    "csharp":     re.compile(r"\binterface\s+I\w+"),
    "typescript": re.compile(r"\binterface\s+\w+\s*\{"),
    "go":         re.compile(r"\btype\s+\w+\s+interface\s*\{"),
    "php":        re.compile(r"\binterface\s+\w+"),
    "ruby":       re.compile(r"\bmodule\s+\w+"),
}

_INTERFACE_METHOD: dict = {
    "java":       re.compile(r"\w[\w<>\[\]]*\s+\w+\s*\("),
    "csharp":     re.compile(r"\w[\w<>\[\]]*\s+\w+\s*\("),
    "typescript": re.compile(r"^\s+\w+\s*(?:\??\s*)?\("),
    "go":         re.compile(r"^\s+\w+\s*\("),
    "php":        re.compile(r"\bpublic\s+function\s+\w+\s*\("),
    "ruby":       re.compile(r"^\s+def\s+\w+"),
}

_BLOCK_END: dict = {
    "java":       re.compile(r"^\s*\}"),
    "csharp":     re.compile(r"^\s*\}"),
    "typescript": re.compile(r"^\s*\}"),
    "go":         re.compile(r"^\s*\}"),
    "php":        re.compile(r"^\s*\}"),
    "ruby":       re.compile(r"^\s*end\b"),
}


def check_isp_interface_size(
    file_path: str,
    lines: List[str],
    language: str,
    threshold: int = 7,
) -> List[SOLIDViolation]:
    """
    Detect ISP violations by counting methods in interface/abstract blocks.

    Args:
        file_path: Path of the source file.
        lines: Source lines of the file.
        language: Language key.
        threshold: Maximum number of interface methods before flagging.

    Returns:
        List of SOLIDViolation.
    """
    lang = language.lower()
    start_pat = _INTERFACE_START.get(lang)
    method_pat = _INTERFACE_METHOD.get(lang)
    end_pat = _BLOCK_END.get(lang)

    if not start_pat or not method_pat or not end_pat:
        return []

    violations: List[SOLIDViolation] = []
    in_interface = False
    interface_name = ""
    method_count = 0
    start_line = 1

    for i, line in enumerate(lines, start=1):
        if not in_interface:
            m = start_pat.search(line)
            if m:
                in_interface = True
                interface_name = line.strip().split()[1] if len(line.strip().split()) > 1 else "<interface>"
                method_count = 0
                start_line = i
        else:
            if end_pat.search(line):
                if method_count > threshold:
                    violations.append(
                        SOLIDViolation(
                            principle=SOLIDPrinciple.ISP,
                            class_name=interface_name,
                            file_path=file_path,
                            line_number=start_line,
                            message=(
                                f"Interface/abstract '{interface_name}' has "
                                f"{method_count} methods (threshold: {threshold}). "
                                "Consider splitting into smaller interfaces."
                            ),
                            severity=ViolationSeverity.MODERATE,
                            suggestion="Apply Interface Segregation: break into focused interfaces.",
                        )
                    )
                in_interface = False
            elif method_pat.search(line):
                method_count += 1

    return violations


# ---------------------------------------------------------------------------
# DIP: detect concrete class instantiation without injection
# ---------------------------------------------------------------------------

_DIP_PATTERNS: dict = {
    "java":       re.compile(r"=\s*new\s+[A-Z][a-zA-Z]*(?:Repository|Service|Dao|Manager)\s*\("),
    "csharp":     re.compile(r"=\s*new\s+[A-Z][a-zA-Z]*(?:Repository|Service|Dao|Manager)\s*\("),
    "go":         re.compile(r"&[A-Z][a-zA-Z]*\{"),
    "typescript": re.compile(r"new\s+[A-Z][a-zA-Z]*(?:Repository|Service|Manager)\s*\("),
    "javascript": re.compile(r"new\s+[A-Z][a-zA-Z]*(?:Repository|Service|Manager)\s*\("),
    "php":        re.compile(r"new\s+[A-Z][a-zA-Z]*(?:Repository|Service|Manager)\s*\("),
    "ruby":       re.compile(r"[A-Z][a-zA-Z]*(?:Repository|Service|Manager)\.new\b"),
}


def check_dip_concrete_instantiation(
    file_path: str,
    lines: List[str],
    language: str,
) -> List[SOLIDViolation]:
    """
    Detect DIP violations: concrete classes instantiated directly.

    Args:
        file_path: Path of the source file.
        lines: Source lines of the file.
        language: Language key.

    Returns:
        List of SOLIDViolation, one per matching line.
    """
    pattern = _DIP_PATTERNS.get(language.lower())
    if pattern is None:
        return []

    violations: List[SOLIDViolation] = []
    for i, line in enumerate(lines, start=1):
        m = pattern.search(line)
        if m:
            concrete = m.group(0).strip()
            violations.append(
                SOLIDViolation(
                    principle=SOLIDPrinciple.DIP,
                    class_name="<file>",
                    file_path=file_path,
                    line_number=i,
                    message=(
                        f"Concrete instantiation detected: '{concrete.strip()}'. "
                        "High-level modules should depend on abstractions, not concretions."
                    ),
                    severity=ViolationSeverity.HIGH,
                    suggestion="Inject the dependency via constructor or DI framework.",
                )
            )
    return violations


# ---------------------------------------------------------------------------
# OCP: detect type-checking / instance checks suggesting closed design
# ---------------------------------------------------------------------------

_OCP_PATTERNS: dict = {
    "python":     re.compile(r"\bif\s+(?:isinstance|type)\s*\("),
    "java":       re.compile(r"\binstanceof\s+[A-Z]"),
    "csharp":     re.compile(r"\bis\s+[A-Z][a-zA-Z]+\b"),
    "go":         re.compile(r"\.\(type\)"),
    "typescript": re.compile(r"\binstanceof\s+\w+"),
    "javascript": re.compile(r"\binstanceof\s+\w+"),
    "php":        re.compile(r"\binstanceof\s+[A-Z]"),
    "ruby":       re.compile(r"\b(?:is_a\?|kind_of\?)\s*\("),
}


def check_ocp_type_checking(
    file_path: str,
    lines: List[str],
    language: str,
) -> List[SOLIDViolation]:
    """
    Detect OCP violations: explicit type checks suggesting non-extensible design.

    Args:
        file_path: Path of the source file.
        lines: Source lines of the file.
        language: Language key.

    Returns:
        List of SOLIDViolation, one per matching line.
    """
    pattern = _OCP_PATTERNS.get(language.lower())
    if pattern is None:
        return []

    violations: List[SOLIDViolation] = []
    for i, line in enumerate(lines, start=1):
        if pattern.search(line):
            violations.append(
                SOLIDViolation(
                    principle=SOLIDPrinciple.OCP,
                    class_name="<file>",
                    file_path=file_path,
                    line_number=i,
                    message=(
                        "Type-check/instanceof detected. "
                        "Extending via concrete type checks violates Open/Closed Principle."
                    ),
                    severity=ViolationSeverity.LOW,
                    suggestion=(
                        "Use polymorphism, the Strategy pattern, or visitor "
                        "instead of explicit type checks."
                    ),
                )
            )
    return violations
