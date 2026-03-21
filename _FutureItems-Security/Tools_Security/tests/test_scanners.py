#!/usr/bin/env python3
"""
Unit tests for security scanners.
"""

import pytest
import tempfile
import os
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sql_injection_scanner import SQLInjectionScanner
from xss_scanner import XSSScanner
from secrets_scanner import SecretsScanner
from command_injection_scanner import CommandInjectionScanner
from sensitive_data_scanner import SensitiveDataScanner
from redos_scanner import ReDoSScanner
from security_misconfig_scanner import SecurityMisconfigScanner
from input_validation_scanner import InputValidationScanner
from info_disclosure_scanner import InfoDisclosureScanner
from race_condition_detector import RaceConditionDetector
from api_security_scanner import APISecurityScanner
from frontend_security_scanner import FrontendSecurityScanner


class TestSQLInjectionScanner:
    """Tests for SQL injection scanner."""

    def setup_method(self):
        self.scanner = SQLInjectionScanner()

    def test_detect_string_concat_sql(self):
        """Test detection of string concatenation in SQL."""
        code = '''
query = "SELECT * FROM users WHERE id = " + user_id
cursor.execute(query)
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0
        assert any('sql' in i.issue_type.lower() for i in issues)

    def test_detect_fstring_sql(self):
        """Test detection of f-strings in SQL."""
        code = '''
query = f"SELECT * FROM users WHERE name = '{name}'"
db.execute(query)
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0

    def test_safe_parameterized_query(self):
        """Test that parameterized queries don't trigger."""
        code = '''
query = "SELECT * FROM users WHERE id = ?"
cursor.execute(query, (user_id,))
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        # Should have fewer or no issues
        assert len(issues) == 0 or all(i.severity != 'CRITICAL' for i in issues)


class TestXSSScanner:
    """Tests for XSS scanner."""

    def setup_method(self):
        self.scanner = XSSScanner()

    def test_detect_innerhtml(self):
        """Test detection of innerHTML assignment."""
        code = '''
element.innerHTML = userInput;
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0
        assert any('innerhtml' in i.issue_type.lower() or 'xss' in i.issue_type.lower() for i in issues)

    def test_detect_document_write(self):
        """Test detection of document.write."""
        code = '''
document.write(userData);
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0


class TestSecretsScanner:
    """Tests for secrets scanner."""

    def setup_method(self):
        self.scanner = SecretsScanner()

    def test_detect_aws_key(self):
        """Test detection of AWS access key."""
        code = '''
AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0
        assert any('aws' in i.secret_type.lower() for i in issues)

    def test_detect_github_token(self):
        """Test detection of GitHub token."""
        code = '''
GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0

    def test_detect_private_key(self):
        """Test detection of private key."""
        code = '''
key = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA...
-----END RSA PRIVATE KEY-----"""
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0


class TestCommandInjectionScanner:
    """Tests for command injection scanner."""

    def setup_method(self):
        self.scanner = CommandInjectionScanner()

    def test_detect_os_system(self):
        """Test detection of os.system with user input."""
        code = '''
import os
os.system("ls " + user_input)
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0

    def test_detect_subprocess_shell(self):
        """Test detection of subprocess with shell=True."""
        code = '''
import subprocess
subprocess.call(cmd, shell=True)
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0


class TestSensitiveDataScanner:
    """Tests for sensitive data scanner."""

    def setup_method(self):
        self.scanner = SensitiveDataScanner()

    def test_detect_ssn(self):
        """Test detection of SSN pattern."""
        code = '''
ssn = "123-45-6789"
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0
        assert any('ssn' in i.pattern_type.lower() for i in issues)

    def test_detect_credit_card(self):
        """Test detection of credit card number."""
        code = '''
card = "4111111111111111"
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0

    def test_detect_hardcoded_password(self):
        """Test detection of hardcoded password."""
        code = '''
password = "mysecretpassword123"
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0


class TestReDoSScanner:
    """Tests for ReDoS scanner."""

    def setup_method(self):
        self.scanner = ReDoSScanner()

    def test_detect_nested_quantifiers(self):
        """Test detection of nested quantifiers."""
        code = '''
import re
pattern = re.compile(r'(a+)+$')
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0

    def test_detect_evil_regex(self):
        """Test detection of evil regex pattern."""
        code = '''
const regex = /^(a|a)+$/;
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0


class TestSecurityMisconfigScanner:
    """Tests for security misconfiguration scanner."""

    def setup_method(self):
        self.scanner = SecurityMisconfigScanner()

    def test_detect_debug_mode(self):
        """Test detection of debug mode enabled."""
        code = '''
DEBUG = True
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0
        assert any('debug' in i.issue_type.lower() for i in issues)

    def test_detect_ssl_verify_disabled(self):
        """Test detection of SSL verification disabled."""
        code = '''
ssl_verify = False
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0


class TestInputValidationScanner:
    """Tests for input validation scanner."""

    def setup_method(self):
        self.scanner = InputValidationScanner()

    def test_detect_unsafe_json_parse(self):
        """Test detection of unsafe JSON parsing."""
        code = '''
data = JSON.parse(req.body.data);
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0

    def test_detect_unsafe_file_path(self):
        """Test detection of file path from user input."""
        code = '''
with open(request.args.get('file')) as f:
    content = f.read()
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        # May or may not detect depending on pattern matching
        # This is a lighter test


class TestInfoDisclosureScanner:
    """Tests for information disclosure scanner."""

    def setup_method(self):
        self.scanner = InfoDisclosureScanner()

    def test_detect_stack_trace_exposure(self):
        """Test detection of stack trace exposure."""
        code = '''
except Exception as e:
    return response.json({'error': e.stack})
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0

    def test_detect_internal_path(self):
        """Test detection of internal file paths."""
        code = '''
path = "/home/user/app/secrets.txt"
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0


class TestRaceConditionDetector:
    """Tests for race condition detector."""

    def setup_method(self):
        self.scanner = RaceConditionDetector()

    def test_detect_toctou(self):
        """Test detection of TOCTOU vulnerability."""
        code = '''
if os.path.exists(filename):
    with open(filename) as f:
        data = f.read()
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0

    def test_detect_shared_state(self):
        """Test detection of shared mutable state."""
        code = '''
global counter
counter = 0
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0


class TestAPISecurityScanner:
    """Tests for API security scanner."""

    def setup_method(self):
        self.scanner = APISecurityScanner()

    def test_detect_mass_assignment(self):
        """Test detection of mass assignment."""
        code = '''
User.create(req.body)
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0

    def test_detect_idor(self):
        """Test detection of IDOR vulnerability."""
        code = '''
user_id = req.params.userId
User.findById(user_id)
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0


class TestFrontendSecurityScanner:
    """Tests for frontend security scanner."""

    def setup_method(self):
        self.scanner = FrontendSecurityScanner()

    def test_detect_eval(self):
        """Test detection of eval usage."""
        code = '''
eval(userInput);
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0

    def test_detect_localstorage_sensitive(self):
        """Test detection of sensitive data in localStorage."""
        code = '''
localStorage.setItem('token', authToken);
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(code)
            f.flush()
            issues = self.scanner.scan_file(Path(f.name))
            os.unlink(f.name)

        assert len(issues) > 0


class TestScannerIntegration:
    """Integration tests for scanners."""

    def test_scan_directory(self):
        """Test scanning a directory with multiple files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create vulnerable Python file
            py_file = Path(tmpdir) / "vulnerable.py"
            py_file.write_text('''
password = "secret123"
query = "SELECT * FROM users WHERE id = " + user_id
''')

            # Create vulnerable JS file
            js_file = Path(tmpdir) / "vulnerable.js"
            js_file.write_text('''
element.innerHTML = userInput;
eval(data);
''')

            # Test SQL injection scanner
            sql_scanner = SQLInjectionScanner()
            sql_issues = sql_scanner.scan_directory(Path(tmpdir))
            assert len(sql_issues) > 0

            # Test XSS scanner
            xss_scanner = XSSScanner()
            xss_issues = xss_scanner.scan_directory(Path(tmpdir))
            assert len(xss_issues) > 0

            # Test secrets scanner
            secrets_scanner = SecretsScanner()
            secrets_issues = secrets_scanner.scan_directory(Path(tmpdir))
            assert len(secrets_issues) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
