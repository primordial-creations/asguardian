"""Data exfiltration pattern detector."""

import os
import re
from pathlib import Path
from typing import List

from Asgard.Heimdall.Security.DataExfil.models.data_exfil_models import (
    ExfilFinding,
    ExfilScanConfig,
    ExfilScanReport,
    ExfilSeverity,
    ExfilType,
)

_EXFIL_PATTERNS = {
    "http_exfil": ("HIGH", "credentials", [
        r"requests\.(?:post|put)\s*\([^)]*(?:password|secret|key|token|credential|ssn|credit)",
        r"urllib.*(?:urlopen|Request).*(?:password|secret|key|token)",
        r"fetch\s*\([^)]*method:\s*['\"](?:POST|PUT)['\"][^)]*(?:password|secret|key)",
        r"axios\.(?:post|put)\s*\([^)]*(?:password|secret|key)",
    ]),
    "dns_exfil": ("HIGH", "encoded_data", [
        r"dns.*(?:query|resolve|lookup).*(?:encode|base64)",
        r"socket\.gethostbyname\s*\([^)]*(?:encode|base64)",
        r"\.(?:burpcollaborator|dnsbin|requestbin)",
    ]),
    "email_exfil": ("HIGH", "credentials", [
        r"smtplib.*(?:sendmail|send_message).*(?:password|secret|key|credential)",
        r"nodemailer.*(?:password|secret|key)",
    ]),
    "ftp_exfil": ("HIGH", "credentials", [
        r"ftplib.*(?:storbinary|storlines).*(?:password|secret|key|credential)",
        r"sftp.*(?:put|upload).*(?:password|secret)",
    ]),
    "cloud_exfil": ("HIGH", "credentials", [
        r"boto3.*(?:put_object|upload).*(?:password|secret|key)",
        r"s3.*(?:put|upload).*(?:password|secret|credential)",
        r"azure.*(?:upload|blob).*(?:password|secret)",
        r"dropbox.*(?:upload|files_upload)",
    ]),
    "webhook_exfil": ("MEDIUM", "mixed", [
        r"(?:slack|discord|telegram).*(?:webhook|api).*(?:password|secret|key)",
        r"hooks\.slack\.com",
        r"discord(?:app)?\.com/api/webhooks",
        r"api\.telegram\.org/bot",
    ]),
    "database_dump": ("HIGH", "database", [
        r"mysqldump|pg_dump|mongodump",
        r"SELECT\s+\*\s+.*INTO\s+OUTFILE",
        r"COPY\s+.*TO\s+['\"][^'\"]+['\"]",
        r"backup.*(?:database|table|collection)",
    ]),
    "file_collection": ("MEDIUM", "documents", [
        r"os\.walk.*(?:\.doc|\.pdf|\.xls|\.ppt|\.txt)",
        r"glob.*(?:\.doc|\.pdf|\.xls|\.ppt)",
        r"zipfile.*(?:write|writestr).*(?:password|secret|credential)",
    ]),
    "clipboard_theft": ("MEDIUM", "clipboard", [
        r"pyperclip|clipboard",
        r"GetClipboardData|OpenClipboard",
        r"navigator\.clipboard",
    ]),
    "screenshot": ("MEDIUM", "visual", [
        r"ImageGrab\.grab|pyautogui\.screenshot",
        r"screencapture|scrot|gnome-screenshot",
    ]),
    "keylog_exfil": ("CRITICAL", "keystrokes", [
        r"pynput.*(?:on_press|on_release).*(?:write|send|post)",
        r"keyboard.*(?:log|record).*(?:send|post|upload)",
        r"GetAsyncKeyState.*(?:send|post|write)",
    ]),
    "sensitive_data": ("CRITICAL", "pii", [
        r"(?:ssn|social.?security).*(?:send|post|upload|write)",
        r"(?:credit.?card|card.?number).*(?:send|post|upload)",
        r"(?:passport|driver.?license).*(?:send|post|upload)",
    ]),
    "encoded_exfil": ("MEDIUM", "encoded", [
        r"base64\.b64encode.*(?:send|post|request)",
        r"(?:encode|compress|encrypt).*(?:send|post|upload)",
        r"zlib\.compress.*(?:send|post)",
    ]),
    "covert_channel": ("HIGH", "hidden", [
        r"icmp.*(?:send|packet)",
        r"steganography|stego",
        r"(?:hide|embed).*(?:image|audio|video)",
    ]),
    "environment_exfil": ("HIGH", "config", [
        r"os\.environ.*(?:send|post|upload|request)",
        r"process\.env.*(?:send|post|fetch)",
        r"getenv.*(?:send|post|curl|wget)",
    ]),
}


class DataExfiltrationDetector:
    """Detects potential data exfiltration patterns in source code."""

    def __init__(self) -> None:
        self._compiled: dict = {}
        for etype, (severity, data_type, patterns) in _EXFIL_PATTERNS.items():
            self._compiled[etype] = {
                "regexes": [re.compile(p, re.IGNORECASE) for p in patterns],
                "severity": severity,
                "data_type": data_type,
            }

    def scan(self, config: ExfilScanConfig) -> ExfilScanReport:
        findings: List[ExfilFinding] = []
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
                    findings.extend(self._scan_file(fp))
                    files_scanned += 1

        by_severity: dict = {}
        by_type: dict = {}
        by_data_type: dict = {}
        for f in findings:
            by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1
            by_type[f.exfil_type.value] = by_type.get(f.exfil_type.value, 0) + 1
            by_data_type[f.data_type] = by_data_type.get(f.data_type, 0) + 1

        return ExfilScanReport(
            scan_path=str(config.scan_path),
            total_findings=len(findings),
            files_scanned=files_scanned,
            findings=findings,
            by_severity=by_severity,
            by_type=by_type,
            by_data_type=by_data_type,
        )

    def _scan_file(self, file_path: Path) -> List[ExfilFinding]:
        findings: List[ExfilFinding] = []
        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return findings

        for line_num, line in enumerate(lines, 1):
            for etype, config in self._compiled.items():
                for regex in config["regexes"]:
                    if regex.search(line):
                        findings.append(ExfilFinding(
                            file_path=str(file_path),
                            line_number=line_num,
                            exfil_type=ExfilType(etype),
                            severity=ExfilSeverity(config["severity"]),
                            description=f"{etype.replace('_', ' ').title()} pattern detected",
                            code_snippet=line.strip()[:150],
                            data_type=config["data_type"],
                        ))
                        break

        return findings
