# Heimdall - Code Quality Control Package

## Overview

Heimdall is GAIA's automated, deterministic code quality control package. Named after the Norse god who guards Bifrost and sees all across the realms, Heimdall provides comprehensive codebase monitoring and quality gates.

## Why Heimdall?

- **Guards Bifrost (the bridge)** - Analogous to guarding code quality gates
- **Can see and hear everything across all realms** - Comprehensive codebase monitoring
- **His horn (Gjallarhorn) warns of problems** - Alerting on quality issues
- **Single deity name** - Matches existing GAIA patterns (Iris, Athena, Themis)

## Package Structure

```
Asgard/
└── Heimdall/
    ├── setup.py
    ├── pyproject.toml
    ├── README.md
    └── Heimdall/
        ├── __init__.py
        ├── __main__.py
        ├── cli.py
        │
        ├── Quality/                       # Code Quality Analysis
        │   ├── models/
        │   │   ├── analysis_models.py
        │   │   ├── complexity_models.py
        │   │   ├── duplication_models.py
        │   │   ├── smell_models.py
        │   │   ├── debt_models.py
        │   │   ├── maintainability_models.py
        │   │   ├── syntax_models.py           # Syntax/linting models
        │   │   └── lazy_import_models.py
        │   ├── services/
        │   │   ├── complexity_analyzer.py
        │   │   ├── duplication_detector.py
        │   │   ├── code_smell_detector.py
        │   │   ├── technical_debt_calculator.py
        │   │   ├── maintainability_analyzer.py
        │   │   ├── syntax_checker.py          # Syntax/linting checker
        │   │   └── lazy_import_scanner.py
        │   └── utilities/
        │
        ├── Security/                      # Security Analysis
        │   ├── __init__.py
        │   ├── models/
        │   │   └── security_models.py
        │   ├── services/
        │   │   ├── secrets_detection_service.py
        │   │   ├── dependency_vulnerability_service.py
        │   │   ├── injection_detection_service.py
        │   │   ├── cryptographic_validation_service.py
        │   │   └── static_security_service.py
        │   ├── utilities/
        │   │   └── security_utils.py
        │   ├── Access/                    # Access Control Analysis
        │   │   ├── models/
        │   │   │   └── access_models.py
        │   │   └── services/
        │   │       ├── access_analyzer.py
        │   │       ├── control_analyzer.py
        │   │       └── permission_analyzer.py
        │   ├── Auth/                      # Authentication Analysis
        │   │   ├── models/
        │   │   │   └── auth_models.py
        │   │   └── services/
        │   │       ├── auth_analyzer.py
        │   │       ├── jwt_validator.py
        │   │       ├── session_analyzer.py
        │   │       └── password_analyzer.py
        │   ├── Headers/                   # Security Headers Analysis
        │   │   ├── models/
        │   │   │   └── header_models.py
        │   │   └── services/
        │   │       ├── headers_analyzer.py
        │   │       ├── csp_analyzer.py
        │   │       └── cors_analyzer.py
        │   ├── TLS/                       # TLS/SSL Analysis
        │   │   ├── models/
        │   │   │   └── tls_models.py
        │   │   └── services/
        │   │       ├── tls_analyzer.py
        │   │       ├── certificate_validator.py
        │   │       └── cipher_validator.py
        │   ├── Container/                 # Container Security Analysis
        │   │   ├── models/
        │   │   │   └── container_models.py
        │   │   └── services/
        │   │       ├── container_analyzer.py
        │   │       ├── dockerfile_analyzer.py
        │   │       └── compose_analyzer.py
        │   └── Infrastructure/            # Infrastructure Security
        │       ├── models/
        │       │   └── infra_models.py
        │       └── services/
        │           ├── infra_analyzer.py
        │           ├── credential_analyzer.py
        │           ├── config_validator.py
        │           └── hardening_checker.py
        │
        ├── Performance/                   # Performance Analysis
        │   ├── models/
        │   ├── services/
        │   └── utilities/
        │
        ├── OOP/                           # Object-Oriented Metrics
        │   ├── models/
        │   │   └── oop_models.py          # CBO, DIT, LCOM, RFC, WMC
        │   └── services/
        │       ├── coupling_analyzer.py
        │       ├── inheritance_analyzer.py
        │       ├── cohesion_analyzer.py
        │       ├── rfc_analyzer.py
        │       └── oop_analyzer.py
        │
        ├── Dependencies/                  # Dependency Analysis
        │   ├── models/
        │   │   ├── dependency_models.py   # Import mapping, cycles
        │   │   ├── requirements_models.py # Requirements validation
        │   │   └── license_models.py      # License compliance
        │   └── services/
        │       ├── import_analyzer.py
        │       ├── graph_builder.py
        │       ├── cycle_detector.py
        │       ├── modularity_analyzer.py
        │       ├── dependency_analyzer.py
        │       ├── requirements_checker.py  # Requirements.txt validation
        │       └── license_checker.py       # License compliance checking
        │
        ├── Architecture/                  # Architecture Analysis
        │   ├── models/
        │   │   └── architecture_models.py # SOLID, layers, patterns
        │   ├── services/
        │   │   ├── solid_validator.py
        │   │   ├── layer_analyzer.py
        │   │   ├── pattern_detector.py
        │   │   └── architecture_analyzer.py
        │   └── utilities/
        │       └── ast_utils.py
        │
        └── Coverage/                      # Test Coverage Analysis
            ├── models/
            │   └── coverage_models.py     # Gaps, suggestions
            ├── services/
            │   ├── gap_analyzer.py
            │   ├── suggestion_engine.py
            │   └── coverage_analyzer.py
            └── utilities/
                └── method_extractor.py
```

## Submodule Overview

| Submodule | Purpose | Services |
|-----------|---------|----------|
| Quality | Code metrics, complexity, duplication, maintainability, syntax/linting, import standards | 8 analyzers |
| Security | Vulnerabilities, secrets, injections, crypto, access, auth, headers, TLS, container, infra | 11 services + 6 subpackages |
| Performance | CPU/memory profiling, database analysis, caching | 5 services |
| OOP | Object-oriented metrics (CBO, DIT, LCOM, RFC, WMC) | 5 analyzers |
| Dependencies | Import mapping, cycle detection, modularity, requirements validation, license compliance | 7 services |
| Architecture | SOLID validation, layer compliance, pattern detection | 4 services |
| Coverage | Test coverage gaps, suggestions, class coverage | 3 services |

---

## Quality Module

Comprehensive code quality analysis including:
- **File Length Analyzer** - File and function length thresholds
- **Complexity Analyzer** - Cyclomatic and cognitive complexity
- **Duplication Detector** - Clone detection and similarity analysis
- **Code Smell Detector** - Anti-pattern and smell detection
- **Technical Debt Analyzer** - Debt quantification with cost estimates
- **Maintainability Analyzer** - Microsoft Maintainability Index
- **Lazy Import Scanner** - Detects imports not at module level (GAIA standard enforcement)

See [02-Quality-Module.md](02-Quality-Module.md) for details.

---

## Security Module

Comprehensive static security analysis including:

**Core Analyzers**:
- **Secrets Detection** - API keys, passwords, tokens, credentials
- **Dependency Vulnerability** - Known CVEs in dependencies
- **Injection Detection** - SQL, XSS, command injection patterns
- **Cryptographic Validation** - Weak crypto, insecure SSL, poor random

**Extended Analyzers** (6 subpackages):
- **Access** - RBAC/ABAC patterns, route permissions, authorization checks
- **Auth** - JWT security, session management, password handling
- **Headers** - CSP, CORS, HSTS, X-Frame-Options validation
- **TLS** - Protocol versions, cipher suites, certificate validation
- **Container** - Dockerfile/docker-compose security, privileged mode, secrets
- **Infrastructure** - Default credentials, debug mode, hardening checks

**Security Score**: 0-100 based on severity-weighted findings

See [04-Security-Module.md](04-Security-Module.md) for details.

---

## Performance Module

Static performance analysis including:
- **Memory Profiler** - Leaks, high allocations, inefficient structures
- **CPU Profiler** - Complexity, blocking operations, inefficient loops
- **Database Analyzer** - N+1 queries, missing indexes, ORM anti-patterns
- **Cache Analyzer** - Missing caches, TTL issues, key problems

**Performance Score**: 0-100 based on severity-weighted findings

See [05-Performance-Module.md](05-Performance-Module.md) for details.

---

## OOP Module

Object-oriented programming metrics analysis including:
- **Coupling Analyzer** - Coupling Between Objects (CBO), Afferent/Efferent coupling
- **Inheritance Analyzer** - Depth of Inheritance Tree (DIT), Number of Children (NOC)
- **Cohesion Analyzer** - Lack of Cohesion of Methods (LCOM)
- **RFC Analyzer** - Response for Class (RFC)
- **WMC Analyzer** - Weighted Methods per Class (WMC)

**Instability Score**: 0.0-1.0 based on Ce/(Ca+Ce) ratio

See [06-OOP-Module.md](06-OOP-Module.md) for details.

---

## Dependencies Module

Dependency analysis and cycle detection including:
- **Import Analyzer** - Python import statement extraction
- **Graph Builder** - NetworkX-based dependency graph construction
- **Cycle Detector** - Circular dependency detection
- **Modularity Analyzer** - Module boundary and coupling analysis

**Modularity Score**: 0.0-1.0 based on dependency isolation

See [07-Dependencies-Module.md](07-Dependencies-Module.md) for details.

---

## Architecture Module

Architectural analysis and SOLID validation including:
- **SOLID Validator** - SRP, OCP, LSP, ISP, DIP validation
- **Layer Analyzer** - Layer compliance and separation of concerns
- **Pattern Detector** - Design pattern detection and validation

See [08-Architecture-Module.md](08-Architecture-Module.md) for details.

---

## Coverage Module

Test coverage analysis and gap detection including:
- **Gap Analyzer** - Identify untested methods and classes
- **Suggestion Engine** - Generate test suggestions for uncovered code
- **Method Extractor** - Extract methods from source for coverage analysis

See [09-Coverage-Module.md](09-Coverage-Module.md) for details.

---

## CLI Interface

```bash
# Main entry point
python -m Heimdall <command> [options]

# Quality analysis
python -m Heimdall quality analyze <path>       # Run all quality checks
python -m Heimdall quality file-length <path>   # File length analysis
python -m Heimdall quality complexity <path>    # Complexity analysis
python -m Heimdall quality duplication <path>   # Duplication detection
python -m Heimdall quality smells <path>        # Code smell detection
python -m Heimdall quality debt <path>          # Technical debt analysis
python -m Heimdall quality maintainability <path>  # Maintainability index
python -m Heimdall quality lazy-imports <path>  # Lazy import detection

# Security analysis
python -m Heimdall security scan <path>         # Full security scan
python -m Heimdall security secrets <path>      # Secrets detection only
python -m Heimdall security dependencies <path> # Dependency vulnerabilities
python -m Heimdall security vulnerabilities <path>  # Injection detection
python -m Heimdall security crypto <path>       # Cryptographic validation
python -m Heimdall security access <path>       # Access control analysis
python -m Heimdall security auth <path>         # Authentication analysis
python -m Heimdall security headers <path>      # Security headers analysis
python -m Heimdall security tls <path>          # TLS/SSL analysis
python -m Heimdall security container <path>    # Container security analysis
python -m Heimdall security infra <path>        # Infrastructure security analysis

# Performance analysis
python -m Heimdall performance scan <path>      # Full performance scan
python -m Heimdall performance memory <path>    # Memory analysis only
python -m Heimdall performance cpu <path>       # CPU/complexity analysis
python -m Heimdall performance database <path>  # Database analysis
python -m Heimdall performance cache <path>     # Cache analysis

# OOP metrics analysis
python -m Heimdall oop analyze <path>           # Full OOP metrics analysis
python -m Heimdall oop coupling <path>          # CBO analysis
python -m Heimdall oop inheritance <path>       # DIT/NOC analysis
python -m Heimdall oop cohesion <path>          # LCOM analysis

# Dependency analysis
python -m Heimdall deps analyze <path>          # Full dependency analysis
python -m Heimdall deps cycles <path>           # Circular dependency detection
python -m Heimdall deps graph <path>            # Dependency graph generation
python -m Heimdall deps modularity <path>       # Modularity analysis

# Architecture analysis
python -m Heimdall arch analyze <path>          # Full architecture analysis
python -m Heimdall arch solid <path>            # SOLID validation
python -m Heimdall arch layers <path>           # Layer compliance
python -m Heimdall arch patterns <path>         # Pattern detection

# Coverage analysis
python -m Heimdall coverage analyze <path>      # Full coverage analysis
python -m Heimdall coverage gaps <path>         # Coverage gap detection
python -m Heimdall coverage suggest <path>      # Test suggestions

# Full audit (all modules)
python -m Heimdall audit <path>                 # Run all analysis modules

# Output formats
python -m Heimdall <command> <path> --format=text
python -m Heimdall <command> <path> --format=json
python -m Heimdall <command> <path> --format=markdown
```

See [03-CLI-Reference.md](03-CLI-Reference.md) for complete CLI documentation.

---

## Implementation Status

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | COMPLETE | Foundation, package structure, Thoth migration |
| Phase 2 | COMPLETE | Enhanced quality analyzers |
| Phase 3 | COMPLETE | Security module (5 services) |
| Phase 4 | COMPLETE | Performance module (5 services) |
| Phase 5 | COMPLETE | Integration and CLI |
| Phase 6 | COMPLETE | Security extensions (Access, Auth, Headers, TLS, Container, Infrastructure) |
| Phase 7 | COMPLETE | OOP, Dependencies, Architecture, Coverage modules |
| Phase 8 | COMPLETE | SonarQube parity: Ratings, QualityGate, Issues, Profiles, TaintAnalysis, Hotspots, Compliance, SBOM, PR Decoration, History, MCP Server, naming/doc scanners, JS/TS/Shell language rules |

---

## Quick Start

### Installation

```bash
# From GAIA root directory
pip install -e ./Asgard/Heimdall
```

### Basic Usage

```bash
# Quick security check
python -m Heimdall security scan ./src

# Performance analysis
python -m Heimdall performance scan ./src --format json

# Full audit
python -m Heimdall audit ./src
```

### Programmatic Usage

```python
from Heimdall import (
    # Quality
    FileAnalyzer, AnalysisConfig,
    # Security - Core
    StaticSecurityService, SecurityScanConfig,
    # Security - Extended Analyzers
    AccessAnalyzer, AccessConfig,
    AuthAnalyzer, AuthConfig,
    HeadersAnalyzer, HeaderConfig,
    TLSAnalyzer, TLSConfig,
    ContainerAnalyzer, ContainerConfig,
    InfraAnalyzer, InfraConfig,
    # Performance
    StaticPerformanceService, PerformanceScanConfig
)

# Full security scan (all analyzers)
security_service = StaticSecurityService()
security_report = security_service.scan("./src")
print(f"Security Score: {security_report.security_score}/100")

# Individual security analyzers
access_analyzer = AccessAnalyzer(AccessConfig(scan_path="./src"))
access_report = access_analyzer.analyze()
print(f"Access Issues: {access_report.total_issues}")

auth_analyzer = AuthAnalyzer(AuthConfig(scan_path="./src"))
auth_report = auth_analyzer.analyze()
print(f"Auth Issues: {auth_report.total_issues}")

# Performance scan
perf_service = StaticPerformanceService()
perf_report = perf_service.scan("./src")
print(f"Performance Score: {perf_report.performance_score}/100")
```

---

## Testing

Heimdall is tested through both internal tests (Heimdall_Test) and the Hercules Testing Framework.

### Test Location

```
Asgard/Heimdall/Heimdall_Test/L0_Mocked/
├── __init__.py
├── Security/
│   ├── __init__.py
│   ├── test_secrets_detection_service.py
│   ├── test_dependency_vulnerability_service.py
│   ├── test_injection_detection_service.py
│   ├── test_cryptographic_validation_service.py
│   ├── test_static_security_service.py
│   ├── test_security_models.py
│   ├── test_security_utils.py
│   ├── Access/                          # Access control tests
│   │   ├── conftest.py
│   │   ├── test_access_models.py
│   │   ├── test_decorator_utils.py
│   │   ├── test_control_analyzer.py
│   │   ├── test_permission_analyzer.py
│   │   └── test_access_analyzer.py
│   ├── Auth/                            # Authentication tests
│   │   ├── conftest.py
│   │   ├── models/
│   │   │   └── test_auth_models.py
│   │   ├── services/
│   │   │   ├── test_jwt_validator.py
│   │   │   ├── test_session_analyzer.py
│   │   │   ├── test_password_analyzer.py
│   │   │   └── test_auth_analyzer.py
│   │   └── utilities/
│   │       └── test_token_utils.py
│   ├── Headers/                         # Security headers tests
│   ├── TLS/                             # TLS/SSL tests
│   ├── Container/                       # Container security tests
│   └── Infrastructure/                  # Infrastructure tests
├── OOP/
│   ├── __init__.py
│   ├── test_oop_models.py               # OOP metrics models
│   └── test_oop_analyzer.py             # OOP analyzer service
├── Dependencies/
│   ├── __init__.py
│   ├── test_dependency_models.py        # Dependency models
│   └── test_dependency_analyzer.py      # Dependency analyzer service
├── Architecture/
│   ├── __init__.py
│   ├── test_architecture_models.py      # Architecture models
│   └── test_architecture_analyzer.py    # Architecture analyzer service
└── Coverage/
    ├── __init__.py
    ├── test_coverage_models.py          # Coverage models
    └── test_coverage_analyzer.py        # Coverage analyzer service

Hercules/tests/L0_unit/heimdall/
├── __init__.py
├── test_cli.py                          # CLI parser and commands
├── quality/
│   ├── __init__.py
│   ├── test_complexity_analyzer.py      # Cyclomatic/Cognitive complexity
│   ├── test_duplication_detector.py     # Code duplication detection
│   └── test_code_smell_detector.py      # Code smell detection
├── security/
│   ├── __init__.py
│   └── test_secrets_detection_service.py  # Secrets detection patterns
└── performance/
    ├── __init__.py
    └── test_memory_profiler_service.py   # Memory profiling patterns
```

### Running Heimdall Tests

```bash
# Run internal Heimdall tests
python -m pytest Asgard/Heimdall/Heimdall_Test -v

# Run all Security module tests (248 tests)
python -m pytest Asgard/Heimdall/Heimdall_Test/L0_Mocked/Security -v

# Run specific Security subpackage tests
python -m pytest Asgard/Heimdall/Heimdall_Test/L0_Mocked/Security/Access -v
python -m pytest Asgard/Heimdall/Heimdall_Test/L0_Mocked/Security/Auth -v
python -m pytest Asgard/Heimdall/Heimdall_Test/L0_Mocked/Security/Headers -v
python -m pytest Asgard/Heimdall/Heimdall_Test/L0_Mocked/Security/TLS -v
python -m pytest Asgard/Heimdall/Heimdall_Test/L0_Mocked/Security/Container -v
python -m pytest Asgard/Heimdall/Heimdall_Test/L0_Mocked/Security/Infrastructure -v

# Run specific internal module tests
python -m pytest Asgard/Heimdall/Heimdall_Test/L0_Mocked/OOP -v
python -m pytest Asgard/Heimdall/Heimdall_Test/L0_Mocked/Dependencies -v
python -m pytest Asgard/Heimdall/Heimdall_Test/L0_Mocked/Architecture -v
python -m pytest Asgard/Heimdall/Heimdall_Test/L0_Mocked/Coverage -v

# Run Hercules integration tests
python -m pytest Hercules/tests/L0_unit/heimdall -v

# Run with heimdall marker
python -m pytest -m heimdall

# Run specific Hercules module tests
python -m pytest Hercules/tests/L0_unit/heimdall/quality -v
python -m pytest Hercules/tests/L0_unit/heimdall/security -v
python -m pytest Hercules/tests/L0_unit/heimdall/performance -v
```

### Test Markers

Tests use the following pytest markers:
- `@pytest.mark.L0` - Quality Assurance level
- `@pytest.mark.heimdall` - Heimdall module
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.fast` - Fast execution tests

---

## Related Documentation

- [02-Quality-Module.md](02-Quality-Module.md) - Quality module details
- [03-CLI-Reference.md](03-CLI-Reference.md) - CLI command reference
- [04-Security-Module.md](04-Security-Module.md) - Security module details
- [05-Performance-Module.md](05-Performance-Module.md) - Performance module details
- [06-OOP-Module.md](06-OOP-Module.md) - OOP metrics module details
- [07-Dependencies-Module.md](07-Dependencies-Module.md) - Dependencies module details
- [08-Architecture-Module.md](08-Architecture-Module.md) - Architecture module details
- [09-Coverage-Module.md](09-Coverage-Module.md) - Coverage module details
- [10-QualityGate-Module.md](10-QualityGate-Module.md) - Quality gate pass/fail thresholds
- [11-Ratings-Module.md](11-Ratings-Module.md) - A-E letter ratings (Maintainability, Reliability, Security)
- [12-Issues-Module.md](12-Issues-Module.md) - Persistent issue lifecycle tracking
- [13-Profiles-Module.md](13-Profiles-Module.md) - Quality profiles and rule sets
- [14-Security-Advanced.md](14-Security-Advanced.md) - Taint analysis, hotspots, OWASP/CWE compliance, SBOM
- [15-Reporting-Advanced.md](15-Reporting-Advanced.md) - Metrics history, PR decoration, MCP server
