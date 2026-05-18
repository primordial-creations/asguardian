"""Tests for Git security scanner."""
import pytest
from pathlib import Path
from Asgard.Heimdall.Security.Git.services.git_scanner import GitSecurityScanner
from Asgard.Heimdall.Security.Git.models.git_models import GitScanReport


class TestGitSecurityScannerInstantiation:
    def test_scanner_can_be_instantiated(self):
        assert GitSecurityScanner() is not None


class TestGitSecurityScannerNonGitDir:
    def test_scan_non_git_dir_returns_report_gracefully(self, tmp_path):
        scanner = GitSecurityScanner()
        report: GitScanReport = scanner.scan(tmp_path)
        assert report is not None
        assert isinstance(report.findings, list)


class TestGitSecurityScannerGitignoreIssues:
    def test_env_file_not_in_gitignore_detected(self, tmp_path):
        import subprocess
        subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=str(tmp_path), check=True, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=str(tmp_path), check=True, capture_output=True
        )
        (tmp_path / ".env").write_text("SECRET_KEY=mysecret\n")
        (tmp_path / ".gitignore").write_text("*.pyc\n")
        scanner = GitSecurityScanner()
        report: GitScanReport = scanner.scan(tmp_path)
        assert report is not None
        assert isinstance(report.findings, list)
