import ast
from typing import Dict, List, Optional, Set, Tuple

from Asgard.Heimdall.Quality.models.thread_safety_models import (
    ThreadSafetyIssue,
    ThreadSafetyIssueType,
    ThreadSafetySeverity,
)


# Names that indicate mutable shared collections
MUTABLE_COLLECTION_NAMES: Set[str] = {
    "list", "dict", "set", "deque", "defaultdict", "OrderedDict",
    "Counter", "bytearray",
}


def _get_self_attr_assignments(method_node: ast.AST) -> Set[str]:
    """Collect all self.attr names assigned in a method body."""
    assigned: Set[str] = set()
    for node in ast.walk(method_node):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ):
                    assigned.add(target.attr)
        elif isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Attribute)
                and isinstance(node.target.value, ast.Name)
                and node.target.value.id == "self"
            ):
                assigned.add(node.target.attr)
    return assigned


def _get_self_attr_reads(method_node: ast.AST) -> Set[str]:
    """Collect all self.attr names read (loaded) in a method body."""
    reads: Set[str] = set()
    for node in ast.walk(method_node):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
            and isinstance(node.ctx, ast.Load)
        ):
            reads.add(node.attr)
    return reads


def _find_mutable_collection_attrs(method_node: ast.AST) -> Dict[str, int]:
    """Find self.attr assignments to mutable collections. Returns {attr_name: line_no}."""
    mutable: Dict[str, int] = {}
    for node in ast.walk(method_node):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ):
                    attr_name = target.attr
                    val = node.value
                    # Direct literal: self.x = [] or self.x = {}
                    if isinstance(val, (ast.List, ast.Dict, ast.Set)):
                        mutable[attr_name] = node.lineno
                    # Constructor call: self.x = list() / dict() / deque() etc.
                    elif isinstance(val, ast.Call):
                        func = val.func
                        if isinstance(func, ast.Name) and func.id in MUTABLE_COLLECTION_NAMES:
                            mutable[attr_name] = node.lineno
                        elif isinstance(func, ast.Attribute) and func.attr in MUTABLE_COLLECTION_NAMES:
                            mutable[attr_name] = node.lineno
    return mutable


def _find_thread_targets(class_node: ast.ClassDef) -> List[Tuple[int, str]]:
    """
    Find threading.Thread(target=self.method) calls in class.
    Returns list of (line_no, method_name).
    """
    targets: List[Tuple[int, str]] = []
    for node in ast.walk(class_node):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_thread_call = (
            (isinstance(func, ast.Name) and func.id == "Thread")
            or (isinstance(func, ast.Attribute) and func.attr == "Thread")
        )
        if not is_thread_call:
            continue
        for kw in node.keywords:
            if kw.arg == "target" and isinstance(kw.value, ast.Attribute):
                val = kw.value
                if isinstance(val.value, ast.Name) and val.value.id == "self":
                    targets.append((node.lineno, val.attr))
    return targets


class ThreadSafetyVisitor(ast.NodeVisitor):
    """
    AST visitor that detects thread safety issues.

    Analyzes each ClassDef for:
    - Attributes accessed by thread targets not initialized in __init__
    - Shared mutable collections used by thread targets
    """

    def __init__(self, file_path: str, source_lines: List[str]):
        """
        Initialize the thread safety visitor.

        Args:
            file_path: Path to the file being analyzed
            source_lines: Source code lines for extracting snippets
        """
        self.file_path = file_path
        self.source_lines = source_lines
        self.issues: List[ThreadSafetyIssue] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Analyze each class for thread safety issues."""
        self._analyze_class(node)
        self.generic_visit(node)

    def _analyze_class(self, class_node: ast.ClassDef) -> None:
        """Perform thread safety analysis on a single class."""
        class_name = class_node.name

        # Collect methods by name
        methods: Dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
        for item in class_node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods[item.name] = item

        # Find threading.Thread targets in this class
        thread_targets = _find_thread_targets(class_node)
        if not thread_targets:
            return

        # Collect attrs initialized in __init__
        init_attrs: Set[str] = set()
        if "__init__" in methods:
            init_attrs = _get_self_attr_assignments(methods["__init__"])

        # Collect all mutable collection assignments (across all methods)
        all_mutable_attrs: Dict[str, int] = {}
        for method_name, method_node in methods.items():
            found = _find_mutable_collection_attrs(method_node)
            for attr, line in found.items():
                if attr not in all_mutable_attrs:
                    all_mutable_attrs[attr] = line

        # For each thread target method, check attribute access
        for thread_line, target_method_name in thread_targets:
            if target_method_name not in methods:
                continue

            target_method = methods[target_method_name]
            attrs_read = _get_self_attr_reads(target_method)

            for attr_name in attrs_read:
                if attr_name not in init_attrs:
                    # Attribute read by thread target but not initialized in __init__
                    if attr_name in all_mutable_attrs:
                        # Shared mutable collection - MEDIUM
                        self.issues.append(ThreadSafetyIssue(
                            file_path=self.file_path,
                            line_number=all_mutable_attrs[attr_name],
                            class_name=class_name,
                            issue_type=ThreadSafetyIssueType.SHARED_MUTABLE_COLLECTION,
                            severity=ThreadSafetySeverity.MEDIUM,
                            description=(
                                f"Shared mutable collection 'self.{attr_name}' is accessed "
                                f"by thread target '{target_method_name}' without lock protection"
                            ),
                            attribute_name=attr_name,
                            thread_target_method=target_method_name,
                            remediation=(
                                f"Protect 'self.{attr_name}' with a threading.Lock(). "
                                f"Initialize it in __init__ and acquire the lock before access."
                            ),
                        ))
                    else:
                        # Attribute not initialized in __init__ - HIGH
                        self.issues.append(ThreadSafetyIssue(
                            file_path=self.file_path,
                            line_number=thread_line,
                            class_name=class_name,
                            issue_type=ThreadSafetyIssueType.UNINITIALIZED_ATTR,
                            severity=ThreadSafetySeverity.HIGH,
                            description=(
                                f"Thread target '{target_method_name}' accesses 'self.{attr_name}' "
                                f"which is not initialized in __init__. Thread may run before "
                                f"attribute is set."
                            ),
                            attribute_name=attr_name,
                            thread_target_method=target_method_name,
                            remediation=(
                                f"Initialize 'self.{attr_name}' in __init__ before starting threads. "
                                f"This ensures the attribute exists when the thread begins execution."
                            ),
                        ))
