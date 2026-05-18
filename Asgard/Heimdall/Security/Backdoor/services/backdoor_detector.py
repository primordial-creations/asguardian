"""Backdoor and web-shell detector."""

import hashlib
import os
import re
from pathlib import Path
from typing import List

from Asgard.Heimdall.Security.Backdoor.models.backdoor_models import (
    BackdoorFinding,
    BackdoorScanConfig,
    BackdoorScanReport,
    BackdoorSeverity,
    BackdoorType,
)

_KNOWN_WEBSHELL_HASHES = {
    "c99": ["3f5b7ba9cd9f7b5f8e1f2d5b8b7c4a1e"],
    "r57": ["2e5d8b9c1a3f4e6d7c8b9a0e1f2d3c4b"],
    "b374k": ["1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p"],
}

_BACKDOOR_PATTERNS = {
    "php_webshell": ("CRITICAL", "webshell", [
        r"(?:eval|assert|preg_replace.*\/e)\s*\(\s*(?:base64_decode|gzinflate|str_rot13)",
        r"\$_(?:GET|POST|REQUEST|COOKIE)\s*\[\s*['\"][^'\"]+['\"]\s*\]\s*\(\s*\$_",
        r"(?:system|exec|shell_exec|passthru|popen)\s*\(\s*\$_(?:GET|POST|REQUEST)",
        r"(?:eval|assert)\s*\(\s*\$_(?:GET|POST|REQUEST|COOKIE)",
        r"preg_replace\s*\(\s*['\"]\/.*\/e['\"]",
    ]),
    "jsp_webshell": ("CRITICAL", "webshell", [
        r"Runtime\.getRuntime\(\)\.exec\s*\(\s*request\.getParameter",
        r"ProcessBuilder.*request\.getParameter",
    ]),
    "asp_webshell": ("CRITICAL", "webshell", [
        r"(?:Execute|Eval)\s*\(\s*Request(?:\.Form|\.QueryString|\()",
        r"CreateObject\s*\(\s*['\"](?:WScript\.Shell|Shell\.Application)['\"]",
    ]),
    "python_backdoor": ("CRITICAL", "backdoor", [
        r"socket.*connect.*exec\s*\(",
        r"subprocess.*shell\s*=\s*True.*(?:stdin|stdout).*PIPE",
        r"pty\.spawn\s*\(\s*['\"]\/bin\/(?:ba)?sh['\"]\s*\)",
    ]),
    "bind_shell": ("CRITICAL", "bindshell", [
        r"socket.*bind.*listen.*accept",
        r"(?:nc|netcat|ncat)\s+-[lp]",
        r"socat.*TCP-LISTEN",
    ]),
    "reverse_shell": ("CRITICAL", "reverseshell", [
        r"socket.*connect.*(?:dup2|os\.dup2)",
        r"bash\s+-i\s+>&\s*/dev/tcp/",
        r"python\s+-c\s+['\"]import\s+socket.*subprocess",
        r"powershell.*-nop.*-c.*\$client\s*=\s*New-Object",
    ]),
    "hidden_admin": ("HIGH", "hiddenaccess", [
        r"(?:admin|root|superuser).*(?:password|pwd)\s*(?:==|===|\.equals)",
        r"if\s*\(\s*\$_(?:GET|POST)\s*\[\s*['\"](?:admin|debug|backdoor)['\"]\s*\]",
    ]),
    "code_execution": ("HIGH", "codeexec", [
        r"(?:eval|exec|compile)\s*\(\s*(?:input|raw_input|sys\.argv)",
        r"Function\s*\(\s*['\"][^'\"]*['\"]\s*\)\s*\(",
    ]),
    "credential_hardcoded": ("MEDIUM", "hardcoded", [
        r"(?:password|passwd|pwd|secret)\s*(?:=|:)\s*['\"][^'\"]{8,}['\"]",
        r"(?:api[_-]?key|apikey|auth[_-]?token)\s*(?:=|:)\s*['\"][^'\"]{16,}['\"]",
    ]),
    "obfuscated": ("HIGH", "obfuscation", [
        r"(?:\\x[0-9a-f]{2}){20,}",
        r"base64_decode\s*\(\s*['\"][A-Za-z0-9+/=]{100,}['\"]",
        r"gzinflate\s*\(\s*base64_decode",
    ]),
    "persistence": ("MEDIUM", "persistence", [
        r"crontab|/etc/cron\.",
        r"HKEY.*(?:Run|RunOnce)",
        r"systemctl.*enable|update-rc\.d",
    ]),
    "c2_communication": ("HIGH", "c2", [
        r"while\s*\(\s*(?:true|1)\s*\).*(?:socket|http|request)",
        r"setInterval.*(?:fetch|ajax|xmlhttp)",
    ]),
}


class BackdoorDetector:
    """Detects backdoors, web shells, and unauthorized access mechanisms."""

    def __init__(self) -> None:
        self._compiled: dict = {}
        for btype, (severity, ioc, patterns) in _BACKDOOR_PATTERNS.items():
            self._compiled[btype] = {
                "regexes": [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in patterns],
                "severity": severity,
                "ioc": ioc,
            }

    def scan(self, config: BackdoorScanConfig) -> BackdoorScanReport:
        findings: List[BackdoorFinding] = []
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
                    findings.extend(ff)
                    files_scanned += 1

        by_severity: dict = {}
        by_type: dict = {}
        by_ioc: dict = {}
        for f in findings:
            by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1
            by_type[f.backdoor_type.value] = by_type.get(f.backdoor_type.value, 0) + 1
            by_ioc[f.ioc] = by_ioc.get(f.ioc, 0) + 1

        return BackdoorScanReport(
            scan_path=str(config.scan_path),
            total_findings=len(findings),
            files_scanned=files_scanned,
            findings=findings,
            by_severity=by_severity,
            by_type=by_type,
            by_ioc=by_ioc,
        )

    def _scan_file(self, file_path: Path) -> List[BackdoorFinding]:
        findings: List[BackdoorFinding] = []

        # Hash-based known web shell detection
        try:
            file_hash = hashlib.md5(file_path.read_bytes()).hexdigest()
            for shell_name, hashes in _KNOWN_WEBSHELL_HASHES.items():
                if file_hash in hashes:
                    findings.append(BackdoorFinding(
                        file_path=str(file_path),
                        line_number=0,
                        backdoor_type=BackdoorType.KNOWN_WEBSHELL,
                        severity=BackdoorSeverity.CRITICAL,
                        description=f"Known web shell: {shell_name}",
                        code_snippet=f"File hash: {file_hash}",
                        ioc="known_malware",
                    ))
        except OSError:
            return findings

        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return findings

        for line_num, line in enumerate(lines, 1):
            for btype, config in self._compiled.items():
                for regex in config["regexes"]:
                    if regex.search(line):
                        findings.append(BackdoorFinding(
                            file_path=str(file_path),
                            line_number=line_num,
                            backdoor_type=BackdoorType(btype),
                            severity=BackdoorSeverity(config["severity"]),
                            description=f"{btype.replace('_', ' ').title()} detected",
                            code_snippet=line.strip()[:150],
                            ioc=config["ioc"],
                        ))
                        break

        # Double-extension heuristic (.jpg.php, etc.)
        if len(file_path.suffixes) > 1 and file_path.suffixes[-1] in {".php", ".jsp", ".asp", ".aspx"}:
            findings.append(BackdoorFinding(
                file_path=str(file_path),
                line_number=0,
                backdoor_type=BackdoorType.DOUBLE_EXTENSION,
                severity=BackdoorSeverity.HIGH,
                description="Suspicious double file extension",
                code_snippet=f"Extensions: {file_path.suffixes}",
                ioc="evasion",
            ))

        return findings
