"""
Heimdall Architecture - Tree-sitter SOLID Checks

Structural SOLID checks using tree-sitter AST parsing.
Falls back to regex-based checks when tree-sitter is unavailable.
"""

import re
from typing import List, Dict, Any

from Asgard.Heimdall.treesitter._language_loader import is_available
from Asgard.Heimdall.treesitter._parser_pool import parse_source
from Asgard.Heimdall.treesitter._query_runner import run_query_all


# ---------------------------------------------------------------------------
# SRP — LCOM4 (Lack of Cohesion of Methods, variant 4)
# ---------------------------------------------------------------------------

_PYTHON_METHODS_QUERY = """
(function_definition name: (identifier) @method.name) @method.def
"""

_PYTHON_ATTRIBUTE_ACCESS_QUERY = """
(attribute object: (identifier) @attr.object attribute: (identifier) @attr.name) @attr.access
"""

_PYTHON_SELF_ATTRIBUTE_QUERY = """
(attribute object: (identifier) @self.ref attribute: (identifier) @field.name) @self.attr
"""


def _build_lcom4_graph_python(source_bytes: bytes, root_node) -> int:
    """Return LCOM4 for the first class found in the parsed Python tree.

    LCOM4 = number of connected components when methods are nodes and edges
    connect methods that share a field (self.x) or call each other.
    Returns 0 when no class or fewer than 2 methods found.
    """
    # Gather all class bodies with their methods
    from Asgard.Heimdall.treesitter._query_runner import run_query_all as _rqa

    classes_q = "(class_definition name: (identifier) @class.name body: (block) @class.body) @class.def"
    class_matches = _rqa(root_node, classes_q, source_bytes, "python")
    if not class_matches:
        return 0

    # Use the first class found (file-level check per class is done by caller)
    # We need raw node access for traversal — re-run via direct tree-sitter API
    try:
        from tree_sitter import Query, Language  # noqa: PLC0415
        from Asgard.Heimdall.treesitter._language_loader import get_language_object  # noqa: PLC0415
        lang_obj = get_language_object("python")
        if lang_obj is None:
            return 0
    except ImportError:
        return 0

    # Walk tree manually to extract per-class method info
    def _walk_classes(node):
        results = []
        if node.type == "class_definition":
            results.append(node)
        for child in node.children:
            results.extend(_walk_classes(child))
        return results

    class_nodes = _walk_classes(root_node)
    if not class_nodes:
        return 0

    max_lcom = 0
    for class_node in class_nodes:
        lcom = _lcom4_for_class(class_node, source_bytes, lang_obj)
        if lcom > max_lcom:
            max_lcom = lcom
    return max_lcom


def _lcom4_for_class(class_node, source_bytes: bytes, lang_obj) -> int:
    """Compute LCOM4 for a single class_definition node."""
    try:
        from tree_sitter import Query  # noqa: PLC0415
    except ImportError:
        return 0

    # Collect method names and their line ranges
    methods_q = Query(lang_obj, "(function_definition name: (identifier) @method.name) @method.def")
    method_captures = methods_q.captures(class_node)

    method_nodes: Dict[str, Any] = {}
    if isinstance(method_captures, dict):
        defs = method_captures.get("method.def", [])
        names = method_captures.get("method.name", [])
        if not isinstance(defs, list):
            defs = [defs]
        if not isinstance(names, list):
            names = [names]
        for name_node, def_node in zip(names, defs):
            name = source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")
            if name == "__init__":
                continue
            method_nodes[name] = def_node
    elif isinstance(method_captures, list):
        current_def = None
        current_name = None
        for node, capture_name in method_captures:
            if capture_name == "method.def":
                current_def = node
            elif capture_name == "method.name":
                current_name = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
            if current_def and current_name:
                if current_name != "__init__":
                    method_nodes[current_name] = current_def
                current_def = None
                current_name = None

    if len(method_nodes) < 2:
        return len(method_nodes)

    # For each method, collect: self.field accesses and direct calls
    self_attr_q = Query(
        lang_obj,
        "(attribute object: (identifier) @obj attribute: (identifier) @field) @self.attr"
    )
    call_q = Query(lang_obj, "(call function: (identifier) @call.name) @call")

    method_fields: Dict[str, set] = {}
    method_calls: Dict[str, set] = {}

    for method_name, method_node in method_nodes.items():
        fields: set = set()
        calls: set = set()

        attr_captures = self_attr_q.captures(method_node)
        _collect_self_attrs(attr_captures, source_bytes, fields)

        call_captures = call_q.captures(method_node)
        _collect_calls(call_captures, source_bytes, calls, set(method_nodes.keys()))

        method_fields[method_name] = fields
        method_calls[method_name] = calls

    # Build adjacency: connect methods that share a field or call each other
    method_names = list(method_nodes.keys())
    adjacency: Dict[str, set] = {m: set() for m in method_names}

    for i, m1 in enumerate(method_names):
        for m2 in method_names[i + 1:]:
            shared_fields = method_fields[m1] & method_fields[m2]
            calls_each_other = (m2 in method_calls[m1]) or (m1 in method_calls[m2])
            if shared_fields or calls_each_other:
                adjacency[m1].add(m2)
                adjacency[m2].add(m1)

    # Count connected components via BFS
    visited: set = set()
    components = 0
    for m in method_names:
        if m not in visited:
            components += 1
            queue = [m]
            while queue:
                curr = queue.pop()
                if curr in visited:
                    continue
                visited.add(curr)
                queue.extend(adjacency[curr] - visited)

    return components


def _collect_self_attrs(captures, source_bytes: bytes, out_fields: set) -> None:
    if isinstance(captures, dict):
        obj_nodes = captures.get("obj", [])
        field_nodes = captures.get("field", [])
        if not isinstance(obj_nodes, list):
            obj_nodes = [obj_nodes]
        if not isinstance(field_nodes, list):
            field_nodes = [field_nodes]
        for obj_node, field_node in zip(obj_nodes, field_nodes):
            obj_text = source_bytes[obj_node.start_byte:obj_node.end_byte].decode("utf-8", errors="replace")
            if obj_text == "self":
                field = source_bytes[field_node.start_byte:field_node.end_byte].decode("utf-8", errors="replace")
                out_fields.add(field)
    elif isinstance(captures, list):
        pairs = {}
        for node, name in captures:
            pairs[name] = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
        if pairs.get("obj") == "self" and "field" in pairs:
            out_fields.add(pairs["field"])


def _collect_calls(captures, source_bytes: bytes, out_calls: set, known_methods: set) -> None:
    if isinstance(captures, dict):
        call_nodes = captures.get("call.name", [])
        if not isinstance(call_nodes, list):
            call_nodes = [call_nodes]
        for node in call_nodes:
            name = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
            if name in known_methods:
                out_calls.add(name)
    elif isinstance(captures, list):
        for node, capture_name in captures:
            if capture_name == "call.name":
                name = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
                if name in known_methods:
                    out_calls.add(name)


def check_srp_lcom4(
    file_path: str,
    source: str,
    language: str,
    rules: Dict[str, bool],
) -> List[Dict]:
    if not rules.get("solid.srp-lcom4", True):
        return []
    if language != "python" or not is_available("python"):
        return _fallback_srp(file_path, source, language, rules)

    source_bytes = source.encode("utf-8")
    root = parse_source(source_bytes, "python")
    if root is None:
        return _fallback_srp(file_path, source, language, rules)

    lcom4 = _build_lcom4_graph_python(source_bytes, root)
    if lcom4 >= 2:
        return [{
            "rule_id": "solid.srp-lcom4",
            "line": 1,
            "message": (
                f"LCOM4={lcom4}: class has {lcom4} disconnected responsibility clusters. "
                "Consider splitting into smaller, focused classes."
            ),
            "severity": "warning",
        }]
    return []


def _fallback_srp(file_path: str, source: str, language: str, rules: Dict[str, bool]) -> List[Dict]:
    from Asgard.Bragi.Architecture.services._generic_solid_checks import check_srp_method_count
    lines = source.splitlines()
    violations = check_srp_method_count(file_path, lines, language)
    return [_to_dict("solid.srp-lcom4", v) for v in violations]


# ---------------------------------------------------------------------------
# ISP — Interface method count
# ---------------------------------------------------------------------------

_ISP_THRESHOLD = 12

_ISP_QUERIES: Dict[str, str] = {
    "python": """
(class_definition
  name: (identifier) @class.name) @class.def
""",
    "java": """
(interface_declaration
  name: (identifier) @interface.name
  body: (interface_body
    (method_declaration name: (identifier) @method.name))) @interface.def
""",
    "typescript": """
(interface_declaration
  name: (type_identifier) @interface.name) @interface.def
""",
    "javascript": """
(interface_declaration
  name: (type_identifier) @interface.name) @interface.def
""",
}


def check_isp_fat_interface(
    file_path: str,
    source: str,
    language: str,
    rules: Dict[str, bool],
) -> List[Dict]:
    if not rules.get("solid.isp-fat-interface", True):
        return []
    if not is_available(language):
        return _fallback_isp(file_path, source, language, rules)

    source_bytes = source.encode("utf-8")
    root = parse_source(source_bytes, language)
    if root is None:
        return _fallback_isp(file_path, source, language, rules)

    results = []

    if language == "python":
        results = _check_isp_python(root, source_bytes, file_path)
    elif language == "java":
        results = _check_isp_java(root, source_bytes, file_path)
    elif language in ("typescript", "javascript"):
        results = _check_isp_typescript(root, source_bytes, file_path, language)
    else:
        return _fallback_isp(file_path, source, language, rules)

    return results


def _check_isp_python(root_node, source_bytes: bytes, file_path: str) -> List[Dict]:
    try:
        from tree_sitter import Query  # noqa: PLC0415
        from Asgard.Heimdall.treesitter._language_loader import get_language_object  # noqa: PLC0415
        lang_obj = get_language_object("python")
        if lang_obj is None:
            return []
    except ImportError:
        return []

    # Find abstract classes (inherit from ABC or have abstractmethod decorators)
    violations = []

    def _walk(node):
        if node.type == "class_definition":
            _check_python_abstract_class(node, source_bytes, violations)
        for child in node.children:
            _walk(child)

    _walk(root_node)
    return violations


def _check_python_abstract_class(class_node, source_bytes: bytes, violations: list) -> None:
    try:
        from tree_sitter import Query  # noqa: PLC0415
        from Asgard.Heimdall.treesitter._language_loader import get_language_object  # noqa: PLC0415
        lang_obj = get_language_object("python")
        if lang_obj is None:
            return
    except ImportError:
        return

    # Check if class inherits from ABC or Protocol
    bases_text = ""
    for child in class_node.children:
        if child.type == "argument_list":
            bases_text = source_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
            break

    is_abstract = "ABC" in bases_text or "Protocol" in bases_text

    if not is_abstract:
        return

    class_name_node = None
    for child in class_node.children:
        if child.type == "identifier":
            class_name_node = child
            break
    class_name = source_bytes[class_name_node.start_byte:class_name_node.end_byte].decode("utf-8", errors="replace") if class_name_node else "<class>"

    # Count abstract methods
    abstract_methods_q = Query(
        lang_obj,
        "(decorated_definition (decorator (identifier) @dec) definition: (function_definition name: (identifier) @method.name)) @decorated"
    )
    captures = abstract_methods_q.captures(class_node)
    count = 0
    if isinstance(captures, dict):
        dec_nodes = captures.get("dec", [])
        if not isinstance(dec_nodes, list):
            dec_nodes = [dec_nodes]
        for dec_node in dec_nodes:
            dec_text = source_bytes[dec_node.start_byte:dec_node.end_byte].decode("utf-8", errors="replace")
            if "abstractmethod" in dec_text:
                count += 1
    elif isinstance(captures, list):
        for node, name in captures:
            if name == "dec":
                dec_text = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
                if "abstractmethod" in dec_text:
                    count += 1

    if count > _ISP_THRESHOLD:
        violations.append({
            "rule_id": "solid.isp-fat-interface",
            "line": class_node.start_point[0] + 1,
            "message": (
                f"Abstract class/Protocol '{class_name}' declares {count} abstract methods "
                f"(threshold: {_ISP_THRESHOLD}). Consider splitting into smaller interfaces."
            ),
            "severity": "warning",
        })


def _check_isp_java(root_node, source_bytes: bytes, file_path: str) -> List[Dict]:
    try:
        from tree_sitter import Query  # noqa: PLC0415
        from Asgard.Heimdall.treesitter._language_loader import get_language_object  # noqa: PLC0415
        lang_obj = get_language_object("java")
        if lang_obj is None:
            return []
    except ImportError:
        return []

    violations = []

    def _walk(node):
        if node.type == "interface_declaration":
            _check_java_interface(node, source_bytes, lang_obj, violations)
        for child in node.children:
            _walk(child)

    _walk(root_node)
    return violations


def _check_java_interface(iface_node, source_bytes: bytes, lang_obj, violations: list) -> None:
    from tree_sitter import Query  # noqa: PLC0415

    name_node = None
    for child in iface_node.children:
        if child.type == "identifier":
            name_node = child
            break
    iface_name = source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace") if name_node else "<interface>"

    method_q = Query(lang_obj, "(method_declaration name: (identifier) @method.name) @method.def")
    captures = method_q.captures(iface_node)
    count = 0
    if isinstance(captures, dict):
        nodes = captures.get("method.name", [])
        count = len(nodes) if isinstance(nodes, list) else (1 if nodes else 0)
    elif isinstance(captures, list):
        count = sum(1 for _, name in captures if name == "method.name")

    if count > _ISP_THRESHOLD:
        violations.append({
            "rule_id": "solid.isp-fat-interface",
            "line": iface_node.start_point[0] + 1,
            "message": (
                f"Interface '{iface_name}' declares {count} methods "
                f"(threshold: {_ISP_THRESHOLD}). Consider splitting into smaller interfaces."
            ),
            "severity": "warning",
        })


def _check_isp_typescript(root_node, source_bytes: bytes, file_path: str, language: str) -> List[Dict]:
    try:
        from tree_sitter import Query  # noqa: PLC0415
        from Asgard.Heimdall.treesitter._language_loader import get_language_object  # noqa: PLC0415
        lang_obj = get_language_object(language)
        if lang_obj is None:
            return []
    except ImportError:
        return []

    violations = []

    def _walk(node):
        if node.type == "interface_declaration":
            _check_ts_interface(node, source_bytes, lang_obj, violations)
        for child in node.children:
            _walk(child)

    _walk(root_node)
    return violations


def _check_ts_interface(iface_node, source_bytes: bytes, lang_obj, violations: list) -> None:
    from tree_sitter import Query  # noqa: PLC0415

    name_node = None
    for child in iface_node.children:
        if child.type in ("type_identifier", "identifier"):
            name_node = child
            break
    iface_name = source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace") if name_node else "<interface>"

    method_q = Query(lang_obj, "(method_signature name: (property_identifier) @method.name) @method.sig")
    captures = method_q.captures(iface_node)
    count = 0
    if isinstance(captures, dict):
        nodes = captures.get("method.name", [])
        count = len(nodes) if isinstance(nodes, list) else (1 if nodes else 0)
    elif isinstance(captures, list):
        count = sum(1 for _, name in captures if name == "method.name")

    if count > _ISP_THRESHOLD:
        violations.append({
            "rule_id": "solid.isp-fat-interface",
            "line": iface_node.start_point[0] + 1,
            "message": (
                f"Interface '{iface_name}' declares {count} methods "
                f"(threshold: {_ISP_THRESHOLD}). Consider splitting into smaller interfaces."
            ),
            "severity": "warning",
        })


def _fallback_isp(file_path: str, source: str, language: str, rules: Dict[str, bool]) -> List[Dict]:
    from Asgard.Bragi.Architecture.services._generic_solid_checks import check_isp_interface_size
    lines = source.splitlines()
    violations = check_isp_interface_size(file_path, lines, language)
    return [_to_dict("solid.isp-fat-interface", v) for v in violations]


# ---------------------------------------------------------------------------
# DIP — Concrete instantiation detection
# ---------------------------------------------------------------------------

_FACTORY_RE = re.compile(r"Factory|Builder|Provider|Container|Registry", re.IGNORECASE)

_DIP_NEW_QUERIES: Dict[str, str] = {
    "python": """
(call function: (identifier) @type.name) @call
""",
    "java": """
(object_creation_expression type: (type_identifier) @type.name) @new.expr
""",
    "typescript": """
(new_expression constructor: (identifier) @type.name) @new.expr
""",
    "javascript": """
(new_expression constructor: (identifier) @type.name) @new.expr
""",
}

# Names that strongly signal a concrete class (not an abstract/interface type)
_CONCRETE_SUFFIXES = re.compile(
    r"(?:Repository|Service|Dao|Manager|Handler|Controller|Client|Adapter|Gateway|Impl)$"
)


def check_dip_concrete_dependency(
    file_path: str,
    source: str,
    language: str,
    rules: Dict[str, bool],
) -> List[Dict]:
    if not rules.get("solid.dip-concrete-dependency", True):
        return []
    if not is_available(language) or language not in _DIP_NEW_QUERIES:
        return _fallback_dip(file_path, source, language, rules)

    source_bytes = source.encode("utf-8")
    root = parse_source(source_bytes, language)
    if root is None:
        return _fallback_dip(file_path, source, language, rules)

    # Determine if file is inside a factory/builder context by checking top-level class names
    enclosing_class = _get_top_level_class_name(root, source_bytes, language)
    if enclosing_class and _FACTORY_RE.search(enclosing_class):
        return []

    query_str = _DIP_NEW_QUERIES[language]
    matches = run_query_all(root, query_str, source_bytes, language)

    violations = []
    for match in matches:
        type_info = match.get("type.name")
        if type_info is None:
            continue
        type_name = type_info["text"]
        line = type_info["line"] + 1

        if _CONCRETE_SUFFIXES.search(type_name):
            violations.append({
                "rule_id": "solid.dip-concrete-dependency",
                "line": line,
                "message": (
                    f"Concrete instantiation of '{type_name}' detected outside factory context. "
                    "Depend on abstractions, not concretions."
                ),
                "severity": "warning",
            })

    return violations


def _get_top_level_class_name(root_node, source_bytes: bytes, language: str) -> str:
    """Return the name of the first top-level class definition, or empty string."""
    type_map = {
        "python": "class_definition",
        "java": "class_declaration",
        "typescript": "class_declaration",
        "javascript": "class_declaration",
    }
    node_type = type_map.get(language, "class_declaration")
    name_node_type = "type_identifier" if language in ("typescript",) else "identifier"

    for child in root_node.children:
        if child.type == node_type:
            for subchild in child.children:
                if subchild.type in ("identifier", "type_identifier"):
                    return source_bytes[subchild.start_byte:subchild.end_byte].decode("utf-8", errors="replace")
    return ""


def _fallback_dip(file_path: str, source: str, language: str, rules: Dict[str, bool]) -> List[Dict]:
    from Asgard.Bragi.Architecture.services._generic_solid_checks import check_dip_concrete_instantiation
    lines = source.splitlines()
    violations = check_dip_concrete_instantiation(file_path, lines, language)
    return [_to_dict("solid.dip-concrete-dependency", v) for v in violations]


# ---------------------------------------------------------------------------
# OCP — Type-dispatch detection
# ---------------------------------------------------------------------------

_OCP_QUERIES: Dict[str, str] = {
    "python": """
(call function: (identifier) @call.name
  (#match? @call.name "^(isinstance|type)$")) @type.check
""",
    "java": """
(instanceof_expression) @instanceof
""",
    "typescript": """
(binary_expression operator: "instanceof" right: (identifier) @type.name) @instanceof
""",
    "javascript": """
(binary_expression operator: "instanceof" right: (identifier) @type.name) @instanceof
""",
}


def check_ocp_type_dispatch(
    file_path: str,
    source: str,
    language: str,
    rules: Dict[str, bool],
) -> List[Dict]:
    if not rules.get("solid.ocp-type-dispatch", True):
        return []
    if not is_available(language) or language not in _OCP_QUERIES:
        return _fallback_ocp(file_path, source, language, rules)

    source_bytes = source.encode("utf-8")
    root = parse_source(source_bytes, language)
    if root is None:
        return _fallback_ocp(file_path, source, language, rules)

    if language == "python":
        return _check_ocp_python(root, source_bytes)

    query_str = _OCP_QUERIES[language]
    matches = run_query_all(root, query_str, source_bytes, language)

    violations = []
    seen_lines: set = set()
    for match in matches:
        info = match.get("instanceof") or match.get("type.name") or next(iter(match.values()), None)
        if info is None:
            continue
        line = info["line"] + 1
        if line in seen_lines:
            continue
        seen_lines.add(line)
        violations.append({
            "rule_id": "solid.ocp-type-dispatch",
            "line": line,
            "message": (
                "Explicit type dispatch detected (instanceof/type check). "
                "This requires modification when new types are added, violating OCP. "
                "Prefer polymorphism."
            ),
            "severity": "warning",
        })

    return violations


def _check_ocp_python(root_node, source_bytes: bytes) -> List[Dict]:
    try:
        from tree_sitter import Query  # noqa: PLC0415
        from Asgard.Heimdall.treesitter._language_loader import get_language_object  # noqa: PLC0415
        lang_obj = get_language_object("python")
        if lang_obj is None:
            return []
    except ImportError:
        return []

    # isinstance() and type() == comparisons
    isinstance_q = Query(
        lang_obj,
        "(call function: (identifier) @func.name) @call"
    )
    type_eq_q = Query(
        lang_obj,
        "(comparison_operator left: (call function: (identifier) @func.name) @call) @comparison"
    )

    violations = []
    seen_lines: set = set()

    for q in (isinstance_q, type_eq_q):
        captures = q.captures(root_node)
        if isinstance(captures, dict):
            nodes = captures.get("func.name", [])
            if not isinstance(nodes, list):
                nodes = [nodes]
            for node in nodes:
                name = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
                if name in ("isinstance", "type"):
                    line = node.start_point[0] + 1
                    if line not in seen_lines:
                        seen_lines.add(line)
                        violations.append({
                            "rule_id": "solid.ocp-type-dispatch",
                            "line": line,
                            "message": (
                                f"Explicit type dispatch via '{name}()' detected. "
                                "This requires modification when new types are added, violating OCP. "
                                "Prefer polymorphism."
                            ),
                            "severity": "warning",
                        })
        elif isinstance(captures, list):
            for node, capture_name in captures:
                if capture_name == "func.name":
                    name = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
                    if name in ("isinstance", "type"):
                        line = node.start_point[0] + 1
                        if line not in seen_lines:
                            seen_lines.add(line)
                            violations.append({
                                "rule_id": "solid.ocp-type-dispatch",
                                "line": line,
                                "message": (
                                    f"Explicit type dispatch via '{name}()' detected. "
                                    "This requires modification when new types are added, violating OCP. "
                                    "Prefer polymorphism."
                                ),
                                "severity": "warning",
                            })

    return violations


def _fallback_ocp(file_path: str, source: str, language: str, rules: Dict[str, bool]) -> List[Dict]:
    from Asgard.Bragi.Architecture.services._generic_solid_checks import check_ocp_type_checking
    lines = source.splitlines()
    violations = check_ocp_type_checking(file_path, lines, language)
    return [_to_dict("solid.ocp-type-dispatch", v) for v in violations]


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _to_dict(rule_id: str, violation) -> Dict:
    return {
        "rule_id": rule_id,
        "line": violation.line_number,
        "message": violation.message,
        "severity": violation.severity.value if hasattr(violation.severity, "value") else str(violation.severity),
    }
