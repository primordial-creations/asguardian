#!/usr/bin/env python3
"""
Permission Auditor
Audits file and directory permissions for security issues.
"""

import os
import stat
import argparse
import pwd
import grp
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PermissionIssue:
    """Represents a permission security issue."""
    path: str
    issue_type: str
    severity: str
    current: str
    recommended: str
    description: str


class PermissionAuditor:
    """Audits file and directory permissions."""

    # World-writable permission issues
    SENSITIVE_PATHS = {
        '.ssh': {'max_perm': 0o700, 'description': 'SSH directory should be private'},
        '.ssh/authorized_keys': {'max_perm': 0o600, 'description': 'SSH keys must be private'},
        '.ssh/id_rsa': {'max_perm': 0o600, 'description': 'Private keys must be private'},
        '.ssh/id_ed25519': {'max_perm': 0o600, 'description': 'Private keys must be private'},
        '.ssh/config': {'max_perm': 0o600, 'description': 'SSH config should be private'},
        '.gnupg': {'max_perm': 0o700, 'description': 'GPG directory should be private'},
        '.aws': {'max_perm': 0o700, 'description': 'AWS credentials directory should be private'},
        '.kube': {'max_perm': 0o700, 'description': 'Kubernetes config should be private'},
        '.docker': {'max_perm': 0o700, 'description': 'Docker config should be private'},
        '.netrc': {'max_perm': 0o600, 'description': 'Netrc contains passwords'},
        '.pgpass': {'max_perm': 0o600, 'description': 'PostgreSQL password file'},
        '.my.cnf': {'max_perm': 0o600, 'description': 'MySQL config may contain passwords'},
        'id_rsa': {'max_perm': 0o600, 'description': 'Private key file'},
        'id_ed25519': {'max_perm': 0o600, 'description': 'Private key file'},
        '.env': {'max_perm': 0o600, 'description': 'Environment file may contain secrets'},
        'credentials': {'max_perm': 0o600, 'description': 'Credentials file'},
        'secrets': {'max_perm': 0o600, 'description': 'Secrets file'},
    }

    # Sensitive file patterns
    SENSITIVE_PATTERNS = [
        '**/private*.pem', '**/private*.key', '**/*.p12', '**/*.pfx',
        '**/credentials*', '**/secret*', '**/.env*', '**/token*'
    ]

    def __init__(self):
        self.issues: List[PermissionIssue] = []
        self.files_scanned = 0

    def get_permission_string(self, mode: int) -> str:
        """Convert mode to permission string like rwxr-xr-x."""
        perms = ''
        for who in ['USR', 'GRP', 'OTH']:
            for what in ['R', 'W', 'X']:
                if mode & getattr(stat, f'S_I{what}{who}'):
                    perms += what.lower()
                else:
                    perms += '-'
        return perms

    def check_file_permissions(self, file_path: Path) -> List[PermissionIssue]:
        """Check permissions on a single file."""
        issues = []

        try:
            file_stat = file_path.stat()
            mode = file_stat.st_mode
            perm_octal = stat.S_IMODE(mode)
            perm_string = self.get_permission_string(perm_octal)
        except (OSError, IOError):
            return issues

        self.files_scanned += 1
        file_name = file_path.name
        rel_path = str(file_path)

        # Check for world-writable
        if mode & stat.S_IWOTH:
            issues.append(PermissionIssue(
                path=rel_path,
                issue_type='world_writable',
                severity='HIGH',
                current=perm_string,
                recommended='Remove world write permission',
                description='File is writable by anyone on the system'
            ))

        # Check for world-readable on sensitive files
        if mode & stat.S_IROTH:
            for sensitive, config in self.SENSITIVE_PATHS.items():
                if file_name == sensitive or rel_path.endswith(sensitive):
                    if perm_octal > config['max_perm']:
                        issues.append(PermissionIssue(
                            path=rel_path,
                            issue_type='too_permissive',
                            severity='HIGH',
                            current=perm_string,
                            recommended=oct(config['max_perm'])[2:],
                            description=config['description']
                        ))
                    break

        # Check for SUID/SGID bits
        if mode & stat.S_ISUID:
            issues.append(PermissionIssue(
                path=rel_path,
                issue_type='suid_bit',
                severity='MEDIUM',
                current=perm_string + ' (SUID)',
                recommended='Review necessity of SUID bit',
                description='File has SUID bit set - runs with owner privileges'
            ))

        if mode & stat.S_ISGID:
            issues.append(PermissionIssue(
                path=rel_path,
                issue_type='sgid_bit',
                severity='MEDIUM',
                current=perm_string + ' (SGID)',
                recommended='Review necessity of SGID bit',
                description='File has SGID bit set - runs with group privileges'
            ))

        # Check for executable scripts with loose permissions
        if file_path.suffix in {'.sh', '.py', '.pl', '.rb'} and mode & stat.S_IXUSR:
            if mode & stat.S_IWGRP or mode & stat.S_IWOTH:
                issues.append(PermissionIssue(
                    path=rel_path,
                    issue_type='writable_script',
                    severity='MEDIUM',
                    current=perm_string,
                    recommended='Remove group/world write on executable',
                    description='Executable script is writable by others'
                ))

        return issues

    def check_directory_permissions(self, dir_path: Path) -> List[PermissionIssue]:
        """Check permissions on a directory."""
        issues = []

        try:
            dir_stat = dir_path.stat()
            mode = dir_stat.st_mode
            perm_octal = stat.S_IMODE(mode)
            perm_string = self.get_permission_string(perm_octal)
        except (OSError, IOError):
            return issues

        dir_name = dir_path.name
        rel_path = str(dir_path)

        # Check for world-writable directories without sticky bit
        if (mode & stat.S_IWOTH) and not (mode & stat.S_ISVTX):
            issues.append(PermissionIssue(
                path=rel_path,
                issue_type='world_writable_dir',
                severity='HIGH',
                current=perm_string,
                recommended='Remove world write or add sticky bit',
                description='Directory is world-writable without sticky bit'
            ))

        # Check sensitive directories
        for sensitive, config in self.SENSITIVE_PATHS.items():
            if dir_name == sensitive or rel_path.endswith(sensitive):
                if perm_octal > config['max_perm']:
                    issues.append(PermissionIssue(
                        path=rel_path,
                        issue_type='too_permissive_dir',
                        severity='HIGH',
                        current=perm_string,
                        recommended=oct(config['max_perm'])[2:],
                        description=config['description']
                    ))
                break

        return issues

    def audit_directory(self, directory: Path, recursive: bool = True) -> List[PermissionIssue]:
        """Audit permissions in a directory."""
        all_issues = []

        skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv'}

        if recursive:
            for root, dirs, files in os.walk(directory):
                # Skip certain directories
                dirs[:] = [d for d in dirs if d not in skip_dirs]

                root_path = Path(root)

                # Check directory permissions
                issues = self.check_directory_permissions(root_path)
                all_issues.extend(issues)

                # Check file permissions
                for file in files:
                    file_path = root_path / file
                    issues = self.check_file_permissions(file_path)
                    all_issues.extend(issues)
        else:
            # Check only immediate contents
            issues = self.check_directory_permissions(directory)
            all_issues.extend(issues)

            for item in directory.iterdir():
                if item.is_file():
                    issues = self.check_file_permissions(item)
                    all_issues.extend(issues)

        self.issues = all_issues
        return all_issues

    def audit_home_directory(self) -> List[PermissionIssue]:
        """Audit permissions in user's home directory."""
        home = Path.home()
        return self.audit_directory(home)

    def get_summary(self) -> Dict:
        """Get summary of findings."""
        summary = {
            'total_issues': len(self.issues),
            'files_scanned': self.files_scanned,
            'by_severity': {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0},
            'by_type': {}
        }

        for issue in self.issues:
            summary['by_severity'][issue.severity] += 1
            if issue.issue_type not in summary['by_type']:
                summary['by_type'][issue.issue_type] = 0
            summary['by_type'][issue.issue_type] += 1

        return summary

    def print_report(self):
        """Print permission audit report."""
        summary = self.get_summary()

        print("\n" + "=" * 70)
        print("PERMISSION AUDIT REPORT")
        print("=" * 70)

        print(f"\nFiles Scanned: {summary['files_scanned']}")
        print(f"Total Issues: {summary['total_issues']}")

        print("\nIssues by Severity:")
        for severity in ['HIGH', 'MEDIUM', 'LOW']:
            count = summary['by_severity'][severity]
            if count > 0:
                print(f"  {severity}: {count}")

        if summary['by_type']:
            print("\nIssues by Type:")
            for issue_type, count in sorted(summary['by_type'].items()):
                print(f"  {issue_type}: {count}")

        if self.issues:
            print("\n" + "-" * 70)
            print("DETAILED FINDINGS")
            print("-" * 70)

            # Sort by severity
            severity_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
            sorted_issues = sorted(self.issues, key=lambda x: severity_order[x.severity])

            for issue in sorted_issues:
                print(f"\n[{issue.severity}] {issue.path}")
                print(f"  Type: {issue.issue_type}")
                print(f"  Current: {issue.current}")
                print(f"  Recommended: {issue.recommended}")
                print(f"  Description: {issue.description}")
        else:
            print("\n✓ No permission issues found!")

        print("\n" + "=" * 70)

        # Return exit code
        if summary['by_severity']['HIGH'] > 0:
            return 2
        elif summary['by_severity']['MEDIUM'] > 0:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Audit file and directory permissions'
    )
    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='Directory to audit (default: current directory)'
    )
    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        default=True,
        help='Audit recursively (default: True)'
    )
    parser.add_argument(
        '--no-recursive',
        action='store_true',
        help='Do not audit recursively'
    )
    parser.add_argument(
        '--home',
        action='store_true',
        help='Audit home directory for sensitive files'
    )

    args = parser.parse_args()
    auditor = PermissionAuditor()

    if args.home:
        print(f"Auditing home directory: {Path.home()}")
        auditor.audit_home_directory()
    else:
        target = Path(args.path)
        if not target.exists():
            print(f"Error: Path not found: {args.path}")
            return 1

        print(f"Auditing: {target.absolute()}")
        recursive = not args.no_recursive
        auditor.audit_directory(target, recursive=recursive)

    return auditor.print_report()


if __name__ == '__main__':
    exit(main())
