#!/usr/bin/env python3
"""
Command Injection Scanner
Detects OS command injection vulnerabilities in source code.
"""

import re
import os
import argparse
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class CommandInjectionIssue:
    """Represents a command injection vulnerability."""
    file_path: str
    line_number: int
    severity: str
    pattern_type: str
    code_snippet: str
    description: str
    recommendation: str


class CommandInjectionScanner:
    """Scans code for command injection vulnerabilities."""

    VULNERABILITY_PATTERNS = {
        'python': [
            {
                'pattern': r'os\.system\s*\(\s*(?:[\'"][^\'"]*[\'"].*\+|\+.*[\'"][^\'"]*[\'"]|f[\'"]|[^\'"]*%|[^\'"]*\.format\s*\()',
                'severity': 'CRITICAL',
                'type': 'os_system_concat',
                'description': 'os.system() with string concatenation/formatting',
                'recommendation': 'Use subprocess.run() with list arguments'
            },
            {
                'pattern': r'os\.system\s*\(\s*(?:input|raw_input|sys\.argv|request\.|args\.|params)',
                'severity': 'CRITICAL',
                'type': 'os_system_input',
                'description': 'os.system() with direct user input',
                'recommendation': 'Never pass user input to os.system()'
            },
            {
                'pattern': r'subprocess\.(?:call|run|Popen)\s*\([^)]*shell\s*=\s*True',
                'severity': 'HIGH',
                'type': 'subprocess_shell',
                'description': 'subprocess with shell=True',
                'recommendation': 'Use shell=False with list of arguments'
            },
            {
                'pattern': r'subprocess\.(?:call|run|Popen)\s*\(\s*f[\'"]',
                'severity': 'CRITICAL',
                'type': 'subprocess_fstring',
                'description': 'subprocess with f-string command',
                'recommendation': 'Use list arguments: ["cmd", arg1, arg2]'
            },
            {
                'pattern': r'os\.popen\s*\(',
                'severity': 'HIGH',
                'type': 'os_popen',
                'description': 'os.popen() is vulnerable to injection',
                'recommendation': 'Use subprocess.run() with list arguments'
            },
            {
                'pattern': r'(?:eval|exec)\s*\(\s*(?:input|raw_input|request\.|sys\.argv)',
                'severity': 'CRITICAL',
                'type': 'eval_input',
                'description': 'eval/exec with user input',
                'recommendation': 'Never use eval/exec with user input'
            },
            {
                'pattern': r'commands\.(?:getoutput|getstatusoutput)\s*\(',
                'severity': 'HIGH',
                'type': 'commands_module',
                'description': 'Deprecated commands module',
                'recommendation': 'Use subprocess with list arguments'
            }
        ],
        'javascript': [
            {
                'pattern': r'child_process\.exec\s*\(\s*(?:[`\'"][^\'"]*[\'"].*\+|\+.*[\'"][^\'"]*[\'"]|`[^`]*\$\{)',
                'severity': 'CRITICAL',
                'type': 'exec_concat',
                'description': 'child_process.exec with string interpolation',
                'recommendation': 'Use execFile() or spawn() with array arguments'
            },
            {
                'pattern': r'child_process\.exec\s*\(\s*(?:req\.|request\.|params\.|query\.)',
                'severity': 'CRITICAL',
                'type': 'exec_input',
                'description': 'child_process.exec with user input',
                'recommendation': 'Use execFile() with array arguments'
            },
            {
                'pattern': r'child_process\.execSync\s*\(',
                'severity': 'HIGH',
                'type': 'exec_sync',
                'description': 'execSync is vulnerable to injection',
                'recommendation': 'Use execFileSync() with array arguments'
            },
            {
                'pattern': r'eval\s*\(\s*(?:req\.|request\.|params\.|query\.)',
                'severity': 'CRITICAL',
                'type': 'eval_input',
                'description': 'eval() with user input',
                'recommendation': 'Never use eval() with user input'
            },
            {
                'pattern': r'new\s+Function\s*\([^)]*(?:req\.|request\.|params\.)',
                'severity': 'CRITICAL',
                'type': 'function_constructor',
                'description': 'Function constructor with user input',
                'recommendation': 'Avoid dynamic code generation'
            },
            {
                'pattern': r'vm\.runInContext\s*\([^)]*(?:req\.|request\.)',
                'severity': 'CRITICAL',
                'type': 'vm_input',
                'description': 'vm.runInContext with user input',
                'recommendation': 'Sanitize and validate all input'
            }
        ],
        'php': [
            {
                'pattern': r'(?:system|exec|shell_exec|passthru|popen|proc_open)\s*\(\s*\$_(?:GET|POST|REQUEST|COOKIE)',
                'severity': 'CRITICAL',
                'type': 'shell_superglobal',
                'description': 'Shell command with superglobal input',
                'recommendation': 'Use escapeshellarg() and escapeshellcmd()'
            },
            {
                'pattern': r'(?:system|exec|shell_exec|passthru)\s*\(\s*[\'"][^\'"]*[\'"]\s*\.\s*\$',
                'severity': 'CRITICAL',
                'type': 'shell_concat',
                'description': 'Shell command with string concatenation',
                'recommendation': 'Escape all variables with escapeshellarg()'
            },
            {
                'pattern': r'`\s*\$_(?:GET|POST|REQUEST)',
                'severity': 'CRITICAL',
                'type': 'backtick_superglobal',
                'description': 'Backtick execution with superglobal',
                'recommendation': 'Use escapeshellarg() on all input'
            },
            {
                'pattern': r'preg_replace\s*\(\s*[\'"][^\'"]*e[\'"]',
                'severity': 'CRITICAL',
                'type': 'preg_replace_e',
                'description': 'preg_replace with /e modifier',
                'recommendation': 'Use preg_replace_callback() instead'
            },
            {
                'pattern': r'(?:assert|create_function)\s*\(\s*\$_(?:GET|POST|REQUEST)',
                'severity': 'CRITICAL',
                'type': 'code_execution',
                'description': 'Code execution with user input',
                'recommendation': 'Never execute user-supplied code'
            }
        ],
        'ruby': [
            {
                'pattern': r'(?:system|exec|`|%x)\s*(?:\(\s*)?(?:[\'"][^\'"]*[\'"].*#\{|#\{.*[\'"])',
                'severity': 'CRITICAL',
                'type': 'shell_interpolation',
                'description': 'Shell command with interpolation',
                'recommendation': 'Use array form: system("cmd", arg1, arg2)'
            },
            {
                'pattern': r'(?:system|exec|`|%x)\s*(?:\(\s*)?params\[',
                'severity': 'CRITICAL',
                'type': 'shell_params',
                'description': 'Shell command with params input',
                'recommendation': 'Use Shellwords.escape() on user input'
            },
            {
                'pattern': r'IO\.popen\s*\([^)]*#\{',
                'severity': 'HIGH',
                'type': 'popen_interpolation',
                'description': 'IO.popen with interpolation',
                'recommendation': 'Use array form of IO.popen'
            },
            {
                'pattern': r'eval\s*\(\s*params\[',
                'severity': 'CRITICAL',
                'type': 'eval_params',
                'description': 'eval() with user params',
                'recommendation': 'Never eval user input'
            }
        ],
        'java': [
            {
                'pattern': r'Runtime\.getRuntime\(\)\.exec\s*\(\s*[^\)]*\+',
                'severity': 'CRITICAL',
                'type': 'runtime_exec_concat',
                'description': 'Runtime.exec with concatenation',
                'recommendation': 'Use ProcessBuilder with array'
            },
            {
                'pattern': r'Runtime\.getRuntime\(\)\.exec\s*\([^)]*request\.getParameter',
                'severity': 'CRITICAL',
                'type': 'runtime_exec_input',
                'description': 'Runtime.exec with request parameter',
                'recommendation': 'Validate and sanitize all input'
            },
            {
                'pattern': r'ProcessBuilder\s*\([^)]*\+',
                'severity': 'HIGH',
                'type': 'processbuilder_concat',
                'description': 'ProcessBuilder with string concatenation',
                'recommendation': 'Use separate array elements'
            }
        ],
        'csharp': [
            {
                'pattern': r'Process\.Start\s*\([^)]*\+',
                'severity': 'CRITICAL',
                'type': 'process_start_concat',
                'description': 'Process.Start with concatenation',
                'recommendation': 'Use ProcessStartInfo with array arguments'
            },
            {
                'pattern': r'Process\.Start\s*\([^)]*Request\[',
                'severity': 'CRITICAL',
                'type': 'process_start_input',
                'description': 'Process.Start with request input',
                'recommendation': 'Validate and sanitize all input'
            }
        ],
        'go': [
            {
                'pattern': r'exec\.Command\s*\(\s*[\'"][^\'"]+[\'"]\s*\+',
                'severity': 'CRITICAL',
                'type': 'exec_command_concat',
                'description': 'exec.Command with concatenation',
                'recommendation': 'Pass arguments as separate parameters'
            },
            {
                'pattern': r'exec\.Command\s*\(\s*[\'"](?:sh|bash|cmd)[\'"]\s*,\s*[\'"]-c[\'"]\s*,',
                'severity': 'HIGH',
                'type': 'shell_exec',
                'description': 'Shell execution with -c flag',
                'recommendation': 'Execute commands directly without shell'
            }
        ]
    }

    def __init__(self):
        self.issues: List[CommandInjectionIssue] = []
        self.files_scanned = 0
        self.compiled_patterns = {}

        # Pre-compile patterns
        for lang, patterns in self.VULNERABILITY_PATTERNS.items():
            self.compiled_patterns[lang] = []
            for p in patterns:
                try:
                    self.compiled_patterns[lang].append({
                        'regex': re.compile(p['pattern'], re.IGNORECASE),
                        **p
                    })
                except re.error:
                    pass

    def get_language(self, file_path: Path) -> str:
        """Determine language from file extension."""
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'javascript',
            '.jsx': 'javascript',
            '.tsx': 'javascript',
            '.php': 'php',
            '.rb': 'ruby',
            '.java': 'java',
            '.cs': 'csharp',
            '.go': 'go'
        }
        return ext_map.get(file_path.suffix.lower(), '')

    def scan_file(self, file_path: Path) -> List[CommandInjectionIssue]:
        """Scan a single file for command injection."""
        issues = []
        language = self.get_language(file_path)

        if not language or language not in self.compiled_patterns:
            return issues

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except (IOError, OSError):
            return issues

        self.files_scanned += 1

        for line_num, line in enumerate(lines, 1):
            for pattern_config in self.compiled_patterns[language]:
                if pattern_config['regex'].search(line):
                    issue = CommandInjectionIssue(
                        file_path=str(file_path),
                        line_number=line_num,
                        severity=pattern_config['severity'],
                        pattern_type=pattern_config['type'],
                        code_snippet=line.strip()[:150],
                        description=pattern_config['description'],
                        recommendation=pattern_config['recommendation']
                    )
                    issues.append(issue)

        return issues

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[CommandInjectionIssue]:
        """Scan directory for command injection vulnerabilities."""
        all_issues = []
        skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'vendor'}

        if recursive:
            for root, dirs, files in os.walk(directory):
                dirs[:] = [d for d in dirs if d not in skip_dirs]

                for file in files:
                    file_path = Path(root) / file
                    issues = self.scan_file(file_path)
                    all_issues.extend(issues)
        else:
            for item in directory.iterdir():
                if item.is_file():
                    issues = self.scan_file(item)
                    all_issues.extend(issues)

        self.issues = all_issues
        return all_issues

    def get_summary(self) -> Dict:
        """Get summary of findings."""
        summary = {
            'total_issues': len(self.issues),
            'files_scanned': self.files_scanned,
            'by_severity': {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0},
            'by_type': {}
        }

        for issue in self.issues:
            summary['by_severity'][issue.severity] += 1
            if issue.pattern_type not in summary['by_type']:
                summary['by_type'][issue.pattern_type] = 0
            summary['by_type'][issue.pattern_type] += 1

        return summary

    def print_report(self):
        """Print scan report."""
        summary = self.get_summary()

        print("\n" + "=" * 70)
        print("COMMAND INJECTION VULNERABILITY SCAN")
        print("=" * 70)

        print(f"\nFiles Scanned: {summary['files_scanned']}")
        print(f"Total Issues: {summary['total_issues']}")

        if summary['total_issues'] > 0:
            print("\nBy Severity:")
            for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
                count = summary['by_severity'][severity]
                if count > 0:
                    print(f"  {severity}: {count}")

            print("\n" + "-" * 70)
            print("VULNERABILITIES FOUND")
            print("-" * 70)

            severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
            sorted_issues = sorted(self.issues, key=lambda x: severity_order[x.severity])

            for issue in sorted_issues:
                print(f"\n[{issue.severity}] {issue.file_path}:{issue.line_number}")
                print(f"  Type: {issue.pattern_type}")
                print(f"  Code: {issue.code_snippet}")
                print(f"  Issue: {issue.description}")
                print(f"  Fix: {issue.recommendation}")
        else:
            print("\n✓ No command injection vulnerabilities detected!")

        print("\n" + "=" * 70)

        if summary['by_severity']['CRITICAL'] > 0:
            return 2
        elif summary['by_severity']['HIGH'] > 0:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Scan code for command injection vulnerabilities'
    )
    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='File or directory to scan (default: current directory)'
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
    scanner = CommandInjectionScanner()

    target = Path(args.path)

    if not target.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    print(f"Scanning for command injection: {target.absolute()}")

    if target.is_file():
        scanner.scan_file(target)
    else:
        recursive = not args.no_recursive
        scanner.scan_directory(target, recursive=recursive)

    return scanner.print_report()


if __name__ == '__main__':
    exit(main())
