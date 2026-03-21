# Security Tools Usage Guide

## Quick Start

### Run a Comprehensive Audit

```bash
cd security-tools
python security_toolkit.py --audit /path/to/your/project
```

This runs 23+ security checks including:
- Secret scanning
- SQL injection detection
- XSS vulnerability detection
- And many more...

### Run Individual Scanners

```bash
# Scan for secrets
python secrets_scanner.py /path/to/code

# Scan for SQL injection
python sql_injection_scanner.py /path/to/code

# Scan for XSS
python xss_scanner.py /path/to/code
```

### List All Available Tools

```bash
python security_toolkit.py --list
```

## Common Use Cases

### 1. Pre-Commit Scanning

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: security-secrets
        name: Scan for secrets
        entry: python /path/to/security-tools/secrets_scanner.py
        language: python
        pass_filenames: false
```

### 2. CI/CD Pipeline Integration

```yaml
# GitHub Actions
- name: Security Scan
  run: |
    python security-tools/security_api.py all . -f sarif -o results.sarif

- uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: results.sarif
```

### 3. Pull Request Checks

```bash
# Check for critical issues before merge
python security_api.py all . -f json | python -c "
import json, sys
data = json.load(sys.stdin)
critical = sum(s['by_severity']['CRITICAL'] for s in data['scans'].values())
if critical > 0:
    print(f'FAILED: {critical} critical issues')
    sys.exit(1)
print('PASSED')
"
```

### 4. Scheduled Security Audits

```bash
# Weekly security report
python security_api.py all /path/to/project -o weekly-report-$(date +%Y%m%d).json
```

## Scanner Categories

### Code Security
- `sqli` - SQL injection
- `xss` - Cross-site scripting
- `cmdi` - Command injection
- `traversal` - Path traversal
- `validation` - Input validation
- `redos` - Regex DoS
- `race` - Race conditions

### Credential Security
- `secrets` - API keys and secrets
- `sensitive` - PII exposure
- `auth` - Authentication issues

### Web Security
- `frontend` - DOM XSS, prototype pollution
- `api` - REST/GraphQL issues
- `ssrf` - SSRF/XXE

### Configuration
- `misconfig` - Security misconfigurations
- `crypto` - Weak cryptography
- `disclosure` - Information disclosure

### Malware Detection
- `malware` - Malware signatures
- `backdoor` - Backdoors and shells
- `exfil` - Data exfiltration

### Infrastructure
- `container` - Docker/K8s security
- `git` - Git repository security
- `permissions` - File permissions

## Understanding Results

### Severity Levels

| Severity | Action Required |
|----------|----------------|
| **CRITICAL** | Fix immediately - active exploitation risk |
| **HIGH** | Fix soon - significant security impact |
| **MEDIUM** | Plan to fix - moderate concern |
| **LOW** | Consider fixing - best practice |

### Exit Codes

- `0` - No issues or low severity only
- `1` - High severity issues found
- `2` - Critical severity issues found

### Example Output

```
======================================================================
SQL INJECTION SCAN
======================================================================

Files Scanned: 42
Total Issues: 3

By Severity:
  CRITICAL: 1
  HIGH: 2

----------------------------------------------------------------------
SQL INJECTION VULNERABILITIES
----------------------------------------------------------------------

[CRITICAL] string_concat_sql
  File: app/database.py:156
  Pattern: query = "SELECT * FROM users WHERE id = " + user_id
  Issue: SQL query built with string concatenation
  Fix: Use parameterized queries with placeholders
```

## Filtering and Customization

### Scan Specific File Types

```bash
# Most scanners automatically filter by language
# JavaScript/TypeScript
python frontend_security_scanner.py /path/to/frontend

# Python
python sql_injection_scanner.py /path/to/backend
```

### Non-Recursive Scan

```bash
python secrets_scanner.py /path/to/code --no-recursive
```

### Output Formats

```bash
# JSON output
python security_api.py sqli . -f json -o results.json

# SARIF for GitHub
python security_api.py sqli . -f sarif -o results.sarif
```

## Best Practices

### 1. Start with Secrets

Always begin by scanning for exposed secrets - this is often the highest-risk issue:

```bash
python secrets_scanner.py .
```

### 2. Focus on Critical First

Address CRITICAL and HIGH severity issues before others.

### 3. Use in Development

Integrate into your development workflow:
- Pre-commit hooks for immediate feedback
- CI/CD for comprehensive checking
- Scheduled scans for ongoing monitoring

### 4. Baseline Known Issues

For large codebases, establish a baseline and focus on preventing new issues.

### 5. Regular Full Audits

Run comprehensive audits regularly:

```bash
python security_toolkit.py --audit . > audit-$(date +%Y%m%d).txt
```

## Troubleshooting

### Scanner Not Finding Issues

1. Check file extensions are supported
2. Verify path is correct
3. Try verbose/debug mode if available
4. Check scanner patterns match your code style

### False Positives

Some patterns may produce false positives. Review context carefully and:
- Add exceptions/ignores as needed
- Report pattern improvements

### Performance Issues

For large codebases:
- Scan specific directories
- Run scanners in parallel
- Use file type filters

## Integration Examples

### GitLab CI

```yaml
security:
  stage: test
  script:
    - python security_api.py all . -f json -o security.json
  artifacts:
    reports:
      sast: security.json
```

### Jenkins

```groovy
pipeline {
  stages {
    stage('Security') {
      steps {
        sh 'python security_api.py all . -o results.json'
        archiveArtifacts 'results.json'
      }
    }
  }
}
```

### Azure DevOps

```yaml
- task: PythonScript@0
  inputs:
    scriptSource: inline
    script: |
      import subprocess
      subprocess.run(['python', 'security_api.py', 'all', '.', '-o', 'results.json'])
```

## Getting Help

```bash
# Tool help
python security_toolkit.py --help

# Individual scanner help
python sql_injection_scanner.py --help
python security_api.py --help
```
