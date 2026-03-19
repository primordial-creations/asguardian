# Heimdall — New Checks Reference

This document describes all new static analysis checks added to Heimdall beyond
the existing null-dereference, unreachable-code, SOLID, and pattern-detection capabilities.

---

## Table of Contents

1. [GoF Pattern Candidate Suggester](#1-gof-pattern-candidate-suggester)
2. [Assertion Misuse Detector](#2-assertion-misuse-detector)
3. [Division by Zero Detector](#3-division-by-zero-detector)
4. [Python Footgun Detector](#4-python-footgun-detector)
5. [Exception Quality Detector](#5-exception-quality-detector)
6. [Type Erosion Scanner](#6-type-erosion-scanner)
7. [Dead Code Detector](#7-dead-code-detector)
8. [Magic Numbers Detector](#8-magic-numbers-detector)
9. [Integration & Usage](#9-integration--usage)

---

## 1. GoF Pattern Candidate Suggester

**Module:** `Asgard/Heimdall/Architecture/services/pattern_suggester.py`
**Model additions:** `PatternSuggestion`, `PatternSuggestionReport` in `architecture_models.py`
**Orchestrator:** `ArchitectureAnalyzer.suggest_patterns()` / `ArchitectureAnalyzer.analyze(suggest_patterns=True)`

### What it does

The existing `PatternDetector` finds GoF patterns that **are already implemented** in the
codebase (Singleton, Factory, Observer, etc.). The new `PatternSuggester` is the opposite: it
analyses code smells and structural signals and **recommends** which GoF pattern would improve
the design.

### Signals and the patterns they trigger

| Code Signal | Suggested Pattern | Confidence |
|---|---|---|
| Constructor with ≥5 params, ≥4 optional | **Builder** | 80% |
| if/elif chain with ≥4 branches in a method | **Strategy** | 75% |
| ≥3 `isinstance()` checks in one method | **Visitor** | 70–75% |
| ≥3 direct `ClassName()` instantiations in `__init__` | **Factory Method** | 70% |
| ≥6 constructor dependencies | **Facade** | 65% |
| ≥9 constructor dependencies | **Mediator** | 65% |
| ≥3 `on_*` / `handle_*` / `notify_*` calls scattered across methods | **Observer** | 70% |
| ≥8 public methods spanning ≥3 responsibility groups | **Facade** | 70% |

### Each suggestion includes

- `rationale` — a human-readable explanation of *why* the pattern fits
- `signals` — the exact code properties that triggered the suggestion
- `confidence` — 0.0–1.0 score for the strength of the signal
- `benefit` — what the developer gains by applying the pattern

### Report formats

Text, JSON, and Markdown — accessible via `PatternSuggester.generate_report(result, format=...)`.

### Example

```python
from Asgard.Heimdall.Architecture import PatternSuggester
from pathlib import Path

suggester = PatternSuggester()
report = suggester.suggest(Path("./src"))

print(f"Suggestions: {report.total_suggestions}")
for s in report.suggestions:
    print(f"  [{s.pattern_type.value}] {s.class_name}: {s.rationale}")
```

---

## 2. Assertion Misuse Detector

**Module:** `Asgard/Heimdall/Quality/BugDetection/services/assertion_misuse_detector.py`
**BugCategory:** `ASSERTION_MISUSE`
**Config flag:** `BugDetectionConfig.detect_assertion_misuse`

### What it detects

| Pattern | Severity | Description |
|---|---|---|
| `assert (condition, "msg")` | **CRITICAL** | Tuple is always truthy — assertion NEVER fails even when condition is False |
| `assert False` / `assert None` / `assert 0` | **HIGH** | Always-falsy constant — unconditionally raises AssertionError |
| `assert isinstance(param, T)` in `__init__` | **MEDIUM** | Silently removed when Python runs with `-O` flag, bypassing the type check |
| `assert obj.mutating_method()` | **MEDIUM** | Method call side-effects disappear in optimised mode |

### Why this matters

Python's `assert` statements are **completely removed** at the bytecode level when the
interpreter runs with `-O` (optimise) or `-OO`. Any validation, type checking, or side
effects inside an assert will silently vanish in production environments that use these flags.

---

## 3. Division by Zero Detector

**Module:** `Asgard/Heimdall/Quality/BugDetection/services/division_by_zero_detector.py`
**BugCategory:** `DIVISION_BY_ZERO` (pre-existing category, now implemented)
**Config flag:** `BugDetectionConfig.detect_division_by_zero`

### What it detects

| Pattern | Severity | Description |
|---|---|---|
| `x / 0`, `x // 0`, `x % 0` | **CRITICAL** | Literal zero as divisor — always raises ZeroDivisionError |
| Variable assigned `0` used as divisor without reassignment | **HIGH** | Provably zero variable in division operation |

### Scope analysis

Each function body is analysed independently using a scoped AST visitor, preventing
false positives from variables in unrelated scopes.

---

## 4. Python Footgun Detector

**Module:** `Asgard/Heimdall/Quality/BugDetection/services/python_footgun_detector.py`
**BugCategories:** `MUTABLE_DEFAULT_ARG`, `LATE_BINDING_CLOSURE`, `IS_LITERAL_COMPARISON`, `BUILTIN_SHADOWING`
**Config flag:** `BugDetectionConfig.detect_python_footguns`

### What it detects

#### Mutable Default Arguments (`MUTABLE_DEFAULT_ARG`, HIGH)

```python
# BAD — default list is shared across ALL calls
def append_item(x, items=[]):
    items.append(x)
    return items

# GOOD
def append_item(x, items=None):
    items = items if items is not None else []
    items.append(x)
    return items
```

Default values are evaluated **once** at function definition time. Mutations accumulate
across calls, producing non-deterministic behaviour.

Detects: `[]`, `{}`, `set()`, `list()`, `dict()`, `defaultdict()`, `deque()`, `Counter()` as defaults.

#### Late-Binding Closures (`LATE_BINDING_CLOSURE`, HIGH)

```python
# BAD — all lambdas see the final value of `i` (e.g. 9)
functions = [lambda: i for i in range(10)]

# GOOD — capture current value with default arg
functions = [lambda i=i: i for i in range(10)]
```

Detects lambdas and nested functions inside `for` loops that reference loop variables
as free variables (not captured via default arguments).

#### Identity Comparison with Value Literals (`IS_LITERAL_COMPARISON`, MEDIUM)

```python
# BAD — only works by coincidence due to CPython integer interning
if x is 42:  ...

# GOOD
if x == 42:  ...
```

`is` / `is not` are correct for `None`, `True`, `False` (singletons) but not for
arbitrary literals. Flags comparisons with non-singleton constant values.

#### Builtin Shadowing (`BUILTIN_SHADOWING`, MEDIUM)

```python
# BAD — `list` built-in is now shadowed in this scope
list = [1, 2, 3]
items = list()  # TypeError: 'list' object is not callable
```

Detects assignments to 30+ important built-in names (`list`, `dict`, `type`, `id`,
`len`, `open`, `print`, `input`, `sorted`, `super`, etc.).

---

## 5. Exception Quality Detector

**Module:** `Asgard/Heimdall/Quality/BugDetection/services/exception_quality_detector.py`
**BugCategories:** `EXCEPTION_SWALLOWING`, `EXCEPTION_CHAINING`
**Config flag:** `BugDetectionConfig.detect_exception_quality`

### What it detects

| Pattern | Severity | Category |
|---|---|---|
| `except:` — bare except clause | **HIGH** | `EXCEPTION_SWALLOWING` |
| `except: pass` — bare except with empty body | **CRITICAL** | `EXCEPTION_SWALLOWING` |
| `except SomeError: pass` — empty handler | **HIGH** | `EXCEPTION_SWALLOWING` |
| `except Exception:` without re-raise | **MEDIUM** | `EXCEPTION_SWALLOWING` |
| `raise X` inside `except` without `from e` | **MEDIUM** | `EXCEPTION_CHAINING` |

### Exception chaining explained

```python
# BAD — original traceback is lost
try:
    risky_operation()
except IOError:
    raise ValueError("Conversion failed")

# GOOD — original cause is preserved in the chain
try:
    risky_operation()
except IOError as e:
    raise ValueError("Conversion failed") from e
```

---

## 6. Type Erosion Scanner

**Module:** `Asgard/Heimdall/Quality/BugDetection/services/type_erosion_scanner.py`
**BugCategory:** `TYPE_EROSION`
**Config flag:** `BugDetectionConfig.detect_type_erosion`

### What it detects

| Pattern | Severity | Description |
|---|---|---|
| Parameter annotated as `Any` | **MEDIUM** | Disables type checking for all operations on the value |
| Return type annotated as `Any` | **MEDIUM** | Callers lose type safety downstream |
| `typing.cast(T, x)` call | **LOW** | Runtime lie to the type checker — no actual verification |
| `# type: ignore` comment | **LOW** | Suppresses a type checker error without fixing it |
| `Union[A, B, C, D]` with ≥4 types | **LOW** | Over-wide union — suggests Protocol or base class |
| Public function missing `-> ReturnType` annotation | **LOW** | Return type implicitly becomes `Any` |

### Why `Any` is contagious

Once a value is typed `Any`, **all operations on it** become untyped. If `f() -> Any`
returns a value used in 10 places, those 10 call sites all lose type checking.
`Any` propagates silently and widely.

---

## 7. Dead Code Detector

**Module:** `Asgard/Heimdall/Quality/BugDetection/services/dead_code_detector.py`
**BugCategory:** `DEAD_CODE`
**Config flag:** `BugDetectionConfig.detect_dead_code`

### What it detects

| Pattern | Severity | Description |
|---|---|---|
| Private method (`_method`) never referenced via `self._method` | **MEDIUM** | Defined but never called within the class |
| Module-level private variable (`_var = ...`) never read in the file | **LOW** | Assigned but never referenced |

### Caveats

- Dynamic dispatch via `getattr(self, '_method_name')` cannot be detected statically.
  Results are candidates for review, not certainties.
- External callers using name mangling or reflection are not detected.
- Add a comment (e.g. `# called via getattr`) to suppress false positives.

---

## 8. Magic Numbers Detector

**Module:** `Asgard/Heimdall/Quality/BugDetection/services/magic_numbers_detector.py`
**BugCategory:** `MAGIC_NUMBER`
**Config flag:** `BugDetectionConfig.detect_magic_numbers`

### What it detects

Numeric literals (int or float) used directly in expressions, where the value has no
obvious meaning without context.

**Flagged contexts:** arithmetic operations (`BinOp`), comparisons (`Compare`), return values.

**Not flagged:**
- `UPPER_CASE = 42` assignments — treated as named constants
- The values `{-1, 0, 1, 2, 100}` — universally idiomatic
- Boolean values `True`/`False`
- Type annotations and default parameter values

### Example

```python
# BAD
if response.status_code == 429:  # What is 429?
    time.sleep(60)               # Why 60?

# GOOD
HTTP_TOO_MANY_REQUESTS = 429
RATE_LIMIT_BACKOFF_SECONDS = 60

if response.status_code == HTTP_TOO_MANY_REQUESTS:
    time.sleep(RATE_LIMIT_BACKOFF_SECONDS)
```

---

## 9. Integration & Usage

### Programmatic API

All new bug detectors are wired into the `BugDetector` orchestrator and run automatically
via `BugDetector.scan()`. Individual detectors can also be used directly:

```python
from pathlib import Path
from Asgard.Heimdall.Quality.BugDetection import (
    BugDetector,
    BugDetectionConfig,
    AssertMisuseDetector,
    DivisionByZeroDetector,
    PythonFootgunDetector,
    ExceptionQualityDetector,
    TypeErosionScanner,
    DeadCodeDetector,
    MagicNumbersDetector,
)

# Full scan (all checks enabled)
config = BugDetectionConfig(scan_path=Path("./src"))
detector = BugDetector(config)
report = detector.scan()
print(f"Total bugs: {report.total_bugs}")

# Selective scan — disable specific checks
config = BugDetectionConfig(
    scan_path=Path("./src"),
    detect_magic_numbers=False,   # too noisy for legacy code
    detect_type_erosion=False,    # project not yet typed
)
detector = BugDetector(config)
report = detector.scan()

# Use individual detector directly
scanner = TypeErosionScanner()
findings = scanner.analyze_file(Path("mymodule.py"), open("mymodule.py").readlines())
for f in findings:
    print(f"  [{f.severity}] {f.title} @ line {f.line_number}")
```

### Pattern Suggestion API

```python
from Asgard.Heimdall.Architecture import ArchitectureAnalyzer, PatternSuggester
from pathlib import Path

# Via the full analyzer (included by default)
analyzer = ArchitectureAnalyzer()
report = analyzer.analyze(Path("./src"))
if report.suggestion_report:
    for s in report.suggestion_report.suggestions:
        print(f"  [{s.pattern_type.value}] {s.class_name} ({s.confidence:.0%}): {s.rationale}")

# Direct suggester
suggester = PatternSuggester()
suggestions = suggester.suggest(Path("./src"))
print(suggester.generate_report(suggestions, format="markdown"))

# Single-class analysis (useful for IDE/MCP integration)
report = suggester.suggest_for_class(source_code, class_name="PaymentProcessor")
```

### New BugCategory values

The following values have been added to the `BugCategory` enum in `bug_models.py`:

| Value | Description |
|---|---|
| `assertion_misuse` | Incorrect/dangerous assert usage |
| `mutable_default_arg` | Mutable default argument (shared state across calls) |
| `late_binding_closure` | Lambda/function in loop captures loop variable by reference |
| `builtin_shadowing` | Assignment shadows a Python built-in name |
| `is_literal_comparison` | Identity comparison with non-singleton literal |
| `exception_swallowing` | Exception caught and silently discarded |
| `exception_chaining` | New exception raised in except without `from e` |
| `type_erosion` | Any annotation, cast(), type:ignore, missing return type |
| `dead_code` | Unused private method or module-level variable |
| `magic_number` | Hard-coded numeric literal should be a named constant |

### New BugDetectionConfig flags

| Flag | Default | Controls |
|---|---|---|
| `detect_assertion_misuse` | `True` | `AssertMisuseDetector` |
| `detect_division_by_zero` | `True` | `DivisionByZeroDetector` |
| `detect_python_footguns` | `True` | `PythonFootgunDetector` |
| `detect_exception_quality` | `True` | `ExceptionQualityDetector` |
| `detect_type_erosion` | `True` | `TypeErosionScanner` |
| `detect_dead_code` | `True` | `DeadCodeDetector` |
| `detect_magic_numbers` | `True` | `MagicNumbersDetector` |

### New Architecture exports

| Symbol | Module |
|---|---|
| `PatternSuggestion` | `architecture_models.py` |
| `PatternSuggestionReport` | `architecture_models.py` |
| `PatternSuggester` | `Architecture/services/pattern_suggester.py` |
| `ArchitectureAnalyzer.suggest_patterns()` | Convenience method for pattern-only analysis |
| `ArchitectureAnalyzer.analyze(..., suggest_patterns=True)` | Included in full analysis by default |
