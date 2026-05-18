"""
Heimdall Security InputValidation — input validation vulnerability scanner.

Detects unvalidated user input in type coercions, file operations, database queries,
shell commands, template rendering, regex construction, and URL operations.

Usage:
    from Asgard.Heimdall.Security.InputValidation import InputValidationScanner, InputValidationScanConfig

    scanner = InputValidationScanner()
    report = scanner.scan(InputValidationScanConfig(scan_path=Path("./src")))
    print(f"Input validation findings: {report.total_findings}")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Heimdall.Security.InputValidation.models.input_validation_models import (
    InputValidationFinding,
    InputValidationScanConfig,
    InputValidationScanReport,
    InputValidationSeverity,
)
from Asgard.Heimdall.Security.InputValidation.services.input_validation_scanner import InputValidationScanner

__all__ = [
    "InputValidationFinding",
    "InputValidationScanConfig",
    "InputValidationScanReport",
    "InputValidationScanner",
    "InputValidationSeverity",
]
