# Forseti - OpenAPI Module

Tools for working with OpenAPI/Swagger specifications.

## Overview

The OpenAPI module provides comprehensive tools for validating, generating, converting, and comparing OpenAPI specifications.

## Services

### SpecValidatorService

Validates OpenAPI specifications for correctness and completeness.

```python
from Forseti.OpenAPI import SpecValidatorService, OpenAPIConfig

# Create validator with configuration
config = OpenAPIConfig(strict_mode=True)
service = SpecValidatorService(config)

# Validate from file
result = service.validate_file("api.yaml")

# Validate from dictionary
spec = {"openapi": "3.0.0", ...}
result = service.validate(spec)

# Check result
if result.is_valid:
    print("Specification is valid")
else:
    for error in result.errors:
        print(f"Error at {error.path}: {error.message}")

# Generate report
report = service.generate_report(result, format="markdown")
```

**Configuration Options:**
- `strict_mode`: Enable strict validation rules
- `check_security`: Validate security definitions
- `check_examples`: Validate example values
- `validate_refs`: Validate $ref references

### SpecGeneratorService

Generates OpenAPI specifications from source code.

```python
from Forseti.OpenAPI import SpecGeneratorService

service = SpecGeneratorService()

# Generate from FastAPI app
spec = service.from_fastapi_app("/path/to/app")

# Save to file
service.save_spec(spec, "openapi.yaml")
```

### SpecConverterService

Converts between OpenAPI specification versions.

```python
from Forseti.OpenAPI import SpecConverterService

service = SpecConverterService()

# Convert from Swagger 2.0 to OpenAPI 3.0
result = service.convert("swagger.json", "3.0.0")

if result.success:
    spec = result.converted_spec
else:
    print(f"Conversion failed: {result.error}")

# Supported versions: 2.0, 3.0.0, 3.1.0
```

### SpecParserService

Parses and analyzes OpenAPI specifications.

```python
from Forseti.OpenAPI import SpecParserService

service = SpecParserService()

# Parse specification
spec = service.parse_file("api.yaml")

# Extract endpoints
endpoints = service.get_endpoints(spec)
for endpoint in endpoints:
    print(f"{endpoint.method} {endpoint.path}")

# Get schemas
schemas = service.get_schemas(spec)
```

## CLI Commands

```bash
# Validate specification
forseti openapi validate api.yaml
forseti openapi validate api.yaml --strict

# Generate specification
forseti openapi generate /path/to/app --output api.yaml

# Convert specification
forseti openapi convert swagger.json --target-version 3.1 --output openapi.yaml

# Compare specifications
forseti openapi diff old.yaml new.yaml
```

## Models

### OpenAPISpec

Represents an OpenAPI specification.

```python
from Forseti.OpenAPI import OpenAPISpec

spec = OpenAPISpec(
    openapi="3.0.0",
    info={"title": "My API", "version": "1.0.0"},
    paths={...}
)
```

### OpenAPIValidationResult

Result of specification validation.

```python
result.is_valid      # bool
result.errors        # list[OpenAPIValidationError]
result.warnings      # list[OpenAPIValidationError]
result.spec_path     # Optional path to spec file
result.error_count   # Number of errors
```

### OpenAPIValidationError

Represents a validation error.

```python
error.path       # JSON path to error location
error.message    # Error description
error.severity   # "error" or "warning"
error.rule       # Validation rule that failed
```

## Utilities

### load_spec_file

Load an OpenAPI specification from file (JSON or YAML).

```python
from Forseti.OpenAPI.utilities import load_spec_file

spec = load_spec_file("api.yaml")
```

### merge_specs

Merge multiple OpenAPI specifications.

```python
from Forseti.OpenAPI.utilities import merge_specs

merged = merge_specs([spec1, spec2, spec3])
```

### compare_specs

Compare two specifications and return differences.

```python
from Forseti.OpenAPI.utilities import compare_specs

diff = compare_specs("old.yaml", "new.yaml")
print(f"Added endpoints: {diff['added_paths']}")
print(f"Removed endpoints: {diff['removed_paths']}")
```

## Best Practices

1. **Always validate before deployment**: Run validation as part of CI/CD
2. **Use strict mode in production**: Catch potential issues early
3. **Version your specifications**: Use semantic versioning
4. **Document breaking changes**: Use the diff command to identify changes
5. **Keep specifications in sync**: Generate from code when possible
