# Forseti - CLI Reference

Complete command-line interface reference.

## Global Options

```bash
forseti [--version] [--format {text,json,markdown}] [--verbose] <command>
```

| Option | Description |
|--------|-------------|
| `--version` | Show version and exit |
| `--format` | Output format: text (default), json, markdown |
| `-v, --verbose` | Enable verbose output |

## OpenAPI Commands

### forseti openapi validate

Validate an OpenAPI specification.

```bash
forseti openapi validate <spec_file> [--strict]
```

| Argument | Description |
|----------|-------------|
| `spec_file` | Path to OpenAPI specification file |
| `--strict` | Enable strict validation mode |

**Example:**
```bash
forseti openapi validate api.yaml --strict
```

### forseti openapi generate

Generate OpenAPI specification from source code.

```bash
forseti openapi generate <source_path> [-o OUTPUT] [--title TITLE] [--version VERSION]
```

| Argument | Description |
|----------|-------------|
| `source_path` | Path to source code |
| `-o, --output` | Output file path |
| `--title` | API title |
| `--version` | API version |

**Example:**
```bash
forseti openapi generate ./app -o api.yaml --title "My API" --version "1.0.0"
```

### forseti openapi convert

Convert between OpenAPI specification versions.

```bash
forseti openapi convert <spec_file> --target-version {2.0,3.0,3.1} [-o OUTPUT]
```

| Argument | Description |
|----------|-------------|
| `spec_file` | Path to specification file |
| `--target-version` | Target OpenAPI version |
| `-o, --output` | Output file path |

**Example:**
```bash
forseti openapi convert swagger.json --target-version 3.1 -o openapi.yaml
```

### forseti openapi diff

Compare two OpenAPI specifications.

```bash
forseti openapi diff <spec1> <spec2>
```

| Argument | Description |
|----------|-------------|
| `spec1` | First specification file |
| `spec2` | Second specification file |

**Example:**
```bash
forseti openapi diff old.yaml new.yaml --format json
```

## GraphQL Commands

### forseti graphql validate

Validate a GraphQL schema.

```bash
forseti graphql validate <schema_file> [--strict]
```

| Argument | Description |
|----------|-------------|
| `schema_file` | Path to GraphQL schema file |
| `--strict` | Enable strict validation mode |

**Example:**
```bash
forseti graphql validate schema.graphql
```

### forseti graphql generate

Generate GraphQL schema from source.

```bash
forseti graphql generate <source_path> [-o OUTPUT]
```

### forseti graphql introspect

Introspect a GraphQL endpoint.

```bash
forseti graphql introspect <endpoint> [-o OUTPUT] [-H HEADER]
```

| Argument | Description |
|----------|-------------|
| `endpoint` | GraphQL endpoint URL |
| `-o, --output` | Output file path |
| `-H, --header` | HTTP headers (can be repeated) |

**Example:**
```bash
forseti graphql introspect https://api.example.com/graphql \
  -H "Authorization: Bearer token" \
  -o schema.graphql
```

## Database Commands

### forseti database analyze

Analyze database schema.

```bash
forseti database analyze <source> [-o OUTPUT]
```

| Argument | Description |
|----------|-------------|
| `source` | SQL file or connection string |
| `-o, --output` | Output file path |

**Example:**
```bash
forseti database analyze schema.sql -o analysis.json
```

### forseti database diff

Compare two database schemas.

```bash
forseti database diff <schema1> <schema2> [-o OUTPUT]
```

| Argument | Description |
|----------|-------------|
| `schema1` | First schema file |
| `schema2` | Second schema file |
| `-o, --output` | Output file path |

**Example:**
```bash
forseti database diff old.sql new.sql --format markdown
```

### forseti database migrate

Generate migration script from diff.

```bash
forseti database migrate <diff_file> [-o OUTPUT] [--dialect {mysql,postgresql,sqlite}]
```

| Argument | Description |
|----------|-------------|
| `diff_file` | Schema diff file |
| `-o, --output` | Output file path |
| `--dialect` | SQL dialect (default: mysql) |

## Contract Commands

### forseti contract validate

Validate implementation against contract.

```bash
forseti contract validate <contract_file> <implementation>
```

| Argument | Description |
|----------|-------------|
| `contract_file` | Contract/specification file |
| `implementation` | Implementation specification file |

**Example:**
```bash
forseti contract validate contract.yaml implementation.yaml
```

### forseti contract check-compat

Check backward compatibility between versions.

```bash
forseti contract check-compat <old_spec> <new_spec>
```

| Argument | Description |
|----------|-------------|
| `old_spec` | Old version specification |
| `new_spec` | New version specification |

**Example:**
```bash
forseti contract check-compat v1.yaml v2.yaml --format json
```

### forseti contract breaking-changes

Detect breaking changes between versions.

```bash
forseti contract breaking-changes <old_spec> <new_spec> [--version VERSION]
```

| Argument | Description |
|----------|-------------|
| `old_spec` | Old version specification |
| `new_spec` | New version specification |
| `--version` | Version string for changelog |

**Example:**
```bash
forseti contract breaking-changes v1.yaml v2.yaml --version 2.0.0
```

## JSONSchema Commands

### forseti jsonschema validate

Validate data against a JSON Schema.

```bash
forseti jsonschema validate <schema_file> <data_file> [--strict]
```

| Argument | Description |
|----------|-------------|
| `schema_file` | JSON Schema file |
| `data_file` | Data file to validate |
| `--strict` | Enable strict mode |

**Example:**
```bash
forseti jsonschema validate user.schema.json user.json --strict
```

### forseti jsonschema generate

Generate JSON Schema from type definitions.

```bash
forseti jsonschema generate <source> [-o OUTPUT] [--class CLASS_NAME]
```

| Argument | Description |
|----------|-------------|
| `source` | Python source file |
| `-o, --output` | Output file path |
| `--class` | Class name to generate from |

**Example:**
```bash
forseti jsonschema generate models.py --class User -o user.schema.json
```

### forseti jsonschema infer

Infer schema from sample data.

```bash
forseti jsonschema infer <samples_file> [-o OUTPUT] [--title TITLE]
```

| Argument | Description |
|----------|-------------|
| `samples_file` | File with sample data (JSON array) |
| `-o, --output` | Output file path |
| `--title` | Schema title |

**Example:**
```bash
forseti jsonschema infer samples.json -o schema.json --title "User Schema"
```

## Audit Command

### forseti audit

Run all applicable checks on a path.

```bash
forseti audit <path> [-o OUTPUT]
```

| Argument | Description |
|----------|-------------|
| `path` | Path to audit |
| `-o, --output` | Output report path |

**Example:**
```bash
forseti audit ./api --format markdown -o audit-report.md
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success / Valid / Compatible |
| 1 | Validation errors or incompatibility detected |
| 2 | Configuration or input errors |

## Examples

### CI/CD Pipeline

```bash
# Validate API specification
forseti openapi validate api.yaml --strict || exit 1

# Check for breaking changes
forseti contract check-compat main.yaml feature.yaml || {
    echo "Breaking changes detected!"
    forseti contract breaking-changes main.yaml feature.yaml --format markdown
    exit 1
}

# Validate all schemas
forseti audit ./schemas --format json > audit-results.json
```

### Development Workflow

```bash
# Generate OpenAPI from FastAPI app
forseti openapi generate ./app -o docs/api.yaml

# Infer schema from API responses
forseti jsonschema infer responses.json -o schemas/response.schema.json

# Validate before commit
forseti openapi validate docs/api.yaml && \
forseti jsonschema validate schemas/response.schema.json responses.json
```
