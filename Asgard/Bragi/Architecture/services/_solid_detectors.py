"""
Heimdall SOLID Checks - Class and Method Pattern Detectors

Helper functions that detect design patterns, class types, and method
characteristics used by the SOLID principle checks to reduce false positives.
"""

import ast
from typing import List, Set

# Class name substrings that indicate utility/facade classes where high
# public method counts are expected and acceptable for SRP.
_UTILITY_CLASS_INDICATORS = {
    "utils", "util", "utility", "utilities",
    "helper", "helpers", "facade", "mixin",
    "toolkit", "tools",
}

# Base classes whose subclasses use the Visitor pattern (many visit_* methods
# are the entire point of the class, not an SRP violation).
_VISITOR_BASE_CLASSES = {
    "NodeVisitor", "NodeTransformer",
    "ast.NodeVisitor", "ast.NodeTransformer",
}

# Common data-model / config base classes whose constructors legitimately
# instantiate many objects (e.g. Pydantic Field(), dataclass field()).
_DATA_MODEL_BASES = {
    "BaseModel", "BaseSettings",  # Pydantic
}

# Instantiation names that are configuration/data helpers, not real
# concrete dependencies worth flagging for DIP.
BENIGN_INSTANTIATIONS = {
    "list", "dict", "set", "tuple", "str", "int", "float", "bool",
    "Path", "PurePath",
    "defaultdict", "OrderedDict", "Counter", "deque",
    "Field",  # Pydantic / dataclass Field()
    "Lock", "RLock", "Event", "Semaphore",  # threading primitives
    "Queue",
    "Logger",
    "re",
    "Pattern",
}

# AST node type names used to detect isinstance checks against ast.* types.
_AST_TYPE_NAMES = {
    "Module", "FunctionDef", "AsyncFunctionDef", "ClassDef",
    "Return", "Delete", "Assign", "AugAssign", "AnnAssign",
    "For", "AsyncFor", "While", "If", "With", "AsyncWith",
    "Raise", "Try", "Assert", "Import", "ImportFrom",
    "Global", "Nonlocal", "Expr", "Pass", "Break", "Continue",
    "BoolOp", "BinOp", "UnaryOp", "Lambda", "IfExp",
    "Dict", "Set", "ListComp", "SetComp", "DictComp", "GeneratorExp",
    "Await", "Yield", "YieldFrom", "Compare", "Call",
    "FormattedValue", "JoinedStr", "Constant", "Attribute",
    "Subscript", "Starred", "Name", "List", "Tuple", "Slice",
    "Add", "Sub", "Mult", "Div", "Mod", "Pow", "LShift", "RShift",
    "BitOr", "BitXor", "BitAnd", "FloorDiv",
    "And", "Or", "Not", "Invert", "UAdd", "USub",
    "Eq", "NotEq", "Lt", "LtE", "Gt", "GtE", "Is", "IsNot", "In", "NotIn",
    "arg", "arguments", "keyword", "alias", "withitem",
    "ExceptHandler", "MatchValue", "MatchSingleton", "MatchSequence",
}

# Value-object class names: these are data containers, not service classes.
_VALUE_OBJECT_SUFFIXES = (
    "Pattern", "Config", "Result", "Report", "Spec", "Entry", "Record", "Info",
)

# Format/value-dispatch keywords for is_format_dispatch.
_FORMAT_KEYWORDS = {
    "json", "yaml", "yml", "text", "txt", "markdown", "md",
    "html", "xml", "csv", "toml",
}

# Maps method-name prefixes to responsibility categories.
_PREFIX_TO_RESPONSIBILITY = {
    "validate": "validation", "check": "validation", "verify": "validation",
    "create": "creation", "build": "creation", "make": "creation", "generate": "creation",
    "parse": "processing", "process": "processing", "transform": "processing", "convert": "processing",
    "save": "persistence", "load": "persistence", "read": "persistence", "write": "persistence", "store": "persistence",
    "send": "communication", "receive": "communication", "notify": "communication", "dispatch": "communication",
    "render": "presentation", "display": "presentation", "show": "presentation", "format": "presentation",
    "calculate": "computation", "compute": "computation", "analyze": "computation",
}

# Prefixes that are too generic to count as responsibilities.
_SKIP_PREFIXES = {"get", "set", "is", "has", "can"}


def is_visitor_class(class_node: ast.ClassDef) -> bool:
    """Return True if the class is an AST Visitor (NodeVisitor/NodeTransformer)."""
    for base in class_node.bases:
        if isinstance(base, ast.Name) and base.id in _VISITOR_BASE_CLASSES:
            return True
        if isinstance(base, ast.Attribute):
            qualified = f"{base.value.id}.{base.attr}" if isinstance(base.value, ast.Name) else base.attr
            if qualified in _VISITOR_BASE_CLASSES or base.attr in _VISITOR_BASE_CLASSES:
                return True
    return False


def is_utility_class(class_name: str) -> bool:
    """Return True if the class name suggests a utility/facade/helper class."""
    name_lower = class_name.lower()
    return any(indicator in name_lower for indicator in _UTILITY_CLASS_INDICATORS)


def _has_data_model_base(class_node: ast.ClassDef) -> bool:
    """Return True if any base class is a known data-model base."""
    for base in class_node.bases:
        if isinstance(base, ast.Name) and base.id in _DATA_MODEL_BASES:
            return True
        if isinstance(base, ast.Attribute) and base.attr in _DATA_MODEL_BASES:
            return True
    return False


def _has_dataclass_decorator(class_node: ast.ClassDef) -> bool:
    """Return True if the class has a @dataclass decorator."""
    for decorator in class_node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == "dataclass":
            return True
        if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name) and decorator.func.id == "dataclass":
            return True
        if isinstance(decorator, ast.Attribute) and decorator.attr == "dataclass":
            return True
    return False


def is_data_model_class(class_node: ast.ClassDef) -> bool:
    """
    Return True if the class is a data model or dataclass.

    Checks for Pydantic BaseModel/BaseSettings inheritance and @dataclass
    decorator. These classes legitimately have many constructor parameters
    and should not be flagged for DIP violations.
    """
    if _has_data_model_base(class_node):
        return True
    if _has_dataclass_decorator(class_node):
        return True
    if class_node.name.endswith(_VALUE_OBJECT_SUFFIXES):
        return True
    return False


def _classify_comparator(comparator: ast.expr) -> tuple:
    """Classify a single comparator as (is_string, is_format, is_enum_format)."""
    if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
        is_format = comparator.value.lower() in _FORMAT_KEYWORDS
        return True, is_format, False
    if isinstance(comparator, ast.Attribute) and comparator.attr.lower() in _FORMAT_KEYWORDS:
        return False, False, True
    return False, False, False


def _count_format_comparisons(method: ast.FunctionDef) -> tuple:
    """Count string, format-keyword, and enum comparisons in a method.

    Returns (string_comparisons, format_matches, enum_comparisons).
    """
    comparators = (
        comp
        for node in ast.walk(method)
        if isinstance(node, ast.Compare)
        for comp in node.comparators
    )
    string_comparisons = 0
    format_matches = 0
    enum_comparisons = 0
    for comparator in comparators:
        is_string, is_format, is_enum = _classify_comparator(comparator)
        string_comparisons += is_string
        format_matches += is_format
        enum_comparisons += is_enum
    return string_comparisons, format_matches, enum_comparisons


def is_format_dispatch(method: ast.FunctionDef) -> bool:
    """
    Return True if the method is a simple format/value-dispatch method.

    Detects if-elif chains that compare against format keywords (json, yaml,
    text, etc.) as string constants or enum attributes, or methods with 4+
    distinct string constant comparisons (version detection, type validation).
    """
    string_comparisons, format_matches, enum_comparisons = _count_format_comparisons(method)
    if format_matches + enum_comparisons >= 2:
        return True
    return string_comparisons >= 4  # type: ignore[no-any-return]


def is_inherently_branchy_method(method_name: str) -> bool:
    """
    Return True if method name suggests branching is inherent to the domain.

    Covers type/schema validation dispatch, severity/rating classification,
    version/format detection, and increment/count dispatchers.
    """
    name_lower = method_name.lower()
    inherently_branchy_keywords = (
        "validate_type", "check_type", "parse_schema",
        "parse_type", "convert_type", "resolve_type",
        "annotation_to", "type_to", "to_type",
        "generate_value", "generate_by_type",
        "detect_version", "detect_format",
        "to_severity", "to_rating", "to_grade", "to_level",
        "severity", "calculate_severity", "calculate_level",
        "coupling_level", "cohesion_level",
        "get_rating", "score_to_grade", "ratio_to_rating",
        "maintainability_level",
        "increment_severity", "increment_risk", "increment_type",
    )
    return any(kw in name_lower for kw in inherently_branchy_keywords)


def _is_ast_type_ref(node: ast.expr) -> bool:
    """Return True if an AST node references an ast.* type."""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "ast":
        return True
    if isinstance(node, ast.Name) and node.id in _AST_TYPE_NAMES:
        return True
    return False


def _isinstance_references_ast(call_node: ast.Call) -> bool:
    """Return True if an isinstance() call references ast.* types."""
    if len(call_node.args) < 2:
        return False
    type_arg = call_node.args[1]
    if _is_ast_type_ref(type_arg):
        return True
    if isinstance(type_arg, ast.Tuple):
        return any(_is_ast_type_ref(elt) for elt in type_arg.elts)
    return False


def uses_ast_isinstance(method: ast.FunctionDef) -> bool:
    """Return True if isinstance checks in this method reference ast.* types."""
    for node in ast.walk(method):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "isinstance"):
            continue
        if _isinstance_references_ast(node):
            return True
    return False


def _split_method_name(name: str) -> List[str]:
    """Split a method name into lowercase word parts on underscores and camelCase."""
    parts: List[str] = []
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
    return parts


def extract_method_prefixes(methods: List[ast.FunctionDef]) -> Set[str]:
    """Extract responsibility prefixes from method names."""
    prefixes: Set[str] = set()
    for method in methods:
        if method.name.startswith("_"):
            continue
        parts = _split_method_name(method.name)
        if not parts or parts[0] in _SKIP_PREFIXES:
            continue
        responsibility = _PREFIX_TO_RESPONSIBILITY.get(parts[0])
        if responsibility:
            prefixes.add(responsibility)
    return prefixes
