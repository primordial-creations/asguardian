"""
Heimdall - Security Analysis

Named after the Norse watchman god who guards Bifrost and can see and hear
everything across all realms. Heimdall watches over your codebase for
security vulnerabilities.

Subpackages (in this package):
- Security: Vulnerability scanning, secrets detection, injection patterns

Other analysis modules have moved:
- Quality, Performance, OOP, Dependencies, Architecture, Coverage,
  Ratings, QualityGate, CodeFix  → Asgard.Bragi
- common, Issues, Profiles, Init  → Asgard.Shared

Usage:
    python -m Heimdall --help
    python -m Heimdall security scan ./src

Programmatic Usage:
    from Asgard.Heimdall.Security import StaticSecurityService, SecurityScanConfig
"""

__version__ = "1.5.0"
__author__ = "Asgard Contributors"

# Package metadata
PACKAGE_INFO = {
    "name": "Heimdall",
    "version": __version__,
    "description": "Security analysis package",
    "author": __author__,
    "sub_packages": [
        "Security - Vulnerability scanning, secrets detection, injection patterns",
    ]
}

# Import Security subpackage
from . import Security

# Re-export commonly used items from Security for convenience
from Asgard.Heimdall.Security import (
    SecurityReport,
    SecurityScanConfig,
    SecuritySeverity,
    StaticSecurityService,
)

__all__ = [
    # Subpackages
    "Security",
    # Security exports
    "SecurityReport",
    "SecurityScanConfig",
    "SecuritySeverity",
    "StaticSecurityService",
]
