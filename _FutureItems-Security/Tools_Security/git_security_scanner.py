#!/usr/bin/env python3
"""
Git Security Scanner
Scans git repositories for security issues in history and configuration.
"""

import os
import re
import subprocess
import argparse
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class GitSecurityIssue:
    """Represents a git security issue."""
    file_path: str
    commit: str
    severity: str
    issue_type: str
    description: str
    recommendation: str
    details: str


class GitSecurityScanner:
    """Scans git repositories for security issues."""

    # Sensitive file patterns
    SENSITIVE_FILES = [
        (r'\.env$|\.env\.\w+$', 'CRITICAL', 'env_file', 'Environment file with secrets'),
        (r'(?:id_rsa|id_dsa|id_ecdsa|id_ed25519)$', 'CRITICAL', 'ssh_private_key', 'SSH private key'),
        (r'\.pem$|\.key$|\.p12$|\.pfx$', 'CRITICAL', 'private_key_file', 'Private key file'),
        (r'credentials\.json$|service[-_]?account\.json$', 'CRITICAL', 'credentials_file', 'Credentials file'),
        (r'\.htpasswd$|\.htaccess$', 'HIGH', 'apache_config', 'Apache config with credentials'),
        (r'wp-config\.php$', 'CRITICAL', 'wordpress_config', 'WordPress config with DB credentials'),
        (r'database\.yml$|secrets\.yml$', 'HIGH', 'rails_secrets', 'Rails secrets file'),
        (r'\.npmrc$|\.pypirc$', 'HIGH', 'package_credentials', 'Package manager credentials'),
        (r'\.docker/config\.json$', 'HIGH', 'docker_config', 'Docker config with auth'),
        (r'\.git-credentials$', 'CRITICAL', 'git_credentials', 'Git credentials file'),
        (r'\.bash_history$|\.zsh_history$', 'MEDIUM', 'shell_history', 'Shell history may contain secrets'),
        (r'\.aws/credentials$', 'CRITICAL', 'aws_credentials', 'AWS credentials file'),
        (r'\.kube/config$', 'CRITICAL', 'kube_config', 'Kubernetes config'),
        (r'terraform\.tfstate$', 'CRITICAL', 'terraform_state', 'Terraform state with secrets'),
    ]

    # Patterns for secrets in file content
    SECRET_PATTERNS = [
        (r'(?:password|passwd|pwd)\s*(?:=|:)\s*[\'"][^\'"]{8,}[\'"]', 'CRITICAL', 'hardcoded_password'),
        (r'AKIA[0-9A-Z]{16}', 'CRITICAL', 'aws_access_key'),
        (r'(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}', 'CRITICAL', 'github_token'),
        (r'sk_live_[0-9a-zA-Z]{24,}', 'CRITICAL', 'stripe_live_key'),
        (r'-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----', 'CRITICAL', 'private_key'),
        (r'(?:api[_-]?key|apikey)\s*(?:=|:)\s*[\'"][A-Za-z0-9_-]{20,}[\'"]', 'HIGH', 'api_key'),
    ]

    def __init__(self):
        self.issues: List[GitSecurityIssue] = []
        self.repo_path = None

    def is_git_repo(self, path: Path) -> bool:
        """Check if path is a git repository."""
        return (path / '.git').exists()

    def run_git_command(self, args: List[str]) -> str:
        """Run a git command and return output."""
        try:
            result = subprocess.run(
                ['git'] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ''

    def check_sensitive_files_in_history(self) -> List[GitSecurityIssue]:
        """Check for sensitive files in git history."""
        issues = []

        # Get all files ever committed
        output = self.run_git_command(['log', '--all', '--pretty=format:', '--name-only', '--diff-filter=A'])
        all_files = set(output.strip().split('\n'))

        for file_path in all_files:
            if not file_path:
                continue

            for pattern, severity, issue_type, desc in self.SENSITIVE_FILES:
                if re.search(pattern, file_path, re.IGNORECASE):
                    # Check if file still exists in current HEAD
                    exists_now = self.run_git_command(['ls-tree', 'HEAD', file_path]).strip()

                    if exists_now:
                        rec = 'Remove file and add to .gitignore, then clean history'
                    else:
                        rec = 'Clean git history with git-filter-repo or BFG'

                    issues.append(GitSecurityIssue(
                        file_path=file_path,
                        commit='history',
                        severity=severity,
                        issue_type=issue_type,
                        description=desc,
                        recommendation=rec,
                        details='Still in repo' if exists_now else 'In history only'
                    ))

        return issues

    def check_secrets_in_current_files(self) -> List[GitSecurityIssue]:
        """Check for secrets in current tracked files."""
        issues = []

        # Get list of tracked files
        output = self.run_git_command(['ls-tree', '-r', 'HEAD', '--name-only'])
        tracked_files = output.strip().split('\n')

        for file_path in tracked_files:
            if not file_path:
                continue

            # Skip binary files
            if any(file_path.endswith(ext) for ext in ['.jpg', '.png', '.gif', '.pdf', '.zip', '.exe']):
                continue

            # Get file content
            content = self.run_git_command(['show', f'HEAD:{file_path}'])

            for pattern, severity, issue_type in self.SECRET_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    issues.append(GitSecurityIssue(
                        file_path=file_path,
                        commit='HEAD',
                        severity=severity,
                        issue_type=issue_type,
                        description=f'Secret pattern found: {issue_type}',
                        recommendation='Remove secret and rotate credentials',
                        details='In current HEAD'
                    ))

        return issues

    def check_gitignore(self) -> List[GitSecurityIssue]:
        """Check for missing .gitignore entries."""
        issues = []

        gitignore_path = self.repo_path / '.gitignore'
        gitignore_content = ''

        if gitignore_path.exists():
            with open(gitignore_path) as f:
                gitignore_content = f.read()

        # Essential patterns that should be ignored
        essential_patterns = [
            ('.env', 'Environment files'),
            ('*.pem', 'Private key files'),
            ('*.key', 'Key files'),
            ('node_modules/', 'Node modules'),
            ('__pycache__/', 'Python cache'),
            ('.aws/', 'AWS credentials'),
            ('*.tfstate', 'Terraform state'),
        ]

        for pattern, desc in essential_patterns:
            if pattern not in gitignore_content:
                issues.append(GitSecurityIssue(
                    file_path='.gitignore',
                    commit='N/A',
                    severity='MEDIUM',
                    issue_type='missing_gitignore',
                    description=f'Missing .gitignore pattern: {pattern}',
                    recommendation=f'Add "{pattern}" to .gitignore ({desc})',
                    details=''
                ))

        return issues

    def check_branch_protection(self) -> List[GitSecurityIssue]:
        """Check for unprotected main branches."""
        issues = []

        # Get list of branches
        output = self.run_git_command(['branch', '-a'])
        branches = output.strip().split('\n')

        main_branches = ['main', 'master', 'develop', 'production']

        for branch in branches:
            branch = branch.strip().replace('* ', '')
            if any(main in branch for main in main_branches):
                # Check if commits can be pushed directly
                issues.append(GitSecurityIssue(
                    file_path=branch,
                    commit='N/A',
                    severity='LOW',
                    issue_type='branch_protection',
                    description=f'Main branch may lack protection: {branch}',
                    recommendation='Enable branch protection rules on GitHub/GitLab',
                    details='Consider requiring PR reviews'
                ))

        return issues

    def check_git_hooks(self) -> List[GitSecurityIssue]:
        """Check for security-related git hooks."""
        issues = []

        hooks_dir = self.repo_path / '.git' / 'hooks'

        if hooks_dir.exists():
            pre_commit = hooks_dir / 'pre-commit'

            if not pre_commit.exists():
                issues.append(GitSecurityIssue(
                    file_path='.git/hooks/pre-commit',
                    commit='N/A',
                    severity='LOW',
                    issue_type='no_pre_commit_hook',
                    description='No pre-commit hook for security checks',
                    recommendation='Add pre-commit hook with secret scanning',
                    details='Consider using pre-commit framework'
                ))

        return issues

    def check_exposed_git(self) -> List[GitSecurityIssue]:
        """Check for exposed .git directory markers."""
        issues = []

        # This is informational for web deployments
        readme_files = ['README.md', 'readme.md', 'README.txt']

        for readme in readme_files:
            readme_path = self.repo_path / readme
            if readme_path.exists():
                with open(readme_path) as f:
                    content = f.read()
                    if 'deploy' in content.lower() and '.git' not in content.lower():
                        issues.append(GitSecurityIssue(
                            file_path=readme,
                            commit='N/A',
                            severity='LOW',
                            issue_type='deployment_warning',
                            description='Deployment mentioned - ensure .git is not exposed',
                            recommendation='Block access to .git directory in web server config',
                            details='Add deny rules for /.git/ path'
                        ))

        return issues

    def scan_repository(self, repo_path: Path) -> List[GitSecurityIssue]:
        """Perform full security scan on repository."""
        self.repo_path = repo_path
        all_issues = []

        if not self.is_git_repo(repo_path):
            print(f"Error: {repo_path} is not a git repository")
            return []

        print("Checking for sensitive files in history...")
        all_issues.extend(self.check_sensitive_files_in_history())

        print("Checking for secrets in current files...")
        all_issues.extend(self.check_secrets_in_current_files())

        print("Checking .gitignore configuration...")
        all_issues.extend(self.check_gitignore())

        print("Checking branch protection...")
        all_issues.extend(self.check_branch_protection())

        print("Checking git hooks...")
        all_issues.extend(self.check_git_hooks())

        self.issues = all_issues
        return all_issues

    def get_summary(self) -> Dict:
        """Get summary of findings."""
        summary = {
            'total_issues': len(self.issues),
            'by_severity': {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0},
            'by_type': {}
        }

        for issue in self.issues:
            summary['by_severity'][issue.severity] += 1
            if issue.issue_type not in summary['by_type']:
                summary['by_type'][issue.issue_type] = 0
            summary['by_type'][issue.issue_type] += 1

        return summary

    def print_report(self):
        """Print scan report."""
        summary = self.get_summary()

        print("\n" + "=" * 70)
        print("GIT SECURITY SCAN REPORT")
        print("=" * 70)

        print(f"\nRepository: {self.repo_path}")
        print(f"Total Issues: {summary['total_issues']}")

        if summary['total_issues'] > 0:
            print("\nBy Severity:")
            for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
                count = summary['by_severity'][severity]
                if count > 0:
                    print(f"  {severity}: {count}")

            print("\nBy Type:")
            for issue_type, count in sorted(summary['by_type'].items(), key=lambda x: -x[1]):
                print(f"  {issue_type}: {count}")

            print("\n" + "-" * 70)
            print("SECURITY ISSUES")
            print("-" * 70)

            severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
            sorted_issues = sorted(self.issues, key=lambda x: severity_order[x.severity])

            for issue in sorted_issues:
                print(f"\n[{issue.severity}] {issue.issue_type}")
                print(f"  File: {issue.file_path}")
                if issue.commit != 'N/A':
                    print(f"  Commit: {issue.commit}")
                print(f"  {issue.description}")
                if issue.details:
                    print(f"  Status: {issue.details}")
                print(f"  Fix: {issue.recommendation}")
        else:
            print("\n✓ No git security issues detected!")

        print("\n" + "=" * 70)

        if summary['by_severity']['CRITICAL'] > 0:
            return 2
        elif summary['by_severity']['HIGH'] > 0:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Scan git repository for security issues'
    )
    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='Repository path (default: current directory)'
    )

    args = parser.parse_args()
    scanner = GitSecurityScanner()

    target = Path(args.path).resolve()

    if not target.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    print(f"Scanning git repository: {target}")

    scanner.scan_repository(target)
    return scanner.print_report()


if __name__ == '__main__':
    exit(main())
