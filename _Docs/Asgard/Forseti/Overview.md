# Forseti - API and Schema Specification Tools

Named after the Norse god of justice and reconciliation who presides over contracts and agreements.

## Overview

Forseti is a comprehensive toolkit for API and schema specification management in the GAIA ecosystem. It provides tools for generating, validating, and managing API contracts, schemas, and specifications.

## Purpose

Forseti addresses the following needs:

1. **API Contract Management**: Define, validate, and version API contracts
2. **Schema Validation**: Validate data against JSON Schemas
3. **Specification Generation**: Generate OpenAPI specs from code
4. **Compatibility Checking**: Detect breaking changes between API versions
5. **Database Schema Analysis**: Analyze and diff database schemas
6. **GraphQL Schema Management**: Validate and generate GraphQL schemas

## Modules

### OpenAPI Module
Tools for working with OpenAPI/Swagger specifications:
- Specification validation
- Specification generation from FastAPI code
- Version conversion (2.0, 3.0, 3.1)
- Specification comparison and diffing

### GraphQL Module
Tools for working with GraphQL schemas:
- Schema validation (SDL syntax)
- Schema generation from Pydantic models
- Endpoint introspection
- Schema merging

### Database Module
Tools for database schema management:
- Schema extraction from SQL files
- Schema comparison and diffing
- Migration script generation
- Multi-dialect support (MySQL, PostgreSQL, SQLite)

### Contracts Module
API contract testing and compatibility tools:
- Implementation validation against contracts
- Backward compatibility checking
- Breaking change detection with mitigations
- Changelog generation

### JSONSchema Module
Tools for working with JSON Schemas:
- Data validation against schemas
- Schema generation from Python types
- Schema inference from sample data
- TypeScript interface generation

## Installation

```bash
# Install core package
pip install Forseti

# Install with optional dependencies
pip install Forseti[openapi]    # OpenAPI tools
pip install Forseti[graphql]    # GraphQL tools
pip install Forseti[database]   # Database tools
pip install Forseti[all]        # All dependencies
```

## Quick Start

### CLI Usage

```bash
# Validate OpenAPI specification
forseti openapi validate api.yaml

# Check API compatibility
forseti contract check-compat old.yaml new.yaml

# Validate data against JSON Schema
forseti jsonschema validate schema.json data.json

# Infer schema from sample data
forseti jsonschema infer samples.json --output schema.json
```

### Python API

```python
from Forseti.OpenAPI import SpecValidatorService
from Forseti.JSONSchema import SchemaValidatorService
from Forseti.Contracts import CompatibilityCheckerService

# Validate OpenAPI spec
validator = SpecValidatorService()
result = validator.validate_file("api.yaml")
print(f"Valid: {result.is_valid}")

# Validate data against schema
schema_validator = SchemaValidatorService()
result = schema_validator.validate(data, schema)

# Check API compatibility
compat_checker = CompatibilityCheckerService()
result = compat_checker.check("v1.yaml", "v2.yaml")
if not result.is_compatible:
    for change in result.breaking_changes:
        print(f"Breaking: {change.message}")
```

## Architecture

Forseti follows the standard Asgard package structure:

```
Forseti/
├── __init__.py
├── __main__.py
├── cli.py
├── OpenAPI/
│   ├── models/
│   ├── services/
│   └── utilities/
├── GraphQL/
│   ├── models/
│   ├── services/
│   └── utilities/
├── Database/
│   ├── models/
│   ├── services/
│   └── utilities/
├── Contracts/
│   ├── models/
│   ├── services/
│   └── utilities/
└── JSONSchema/
    ├── models/
    ├── services/
    └── utilities/
```

Each module follows the three-tier pattern:
- **models/**: Pydantic data models
- **services/**: Business logic services
- **utilities/**: Helper functions

## Output Formats

All commands support multiple output formats:

- `--format text` (default): Human-readable output
- `--format json`: Machine-readable JSON
- `--format markdown`: Documentation-ready markdown

## Exit Codes

- `0`: Success / Valid / Compatible
- `1`: Validation errors or incompatibility detected
- `2`: Configuration or input errors

## Related Packages

- **Heimdall**: Code quality analysis
- **Freya**: Visual and accessibility testing
- **Volundr**: Infrastructure as Code tools
- **Verdandi**: Observability and monitoring
