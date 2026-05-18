"""
Heimdall Security FileIntegrity — file integrity baseline creation and verification.

Creates MD5+SHA-256 baselines for directory trees and detects modifications,
additions, deletions, and permission changes since the baseline was captured.

Usage:
    from Asgard.Heimdall.Security.FileIntegrity import FileIntegrityChecker

    checker = FileIntegrityChecker()
    checker.create_baseline(Path("./src"))
    report = checker.verify_integrity(Path("./src"))
    print(f"Modified: {len(report.modified)}  Added: {len(report.added)}")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Heimdall.Security.FileIntegrity.models.file_integrity_models import (
    FileIntegrityReport,
    FileModification,
    FileRecord,
    PermissionChange,
)
from Asgard.Heimdall.Security.FileIntegrity.services.file_integrity_checker import FileIntegrityChecker

__all__ = [
    "FileIntegrityChecker",
    "FileIntegrityReport",
    "FileModification",
    "FileRecord",
    "PermissionChange",
]
