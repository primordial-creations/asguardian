"""
Heimdall Security Hotspot Detector Service

Detects security-sensitive code patterns in Python source files using AST
analysis and regular expressions. Hotspots are not confirmed vulnerabilities
but areas that require manual security review.

Detected categories:
1. Cookie Configuration - insecure cookie settings
2. Cryptographic Code - crypto module usage (flag for review)
3. Dynamic Code Execution - eval, exec, compile, __import__
4. Regex DoS (ReDoS) - complex nested quantifier patterns
5. XML External Entity (XXE) - XML parsing without explicit entity disabling
6. Pickle/Deserialization - unsafe deserialization calls
7. SSRF - HTTP calls with potentially user-supplied URLs
8. Random Number Generation - use of random module for security operations
9. Permission / Authorization Checks - os.chmod, os.access usage
10. HTTP Request Without TLS Verification - verify=False in requests calls
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
                        if self._meets_min_priority(hotspot.review_priority):
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

        try:
            tree = ast.parse(source)
            hotspots.extend(detect_ast_hotspots(
                tree, str_path, lines, self.config,
                self._get_line, self._get_call_name,
            ))
        except SyntaxError:
            pass

        hotspots.extend(detect_regex_hotspots(lines, str_path, self.config))

        return hotspots

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
