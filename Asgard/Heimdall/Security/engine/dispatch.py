"""
3-layer dispatch pipeline (per file).

Run-all-and-merge blows both the latency and dedup budgets; instead:

    Layer 1  regex sweep (secret/key prefixes)       -- raw text, always
    Layer 2  single AST parse                        -- structural rules +
             trigger-node scan (alias-resolved source/sink index)
    Layer 3  lazy taint                              -- only functions that
             appear in the trigger index get taint state built

Findings deduplicate by (file, sink line, sink column, CWE) before reporting.

This engine is a library component: it does not touch CLI wiring. The
intended integration (StaticSecurityService.scan / cli handlers routing
through it) is deferred to the CLI-owning change.
"""

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

from Asgard.Heimdall.Security.context.test_context import is_test_context
from Asgard.Heimdall.Security.normalization.priority import confidence_bucket
from Asgard.Heimdall.Security.TaintAnalysis.catalog.sinks import lookup_sink
from Asgard.Heimdall.Security.TaintAnalysis.catalog.sources import lookup_source
from Asgard.Heimdall.Security.TaintAnalysis.models.taint_models import TaintFlow
from Asgard.Heimdall.Security.TaintAnalysis.services._taint_visitor import (
    _FunctionTaintVisitor,
    _attr_chain,
    build_alias_map,
    resolve_chain,
)
from Asgard.Heimdall.Security.TaintAnalysis.engine.cst_taint_visitor import (
    scan_java_source,
    scan_js_ts_source,
)
from Asgard.Heimdall.treesitter.ast_engine import is_engine_enabled
from Asgard.Heimdall.treesitter.file_context import FileParseContext, language_for_path

# Extensions routed through the CST taint path (plan 04 Phase 4 / plan 01
# waves 2-3). Python keeps the ``ast``-backed path above, unchanged.
_JS_TS_EXTENSIONS = frozenset({".js", ".jsx", ".mjs", ".cjs", ".ts", ".mts", ".cts", ".tsx"})
_JAVA_EXTENSIONS = frozenset({".java"})

# Layer-1 default sweep: unambiguous machine-issued token prefixes only
# (low-FP by construction). Full secret scanning stays in SecretsDetection.
_LAYER1_PATTERNS: Tuple[Tuple[str, str, "re.Pattern"], ...] = tuple(
    (name, mechanism, re.compile(pattern))
    for name, mechanism, pattern in [
        ("aws_access_key", "secret.cloud_admin.validated",
         r"(?:AKIA|ABIA|ACCA)[0-9A-Z]{16}"),
        ("github_token", "secret.third_party.scoped_live",
         r"gh[pousr]_[A-Za-z0-9]{36,}"),
        ("slack_token", "secret.third_party.scoped_live",
         r"xox[baprs]-[A-Za-z0-9-]{10,}"),
        ("private_key_block", "secret.third_party.scoped_live",
         r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ]
)


@dataclass
class StructuralFinding:
    """A Layer-1/Layer-2 finding (no data-flow reasoning involved)."""
    rule_id: str
    mechanism_id: str
    file_path: str
    line_number: int
    message: str
    severity: str
    confidence: float
    confidence_bucket: str
    layer: int
    cwe_id: str = ""


@dataclass
class DispatchResult:
    """Result of dispatching one file through the layered pipeline."""
    file_path: str
    structural_findings: List[StructuralFinding] = field(default_factory=list)
    taint_flows: List[TaintFlow] = field(default_factory=list)
    # func name -> ("sources"/"sinks") -> resolved chains found
    trigger_index: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)
    parse_failed: bool = False


class DispatchEngine:
    """Layered per-file dispatch: regex -> AST triggers -> lazy taint."""

    def __init__(
        self,
        custom_sanitizers: Optional[Set[str]] = None,
        is_test_context: Optional[bool] = None,
        strict_scan_paths: Sequence[str] = (),
    ):
        """
        ``is_test_context=None`` (default) auto-classifies each scanned
        file through the Security/context engine; pass an explicit bool
        to force the context. ``strict_scan_paths`` regexes bypass the
        test-context engine entirely (security-regression tests).
        """
        self.custom_sanitizers = custom_sanitizers or set()
        self._forced_test_context = is_test_context
        self.is_test_context = bool(is_test_context)
        self.strict_scan_paths = tuple(strict_scan_paths)

    # ------------------------------------------------------------------ API

    def scan_file(self, file_path: Path, source: Optional[str] = None) -> DispatchResult:
        file_path = Path(file_path)
        if self._forced_test_context is None:
            self.is_test_context = is_test_context(
                str(file_path), self.strict_scan_paths
            )
        if source is None:
            try:
                source = file_path.read_text(encoding="utf-8", errors="ignore")
            except (IOError, OSError):
                return DispatchResult(file_path=str(file_path), parse_failed=True)
        result = DispatchResult(file_path=str(file_path))

        # Layer 1: raw-text regex sweep -- always runs, even on unparsable files.
        result.structural_findings.extend(self._layer1(source, str(file_path)))

        suffix = file_path.suffix.lower()
        if suffix in _JS_TS_EXTENSIONS or suffix in _JAVA_EXTENSIONS:
            result.taint_flows = self._scan_cst_language(source, file_path)
            result.taint_flows = self._dedup(result.taint_flows)
            return result

        if suffix != ".py":
            return result

        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            result.parse_failed = True
            return result

        # Layer 2: single parse -- alias map, structural rules, trigger index.
        alias_map = build_alias_map(tree)
        result.structural_findings.extend(
            self._layer2_structural(tree, alias_map, str(file_path))
        )
        result.trigger_index = self._layer2_triggers(tree, alias_map)

        # Layer 3: lazy taint on triggered functions only.
        result.taint_flows = self._layer3(
            tree, alias_map, source.splitlines(), str(file_path), result.trigger_index
        )
        result.taint_flows = self._dedup(result.taint_flows)
        return result

    # ------------------------------------------------ CST path (JS/TS/Java)

    def _scan_cst_language(self, source: str, file_path: Path) -> List[TaintFlow]:
        """Route JS/TS/Java files through the tree-sitter CST taint engine.

        Behind ``@with_ast_fallback``'s spirit (graceful degradation): when
        tree-sitter or the grammar for this language is unavailable, or the
        parse fails, this returns an empty list -- Layer 1 regex findings
        (already collected by the caller) are still reported, but no
        data-flow reasoning happens. This mirrors plan 01's "tree-sitter
        stays optional" mandate: the test suite must pass without the
        grammars installed.
        """
        lang = language_for_path(file_path)
        if lang is None or not is_engine_enabled(lang):
            return []
        ctx = FileParseContext.parse(file_path, source.splitlines(), lang)
        if ctx.root is None:
            return []
        if lang == "java":
            scan_fn = scan_java_source
        elif lang in ("javascript", "typescript", "tsx"):
            scan_fn = scan_js_ts_source
        else:
            return []
        try:
            return scan_fn(
                str(file_path), ctx,
                custom_sanitizers=self.custom_sanitizers,
                is_test_context=self.is_test_context,
            )
        except Exception:
            # A CST-rule failure must never crash the scan -- degrade to
            # "no taint findings for this file" (Layer 1 still reported).
            return []

    # -------------------------------------------------------------- layer 1

    def _layer1(self, source: str, file_path: str) -> List[StructuralFinding]:
        findings = []
        for name, mechanism, pattern in _LAYER1_PATTERNS:
            for match in pattern.finditer(source):
                line = source.count("\n", 0, match.start()) + 1
                # Hardcoded secrets are NEVER suppressed or confidence-capped
                # by test context (plan 08): a live credential in conftest.py
                # is exactly as compromised as one in production code. Dummy
                # values are handled by the dummy filter, not the context.
                if self._looks_dummy(match.group(0)):
                    continue
                conf = 0.95
                findings.append(StructuralFinding(
                    rule_id=f"L1.{name}",
                    mechanism_id=mechanism,
                    file_path=file_path,
                    line_number=line,
                    message=f"Machine-issued credential pattern '{name}' in source",
                    severity="critical" if "cloud_admin" in mechanism else "high",
                    confidence=conf,
                    confidence_bucket=confidence_bucket(conf),
                    layer=1,
                    cwe_id="CWE-798",
                ))
        return findings

    _DUMMY_TOKEN_RE = re.compile(
        r"EXAMPLE|XXXX|0000000000|1234567890|placeholder|dummy", re.IGNORECASE
    )

    @classmethod
    def _looks_dummy(cls, token: str) -> bool:
        """Dummy-value filter (plan 07.3): obvious placeholder tokens."""
        return bool(cls._DUMMY_TOKEN_RE.search(token))

    # -------------------------------------------------------------- layer 2

    def _layer2_structural(
        self, tree: ast.AST, alias_map: Dict[str, str], file_path: str
    ) -> List[StructuralFinding]:
        """Structural rules needing an AST but no data flow."""
        findings = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            chain = resolve_chain(_attr_chain(node.func), alias_map)
            if chain == "yaml.load":
                if not any(
                    kw.arg == "Loader" and "Safe" in _attr_chain(kw.value)
                    for kw in node.keywords
                ):
                    conf = 0.1 if self.is_test_context else 0.9
                    findings.append(StructuralFinding(
                        rule_id="L2.yaml_unsafe_load",
                        mechanism_id="deserialization.untrusted",
                        file_path=file_path,
                        line_number=node.lineno,
                        message="yaml.load without SafeLoader",
                        severity="critical",
                        confidence=conf,
                        confidence_bucket=confidence_bucket(conf),
                        layer=2,
                        cwe_id="CWE-502",
                    ))
            elif chain in ("pickle.loads", "pickle.load"):
                conf = 0.1 if self.is_test_context else 0.5
                findings.append(StructuralFinding(
                    rule_id="L2.pickle_load",
                    mechanism_id="deserialization.untrusted",
                    file_path=file_path,
                    line_number=node.lineno,
                    message="pickle deserialization (unsafe on untrusted data)",
                    severity="critical",
                    confidence=conf,
                    confidence_bucket=confidence_bucket(conf),
                    layer=2,
                    cwe_id="CWE-502",
                ))
        return findings

    def _layer2_triggers(
        self, tree: ast.AST, alias_map: Dict[str, str]
    ) -> Dict[str, Dict[str, List[str]]]:
        """Trigger-node index: which functions contain sources/sinks."""
        index: Dict[str, Dict[str, List[str]]] = {}

        def scan_body(func_name: str, body: Sequence[ast.stmt]) -> None:
            sources: List[str] = []
            sinks: List[str] = []
            for stmt in body:
                for node in ast.walk(stmt):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                            and stmt is not node:
                        continue
                    chain = ""
                    if isinstance(node, (ast.Attribute, ast.Name)):
                        chain = resolve_chain(_attr_chain(node), alias_map)
                        if chain and lookup_source(chain) is not None:
                            sources.append(chain)
                    if isinstance(node, ast.Call):
                        chain = resolve_chain(_attr_chain(node.func), alias_map)
                        if chain and lookup_sink(chain) is not None:
                            sinks.append(chain)
                        if chain and lookup_source(chain, is_call=True) is not None:
                            sources.append(chain)
            if sources or sinks:
                index[func_name] = {"sources": sources, "sinks": sinks}

        scan_body("<module>", [
            s for s in tree.body
            if not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ])
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scan_body(node.name, node.body)
        return index

    # -------------------------------------------------------------- layer 3

    def _layer3(
        self,
        tree: ast.AST,
        alias_map: Dict[str, str],
        lines: List[str],
        file_path: str,
        trigger_index: Dict[str, Dict[str, List[str]]],
    ) -> List[TaintFlow]:
        """Build taint state ONLY for trigger-indexed scopes with a sink."""
        flows: List[TaintFlow] = []
        triggered = {
            name for name, hits in trigger_index.items() if hits.get("sinks")
        }
        if not triggered:
            return flows

        if "<module>" in triggered:
            visitor = self._make_visitor(file_path, "<module>", lines, alias_map)
            for stmt in tree.body:
                visitor.visit(stmt)
            flows.extend(visitor.found_flows)

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name not in triggered:
                continue  # lazy: no taint state for un-triggered functions
            visitor = self._make_visitor(file_path, node.name, lines, alias_map)
            for stmt in node.body:
                visitor.visit(stmt)
            flows.extend(visitor.found_flows)
        return flows

    def _make_visitor(self, file_path, func_name, lines, alias_map):
        return _FunctionTaintVisitor(
            file_path=file_path,
            func_name=func_name,
            lines=lines,
            alias_map=alias_map,
            custom_sanitizers=self.custom_sanitizers,
            is_test_context=self.is_test_context,
        )

    # ----------------------------------------------------------------- dedup

    @staticmethod
    def _dedup(flows: List[TaintFlow]) -> List[TaintFlow]:
        best: Dict[tuple, TaintFlow] = {}
        for flow in flows:
            key = (
                flow.sink_location.file_path,
                flow.sink_location.line_number,
                flow.sink_location.column,
                flow.cwe_id,
            )
            existing = best.get(key)
            if existing is None or flow.confidence > existing.confidence:
                best[key] = flow
        return sorted(
            best.values(),
            key=lambda f: (f.sink_location.line_number, f.cwe_id, -f.confidence),
        )
