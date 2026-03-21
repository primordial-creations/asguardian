# Security Tools Suite

A comprehensive collection of 34+ cybersecurity checking tools for defensive security, auditing, and code analysis.

## Features

- **34+ Security Scanners** covering OWASP Top 10 and more
- **Multi-language support** - Python, JavaScript, TypeScript, Java, Go, Ruby, PHP, C#
- **CI/CD Integration** - JSON and SARIF output formats
- **GitHub Actions** - Ready-to-use workflow included
- **Pre-commit hooks** - Catch issues before commit
- **Programmatic API** - Integrate into your tools

## Quick Start

```bash
# Run comprehensive security audit
python security_toolkit.py --audit /path/to/project

# Use the API for JSON/SARIF output
python security_api.py all . -f sarif -o results.sarif

# Run tests
pytest tests/ -v
```

## Tools Overview (34 Tools)

### Code Security (12 tools)
| Tool | Command | Description |
|------|---------|-------------|
| SQL Injection Scanner | `sqli` | Detect SQL injection vulnerabilities |
| XSS Scanner | `xss` | Cross-site scripting detection |
| Command Injection | `cmdi` | OS command injection |
| Path Traversal | `traversal` | Directory traversal/LFI |
| SSRF/XXE Scanner | `ssrf` | SSRF and XXE vulnerabilities |
| Deserialization | `deserial` | Insecure deserialization |
| Input Validation | `validation` | Missing input validation |
| ReDoS Scanner | `redos` | Regex denial of service |
| Race Condition | `race` | Race conditions and TOCTOU |
| Encryption Analyzer | `crypto` | Weak cryptographic implementations |
| Auth Security | `auth` | Authentication/session issues |
| Dependency Checker | `dependencies` | Vulnerable dependencies |

### Web Security (4 tools)
| Tool | Command | Description |
|------|---------|-------------|
| Frontend Security | `frontend` | DOM XSS, prototype pollution, postMessage |
| API Security | `api` | REST/GraphQL security issues |
| HTTP Headers | `headers` | Security headers check |
| CORS Checker | `cors` | CORS misconfigurations |

### Data Protection (3 tools)
| Tool | Command | Description |
|------|---------|-------------|
| Secrets Scanner | `secrets` | API keys, tokens, credentials |
| Sensitive Data | `sensitive` | PII, credit cards, SSN |
| Info Disclosure | `disclosure` | Information disclosure issues |

### Malware Detection (3 tools)
| Tool | Command | Description |
|------|---------|-------------|
| Malware Scanner | `malware` | Malware signatures and patterns |
| Backdoor Detector | `backdoor` | Backdoors and web shells |
| Data Exfiltration | `exfil` | Data exfiltration patterns |

### Configuration (2 tools)
| Tool | Command | Description |
|------|---------|-------------|
| Misconfiguration | `misconfig` | Security misconfigurations |
| Container Security | `container` | Docker/Kubernetes issues |

### Network Security (4 tools)
| Tool | Command | Description |
|------|---------|-------------|
| Port Scanner | `ports` | Open port scanning |
| SSL/TLS Checker | `ssl` | Certificate security |
| DNS Security | `dns` | SPF, DMARC, DNSSEC |
| Git Security | `git` | Git repository security |

### Other (6 tools)
| Tool | Command | Description |
|------|---------|-------------|
| Password Strength | `password` | Password analysis |
| File Integrity | `integrity` | Checksum verification |
| Permission Auditor | `permissions` | File permission audit |
| Hash Analyzer | `hash` | Hash identification |
| Log Analyzer | `logs` | Security event analysis |

## Usage

### Unified Toolkit

```bash
# List all tools
python security_toolkit.py --list

# Run specific tool
python security_toolkit.py sqli /path/to/code
python security_toolkit.py secrets .

# Run comprehensive audit (23 tools)
python security_toolkit.py --audit /path/to/project
```

### API with JSON/SARIF Output

```bash
# JSON output
python security_api.py sqli . -f json -o results.json

# SARIF for GitHub Code Scanning
python security_api.py all . -f sarif -o results.sarif

# List available tools
python security_api.py --list
```

### Python API

```python
from security_api import SecurityAPI

api = SecurityAPI()

# Single scan
report = api.scan('sqli', '/path/to/code')
print(f"Found {report.total_issues} issues")

# Get JSON
json_output = api.to_json(report)

# Get SARIF
sarif_output = api.to_sarif(report)

# Run all scans
results = api.scan_all('/path/to/code')
```

## CI/CD Integration

### GitHub Actions

A complete workflow is included at `.github/workflows/security-scan.yml`:

```yaml
- name: Security Scan
  run: python security_api.py all . -f sarif -o results.sarif

- uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: results.sarif
```

### Pre-commit Hooks

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: security-secrets
        name: Scan for secrets
        entry: python security-tools/secrets_scanner.py
        language: python
        pass_filenames: false
```

### Exit Codes

- `0` - No issues or LOW severity only
- `1` - HIGH severity issues found
- `2` - CRITICAL severity issues found

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=. --cov-report=html
```

## Documentation

- [API Documentation](docs/API.md) - Programmatic API reference
- [Usage Guide](docs/USAGE.md) - Detailed usage examples

## Severity Levels

| Level | Score | Action |
|-------|-------|--------|
| CRITICAL | 9.0 | Fix immediately |
| HIGH | 7.0 | Fix soon |
| MEDIUM | 5.0 | Plan to fix |
| LOW | 3.0 | Consider fixing |

## Individual Tool Examples

```bash
# Scan for secrets
python secrets_scanner.py /path/to/code

# SQL injection detection
python sql_injection_scanner.py /path/to/code

# XSS vulnerability scan
python xss_scanner.py /path/to/code

# Frontend security (DOM XSS, prototype pollution)
python frontend_security_scanner.py /path/to/frontend

# API security (REST/GraphQL)
python api_security_scanner.py /path/to/api

# Check for sensitive data (PII, credentials)
python sensitive_data_scanner.py /path/to/code

# Detect race conditions
python race_condition_detector.py /path/to/code

# Git repository security
python git_security_scanner.py /path/to/repo

# Security misconfigurations
python security_misconfig_scanner.py /path/to/configs

# Malware detection
python malware_scanner.py /path/to/code
```

## Requirements

- Python 3.8+
- No external dependencies for core scanning
- pytest for testing

```bash
pip install -r requirements.txt
```

## Security Considerations

These tools are intended for:
- Security auditing of your own systems
- Educational purposes
- Defensive security assessments
- CI/CD pipeline integration

**Always obtain proper authorization before scanning systems you don't own.**

## Project Structure

```
security-tools/
├── *_scanner.py          # Individual scanners
├── security_toolkit.py   # Unified CLI interface
├── security_api.py       # Programmatic API
├── tests/                # Unit tests
│   ├── test_scanners.py
│   └── conftest.py
├── docs/                 # Documentation
│   ├── API.md
│   └── USAGE.md
├── .github/workflows/    # GitHub Actions
└── .pre-commit-hooks.yaml
```

## License

MIT License - Use responsibly for defensive security purposes only.
