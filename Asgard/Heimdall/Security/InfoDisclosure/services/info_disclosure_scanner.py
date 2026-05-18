"""Information disclosure vulnerability scanner."""

import os
import re
from pathlib import Path
from typing import List

from Asgard.Heimdall.Security.InfoDisclosure.models.info_disclosure_models import (
    InfoDisclosureFinding,
    InfoDisclosureScanConfig,
    InfoDisclosureScanReport,
    InfoDisclosureSeverity,
)

_DISCLOSURE_PATTERNS: dict = {
    "error_messages": [
        (r"(?:catch|except)\s*[^{]*\{?\s*[^}]*(?:res\.|response\.)?(?:send|json|write)\s*\(\s*(?:err|error|e)(?:\.message|\.stack)?", "MEDIUM", "raw_error_response", "Raw error object sent to client", "Return generic error messages"),
        (r"stack.*(?:res\.|response\.)", "HIGH", "stack_trace_response", "Stack trace in HTTP response", "Never expose stack traces to clients"),
        (r"\.printStackTrace\s*\(\s*(?:resp|response|out|writer)", "HIGH", "java_stack_trace", "Java stack trace in response", "Log internally, send generic error"),
    ],
    "debug_info": [
        (r"console\.(?:log|debug|trace)\s*\([^)]*(?:password|secret|token|key|credential)", "HIGH", "debug_secrets", "Secrets logged to console", "Remove sensitive debug logging"),
        (r"(?:var_dump|print_r|debug_backtrace)\s*\(", "MEDIUM", "php_debug_output", "PHP debug function in production code", "Remove debug output functions"),
        (r"dd\s*\(|dump\s*\(|ray\s*\(", "MEDIUM", "laravel_debug", "Laravel debug helper in production code", "Remove before deployment"),
    ],
    "comments": [
        (r"//\s*(?:TODO|FIXME|HACK|password|secret|key|credential|admin|backdoor)", "LOW", "sensitive_comment", "Sensitive information in code comment", "Remove sensitive details from comments"),
        (r"<!--.*(?:password|secret|key|admin|todo.*auth).*-->", "LOW", "html_sensitive_comment", "Sensitive info in HTML comment", "Remove HTML comments with sensitive data"),
    ],
    "version_info": [
        (r"(?:Server|X-Powered-By|X-AspNet-Version)\s*:\s*\w+[/\s]\d+\.\d+", "LOW", "version_header", "Server version disclosed in header", "Remove or genericize version headers"),
        (r"powered\s+by.*\d+\.\d+|version\s*[=:]\s*['\"][\d.]+['\"]", "LOW", "version_disclosure", "Software version disclosed", "Avoid version disclosure"),
    ],
    "internal_paths": [
        (r"(?:/home/\w+|/root/|C:\\\\Users\\\\|/var/www/|/opt/|/srv/)", "MEDIUM", "internal_path", "Internal filesystem path disclosed", "Remove internal paths from responses/logs"),
        (r"(?:__file__|__dirname|os\.getcwd\(\))\s*.*(?:response|send|json|log)", "MEDIUM", "code_path_disclosure", "Source file path in response", "Never expose internal paths"),
    ],
    "database_info": [
        (r"(?:PDOException|mysqli_error|pg_last_error|ORA-\d{5}|SQLSTATE)", "HIGH", "db_error_disclosure", "Database error message disclosed", "Catch and log DB errors internally"),
        (r"(?:table|column|schema).*(?:does not exist|unknown column|no such table)", "MEDIUM", "db_schema_disclosure", "Database schema information disclosed", "Use generic error messages"),
    ],
    "api_keys": [
        (r"(?:api[_-]?key|apikey|access[_-]?token)\s*[:=]\s*['\"]([A-Za-z0-9_.-]{16,})['\"]", "CRITICAL", "api_key_in_response", "API key potentially in response/log", "Never include API keys in responses"),
    ],
    "jwt_details": [
        (r"eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}", "HIGH", "jwt_in_response", "JWT token in response or log", "Transmit JWTs only via Authorization header or secure cookies"),
    ],
    "system_info": [
        (r"(?:os\.uname|platform\.platform|sys\.version|os\.environ).*(?:response|send|json|log)", "MEDIUM", "system_info_disclosure", "System information disclosed", "Never expose system details"),
        (r"hostname|server\s*name.*(?:response|send|json)", "LOW", "hostname_disclosure", "Hostname potentially disclosed", "Avoid disclosing internal hostnames"),
    ],
}


class InfoDisclosureScanner:
    """Scans source code for information disclosure vulnerabilities."""

    def __init__(self) -> None:
        self._compiled: dict = {}
        for category, patterns in _DISCLOSURE_PATTERNS.items():
            self._compiled[category] = [
                (re.compile(p, re.IGNORECASE), sev, ptype, desc, rec)
                for p, sev, ptype, desc, rec in patterns
            ]

    def scan(self, config: InfoDisclosureScanConfig) -> InfoDisclosureScanReport:
        findings: List[InfoDisclosureFinding] = []
        files_scanned = 0
        target = config.scan_path
        skip = set(config.skip_dirs)

        if target.is_file():
            findings = self._scan_file(target)
            files_scanned = 1
        else:
            for root, dirs, files in os.walk(target):
                dirs[:] = [d for d in dirs if d not in skip]
                for name in files:
                    fp = Path(root) / name
                    ff = self._scan_file(fp)
                    if ff:
                        findings.extend(ff)
                        files_scanned += 1

        by_severity: dict = {}
        by_category: dict = {}
        for f in findings:
            by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1
            by_category[f.category] = by_category.get(f.category, 0) + 1

        return InfoDisclosureScanReport(
            scan_path=str(config.scan_path),
            total_findings=len(findings),
            files_scanned=files_scanned,
            findings=findings,
            by_severity=by_severity,
            by_category=by_category,
        )

    def _scan_file(self, file_path: Path) -> List[InfoDisclosureFinding]:
        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return []

        findings: List[InfoDisclosureFinding] = []
        for line_num, line in enumerate(lines, 1):
            for category, patterns in self._compiled.items():
                for regex, sev, ptype, desc, rec in patterns:
                    if regex.search(line):
                        findings.append(InfoDisclosureFinding(
                            file_path=str(file_path),
                            line_number=line_num,
                            severity=InfoDisclosureSeverity(sev),
                            category=category,
                            issue_type=ptype,
                            code_snippet=line.strip()[:150],
                            description=desc,
                            recommendation=rec,
                        ))
                        break

        return findings
