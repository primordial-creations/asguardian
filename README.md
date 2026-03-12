# Asguardian

Named after the realm of the Norse gods, **Asguardian** is a comprehensive suite of development quality assurance tools for Python projects. It covers static analysis, security scanning, API validation, performance metrics, infrastructure generation, and more — all from a single package.

## Installation

```bash
pip install asguardian
```

Python 3.11 or higher is required.

## Quick Start

### Static Analysis and Code Quality

```bash
# Analyse a project directory
asgard heimdall analyze ./src

# Get letter ratings (A–E) for Maintainability, Reliability, and Security
asgard heimdall ratings ./src

# Check quality gate (pass/fail against thresholds)
asgard heimdall gate ./src

# Check for security vulnerabilities
asgard heimdall security scan ./src

# View tracked issues with lifecycle states
asgard heimdall issues ./src
```

### Security Scanning

```bash
# Detect security hotspots requiring manual review
asgard heimdall security hotspots ./src

# OWASP Top 10 and CWE Top 25 compliance report
asgard heimdall security compliance ./src

# Taint analysis: source-to-sink injection tracking
asgard heimdall security taint ./src
```

### API and Schema Validation

```bash
# Validate an OpenAPI specification
asgard forseti validate openapi.yaml

# Check for breaking changes between two specs
asgard forseti breaking-changes old.yaml new.yaml

# Validate a GraphQL schema
asgard forseti validate schema.graphql
```

### Web and UI Testing

```bash
# Crawl a site and check for broken links
asgard freya crawl http://localhost:3000

# Run image optimisation scan
asgard freya images http://localhost:3000
```

### Performance Metrics

```bash
# Calculate web vitals from a metrics file
asgard verdandi report ./metrics.json

# Check SLO compliance
asgard verdandi slo ./metrics.json
```

### Infrastructure Generation

```bash
# Generate Kubernetes manifests
asgard volundr generate kubernetes --name myapp --image myapp:latest

# Generate a Dockerfile
asgard volundr generate dockerfile --lang python

# Generate a GitHub Actions CI/CD pipeline
asgard volundr generate ci github
```

## Web Dashboard

Asguardian includes a standalone web dashboard that displays your project's quality metrics, issues, and history in a browser.

### Launch the dashboard

```bash
# Start on the default port (8080)
asgard-dashboard --path ./src

# Specify a custom port
asgard-dashboard --path ./src --port 9090
```

Then open `http://localhost:8080` in your browser.

The dashboard provides three pages:

- **Overview** — quality gate status, A–E ratings (Maintainability, Reliability, Security), and issue summary
- **Issues** — filterable table of all tracked issues with severity and lifecycle status
- **History** — trend view of analysis snapshots over time

The `heimdall dashboard` command is an alias for `asgard-dashboard`.

## MCP Server (AI Agent Integration)

Asguardian includes a JSON-RPC MCP server that exposes analysis results to AI coding assistants such as Claude Code, Cursor, and Windsurf.

### Start the MCP server

```bash
asgard-mcp --path ./src
```

### Configure Claude Code

Add the following to your `.claude/mcp.json` (or Claude Code settings):

```json
{
  "mcpServers": {
    "asguardian": {
      "command": "asgard-mcp",
      "args": ["--path", "/path/to/your/project"]
    }
  }
}
```

Once configured, your AI assistant can query quality ratings, issues, hotspots, and history directly.

## Quality Profiles

Asguardian ships with built-in quality profiles that group rules into named sets.

```bash
# List available profiles
asgard heimdall profiles list

# Run analysis using a specific profile
asgard heimdall analyze ./src --profile "Asgard Way - Strict"
```

Built-in profiles:

| Profile | Description |
|---|---|
| Asgard Way - Python | Balanced rule set for Python projects |
| Asgard Way - Strict | Stricter thresholds for production codebases |

## Quality Gates

```bash
# Evaluate the built-in "Asgard Way" gate
asgard heimdall gate ./src

# Specify a custom gate configuration
asgard heimdall gate ./src --gate my-gate.yaml
```

A gate returns `PASSED` or `FAILED` with a per-condition breakdown. Exit code is `0` for pass and `1` for failure, making it suitable for CI/CD pipelines.

## New Code Period

Track metrics specifically for code changed since a baseline commit or date.

```bash
# Metrics for code changed since a git tag
asgard heimdall new-code ./src --since v1.0.0

# Metrics for code changed in the last 30 days
asgard heimdall new-code ./src --days 30
```

## SBOM Generation

Generate a Software Bill of Materials in industry-standard formats.

```bash
# SPDX 2.3 format
asgard heimdall sbom ./src --format spdx

# CycloneDX 1.4 format
asgard heimdall sbom ./src --format cyclonedx
```

## Auto CodeFix

Get template-based fix suggestions for common rule violations.

```bash
asgard heimdall codefix ./src
```

## Language Support

| Language | Rules |
|---|---|
| Python | Complexity, duplication, smells, security, naming (PEP 8), documentation, taint analysis |
| JavaScript | no-eval, no-debugger, no-var, eqeqeq, no-console, complexity (12 rules) |
| TypeScript | All JS rules + no-explicit-any, no-any-cast, no-non-null-assertion, prefer-interface |
| Shell/Bash | eval injection, curl --insecure, hardcoded secrets, missing set -e/u (12 rules) |

## Python API

All modules can be used directly in Python code.

```python
from Asgard.Heimdall.Ratings.services.ratings_calculator import RatingsCalculator
from Asgard.Heimdall.QualityGate.services.quality_gate_evaluator import QualityGateEvaluator
from Asgard.Heimdall.Security.services.hotspot_detector import HotspotDetector
from Asgard.Heimdall.Security.services.taint_analyzer import TaintAnalyzer
from Asgard.Heimdall.Issues.services.issue_tracker import IssueTracker
from Asgard.Reporting.services.history_store import HistoryStore
from Asgard.Dashboard.services.data_collector import DataCollector
from Asgard.Forseti.OpenAPI.services import SpecValidatorService
from Asgard.Verdandi.Web.services import VitalsCalculator
from Asgard.Volundr.Kubernetes.services import ManifestGenerator
```

## CLI Reference

### Unified CLI (`asgard`)

```
asgard heimdall analyze <path>
asgard heimdall ratings <path>
asgard heimdall gate <path>
asgard heimdall profiles list
asgard heimdall history <path>
asgard heimdall new-code <path>
asgard heimdall issues <path>
asgard heimdall sbom <path>
asgard heimdall codefix <path>
asgard heimdall mcp-server
asgard heimdall dashboard

asgard heimdall quality documentation <path>
asgard heimdall quality naming <path>
asgard heimdall quality bugs <path>
asgard heimdall quality javascript <path>
asgard heimdall quality typescript <path>
asgard heimdall quality shell <path>

asgard heimdall security hotspots <path>
asgard heimdall security compliance <path>
asgard heimdall security taint <path>

asgard freya crawl <url>
asgard freya images <url>

asgard forseti validate <spec>
asgard forseti breaking-changes <old> <new>

asgard verdandi report <metrics>
asgard verdandi slo <metrics>

asgard volundr generate kubernetes
asgard volundr generate dockerfile
asgard volundr generate ci
```

### Standalone entry points

```
heimdall       Individual Heimdall CLI
freya          Individual Freya CLI
forseti        Individual Forseti CLI
verdandi       Individual Verdandi CLI
volundr        Individual Volundr CLI
asgard-mcp     Start the MCP JSON-RPC server
asgard-dashboard   Start the web dashboard
```

## Project Structure

```
Asgard/
├── Asgard/
│   ├── cli.py
│   ├── Heimdall/           # Static analysis, security, quality
│   ├── Freya/              # Visual and UI testing
│   ├── Forseti/            # API and schema validation
│   ├── Verdandi/           # Runtime performance metrics
│   ├── Volundr/            # Infrastructure generation
│   ├── Reporting/          # History store, PR decoration
│   ├── MCP/                # MCP JSON-RPC server
│   └── Dashboard/          # Web dashboard
├── Asgard_Test/            # Test suite (716 tests)
├── pyproject.toml
├── CHANGELOG.md
└── README.md
```

## License

MIT License — see [LICENSE](LICENSE) for details.
