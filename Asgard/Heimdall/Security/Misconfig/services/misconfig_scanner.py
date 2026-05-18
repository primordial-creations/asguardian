"""Security misconfiguration scanner."""

import os
import re
from pathlib import Path
from typing import List

from Asgard.Heimdall.Security.Misconfig.models.misconfig_models import (
    MisconfigFinding,
    MisconfigScanConfig,
    MisconfigScanReport,
    MisconfigSeverity,
)

_MISCONFIG_PATTERNS: dict = {
    "debug_mode": [
        (r"(?:DEBUG|debug)\s*(?:=|:)\s*(?:True|true|1|yes|on)", "HIGH", "debug_enabled", "Debug mode enabled", "Disable debug mode in production"),
        (r"(?:NODE_ENV|FLASK_ENV|RAILS_ENV|APP_ENV)\s*(?:=|:)\s*['\"`]?(?:development|dev)['\"`]?", "MEDIUM", "dev_environment", "Development environment configuration", "Use production environment in deployment"),
        (r"(?:FLASK_DEBUG|DJANGO_DEBUG)\s*(?:=|:)\s*(?:True|true|1)", "HIGH", "framework_debug", "Framework debug mode enabled", "Disable framework debug in production"),
    ],
    "default_credentials": [
        (r"(?:password|passwd|pwd)\s*(?:=|:)\s*['\"`](?:admin|password|123456|root|default|test)['\"`]", "CRITICAL", "default_password", "Default/weak password", "Use strong, unique passwords"),
        (r"(?:user|username|login)\s*(?:=|:)\s*['\"`](?:admin|root|test|user)['\"`]", "MEDIUM", "default_username", "Default username", "Avoid common usernames"),
    ],
    "insecure_protocols": [
        (r"http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)", "MEDIUM", "http_protocol", "HTTP instead of HTTPS", "Use HTTPS for all external connections"),
        (r"ftp://[^\s'\"`]+", "MEDIUM", "ftp_protocol", "FTP protocol (unencrypted)", "Use SFTP or FTPS instead"),
        (r"telnet://[^\s'\"`]+", "HIGH", "telnet_protocol", "Telnet protocol (unencrypted)", "Use SSH instead of Telnet"),
    ],
    "ssl_tls": [
        (r"(?:ssl|tls).*(?:verify|check)\s*(?:=|:)\s*(?:False|false|0|no)", "CRITICAL", "ssl_verify_disabled", "SSL/TLS verification disabled", "Always verify SSL certificates"),
        (r"(?:SSLv2|SSLv3|TLSv1\.0|TLSv1\.1)\s*(?:=|:)\s*(?:True|true|1|enabled)", "HIGH", "weak_tls", "Weak TLS/SSL version enabled", "Use TLS 1.2+ only"),
        (r"CERT_NONE|ssl\.CERT_NONE", "CRITICAL", "cert_none", "Certificate verification disabled", "Use ssl.CERT_REQUIRED"),
    ],
    "cors": [
        (r"Access-Control-Allow-Origin['\"]?\s*:\s*['\"]?\*", "MEDIUM", "cors_wildcard", "Permissive CORS wildcard", "Restrict to specific trusted origins"),
        (r"cors\s*\(\s*\{[^}]*origin\s*:\s*(?:true|\*)", "MEDIUM", "cors_all_origins", "CORS allowing all origins", "Whitelist specific origins"),
    ],
    "session": [
        (r"(?:session|cookie).*(?:secure|httponly)\s*(?:=|:)\s*(?:False|false|0)", "HIGH", "insecure_session", "Session cookie without secure/httponly flags", "Set Secure and HttpOnly flags on session cookies"),
        (r"SECRET_KEY\s*=\s*['\"](?:dev|test|debug|secret|changeme|your[_-]secret)['\"]", "CRITICAL", "weak_secret_key", "Weak Flask/Django secret key", "Use a strong random secret key"),
    ],
    "database": [
        (r"(?:host|server)\s*(?:=|:)\s*['\"](?:0\.0\.0\.0)['\"]", "HIGH", "db_bind_all", "Database bound to all interfaces", "Bind database to specific interface"),
        (r"GRANT\s+ALL\s+PRIVILEGES\s+ON\s+\*\.\*", "HIGH", "db_all_privileges", "Database granting all privileges", "Grant only required privileges"),
    ],
    "logging": [
        (r"(?:logging|log).*(?:level|setLevel)\s*(?:=|:)\s*(?:DEBUG|10)", "LOW", "debug_logging", "Debug logging level in production", "Use WARNING or ERROR in production"),
        (r"logging\.disable\s*\(\s*logging\.CRITICAL", "HIGH", "logging_disabled", "Critical logging disabled", "Do not disable critical logging"),
    ],
    "docker": [
        (r"privileged\s*:\s*true", "CRITICAL", "docker_privileged", "Docker container running in privileged mode", "Remove privileged mode"),
        (r"user\s*:\s*root", "HIGH", "docker_root_user", "Docker container running as root", "Specify non-root user"),
        (r"(?:ADD|COPY)\s+\.\s+/", "MEDIUM", "docker_copy_all", "Copying entire context into container", "Copy only necessary files"),
    ],
    "secrets": [
        (r"(?:AWS_SECRET_ACCESS_KEY|PRIVATE_KEY|DB_PASSWORD)\s*=\s*['\"][^'\"]{8,}['\"]", "CRITICAL", "hardcoded_env_secret", "Hardcoded secret in environment config", "Use secrets management or environment injection"),
    ],
    "error_handling": [
        (r"display_errors\s*=\s*(?:On|1|true)", "MEDIUM", "php_display_errors", "PHP display_errors enabled", "Disable display_errors in production"),
        (r"app\.use\(errorHandler\(\)\)|app\.use\(express-error\)", "LOW", "verbose_error_handler", "Verbose error handler may leak info", "Use generic error messages in production"),
    ],
}


class SecurityMisconfigScanner:
    """Scans source code and config files for security misconfigurations."""

    def __init__(self) -> None:
        self._compiled: dict = {}
        for category, patterns in _MISCONFIG_PATTERNS.items():
            self._compiled[category] = [
                (re.compile(p, re.IGNORECASE), sev, ptype, desc, rec)
                for p, sev, ptype, desc, rec in patterns
            ]

    def scan(self, config: MisconfigScanConfig) -> MisconfigScanReport:
        findings: List[MisconfigFinding] = []
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

        return MisconfigScanReport(
            scan_path=str(config.scan_path),
            total_findings=len(findings),
            files_scanned=files_scanned,
            findings=findings,
            by_severity=by_severity,
            by_category=by_category,
        )

    def _scan_file(self, file_path: Path) -> List[MisconfigFinding]:
        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return []

        findings: List[MisconfigFinding] = []
        for line_num, line in enumerate(lines, 1):
            for category, patterns in self._compiled.items():
                for regex, sev, ptype, desc, rec in patterns:
                    if regex.search(line):
                        findings.append(MisconfigFinding(
                            file_path=str(file_path),
                            line_number=line_num,
                            severity=MisconfigSeverity(sev),
                            category=category,
                            issue_type=ptype,
                            code_snippet=line.strip()[:150],
                            description=desc,
                            recommendation=rec,
                        ))
                        break

        return findings
