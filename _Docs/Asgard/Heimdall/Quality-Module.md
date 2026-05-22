# Heimdall Quality Module

## Overview

The Quality module provides comprehensive code quality analysis including file metrics, complexity analysis, duplication detection, code smell detection, technical debt quantification, and maintainability index calculation.

## Analyzers

### 1. File Length Analyzer

**Purpose**: Analyzes file and function lengths to identify oversized code units.

**Key Features**:
- Configurable line thresholds for files, functions, and classes
- Separate tracking for code lines vs total lines
- Supports multiple file extensions
- Generates detailed reports

**Configuration**:
```python
FileConfig(
    max_file_lines=500,
    max_function_lines=50,
    max_class_lines=300,
    include_extensions=[".py"],
    exclude_patterns=["__pycache__", ".git", "venv"]
)
```

**Output**: `FileReport` with file results, function results, and severity levels.

---

### 2. Complexity Analyzer

**Purpose**: Calculates cyclomatic and cognitive complexity for functions.

**Key Features**:
- **Cyclomatic Complexity**: Measures control flow paths (if/for/while/try/etc.)
- **Cognitive Complexity**: Measures human comprehension difficulty
- Per-function and per-file analysis
- Hotspot identification

**Complexity Levels**:
| Level | Cyclomatic | Cognitive |
|-------|------------|-----------|
| LOW | 1-5 | 1-5 |
| MODERATE | 6-10 | 6-10 |
| HIGH | 11-20 | 11-15 |
| VERY_HIGH | 21-50 | 16-25 |
| CRITICAL | >50 | >25 |

**Configuration**:
```python
ComplexityConfig(
    max_cyclomatic_complexity=10,
    max_cognitive_complexity=15,
    include_nested_functions=True
)
```

---

### 3. Duplication Detector

**Purpose**: Identifies duplicate and similar code blocks across the codebase.

**Key Features**:
- Exact duplicate detection
- Near-duplicate detection with similarity threshold
- Configurable minimum block size
- Cross-file duplicate grouping
- Fingerprint-based detection using MinHash/SimHash

**Detection Methods**:
- **Exact**: Hash-based matching of normalized code blocks
- **Similar**: Token-based similarity with configurable threshold (0.0-1.0)

**Configuration**:
```python
DuplicationConfig(
    min_lines=6,
    similarity_threshold=0.8,
    ignore_imports=True,
    ignore_comments=True
)
```

**Output**: `DuplicationReport` with clone groups, statistics, and refactoring suggestions.

---

### 4. Code Smell Detector

**Purpose**: Identifies common code quality issues and anti-patterns.

**Detected Smells**:

| Category | Smell | Description |
|----------|-------|-------------|
| SIZE | long_method | Methods exceeding line threshold |
| SIZE | large_class | Classes with too many methods/lines |
| SIZE | long_parameter_list | Functions with too many parameters |
| COMPLEXITY | complex_conditional | Deeply nested or complex conditions |
| COMPLEXITY | nested_callbacks | Callback hell patterns |
| NAMING | inconsistent_naming | Naming convention violations |
| NAMING | magic_numbers | Unexplained numeric literals |
| DESIGN | god_class | Classes doing too much |
| DESIGN | feature_envy | Methods using other class data excessively |
| DESIGN | data_class | Classes with only data, no behavior |
| MAINTAINABILITY | dead_code | Unreachable or unused code |
| MAINTAINABILITY | duplicate_code | Copy-paste code patterns |
| MAINTAINABILITY | commented_code | Large blocks of commented code |

**Severity Levels**: CRITICAL, HIGH, MEDIUM, LOW, INFO

**Configuration**:
```python
SmellConfig(
    max_method_lines=50,
    max_class_methods=20,
    max_parameters=5,
    max_nesting_depth=4,
    detect_magic_numbers=True,
    min_severity=SeverityLevel.LOW
)
```

---

### 5. Technical Debt Analyzer

**Purpose**: Quantifies technical debt with cost estimates and prioritization.

**Debt Categories**:
| Category | Description |
|----------|-------------|
| CODE | Code-level issues (complexity, duplication) |
| DESIGN | Architectural problems (coupling, cohesion) |
| TEST | Testing gaps (coverage, quality) |
| DOCUMENTATION | Missing or outdated documentation |
| DEPENDENCIES | Outdated or vulnerable dependencies |

**Key Features**:
- Time-based cost estimation (minutes/hours to fix)
- Interest rate calculation (ongoing cost of not fixing)
- ROI analysis for prioritization
- Time horizon projections (1mo, 3mo, 6mo, 12mo)
- Weighted scoring by severity and impact

**Configuration**:
```python
DebtConfig(
    include_code_debt=True,
    include_design_debt=True,
    include_test_debt=True,
    hourly_rate=75.0,  # For cost calculation
    include_time_projections=True
)
```

**Output**: `DebtReport` with total principal, interest rates, projected costs, and prioritized items.

---

### 6. Maintainability Analyzer

**Purpose**: Calculates Microsoft's Maintainability Index for code quality assessment.

**Formula**:
```
MI = 171 - 5.2*ln(HV) - 0.23*CC - 16.2*ln(LOC) + 50*sin(sqrt(2.4*CM))
```

Where:
- **HV**: Halstead Volume
- **CC**: Cyclomatic Complexity
- **LOC**: Lines of Code
- **CM**: Comment percentage (0-100)

**Maintainability Levels**:
| Level | Index Range |
|-------|-------------|
| EXCELLENT | 85-100 |
| GOOD | 70-84 |
| MODERATE | 50-69 |
| POOR | 25-49 |
| CRITICAL | 0-24 |

**Halstead Metrics**:
- **Vocabulary (n)**: n1 + n2 (distinct operators + operands)
- **Length (N)**: N1 + N2 (total operators + operands)
- **Volume (V)**: N * log2(n)
- **Difficulty (D)**: (n1/2) * (N2/n2)
- **Effort (E)**: D * V

**Language Profiles**:
| Language | Complexity Weight | Volume Weight |
|----------|------------------|---------------|
| Python | 0.23 | 5.2 |
| Java | 0.25 | 5.5 |
| JavaScript | 0.20 | 4.8 |

**Configuration**:
```python
MaintainabilityConfig(
    include_halstead=True,
    include_comments=True,
    language_profile=LanguageProfile.PYTHON,
    thresholds=MaintainabilityThresholds(excellent=85, good=70)
)
```

---

### 7. Lazy Import Scanner

**Purpose**: Detects imports not at module level, which violates the GAIA coding standard.

**GAIA Standard**: ALL imports MUST be at the top of the file. No importing inside functions, methods, or conditional blocks.

**Detected Violations**:

| Type | Description | Severity |
|------|-------------|----------|
| FUNCTION | Import inside a function | HIGH |
| METHOD | Import inside a class method | HIGH |
| CONDITIONAL | Import inside if/elif/else block | MEDIUM |
| TRY_EXCEPT | Import inside try/except block | MEDIUM |
| LOOP | Import inside for/while loop | LOW |
| WITH_BLOCK | Import inside with statement | LOW |

**Special Exception**: Imports inside `if TYPE_CHECKING:` blocks are allowed as this is a valid Python pattern for avoiding circular imports in type hints.

**Key Features**:
- AST-based detection for accurate analysis
- Identifies all non-module-level import locations
- Tracks containing function/class for context
- Provides remediation suggestions
- Configurable severity filtering
- Excludes TYPE_CHECKING blocks (valid pattern)

**Severity Levels**: HIGH, MEDIUM, LOW

**Configuration**:
```python
LazyImportConfig(
    scan_path=Path("./src"),
    severity_filter=LazyImportSeverity.LOW,
    output_format="text",  # text, json, markdown
    include_extensions=[".py"],
    exclude_patterns=["__pycache__", ".git", "venv"],
    include_tests=True
)
```

**Output**: `LazyImportReport` with detected violations, statistics, and most problematic files.

---

## Usage Examples

### CLI Usage

```bash
# Run all quality checks
python -m Heimdall quality analyze ./src

# Specific analyzers
python -m Heimdall quality complexity ./src --max-cyclomatic=10
python -m Heimdall quality duplication ./src --min-lines=6
python -m Heimdall quality smells ./src --severity=medium
python -m Heimdall quality debt ./src --format=json
python -m Heimdall quality maintainability ./src --format=markdown
python -m Heimdall quality lazy-imports ./src --format=text
```

### Programmatic Usage

```python
from Heimdall.Quality.services import (
    FileAnalyzer,
    ComplexityAnalyzer,
    DuplicationDetector,
    CodeSmellDetector,
    TechnicalDebtAnalyzer,
    MaintainabilityAnalyzer,
    LazyImportScanner
)
from pathlib import Path

# Complexity analysis
analyzer = ComplexityAnalyzer()
report = analyzer.analyze(Path("./src"))
print(f"Hotspots: {len(report.hotspots)}")

# Technical debt
debt_analyzer = TechnicalDebtAnalyzer()
debt_report = debt_analyzer.analyze(Path("./src"))
print(f"Total debt: ${debt_report.total_cost:.2f}")

# Maintainability
mi_analyzer = MaintainabilityAnalyzer()
mi_report = mi_analyzer.analyze(Path("./src"))
print(f"Overall MI: {mi_report.overall_index:.1f}")

# Lazy import detection
lazy_scanner = LazyImportScanner()
lazy_report = lazy_scanner.analyze(Path("./src"))
print(f"Lazy imports found: {lazy_report.total_violations}")
for violation in lazy_report.detected_imports:
    print(f"{violation.location}: {violation.import_statement}")
```

---

## Test Coverage

All analyzers have comprehensive test suites:

| Analyzer | Test File | Test Count |
|----------|-----------|------------|
| File Length | test_file_length_analyzer.py | 15 |
| Complexity | test_complexity_analyzer.py | 22 |
| Duplication | test_duplication_detector.py | 18 |
| Code Smell | test_code_smell_detector.py | 27 |
| Technical Debt | test_technical_debt_analyzer.py | 38 |
| Maintainability | test_maintainability_analyzer.py | 34 |
| Lazy Import | test_lazy_import_scanner.py | TBD |
| **Total** | | **154+** |

All tests pass successfully.

---

## Additional Analyzers

### Naming Convention Scanner

**Location:** `Quality/services/naming_convention_scanner.py`

Enforces language-specific naming conventions. For Python, validates PEP 8 naming rules.

| Element | Convention | Example |
|---------|-----------|---------|
| Functions / methods | `snake_case` | `calculate_total` |
| Classes | `PascalCase` | `UserService` |
| Constants (module-level) | `UPPER_CASE` | `MAX_RETRIES` |
| Variables | `snake_case` | `user_id` |
| Private members | `_snake_case` | `_internal_cache` |

```python
from Asgard.Heimdall.Quality.services.naming_convention_scanner import NamingConventionScanner

scanner = NamingConventionScanner()
report = scanner.scan("./src")

for violation in report.violations:
    print(f"{violation.file_path}:{violation.line} - {violation.element} '{violation.name}' "
          f"should be {violation.expected_convention}")
```

CLI: `python -m Heimdall quality naming <path>`

---

### Documentation Scanner

**Location:** `Quality/services/documentation_scanner.py`

Measures comment density and identifies undocumented public APIs (functions, classes, methods).

**Metrics Produced:**
- Comment line count (single-line, multi-line, docstrings)
- Comment density ratio (comment lines / total lines)
- Undocumented public API count
- API documentation coverage percentage

```python
from Asgard.Heimdall.Quality.services.documentation_scanner import DocumentationScanner

scanner = DocumentationScanner()
report = scanner.scan("./src")

print(f"Comment density: {report.comment_density:.1f}%")
print(f"API doc coverage: {report.api_documentation_coverage:.1f}%")
for item in report.undocumented_items:
    print(f"Undocumented: {item.qualified_name} at {item.file_path}:{item.line}")
```

CLI: `python -m Heimdall quality docs <path>`

---

## Multi-Language Quality Rules

In addition to deep Python analysis, Heimdall includes quality rule sets for JavaScript, TypeScript, and Shell scripts.

### JavaScript / TypeScript

**Location:** `Quality/languages/javascript/`, `Quality/languages/typescript/`

Covers:
- Bug detection: null/undefined access, type coercion issues, unreachable code
- Code smells: high complexity, deeply nested code, long functions
- Style: naming conventions, formatting patterns
- Framework-aware rules: React patterns

### Shell Scripts

**Location:** `Quality/languages/shell/`

Covers:
- Security: unquoted variables, `eval` usage, command injection patterns
- Style: POSIX compliance, quoting correctness, word-splitting issues
- Equivalent to a subset of ShellCheck rules

```bash
python -m Heimdall quality analyze <path> --languages=python,javascript,shell
```
