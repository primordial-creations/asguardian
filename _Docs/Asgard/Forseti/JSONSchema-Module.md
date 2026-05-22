# Forseti - JSONSchema Module

Tools for working with JSON Schemas.

## Overview

The JSONSchema module provides comprehensive tools for validating data against schemas, generating schemas from Python types, and inferring schemas from sample data.

## Services

### SchemaValidatorService

Validates data against JSON Schemas with detailed error reporting.

```python
from Forseti.JSONSchema import SchemaValidatorService, JSONSchemaConfig

# Create validator with configuration
config = JSONSchemaConfig(
    strict_mode=True,
    check_formats=True,
    resolve_references=True
)
service = SchemaValidatorService(config)

# Define schema
schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "email": {"type": "string", "format": "email"},
        "age": {"type": "integer", "minimum": 0}
    },
    "required": ["name", "email"]
}

# Validate data
data = {"name": "John", "email": "john@example.com", "age": 30}
result = service.validate(data, schema)

if result.is_valid:
    print("Data is valid")
else:
    for error in result.errors:
        print(f"Error at {error.path}: {error.message}")
        print(f"  Constraint: {error.constraint}")
        print(f"  Expected: {error.expected}")

# Validate from files
result = service.validate_file("data.json", "schema.json")

# Generate report
report = service.generate_report(result, format="markdown")
```

**Supported Validations:**
- Type checking (string, number, integer, boolean, array, object, null)
- String: minLength, maxLength, pattern, format
- Number: minimum, maximum, exclusiveMinimum, exclusiveMaximum, multipleOf
- Array: minItems, maxItems, uniqueItems, items, contains
- Object: required, properties, additionalProperties, minProperties, maxProperties
- Combiners: allOf, anyOf, oneOf, not
- Const and enum

### SchemaGeneratorService

Generates JSON Schemas from Python types and Pydantic models.

```python
from Forseti.JSONSchema import SchemaGeneratorService, JSONSchemaConfig

config = JSONSchemaConfig(
    include_descriptions=True,
    include_examples=True,
    include_defaults=True
)
service = SchemaGeneratorService(config)

# Generate from Pydantic model
from pydantic import BaseModel

class User(BaseModel):
    id: str
    name: str
    email: str
    age: int | None = None

schema = service.from_pydantic(User, title="User Schema")

# Generate from dataclass
from dataclasses import dataclass

@dataclass
class Product:
    id: str
    name: str
    price: float

schema = service.from_dataclass(Product)

# Generate from type hint
schema = service.from_type(dict[str, list[int]])

# Generate from sample dictionary
sample = {"name": "John", "email": "john@example.com"}
schema = service.from_dict_sample(sample)

# Save schema
service.save_schema(schema, "user.schema.json")
```

### SchemaInferenceService

Infers JSON Schemas from sample data.

```python
from Forseti.JSONSchema import SchemaInferenceService, JSONSchemaConfig

config = JSONSchemaConfig(
    infer_formats=True,   # Detect email, date, uri, etc.
    infer_enums=True,     # Detect enum values
    enum_threshold=10     # Max unique values for enum
)
service = SchemaInferenceService(config)

# Infer from multiple samples
samples = [
    {"id": "123", "name": "John", "status": "active"},
    {"id": "456", "name": "Jane", "status": "inactive"},
    {"id": "789", "name": "Bob", "status": "pending"}
]

result = service.infer(samples, title="User Schema")

print(f"Inferred schema: {result.schema}")
print(f"Samples analyzed: {result.sample_count}")
print(f"Confidence: {result.confidence:.1%}")

if result.warnings:
    print("Warnings:")
    for warning in result.warnings:
        print(f"  - {warning}")

# Infer from file
result = service.infer_from_file("samples.json")

# Generate report
report = service.generate_report(result, format="text")
```

## CLI Commands

```bash
# Validate data against schema
forseti jsonschema validate schema.json data.json
forseti jsonschema validate schema.json data.json --strict

# Generate schema (from Python source)
forseti jsonschema generate models.py --class User --output user.schema.json

# Infer schema from samples
forseti jsonschema infer samples.json --output schema.json --title "My Schema"
```

## Models

### JSONSchemaConfig

Configuration for JSON Schema operations.

```python
from Forseti.JSONSchema import JSONSchemaConfig

config = JSONSchemaConfig(
    # Validation options
    strict_mode=True,           # Fail on additional properties
    check_formats=True,         # Validate format constraints
    resolve_references=True,    # Resolve $ref references

    # Generation options
    include_descriptions=True,  # Include descriptions
    include_examples=False,     # Include examples
    include_defaults=True,      # Include default values

    # Inference options
    infer_formats=True,         # Detect string formats
    infer_enums=True,           # Infer enum values
    enum_threshold=10,          # Max values for enum

    # Schema version
    schema_version="http://json-schema.org/draft-07/schema#"
)
```

### JSONSchemaValidationResult

Result of schema validation.

```python
result.is_valid           # bool
result.errors             # list[JSONSchemaValidationError]
result.schema_path        # Path to schema file
result.data_path          # Path to data file
result.validation_time_ms # Time taken
result.error_count        # Number of errors
```

### JSONSchemaValidationError

Represents a validation error.

```python
error.path         # JSON path to error location
error.message      # Error description
error.value        # Invalid value
error.schema_path  # Path in schema that failed
error.constraint   # Constraint that failed
error.expected     # Expected value or type
```

### JSONSchemaInferenceResult

Result of schema inference.

```python
result.schema        # Inferred JSON Schema dict
result.sample_count  # Number of samples analyzed
result.confidence    # Confidence score (0.0 to 1.0)
result.warnings      # Inference warnings
result.statistics    # Data statistics
```

## Utilities

### load_schema_file / save_schema_file

Load and save schema files (JSON or YAML).

```python
from Forseti.JSONSchema.utilities import load_schema_file, save_schema_file

schema = load_schema_file("schema.json")
save_schema_file("output.yaml", schema)
```

### merge_schemas

Merge multiple schemas.

```python
from Forseti.JSONSchema.utilities import merge_schemas

merged = merge_schemas(base_schema, overlay_schema, deep=True)
```

### resolve_refs

Resolve $ref references in a schema.

```python
from Forseti.JSONSchema.utilities import resolve_refs

resolved = resolve_refs(schema)
```

### validate_schema_syntax

Validate JSON Schema syntax.

```python
from Forseti.JSONSchema.utilities import validate_schema_syntax

errors = validate_schema_syntax(schema)
if errors:
    for error in errors:
        print(f"Syntax error: {error}")
```

### schema_to_typescript

Convert JSON Schema to TypeScript interface.

```python
from Forseti.JSONSchema.utilities import schema_to_typescript

typescript = schema_to_typescript(schema, name="User")
print(typescript)
# interface User {
#   id: string;
#   name: string;
#   email?: string;
# }
```

## Best Practices

1. **Use explicit schemas**: Don't rely on inference for production
2. **Validate at boundaries**: Check input at API boundaries
3. **Include format validation**: Use format constraints for emails, dates, etc.
4. **Document with descriptions**: Add descriptions to schema properties
5. **Version your schemas**: Track schema changes over time
6. **Test with edge cases**: Validate with minimal and maximal valid data
