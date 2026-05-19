# Asgard Testing Standards

## Overview

All Asgard tests live in `Asgard_Test/`. Tests are organised by package (`tests_Heimdall/`, `tests_Forseti/`, etc.) and then by level.

L4 (UI/E2E) and L9 (Chaos/Live) are not applicable to Asgard — it is a static-analysis library with no UI and no live infrastructure.

---

## Test Levels

| Level | Name | Scope | Dependencies | Speed |
|:------|:-----|:------|:-------------|:------|
| **L0** | Unit | Single function/class | All external deps mocked | Fast (<100ms/test) |
| **L1** | Integration | Single module end-to-end | Real scanners, temp files | Medium |
| **L2** | Cross-Package | Multiple Asgard packages together | Multiple scanners | Slower |
| **L3** | Contract | Public API schemas & model shapes | Pydantic validation | Fast |
| **L5** | Compliance | Security scanner detection quality | Known-bad code fixtures | Medium |
| **L8** | Performance | Scanner throughput & latency | Real files, `pytest-benchmark` | Slow |

---

## Folder Structure

```
Asgard_Test/
    conftest.py                    # Global fixtures
    tests_Heimdall/
        L0_Mocked/                 # Unit tests — all external calls mocked
        L1_Integration/            # Integration — real scan on temp files
        L3_Contract/               # Contract — Pydantic model shape assertions
        L5_Compliance/             # Compliance — known-bad code must be detected
        L8_Performance/            # Performance — benchmark scanner throughput
    tests_Forseti/
        L0_Mocked/
        L1_Integration/
        L3_Contract/
        L5_Compliance/
        L8_Performance/
    tests_Freya/
        L0_Mocked/
        L1_Integration/
        L3_Contract/
        L8_Performance/
    tests_Verdandi/
        L0_Mocked/
        L1_Integration/
        L3_Contract/
        L8_Performance/
    tests_Volundr/
        L0_Mocked/
        L3_Contract/
        L8_Performance/
    L2_CrossPackage/               # Cross-package integration tests
```

---

## L0: Unit Tests

### Purpose
Test individual functions and classes in complete isolation.

### Rules
- Mock **all** external calls (filesystem, subprocesses, other packages)
- One behaviour per test
- Target <100ms per test
- Use `tmp_path` pytest fixture for any file I/O

### Naming
```
test_<component>_<behaviour>[_when_<condition>].py
```

### Example
```python
class TestReDoSScanner:
    def test_nested_quantifiers_detected(self, tmp_path):
        (tmp_path / "vuln.py").write_text("re.compile(r'(a+)+')")
        report = ReDoSScanner().scan(ReDoSScanConfig(scan_path=tmp_path))
        assert report.total_findings > 0
```

---

## L1: Integration Tests

### Purpose
Run a full scan on real (temporary) files using real scanner logic. No mocks.

### Rules
- Write real files to `tmp_path`
- Call the top-level `.scan()` or `.analyze()` method
- Assert on report fields (`total_findings`, `violations`, `score`, etc.)
- No network calls, no external services

---

## L2: Cross-Package Tests

### Purpose
Verify that multiple Asgard packages work together correctly.

### Location
`Asgard_Test/L2_CrossPackage/`

### Example scenarios
- Heimdall security scan feeds into Volundr CI/CD gate
- Forseti contract validation combined with Heimdall dependency check

---

## L3: Contract Tests

### Purpose
Verify the public API surface — model field names, types, and required fields — so that breaking changes in Pydantic models are caught immediately.

### Rules
- Instantiate every public model with valid data and assert field presence
- Attempt instantiation with missing required fields and assert `ValidationError`
- No scanner logic needed — pure model shape tests

### Example
```python
from pydantic import ValidationError

class TestReDoSScanConfigContract:
    def test_requires_scan_path(self):
        with pytest.raises(ValidationError):
            ReDoSScanConfig()  # scan_path is required

    def test_accepts_valid_config(self, tmp_path):
        config = ReDoSScanConfig(scan_path=tmp_path)
        assert hasattr(config, "scan_path")
        assert hasattr(config, "severity_threshold")
```

---

## L5: Compliance Tests

### Purpose
Verify that security scanners actually catch real vulnerability patterns. These are the ground-truth detection tests — if L5 fails, the scanner is broken, not just slow.

### Rules
- Use a library of known-bad code fixtures (`Asgard_Test/tests_Heimdall/fixtures/`)
- Assert that CRITICAL and HIGH severity patterns are always detected
- Assert that known-safe code produces zero findings
- Cover every scanner category

### Location
`Asgard_Test/tests_Heimdall/L5_Compliance/`

---

## L8: Performance Tests

### Purpose
Measure and enforce scanner throughput and latency budgets.

### Tools
`pytest-benchmark` — run with `pytest --benchmark-only`

### Budgets

| Scanner type | Budget |
|---|---|
| Single-file scan | < 50ms |
| 100-file directory scan | < 2s |
| Architecture analysis | < 5s |

### Example
```python
class TestReDoSScannerPerformance:
    def test_single_file_scan_under_50ms(self, benchmark, tmp_path):
        (tmp_path / "code.py").write_text("x = 1\n" * 500)
        config = ReDoSScanConfig(scan_path=tmp_path)
        scanner = ReDoSScanner()
        result = benchmark(scanner.scan, config)
        assert result is not None
```

---

## Coverage Requirements

| Scope | Minimum |
|---|---|
| L0 per scanner/service | 3 tests minimum (instantiation, clean, bad) |
| L3 per public model | 2 tests minimum (valid, invalid) |
| L5 per security category | 1 known-bad detection test |
| L8 per scanner | 1 benchmark test |

---

## Running Tests

```bash
# Full suite
pytest Asgard_Test/ -v

# Specific level
pytest Asgard_Test/tests_Heimdall/L0_Mocked/ -v
pytest Asgard_Test/tests_Heimdall/L5_Compliance/ -v

# Performance only
pytest Asgard_Test/ --benchmark-only -v

# Exclude performance (fast run)
pytest Asgard_Test/ --ignore=Asgard_Test/tests_Heimdall/L8_Performance/ -v
```
