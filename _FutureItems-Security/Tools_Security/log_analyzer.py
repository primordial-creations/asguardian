#!/usr/bin/env python3
"""
Security Log Analyzer
Analyzes log files for security events and suspicious activity.
"""

import re
import os
import argparse
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class SecurityEvent:
    """Represents a security event found in logs."""
    file_path: str
    line_number: int
    timestamp: str
    event_type: str
    severity: str
    description: str
    raw_line: str
    source_ip: str = ''


class LogAnalyzer:
    """Analyzes log files for security events."""

    # Security event patterns
    EVENT_PATTERNS = {
        'failed_login': {
            'patterns': [
                r'failed\s+(?:password|login|authentication)',
                r'authentication\s+fail(?:ure|ed)',
                r'invalid\s+(?:user|password|credentials)',
                r'login\s+incorrect',
                r'access\s+denied',
                r'permission\s+denied'
            ],
            'severity': 'MEDIUM',
            'description': 'Failed authentication attempt'
        },
        'successful_login': {
            'patterns': [
                r'accepted\s+(?:password|publickey)',
                r'session\s+opened',
                r'successful\s+login',
                r'authentication\s+success'
            ],
            'severity': 'INFO',
            'description': 'Successful authentication'
        },
        'brute_force': {
            'patterns': [
                r'multiple\s+failed\s+logins',
                r'too\s+many\s+authentication\s+failures',
                r'maximum\s+(?:login\s+)?attempts',
                r'account\s+locked',
                r'blocking\s+(?:ip|address)'
            ],
            'severity': 'HIGH',
            'description': 'Potential brute force attack'
        },
        'sql_injection': {
            'patterns': [
                r'(?:union|select|insert|update|delete|drop)\s+.*(?:from|into|table)',
                r'(?:--|;|\')\s*(?:or|and)\s+[\'"0-9]',
                r'information_schema',
                r'sql\s*(?:syntax|error|exception)',
                r'mysql_fetch|pg_query|sqlite_query'
            ],
            'severity': 'CRITICAL',
            'description': 'Potential SQL injection attempt'
        },
        'xss_attempt': {
            'patterns': [
                r'<script[^>]*>',
                r'javascript:',
                r'on(?:error|load|click|mouse)\s*=',
                r'eval\s*\(',
                r'document\.(?:cookie|write|location)'
            ],
            'severity': 'HIGH',
            'description': 'Potential XSS attempt'
        },
        'path_traversal': {
            'patterns': [
                r'\.\./',
                r'%2e%2e/',
                r'/etc/(?:passwd|shadow)',
                r'/proc/self',
                r'\\\.\\\.\\\\',
            ],
            'severity': 'HIGH',
            'description': 'Potential path traversal attempt'
        },
        'command_injection': {
            'patterns': [
                r';\s*(?:ls|cat|rm|wget|curl|bash|sh|nc)\s',
                r'\|\s*(?:bash|sh|nc|netcat)',
                r'\$\(.*\)',
                r'`[^`]+`'
            ],
            'severity': 'CRITICAL',
            'description': 'Potential command injection'
        },
        'port_scan': {
            'patterns': [
                r'port\s*scan',
                r'connection\s+refused.*multiple',
                r'nmap',
                r'masscan'
            ],
            'severity': 'MEDIUM',
            'description': 'Potential port scanning activity'
        },
        'dos_attack': {
            'patterns': [
                r'dos\s+attack',
                r'rate\s+limit\s+exceeded',
                r'connection\s+flood',
                r'syn\s+flood',
                r'too\s+many\s+connections'
            ],
            'severity': 'HIGH',
            'description': 'Potential DoS attack'
        },
        'privilege_escalation': {
            'patterns': [
                r'sudo.*(?:incorrect|failed)',
                r'su:\s+(?:failed|incorrect)',
                r'privilege.*escalat',
                r'root.*(?:failed|denied)'
            ],
            'severity': 'HIGH',
            'description': 'Privilege escalation attempt'
        },
        'malware_indicator': {
            'patterns': [
                r'malware|virus|trojan|ransomware',
                r'backdoor',
                r'reverse\s*shell',
                r'bind\s*shell',
                r'meterpreter'
            ],
            'severity': 'CRITICAL',
            'description': 'Malware indicator detected'
        },
        'sensitive_file_access': {
            'patterns': [
                r'/etc/passwd|/etc/shadow',
                r'\.ssh/.*key',
                r'\.(?:bash_history|mysql_history)',
                r'credentials|secrets|password'
            ],
            'severity': 'HIGH',
            'description': 'Sensitive file access attempt'
        },
        'error': {
            'patterns': [
                r'error|exception|fatal|critical',
                r'stack\s*trace',
                r'segmentation\s+fault',
                r'core\s+dump'
            ],
            'severity': 'LOW',
            'description': 'Application error'
        }
    }

    # IP address pattern
    IP_PATTERN = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')

    # Timestamp patterns
    TIMESTAMP_PATTERNS = [
        r'\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}',
        r'\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}',
        r'\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2}'
    ]

    def __init__(self):
        self.events: List[SecurityEvent] = []
        self.ip_stats: Dict[str, int] = defaultdict(int)
        self.lines_analyzed = 0
        self.compiled_patterns = {}

        # Pre-compile patterns
        for event_type, config in self.EVENT_PATTERNS.items():
            self.compiled_patterns[event_type] = {
                'regexes': [re.compile(p, re.IGNORECASE) for p in config['patterns']],
                'severity': config['severity'],
                'description': config['description']
            }

    def extract_timestamp(self, line: str) -> str:
        """Extract timestamp from log line."""
        for pattern in self.TIMESTAMP_PATTERNS:
            match = re.search(pattern, line)
            if match:
                return match.group(0)
        return ''

    def extract_ip(self, line: str) -> str:
        """Extract IP address from log line."""
        match = self.IP_PATTERN.search(line)
        return match.group(0) if match else ''

    def analyze_line(self, line: str, file_path: str, line_number: int) -> List[SecurityEvent]:
        """Analyze a single log line for security events."""
        events = []

        for event_type, config in self.compiled_patterns.items():
            for regex in config['regexes']:
                if regex.search(line):
                    event = SecurityEvent(
                        file_path=file_path,
                        line_number=line_number,
                        timestamp=self.extract_timestamp(line),
                        event_type=event_type,
                        severity=config['severity'],
                        description=config['description'],
                        raw_line=line.strip()[:200],
                        source_ip=self.extract_ip(line)
                    )
                    events.append(event)

                    # Track IP statistics
                    if event.source_ip:
                        self.ip_stats[event.source_ip] += 1

                    break  # Only match once per event type

        return events

    def analyze_file(self, file_path: Path) -> List[SecurityEvent]:
        """Analyze a log file for security events."""
        file_events = []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    self.lines_analyzed += 1
                    events = self.analyze_line(line, str(file_path), line_num)
                    file_events.extend(events)
        except (IOError, OSError) as e:
            print(f"Error reading {file_path}: {e}")

        return file_events

    def analyze_directory(self, directory: Path, patterns: List[str] = None) -> List[SecurityEvent]:
        """Analyze log files in a directory."""
        all_events = []

        if patterns is None:
            patterns = ['*.log', '*.txt', '*access*', '*error*', '*auth*', '*secure*', '*syslog*']

        for pattern in patterns:
            for log_file in directory.rglob(pattern):
                if log_file.is_file():
                    events = self.analyze_file(log_file)
                    all_events.extend(events)

        self.events = all_events
        return all_events

    def get_summary(self) -> Dict:
        """Get summary of findings."""
        summary = {
            'total_events': len(self.events),
            'lines_analyzed': self.lines_analyzed,
            'by_severity': defaultdict(int),
            'by_type': defaultdict(int),
            'top_ips': [],
            'timeline': defaultdict(int)
        }

        for event in self.events:
            summary['by_severity'][event.severity] += 1
            summary['by_type'][event.event_type] += 1

        # Top IPs
        sorted_ips = sorted(self.ip_stats.items(), key=lambda x: -x[1])
        summary['top_ips'] = sorted_ips[:10]

        return dict(summary)

    def print_report(self, verbose: bool = False):
        """Print analysis report."""
        summary = self.get_summary()

        print("\n" + "=" * 70)
        print("SECURITY LOG ANALYSIS REPORT")
        print("=" * 70)

        print(f"\nLines Analyzed: {summary['lines_analyzed']:,}")
        print(f"Security Events Found: {summary['total_events']}")

        # By severity
        print("\nEvents by Severity:")
        for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']:
            count = summary['by_severity'].get(severity, 0)
            if count > 0:
                print(f"  {severity}: {count}")

        # By type
        if summary['by_type']:
            print("\nEvents by Type:")
            for event_type, count in sorted(summary['by_type'].items(), key=lambda x: -x[1]):
                print(f"  {event_type}: {count}")

        # Top IPs
        if summary['top_ips']:
            print("\n" + "-" * 40)
            print("TOP SOURCE IPs")
            print("-" * 40)
            for ip, count in summary['top_ips']:
                print(f"  {ip}: {count} events")

        # Critical and High severity events
        critical_high = [e for e in self.events if e.severity in ['CRITICAL', 'HIGH']]
        if critical_high:
            print("\n" + "-" * 70)
            print("CRITICAL AND HIGH SEVERITY EVENTS")
            print("-" * 70)

            for event in critical_high[:20]:  # Limit to first 20
                print(f"\n[{event.severity}] {event.event_type}")
                print(f"  File: {event.file_path}:{event.line_number}")
                if event.timestamp:
                    print(f"  Time: {event.timestamp}")
                if event.source_ip:
                    print(f"  IP: {event.source_ip}")
                print(f"  {event.description}")
                if verbose:
                    print(f"  Log: {event.raw_line}")

            if len(critical_high) > 20:
                print(f"\n  ... and {len(critical_high) - 20} more")

        # Recommendations
        print("\n" + "-" * 40)
        print("RECOMMENDATIONS")
        print("-" * 40)

        if summary['by_severity'].get('CRITICAL', 0) > 0:
            print("\n• CRITICAL events detected - immediate investigation required")

        if summary['by_type'].get('brute_force', 0) > 0:
            print("\n• Implement rate limiting and account lockout policies")

        if summary['by_type'].get('sql_injection', 0) > 0:
            print("\n• Review application for SQL injection vulnerabilities")

        if summary['by_type'].get('xss_attempt', 0) > 0:
            print("\n• Implement Content Security Policy and input validation")

        if any(count > 100 for _, count in summary['top_ips']):
            print("\n• Consider blocking or rate-limiting high-activity IPs")

        print("\n" + "=" * 70)

        # Return exit code
        if summary['by_severity'].get('CRITICAL', 0) > 0:
            return 2
        elif summary['by_severity'].get('HIGH', 0) > 0:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Analyze log files for security events'
    )
    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='Log file or directory to analyze (default: current directory)'
    )
    parser.add_argument(
        '-p', '--pattern',
        action='append',
        help='File patterns to include (can be specified multiple times)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show verbose output with raw log lines'
    )
    parser.add_argument(
        '-o', '--output',
        help='Export results to JSON file'
    )

    args = parser.parse_args()
    analyzer = LogAnalyzer()

    target = Path(args.path)

    if not target.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    print(f"Analyzing logs: {target.absolute()}")

    if target.is_file():
        analyzer.analyze_file(target)
        analyzer.events = analyzer.events  # Set for report
    else:
        analyzer.analyze_directory(target, patterns=args.pattern)

    exit_code = analyzer.print_report(verbose=args.verbose)

    if args.output:
        import json

        output_data = {
            'timestamp': datetime.now().isoformat(),
            'summary': analyzer.get_summary(),
            'events': [
                {
                    'file': e.file_path,
                    'line': e.line_number,
                    'timestamp': e.timestamp,
                    'type': e.event_type,
                    'severity': e.severity,
                    'description': e.description,
                    'ip': e.source_ip
                }
                for e in analyzer.events
            ]
        }

        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)

        print(f"\nResults exported to: {args.output}")

    return exit_code


if __name__ == '__main__':
    exit(main())
