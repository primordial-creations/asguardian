"""Security log analyzer — scans log files for security events and suspicious activity."""

import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from Asgard.Heimdall.Security.LogAnalysis.models.log_models import LogAnalysisReport, LogEvent

_EVENT_PATTERNS: dict = {
    "failed_login": ("MEDIUM", "Failed authentication attempt", [
        r"failed\s+(?:password|login|authentication)",
        r"authentication\s+fail(?:ure|ed)",
        r"invalid\s+(?:user|password|credentials)",
        r"access\s+denied",
    ]),
    "brute_force": ("HIGH", "Potential brute force attack", [
        r"multiple\s+failed\s+logins",
        r"too\s+many\s+authentication\s+failures",
        r"account\s+locked",
        r"blocking\s+(?:ip|address)",
    ]),
    "sql_injection": ("CRITICAL", "Potential SQL injection attempt", [
        r"(?:union|select|insert|update|delete|drop)\s+.*(?:from|into|table)",
        r"(?:--|;|')\s*(?:or|and)\s+['\"]?[0-9]",
        r"information_schema",
    ]),
    "xss_attempt": ("HIGH", "Potential XSS attempt", [
        r"<script[^>]*>",
        r"javascript:",
        r"on(?:error|load|click|mouse)\s*=",
        r"document\.(?:cookie|write|location)",
    ]),
    "path_traversal": ("HIGH", "Potential path traversal attempt", [
        r"\.\./",
        r"%2e%2e/",
        r"/etc/(?:passwd|shadow)",
        r"/proc/self",
    ]),
    "command_injection": ("CRITICAL", "Potential command injection", [
        r";\s*(?:ls|cat|rm|wget|curl|bash|sh|nc)\s",
        r"\|\s*(?:bash|sh|nc|netcat)",
        r"\$\(.*\)",
    ]),
    "dos_attack": ("HIGH", "Potential DoS attack", [
        r"rate\s+limit\s+exceeded",
        r"connection\s+flood",
        r"too\s+many\s+connections",
    ]),
    "privilege_escalation": ("HIGH", "Privilege escalation attempt", [
        r"sudo.*(?:incorrect|failed)",
        r"su:\s+(?:failed|incorrect)",
        r"privilege.*escalat",
    ]),
    "malware_indicator": ("CRITICAL", "Malware indicator detected", [
        r"malware|virus|trojan|ransomware",
        r"backdoor|reverse\s*shell|meterpreter",
    ]),
    "sensitive_file_access": ("HIGH", "Sensitive file access attempt", [
        r"/etc/passwd|/etc/shadow",
        r"\.ssh/.*key",
        r"credentials|secrets|password",
    ]),
}

_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_TS_PATTERNS = [
    re.compile(r"\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}"),
    re.compile(r"\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}"),
]
_DEFAULT_LOG_PATTERNS = ["*.log", "*.txt", "*access*", "*error*", "*auth*", "*secure*", "*syslog*"]


class LogAnalyzer:
    """Scans log files for security-relevant events."""

    def __init__(self) -> None:
        self._compiled: dict = {}
        for etype, (severity, desc, patterns) in _EVENT_PATTERNS.items():
            self._compiled[etype] = {
                "severity": severity,
                "description": desc,
                "regexes": [re.compile(p, re.IGNORECASE) for p in patterns],
            }

    def analyze_file(self, file_path: Path) -> LogAnalysisReport:
        report = LogAnalysisReport()
        ip_counts: Dict[str, int] = defaultdict(int)
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    report.lines_analyzed += 1
                    events = self._analyze_line(line, str(file_path), line_num)
                    report.events.extend(events)
                    for e in events:
                        if e.source_ip:
                            ip_counts[e.source_ip] += 1
        except OSError:
            pass

        self._aggregate(report, ip_counts)
        return report

    def analyze_directory(self, directory: Path, patterns: Optional[List[str]] = None) -> LogAnalysisReport:
        report = LogAnalysisReport()
        ip_counts: Dict[str, int] = defaultdict(int)
        for pattern in (patterns or _DEFAULT_LOG_PATTERNS):
            for log_file in directory.rglob(pattern):
                if not log_file.is_file():
                    continue
                try:
                    with open(log_file, encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            report.lines_analyzed += 1
                            events = self._analyze_line(line, str(log_file), line_num)
                            report.events.extend(events)
                            for e in events:
                                if e.source_ip:
                                    ip_counts[e.source_ip] += 1
                except OSError:
                    pass

        self._aggregate(report, ip_counts)
        return report

    def _analyze_line(self, line: str, file_path: str, line_num: int) -> List[LogEvent]:
        events: List[LogEvent] = []
        ts_match = next((p.search(line) for p in _TS_PATTERNS if p.search(line)), None)
        timestamp = ts_match.group(0) if ts_match else ""
        ip_match = _IP_RE.search(line)
        source_ip = ip_match.group(0) if ip_match else ""

        for etype, config in self._compiled.items():
            for regex in config["regexes"]:
                if regex.search(line):
                    events.append(LogEvent(
                        file_path=file_path,
                        line_number=line_num,
                        timestamp=timestamp,
                        event_type=etype,
                        severity=config["severity"],
                        description=config["description"],
                        raw_line=line.strip()[:200],
                        source_ip=source_ip,
                    ))
                    break

        return events

    def _aggregate(self, report: LogAnalysisReport, ip_counts: Dict[str, int]) -> None:
        report.total_events = len(report.events)
        by_severity: dict = {}
        by_type: dict = {}
        for e in report.events:
            by_severity[e.severity] = by_severity.get(e.severity, 0) + 1
            by_type[e.event_type] = by_type.get(e.event_type, 0) + 1
        report.by_severity = by_severity
        report.by_type = by_type
        report.top_ips = sorted(ip_counts.items(), key=lambda x: -x[1])[:10]
