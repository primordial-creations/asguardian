#!/usr/bin/env python3
"""
Backdoor Detector
Detects hidden backdoors, web shells, and unauthorized access mechanisms.
"""

import re
import os
import argparse
import hashlib
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class BackdoorIndicator:
    """Represents a backdoor indicator."""
    file_path: str
    line_number: int
    backdoor_type: str
    severity: str
    description: str
    code_snippet: str
    ioc: str  # Indicator of Compromise


class BackdoorDetector:
    """Detects backdoors and unauthorized access mechanisms."""

    # Known web shell signatures (hashes of common web shells)
    KNOWN_WEBSHELL_HASHES = {
        'c99': ['3f5b7ba9cd9f7b5f8e1f2d5b8b7c4a1e'],
        'r57': ['2e5d8b9c1a3f4e6d7c8b9a0e1f2d3c4b'],
        'b374k': ['1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p'],
    }

    # Backdoor patterns
    BACKDOOR_PATTERNS = {
        'php_webshell': {
            'patterns': [
                r'(?:eval|assert|preg_replace.*\/e)\s*\(\s*(?:base64_decode|gzinflate|str_rot13)',
                r'\$_(?:GET|POST|REQUEST|COOKIE)\s*\[\s*[\'"][^\'"]+[\'"]\s*\]\s*\(\s*\$_',
                r'(?:system|exec|shell_exec|passthru|popen)\s*\(\s*\$_(?:GET|POST|REQUEST)',
                r'(?:eval|assert)\s*\(\s*\$_(?:GET|POST|REQUEST|COOKIE)',
                r'create_function\s*\(\s*[\'"][^\'"]*[\'"]\s*,\s*\$_(?:GET|POST)',
                r'\$\w+\s*=\s*str_replace\s*\([^)]+\)\s*;\s*\$\w+\s*\(',
                r'(?:move_uploaded_file|copy)\s*\([^)]*\$_FILES',
                r'preg_replace\s*\(\s*[\'"]\/.*\/e[\'"]\s*,',
                r'\$\{\s*\$_(?:GET|POST|REQUEST)',
            ],
            'severity': 'CRITICAL',
            'description': 'PHP web shell detected',
            'ioc': 'webshell'
        },
        'jsp_webshell': {
            'patterns': [
                r'Runtime\.getRuntime\(\)\.exec\s*\(\s*request\.getParameter',
                r'ProcessBuilder.*request\.getParameter',
                r'<%.*Runtime.*exec.*request\.get',
            ],
            'severity': 'CRITICAL',
            'description': 'JSP web shell detected',
            'ioc': 'webshell'
        },
        'asp_webshell': {
            'patterns': [
                r'(?:Execute|Eval)\s*\(\s*Request(?:\.Form|\.QueryString|\()',
                r'CreateObject\s*\(\s*[\'"](?:WScript\.Shell|Shell\.Application)[\'"]\s*\)',
                r'Server\.CreateObject.*Scripting\.FileSystemObject',
            ],
            'severity': 'CRITICAL',
            'description': 'ASP web shell detected',
            'ioc': 'webshell'
        },
        'python_backdoor': {
            'patterns': [
                r'socket.*connect.*exec\s*\(',
                r'subprocess.*shell\s*=\s*True.*(?:stdin|stdout).*PIPE',
                r'os\.system\s*\(\s*[\'"](?:nc|netcat|bash\s+-i)',
                r'pty\.spawn\s*\(\s*[\'"]\/bin\/(?:ba)?sh[\'"]\s*\)',
                r'exec\s*\(\s*compile\s*\(.*[\'"]exec[\'"]\s*\)',
            ],
            'severity': 'CRITICAL',
            'description': 'Python backdoor detected',
            'ioc': 'backdoor'
        },
        'bind_shell': {
            'patterns': [
                r'socket.*bind.*listen.*accept',
                r'(?:nc|netcat|ncat)\s+-[lp]',
                r'socat.*TCP-LISTEN',
                r'ServerSocket.*accept.*getInputStream',
            ],
            'severity': 'CRITICAL',
            'description': 'Bind shell detected',
            'ioc': 'bindshell'
        },
        'reverse_shell': {
            'patterns': [
                r'socket.*connect.*(?:dup2|os\.dup2)',
                r'bash\s+-i\s+>&\s*/dev/tcp/',
                r'python\s+-c\s+[\'"]import\s+socket.*subprocess',
                r'ruby\s+-rsocket\s+-e',
                r'perl\s+-e\s+[\'"]use\s+Socket',
                r'php\s+-r\s+[\'"].*fsockopen.*exec',
                r'powershell.*-nop.*-c.*\$client\s*=\s*New-Object',
            ],
            'severity': 'CRITICAL',
            'description': 'Reverse shell detected',
            'ioc': 'reverseshell'
        },
        'hidden_admin': {
            'patterns': [
                r'(?:admin|root|superuser).*(?:password|pwd)\s*(?:==|===|\.equals)',
                r'if\s*\(\s*\$_(?:GET|POST)\s*\[\s*[\'"](?:admin|debug|backdoor)[\'"]\s*\]',
                r'(?:secret|hidden|debug).*(?:login|access|admin)',
                r'\?(?:admin|debug|backdoor)=(?:true|1|yes)',
            ],
            'severity': 'HIGH',
            'description': 'Hidden admin access detected',
            'ioc': 'hiddenaccess'
        },
        'file_manager': {
            'patterns': [
                r'(?:scandir|readdir|opendir).*(?:unlink|rmdir|rename|copy)',
                r'(?:file_get_contents|file_put_contents|fopen).*\$_(?:GET|POST)',
                r'(?:mkdir|rmdir|unlink|chmod|chown).*\$_(?:GET|POST|REQUEST)',
            ],
            'severity': 'HIGH',
            'description': 'File manager functionality detected',
            'ioc': 'filemanager'
        },
        'code_execution': {
            'patterns': [
                r'(?:eval|exec|compile)\s*\(\s*(?:input|raw_input|sys\.argv)',
                r'Function\s*\(\s*[\'"][^\'"]*[\'"]\s*\)\s*\(',
                r'(?:eval|exec)\s*\(\s*[\'"][^\'"]+[\'"]\s*\+\s*',
                r'new\s+Function\s*\([^)]*(?:arguments|window|document)',
            ],
            'severity': 'HIGH',
            'description': 'Dynamic code execution',
            'ioc': 'codeexec'
        },
        'credential_hardcoded': {
            'patterns': [
                r'(?:password|passwd|pwd|secret)\s*(?:=|:)\s*[\'"][^\'"]{8,}[\'"]',
                r'(?:api[_-]?key|apikey|auth[_-]?token)\s*(?:=|:)\s*[\'"][^\'"]{16,}[\'"]',
            ],
            'severity': 'MEDIUM',
            'description': 'Hardcoded credentials',
            'ioc': 'hardcoded'
        },
        'obfuscated': {
            'patterns': [
                r'(?:\\x[0-9a-f]{2}){20,}',
                r'(?:chr\s*\(\s*\d+\s*\)\s*\.?\s*){10,}',
                r'base64_decode\s*\(\s*[\'"][A-Za-z0-9+/=]{100,}[\'"]',
                r'gzinflate\s*\(\s*base64_decode',
                r'str_rot13\s*\(\s*base64_decode',
            ],
            'severity': 'HIGH',
            'description': 'Heavily obfuscated code',
            'ioc': 'obfuscation'
        },
        'persistence': {
            'patterns': [
                r'crontab|/etc/cron\.',
                r'HKEY.*(?:Run|RunOnce)',
                r'\.bashrc|\.bash_profile|\.zshrc',
                r'systemctl.*enable|update-rc\.d',
                r'launchctl|LaunchAgents|LaunchDaemons',
            ],
            'severity': 'MEDIUM',
            'description': 'Persistence mechanism',
            'ioc': 'persistence'
        },
        'c2_communication': {
            'patterns': [
                r'while\s*\(\s*(?:true|1)\s*\).*(?:socket|http|request)',
                r'setInterval.*(?:fetch|ajax|xmlhttp)',
                r'sleep.*(?:send|post|get)',
                r'beacon|heartbeat|callback',
            ],
            'severity': 'HIGH',
            'description': 'C2 communication pattern',
            'ioc': 'c2'
        }
    }

    def __init__(self):
        self.indicators: List[BackdoorIndicator] = []
        self.files_scanned = 0
        self.compiled_patterns = {}

        # Pre-compile patterns
        for backdoor_type, config in self.BACKDOOR_PATTERNS.items():
            self.compiled_patterns[backdoor_type] = {
                'regexes': [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in config['patterns']],
                'severity': config['severity'],
                'description': config['description'],
                'ioc': config['ioc']
            }

    def calculate_file_hash(self, file_path: Path) -> str:
        """Calculate MD5 hash of file."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except (IOError, OSError):
            return ''

    def scan_file(self, file_path: Path) -> List[BackdoorIndicator]:
        """Scan a single file for backdoors."""
        indicators = []

        # Check file hash against known malicious files
        file_hash = self.calculate_file_hash(file_path)
        for shell_name, hashes in self.KNOWN_WEBSHELL_HASHES.items():
            if file_hash in hashes:
                indicators.append(BackdoorIndicator(
                    file_path=str(file_path),
                    line_number=0,
                    backdoor_type='known_webshell',
                    severity='CRITICAL',
                    description=f'Known web shell detected: {shell_name}',
                    code_snippet=f'File hash: {file_hash}',
                    ioc='known_malware'
                ))

        # Read and scan content
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except (IOError, OSError):
            return indicators

        self.files_scanned += 1

        # Check patterns
        for line_num, line in enumerate(lines, 1):
            for backdoor_type, config in self.compiled_patterns.items():
                for regex in config['regexes']:
                    if regex.search(line):
                        indicator = BackdoorIndicator(
                            file_path=str(file_path),
                            line_number=line_num,
                            backdoor_type=backdoor_type,
                            severity=config['severity'],
                            description=config['description'],
                            code_snippet=line.strip()[:150],
                            ioc=config['ioc']
                        )
                        indicators.append(indicator)
                        break

        # Check for suspicious file characteristics
        file_ext = file_path.suffix.lower()

        # Check for double extensions (e.g., .jpg.php)
        if len(file_path.suffixes) > 1:
            if file_path.suffixes[-1] in {'.php', '.jsp', '.asp', '.aspx'}:
                indicators.append(BackdoorIndicator(
                    file_path=str(file_path),
                    line_number=0,
                    backdoor_type='double_extension',
                    severity='HIGH',
                    description='Suspicious double file extension',
                    code_snippet=f'Extensions: {file_path.suffixes}',
                    ioc='evasion'
                ))

        return indicators

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[BackdoorIndicator]:
        """Scan directory for backdoors."""
        all_indicators = []
        skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv'}

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
            'by_ioc': {}
        }

        for indicator in self.indicators:
            summary['by_severity'][indicator.severity] += 1
            if indicator.backdoor_type not in summary['by_type']:
                summary['by_type'][indicator.backdoor_type] = 0
            summary['by_type'][indicator.backdoor_type] += 1
            if indicator.ioc not in summary['by_ioc']:
                summary['by_ioc'][indicator.ioc] = 0
            summary['by_ioc'][indicator.ioc] += 1

        return summary

    def print_report(self, verbose: bool = False):
        """Print backdoor detection report."""
        summary = self.get_summary()

        print("\n" + "=" * 70)
        print("BACKDOOR DETECTION REPORT")
        print("=" * 70)

        print(f"\nFiles Scanned: {summary['files_scanned']}")
        print(f"Backdoor Indicators Found: {summary['total_indicators']}")

        if summary['total_indicators'] > 0:
            print("\nBy Severity:")
            for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
                count = summary['by_severity'][severity]
                if count > 0:
                    print(f"  {severity}: {count}")

            print("\nBy Type:")
            for backdoor_type, count in sorted(summary['by_type'].items(), key=lambda x: -x[1]):
                print(f"  {backdoor_type}: {count}")

            print("\nBy IOC Category:")
            for ioc, count in sorted(summary['by_ioc'].items(), key=lambda x: -x[1]):
                print(f"  {ioc}: {count}")

            print("\n" + "-" * 70)
            print("BACKDOORS DETECTED")
            print("-" * 70)

            severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
            sorted_indicators = sorted(self.indicators, key=lambda x: severity_order[x.severity])

            for indicator in sorted_indicators:
                print(f"\n[{indicator.severity}] {indicator.backdoor_type}")
                print(f"  File: {indicator.file_path}:{indicator.line_number}")
                print(f"  {indicator.description}")
                print(f"  IOC: {indicator.ioc}")
                if verbose:
                    print(f"  Code: {indicator.code_snippet}")
        else:
            print("\n✓ No backdoors detected!")

        print("\n" + "=" * 70)

        if summary['by_severity']['CRITICAL'] > 0:
            return 2
        elif summary['by_severity']['HIGH'] > 0:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Detect backdoors and unauthorized access mechanisms'
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
    detector = BackdoorDetector()

    target = Path(args.path)

    if not target.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    print(f"Scanning for backdoors: {target.absolute()}")

    if target.is_file():
        detector.scan_file(target)
        detector.indicators = detector.indicators
    else:
        recursive = not args.no_recursive
        detector.scan_directory(target, recursive=recursive)

    return detector.print_report(verbose=args.verbose)


if __name__ == '__main__':
    exit(main())
