"""
Heimdall Static Security Service - targeted single-domain scan helpers.

Standalone functions for running a single security domain scan and
returning a SecurityReport. Each function accepts the relevant analyzer
(or service) as a parameter to avoid holding instance state.
"""

import time
from pathlib import Path
from typing import Optional

from Asgard.Heimdall.Security.models.security_models import (
    SecurityReport,
    SecurityScanConfig,
)


def _make_report(path: Path, config: SecurityScanConfig) -> SecurityReport:
    """Create a fresh SecurityReport for the given path and config."""
    return SecurityReport(scan_path=str(path), scan_config=config)


def scan_secrets_only(
    path: Path,
    config: SecurityScanConfig,
    secrets_service,
) -> SecurityReport:
    """Scan only for hardcoded secrets."""
    report = _make_report(path, config)
    start_time = time.time()
    report.secrets_report = secrets_service.scan(path)
    report.scan_duration_seconds = time.time() - start_time
    report.calculate_totals()
    return report


def scan_dependencies_only(
    path: Path,
    config: SecurityScanConfig,
    dependency_service,
) -> SecurityReport:
    """Scan only for dependency vulnerabilities."""
    report = _make_report(path, config)
    start_time = time.time()
    report.dependency_report = dependency_service.scan(path)
    report.scan_duration_seconds = time.time() - start_time
    report.calculate_totals()
    return report


def scan_vulnerabilities_only(
    path: Path,
    config: SecurityScanConfig,
    injection_service,
) -> SecurityReport:
    """Scan only for injection vulnerabilities."""
    report = _make_report(path, config)
    start_time = time.time()
    report.vulnerability_report = injection_service.scan(path)
    report.scan_duration_seconds = time.time() - start_time
    report.calculate_totals()
    return report


def scan_crypto_only(
    path: Path,
    config: SecurityScanConfig,
    crypto_service,
) -> SecurityReport:
    """Scan only for cryptographic issues."""
    report = _make_report(path, config)
    start_time = time.time()
    report.crypto_report = crypto_service.scan(path)
    report.scan_duration_seconds = time.time() - start_time
    report.calculate_totals()
    return report


def scan_access_only(
    path: Path,
    config: SecurityScanConfig,
    access_analyzer,
) -> SecurityReport:
    """Scan only for access control issues."""
    report = _make_report(path, config)
    start_time = time.time()
    report.access_report = access_analyzer.scan(path)
    report.scan_duration_seconds = time.time() - start_time
    report.calculate_totals()
    return report


def scan_auth_only(
    path: Path,
    config: SecurityScanConfig,
    auth_analyzer,
) -> SecurityReport:
    """Scan only for authentication issues."""
    report = _make_report(path, config)
    start_time = time.time()
    report.auth_report = auth_analyzer.scan(path)
    report.scan_duration_seconds = time.time() - start_time
    report.calculate_totals()
    return report


def scan_headers_only(
    path: Path,
    config: SecurityScanConfig,
    headers_analyzer,
) -> SecurityReport:
    """Scan only for security header issues."""
    report = _make_report(path, config)
    start_time = time.time()
    report.headers_report = headers_analyzer.scan(path)
    report.scan_duration_seconds = time.time() - start_time
    report.calculate_totals()
    return report


def scan_tls_only(
    path: Path,
    config: SecurityScanConfig,
    tls_analyzer,
) -> SecurityReport:
    """Scan only for TLS/SSL issues."""
    report = _make_report(path, config)
    start_time = time.time()
    report.tls_report = tls_analyzer.scan(path)
    report.scan_duration_seconds = time.time() - start_time
    report.calculate_totals()
    return report


def scan_container_only(
    path: Path,
    config: SecurityScanConfig,
    container_analyzer,
) -> SecurityReport:
    """Scan only for container security issues."""
    report = _make_report(path, config)
    start_time = time.time()
    report.container_report = container_analyzer.scan(path)
    report.scan_duration_seconds = time.time() - start_time
    report.calculate_totals()
    return report


def scan_infrastructure_only(
    path: Path,
    config: SecurityScanConfig,
    infrastructure_analyzer,
) -> SecurityReport:
    """Scan only for infrastructure security issues."""
    report = _make_report(path, config)
    start_time = time.time()
    report.infrastructure_report = infrastructure_analyzer.scan(path)
    report.scan_duration_seconds = time.time() - start_time
    report.calculate_totals()
    return report
