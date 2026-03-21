#!/usr/bin/env python3
"""
Data Exfiltration Detector
Monitors code and configurations for potential data exfiltration patterns.
"""

import re
import os
import argparse
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class ExfilIndicator:
    """Represents a data exfiltration indicator."""
    file_path: str
    line_number: int
    exfil_type: str
    severity: str
    description: str
    code_snippet: str
    data_type: str


class DataExfiltrationDetector:
    """Detects potential data exfiltration patterns in code."""

    # Data exfiltration patterns
    EXFIL_PATTERNS = {
        'http_exfil': {
            'patterns': [
                r'requests\.(?:post|put)\s*\([^)]*(?:password|secret|key|token|credential|ssn|credit)',
                r'urllib.*(?:urlopen|Request).*(?:password|secret|key|token)',
                r'http\.(?:Post|Put)\s*\([^)]*(?:password|secret|key)',
                r'fetch\s*\([^)]*method:\s*[\'"](?:POST|PUT)[\'"][^)]*(?:password|secret|key)',
                r'axios\.(?:post|put)\s*\([^)]*(?:password|secret|key)',
                r'\$\.(?:post|ajax)\s*\([^)]*(?:password|secret|key)',
            ],
            'severity': 'HIGH',
            'description': 'HTTP-based data exfiltration',
            'data_type': 'credentials'
        },
        'dns_exfil': {
            'patterns': [
                r'dns.*(?:query|resolve|lookup).*(?:encode|base64)',
                r'socket\.gethostbyname\s*\([^)]*(?:encode|base64)',
                r'nslookup|dig\s+.*\$',
                r'\.(?:burpcollaborator|dnsbin|requestbin)',
            ],
            'severity': 'HIGH',
            'description': 'DNS-based data exfiltration',
            'data_type': 'encoded_data'
        },
        'email_exfil': {
            'patterns': [
                r'smtplib.*(?:sendmail|send_message).*(?:password|secret|key|credential)',
                r'email\.mime.*(?:password|secret|key)',
                r'nodemailer.*(?:password|secret|key)',
                r'mail\s*\(.*(?:password|secret|key)',
            ],
            'severity': 'HIGH',
            'description': 'Email-based data exfiltration',
            'data_type': 'credentials'
        },
        'ftp_exfil': {
            'patterns': [
                r'ftplib.*(?:storbinary|storlines).*(?:password|secret|key|credential)',
                r'ftp.*(?:put|stor).*(?:password|secret)',
                r'sftp.*(?:put|upload).*(?:password|secret)',
            ],
            'severity': 'HIGH',
            'description': 'FTP-based data exfiltration',
            'data_type': 'credentials'
        },
        'cloud_exfil': {
            'patterns': [
                r'boto3.*(?:put_object|upload).*(?:password|secret|key)',
                r's3.*(?:put|upload).*(?:password|secret|credential)',
                r'azure.*(?:upload|blob).*(?:password|secret)',
                r'google.*(?:storage|cloud).*(?:upload).*(?:password|secret)',
                r'dropbox.*(?:upload|files_upload)',
            ],
            'severity': 'HIGH',
            'description': 'Cloud storage exfiltration',
            'data_type': 'credentials'
        },
        'webhook_exfil': {
            'patterns': [
                r'(?:slack|discord|telegram).*(?:webhook|api).*(?:password|secret|key)',
                r'hooks\.slack\.com',
                r'discord(?:app)?\.com/api/webhooks',
                r'api\.telegram\.org/bot',
            ],
            'severity': 'MEDIUM',
            'description': 'Webhook-based exfiltration',
            'data_type': 'mixed'
        },
        'database_dump': {
            'patterns': [
                r'mysqldump|pg_dump|mongodump',
                r'SELECT\s+\*\s+.*INTO\s+OUTFILE',
                r'COPY\s+.*TO\s+[\'"]/',
                r'\.export\s*\(|\.dump\s*\(',
                r'backup.*(?:database|table|collection)',
            ],
            'severity': 'HIGH',
            'description': 'Database dump/export',
            'data_type': 'database'
        },
        'file_collection': {
            'patterns': [
                r'os\.walk.*(?:\.doc|\.pdf|\.xls|\.ppt|\.txt)',
                r'glob.*(?:\.doc|\.pdf|\.xls|\.ppt)',
                r'find\s+.*-name\s+[\'"]?\*\.(?:doc|pdf|xls|ppt)',
                r'zipfile.*(?:write|writestr).*(?:password|secret|credential)',
                r'tarfile.*(?:add|addfile)',
            ],
            'severity': 'MEDIUM',
            'description': 'Bulk file collection',
            'data_type': 'documents'
        },
        'clipboard_theft': {
            'patterns': [
                r'pyperclip|clipboard',
                r'GetClipboardData|OpenClipboard',
                r'pbpaste|xclip|xsel',
                r'navigator\.clipboard',
            ],
            'severity': 'MEDIUM',
            'description': 'Clipboard data access',
            'data_type': 'clipboard'
        },
        'screenshot': {
            'patterns': [
                r'ImageGrab\.grab|pyautogui\.screenshot',
                r'screencapture|scrot|gnome-screenshot',
                r'Graphics\.CopyFromScreen',
                r'html2canvas|dom-to-image',
            ],
            'severity': 'MEDIUM',
            'description': 'Screenshot capture',
            'data_type': 'visual'
        },
        'keylog_exfil': {
            'patterns': [
                r'pynput.*(?:on_press|on_release).*(?:write|send|post)',
                r'keyboard.*(?:log|record).*(?:send|post|upload)',
                r'GetAsyncKeyState.*(?:send|post|write)',
            ],
            'severity': 'CRITICAL',
            'description': 'Keylogger with exfiltration',
            'data_type': 'keystrokes'
        },
        'sensitive_data': {
            'patterns': [
                r'(?:ssn|social.?security).*(?:send|post|upload|write)',
                r'(?:credit.?card|card.?number).*(?:send|post|upload)',
                r'(?:bank.?account|routing.?number).*(?:send|post)',
                r'(?:passport|driver.?license).*(?:send|post|upload)',
            ],
            'severity': 'CRITICAL',
            'description': 'Sensitive PII exfiltration',
            'data_type': 'pii'
        },
        'encoded_exfil': {
            'patterns': [
                r'base64\.b64encode.*(?:send|post|request)',
                r'(?:encode|compress|encrypt).*(?:send|post|upload)',
                r'zlib\.compress.*(?:send|post)',
                r'hexlify.*(?:send|post|request)',
            ],
            'severity': 'MEDIUM',
            'description': 'Encoded data transmission',
            'data_type': 'encoded'
        },
        'covert_channel': {
            'patterns': [
                r'icmp.*(?:send|packet)',
                r'steganography|stego',
                r'(?:hide|embed).*(?:image|audio|video)',
                r'invisible.*(?:text|char)',
            ],
            'severity': 'HIGH',
            'description': 'Covert channel communication',
            'data_type': 'hidden'
        },
        'environment_exfil': {
            'patterns': [
                r'os\.environ.*(?:send|post|upload|request)',
                r'process\.env.*(?:send|post|fetch)',
                r'getenv.*(?:send|post|curl|wget)',
                r'System\.getenv.*(?:send|post|http)',
            ],
            'severity': 'HIGH',
            'description': 'Environment variable exfiltration',
            'data_type': 'config'
        }
    }

    def __init__(self):
        self.indicators: List[ExfilIndicator] = []
        self.files_scanned = 0
        self.compiled_patterns = {}

        # Pre-compile patterns
        for exfil_type, config in self.EXFIL_PATTERNS.items():
            self.compiled_patterns[exfil_type] = {
                'regexes': [re.compile(p, re.IGNORECASE) for p in config['patterns']],
                'severity': config['severity'],
                'description': config['description'],
                'data_type': config['data_type']
            }

    def scan_file(self, file_path: Path) -> List[ExfilIndicator]:
        """Scan a single file for exfiltration patterns."""
        indicators = []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except (IOError, OSError):
            return indicators

        self.files_scanned += 1

        for line_num, line in enumerate(lines, 1):
            for exfil_type, config in self.compiled_patterns.items():
                for regex in config['regexes']:
                    if regex.search(line):
                        indicator = ExfilIndicator(
                            file_path=str(file_path),
                            line_number=line_num,
                            exfil_type=exfil_type,
                            severity=config['severity'],
                            description=config['description'],
                            code_snippet=line.strip()[:150],
                            data_type=config['data_type']
                        )
                        indicators.append(indicator)
                        break

        return indicators

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[ExfilIndicator]:
        """Scan directory for exfiltration patterns."""
        all_indicators = []
        skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'vendor'}

        if recursive:
            for root, dirs, files in os.walk(directory):
                dirs[:] = [d for d in dirs if d not in skip_dirs]

                for file in files:
                    file_path = Path(root) / file
                    indicators = self.scan_file(file_path)
                    all_indicators.extend(indicators)
        else:
            for item in directory.iterdir():
                if item.is_file():
                    indicators = self.scan_file(item)
                    all_indicators.extend(indicators)

        self.indicators = all_indicators
        return all_indicators

    def get_summary(self) -> Dict:
        """Get summary of findings."""
        summary = {
            'total_indicators': len(self.indicators),
            'files_scanned': self.files_scanned,
            'by_severity': {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0},
            'by_type': {},
            'by_data_type': {}
        }

        for indicator in self.indicators:
            summary['by_severity'][indicator.severity] += 1
            if indicator.exfil_type not in summary['by_type']:
                summary['by_type'][indicator.exfil_type] = 0
            summary['by_type'][indicator.exfil_type] += 1
            if indicator.data_type not in summary['by_data_type']:
                summary['by_data_type'][indicator.data_type] = 0
            summary['by_data_type'][indicator.data_type] += 1

        return summary

    def print_report(self, verbose: bool = False):
        """Print exfiltration detection report."""
        summary = self.get_summary()

        print("\n" + "=" * 70)
        print("DATA EXFILTRATION DETECTION REPORT")
        print("=" * 70)

        print(f"\nFiles Scanned: {summary['files_scanned']}")
        print(f"Exfiltration Indicators Found: {summary['total_indicators']}")

        if summary['total_indicators'] > 0:
            print("\nBy Severity:")
            for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
                count = summary['by_severity'][severity]
                if count > 0:
                    print(f"  {severity}: {count}")

            print("\nBy Exfiltration Type:")
            for exfil_type, count in sorted(summary['by_type'].items(), key=lambda x: -x[1]):
                print(f"  {exfil_type}: {count}")

            print("\nBy Data Type:")
            for data_type, count in sorted(summary['by_data_type'].items(), key=lambda x: -x[1]):
                print(f"  {data_type}: {count}")

            print("\n" + "-" * 70)
            print("EXFILTRATION INDICATORS DETECTED")
            print("-" * 70)

            severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
            sorted_indicators = sorted(self.indicators, key=lambda x: severity_order[x.severity])

            for indicator in sorted_indicators:
                print(f"\n[{indicator.severity}] {indicator.exfil_type}")
                print(f"  File: {indicator.file_path}:{indicator.line_number}")
                print(f"  {indicator.description}")
                print(f"  Data type: {indicator.data_type}")
                if verbose:
                    print(f"  Code: {indicator.code_snippet}")
        else:
            print("\n✓ No data exfiltration patterns detected!")

        print("\n" + "=" * 70)

        if summary['by_severity']['CRITICAL'] > 0:
            return 2
        elif summary['by_severity']['HIGH'] > 0:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Detect potential data exfiltration patterns'
    )
    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='File or directory to scan (default: current directory)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show verbose output with code snippets'
    )
    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        default=True,
        help='Scan directories recursively (default: True)'
    )
    parser.add_argument(
        '--no-recursive',
        action='store_true',
        help='Do not scan directories recursively'
    )

    args = parser.parse_args()
    detector = DataExfiltrationDetector()

    target = Path(args.path)

    if not target.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    print(f"Scanning for data exfiltration: {target.absolute()}")

    if target.is_file():
        detector.scan_file(target)
        detector.indicators = detector.indicators
    else:
        recursive = not args.no_recursive
        detector.scan_directory(target, recursive=recursive)

    return detector.print_report(verbose=args.verbose)


if __name__ == '__main__':
    exit(main())
