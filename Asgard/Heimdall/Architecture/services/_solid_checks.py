"""
Heimdall SOLID Principle Checks

Individual SOLID principle check helpers extracted from SOLIDValidator.
"""

import ast
from pathlib import Path
from typing import List, Set

from Asgard.Heimdall.Architecture.models.architecture_models import (
    SOLIDPrinciple,
    SOLIDViolation,
    ViolationSeverity,
)
from Asgard.Heimdall.Architecture.utilities.ast_utils import (
    get_abstract_methods,
    get_class_bases,
    get_class_methods,
    get_constructor_params,
    is_abstract_class,
)


def extract_method_prefixes(methods: List[ast.FunctionDef]) -> Set[str]:
    """Extract responsibility prefixes from method names."""
    prefixes: Set[str] = set()
    responsibility_words = {
        "get", "set", "is", "has", "can",
        "validate", "check", "verify",
        "create", "build", "make", "generate",
        "parse", "process", "transform", "convert",
        "save", "load", "read", "write", "store",
        "send", "receive", "notify", "dispatch",
        "render", "display", "show", "format",
        "calculate", "compute", "analyze",
    }

    for method in methods:
        name = method.name
        if name.startswith("_"):
            continue

        parts = []
        current: List[str] = []
        for char in name:
            if char == "_":
                if current:
                    parts.append("".join(current).lower())
                    current = []
            elif char.isupper() and current:
                parts.append("".join(current).lower())
                current = [char.lower()]
            else:
                current.append(char.lower())
        if current:
            parts.append("".join(current))

        if parts and parts[0] in responsibility_words:
            prefix = parts[0]
            if prefix in {"get", "set", "is", "has", "can"}:
                continue
            if prefix in {"validate", "check", "verify"}:
                prefixes.add("validation")
            elif prefix in {"create", "build", "make", "generate"}:
                prefixes.add("creation")
            elif prefix in {"parse", "process", "transform", "convert"}:
                prefixes.add("processing")
            elif prefix in {"save", "load", "read", "write", "store"}:
                prefixes.add("persistence")
            elif prefix in {"send", "receive", "notify", "dispatch"}:
                prefixes.add("communication")
            elif prefix in {"render", "display", "show", "format"}:
                prefixes.add("presentation")
            elif prefix in {"calculate", "compute", "analyze"}:
                prefixes.add("computation")

    return prefixes


def count_if_chain(method: ast.FunctionDef) -> int:
    """Count the length of the longest if-elif chain in a method."""
    max_chain = 0
    for node in ast.walk(method):
        if isinstance(node, ast.If):
            chain = 1
            current = node
            while current.orelse:
                if len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
                    chain += 1
                    current = current.orelse[0]
                else:
                    if current.orelse:
                        chain += 1
                    break
            max_chain = max(max_chain, chain)
    return max_chain


def count_isinstance_checks(method: ast.FunctionDef) -> int:
    """Count isinstance calls in a method."""
    return sum(
        1
        for node in ast.walk(method)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "isinstance"
    )


def is_empty_method(method: ast.FunctionDef) -> bool:
    """Check if a method body is empty (just pass or ...)."""
    if len(method.body) == 1:
        stmt = method.body[0]
        if isinstance(stmt, ast.Pass):
            return True
        if isinstance(stmt, ast.Expr):
            if isinstance(stmt.value, ast.Constant) and stmt.value.value is ...:
                return True
    return False


def find_instantiations(method: ast.FunctionDef) -> List[str]:
    """Find class instantiations in a method."""
    instantiations = []
    for node in ast.walk(method):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                name = node.func.id
                if name[0].isupper():
                    instantiations.append(name)
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
                if name[0].isupper():
                    instantiations.append(name)
    return instantiations


def check_ocp(
    class_node: ast.ClassDef,
    file_path: Path,
) -> List[SOLIDViolation]:
    """Check Open/Closed Principle."""
    violations = []
    for method in get_class_methods(class_node):
        if_chain_length = count_if_chain(method)
        if if_chain_length >= 4:
            violations.append(SOLIDViolation(
                principle=SOLIDPrinciple.OCP,
                class_name=class_node.name,
                file_path=str(file_path),
                line_number=method.lineno,
                message=f"Method '{method.name}' has {if_chain_length} branches - consider polymorphism",
                severity=ViolationSeverity.MODERATE,
                suggestion="Replace conditionals with polymorphism using a strategy pattern",
            ))

        isinstance_count = count_isinstance_checks(method)
        if isinstance_count >= 3:
            violations.append(SOLIDViolation(
                principle=SOLIDPrinciple.OCP,
                class_name=class_node.name,
                file_path=str(file_path),
                line_number=method.lineno,
                message=f"Method '{method.name}' has {isinstance_count} isinstance checks",
                severity=ViolationSeverity.MODERATE,
                suggestion="Use polymorphism instead of type checking",
            ))
    return violations


def check_lsp(
    class_node: ast.ClassDef,
    file_path: Path,
) -> List[SOLIDViolation]:
    """Check Liskov Substitution Principle."""
    violations: List[SOLIDViolation] = []
    bases = get_class_bases(class_node)

    if not bases or bases == ["object"]:
        return violations

    for method in get_class_methods(class_node):
        for node in ast.walk(method):
            if isinstance(node, ast.Raise):
                if isinstance(node.exc, ast.Call) and isinstance(node.exc.func, ast.Name):
                    if node.exc.func.id == "NotImplementedError":
                        violations.append(SOLIDViolation(
                            principle=SOLIDPrinciple.LSP,
                            class_name=class_node.name,
                            file_path=str(file_path),
                            line_number=node.lineno,
                            message=f"Method '{method.name}' raises NotImplementedError in derived class",
                            severity=ViolationSeverity.HIGH,
                            suggestion="Override method with proper implementation or use abstract base class",
                        ))

        for node in ast.walk(method):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "type":
                    if len(node.args) == 1:
                        if isinstance(node.args[0], ast.Name) and node.args[0].id == "self":
                            violations.append(SOLIDViolation(
                                principle=SOLIDPrinciple.LSP,
                                class_name=class_node.name,
                                file_path=str(file_path),
                                line_number=node.lineno,
                                message=f"Method '{method.name}' checks type(self)",
                                severity=ViolationSeverity.MODERATE,
                                suggestion="Avoid type checking on self in derived classes",
                            ))
    return violations


def check_isp(
    class_node: ast.ClassDef,
    file_path: Path,
) -> List[SOLIDViolation]:
    """Check Interface Segregation Principle."""
    violations = []

    if is_abstract_class(class_node):
        abstract_methods = get_abstract_methods(class_node)
        if len(abstract_methods) > 7:
            violations.append(SOLIDViolation(
                principle=SOLIDPrinciple.ISP,
                class_name=class_node.name,
                file_path=str(file_path),
                line_number=class_node.lineno,
                message=f"Interface has {len(abstract_methods)} abstract methods",
                severity=ViolationSeverity.MODERATE,
                suggestion="Split into smaller, focused interfaces",
            ))

    empty_methods = [m.name for m in get_class_methods(class_node) if is_empty_method(m)]
    if len(empty_methods) >= 3:
        violations.append(SOLIDViolation(
            principle=SOLIDPrinciple.ISP,
            class_name=class_node.name,
            file_path=str(file_path),
            line_number=class_node.lineno,
            message=f"Class has {len(empty_methods)} empty methods: {', '.join(empty_methods[:3])}",
            severity=ViolationSeverity.HIGH,
            suggestion="This class may be implementing an interface it doesn't need",
        ))
    return violations


def check_dip(
    class_node: ast.ClassDef,
    file_path: Path,
    max_dependencies: int,
) -> List[SOLIDViolation]:
    """Check Dependency Inversion Principle."""
    violations = []

    for method in get_class_methods(class_node):
        if method.name == "__init__":
            instantiations = find_instantiations(method)
            concrete_deps = [
                i for i in instantiations
                if i not in {"list", "dict", "set", "tuple", "str", "int", "float", "bool"}
                and not i.startswith("_")
            ]
            if len(concrete_deps) > 3:
                violations.append(SOLIDViolation(
                    principle=SOLIDPrinciple.DIP,
                    class_name=class_node.name,
                    file_path=str(file_path),
                    line_number=method.lineno,
                    message=f"Constructor instantiates {len(concrete_deps)} concrete dependencies",
                    severity=ViolationSeverity.MODERATE,
                    suggestion="Use dependency injection instead of direct instantiation",
                ))

    params = get_constructor_params(class_node)
    if len(params) > max_dependencies:
        violations.append(SOLIDViolation(
            principle=SOLIDPrinciple.DIP,
            class_name=class_node.name,
            file_path=str(file_path),
            line_number=class_node.lineno,
            message=f"Class has {len(params)} constructor dependencies (threshold: {max_dependencies})",
            severity=ViolationSeverity.LOW,
            suggestion="Consider using a facade or splitting the class",
        ))

    return violations
