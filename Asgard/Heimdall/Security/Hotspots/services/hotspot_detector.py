"""
Heimdall Security Hotspot Detector Service

Detects the six defensible hotspot families (plan 08 Part A): weak
hashing, standard PRNG, disabled transport security, permissive
bindings/CORS, opaque deserialization, and cryptography.hazmat usage.
A hotspot is syntactically flawless code whose safety depends on
extrinsic context — never a failed finding.

Python files use AST checks; other languages fall back to regex rules.
Hotspots are routed through the test-context engine (plan 08 Part B):
findings in test code get contextual severity or suppression (retained
with ``suppressed_by_context=True``; include via
``config.include_test_context``).
"""

import ast
import fnmatch
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Security.Hotspots.models.hotspot_models import (
    HotspotCategory,
    HotspotConfig,
    HotspotReport,
    ReviewPriority,
    ReviewStatus,
    SecurityHotspot,
)
from Asgard.Heimdall.Security.Hotspots.services._ast_hotspot_checks import detect_ast_hotspots
from Asgard.Heimdall.Security.Hotspots.services._regex_hotspot_checks import detect_regex_hotspots
from Asgard.Heimdall.Security.context.test_context import (
    ContextTag,
    FindingKind,
    TestContextIndex,
    contextual_action,
    ContextAction,
)

# Hotspot family -> severity-matrix family (plan 08 Part B).
_CATEGORY_KIND = {
    HotspotCategory.WEAK_HASHING: FindingKind.WEAK_CRYPTO,
    HotspotCategory.STANDARD_PRNG: FindingKind.WEAK_CRYPTO,
    HotspotCategory.HAZMAT_CRYPTO: FindingKind.WEAK_CRYPTO,
    HotspotCategory.DISABLED_TLS: FindingKind.NETWORK_CONFIG,
    HotspotCategory.PERMISSIVE_BINDING: FindingKind.NETWORK_CONFIG,
    # Deserialization of fixtures is ubiquitous in tests, but on an
    # integration/CI runner it is a real (reduced) attack surface — same
    # routing as command injection.
    HotspotCategory.OPAQUE_DESERIALIZATION: FindingKind.COMMAND_INJECTION,
}


class HotspotDetector:
    """
    Detects security-sensitive code patterns requiring manual review.

    Uses AST analysis combined with regex scanning to identify patterns
    across ten hotspot categories aligned with OWASP Top 10 and CWE Top 25.

    Usage:
        detector = HotspotDetector()
        report = detector.scan(Path("./src"))

        print(f"Total hotspots: {report.total_hotspots}")
        for hotspot in report.hotspots:
            print(f"  [{hotspot.review_priority}] {hotspot.title} at {hotspot.file_path}:{hotspot.line_number}")
    """

    def __init__(self, config: Optional[HotspotConfig] = None):
        """
        Initialize the hotspot detector.

        Args:
            config: Configuration for the detector. If None, uses defaults.
        """
        self.config = config or HotspotConfig()

    def scan(self, scan_path: Path) -> HotspotReport:
        """
        Scan a directory for security hotspots.

        Args:
            scan_path: Path to directory to analyze

        Returns:
            HotspotReport with all detected hotspots

        Raises:
            FileNotFoundError: If scan_path does not exist
        """
        if not scan_path.exists():
            raise FileNotFoundError(f"Path does not exist: {scan_path}")

        start_time = datetime.now()
        report = HotspotReport(scan_path=str(scan_path))

        for root, dirs, files in os.walk(scan_path):
            root_path = Path(root)

            dirs[:] = [
                d for d in dirs
                if not any(self._matches_pattern(d, p) for p in self.config.exclude_patterns)
            ]

            for file in files:
                if not self._should_analyze_file(file):
                    continue

                file_path = root_path / file
                try:
                    hotspots = self._analyze_file(file_path)
                    for hotspot in hotspots:
                        if not self._meets_min_priority(hotspot.review_priority):
                            continue
                        if hotspot.suppressed_by_context:
                            report.suppressed_by_context_count += 1
                            if not self.config.include_test_context:
                                continue
                        report.add_hotspot(hotspot)
                except Exception:
                    pass

        report.scan_duration_seconds = (datetime.now() - start_time).total_seconds()

        return report

    def _analyze_file(self, file_path: Path) -> List[SecurityHotspot]:
        """Analyze a single file for hotspots using AST and regex."""
        try:
            source = file_path.read_text(encoding="utf-8")
        except Exception:
            return []

        hotspots: List[SecurityHotspot] = []
        lines = source.splitlines()
        str_path = str(file_path)
        tree = None

        if file_path.suffix in (".py", ".pyw"):
            try:
                tree = ast.parse(source)
                hotspots.extend(detect_ast_hotspots(
                    tree, str_path, lines, self.config,
                    self._get_line, self._get_call_name,
                ))
            except SyntaxError:
                tree = None

        # Regex fallback; on parsed Python files, dedupe (category, line)
        # already covered by the AST checks.
        seen = {(h.category, h.line_number) for h in hotspots}
        for h in detect_regex_hotspots(lines, str_path, self.config):
            if tree is not None and (h.category, h.line_number) in seen:
                continue
            hotspots.append(h)

        if self.config.test_context_enabled and hotspots:
            self._apply_test_context(str_path, source, tree, hotspots)

        return hotspots

    def _apply_test_context(self, str_path, source, tree, hotspots: List[SecurityHotspot]) -> None:
        """Route hotspots through the contextual severity matrix (plan 08 B)."""
        index = TestContextIndex.for_python_source(
            str_path, source,
            strict_scan_paths=self.config.strict_scan_paths,
            tree=tree,
        )
        for hotspot in hotspots:
            tag = index.tag_for_line(hotspot.line_number)
            hotspot.context_tag = tag.value
            if tag is ContextTag.PRODUCTION:
                continue
            category = hotspot.category if isinstance(hotspot.category, HotspotCategory) \
                else HotspotCategory(hotspot.category)
            kind = _CATEGORY_KIND.get(category, FindingKind.OTHER)
            action = contextual_action(kind, tag)
            if action is ContextAction.SUPPRESS:
                hotspot.suppressed_by_context = True
            elif action is ContextAction.DOWNGRADE_LOW:
                hotspot.review_priority = ReviewPriority.LOW
            elif action is ContextAction.DOWNGRADE_INFO:
                hotspot.review_priority = ReviewPriority.LOW

    def _get_call_name(self, node: ast.Call) -> str:
        """Extract a dotted name string from a Call node's func attribute."""
        func = node.func
        if isinstance(func, ast.Name):
            return func.id
        elif isinstance(func, ast.Attribute):
            parts = []
            current: ast.expr = func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return ""

    def _get_line(self, lines: List[str], line_number: int) -> str:
        """Safely retrieve a source line by 1-based line number."""
        if 1 <= line_number <= len(lines):
            return lines[line_number - 1].strip()
        return ""

    def _meets_min_priority(self, priority: ReviewPriority) -> bool:
        """Check whether a hotspot meets the configured minimum priority."""
        order = {
            ReviewPriority.HIGH: 3,
            ReviewPriority.MEDIUM: 2,
            ReviewPriority.LOW: 1,
        }
        min_order = order.get(self.config.min_priority, 1)
        hotspot_order = order.get(priority, 1)
        if isinstance(priority, str):
            hotspot_order = order.get(ReviewPriority(priority), 1)
        return hotspot_order >= min_order

    def _should_analyze_file(self, filename: str) -> bool:
        """Determine whether a file should be analyzed."""
        has_valid_ext = any(filename.endswith(ext) for ext in self.config.include_extensions)
        if not has_valid_ext:
            return False

        if any(self._matches_pattern(filename, p) for p in self.config.exclude_patterns):
            return False

        if not self.config.include_tests:
            if filename.startswith("test_") or filename.endswith("_test.py"):
                return False

        return True

    def _matches_pattern(self, name: str, pattern: str) -> bool:
        """Check if a name matches an exclude glob pattern."""
        return fnmatch.fnmatch(name, pattern)
