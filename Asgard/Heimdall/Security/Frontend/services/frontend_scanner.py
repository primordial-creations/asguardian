"""Frontend (client-side) security vulnerability scanner."""

import os
import re
from pathlib import Path
from typing import List

from Asgard.Heimdall.Security.Frontend.models.frontend_models import (
    FrontendFinding,
    FrontendScanConfig,
    FrontendScanReport,
    FrontendSeverity,
)

_FRONTEND_EXTENSIONS = {".js", ".ts", ".jsx", ".tsx", ".html", ".htm", ".vue", ".svelte"}

_VULNERABILITY_PATTERNS: dict = {
    "dom_xss": [
        (r"innerHTML\s*=", "HIGH", "innerhtml_assign", "innerHTML assignment — potential DOM XSS sink", "Use textContent or sanitize with DOMPurify"),
        (r"outerHTML\s*=", "HIGH", "outerhtml_assign", "outerHTML assignment — DOM XSS sink", "Use safe DOM APIs"),
        (r"document\.write\s*\(", "HIGH", "document_write", "document.write() — DOM XSS sink", "Use createElement and appendChild"),
        (r"\.insertAdjacentHTML\s*\(", "MEDIUM", "insertadjacenthtml", "insertAdjacentHTML — potential XSS sink", "Sanitize HTML before inserting"),
    ],
    "prototype_pollution": [
        (r"__proto__\s*\[", "HIGH", "proto_bracket", "Prototype pollution via __proto__", "Validate keys before property assignment"),
        (r"constructor\s*\[.*\]\s*=", "HIGH", "constructor_pollution", "Prototype pollution via constructor", "Use Object.create(null) for maps"),
        (r"Object\.assign\s*\(\s*(?:\{\}|Object\.create\(null\))", "LOW", "object_assign_clean", "Object.assign potentially safe — verify source", "Validate source object keys"),
    ],
    "storage_security": [
        (r"localStorage\.(setItem|getItem)\s*\([^)]*(?:token|password|secret|key)", "HIGH", "localstorage_sensitive", "Sensitive data in localStorage (not secure)", "Use sessionStorage or httpOnly cookies"),
        (r"sessionStorage\.(setItem|getItem)\s*\([^)]*(?:password|credit|ssn)", "MEDIUM", "sessionstorage_pii", "PII in sessionStorage", "Never store PII in browser storage"),
    ],
    "unsafe_redirects": [
        (r"(?:window\.location|location\.href)\s*=\s*(?:req\.|request\.|params\.|query\.|document\.URL|document\.referrer)", "HIGH", "open_redirect", "Open redirect via unvalidated URL", "Validate redirect destination against allowlist"),
    ],
    "eval_usage": [
        (r"eval\s*\([^)]+\)", "HIGH", "eval_call", "eval() with dynamic content", "Avoid eval(); use JSON.parse() for data"),
        (r"new\s+Function\s*\(", "HIGH", "new_function", "new Function() — dynamic code execution", "Use static functions instead"),
        (r"setTimeout\s*\(\s*['\"][^'\"]+['\"]", "MEDIUM", "settimeout_string", "setTimeout with string argument (eval equivalent)", "Pass a function reference instead"),
    ],
    "sensitive_exposure": [
        (r"console\.\w+\s*\([^)]*(?:password|secret|token|key|credential)", "MEDIUM", "console_secret", "Sensitive data logged to console", "Remove logging of sensitive values"),
        (r"(?:API_KEY|SECRET|PASSWORD)\s*=\s*['\"][^'\"]+['\"]", "CRITICAL", "hardcoded_frontend_secret", "Hardcoded secret in frontend code", "Use environment variables via build process"),
    ],
    "react_specific": [
        (r"dangerouslySetInnerHTML\s*=\s*\{\s*\{", "HIGH", "react_dangerous_html", "dangerouslySetInnerHTML — XSS risk", "Sanitize HTML with DOMPurify before use"),
    ],
    "angular_specific": [
        (r"\[innerHTML\]\s*=", "HIGH", "angular_inner_html", "Angular innerHTML binding — XSS risk", "Use DomSanitizer.bypassSecurityTrustHtml() carefully"),
        (r"bypassSecurityTrust(?!ResourceUrl)", "MEDIUM", "angular_bypass_trust", "Angular security bypass — verify necessity", "Avoid bypassing Angular's sanitization"),
    ],
    "vue_specific": [
        (r"v-html\s*=", "HIGH", "vue_html_directive", "v-html directive — XSS risk", "Sanitize content with DOMPurify before v-html"),
    ],
    "clickjacking": [
        (r"X-Frame-Options.*ALLOW-FROM|frame-ancestors.*\*", "MEDIUM", "permissive_framing", "Permissive framing policy", "Use Content-Security-Policy frame-ancestors"),
    ],
}


class FrontendSecurityScanner:
    """Scans frontend source code for client-side security vulnerabilities."""

    def __init__(self) -> None:
        self._compiled: dict = {}
        for category, patterns in _VULNERABILITY_PATTERNS.items():
            self._compiled[category] = [
                (re.compile(p, re.IGNORECASE), sev, ptype, desc, rec)
                for p, sev, ptype, desc, rec in patterns
            ]

    def scan(self, config: FrontendScanConfig) -> FrontendScanReport:
        findings: List[FrontendFinding] = []
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
                    if fp.suffix.lower() not in _FRONTEND_EXTENSIONS:
                        continue
                    ff = self._scan_file(fp)
                    if ff or fp.suffix.lower() in _FRONTEND_EXTENSIONS:
                        findings.extend(ff)
                        files_scanned += 1

        by_severity: dict = {}
        by_category: dict = {}
        for f in findings:
            by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1
            by_category[f.category] = by_category.get(f.category, 0) + 1

        return FrontendScanReport(
            scan_path=str(config.scan_path),
            total_findings=len(findings),
            files_scanned=files_scanned,
            findings=findings,
            by_severity=by_severity,
            by_category=by_category,
        )

    def _scan_file(self, file_path: Path) -> List[FrontendFinding]:
        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return []

        findings: List[FrontendFinding] = []
        for line_num, line in enumerate(lines, 1):
            for category, patterns in self._compiled.items():
                for regex, sev, ptype, desc, rec in patterns:
                    if regex.search(line):
                        findings.append(FrontendFinding(
                            file_path=str(file_path),
                            line_number=line_num,
                            severity=FrontendSeverity(sev),
                            category=category,
                            pattern_type=ptype,
                            code_snippet=line.strip()[:150],
                            description=desc,
                            recommendation=rec,
                        ))
                        break

        return findings
