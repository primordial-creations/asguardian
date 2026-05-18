"""Git repository security scanner."""

import re
import subprocess
from pathlib import Path
from typing import List

from Asgard.Heimdall.Security.Git.models.git_models import GitFinding, GitScanReport, GitSeverity

_SENSITIVE_FILES = [
    (r"\.env$|\.env\.\w+$", "CRITICAL", "env_file", "Environment file with secrets"),
    (r"(?:id_rsa|id_dsa|id_ecdsa|id_ed25519)$", "CRITICAL", "ssh_private_key", "SSH private key"),
    (r"\.pem$|\.key$|\.p12$|\.pfx$", "CRITICAL", "private_key_file", "Private key file"),
    (r"credentials\.json$|service[-_]?account\.json$", "CRITICAL", "credentials_file", "Credentials file"),
    (r"wp-config\.php$", "CRITICAL", "wordpress_config", "WordPress config with DB credentials"),
    (r"\.npmrc$|\.pypirc$", "HIGH", "package_credentials", "Package manager credentials"),
    (r"\.git-credentials$", "CRITICAL", "git_credentials", "Git credentials file"),
    (r"\.aws/credentials$", "CRITICAL", "aws_credentials", "AWS credentials file"),
    (r"\.kube/config$", "CRITICAL", "kube_config", "Kubernetes config"),
    (r"terraform\.tfstate$", "CRITICAL", "terraform_state", "Terraform state with secrets"),
]

_SECRET_PATTERNS = [
    (r"(?:password|passwd|pwd)\s*(?:=|:)\s*['\"][^'\"]{8,}['\"]", "CRITICAL", "hardcoded_password"),
    (r"AKIA[0-9A-Z]{16}", "CRITICAL", "aws_access_key"),
    (r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}", "CRITICAL", "github_token"),
    (r"sk_live_[0-9a-zA-Z]{24,}", "CRITICAL", "stripe_live_key"),
    (r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----", "CRITICAL", "private_key"),
    (r"(?:api[_-]?key|apikey)\s*(?:=|:)\s*['\"][A-Za-z0-9_-]{20,}['\"]", "HIGH", "api_key"),
]

_ESSENTIAL_GITIGNORE = [
    (".env", "Environment files"),
    ("*.pem", "Private key files"),
    ("*.key", "Key files"),
    ("node_modules/", "Node modules"),
    ("__pycache__/", "Python cache"),
    (".aws/", "AWS credentials"),
    ("*.tfstate", "Terraform state"),
]


class GitSecurityScanner:
    """Scans git repositories for secrets in history, current files, and config issues."""

    def scan(self, repo_path: Path) -> GitScanReport:
        if not (repo_path / ".git").exists():
            return GitScanReport(repo_path=str(repo_path))

        self._repo = repo_path
        findings: List[GitFinding] = []
        findings.extend(self._check_sensitive_files_in_history())
        findings.extend(self._check_secrets_in_current_files())
        findings.extend(self._check_gitignore())
        findings.extend(self._check_branch_protection())
        findings.extend(self._check_git_hooks())

        by_severity: dict = {}
        by_type: dict = {}
        for f in findings:
            by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1
            by_type[f.issue_type] = by_type.get(f.issue_type, 0) + 1

        return GitScanReport(
            repo_path=str(repo_path),
            total_findings=len(findings),
            findings=findings,
            by_severity=by_severity,
            by_type=by_type,
        )

    def _git(self, args: List[str]) -> str:
        try:
            result = subprocess.run(
                ["git"] + args, cwd=self._repo, capture_output=True, text=True, timeout=30
            )
            return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""

    def _check_sensitive_files_in_history(self) -> List[GitFinding]:
        findings: List[GitFinding] = []
        output = self._git(["log", "--all", "--pretty=format:", "--name-only", "--diff-filter=A"])
        for file_path in set(output.strip().splitlines()):
            if not file_path:
                continue
            for pattern, severity, issue_type, desc in _SENSITIVE_FILES:
                if re.search(pattern, file_path, re.IGNORECASE):
                    exists_now = bool(self._git(["ls-tree", "HEAD", file_path]).strip())
                    findings.append(GitFinding(
                        file_path=file_path,
                        commit="history",
                        severity=GitSeverity(severity),
                        issue_type=issue_type,
                        description=desc,
                        recommendation="Clean git history with git-filter-repo or BFG",
                        details="Still in repo" if exists_now else "In history only",
                    ))
        return findings

    def _check_secrets_in_current_files(self) -> List[GitFinding]:
        findings: List[GitFinding] = []
        output = self._git(["ls-tree", "-r", "HEAD", "--name-only"])
        skip_exts = {".jpg", ".png", ".gif", ".pdf", ".zip", ".exe"}
        for file_path in output.strip().splitlines():
            if not file_path or any(file_path.endswith(e) for e in skip_exts):
                continue
            content = self._git(["show", f"HEAD:{file_path}"])
            for pattern, severity, issue_type in _SECRET_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    findings.append(GitFinding(
                        file_path=file_path,
                        commit="HEAD",
                        severity=GitSeverity(severity),
                        issue_type=issue_type,
                        description=f"Secret pattern found: {issue_type}",
                        recommendation="Remove secret and rotate credentials",
                        details="In current HEAD",
                    ))
        return findings

    def _check_gitignore(self) -> List[GitFinding]:
        findings: List[GitFinding] = []
        gi_path = self._repo / ".gitignore"
        content = gi_path.read_text(errors="ignore") if gi_path.exists() else ""
        for pattern, desc in _ESSENTIAL_GITIGNORE:
            if pattern not in content:
                findings.append(GitFinding(
                    file_path=".gitignore",
                    severity=GitSeverity.MEDIUM,
                    issue_type="missing_gitignore",
                    description=f"Missing .gitignore pattern: {pattern}",
                    recommendation=f'Add "{pattern}" to .gitignore ({desc})',
                ))
        return findings

    def _check_branch_protection(self) -> List[GitFinding]:
        findings: List[GitFinding] = []
        output = self._git(["branch", "-a"])
        main_branches = {"main", "master", "develop", "production"}
        for branch in output.strip().splitlines():
            branch = branch.strip().lstrip("* ")
            if any(mb in branch for mb in main_branches):
                findings.append(GitFinding(
                    file_path=branch,
                    severity=GitSeverity.LOW,
                    issue_type="branch_protection",
                    description=f"Main branch may lack protection: {branch}",
                    recommendation="Enable branch protection rules on GitHub/GitLab",
                    details="Consider requiring PR reviews",
                ))
        return findings

    def _check_git_hooks(self) -> List[GitFinding]:
        findings: List[GitFinding] = []
        hooks_dir = self._repo / ".git" / "hooks"
        if hooks_dir.exists() and not (hooks_dir / "pre-commit").exists():
            findings.append(GitFinding(
                file_path=".git/hooks/pre-commit",
                severity=GitSeverity.LOW,
                issue_type="no_pre_commit_hook",
                description="No pre-commit hook for security checks",
                recommendation="Add pre-commit hook with secret scanning",
                details="Consider using pre-commit framework",
            ))
        return findings
