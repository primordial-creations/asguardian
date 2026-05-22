# Asgard Package

[[Asgard|Back to Asgard]] | [[GAIA Index|Back to GAIA Documentation]]

---
## Package Structure

```
Asgard/
  Asgard/
    cli.py                 # Main CLI entry point
    common/                # Shared utilities (baseline, parallel, output, progress)
    Forseti/               # API and schema validation
      OpenAPI/             # OpenAPI specification validation
      Contracts/           # Contract testing
      JSONSchema/          # JSON Schema inference and validation
      AsyncAPI/            # AsyncAPI specification support
      Avro/                # Avro schema validation and compatibility
    Freya/                 # Web and UI testing
      Accessibility/       # Accessibility scanning
      Visual/              # Visual regression testing
      Responsive/          # Responsive design checks
      Integration/         # Integration with CI/CD
    Heimdall/              # Static analysis and code quality
      Quality/             # Code quality metrics
      Security/            # Security vulnerability scanning
      QualityGate/         # Pass/fail quality gates
      Ratings/             # Letter ratings (A-E)
      Issues/              # Issue tracking with lifecycle states
      Profiles/            # Quality profiles
      Reporting/           # Advanced reporting
    Verdandi/              # Performance metrics
      Analysis/            # Metric analysis
      Web/                 # Web vitals
      Database/            # Database performance
      System/              # System metrics
      Network/             # Network metrics
      Cache/               # Cache performance
    Volundr/               # Infrastructure generation
      Kubernetes/          # K8s manifests
      Terraform/           # Terraform configs
      Docker/              # Dockerfiles
      CICD/                # CI/CD pipelines
```

---
## Installation

```bash
pip install asguardian
```

---
## CLI Reference

The main entry point is `asgard` (or `python -m Asgard.cli`):

```
asgard <tool> <command> [options]
```

Where `<tool>` is one of: `forseti`, `freya`, `heimdall`, `verdandi`, `volundr`.

See individual tool documentation for detailed CLI references:
- [[Asgard/Forseti/05-CLI-Reference|Forseti CLI Reference]]
- [[Asgard/Heimdall/03-CLI-Reference|Heimdall CLI Reference]]
- [[Asgard/Volundr/06-CLI-Reference|Volundr CLI Reference]]

---
## Related Documentation
- [[Asgard]] - Asgard overview
- [[04 - DevOps]] - CI/CD integration
