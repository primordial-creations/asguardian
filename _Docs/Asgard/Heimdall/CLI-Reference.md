# Heimdall CLI Reference

## Installation

```bash
# From GAIA root directory
pip install -e ./Heimdall
```

## Basic Usage

```bash
# Using module directly
python -m Heimdall <command> [options]

# Using entry point (after install)
heimdall <command> [options]
```

## Global Options

| Option | Description |
|--------|-------------|
| `-v, --verbose` | Enable verbose output |
| `-h, --help` | Show help message |

---

## Syntax Commands

### check - Run Syntax and Linting Checks

```bash
heimdall syntax check <path> [options]
```

Runs syntax and linting checks using external linters (ruff, flake8, pylint, mypy).

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--linters` | ruff | Comma-separated list of linters: ruff, flake8, pylint, mypy |
| `--min-severity` | warning | Minimum severity: error, warning, info, style |
| `--include-style` | false | Include style issues |
| `--extensions` | .py | File extensions to include |
| `--exclude` | - | Patterns to exclude |
| `--format` | text | Output format: text, json, markdown |

**Example**:
```bash
heimdall syntax check ./src --linters=ruff,flake8 --format=json
heimdall syntax check ./src --min-severity=error --format=markdown
```

---

### fix - Auto-fix Syntax Issues

```bash
heimdall syntax fix <path> [options]
```

Runs syntax analysis and applies auto-fixes using ruff.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--linters` | ruff | Linters to use (ruff supports auto-fix) |
| `--exclude` | - | Patterns to exclude |
| `--format` | text | Output format: text, json, markdown |

**Example**:
```bash
heimdall syntax fix ./src
heimdall syntax fix ./src --format=json
```

---

## Requirements Commands

### check - Validate Requirements.txt

```bash
heimdall requirements check <path> [options]
```

Validates that all imported packages are listed in requirements files and identifies unused packages.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--requirements-files` | requirements.txt,... | Comma-separated list of requirements files |
| `--no-check-unused` | false | Skip checking for unused packages |
| `--exclude` | - | Patterns to exclude from scanning |
| `--format` | text | Output format: text, json, markdown |

**Detected Issues**:
- **Missing**: Package imported but not in requirements
- **Unused**: Package in requirements but not imported

**Example**:
```bash
heimdall requirements check ./src --format=json
heimdall requirements check ./src --no-check-unused
```

---

### sync - Synchronize Requirements.txt

```bash
heimdall requirements sync <path> [options]
```

Automatically updates requirements.txt based on actual imports.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--requirements-files` | requirements.txt | Target file to update |
| `--format` | text | Output format: text, json, markdown |

**Example**:
```bash
heimdall requirements sync ./src
```

---

### unused - List Unused Packages

```bash
heimdall requirements unused <path> [options]
```

Lists packages that are in requirements but not actually imported.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--requirements-files` | requirements.txt,... | Requirements files to check |
| `--format` | text | Output format: text, json, markdown |

**Example**:
```bash
heimdall requirements unused ./src --format=markdown
```

---

## Licenses Commands

### check - License Compliance Check

```bash
heimdall licenses check <path> [options]
```

Validates that all packages have acceptable licenses for commercial use.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--requirements-files` | requirements.txt,... | Requirements files to check |
| `--allow` | MIT,Apache-2.0,... | Comma-separated list of allowed licenses |
| `--prohibit` | GPL-3.0,AGPL-3.0,... | Comma-separated list of prohibited licenses |
| `--no-cache` | false | Disable license caching |
| `--format` | text | Output format: text, json, markdown |

**License Categories**:
- **Permissive**: MIT, Apache-2.0, BSD-3-Clause, BSD-2-Clause, ISC, PSF-2.0
- **Weak Copyleft**: LGPL-3.0, LGPL-2.1, MPL-2.0
- **Strong Copyleft**: GPL-3.0, GPL-2.0, AGPL-3.0 (typically prohibited)
- **Public Domain**: Unlicense, CC0-1.0, WTFPL

**Issue Severities**:
- **CRITICAL**: Prohibited license detected
- **HIGH**: Strong copyleft license
- **MODERATE**: Unknown license
- **LOW**: Weak copyleft license
- **OK**: Permissive/allowed license

**Example**:
```bash
heimdall licenses check ./src --format=json
heimdall licenses check ./src --prohibit="GPL-3.0,AGPL-3.0"
```

---

### audit - Full License Audit

```bash
heimdall licenses audit <path> [options]
```

Same as `check` but provides more detailed reporting of all packages.

**Example**:
```bash
heimdall licenses audit ./src --format=markdown
```

---

## Logic Commands

### duplication - Code Duplication Detection

```bash
heimdall logic duplication <path> [options]
```

Detects duplicated code blocks using AST comparison.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--min-tokens` | 50 | Minimum tokens for duplicate detection |
| `--min-lines` | 6 | Minimum lines for duplicate detection |
| `--extensions` | .py | File extensions to include |
| `--exclude` | - | Patterns to exclude |
| `--format` | text | Output format: text, json, markdown |

**Example**:
```bash
heimdall logic duplication ./src --min-lines=10 --format=json
```

---

### patterns - Code Pattern Detection

```bash
heimdall logic patterns <path> [options]
```

Detects inefficient patterns and anti-patterns in code.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--severity` | low | Minimum severity: critical, high, medium, low, info |
| `--extensions` | .py | File extensions to include |
| `--exclude` | - | Patterns to exclude |
| `--format` | text | Output format: text, json, markdown |

**Detected Patterns**: Long methods, long parameter lists, deep nesting, feature envy, data clumps, god classes

**Example**:
```bash
heimdall logic patterns ./src --severity=medium --format=markdown
```

---

### complexity - Cyclomatic Complexity Analysis

```bash
heimdall logic complexity <path> [options]
```

Analyzes cyclomatic and cognitive complexity of functions.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--max-complexity` | 10 | Maximum acceptable cyclomatic complexity |
| `--extensions` | .py | File extensions to include |
| `--exclude` | - | Patterns to exclude |
| `--format` | text | Output format: text, json, markdown |

**Example**:
```bash
heimdall logic complexity ./src --max-complexity=8 --format=json
```

---

### audit - Full Logic Audit

```bash
heimdall logic audit <path> [options]
```

Runs all logic analyzers: duplication, patterns, and complexity.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--min-tokens` | 50 | Minimum tokens for duplicate detection |
| `--min-lines` | 6 | Minimum lines for duplicate detection |
| `--max-complexity` | 10 | Maximum cyclomatic complexity |
| `--severity` | low | Minimum severity for patterns |
| `--format` | text | Output format: text, json, markdown |

**Example**:
```bash
heimdall logic audit ./src --format=json
```

---

## Quality Commands

### analyze - Run All Quality Checks

```bash
heimdall quality analyze <path> [options]
```

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--format` | text | Output format: text, json, markdown |
| `--output` | - | Output file path |
| `--include-tests` | false | Include test files |

**Example**:
```bash
heimdall quality analyze ./src --format=json --output=report.json
```

---

### file-length - File Length Analysis

```bash
heimdall quality file-length <path> [options]
```

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--max-file-lines` | 500 | Maximum lines per file |
| `--max-function-lines` | 50 | Maximum lines per function |
| `--max-class-lines` | 300 | Maximum lines per class |
| `--extensions` | .py | File extensions to include |
| `--format` | text | Output format |

**Example**:
```bash
heimdall quality file-length ./src --max-file-lines=400 --format=markdown
```

---

### complexity - Complexity Analysis

```bash
heimdall quality complexity <path> [options]
```

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--max-cyclomatic` | 10 | Maximum cyclomatic complexity |
| `--max-cognitive` | 15 | Maximum cognitive complexity |
| `--include-nested` | true | Include nested functions |
| `--format` | text | Output format |

**Example**:
```bash
heimdall quality complexity ./src --max-cyclomatic=8 --format=json
```

---

### duplication - Duplication Detection

```bash
heimdall quality duplication <path> [options]
```

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--min-lines` | 6 | Minimum lines for duplicate detection |
| `--similarity` | 0.8 | Similarity threshold (0.0-1.0) |
| `--ignore-imports` | true | Ignore import statements |
| `--ignore-comments` | true | Ignore comments |
| `--format` | text | Output format |

**Example**:
```bash
heimdall quality duplication ./src --min-lines=10 --similarity=0.9
```

---

### smells - Code Smell Detection

```bash
heimdall quality smells <path> [options]
```

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--severity` | low | Minimum severity: critical, high, medium, low, info |
| `--max-method-lines` | 50 | Threshold for long method smell |
| `--max-parameters` | 5 | Threshold for long parameter list |
| `--max-nesting` | 4 | Maximum nesting depth |
| `--format` | text | Output format |

**Example**:
```bash
heimdall quality smells ./src --severity=medium --format=markdown
```

---

### debt - Technical Debt Analysis

```bash
heimdall quality debt <path> [options]
```

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--hourly-rate` | 75.0 | Hourly rate for cost calculation |
| `--include-projections` | true | Include time projections |
| `--categories` | all | Debt categories to analyze |
| `--format` | text | Output format |

**Categories**: code, design, test, documentation, dependencies

**Example**:
```bash
heimdall quality debt ./src --hourly-rate=100 --format=json
```

---

### maintainability - Maintainability Index

```bash
heimdall quality maintainability <path> [options]
```

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--language` | python | Language profile: python, java, javascript |
| `--include-halstead` | true | Include Halstead metrics |
| `--include-comments` | true | Factor in comment density |
| `--include-tests` | false | Include test files |
| `--format` | text | Output format |

**Example**:
```bash
heimdall quality maintainability ./src --language=python --format=markdown
```

---

### lazy-imports - Lazy Import Detection

```bash
heimdall quality lazy-imports <path> [options]
```

Detects imports not at module level, which violates the GAIA coding standard that ALL imports MUST be at the top of the file.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--severity` | low | Minimum severity: low, medium, high |
| `--include-tests` | true | Include test files |
| `--format` | text | Output format |
| `--exclude` | - | Additional patterns to exclude |

**Detected Violations**:
- **HIGH**: Imports inside functions or methods
- **MEDIUM**: Imports inside conditionals or try/except blocks
- **LOW**: Imports inside loops or with blocks

**Special Exception**: Imports inside `if TYPE_CHECKING:` blocks are allowed (valid pattern for type hints).

**Example**:
```bash
heimdall quality lazy-imports ./src --format=json
heimdall quality lazy-imports ./src --severity=high --format=markdown
```

---

## Security Commands

### scan - Full Security Scan

```bash
heimdall security scan <path> [options]
```

Runs all security analyzers: secrets detection, dependency vulnerabilities, injection detection, and cryptographic validation.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--format, -f` | text | Output format: text, json, markdown |
| `--severity, -s` | low | Minimum severity: info, low, medium, high, critical |
| `--exclude, -x` | - | Additional patterns to exclude |

**Example**:
```bash
heimdall security scan ./src --severity=medium --format=json
heimdall security scan ./src --exclude "test_*" "*.test.*"
```

---

### secrets - Secrets Detection

```bash
heimdall security secrets <path> [options]
```

Detects hardcoded secrets, API keys, passwords, and credentials.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--format, -f` | text | Output format: text, json, markdown |
| `--severity, -s` | low | Minimum severity to report |
| `--exclude, -x` | - | Additional patterns to exclude |

**Detected Types**: API keys, AWS/Azure/GCP credentials, passwords, private keys, access tokens, database URLs, JWT tokens, SSH keys, certificates

**Example**:
```bash
heimdall security secrets ./src --format=json
```

---

### dependencies - Dependency Vulnerabilities

```bash
heimdall security dependencies <path> [options]
```

Scans project dependencies for known security vulnerabilities.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--format, -f` | text | Output format: text, json, markdown |
| `--severity, -s` | low | Minimum severity to report |

**Supported Files**: requirements.txt, setup.py, pyproject.toml

**Example**:
```bash
heimdall security dependencies ./src --format=markdown
```

---

### vulnerabilities - Injection Detection

```bash
heimdall security vulnerabilities <path> [options]
```

Detects potential injection vulnerabilities in source code.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--format, -f` | text | Output format: text, json, markdown |
| `--severity, -s` | low | Minimum severity to report |
| `--exclude, -x` | - | Additional patterns to exclude |

**Detected Vulnerabilities**: SQL injection, XSS, command injection, path traversal, insecure deserialization, SSRF, open redirect

**Example**:
```bash
heimdall security vulnerabilities ./src --severity=high
```

---

### crypto - Cryptographic Validation

```bash
heimdall security crypto <path> [options]
```

Identifies weak, deprecated, or improperly implemented cryptographic operations.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--format, -f` | text | Output format: text, json, markdown |
| `--severity, -s` | low | Minimum severity to report |
| `--exclude, -x` | - | Additional patterns to exclude |

**Detected Issues**: Weak hash algorithms (MD5, SHA1), insecure random, disabled SSL, hardcoded keys, deprecated ciphers, Base64 as encryption

**Example**:
```bash
heimdall security crypto ./src --format=json
```

---

### access - Access Control Analysis

```bash
heimdall security access <path> [options]
```

Analyzes access control patterns including RBAC/ABAC, route permissions, and authorization checks.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--format, -f` | text | Output format: text, json, markdown |
| `--severity, -s` | low | Minimum severity to report |
| `--exclude, -x` | - | Additional patterns to exclude |

**Detected Issues**: Missing authentication decorators, missing authorization, hardcoded roles, inconsistent RBAC patterns, unprotected sensitive endpoints

**Example**:
```bash
heimdall security access ./src --format=json
heimdall security access ./src --severity=high
```

---

### auth - Authentication Analysis

```bash
heimdall security auth <path> [options]
```

Analyzes authentication implementations for security issues.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--format, -f` | text | Output format: text, json, markdown |
| `--severity, -s` | low | Minimum severity to report |
| `--exclude, -x` | - | Additional patterns to exclude |

**Detected Issues**: JWT none algorithm, weak JWT secrets, missing token expiration, session cookie flags (HttpOnly, Secure), session fixation, plaintext passwords, weak password hashing, hardcoded credentials

**Example**:
```bash
heimdall security auth ./src --format=markdown
heimdall security auth ./src --severity=medium
```

---

### headers - Security Headers Analysis

```bash
heimdall security headers <path> [options]
```

Validates security header configurations in application code.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--format, -f` | text | Output format: text, json, markdown |
| `--severity, -s` | low | Minimum severity to report |
| `--exclude, -x` | - | Additional patterns to exclude |

**Detected Issues**: Missing/misconfigured CSP (unsafe-inline, unsafe-eval), CORS wildcards with credentials, missing HSTS, short HSTS max-age, missing X-Frame-Options, missing X-Content-Type-Options

**Example**:
```bash
heimdall security headers ./src --format=json
heimdall security headers ./src --severity=high
```

---

### tls - TLS/SSL Analysis

```bash
heimdall security tls <path> [options]
```

Analyzes TLS/SSL configurations for security issues.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--format, -f` | text | Output format: text, json, markdown |
| `--severity, -s` | low | Minimum severity to report |
| `--exclude, -x` | - | Additional patterns to exclude |

**Detected Issues**: SSLv2/SSLv3 enabled, TLS 1.0/1.1 enabled, weak cipher suites, disabled certificate verification, self-signed certificates allowed, ignored expired certificates

**Example**:
```bash
heimdall security tls ./src --format=markdown
heimdall security tls ./src --severity=critical
```

---

### container - Container Security Analysis

```bash
heimdall security container <path> [options]
```

Analyzes Docker and container configurations for security issues.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--format, -f` | text | Output format: text, json, markdown |
| `--severity, -s` | low | Minimum severity to report |
| `--exclude, -x` | - | Additional patterns to exclude |

**Detected Issues**: Privileged containers, running as root, secrets in Dockerfile/compose, sensitive ports exposed, missing healthchecks, :latest tag usage, ADD instead of COPY, missing USER instruction

**Supported Files**: Dockerfile, docker-compose.yml, docker-compose.yaml

**Example**:
```bash
heimdall security container ./src --format=json
heimdall security container . --severity=high
```

---

### infra - Infrastructure Security Analysis

```bash
heimdall security infra <path> [options]
```

Analyzes infrastructure configurations for security issues.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--format, -f` | text | Output format: text, json, markdown |
| `--severity, -s` | low | Minimum severity to report |
| `--exclude, -x` | - | Additional patterns to exclude |

**Detected Issues**: Default/weak credentials, debug mode in production, exposed admin endpoints, insecure configuration values, missing rate limiting, verbose error messages, missing security logging

**Example**:
```bash
heimdall security infra ./src --format=markdown
heimdall security infra . --severity=medium
```

---

## Performance Commands

### scan - Full Performance Scan

```bash
heimdall performance scan <path> [options]
```

Runs all performance analyzers: memory, CPU, database, and cache analysis.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--format, -f` | text | Output format: text, json, markdown |
| `--severity, -s` | low | Minimum severity: info, low, medium, high, critical |
| `--exclude, -x` | - | Additional patterns to exclude |

**Example**:
```bash
heimdall performance scan ./src --severity=medium --format=json
heimdall performance scan ./src --exclude "migrations" "generated"
```

---

### memory - Memory Analysis

```bash
heimdall performance memory <path> [options]
```

Detects memory-related performance issues including leaks, high allocations, and inefficient data structures.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--format, -f` | text | Output format: text, json, markdown |
| `--severity, -s` | low | Minimum severity to report |
| `--exclude, -x` | - | Additional patterns to exclude |

**Detected Issues**: Memory leaks, high allocations, circular references, large objects, unbounded growth, inefficient structures

**Example**:
```bash
heimdall performance memory ./src --format=markdown
```

---

### cpu - CPU/Complexity Analysis

```bash
heimdall performance cpu <path> [options]
```

Identifies CPU-intensive patterns including high complexity functions and blocking operations.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--format, -f` | text | Output format: text, json, markdown |
| `--severity, -s` | low | Minimum severity to report |
| `--exclude, -x` | - | Additional patterns to exclude |

**Detected Issues**: High cyclomatic complexity, inefficient loops, blocking operations, excessive recursion, redundant computation, synchronous I/O

**Example**:
```bash
heimdall performance cpu ./src --severity=medium --format=json
```

---

### database - Database Analysis

```bash
heimdall performance database <path> [options]
```

Detects database performance anti-patterns including N+1 queries and ORM inefficiencies.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--format, -f` | text | Output format: text, json, markdown |
| `--severity, -s` | low | Minimum severity to report |
| `--exclude, -x` | - | Additional patterns to exclude |

**Detected ORMs**: Django ORM, SQLAlchemy, Peewee, Tortoise ORM, Prisma

**Detected Issues**: N+1 queries, missing indexes, full table scans, excessive queries, unoptimized joins

**Example**:
```bash
heimdall performance database ./src --format=markdown
```

---

### cache - Cache Analysis

```bash
heimdall performance cache <path> [options]
```

Identifies caching issues and opportunities.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--format, -f` | text | Output format: text, json, markdown |
| `--severity, -s` | low | Minimum severity to report |
| `--exclude, -x` | - | Additional patterns to exclude |

**Detected Systems**: Redis, Memcached, Python functools, Django Cache, Flask-Caching, Browser Storage, IndexedDB

**Detected Issues**: Missing cache opportunities, stale cache (no TTL), inefficient keys, cache stampede, over-caching

**Example**:
```bash
heimdall performance cache ./src --format=json
```

---

## Audit Command

### audit - Full Codebase Audit

```bash
heimdall audit <path> [options]
```

Runs quality, security, and performance analysis in a single scan.

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--format, -f` | text | Output format: text, json, markdown |
| `--severity, -s` | low | Minimum severity to report |
| `--exclude, -x` | - | Additional patterns to exclude |

**Example**:
```bash
heimdall audit ./src --format=json --severity=medium
```

---

## Output Formats

### Text (Default)

Human-readable console output with colors and formatting:

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

============================================================
RESULT: FAIL
============================================================
```

### JSON

Machine-readable JSON output for integration:

```json
{
  "scan_path": "./src",
  "scanned_at": "2024-01-15T10:30:00",
  "security_score": 65.0,
  "total_issues": 12,
  "critical_issues": 1,
  "high_issues": 4,
  "findings": [...]
}
```

### Markdown

Documentation-friendly markdown output:

```markdown
# Heimdall Security Report

**Scan Path**: ./src
**Security Score**: 65.0/100

## Summary
| Severity | Count |
|----------|-------|
| Critical | 1 |
| High | 4 |
| Medium | 5 |
| Low | 2 |
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success - scan passed (no critical/high issues) |
| 1 | Failed - critical or high issues found |
| 2 | Fatal error during analysis |

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `HEIMDALL_CONFIG` | Path to configuration file |
| `HEIMDALL_OUTPUT_DIR` | Default output directory |
| `HEIMDALL_VERBOSE` | Enable verbose mode (1/0) |

---

## Configuration File

Create `.heimdall.yaml` in project root:

```yaml
quality:
  file_length:
    max_file_lines: 500
    max_function_lines: 50
  complexity:
    max_cyclomatic: 10
    max_cognitive: 15
  duplication:
    min_lines: 6
    similarity_threshold: 0.8
  smells:
    min_severity: low
  maintainability:
    language: python
    include_halstead: true

security:
  # Core analyzers
  scan_secrets: true
  scan_vulnerabilities: true
  scan_dependencies: true
  scan_crypto: true
  # Extended analyzers
  scan_access: true
  scan_auth: true
  scan_headers: true
  scan_tls: true
  scan_container: true
  scan_infra: true
  min_severity: low

performance:
  scan_memory: true
  scan_cpu: true
  scan_database: true
  scan_cache: true
  min_severity: low
  complexity_threshold: 10

exclude_patterns:
  - __pycache__
  - .git
  - venv
  - node_modules
  - migrations
  - test
  - tests

include_extensions:
  - .py
  - .js
  - .ts
```

---

## Common Use Cases

### CI/CD Integration

```bash
# Fail build on security issues
heimdall security scan ./src --severity=high
if [ $? -ne 0 ]; then
    echo "Security issues found!"
    exit 1
fi

# Generate JSON report for artifact
heimdall audit ./src --format=json > heimdall-report.json
```

### Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

heimdall security secrets . --severity=critical
if [ $? -ne 0 ]; then
    echo "Critical secrets detected! Aborting commit."
    exit 1
fi
```

### Batch Scanning

```bash
# Scan multiple directories
for dir in Ankh Iris Themis Athena; do
    echo "Scanning $dir..."
    heimdall security scan ./$dir --format=text > reports/security_$dir.txt
done
```
