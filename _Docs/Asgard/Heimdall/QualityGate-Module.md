# Heimdall Quality Gate Module

## Overview

The Quality Gate module evaluates aggregate analysis results against configurable pass/fail thresholds to produce a gate status used for CI/CD pipeline gating. It is the primary mechanism for enforcing quality standards across the codebase.

## Concepts

A **Quality Gate** is a named collection of conditions. Each condition tests one metric against a threshold using a comparison operator. If any condition marked `error_on_fail=True` fails, the gate status is `FAILED`. Conditions with `error_on_fail=False` produce a `WARNING` status only.

## Built-in Gate: "Asgard Way"

The default gate mirrors SonarQube's recommended defaults:

| Condition | Threshold | Blocks |
|-----------|-----------|--------|
| Security Rating | B or better | Yes |
| Reliability Rating | C or better | Yes |
| Maintainability Rating | C or better | Yes |
| Critical Vulnerabilities | 0 | Yes |
| Code Duplication | <= 3% | No (warning) |
| Comment Density | >= 10% | No (warning) |
| API Documentation Coverage | >= 70% | No (warning) |

## Programmatic Usage

```python
from Asgard.Heimdall.QualityGate import QualityGateEvaluator
from Asgard.Heimdall.QualityGate.models import (
    GateCondition,
    GateOperator,
    GateStatus,
    MetricType,
    QualityGate,
    QualityGateConfig,
)

evaluator = QualityGateEvaluator()

# Evaluate using the built-in "Asgard Way" gate
result = evaluator.evaluate_asgard_way(
    debt_report=debt_report,
    security_report=security_report,
    quality_report=quality_report,
    ratings=ratings,
)

print(f"Gate status: {result.status}")       # PASSED / FAILED / WARNING
print(f"Failed conditions: {result.failed_conditions}")
print(f"Warning conditions: {result.warning_conditions}")

# Evaluate a custom gate
custom_gate = QualityGate(
    name="Strict",
    conditions=[
        GateCondition(
            metric=MetricType.SECURITY_RATING,
            operator=GateOperator.EQUALS,
            threshold="A",
            error_on_fail=True,
            description="Security rating must be A",
        ),
        GateCondition(
            metric=MetricType.DUPLICATION_PERCENTAGE,
            operator=GateOperator.LESS_THAN_OR_EQUAL,
            threshold=1.0,
            error_on_fail=True,
            description="Duplication must be <= 1%",
        ),
    ],
)
result = evaluator.evaluate(custom_gate, metrics_dict)
```

## Metric Types

| MetricType | Description |
|------------|-------------|
| `SECURITY_RATING` | Letter rating A-E from Ratings module |
| `RELIABILITY_RATING` | Letter rating A-E from Ratings module |
| `MAINTAINABILITY_RATING` | Letter rating A-E from Ratings module |
| `DUPLICATION_PERCENTAGE` | Duplicate code percentage (float) |
| `COMMENT_DENSITY` | Comment lines / total lines percentage (float) |
| `API_DOCUMENTATION_COVERAGE` | Documented public APIs percentage (float) |
| `CRITICAL_VULNERABILITIES` | Count of critical severity vulnerabilities (int) |
| `HIGH_VULNERABILITIES` | Count of high severity vulnerabilities (int) |
| `NAMING_VIOLATIONS` | Count of naming convention violations (int) |

## Gate Operators

`LESS_THAN`, `LESS_THAN_OR_EQUAL`, `GREATER_THAN`, `GREATER_THAN_OR_EQUAL`, `EQUALS`, `NOT_EQUALS`

Letter ratings (A-E) are compared ordinally: A=1 (best), E=5 (worst). So `LESS_THAN_OR_EQUAL B` means A or B.

## Gate Status Values

| Status | Meaning |
|--------|---------|
| `PASSED` | All conditions satisfied |
| `FAILED` | One or more error conditions failed |
| `WARNING` | All error conditions passed, but warning conditions failed |
| `NOT_COMPUTED` | Insufficient data to evaluate |

## CLI Usage

```bash
python -m Heimdall gate evaluate <path>            # Evaluate Asgard Way gate
python -m Heimdall gate evaluate <path> --gate=Strict  # Named gate
python -m Heimdall gate list                       # List available gates
python -m Heimdall gate show <name>                # Show gate conditions
```
