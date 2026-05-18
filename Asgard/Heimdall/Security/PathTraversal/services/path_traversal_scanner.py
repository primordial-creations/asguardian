"""Path traversal vulnerability scanner."""

import os
import re
from pathlib import Path
from typing import List

from Asgard.Heimdall.Security.PathTraversal.models.path_traversal_models import (
    PathTraversalFinding,
    PathTraversalScanConfig,
    PathTraversalScanReport,
    PathTraversalSeverity,
)

_LANG_EXTENSIONS = {".py": "python", ".js": "javascript", ".ts": "javascript", ".php": "php",
                    ".java": "java", ".rb": "ruby", ".cs": "csharp", ".go": "go"}

_VULNERABILITY_PATTERNS: dict = {
    "python": [
        (r"open\s*\(\s*(?:request\.|args\.|params\.|input\()", "CRITICAL", "open_user_input", "File open with user-controlled path", "Validate path and use os.path.basename()"),
        (r"(?:os\.path\.join|pathlib\.Path)\s*\([^)]*(?:request\.|args\.|params\.)", "HIGH", "path_join_input", "Path construction with user input", "Validate and sanitize path components"),
        (r"send_file\s*\(\s*(?:request\.|args\.|params\.)", "CRITICAL", "send_file_input", "send_file with user-controlled path", "Use safe_join() and validate file access"),
        (r"(?:shutil\.copy|shutil\.move)\s*\([^)]*(?:request\.|args\.|params\.)", "HIGH", "file_ops_input", "File operation with user input", "Validate paths before file operations"),
    ],
    "javascript": [
        (r"(?:fs\.readFile|fs\.readFileSync|fs\.createReadStream)\s*\(\s*(?:req\.|request\.|params\.)", "CRITICAL", "fs_read_input", "File read with user-controlled path", "Use path.basename() and validate"),
        (r"path\.(?:join|resolve)\s*\([^)]*(?:req\.|request\.|params\.)", "HIGH", "path_join_input", "Path construction with user input", "Validate path components"),
        (r"res\.sendFile\s*\(\s*(?:req\.|request\.|params\.)", "CRITICAL", "sendfile_input", "sendFile with user-controlled path", "Use express.static() or validate paths"),
        (r"require\s*\(\s*(?:req\.|request\.|params\.)", "CRITICAL", "require_input", "Dynamic require with user input", "Never use user input in require()"),
    ],
    "php": [
        (r"(?:include|require|include_once|require_once)\s*\(\s*\$_(?:GET|POST|REQUEST)", "CRITICAL", "php_include_input", "PHP include/require with user input", "Whitelist allowed files"),
        (r"file_get_contents\s*\(\s*\$_(?:GET|POST|REQUEST)", "CRITICAL", "php_file_get_input", "file_get_contents with user input", "Validate and sanitize path"),
        (r"readfile\s*\(\s*\$_(?:GET|POST|REQUEST)", "CRITICAL", "php_readfile_input", "readfile with user input", "Validate file path"),
    ],
    "java": [
        (r"new\s+File\s*\(\s*(?:request\.getParameter|req\.getParam)", "CRITICAL", "java_file_input", "File constructor with user input", "Validate path and use canonical path"),
        (r"(?:FileInputStream|FileOutputStream)\s*\(\s*request\.getParameter", "CRITICAL", "java_filestream_input", "File stream with user input", "Canonicalize and validate path"),
    ],
}


class PathTraversalScanner:
    """Scans source code for path traversal vulnerabilities."""

    def __init__(self) -> None:
        self._compiled: dict = {}
        for lang, patterns in _VULNERABILITY_PATTERNS.items():
            self._compiled[lang] = [
                (re.compile(p, re.IGNORECASE), sev, ptype, desc, rec)
                for p, sev, ptype, desc, rec in patterns
            ]

    def scan(self, config: PathTraversalScanConfig) -> PathTraversalScanReport:
        findings: List[PathTraversalFinding] = []
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
        by_language: dict = {}
        for f in findings:
            by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1
            by_language[f.language] = by_language.get(f.language, 0) + 1

        return PathTraversalScanReport(
            scan_path=str(config.scan_path),
            total_findings=len(findings),
            files_scanned=files_scanned,
            findings=findings,
            by_severity=by_severity,
            by_language=by_language,
        )

    def _scan_file(self, file_path: Path) -> List[PathTraversalFinding]:
        findings: List[PathTraversalFinding] = []
        lang = _LANG_EXTENSIONS.get(file_path.suffix.lower())
        if not lang or lang not in self._compiled:
            return findings

        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return findings

        for line_num, line in enumerate(lines, 1):
            for regex, sev, ptype, desc, rec in self._compiled[lang]:
                if regex.search(line):
                    findings.append(PathTraversalFinding(
                        file_path=str(file_path),
                        line_number=line_num,
                        severity=PathTraversalSeverity(sev),
                        language=lang,
                        pattern_type=ptype,
                        code_snippet=line.strip()[:150],
                        description=desc,
                        recommendation=rec,
                    ))

        return findings
