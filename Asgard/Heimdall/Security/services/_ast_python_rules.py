"""Python pilot rules for the dual-engine (AST + regex fallback) migration.

Wave-1 rules per the tree-sitter migration plan:

- ``check_eval_exec``            — ``eval()`` / ``exec()`` usage (CWE-95)
- ``check_yaml_unsafe_load``     — ``yaml.load`` without a ``Loader`` (CWE-502)
- ``check_subprocess_shell_true``— ``subprocess.*(..., shell=True)`` (CWE-78)
- ``check_route_missing_auth``   — route handler without auth decorator (CWE-306)
- ``check_injection_sink_candidates`` — non-literal args flowing into known
  sinks; INFO-level pre-filter feeding the taint-analysis plan.

Each rule is a regex implementation wrapped by ``@with_ast_fallback`` with a
tree-sitter AST implementation.  Both engines return the same plain-dict
finding shape (primitives only — no tree-sitter nodes leak out):

    {"rule_id", "line" (1-based), "col", "message", "severity",
     "confidence", "cwe_id", "engine"}

Lexical rules (secrets, TODO scanning, .env parsing) intentionally stay
regex — AST hurts recall there.  No framework- or organisation-specific
assumptions: decorator/sink names below are public-framework conventions.
"""
import re
from typing import Any, Dict, List, Optional, Sequence

from Asgard.Heimdall.treesitter.ast_engine import with_ast_fallback
from Asgard.Heimdall.treesitter.file_context import FileParseContext

Finding = Dict[str, Any]


def _finding(rule_id: str, line: int, message: str, severity: str,
             confidence: float, cwe_id: str, engine: str, col: int = 0) -> Finding:
    return {
        "rule_id": rule_id,
        "line": line,
        "col": col,
        "message": message,
        "severity": severity,
        "confidence": confidence,
        "cwe_id": cwe_id,
        "engine": engine,
    }


# ---------------------------------------------------------------------------
# AST helpers (nodes never escape this module)
# ---------------------------------------------------------------------------

def _iter_nodes(root):
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(node.children)


def _callee_parts(call_node, ctx: FileParseContext):
    """Return (object_text, attr_or_name_text) for a ``call`` node."""
    fn = call_node.child_by_field_name("function")
    if fn is None:
        return "", ""
    if fn.type == "identifier":
        return "", ctx.node_text(fn)
    if fn.type == "attribute":
        obj = fn.child_by_field_name("object")
        attr = fn.child_by_field_name("attribute")
        return ctx.node_text(obj), ctx.node_text(attr)
    return "", ""


_LITERAL_TYPES = {"string", "integer", "float", "true", "false", "none", "concatenated_string"}


def _is_literal_expr(node) -> bool:
    """True when *node* is a static literal (no interpolation)."""
    if node.type not in _LITERAL_TYPES:
        return False
    if node.type in ("string", "concatenated_string"):
        # f-strings parse as `string` containing `interpolation` children
        return not any(n.type == "interpolation" for n in _iter_nodes(node))
    return True


def _positional_args(call_node):
    args = call_node.child_by_field_name("arguments")
    if args is None:
        return []
    return [c for c in args.children
            if c.is_named and c.type not in ("keyword_argument", "comment")]


def _keyword_args(call_node, ctx: FileParseContext):
    args = call_node.child_by_field_name("arguments")
    out = {}
    if args is None:
        return out
    for c in args.children:
        if c.type == "keyword_argument":
            name = c.child_by_field_name("name")
            value = c.child_by_field_name("value")
            out[ctx.node_text(name)] = value
    return out


def _line_of(node) -> int:
    return node.start_point[0] + 1


def _skip(ctx: FileParseContext, node) -> bool:
    return ctx.intersects_error(node.start_point[0], node.end_point[0])


def _is_comment_line(line: str) -> bool:
    return line.lstrip().startswith("#")


# ---------------------------------------------------------------------------
# Rule 1: eval / exec usage
# ---------------------------------------------------------------------------

_EVAL_EXEC_RULE = "python.eval-exec-usage"
_EVAL_EXEC_RE = re.compile(r"(?<![\w.])(eval|exec)\s*\(")


def _eval_exec_ast(file_path, ctx: FileParseContext) -> List[Finding]:
    findings: List[Finding] = []
    for node in _iter_nodes(ctx.root):
        if node.type != "call" or _skip(ctx, node):
            continue
        obj, name = _callee_parts(node, ctx)
        if obj == "" and name in ("eval", "exec"):
            pos = _positional_args(node)
            dynamic = any(not _is_literal_expr(a) for a in pos)
            findings.append(_finding(
                _EVAL_EXEC_RULE, _line_of(node),
                f"Use of '{name}()' — dynamic code execution."
                + (" Argument is not a static literal." if dynamic else ""),
                "high" if dynamic else "medium",
                0.9 if dynamic else 0.7,
                "CWE-95", "ast", node.start_point[1],
            ))
    return findings


@with_ast_fallback("python", _eval_exec_ast)
def check_eval_exec(file_path, lines: Sequence[str], enabled: bool = True, **kwargs) -> List[Finding]:
    findings: List[Finding] = []
    for i, line in enumerate(lines, start=1):
        if _is_comment_line(line):
            continue
        for match in _EVAL_EXEC_RE.finditer(line):
            findings.append(_finding(
                _EVAL_EXEC_RULE, i,
                f"Use of '{match.group(1)}()' — dynamic code execution.",
                "medium", 0.5, "CWE-95", "regex", match.start(),
            ))
    return findings


# ---------------------------------------------------------------------------
# Rule 2: yaml.load without Loader
# ---------------------------------------------------------------------------

_YAML_LOAD_RULE = "python.yaml-unsafe-load"
_YAML_LOAD_RE = re.compile(r"\byaml\.load\s*\(")


def _yaml_load_ast(file_path, ctx: FileParseContext) -> List[Finding]:
    findings: List[Finding] = []
    for node in _iter_nodes(ctx.root):
        if node.type != "call" or _skip(ctx, node):
            continue
        obj, name = _callee_parts(node, ctx)
        if obj != "yaml" or name != "load":
            continue
        kwargs_map = _keyword_args(node, ctx)
        positional = _positional_args(node)
        loader_node = kwargs_map.get("Loader") or (positional[1] if len(positional) > 1 else None)
        if loader_node is None:
            findings.append(_finding(
                _YAML_LOAD_RULE, _line_of(node),
                "yaml.load() without an explicit Loader deserializes arbitrary "
                "objects. Use yaml.safe_load() or Loader=yaml.SafeLoader.",
                "high", 0.9, "CWE-502", "ast", node.start_point[1],
            ))
        elif "Unsafe" in ctx.node_text(loader_node):
            findings.append(_finding(
                _YAML_LOAD_RULE, _line_of(node),
                "yaml.load() with UnsafeLoader deserializes arbitrary objects.",
                "high", 0.9, "CWE-502", "ast", node.start_point[1],
            ))
    return findings


@with_ast_fallback("python", _yaml_load_ast)
def check_yaml_unsafe_load(file_path, lines: Sequence[str], enabled: bool = True, **kwargs) -> List[Finding]:
    findings: List[Finding] = []
    for i, line in enumerate(lines, start=1):
        if _is_comment_line(line):
            continue
        match = _YAML_LOAD_RE.search(line)
        if match and "Loader" not in line and "safe_load" not in line:
            findings.append(_finding(
                _YAML_LOAD_RULE, i,
                "yaml.load() without an explicit Loader deserializes arbitrary "
                "objects. Use yaml.safe_load() or Loader=yaml.SafeLoader.",
                "high", 0.6, "CWE-502", "regex", match.start(),
            ))
    return findings


# ---------------------------------------------------------------------------
# Rule 3: subprocess shell=True
# ---------------------------------------------------------------------------

_SHELL_TRUE_RULE = "python.subprocess-shell-true"
_SUBPROCESS_FNS = {"run", "call", "check_call", "check_output", "Popen", "getoutput", "getstatusoutput"}
_SHELL_TRUE_RE = re.compile(
    r"\b(?:subprocess\.(?:run|call|check_call|check_output|Popen)|Popen)\s*\([^)]*shell\s*=\s*True"
)


def _subprocess_shell_ast(file_path, ctx: FileParseContext) -> List[Finding]:
    findings: List[Finding] = []
    for node in _iter_nodes(ctx.root):
        if node.type != "call" or _skip(ctx, node):
            continue
        obj, name = _callee_parts(node, ctx)
        is_subprocess_call = (obj == "subprocess" and name in _SUBPROCESS_FNS) or \
                             (obj == "" and name == "Popen")
        if not is_subprocess_call:
            continue
        shell_value = _keyword_args(node, ctx).get("shell")
        if shell_value is None or shell_value.type != "true":
            continue
        positional = _positional_args(node)
        static_cmd = bool(positional) and _is_literal_expr(positional[0])
        findings.append(_finding(
            _SHELL_TRUE_RULE, _line_of(node),
            "subprocess with shell=True"
            + (" and a non-literal command — command injection risk."
               if not static_cmd else " (static command literal)."),
            "low" if static_cmd else "high",
            0.6 if static_cmd else 0.85,
            "CWE-78", "ast", node.start_point[1],
        ))
    return findings


@with_ast_fallback("python", _subprocess_shell_ast)
def check_subprocess_shell_true(file_path, lines: Sequence[str], enabled: bool = True, **kwargs) -> List[Finding]:
    findings: List[Finding] = []
    for i, line in enumerate(lines, start=1):
        if _is_comment_line(line):
            continue
        match = _SHELL_TRUE_RE.search(line)
        if match:
            findings.append(_finding(
                _SHELL_TRUE_RULE, i,
                "subprocess with shell=True — command injection risk.",
                "high", 0.6, "CWE-78", "regex", match.start(),
            ))
    return findings


# ---------------------------------------------------------------------------
# Rule 4: route handler without auth decorator
# ---------------------------------------------------------------------------

_ROUTE_AUTH_RULE = "python.route-missing-auth"
_ROUTE_DEC_RE = re.compile(r"\.\s*(?:route|get|post|put|delete|patch|websocket)\s*\(")
_AUTH_DEC_RE = re.compile(
    r"(login_required|jwt_required|auth|permission|requires|protected|secured)",
    re.IGNORECASE,
)


def _route_auth_ast(file_path, ctx: FileParseContext) -> List[Finding]:
    findings: List[Finding] = []
    for node in _iter_nodes(ctx.root):
        if node.type != "decorated_definition" or _skip(ctx, node):
            continue
        decorators = [ctx.node_text(c) for c in node.children if c.type == "decorator"]
        if not any(_ROUTE_DEC_RE.search(d) for d in decorators):
            continue
        if any(_AUTH_DEC_RE.search(d) for d in decorators):
            continue
        definition = node.child_by_field_name("definition")
        line = _line_of(definition if definition is not None else node)
        findings.append(_finding(
            _ROUTE_AUTH_RULE, line,
            "Route handler has no authentication/authorization decorator. "
            "Verify this endpoint is intentionally public.",
            "medium", 0.5, "CWE-306", "ast",
        ))
    return findings


@with_ast_fallback("python", _route_auth_ast)
def check_route_missing_auth(file_path, lines: Sequence[str], enabled: bool = True, **kwargs) -> List[Finding]:
    findings: List[Finding] = []
    pending: List[str] = []  # decorator lines above the next def
    for i, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("@"):
            pending.append(line)
            continue
        if line.startswith(("def ", "async def ")):
            if pending and any(_ROUTE_DEC_RE.search(d) for d in pending) \
                    and not any(_AUTH_DEC_RE.search(d) for d in pending):
                findings.append(_finding(
                    _ROUTE_AUTH_RULE, i,
                    "Route handler has no authentication/authorization decorator. "
                    "Verify this endpoint is intentionally public.",
                    "medium", 0.4, "CWE-306", "regex",
                ))
            pending = []
        elif line and not line.startswith("#"):
            pending = []
    return findings


# ---------------------------------------------------------------------------
# Rule 5: injection sink pre-filter (feeds taint analysis)
# ---------------------------------------------------------------------------

_SINK_RULE = "python.injection-sink-candidate"
_SINK_NAMES = {"execute", "executemany", "executescript", "system", "popen"}
_SINK_RE = re.compile(r"\b(execute|executemany|executescript|system|popen)\s*\(")
_PURE_LITERAL_CALL_RE = re.compile(
    r"\b(?:execute|executemany|executescript|system|popen)\s*\(\s*[rbu]*['\"][^'\"{}%]*['\"]\s*[,)]"
)


def _sink_candidates_ast(file_path, ctx: FileParseContext) -> List[Finding]:
    findings: List[Finding] = []
    for node in _iter_nodes(ctx.root):
        if node.type != "call" or _skip(ctx, node):
            continue
        _obj, name = _callee_parts(node, ctx)
        if name not in _SINK_NAMES:
            continue
        positional = _positional_args(node)
        if not positional or _is_literal_expr(positional[0]):
            continue
        findings.append(_finding(
            _SINK_RULE, _line_of(node),
            f"Non-literal expression flows into sink '{name}()' — "
            "candidate for taint analysis.",
            "info", 0.3, "CWE-89", "ast", node.start_point[1],
        ))
    return findings


@with_ast_fallback("python", _sink_candidates_ast)
def check_injection_sink_candidates(file_path, lines: Sequence[str], enabled: bool = True, **kwargs) -> List[Finding]:
    findings: List[Finding] = []
    for i, line in enumerate(lines, start=1):
        if _is_comment_line(line):
            continue
        match = _SINK_RE.search(line)
        if match and not _PURE_LITERAL_CALL_RE.search(line):
            findings.append(_finding(
                _SINK_RULE, i,
                f"Possible non-literal expression flows into sink "
                f"'{match.group(1)}()' — candidate for taint analysis.",
                "info", 0.2, "CWE-89", "regex", match.start(),
            ))
    return findings


#: All wave-1 pilot rules (used by orchestrators and the benchmark harness).
PYTHON_PILOT_RULES = [
    check_eval_exec,
    check_yaml_unsafe_load,
    check_subprocess_shell_true,
    check_route_missing_auth,
    check_injection_sink_candidates,
]


def run_python_pilot_rules(
    file_path,
    lines: Sequence[str],
    parse_context: Optional[FileParseContext] = None,
) -> List[Finding]:
    """Run every wave-1 rule with a shared single-parse context."""
    from Asgard.Heimdall.treesitter.ast_engine import is_engine_enabled  # noqa: PLC0415
    if parse_context is None and is_engine_enabled("python"):
        parse_context = FileParseContext.parse(file_path, lines, "python")
    findings: List[Finding] = []
    for rule in PYTHON_PILOT_RULES:
        findings.extend(rule(file_path, lines, True, parse_context=parse_context))
    return findings
