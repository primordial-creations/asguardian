# Heimdall Security Module

## Overview

The Security module provides comprehensive static security analysis for codebases, detecting vulnerabilities, secrets, and security anti-patterns. It combines multiple specialized analyzers into a unified security scanning system.

## Analyzers

### 1. Secrets Detection Service

**Purpose**: Detects hardcoded secrets, API keys, passwords, and sensitive credentials in source code.

**Key Features**:
- Pattern-based detection with confidence scoring
- Automatic secret masking in reports
- Support for 14+ secret types
- Context-aware detection (ignores test data when appropriate)

**Detected Secret Types**:

| Type | Description | Severity |
|------|-------------|----------|
| `api_key` | Generic API keys | HIGH |
| `aws_credentials` | AWS access keys and secrets | CRITICAL |
| `azure_credentials` | Azure service credentials | CRITICAL |
| `gcp_credentials` | Google Cloud credentials | CRITICAL |
| `password` | Hardcoded passwords | HIGH |
| `private_key` | RSA/EC private keys | CRITICAL |
| `access_token` | Bearer tokens, OAuth tokens | HIGH |
| `secret_key` | Generic secret keys | HIGH |
| `database_url` | Database connection strings | CRITICAL |
| `jwt_token` | JSON Web Tokens | HIGH |
| `ssh_key` | SSH private keys | CRITICAL |
| `certificate` | SSL/TLS certificates | MEDIUM |
| `oauth_token` | OAuth access/refresh tokens | HIGH |
| `generic_secret` | Other detected secrets | MEDIUM |

**Detection Patterns**:

```python
# Examples of detected patterns
api_key = "sk-1234567890abcdef"           # API key pattern
password = "MySecretPassword123"           # Password assignment
AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI..."  # AWS credentials
DATABASE_URL = "mysql://user:pass@host/db"  # Connection string
```

**Configuration**:
```python
from Heimdall.Security import SecurityScanConfig

config = SecurityScanConfig(
    scan_secrets=True,
    min_severity="medium",
    exclude_patterns=["test_*.py", "*_test.py"]
)
```

---

### 2. Dependency Vulnerability Service

**Purpose**: Scans project dependencies for known security vulnerabilities using the PyPI advisory database.

**Key Features**:
- Parses requirements.txt, setup.py, pyproject.toml
- Checks against PyPI vulnerability database
- Provides fix version recommendations
- Risk scoring based on vulnerability severity

**Risk Levels**:

| Level | Description |
|-------|-------------|
| CRITICAL | Remote code execution, complete system compromise |
| HIGH | Privilege escalation, data breach potential |
| MODERATE | Information disclosure, denial of service |
| LOW | Minor security issues |
| SAFE | No known vulnerabilities |

**Output Example**:
```
DEPENDENCY VULNERABILITIES
--------------------------
Dependencies Analyzed: 45
Vulnerable Packages: 3

  [CRITICAL] requests 2.25.0
    CVE-2023-32681: Unintended leak of Proxy-Authorization header
    Fix: Upgrade to 2.31.0

  [HIGH] pyyaml 5.3.1
    CVE-2020-14343: Arbitrary code execution via FullLoader
    Fix: Upgrade to 5.4
```

---

### 3. Injection Detection Service

**Purpose**: Detects potential injection vulnerabilities including SQL injection, XSS, command injection, and path traversal.

**Detected Vulnerability Types**:

| Type | Description | CWE |
|------|-------------|-----|
| `sql_injection` | SQL query built with string formatting | CWE-89 |
| `xss` | Unescaped user input in HTML output | CWE-79 |
| `command_injection` | User input in shell commands | CWE-78 |
| `path_traversal` | User input in file paths | CWE-22 |
| `insecure_deserialization` | Untrusted data deserialization | CWE-502 |
| `ssrf` | Server-side request forgery patterns | CWE-918 |
| `open_redirect` | Unvalidated redirects | CWE-601 |

**Detection Examples**:

```python
# SQL Injection (CRITICAL)
query = f"SELECT * FROM users WHERE id = {user_id}"
cursor.execute("DELETE FROM users WHERE id = " + str(user_id))

# Command Injection (CRITICAL)
os.system(f"echo {user_input}")
subprocess.call(user_command, shell=True)

# Path Traversal (HIGH)
file_path = os.path.join(base_dir, user_filename)
open(user_supplied_path, "r")

# XSS (HIGH)
return f"<div>{user_input}</div>"
html = "<script>" + user_data + "</script>"
```

**OWASP Mapping**:
- A03:2021 - Injection
- A07:2021 - Cross-Site Scripting

---

### 4. Cryptographic Validation Service

**Purpose**: Identifies weak, deprecated, or improperly implemented cryptographic operations.

**Detected Issues**:

| Issue | Severity | Description |
|-------|----------|-------------|
| Weak hash algorithms | HIGH | MD5, SHA1 for security purposes |
| Insecure random | HIGH | Using `random` instead of `secrets` |
| Disabled SSL verification | HIGH | `verify=False` in HTTPS calls |
| Hardcoded encryption keys | CRITICAL | Encryption keys in source code |
| Deprecated ciphers | MEDIUM | DES, 3DES, RC4 usage |
| Base64 as encryption | HIGH | Using encoding for security |
| ECB mode | MEDIUM | Electronic Codebook mode usage |
| Small key sizes | MEDIUM | Keys below recommended sizes |

**Detection Examples**:

```python
# Weak hash (HIGH)
hashlib.md5(password.encode())
hashlib.sha1(sensitive_data)

# Insecure random (HIGH)
import random
token = random.randint(0, 999999)

# Disabled SSL (HIGH)
requests.get(url, verify=False)
ssl_context.check_hostname = False

# Base64 "encryption" (HIGH)
encrypted = base64.b64encode(secret.encode())
```

**Recommendations**:
- Use SHA-256 or SHA-3 for hashing
- Use `secrets` module for cryptographic randomness
- Always verify SSL certificates
- Use `cryptography` library with proper key management

---

### 5. Static Security Service

**Purpose**: Orchestrates all security analyzers into a unified scan with consolidated reporting.

**Key Features**:
- Runs all analyzers in a single scan
- Aggregates findings with severity counts
- Calculates overall security score (0-100)
- Generates comprehensive reports

**Security Score Calculation**:
```
Score = 100 - (critical * 25) - (high * 10) - (medium * 5) - (low * 1)
Score = max(0, Score)  # Floor at 0
```

| Score Range | Status |
|-------------|--------|
| 80-100 | Healthy |
| 60-79 | Needs Attention |
| 40-59 | At Risk |
| 0-39 | Critical |

---

## Usage Examples

### CLI Usage

```bash
# Full security scan
python -m Heimdall security scan ./src

# Specific analyzers
python -m Heimdall security secrets ./src
python -m Heimdall security dependencies ./src
python -m Heimdall security vulnerabilities ./src
python -m Heimdall security crypto ./src

# With options
python -m Heimdall security scan ./src --severity medium --format json
python -m Heimdall security scan ./src --exclude "test_*" --format markdown
```

### Programmatic Usage

```python
from Heimdall.Security import (
    StaticSecurityService,
    SecretsDetectionService,
    DependencyVulnerabilityService,
    InjectionDetectionService,
    CryptographicValidationService,
    SecurityScanConfig
)
from pathlib import Path

# Full security scan
service = StaticSecurityService()
report = service.scan(Path("./src"))

print(f"Security Score: {report.security_score}/100")
print(f"Total Issues: {report.total_issues}")
print(f"Critical: {report.critical_issues}")
print(f"High: {report.high_issues}")

# Secrets detection only
secrets_service = SecretsDetectionService()
secrets_report = secrets_service.scan(Path("./src"))

for finding in secrets_report.findings:
    print(f"[{finding.severity}] {finding.file_path}:{finding.line_number}")
    print(f"  Type: {finding.secret_type}")
    print(f"  Value: {finding.masked_value}")

# Dependency scanning
dep_service = DependencyVulnerabilityService()
dep_report = dep_service.scan(Path("./src"))

for vuln in dep_report.vulnerabilities:
    print(f"[{vuln.risk_level}] {vuln.package_name} {vuln.installed_version}")
    print(f"  {vuln.title}")
    print(f"  Fix: {vuln.fixed_version}")
```

---

## Configuration

### SecurityScanConfig

```python
SecurityScanConfig(
    scan_path=Path("."),           # Root path to scan
    scan_secrets=True,             # Enable secrets detection
    scan_vulnerabilities=True,     # Enable injection detection
    scan_dependencies=True,        # Enable dependency scanning
    scan_crypto=True,              # Enable crypto validation
    min_severity="low",            # Minimum severity: info, low, medium, high, critical
    exclude_patterns=[             # Patterns to exclude
        "__pycache__",
        "node_modules",
        ".git",
        ".venv",
        "venv",
        "test",
        "tests"
    ],
    include_extensions=None,       # File extensions (None = all supported)
    custom_patterns={},            # Additional detection patterns
    ignore_paths=[],               # Specific paths to ignore
    baseline_file=None             # Previous scan for comparison
)
```

---

## Output Formats

### Text (Default)

```
============================================================
HEIMDALL SECURITY ANALYSIS REPORT
============================================================
Scan Path: ./src
Scanned At: 2024-01-15 10:30:00
Duration: 2.45 seconds

----------------------------------------
SUMMARY
----------------------------------------
Security Score: 65.0/100
Total Issues: 12
  Critical: 1
  High: 4
  Medium: 5
  Low: 2

----------------------------------------
SECRETS DETECTION
----------------------------------------
Files Scanned: 156
Secrets Found: 5

  [CRITICAL] src/config.py:45
    aws_credentials: AKIA****************WXYZ
  [HIGH] src/database.py:12
    database_url: mysql://****:****@localhost/db

============================================================
RESULT: FAIL
============================================================
```

### JSON

```json
{
  "scan_path": "./src",
  "security_score": 65.0,
  "total_issues": 12,
  "critical_issues": 1,
  "high_issues": 4,
  "secrets_report": {
    "findings": [
      {
        "file_path": "src/config.py",
        "line_number": 45,
        "secret_type": "aws_credentials",
        "severity": "critical",
        "masked_value": "AKIA****************WXYZ"
      }
    ]
  }
}
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Scan passed (no critical/high issues) |
| 1 | Scan failed (critical or high issues found) |
| 2 | Fatal error during analysis |

---

## Extended Security Analyzers

The Security module includes additional specialized analyzers for comprehensive security coverage.

---

### 6. Access Control Analyzer

**Purpose**: Detects access control issues including missing authentication, improper authorization, and RBAC/ABAC pattern violations.

**Key Features**:
- Route permission analysis
- Decorator-based auth detection
- RBAC/ABAC pattern validation
- Missing authorization detection

**Detected Issues**:

| Type | Description | Severity |
|------|-------------|----------|
| `missing_auth` | Route without authentication decorator | HIGH |
| `missing_authorization` | Authenticated route without authorization | MEDIUM |
| `hardcoded_role` | Role checks with hardcoded strings | LOW |
| `inconsistent_rbac` | Inconsistent RBAC patterns | MEDIUM |
| `public_sensitive_endpoint` | Sensitive endpoint without protection | CRITICAL |

**Usage**:
```python
from Heimdall.Security import AccessAnalyzer, AccessConfig

analyzer = AccessAnalyzer(AccessConfig(scan_path="./src"))
report = analyzer.analyze()

print(f"Access Issues: {report.total_issues}")
print(f"Score: {report.score}/100")

for finding in report.findings:
    print(f"[{finding.severity}] {finding.file_path}:{finding.line}")
    print(f"  {finding.message}")
```

**CLI**:
```bash
python -m Heimdall security access ./src
python -m Heimdall security access ./src --format json
```

---

### 7. Authentication Analyzer

**Purpose**: Analyzes authentication implementations for security issues including JWT vulnerabilities, session management problems, and password handling flaws.

**Key Features**:
- JWT security validation (none algorithm, weak secrets)
- Session security analysis (cookie flags, fixation)
- Password handling analysis (plaintext, weak hashing)
- Token expiration validation

**Detected Issues**:

| Type | Description | Severity |
|------|-------------|----------|
| `jwt_none_algorithm` | JWT using "none" algorithm | CRITICAL |
| `jwt_weak_secret` | JWT with weak or hardcoded secret | HIGH |
| `jwt_missing_expiration` | JWT without expiration claim | MEDIUM |
| `session_no_httponly` | Session cookie without HttpOnly flag | HIGH |
| `session_no_secure` | Session cookie without Secure flag | HIGH |
| `session_fixation` | Vulnerable to session fixation | HIGH |
| `plaintext_password` | Password stored in plaintext | CRITICAL |
| `weak_password_hash` | Using MD5/SHA1 for passwords | HIGH |
| `hardcoded_credentials` | Credentials in source code | CRITICAL |

**Usage**:
```python
from Heimdall.Security import AuthAnalyzer, AuthConfig

analyzer = AuthAnalyzer(AuthConfig(scan_path="./src"))
report = analyzer.analyze()

print(f"Auth Issues: {report.total_issues}")
for finding in report.findings:
    print(f"[{finding.finding_type}] {finding.description}")
```

**CLI**:
```bash
python -m Heimdall security auth ./src
python -m Heimdall security auth ./src --severity high
```

---

### 8. Security Headers Analyzer

**Purpose**: Validates security header configurations including CSP, CORS, HSTS, and other protective headers.

**Key Features**:
- Content Security Policy (CSP) validation
- CORS configuration analysis
- HSTS configuration checking
- X-Frame-Options, X-Content-Type-Options validation

**Detected Issues**:

| Type | Description | Severity |
|------|-------------|----------|
| `missing_csp` | No Content-Security-Policy header | HIGH |
| `unsafe_csp_inline` | CSP allows unsafe-inline | MEDIUM |
| `unsafe_csp_eval` | CSP allows unsafe-eval | HIGH |
| `cors_wildcard` | CORS allows all origins (*) | HIGH |
| `cors_credentials_wildcard` | CORS credentials with wildcard | CRITICAL |
| `missing_hsts` | No Strict-Transport-Security header | MEDIUM |
| `hsts_short_max_age` | HSTS max-age too short | LOW |
| `missing_x_frame_options` | No X-Frame-Options header | MEDIUM |
| `missing_x_content_type` | No X-Content-Type-Options header | LOW |

**Usage**:
```python
from Heimdall.Security import HeadersAnalyzer, HeaderConfig

analyzer = HeadersAnalyzer(HeaderConfig(scan_path="./src"))
report = analyzer.analyze()

print(f"Header Issues: {report.total_issues}")
print(f"CSP Issues: {len([f for f in report.findings if 'csp' in f.finding_type.value])}")
```

**CLI**:
```bash
python -m Heimdall security headers ./src
python -m Heimdall security headers ./src --format markdown
```

---

### 9. TLS/SSL Analyzer

**Purpose**: Analyzes TLS/SSL configurations for security issues including weak protocols, insecure ciphers, and certificate problems.

**Key Features**:
- Protocol version validation (TLS 1.2+ required)
- Cipher suite analysis
- Certificate validation patterns
- SSL context configuration checking

**Detected Issues**:

| Type | Description | Severity |
|------|-------------|----------|
| `ssl_v2_enabled` | SSLv2 protocol enabled | CRITICAL |
| `ssl_v3_enabled` | SSLv3 protocol enabled | CRITICAL |
| `tls_1_0_enabled` | TLS 1.0 protocol enabled | HIGH |
| `tls_1_1_enabled` | TLS 1.1 protocol enabled | MEDIUM |
| `weak_cipher` | Weak cipher suite configured | HIGH |
| `no_cert_verification` | Certificate verification disabled | CRITICAL |
| `self_signed_allowed` | Self-signed certificates allowed | MEDIUM |
| `expired_cert_ignored` | Expired certificate errors ignored | HIGH |

**Usage**:
```python
from Heimdall.Security import TLSAnalyzer, TLSConfig

analyzer = TLSAnalyzer(TLSConfig(scan_path="./src"))
report = analyzer.analyze()

print(f"TLS Issues: {report.total_issues}")
print(f"Score: {report.score}/100")
```

**CLI**:
```bash
python -m Heimdall security tls ./src
python -m Heimdall security tls ./src --severity medium
```

---

### 10. Container Security Analyzer

**Purpose**: Analyzes Docker and container configurations for security issues including privileged containers, exposed secrets, and insecure defaults.

**Key Features**:
- Dockerfile security analysis
- docker-compose.yml security validation
- Privileged mode detection
- Secrets exposure detection
- User/root analysis

**Detected Issues**:

| Type | Description | Severity |
|------|-------------|----------|
| `privileged_container` | Container running in privileged mode | CRITICAL |
| `root_user` | Container running as root | HIGH |
| `exposed_secrets` | Secrets in Dockerfile/compose | CRITICAL |
| `sensitive_port_exposed` | Sensitive ports exposed publicly | HIGH |
| `no_healthcheck` | Missing health check | LOW |
| `latest_tag` | Using :latest tag | MEDIUM |
| `add_instead_copy` | Using ADD instead of COPY | LOW |
| `no_user_instruction` | No USER instruction | MEDIUM |

**Usage**:
```python
from Heimdall.Security import ContainerAnalyzer, ContainerConfig

analyzer = ContainerAnalyzer(ContainerConfig(scan_path="./src"))
report = analyzer.analyze()

print(f"Container Issues: {report.total_issues}")
for finding in report.findings:
    print(f"[{finding.severity}] {finding.file_path}: {finding.message}")
```

**CLI**:
```bash
python -m Heimdall security container ./src
python -m Heimdall security container ./src --format json
```

---

### 11. Infrastructure Security Analyzer

**Purpose**: Analyzes infrastructure configurations for security issues including default credentials, insecure configurations, and missing hardening.

**Key Features**:
- Default credential detection
- Configuration security validation
- Hardening best practice checking
- Debug mode detection
- Exposed admin endpoints

**Detected Issues**:

| Type | Description | Severity |
|------|-------------|----------|
| `default_credentials` | Default or weak credentials | CRITICAL |
| `debug_mode_enabled` | Debug mode in production config | HIGH |
| `admin_endpoint_exposed` | Admin endpoints without protection | HIGH |
| `insecure_config` | Insecure configuration values | MEDIUM |
| `missing_rate_limiting` | No rate limiting configured | MEDIUM |
| `verbose_errors` | Verbose error messages enabled | MEDIUM |
| `missing_logging` | Security logging not configured | LOW |

**Usage**:
```python
from Heimdall.Security import InfraAnalyzer, InfraConfig

analyzer = InfraAnalyzer(InfraConfig(scan_path="./src"))
report = analyzer.analyze()

print(f"Infrastructure Issues: {report.total_issues}")
print(f"Score: {report.score}/100")
```

**CLI**:
```bash
python -m Heimdall security infra ./src
python -m Heimdall security infra ./src --severity high
```

---

## Complete Security Scan

The `StaticSecurityService` can run all security analyzers in a single unified scan:

```python
from Heimdall.Security import StaticSecurityService, SecurityScanConfig

# Configure scan with all analyzers
config = SecurityScanConfig(
    scan_path="./src",
    # Core analyzers
    scan_secrets=True,
    scan_vulnerabilities=True,
    scan_dependencies=True,
    scan_crypto=True,
    # Extended analyzers
    scan_access=True,
    scan_auth=True,
    scan_headers=True,
    scan_tls=True,
    scan_container=True,
    scan_infra=True,
    min_severity="medium"
)

service = StaticSecurityService(config)
report = service.scan()

print(f"Overall Security Score: {report.security_score}/100")
print(f"Total Issues: {report.total_issues}")
print(f"  Critical: {report.critical_issues}")
print(f"  High: {report.high_issues}")
print(f"  Medium: {report.medium_issues}")
print(f"  Low: {report.low_issues}")
```

---

## Best Practices

1. **Run regularly**: Include security scans in CI/CD pipelines
2. **Set appropriate severity**: Use `--severity medium` for production code
3. **Exclude test fixtures**: Test files may contain intentional "secrets" for testing
4. **Review all findings**: Some patterns may produce false positives
5. **Fix critical issues first**: Prioritize by severity
6. **Use baseline files**: Track security improvements over time
7. **Layer security checks**: Use access + auth + headers for API security
8. **Container hardening**: Always run container analysis before deployment
9. **Infrastructure review**: Run infra analysis on config files before deployment
