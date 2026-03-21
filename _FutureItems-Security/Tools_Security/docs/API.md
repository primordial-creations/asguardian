# Security Tools API Documentation

## Overview

The Security Tools API provides a programmatic interface for running security scans with structured JSON/SARIF output, ideal for CI/CD integration.

## Installation

```bash
cd security-tools
pip install -r requirements.txt  # if applicable
```

## API Usage

### Python API

```python
from security_api import SecurityAPI

api = SecurityAPI()

# Run a single scan
report = api.scan('sqli', '/path/to/code')

# Access results
print(f"Found {report.total_issues} issues")
for issue in report.issues:
    print(f"[{issue['severity']}] {issue['description']}")

# Get JSON output
json_output = api.to_json(report)

# Get SARIF output for GitHub
sarif_output = api.to_sarif(report)
```

### Running Multiple Scans

```python
# Run all available scans
results = api.scan_all('/path/to/code')

# Run specific scans
results = api.scan_all('/path/to/code', tools=['sqli', 'xss', 'secrets'])

for tool, report in results.items():
    print(f"{tool}: {report.total_issues} issues")
```

## Command Line Usage

### Basic Scanning

```bash
# Run a specific scanner with JSON output
python security_api.py sqli /path/to/code

# Run all scanners
python security_api.py all /path/to/code

# Output to file
python security_api.py xss /path/to/code -o results.json
```

### SARIF Output for GitHub

```bash
# Generate SARIF for GitHub Code Scanning
python security_api.py sqli /path/to/code -f sarif -o results.sarif
```

### List Available Tools

```bash
python security_api.py --list
```

## Available Tools

| Tool ID | Description |
|---------|-------------|
| `sqli` | SQL injection vulnerabilities |
| `xss` | Cross-site scripting |
| `secrets` | Exposed secrets and API keys |
| `cmdi` | Command injection |
| `sensitive` | PII and sensitive data exposure |
| `redos` | Regex denial of service |
| `misconfig` | Security misconfigurations |
| `validation` | Input validation issues |
| `disclosure` | Information disclosure |
| `race` | Race conditions and TOCTOU |
| `api` | REST/GraphQL API security |
| `frontend` | Frontend-specific vulnerabilities |
| `traversal` | Path traversal |
| `ssrf` | SSRF and XXE |
| `deserial` | Insecure deserialization |
| `auth` | Authentication issues |
| `malware` | Malware patterns |
| `backdoor` | Backdoor detection |
| `exfil` | Data exfiltration patterns |
| `crypto` | Weak cryptography |
| `git` | Git repository security |

## Output Formats

### JSON Format

```json
{
  "tool": "sqli",
  "target": "/path/to/code",
  "timestamp": "2024-01-15T10:30:00",
  "duration_ms": 1234,
  "total_issues": 5,
  "by_severity": {
    "CRITICAL": 2,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 0
  },
  "issues": [
    {
      "tool": "sqli",
      "file_path": "app/db.py",
      "line_number": 42,
      "severity": "CRITICAL",
      "issue_type": "string_concat_sql",
      "description": "SQL query built with string concatenation",
      "recommendation": "Use parameterized queries"
    }
  ]
}
```

### SARIF Format

The SARIF output is compatible with GitHub Code Scanning. Upload it using:

```yaml
- uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: results.sarif
```

## Data Contracts

### ScanResult

```python
@dataclass
class ScanResult:
    tool: str           # Tool identifier
    file_path: str      # Affected file
    line_number: int    # Line number
    severity: str       # CRITICAL, HIGH, MEDIUM, LOW
    issue_type: str     # Specific vulnerability type
    description: str    # Human-readable description
    recommendation: str # How to fix
    code_snippet: str   # Optional code context
```

### ScanReport

```python
@dataclass
class ScanReport:
    tool: str                    # Tool identifier
    target: str                  # Scanned path
    timestamp: str               # ISO timestamp
    duration_ms: int             # Scan duration
    total_issues: int            # Total findings
    by_severity: Dict[str, int]  # Count by severity
    issues: List[Dict]           # All findings
```

## Severity Levels

| Level | Score | Description |
|-------|-------|-------------|
| CRITICAL | 9.0 | Immediate exploitation risk |
| HIGH | 7.0 | Significant security risk |
| MEDIUM | 5.0 | Moderate security concern |
| LOW | 3.0 | Minor issue or best practice |

## CI/CD Integration

### Exit Codes

- `0`: No critical or high issues
- `1`: High severity issues found
- `2`: Critical severity issues found

### Example Pipeline

```yaml
security-scan:
  script:
    - python security_api.py all . -f sarif -o results.sarif
    - |
      CRITICAL=$(python -c "
        import json
        with open('results.sarif') as f:
          sarif = json.load(f)
        results = sarif['runs'][0]['results']
        critical = sum(1 for r in results if r['level'] == 'error')
        print(critical)
      ")
      if [ "$CRITICAL" -gt 0 ]; then
        echo "Found $CRITICAL critical issues"
        exit 1
      fi
  artifacts:
    reports:
      sast: results.sarif
```

## Filtering Results

### By Severity

```bash
python security_api.py sqli . --min-severity HIGH
```

### By Tool

```bash
python security_api.py all . --tools sqli,xss,secrets
```

## Error Handling

```python
from security_api import SecurityAPI

api = SecurityAPI()

try:
    report = api.scan('invalid_tool', '/path')
except ValueError as e:
    print(f"Invalid tool: {e}")
except FileNotFoundError as e:
    print(f"Scanner not found: {e}")
```

## Performance Tips

1. **Scan specific directories**: Target only source code directories
2. **Use tool subsets**: Run only relevant scanners
3. **Parallel execution**: Run multiple scans concurrently
4. **Cache results**: Store reports for comparison

## Extending the API

### Adding a Custom Scanner

1. Create scanner following the standard pattern
2. Add to `TOOLS` dictionary in `SecurityAPI`
3. Ensure scanner has `scan_file` and `scan_directory` methods
4. Return list of dataclass issues with standard fields
