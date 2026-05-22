# Forseti - Contracts Module

API contract testing and backward compatibility tools.

## Overview

The Contracts module provides tools for validating API implementations against contracts, checking backward compatibility between versions, and detecting breaking changes.

## Services

### ContractValidatorService

Validates that an API implementation matches its contract specification.

```python
from Forseti.Contracts import ContractValidatorService, ContractConfig

# Create validator
config = ContractConfig(
    check_parameters=True,
    check_request_body=True,
    check_response_body=True
)
service = ContractValidatorService(config)

# Validate implementation against contract
result = service.validate("contract.yaml", "implementation.yaml")

if result.is_valid:
    print("Implementation matches contract")
else:
    for error in result.errors:
        print(f"Error: {error.message}")
        print(f"  Path: {error.path}")

# Generate report
report = service.generate_report(result, format="text")
```

### CompatibilityCheckerService

Checks backward compatibility between API versions.

```python
from Forseti.Contracts import CompatibilityCheckerService

service = CompatibilityCheckerService()

# Check compatibility
result = service.check("v1.yaml", "v2.yaml")

print(f"Compatible: {result.is_compatible}")
print(f"Compatibility Level: {result.compatibility_level}")

# Review changes
print(f"Added endpoints: {result.added_endpoints}")
print(f"Removed endpoints: {result.removed_endpoints}")
print(f"Modified endpoints: {result.modified_endpoints}")

# Check breaking changes
for change in result.breaking_changes:
    print(f"Breaking: {change.message}")
    print(f"  Location: {change.location}")
    print(f"  Mitigation: {change.mitigation}")
```

### BreakingChangeDetectorService

Detects and categorizes breaking changes with detailed analysis.

```python
from Forseti.Contracts import BreakingChangeDetectorService

service = BreakingChangeDetectorService()

# Detect breaking changes
changes = service.detect("v1.yaml", "v2.yaml")

# Categorize by type
categorized = service.categorize_changes(changes)
for change_type, type_changes in categorized.items():
    print(f"\n{change_type}:")
    for change in type_changes:
        print(f"  - {change.message}")

# Get severity summary
summary = service.get_severity_summary(changes)
print(f"Errors: {summary['error']}")
print(f"Warnings: {summary['warning']}")

# Get suggested mitigations
mitigations = service.suggest_mitigations(changes)
for location, mitigation in mitigations.items():
    print(f"{location}: {mitigation}")

# Estimate impact
impact = service.estimate_impact(changes)
print(f"Overall Impact: {impact['overall_impact']}")
print(f"Recommendation: {impact['recommendation']}")

# Generate changelog
changelog = service.generate_changelog(changes, version="2.0.0")
print(changelog)
```

## CLI Commands

```bash
# Validate implementation against contract
forseti contract validate contract.yaml implementation.yaml

# Check backward compatibility
forseti contract check-compat old.yaml new.yaml

# Detect breaking changes with changelog
forseti contract breaking-changes old.yaml new.yaml --version 2.0.0
```

## Models

### ContractConfig

Configuration for contract validation.

```python
from Forseti.Contracts import ContractConfig

config = ContractConfig(
    check_parameters=True,       # Validate parameters
    check_request_body=True,     # Validate request bodies
    check_response_body=True,    # Validate response bodies
    allow_added_required=False,  # Don't allow new required fields
)
```

### CompatibilityResult

Result of compatibility check.

```python
result.is_compatible         # bool
result.compatibility_level   # CompatibilityLevel enum
result.source_version        # Old version path
result.target_version        # New version path
result.breaking_changes      # List of breaking changes
result.warnings             # List of warnings
result.added_endpoints      # New endpoints
result.removed_endpoints    # Removed endpoints
result.modified_endpoints   # Changed endpoints
result.check_time_ms        # Time taken
```

### BreakingChange

Represents a breaking change.

```python
change.change_type   # BreakingChangeType enum
change.path          # API path affected
change.location      # Specific location
change.message       # Description
change.old_value     # Previous value
change.new_value     # New value
change.severity      # "error" or "warning"
change.mitigation    # Suggested fix
```

### BreakingChangeType

Types of breaking changes:

- `REMOVED_ENDPOINT`: Endpoint removed
- `REMOVED_FIELD`: Response field removed
- `REMOVED_PARAMETER`: Parameter removed
- `CHANGED_TYPE`: Type changed
- `CHANGED_REQUIRED`: Required status changed
- `ADDED_REQUIRED_PARAMETER`: New required parameter
- `CHANGED_RESPONSE_TYPE`: Response type changed
- `REMOVED_RESPONSE`: Response status removed

### CompatibilityLevel

Levels of compatibility:

- `FULL`: Fully compatible, no changes
- `BACKWARD`: Backward compatible (additive changes only)
- `NONE`: Breaking changes present

## Best Practices

1. **Run compatibility checks in CI/CD**: Prevent accidental breaking changes
2. **Document all breaking changes**: Generate changelogs automatically
3. **Provide migration guides**: Use mitigation suggestions
4. **Version your API**: Follow semantic versioning
5. **Use deprecation periods**: Mark endpoints as deprecated before removal
6. **Test contract compliance**: Validate implementations regularly
