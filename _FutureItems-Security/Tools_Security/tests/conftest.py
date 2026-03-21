"""
Pytest configuration and fixtures for security scanner tests.
"""

import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def vulnerable_python_file(temp_dir):
    """Create a Python file with common vulnerabilities."""
    file_path = temp_dir / "vulnerable.py"
    file_path.write_text('''
# Vulnerable Python code for testing

import os
import subprocess

# SQL Injection
def get_user(user_id):
    query = "SELECT * FROM users WHERE id = " + user_id
    return db.execute(query)

# Command Injection
def run_command(cmd):
    os.system("ls " + cmd)
    subprocess.call(cmd, shell=True)

# Hardcoded secrets
API_KEY = "AKIAIOSFODNN7EXAMPLE"
password = "mysecretpassword123"
github_token = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# Private key
key = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA...
-----END RSA PRIVATE KEY-----"""

# Sensitive data
ssn = "123-45-6789"
credit_card = "4111111111111111"

# TOCTOU race condition
if os.path.exists(filename):
    with open(filename) as f:
        data = f.read()

# Debug mode
DEBUG = True
''')
    return file_path


@pytest.fixture
def vulnerable_js_file(temp_dir):
    """Create a JavaScript file with common vulnerabilities."""
    file_path = temp_dir / "vulnerable.js"
    file_path.write_text('''
// Vulnerable JavaScript code for testing

// XSS vulnerabilities
element.innerHTML = userInput;
document.write(userData);

// Eval usage
eval(userCode);
new Function(userInput);

// Prototype pollution
obj.__proto__.admin = true;
Object.prototype.isAdmin = true;

// postMessage without origin check
window.addEventListener('message', function(event) {
    processData(event.data);
});

// localStorage with sensitive data
localStorage.setItem('token', authToken);
localStorage.setItem('password', userPassword);

// Mass assignment
User.create(req.body);
Object.assign(user, req.body);

// Unsafe regex
const regex = /^(a+)+$/;
const evil = /(a|a)+/;
''')
    return file_path


@pytest.fixture
def safe_python_file(temp_dir):
    """Create a Python file with safe patterns."""
    file_path = temp_dir / "safe.py"
    file_path.write_text('''
# Safe Python code for testing

import os
from pathlib import Path

# Parameterized query
def get_user(user_id):
    query = "SELECT * FROM users WHERE id = ?"
    return db.execute(query, (user_id,))

# Safe subprocess
def run_command(args):
    import subprocess
    subprocess.run(args, shell=False)

# Environment variables for secrets
API_KEY = os.environ.get('API_KEY')
password = os.environ.get('DB_PASSWORD')

# Production mode
DEBUG = False
''')
    return file_path


@pytest.fixture
def config_file(temp_dir):
    """Create a configuration file with misconfigurations."""
    file_path = temp_dir / "config.yaml"
    file_path.write_text('''
# Configuration with security issues

debug: true
environment: development

database:
  host: 0.0.0.0
  password: "admin"
  ssl_verify: false

cors:
  origin: "*"
  credentials: true

secret_key: "changeme"
''')
    return file_path
