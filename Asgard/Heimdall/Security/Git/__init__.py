"""
Heimdall Security Git — git repository security scanner.

Detects sensitive files in commit history, secrets in tracked files,
missing .gitignore patterns, unprotected branches, and absent pre-commit hooks.

Usage:
    from Asgard.Heimdall.Security.Git import GitSecurityScanner

    scanner = GitSecurityScanner()
    report = scanner.scan(Path("."))
    print(f"Git security issues: {report.total_findings}")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Heimdall.Security.Git.models.git_models import GitFinding, GitScanReport, GitSeverity
from Asgard.Heimdall.Security.Git.services.git_scanner import GitSecurityScanner

__all__ = ["GitFinding", "GitScanReport", "GitSecurityScanner", "GitSeverity"]
