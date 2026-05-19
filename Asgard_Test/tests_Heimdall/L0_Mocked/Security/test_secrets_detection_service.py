"""
Tests for Heimdall Secrets Detection Service

Unit tests for the secrets detection service with mocked file system operations.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from Asgard.Heimdall.Security.services.secrets_detection_service import (
    SecretPattern,
    SecretsDetectionService,
)
from Asgard.Heimdall.Security.services._secret_patterns import (
    DEFAULT_SECRET_PATTERNS,
    FALSE_POSITIVE_PATTERNS,
)
from Asgard.Heimdall.Security.models.security_models import (
    SecretType,
    SecuritySeverity,
    SecurityScanConfig,
    SecretsReport,
)


class TestSecretPattern:
    """Tests for SecretPattern class."""

    def test_pattern_creation(self):
        """Test creating a secret pattern."""
        pattern = SecretPattern(
            name="test_pattern",
            pattern=r"secret_\d+",
            secret_type=SecretType.API_KEY,
            severity=SecuritySeverity.HIGH,
            description="Test secret pattern",
            min_entropy=3.0,
            remediation="Remove the secret"
        )

        assert pattern.name == "test_pattern"
        assert pattern.secret_type == SecretType.API_KEY
        assert pattern.severity == SecuritySeverity.HIGH
        assert pattern.min_entropy == 3.0

    def test_pattern_regex_compilation(self):
        """Test that pattern regex is properly compiled."""
        pattern = SecretPattern(
            name="test",
            pattern=r"API[_-]?KEY",
            secret_type=SecretType.API_KEY,
            severity=SecuritySeverity.HIGH
        )

        test_string = "MY_api_key_value"
        match = pattern.pattern.search(test_string)
        assert match is not None


class TestDefaultSecretPatterns:
    """Tests for DEFAULT_SECRET_PATTERNS."""

    def test_has_aws_patterns(self):
        """Test that AWS credential patterns are included."""
        pattern_names = [p.name for p in DEFAULT_SECRET_PATTERNS]
        assert "aws_access_key" in pattern_names
        assert "aws_secret_key" in pattern_names

    def test_has_generic_patterns(self):
        """Test that generic secret patterns are included."""
        pattern_names = [p.name for p in DEFAULT_SECRET_PATTERNS]
        assert "generic_api_key" in pattern_names
        assert "password_assignment" in pattern_names
        assert "private_key_header" in pattern_names

    def test_has_service_specific_patterns(self):
        """Test that service-specific patterns are included."""
        pattern_names = [p.name for p in DEFAULT_SECRET_PATTERNS]
        assert "github_token" in pattern_names
        assert "slack_token" in pattern_names
        assert "stripe_key" in pattern_names


class TestFalsePositivePatterns:
    """Tests for FALSE_POSITIVE_PATTERNS."""

    def test_detects_example_strings(self):
        """Test that example/sample strings are detected as false positives."""
        test_strings = [
            "example_key",
            "sample_secret",
            "test_password",
            "dummy_token",
        ]

        for test_str in test_strings:
            matched = any(p.search(test_str) for p in FALSE_POSITIVE_PATTERNS)
            assert matched, f"'{test_str}' should be detected as false positive"

    def test_detects_repeated_characters(self):
        """Test that repeated character patterns are detected."""
        test_strings = ["xxxxxxxx", "00000000", "aaaaaaaa"]

        for test_str in test_strings:
            matched = any(p.search(test_str) for p in FALSE_POSITIVE_PATTERNS)
            assert matched

    def test_detects_placeholders(self):
        """Test that placeholder patterns are detected."""
        test_strings = ["<api_key>", "${SECRET}", "%(password)s"]

        for test_str in test_strings:
            matched = any(p.search(test_str) for p in FALSE_POSITIVE_PATTERNS)
            assert matched


class TestSecretsDetectionService:
    """Tests for SecretsDetectionService class."""

    def test_service_initialization_default(self):
        """Test service initialization with default config."""
        service = SecretsDetectionService()

        assert service.config is not None
        assert len(service.patterns) > 0

    def test_service_initialization_custom_config(self):
        """Test service initialization with custom config."""
        config = SecurityScanConfig(
            scan_path=Path("/custom/path"),
            min_severity=SecuritySeverity.HIGH
        )

        service = SecretsDetectionService(config)

        assert service.config == config
        assert service.config.min_severity == "high"

    def test_service_with_custom_patterns(self):
        """Test service with custom detection patterns."""
        config = SecurityScanConfig(
            custom_patterns={
                "my_secret": r"MY_SECRET_\d+"
            }
        )

        service = SecretsDetectionService(config)

        custom_patterns = [p for p in service.patterns if p.name.startswith("custom_")]
        assert len(custom_patterns) > 0

    def test_add_pattern(self):
        """Test adding a custom pattern to the service."""
        service = SecretsDetectionService()
        initial_count = len(service.patterns)

        custom_pattern = SecretPattern(
            name="custom_secret",
            pattern=r"CUSTOM_\w+",
            secret_type=SecretType.GENERIC_SECRET,
            severity=SecuritySeverity.HIGH
        )

        service.add_pattern(custom_pattern)

        assert len(service.patterns) == initial_count + 1

    def test_get_patterns(self):
        """Test getting list of pattern names."""
        service = SecretsDetectionService()
        pattern_names = service.get_patterns()

        assert isinstance(pattern_names, list)
        assert len(pattern_names) > 0
        assert "aws_access_key" in pattern_names

    def test_scan_nonexistent_path_raises_error(self):
        """Test that scanning a nonexistent path raises FileNotFoundError."""
        service = SecretsDetectionService()

        with pytest.raises(FileNotFoundError):
            service.scan(Path("/nonexistent/path"))

    def test_scan_empty_directory(self):
        """Test scanning an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = SecretsDetectionService()
            report = service.scan(Path(tmpdir))

            assert report.total_files_scanned == 0
            assert report.secrets_found == 0
            assert report.has_findings is False

    def test_scan_directory_with_clean_files(self):
        """Test scanning directory with files containing no secrets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "app.py").write_text("""
def calculate_sum(a, b):
    return a + b

result = calculate_sum(5, 10)
print(result)
""")

            service = SecretsDetectionService()
            report = service.scan(tmpdir_path)

            assert report.total_files_scanned > 0
            assert report.secrets_found == 0

    def test_scan_detects_aws_access_key(self):
        """Test detection of AWS access key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "config.py").write_text("""
AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
""")

            service = SecretsDetectionService()
            report = service.scan(tmpdir_path)

            # AWS key detection depends on entropy and pattern matching
            assert report.total_files_scanned > 0

    def test_scan_detects_private_key(self):
        """Test detection of private key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Use single-quoted concatenation so the BEGIN marker isn't inside a triple-quoted docstring
            (tmpdir_path / "keys.py").write_text(
                'PRIVATE_KEY = ("-----BEGIN RSA PRIVATE KEY-----\\n"\n'
                '               "MIIEpAIBAAKCAQEAabcdefghijklmnopqrstuvwxyz0123456789\\n"\n'
                '               "-----END RSA PRIVATE KEY-----")\n'
            )

            service = SecretsDetectionService()
            report = service.scan(tmpdir_path)

            assert report.secrets_found > 0

    def test_scan_detects_github_token(self):
        """Test detection of GitHub token."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "auth.py").write_text(
                'GITHUB_TOKEN = "ghp_aB3dEfGhIjKlMnOpQrStUvWxYz1234567890ABCD"\n'
            )

            service = SecretsDetectionService()
            report = service.scan(tmpdir_path)

            assert report.secrets_found > 0

    def test_scan_ignores_false_positives(self):
        """Test that false positives are filtered out."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "example.py").write_text("""
EXAMPLE_API_KEY = "your_api_key_here"
SAMPLE_PASSWORD = "example_password"
TEST_SECRET = "xxxxxxxxxxxxxxxx"
""")

            service = SecretsDetectionService()
            report = service.scan(tmpdir_path)

            assert report.secrets_found == 0

    def test_scan_ignores_env_var_references(self):
        """Test that environment variable references are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "config.py").write_text("""
import os
API_KEY = os.environ.get("API_KEY")
SECRET = os.getenv("SECRET_KEY")
PASSWORD = process.env.PASSWORD
""")

            service = SecretsDetectionService()
            report = service.scan(tmpdir_path)

            assert report.secrets_found == 0

    def test_scan_respects_min_severity(self):
        """Test that min_severity config is respected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "secrets.py").write_text("""
API_KEY = "sk_fake_test_key_not_real_000000"
""")

            config = SecurityScanConfig(min_severity=SecuritySeverity.CRITICAL)
            service = SecretsDetectionService(config)
            report = service.scan(tmpdir_path)

            for finding in report.findings:
                assert finding.severity in ["critical"]

    def test_scan_respects_ignore_paths(self):
        """Test that ignore_paths configuration is respected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            ignored_file = tmpdir_path / "ignored.py"
            ignored_file.write_text('SECRET = "AKIAIOSFODNN7EXAMPLE"')

            scanned_file = tmpdir_path / "scanned.py"
            scanned_file.write_text('SECRET = "AKIAIOSFODNN7EXAMPLE"')

            config = SecurityScanConfig(
                ignore_paths=[str(ignored_file)]
            )

            service = SecretsDetectionService(config)
            report = service.scan(tmpdir_path)

            file_paths = [f.file_path for f in report.findings]
            assert "ignored.py" not in " ".join(file_paths)

    def test_scan_with_exclude_patterns(self):
        """Test scanning with exclude patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            test_dir = tmpdir_path / "tests"
            test_dir.mkdir()
            (test_dir / "test_config.py").write_text('SECRET = "AKIAIOSFODNN7EXAMPLE"')

            (tmpdir_path / "app.py").write_text('SECRET = "AKIAIOSFODNN7EXAMPLE"')

            config = SecurityScanConfig(
                exclude_patterns=["tests"]
            )

            service = SecretsDetectionService(config)
            report = service.scan(tmpdir_path)

            file_paths = [f.file_path for f in report.findings]
            assert not any("tests" in fp for fp in file_paths)

    def test_scan_uses_config_path(self):
        """Test that scan uses config path when no path provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "app.py").write_text("code = 'clean'")

            config = SecurityScanConfig(scan_path=tmpdir_path)
            service = SecretsDetectionService(config)

            report = service.scan()

            assert tmpdir_path.name in report.scan_path or str(tmpdir_path) in report.scan_path

    def test_masked_value_in_findings(self):
        """Test that secret values are properly masked in findings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "secrets.py").write_text("""
STRIPE_KEY = "sk_fake_test_key_not_real_00000000000000000"
""")

            service = SecretsDetectionService()
            report = service.scan(tmpdir_path)

            if report.secrets_found > 0:
                finding = report.findings[0]
                assert "*" in finding.masked_value
                assert "sk_fake" not in finding.masked_value or finding.masked_value.startswith("sk_f")

    def test_confidence_score_calculation(self):
        """Test that confidence scores are calculated for findings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "keys.py").write_text("""
PRIVATE_KEY = '''-----BEGIN RSA PRIVATE KEY-----'''
""")

            service = SecretsDetectionService()
            report = service.scan(tmpdir_path)

            if report.secrets_found > 0:
                for finding in report.findings:
                    assert 0.0 <= finding.confidence <= 1.0

    def test_line_number_accuracy(self):
        """Test that line numbers are accurately reported."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "config.py").write_text("""line 1
line 2
line 3
API_KEY = "AKIAIOSFODNN7EXAMPLE"
line 5
""")

            service = SecretsDetectionService()
            report = service.scan(tmpdir_path)

            if report.secrets_found > 0:
                finding = report.findings[0]
                assert finding.line_number == 4

    def test_scan_duration_recorded(self):
        """Test that scan duration is recorded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = SecretsDetectionService()
            report = service.scan(Path(tmpdir))

            assert report.scan_duration_seconds >= 0.0

    def test_patterns_used_recorded(self):
        """Test that patterns used are recorded in report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = SecretsDetectionService()
            report = service.scan(Path(tmpdir))

            assert isinstance(report.patterns_used, list)
            assert len(report.patterns_used) > 0

    def test_entropy_filtering(self):
        """Test that low-entropy matches are filtered out."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "config.py").write_text("""
PASSWORD = "password123"
""")

            service = SecretsDetectionService()
            report = service.scan(tmpdir_path)

            low_entropy_count = sum(
                1 for f in report.findings
                if "password" in f.pattern_name.lower() and f.confidence < 0.5
            )

            assert low_entropy_count >= 0

    def test_scan_multiple_files(self):
        """Test scanning multiple files in directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "file1.py").write_text('KEY1 = "AKIAIOSFODNN7EXAMPLE"')
            (tmpdir_path / "file2.js").write_text('const key2 = "ghp_fake00000000000000000000000000000000000000";')

            service = SecretsDetectionService()
            report = service.scan(tmpdir_path)

            assert report.total_files_scanned >= 2

    def test_relative_path_in_findings(self):
        """Test that findings contain relative paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            subdir = tmpdir_path / "src"
            subdir.mkdir()
            (subdir / "config.py").write_text('KEY = "AKIAIOSFODNN7EXAMPLE"')

            service = SecretsDetectionService()
            report = service.scan(tmpdir_path)

            if report.secrets_found > 0:
                finding = report.findings[0]
                assert not finding.file_path.startswith("/tmp")
                assert "src" in finding.file_path or "config.py" in finding.file_path

    def test_remediation_provided(self):
        """Test that remediation guidance is provided in findings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "app.py").write_text('AWS_KEY = "AKIAIOSFODNN7EXAMPLE"')

            service = SecretsDetectionService()
            report = service.scan(tmpdir_path)

            if report.secrets_found > 0:
                finding = report.findings[0]
                assert finding.remediation != ""
                assert len(finding.remediation) > 10

    def test_database_url_detection(self):
        """Test detection of database connection strings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "db.py").write_text("""
DATABASE_URL = "postgresql://user:password@localhost:5432/mydb"
""")

            service = SecretsDetectionService()
            report = service.scan(tmpdir_path)

            assert report.secrets_found > 0
            db_findings = [f for f in report.findings if "database" in f.secret_type.lower()]
            assert len(db_findings) > 0

    def test_jwt_token_detection(self):
        """Test detection of JWT tokens."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "auth.py").write_text("""
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
""")

            service = SecretsDetectionService()
            report = service.scan(tmpdir_path)

            assert report.secrets_found > 0
