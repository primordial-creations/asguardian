"""
Test-Context Engine (plan 08 Part B, DEEPTHINK_08 / DEEPTHINK_03).

Determines whether a finding sits in test code and routes its severity
through the contextual severity matrix. Detection is language-agnostic:
path heuristics use word-boundary directory matching plus filename
conventions covering Python, JS/TS, Go, Java, Ruby, etc. — no assumptions
about any particular organisation's repository layout.

Context determination (composite, in precedence order):

1. Override: ``strict_scan_paths`` regexes (``.heimdall.yml``) force
   PRODUCTION; inline pragma ``# heimdall: enforce`` strips context tags
   for the annotated line/scope.
2. File-level TEST_UNIT / TEST_INTEGRATION: the path must contain a test
   *directory* segment (word-boundary match — ``/ab_testing/`` does NOT
   qualify) AND the filename must follow a test naming convention
   (``test_flight_api.py`` in a prod dir does NOT qualify). Well-known
   test-infrastructure filenames (``conftest.py`` …) qualify standalone,
   as do compiler-enforced conventions (Go ``*_test.go``).
3. AST-level TEST_FUNCTION tainting (Python) for files not tagged above:
   test classes, pytest/mock fixture decorators, and ``test_*`` functions
   containing asserts push a context that pops with AST scope, so a prod
   helper in a test file and a mock factory in ``utils.py`` are each
   handled correctly.

Contextual severity matrix (applied post-detection, pre-scoring):

    category                     TEST_UNIT/TEST_FUNCTION   TEST_INTEGRATION
    data-flow injection          SUPPRESS                  SUPPRESS
    weak crypto / weak PRNG      SUPPRESS                  SUPPRESS
    command injection / SSRF     SUPPRESS                  DOWNGRADE -> low
    network config               SUPPRESS                  DOWNGRADE -> info
    hardcoded secrets            NEVER suppressed (dummy filter, then CRITICAL)

Suppressed findings are retained with ``suppressed_by_context=True`` —
they are excluded from score (plan 06) and gate (plan 09), never deleted.
"""

import ast
import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, List, Optional, Sequence, Tuple


class ContextTag(str, Enum):
    """Code context a finding is located in."""
    PRODUCTION = "production"
    TEST_UNIT = "test_unit"
    TEST_INTEGRATION = "test_integration"
    TEST_FUNCTION = "test_function"


class ContextAction(str, Enum):
    """Routing action from the contextual severity matrix."""
    KEEP = "keep"
    SUPPRESS = "suppress"
    DOWNGRADE_LOW = "downgrade_low"
    DOWNGRADE_INFO = "downgrade_info"


class FindingKind(str, Enum):
    """Coarse finding families the severity matrix routes on."""
    DATA_FLOW_INJECTION = "data_flow_injection"
    WEAK_CRYPTO = "weak_crypto"
    COMMAND_INJECTION = "command_injection"
    SSRF = "ssrf"
    NETWORK_CONFIG = "network_config"
    HARDCODED_SECRET = "hardcoded_secret"
    OTHER = "other"


# --------------------------------------------------------------------------
# File-level heuristics (language-agnostic)
# --------------------------------------------------------------------------

# Word-boundary directory segment match: prevents /ab_testing/ or
# /protest/ from qualifying.
_TEST_DIR_RE = re.compile(r"(?:^|/)(tests?|testing|specs?|__tests__|__mocks__)(?:/|$)", re.IGNORECASE)
_INTEGRATION_DIR_RE = re.compile(r"(?:^|/)(integration|e2e|system|functional)(?:/|$)", re.IGNORECASE)

# Filename conventions across languages (extension-agnostic where safe).
_TEST_FILE_RE = re.compile(
    r"(?:"
    r"^test_.*\.\w+$"            # Python test_x.py (and test_x.js …)
    r"|.*_test\.\w+$"            # x_test.py / x_test.go / x_test.rb
    r"|.*\.(?:test|spec)\.\w+$"  # x.test.ts / x.spec.js
    r"|^.*Tests?\.(?:java|kt|cs|swift|scala)$"  # FooTest.java / FooTests.cs
    r")",
    re.IGNORECASE,
)

# Test-infrastructure files that qualify standalone (no test dir needed).
_STANDALONE_TEST_FILES = frozenset({
    "conftest.py", "noxfile.py", "factories.py", "mocks.py",
    "jest.setup.js", "jest.setup.ts", "setup_test.go",
})

# Compiler/runner-enforced test-only suffixes: safe standalone because the
# toolchain itself excludes them from production builds.
_STANDALONE_TEST_SUFFIX_RE = re.compile(r"(?:_test\.go|\.(?:test|spec)\.[jt]sx?)$", re.IGNORECASE)


def _norm(path: str) -> str:
    return str(path).replace("\\", "/")


def classify_file_context(
    file_path: str,
    strict_scan_paths: Sequence[str] = (),
) -> ContextTag:
    """
    File-level context classification.

    ``strict_scan_paths`` regexes (from ``.heimdall.yml``) bypass the
    engine entirely: matching paths are always PRODUCTION so
    security-regression tests stay fully scannable.
    """
    path = _norm(file_path)
    for pattern in strict_scan_paths:
        try:
            if re.search(pattern, path):
                return ContextTag.PRODUCTION
        except re.error:
            continue
    name = path.rsplit("/", 1)[-1]

    is_test_file = False
    if name.lower() in _STANDALONE_TEST_FILES:
        is_test_file = True
    elif _STANDALONE_TEST_SUFFIX_RE.search(name):
        is_test_file = True
    elif _TEST_DIR_RE.search(path) and _TEST_FILE_RE.match(name):
        # Conjunction: test directory AND test filename. Prevents both the
        # /ab_testing/ dir false positive and the prod-script
        # test_db_connection.py false suppression.
        is_test_file = True

    if not is_test_file:
        return ContextTag.PRODUCTION
    if _INTEGRATION_DIR_RE.search(path):
        return ContextTag.TEST_INTEGRATION
    return ContextTag.TEST_UNIT


def is_test_context(file_path: str, strict_scan_paths: Sequence[str] = ()) -> bool:
    """True if the file is any flavour of test context."""
    return classify_file_context(file_path, strict_scan_paths) is not ContextTag.PRODUCTION


# --------------------------------------------------------------------------
# Inline pragma
# --------------------------------------------------------------------------

_ENFORCE_PRAGMA_RE = re.compile(r"#\s*heimdall\s*:\s*enforce\b", re.IGNORECASE)
_ENFORCE_PRAGMA_SLASH_RE = re.compile(r"//\s*heimdall\s*:\s*enforce\b", re.IGNORECASE)


def _enforced_lines(lines: Sequence[str]) -> frozenset:
    """1-based line numbers annotated with ``# heimdall: enforce``."""
    out = set()
    for i, line in enumerate(lines, start=1):
        if _ENFORCE_PRAGMA_RE.search(line) or _ENFORCE_PRAGMA_SLASH_RE.search(line):
            out.add(i)
    return frozenset(out)


# --------------------------------------------------------------------------
# AST-level TEST_FUNCTION tainting (Python)
# --------------------------------------------------------------------------

_TEST_BASE_CLASS_RE = re.compile(r"(?:^|\.)(?:TestCase|IsolatedAsyncioTestCase|SimpleTestCase|TransactionTestCase|LiveServerTestCase)$")
_TEST_DECORATORS = (
    "pytest.fixture", "fixture",
    "patch", "mock.patch", "unittest.mock.patch",
    "responses.activate",
    "given", "hypothesis.given",
    "pytest.mark",
    "freeze_time",
)


def _dec_name(node: ast.expr) -> str:
    """Dotted name of a decorator expression (calls unwrapped)."""
    if isinstance(node, ast.Call):
        node = node.func
    parts: List[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _is_test_decorator(name: str) -> bool:
    for known in _TEST_DECORATORS:
        if name == known or name.startswith(known + "."):
            return True
    return False


def _contains_assert(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Assert):
            return True
        if isinstance(child, ast.Call):
            func = child.func
            attr = func.attr if isinstance(func, ast.Attribute) else ""
            if attr.startswith("assert"):
                return True
    return False


@dataclass(frozen=True)
class _TaggedRange:
    start: int
    end: int
    tag: ContextTag


class TestContextIndex:
    """
    Per-file context index: maps a line number to its context tag.

    Combines the file-level tag, AST-level TEST_FUNCTION scope ranges
    (context pushes/pops with AST scope), and the ``# heimdall: enforce``
    pragma (which strips context tags for that line and, when placed on a
    scope's definition line, the whole scope).
    """

    def __init__(
        self,
        file_tag: ContextTag,
        ranges: Sequence[_TaggedRange] = (),
        enforced: frozenset = frozenset(),
    ):
        self.file_tag = file_tag
        self._ranges = sorted(ranges, key=lambda r: (r.start, -r.end))
        self._enforced = enforced

    @classmethod
    def for_python_source(
        cls,
        file_path: str,
        source: str,
        strict_scan_paths: Sequence[str] = (),
        tree: Optional[ast.AST] = None,
    ) -> "TestContextIndex":
        lines = source.splitlines()
        enforced = _enforced_lines(lines)
        file_tag = classify_file_context(file_path, strict_scan_paths)
        ranges: List[_TaggedRange] = []
        if file_tag is ContextTag.PRODUCTION:
            # AST-level tainting only matters for files not already tagged.
            if tree is None:
                try:
                    tree = ast.parse(source)
                except SyntaxError:
                    tree = None
            if tree is not None:
                ranges = cls._collect_test_scopes(tree)
        return cls(file_tag, ranges, enforced)

    @staticmethod
    def _collect_test_scopes(tree: ast.AST) -> List[_TaggedRange]:
        ranges: List[_TaggedRange] = []

        def scope_range(node) -> Tuple[int, int]:
            end = getattr(node, "end_lineno", None) or node.lineno
            return node.lineno, end

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    name = _dec_name(base)
                    if name and _TEST_BASE_CLASS_RE.search(name):
                        start, end = scope_range(node)
                        ranges.append(_TaggedRange(start, end, ContextTag.TEST_FUNCTION))
                        break
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                tagged = False
                for dec in node.decorator_list:
                    if _is_test_decorator(_dec_name(dec)):
                        tagged = True
                        break
                if not tagged and node.name.startswith("test_") and _contains_assert(node):
                    tagged = True
                if tagged:
                    start, end = scope_range(node)
                    ranges.append(_TaggedRange(start, end, ContextTag.TEST_FUNCTION))
        return ranges

    def tag_for_line(self, line_number: int) -> ContextTag:
        """Context tag governing the given 1-based line."""
        if line_number in self._enforced:
            return ContextTag.PRODUCTION
        # Enforce pragma on a scope's def line strips the whole scope.
        for rng in self._ranges:
            if rng.start in self._enforced and rng.start <= line_number <= rng.end:
                return ContextTag.PRODUCTION
        if self.file_tag is not ContextTag.PRODUCTION:
            return self.file_tag
        for rng in self._ranges:
            if rng.start <= line_number <= rng.end:
                return rng.tag
        return ContextTag.PRODUCTION


# --------------------------------------------------------------------------
# Contextual severity matrix
# --------------------------------------------------------------------------

_UNIT_LIKE = (ContextTag.TEST_UNIT, ContextTag.TEST_FUNCTION)

# (kind) -> {unit-like action, integration action}
_MATRIX = {
    FindingKind.DATA_FLOW_INJECTION: (ContextAction.SUPPRESS, ContextAction.SUPPRESS),
    FindingKind.WEAK_CRYPTO: (ContextAction.SUPPRESS, ContextAction.SUPPRESS),
    FindingKind.COMMAND_INJECTION: (ContextAction.SUPPRESS, ContextAction.DOWNGRADE_LOW),
    FindingKind.SSRF: (ContextAction.SUPPRESS, ContextAction.DOWNGRADE_LOW),
    FindingKind.NETWORK_CONFIG: (ContextAction.SUPPRESS, ContextAction.DOWNGRADE_INFO),
    # Secrets are NEVER suppressed by test context (dummy-value filtering is
    # the secrets scanner's job, plan 07.3); a live credential in a fixture
    # is exactly as compromised as one in prod code.
    FindingKind.HARDCODED_SECRET: (ContextAction.KEEP, ContextAction.KEEP),
    FindingKind.OTHER: (ContextAction.KEEP, ContextAction.KEEP),
}

_CWE_KIND = {
    "CWE-89": FindingKind.DATA_FLOW_INJECTION,   # SQLi
    "CWE-79": FindingKind.DATA_FLOW_INJECTION,   # XSS
    "CWE-22": FindingKind.DATA_FLOW_INJECTION,   # path traversal
    "CWE-90": FindingKind.DATA_FLOW_INJECTION,   # LDAP injection
    "CWE-943": FindingKind.DATA_FLOW_INJECTION,  # NoSQL injection
    "CWE-327": FindingKind.WEAK_CRYPTO,
    "CWE-328": FindingKind.WEAK_CRYPTO,
    "CWE-338": FindingKind.WEAK_CRYPTO,
    "CWE-78": FindingKind.COMMAND_INJECTION,
    "CWE-77": FindingKind.COMMAND_INJECTION,
    "CWE-94": FindingKind.COMMAND_INJECTION,
    "CWE-918": FindingKind.SSRF,
    "CWE-295": FindingKind.NETWORK_CONFIG,
    "CWE-319": FindingKind.NETWORK_CONFIG,
    "CWE-798": FindingKind.HARDCODED_SECRET,
    "CWE-259": FindingKind.HARDCODED_SECRET,
    "CWE-321": FindingKind.HARDCODED_SECRET,
}


def finding_kind_for_cwe(cwe_id: Optional[str]) -> FindingKind:
    """Map a CWE identifier to its severity-matrix family."""
    if not cwe_id:
        return FindingKind.OTHER
    return _CWE_KIND.get(str(cwe_id).upper().strip(), FindingKind.OTHER)


def contextual_action(kind: FindingKind, tag: ContextTag) -> ContextAction:
    """Look up the severity-matrix action for a finding kind in a context."""
    if tag is ContextTag.PRODUCTION:
        return ContextAction.KEEP
    unit_action, integration_action = _MATRIX.get(
        kind, (ContextAction.KEEP, ContextAction.KEEP)
    )
    if tag in _UNIT_LIKE:
        return unit_action
    return integration_action


@dataclass(frozen=True)
class ContextDecision:
    """Outcome of routing one finding through the severity matrix."""
    context_tag: ContextTag
    action: ContextAction
    suppressed_by_context: bool
    severity: str  # possibly downgraded


def apply_test_context(
    severity: str,
    tag: ContextTag,
    kind: Optional[FindingKind] = None,
    cwe_id: Optional[str] = None,
) -> ContextDecision:
    """
    Route a finding through the contextual severity matrix.

    Severity is only ever downgraded per the matrix; suppressed findings
    keep their original severity but carry ``suppressed_by_context=True``
    so they are retained (visible via ``--include-test-context``) while
    excluded from score and gate.
    """
    resolved_kind = kind if kind is not None else finding_kind_for_cwe(cwe_id)
    action = contextual_action(resolved_kind, tag)
    new_severity = severity
    if action is ContextAction.DOWNGRADE_LOW:
        new_severity = "low"
    elif action is ContextAction.DOWNGRADE_INFO:
        new_severity = "info"
    return ContextDecision(
        context_tag=tag,
        action=action,
        suppressed_by_context=(action is ContextAction.SUPPRESS),
        severity=new_severity,
    )
