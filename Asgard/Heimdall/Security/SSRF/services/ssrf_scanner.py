"""SSRF and XXE vulnerability scanner."""

import os
import re
from pathlib import Path
from typing import List

from Asgard.Heimdall.Security.SSRF.models.ssrf_models import (
    SSRFFinding,
    SSRFScanConfig,
    SSRFScanReport,
    SSRFSeverity,
    SSRFVulnerabilityType,
)

_LANG_EXTENSIONS = {".py": "python", ".js": "javascript", ".ts": "javascript",
                    ".php": "php", ".java": "java", ".cs": "csharp", ".rb": "ruby", ".go": "go"}

# (pattern, vuln_type, severity, pattern_type, description, recommendation)
_VULNERABILITY_PATTERNS: dict = {
    "python": [
        (r"requests\.(?:get|post|put|delete|head|patch)\s*\(\s*(?:f['\"]|['\"][^'\"]*\{|[^'\"]+(?:url|URL|host|target|endpoint|redirect))", "ssrf", "HIGH", "ssrf_requests", "SSRF via requests with dynamic URL", "Validate URL against allowlist before making requests"),
        (r"urllib\.request\.urlopen\s*\(\s*(?:[^'\"]+(?:url|URL|host|target)|f['\"])", "ssrf", "HIGH", "ssrf_urllib", "SSRF via urllib with dynamic URL", "Validate and allowlist URLs"),
        (r"xml\.etree\b|minidom\.parse|lxml\.etree.*fromstring(?!.*resolve_entities\s*=\s*False)", "xxe", "HIGH", "xxe_python_xml", "XML parsing without XXE protection", "Disable external entity resolution"),
    ],
    "javascript": [
        (r"(?:fetch|axios\.get|axios\.post|http\.get|http\.request)\s*\(\s*(?:req\.|request\.|params\.|body\.|query\.)", "ssrf", "HIGH", "ssrf_fetch", "SSRF via fetch/axios with user-controlled URL", "Validate URL against allowlist"),
        (r"new\s+(?:XMLParser|DOMParser|xml2js)(?!.*(?:processEntities|resolveExternalEntities)\s*:\s*false)", "xxe", "MEDIUM", "xxe_js_xml", "XML parsing potentially vulnerable to XXE", "Disable entity resolution"),
    ],
    "php": [
        (r"(?:file_get_contents|fopen|curl_init)\s*\(\s*\$_(?:GET|POST|REQUEST)", "ssrf", "CRITICAL", "ssrf_php_request", "SSRF via file_get_contents/curl with user input", "Validate URL scheme and host"),
        (r"simplexml_load_(?:string|file)|DOMDocument.*loadXML(?!.*LIBXML_NOENT\s*=\s*0)", "xxe", "HIGH", "xxe_php", "PHP XML parsing vulnerable to XXE", "Use LIBXML_NOENT=0 and disable external entities"),
    ],
    "java": [
        (r"new\s+URL\s*\(\s*(?:request\.getParameter|req\.getParam)", "ssrf", "HIGH", "ssrf_java_url", "SSRF via URL constructor with user input", "Validate URL against allowlist"),
        (r"DocumentBuilder(?!.*setFeature.*\"http://apache.org/xml/features/disallow-doctype-decl\")", "xxe", "CRITICAL", "xxe_java_docbuilder", "Java DocumentBuilder without XXE protection", "Disable DOCTYPE declarations"),
        (r"SAXParser(?!.*setFeature.*disallow-doctype-decl)", "xxe", "CRITICAL", "xxe_java_sax", "SAXParser without XXE protection", "Disable DOCTYPE declarations"),
    ],
    "csharp": [
        (r"new\s+WebClient\s*\(\s*\).*DownloadString\s*\(\s*(?:Request\[|HttpContext)", "ssrf", "HIGH", "ssrf_csharp_webclient", "SSRF via WebClient with user input", "Validate URLs"),
        (r"XmlDocument(?!.*XmlResolver\s*=\s*null)", "xxe", "HIGH", "xxe_csharp_xml", "XmlDocument without XXE protection", "Set XmlResolver = null"),
    ],
}


class SSRFXXEScanner:
    """Scans source code for SSRF and XXE vulnerabilities."""

    def __init__(self) -> None:
        self._compiled: dict = {}
        for lang, patterns in _VULNERABILITY_PATTERNS.items():
            self._compiled[lang] = [
                (re.compile(p, re.IGNORECASE), vtype, sev, ptype, desc, rec)
                for p, vtype, sev, ptype, desc, rec in patterns
            ]

    def scan(self, config: SSRFScanConfig) -> SSRFScanReport:
        findings: List[SSRFFinding] = []
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
        by_vuln_type: dict = {}
        for f in findings:
            by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1
            by_vuln_type[f.vulnerability_type.value] = by_vuln_type.get(f.vulnerability_type.value, 0) + 1

        return SSRFScanReport(
            scan_path=str(config.scan_path),
            total_findings=len(findings),
            files_scanned=files_scanned,
            findings=findings,
            by_severity=by_severity,
            by_vulnerability_type=by_vuln_type,
        )

    def _scan_file(self, file_path: Path) -> List[SSRFFinding]:
        lang = _LANG_EXTENSIONS.get(file_path.suffix.lower())
        if not lang or lang not in self._compiled:
            return []

        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return []

        findings: List[SSRFFinding] = []
        for line_num, line in enumerate(lines, 1):
            for regex, vtype, sev, ptype, desc, rec in self._compiled[lang]:
                if regex.search(line):
                    findings.append(SSRFFinding(
                        file_path=str(file_path),
                        line_number=line_num,
                        vulnerability_type=SSRFVulnerabilityType(vtype),
                        severity=SSRFSeverity(sev),
                        language=lang,
                        pattern_type=ptype,
                        code_snippet=line.strip()[:150],
                        description=desc,
                        recommendation=rec,
                    ))

        return findings
