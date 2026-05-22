# Heimdall Security - Advanced Modules

## Overview

Three advanced security submodules extend the core Security module with taint analysis, security hotspot detection, OWASP/CWE compliance reporting, and SBOM generation.

---

## 1. Taint Analysis

**Location:** `Asgard/Heimdall/Security/TaintAnalysis/`

Performs intra-function and cross-function taint analysis using Python's AST module to track untrusted data from **sources** to dangerous **sinks**.

### How It Works

1. The analyser walks each Python file's AST, identifying assignments from known source patterns.
2. Tainted variables are tracked through the function body; any variable derived from a tainted source is itself tainted.
3. When a tainted variable reaches a known sink, a `TaintFlow` is recorded.
4. Cross-function tracking follows return values and function call arguments.

### Source Types

| SourceType | Examples |
|-----------|---------|
| `HTTP_PARAMETER` | `request.args`, `request.form`, `request.json`, FastAPI path/query params |
| `COOKIE` | `request.cookies` |
| `HEADER` | `request.headers` |
| `ENV_VAR` | `os.environ`, `os.getenv` |
| `USER_INPUT` | `input()` |
| `COMMAND_LINE_ARG` | `sys.argv`, `argparse` results |
| `FILE_READ` | `open()` return values |

### Sink Types

| SinkType | Examples |
|---------|---------|
| `SQL_QUERY` | `cursor.execute()`, `session.execute()`, raw SQL string construction |
| `SHELL_COMMAND` | `os.system()`, `subprocess.run()`, `subprocess.Popen()` |
| `FILE_WRITE` | `open(path, 'w')`, `Path.write_text()` |
| `HTML_OUTPUT` | Template rendering with user data |
| `EVAL` | `eval()`, `exec()`, `compile()` |
| `HTTP_REQUEST` | `requests.get()`, `httpx.get()` (SSRF) |

### Programmatic Usage

```python
from Asgard.Heimdall.Security.TaintAnalysis import TaintAnalyzer
from Asgard.Heimdall.Security.TaintAnalysis.models import TaintConfig

config = TaintConfig(
    scan_path="./src",
    include_extensions=[".py"],
    track_cross_function=True,
    framework="fastapi",        # Source-aware: fastapi, django, flask
)

analyzer = TaintAnalyzer(config)
report = analyzer.analyze()

for flow in report.taint_flows:
    print(f"{flow.source_type} -> {flow.sink_type} in {flow.file_path}:{flow.sink_line}")
    for step in flow.steps:
        print(f"  Line {step.line}: {step.variable} = {step.expression}")
```

### CLI Usage

```bash
python -m Heimdall security taint <path>
python -m Heimdall security taint <path> --framework=django
python -m Heimdall security taint <path> --format=json
```

---

## 2. Security Hotspots

**Location:** `Asgard/Heimdall/Security/Hotspots/`

Detects security-sensitive code patterns that require manual security review. Hotspots are distinct from confirmed vulnerabilities; they indicate areas where security decisions need conscious validation.

### Detected Categories

| Category | Description | Priority |
|----------|-------------|---------|
| `COOKIE_CONFIGURATION` | Missing `secure=True`, `httponly=True` | HIGH |
| `CRYPTOGRAPHIC_CODE` | Any use of `hashlib`, `cryptography`, `hmac` | MEDIUM |
| `DYNAMIC_CODE_EXECUTION` | `eval()`, `exec()`, `compile()`, `__import__()` | HIGH |
| `REGEX_DOS` | Nested quantifier patterns susceptible to ReDoS | MEDIUM |
| `XML_EXTERNAL_ENTITY` | XML parsing without explicit XXE disabling | HIGH |
| `INSECURE_DESERIALIZATION` | `pickle.loads()`, `yaml.load()` without SafeLoader | HIGH |
| `SSRF` | HTTP requests with potentially user-supplied URLs | HIGH |
| `INSECURE_RANDOM` | `random` module used for security-sensitive operations | MEDIUM |
| `PERMISSION_CHECKS` | `os.chmod()`, `os.access()` — verify intended permissions | LOW |
| `HTTP_WITHOUT_TLS_VERIFICATION` | `verify=False` in requests calls | HIGH |

### Review Workflow

Each hotspot has a `ReviewStatus`:
- `TO_REVIEW` — default; needs manual assessment
- `REVIEWED_SAFE` — reviewed and confirmed as safe
- `REVIEWED_FIXED` — reviewed and a fix was applied

### Programmatic Usage

```python
from Asgard.Heimdall.Security.Hotspots import HotspotDetector
from Asgard.Heimdall.Security.Hotspots.models import HotspotConfig

detector = HotspotDetector()
report = detector.detect(HotspotConfig(scan_path="./src"))

for hotspot in report.hotspots:
    print(f"[{hotspot.review_priority}] {hotspot.category} at {hotspot.file_path}:{hotspot.line}")
    print(f"  {hotspot.description}")
    print(f"  Suggested review: {hotspot.review_guidance}")
```

### CLI Usage

```bash
python -m Heimdall security hotspots <path>
python -m Heimdall security hotspots <path> --priority=high
```

---

## 3. OWASP / CWE Compliance Reporting

**Location:** `Asgard/Heimdall/Security/Compliance/`

Maps Heimdall security findings from existing reports to OWASP Top 10 (2021) and CWE Top 25 (2024) categories and produces compliance grade reports.

### Compliance Grades

| Grade | Criteria |
|-------|---------|
| A | Zero findings in this category |
| B | 1-2 LOW severity findings only |
| C | Any MEDIUM findings, or 3+ LOW findings |
| D | Any HIGH findings |
| F | Any CRITICAL findings |

### OWASP Top 10 (2021) Mapping

| Category | Code | Heimdall Rules Mapped |
|----------|------|-----------------------|
| Broken Access Control | A01 | `path_traversal`, `open_redirect`, `improper_input_validation` |
| Cryptographic Failures | A02 | `insecure_crypto`, `hardcoded_secret`, `insecure_random`, `weak_hash` |
| Injection | A03 | `sql_injection`, `command_injection`, `xss`, `template_injection` |
| Insecure Design | A04 | Architecture-level findings |
| Security Misconfiguration | A05 | Container/infrastructure findings |
| Vulnerable Components | A06 | Dependency vulnerability findings |
| Auth & Access Failures | A07 | `missing_auth`, cookie/session issues |
| Software & Data Integrity | A08 | `insecure_deserialization` |
| Logging & Monitoring Failures | A09 | Logging gaps |
| SSRF | A10 | `ssrf` |

### Programmatic Usage

```python
from Asgard.Heimdall.Security.Compliance import ComplianceReporter
from Asgard.Heimdall.Security.Compliance.models import ComplianceConfig

reporter = ComplianceReporter()

# OWASP Top 10 report
owasp_report = reporter.generate_owasp_report(
    security_report=security_report,
    vulnerability_report=vuln_report,
    secrets_report=secrets_report,
    crypto_report=crypto_report,
    dependency_report=dep_report,
)

for category in owasp_report.categories:
    print(f"{category.code} {category.name}: {category.grade} ({category.findings_count} findings)")

# CWE Top 25 report
cwe_report = reporter.generate_cwe_report(security_report=security_report)
for cwe in cwe_report.categories:
    print(f"CWE-{cwe.cwe_id} {cwe.name}: {cwe.grade}")

# Overall compliance summary
print(f"OWASP Overall: {owasp_report.overall_grade}")
print(f"CWE Overall: {cwe_report.overall_grade}")
```

### CLI Usage

```bash
python -m Heimdall security compliance <path>         # Both OWASP and CWE
python -m Heimdall security compliance <path> --standard=owasp
python -m Heimdall security compliance <path> --standard=cwe
python -m Heimdall security compliance <path> --format=json
```

---

## 4. SBOM Generation

**Location:** `Asgard/Heimdall/Dependencies/services/sbom_generator.py`

Generates Software Bill of Materials documents from project dependency declaration files.

### Supported Formats

- **SPDX 2.3** (JSON)
- **CycloneDX 1.4** (JSON)

### Supported Dependency Sources

- `requirements.txt` / `requirements-*.txt`
- `pyproject.toml` (PEP 517/518 `[project.dependencies]` and `[tool.poetry.dependencies]`)
- Installed package metadata via `importlib.metadata`

### Programmatic Usage

```python
from Asgard.Heimdall.Dependencies.services.sbom_generator import SBOMGenerator
from Asgard.Heimdall.Dependencies.models.sbom_models import SBOMConfig, SBOMFormat

generator = SBOMGenerator(config=SBOMConfig(output_format=SBOMFormat.CYCLONEDX))
sbom = generator.generate(scan_path="./src")

print(f"Components found: {len(sbom.components)}")
for component in sbom.components:
    print(f"  {component.name}=={component.version} (license: {component.license})")

# Export to JSON string
json_output = generator.to_json(sbom)
```

### CLI Usage

```bash
python -m Heimdall deps sbom <path>                      # CycloneDX (default)
python -m Heimdall deps sbom <path> --format=spdx
python -m Heimdall deps sbom <path> --output=sbom.json
```
