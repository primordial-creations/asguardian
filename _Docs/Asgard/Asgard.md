# 93 - Asgard
Quality assurance and development tooling package for GAIA.

[[GAIA Index|Back to GAIA Documentation]]

---
## Overview

Asgard (published as `asguardian` on PyPI) is a comprehensive suite of development quality assurance tools for Python projects. It covers static analysis, security scanning, API validation, performance metrics, infrastructure generation, and web/UI testing -- all from a single CLI.

**Requires**: Python 3.11+

```bash
pip install asguardian
```

---
## Sub-Tools

| Tool | Purpose | CLI Prefix |
|------|---------|------------|
| [[Asgard/Forseti/01-Overview\|Forseti]] | API and schema validation (OpenAPI, GraphQL, JSON Schema, AsyncAPI, Avro) | `asgard forseti` |
| [[Asgard/Freya/01-Overview\|Freya]] | Web and UI testing (crawling, accessibility, visual regression, responsive checks) | `asgard freya` |
| [[Asgard/Heimdall/01-Overview\|Heimdall]] | Static analysis, code quality, security scanning, quality gates | `asgard heimdall` |
| [[Asgard/Verdandi/01-Overview\|Verdandi]] | Performance metrics, SLO compliance, web vitals analysis | `asgard verdandi` |
| [[Asgard/Volundr/01-Overview\|Volundr]] | Infrastructure generation (Kubernetes, Terraform, Docker, CI/CD) | `asgard volundr` |

---
## Quick Start

### Static Analysis and Code Quality
```bash
asgard heimdall analyze ./src
asgard heimdall ratings ./src
asgard heimdall gate ./src
```

### Security Scanning
```bash
asgard heimdall security scan ./src
asgard heimdall security hotspots ./src
asgard heimdall security compliance ./src
```

### API Validation
```bash
asgard forseti validate openapi.yaml
asgard forseti breaking-changes old.yaml new.yaml
```

### Web Testing
```bash
asgard freya crawl http://localhost:3000
asgard freya images http://localhost:3000
```

### Performance
```bash
asgard verdandi report ./metrics.json
asgard verdandi slo ./metrics.json
```

### Infrastructure
```bash
asgard volundr k8s generate ./deployment.yaml
asgard volundr docker generate ./Dockerfile
```

---
## GAIA Integration

Asgard is used in GAIA's CI/CD pipeline and development workflow:
- `python -m Heimdall quality lazy-imports <path>` detects lazy import violations (a GAIA codebase rule)
- Quality gates run as part of the test coverage matrix via Hercules

---
## Related Documentation
- [[Asgard Package]] - Detailed package documentation
- [[04 - DevOps]] - CI/CD and deployment
- [[97-Standards]] - Code quality standards
