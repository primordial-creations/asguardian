# Asguardian

Named after the realm of the Norse gods, **Asguardian** is a comprehensive suite of development quality assurance tools for Python projects. It covers static analysis, security scanning, API validation, performance metrics, infrastructure generation, and more — all from a single package.

## Installation

```bash
pip install asguardian
```

Python 3.11 or higher is required.

The installed commands are `asguardian`, `asguardian-dashboard`, and
`asguardian-mcp`. The former documented names `asgard`, `asgard-dashboard`, and
`asgard-mcp` are compatibility aliases for the same entrypoints; their help uses
the canonical `asguardian` names. Module commands such as `heimdall` also remain
available. From a source checkout, run `python -m Asgard.cli --help`.

## Quick Start

### Static Analysis and Code Quality

```bash
# Analyse a project directory
asguardian heimdall quality analyze ./src

# Get letter ratings (A–E) for Maintainability, Reliability, and Security
asguardian heimdall ratings ./src

# Check quality gate (pass/fail against thresholds)
asguardian heimdall gate ./src

# Check for security vulnerabilities
asguardian heimdall security scan ./src

# View tracked issues with lifecycle states
asguardian heimdall issues ./src
```

### Security Scanning

```bash
# Versioned external-orchestrator scan (JSON Lines output)
asgard scan --contract-version hercules-l13/v1 --target ./src --output findings.jsonl

# Detect security hotspots requiring manual review
asguardian heimdall security hotspots ./src

# OWASP Top 10 and CWE Top 25 compliance report
asguardian heimdall security compliance ./src

# Taint analysis: source-to-sink injection tracking
asguardian heimdall security taint ./src
```

The root `scan` command is the supported Hercules executable boundary. Exit 0
means analysis completed and the final `HERCULES_SCAN:` record says either
`clean` or `findings`; scanner/domain failures exit 3 and do not write a new
result. Omitting `--contract-version` emits the transition-only `legacy-v0`
finding lines. Both installed aliases, `asgard` and `asguardian`, expose the
same command.

### API and Schema Validation

```bash
# Validate an OpenAPI specification
asguardian forseti openapi validate openapi.yaml

# Check for breaking changes between two specs
asguardian forseti contract check-compat old.yaml new.yaml

# Validate a GraphQL schema
asguardian forseti graphql validate schema.graphql
```

### Web and UI Testing

```bash
# Crawl a site and check for broken links
asguardian freya crawl http://localhost:3000

# Run image optimisation scan
asguardian freya images audit http://localhost:3000
```

### Performance Metrics

```bash
# Generate a performance report from a metrics file
asguardian verdandi report generate ./metrics.json

# Check SLO compliance
asguardian verdandi slo calculate ./metrics.json
```

### Infrastructure Generation

```bash
# Generate Kubernetes manifests
asguardian volundr kubernetes generate --name myapp --image myapp:latest

# Generate a Dockerfile
asguardian volundr docker dockerfile --name myapp --base python:3.12-slim

# Generate a GitHub Actions CI/CD pipeline
asguardian volundr cicd generate --name myapp --platform github_actions
```

Dockerfile generation requires an explicit base image; a `--lang` preset option
is not implemented.

## Web Dashboard

Asguardian includes a standalone web dashboard that displays your project's quality metrics, issues, and history in a browser.

### Launch the dashboard

```bash
# Start on the default port (8080)
asguardian-dashboard --path ./src

# Specify a custom port
asguardian-dashboard --path ./src --port 9090
```

Then open `http://localhost:8080` in your browser.

The dashboard provides three pages:

- **Overview** — quality gate status, A–E ratings (Maintainability, Reliability, Security), and issue summary
- **Issues** — filterable table of all tracked issues with severity and lifecycle status
- **History** — trend view of analysis snapshots over time

The `heimdall dashboard` command is an alias for `asguardian-dashboard`.

## MCP Server (AI Agent Integration)

Asguardian includes a JSON-RPC MCP server that exposes analysis results to AI coding assistants such as Claude Code, Cursor, and Windsurf.

### Start the MCP server

```bash
asguardian-mcp --path ./src
```

### Configure Claude Code

Add the following to your `.claude/mcp.json` (or Claude Code settings):

```json
{
  "mcpServers": {
    "asguardian": {
      "command": "asguardian-mcp",
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
asguardian heimdall profiles list

# Inspect the strict quality profile
asguardian heimdall profiles show "Asgard Way - Strict"
```

The CLI supports profile inspection and management. Passing a named profile
directly to `quality analyze` through `--profile` is not implemented and remains
an integration task.

Built-in profiles:

| Profile | Description |
|---|---|
| Asgard Way - Python | Balanced rule set for Python projects |
| Asgard Way - Strict | Stricter thresholds for production codebases |

## Quality Gates

```bash
# Evaluate the built-in "Asgard Way" gate
asguardian heimdall gate ./src

# Specify a custom gate configuration
asguardian heimdall gate ./src --gate my-gate.yaml
```

A gate returns `PASSED` or `FAILED` with a per-condition breakdown. Exit code is `0` for pass and `1` for failure, making it suitable for CI/CD pipelines.

## New Code Period

Identify new and modified files since a reference commit or date.

```bash
# Detect code changed since a git tag
asguardian heimdall new-code detect ./src --since-version v1.0.0

# Detect code changed since a chosen date
asguardian heimdall new-code detect ./src --since-date 2026-01-01
```

Use an explicit date, branch, or version reference. Relative `--days` filtering
and running quality metrics over only this detected change set remain integration
tasks; `new-code detect` reports the changed files and line count.

## SBOM Generation

Generate a Software Bill of Materials in industry-standard formats.

```bash
# SPDX 2.3 format
asguardian heimdall sbom ./src --format spdx

# CycloneDX 1.4 format
asguardian heimdall sbom ./src --format cyclonedx
```

## Auto CodeFix

Get template-based fix suggestions for common rule violations.

```bash
asguardian heimdall codefix ./src
```

## Language Support

| Language | Rules |
|---|---|
| Python | Complexity, duplication, smells, security, naming (PEP 8), documentation, taint analysis |
| JavaScript | no-eval, no-debugger, no-var, eqeqeq, no-console, complexity (12 rules) |
| TypeScript | All JS rules + no-explicit-any, no-any-cast, no-non-null-assertion, prefer-interface |
| Shell/Bash | eval injection, curl --insecure, hardcoded secrets, missing set -e/u (12 rules) |
| Rust | unsafe blocks, unwrap/expect, transmute, raw pointer deref, command injection, hardcoded credentials (8 pattern rules) |

Rust and Node also have toolchain-orchestrating analysers that run the ecosystem's own tools
instead of pattern rules -- see [Toolchain-Orchestrated Analysis](#toolchain-orchestrated-analysis)
below.

## Toolchain-Orchestrated Analysis

For Rust and Node, Heimdall orchestrates each ecosystem's own mature tools rather than
reimplementing their analysis in Python: `cargo clippy`, `cargo-audit`, ESLint, `npm audit`, and
`tsc`. Findings are normalised into the same rating/gate/issue-tracking model used everywhere
else in Heimdall, regardless of which tool produced them.

```bash
# Rust: cargo clippy lint diagnostics (requires cargo + clippy)
asguardian heimdall quality rust-clippy ./my-crate

# Rust: Cargo.lock vulnerability scan against the RustSec advisory database
# (requires the separate cargo-audit plugin: cargo install cargo-audit)
asguardian heimdall quality rust-audit ./my-crate

# Node: the project's own configured ESLint (requires an ESLint config)
asguardian heimdall quality node-lint ./frontend

# Node: package.json/package-lock.json vulnerability scan via npm audit
asguardian heimdall quality node-audit ./frontend

# Node: TypeScript compiler diagnostics (requires tsconfig.json)
asguardian heimdall quality node-typecheck ./frontend
```

Each of these requires the underlying tool to be installed. `rust-clippy`, `node-lint`, and
`node-typecheck` require their tool (cargo, eslint, tsc); when it is missing, the command prints a
clear, actionable message (what to install and how) and exits non-zero -- it never crashes with a
raw traceback. Explicitly requesting any toolchain check, including `rust-audit` or `go-vuln`,
requires that scanner to run: a missing tool or configuration (no ESLint config,
tsconfig.json, Cargo.toml/Cargo.lock, package.json, or go.mod under the scanned path) produces
an incomplete-scan diagnostic and exits non-zero. Run only the checks applicable to your project.
The Python report retains `tools_unavailable` separately from `tool_failed` so callers can
distinguish missing prerequisites from execution errors. In every case, a tool that was invoked but crashed,
timed out, or produced output the analyser could not parse is a distinct, always-non-zero outcome
even if it happens to find zero issues -- that failure is never presented as a clean scan.

**Security note: these commands execute the scanned project's own toolchain.** Unlike Heimdall's
Python type-check orchestration (which runs mypy/Pyright from an isolated, empty working
directory with Asgard-owned config so a hostile tree's `pylintrc`/`mypy.ini` cannot run arbitrary
init-hooks), `cargo clippy`, `cargo-audit`, ESLint, and `tsc` are all invoked with the scanned
project directory as their working directory, because each needs its own `Cargo.toml`,
`eslint.config.*`/`.eslintrc.*`, or `tsconfig.json` to run at all. That means running any of these
five commands against an untrusted or unreviewed tree can execute that tree's own build scripts
(`build.rs`, package install/postinstall scripts under `npm audit`'s dependency resolution) and
plugin/loader configuration (a custom ESLint plugin, a `tsconfig.json` `extends` chain, a Cargo
build script) with the same privileges as the `asguardian` process itself. Only run these commands
against code you already trust, the same way you would before running `cargo build`, `npm
install`, or `tsc` directly in that tree.

## Python API

All modules can be used directly in Python code.

```python
from Asgard.Heimdall.Ratings.services.ratings_calculator import RatingsCalculator
from Asgard.Heimdall.QualityGate.services.quality_gate_evaluator import QualityGateEvaluator
from Asgard.Heimdall.Security.services.hotspot_detector import HotspotDetector
from Asgard.Heimdall.Security.services.taint_analyzer import TaintAnalyzer
from Asgard.Heimdall.Issues.services.issue_tracker import IssueTracker
from Asgard.Reporting.History import HistoryStore
from Asgard.Dashboard.services.data_collector import DataCollector
from Asgard.Forseti.OpenAPI.services import SpecValidatorService
from Asgard.Verdandi.Web.services import VitalsCalculator
from Asgard.Volundr.Kubernetes.services import ManifestGenerator
```

## CLI Reference

### Unified CLI (`asguardian`)

```
asguardian heimdall quality analyze <path>
asguardian heimdall ratings <path>
asguardian heimdall gate <path>
asguardian heimdall profiles list
asguardian heimdall history show <path>
asguardian heimdall new-code detect <path>
asguardian heimdall issues <path>
asguardian heimdall sbom <path>
asguardian heimdall codefix <path>
asguardian heimdall mcp-server
asguardian heimdall dashboard

asguardian heimdall quality documentation <path>
asguardian heimdall quality naming <path>
asguardian heimdall quality bugs <path>
asguardian heimdall quality javascript <path>
asguardian heimdall quality typescript <path>
asguardian heimdall quality shell <path>
asguardian heimdall quality rust <path>
asguardian heimdall quality rust-clippy <path>
asguardian heimdall quality rust-audit <path>
asguardian heimdall quality node-lint <path>
asguardian heimdall quality node-audit <path>
asguardian heimdall quality node-typecheck <path>

asguardian heimdall security hotspots <path>
asguardian heimdall security compliance <path>
asguardian heimdall security taint <path>

asguardian freya crawl <url>
asguardian freya images audit <url>

asguardian forseti openapi validate <spec>
asguardian forseti contract check-compat <old> <new>

asguardian verdandi report generate <metrics>
asguardian verdandi slo calculate <metrics>

asguardian volundr kubernetes generate --name <name> --image <image>
asguardian volundr docker dockerfile --name <name> --base <base-image>
asguardian volundr cicd generate --name <name> --platform github_actions
```

### Standalone entry points

```
heimdall       Individual Heimdall CLI
freya          Individual Freya CLI
forseti        Individual Forseti CLI
verdandi       Individual Verdandi CLI
volundr        Individual Volundr CLI
asguardian-mcp     Start the MCP JSON-RPC server
asguardian-dashboard   Start the web dashboard
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

Proprietary. All rights reserved. Commercial use requires a separate, written licensing agreement with the owner. See [LICENSE](LICENSE) for details.
