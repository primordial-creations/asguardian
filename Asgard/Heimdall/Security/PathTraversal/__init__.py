"""
Heimdall Security PathTraversal — path traversal vulnerability scanner.

Detects user-controlled file paths in open(), send_file, fs.readFile, PHP include,
Java File constructors, and other file operation sinks across multiple languages.

Usage:
    from Asgard.Heimdall.Security.PathTraversal import PathTraversalScanner, PathTraversalScanConfig

    scanner = PathTraversalScanner()
    report = scanner.scan(PathTraversalScanConfig(scan_path=Path("./src")))
    print(f"Path traversal findings: {report.total_findings}")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Heimdall.Security.PathTraversal.models.path_traversal_models import (
    PathTraversalFinding,
    PathTraversalScanConfig,
    PathTraversalScanReport,
    PathTraversalSeverity,
)
from Asgard.Heimdall.Security.PathTraversal.services.path_traversal_scanner import PathTraversalScanner

__all__ = [
    "PathTraversalFinding",
    "PathTraversalScanConfig",
    "PathTraversalScanReport",
    "PathTraversalScanner",
    "PathTraversalSeverity",
]
