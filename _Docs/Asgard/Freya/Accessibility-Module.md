# Freya Accessibility Module

## Overview

The Accessibility module provides WCAG 2.1 compliance testing, color contrast validation, keyboard navigation testing, screen reader compatibility checks, and ARIA attribute validation.

---

## Package Structure

```
Freya/Accessibility/
├── __init__.py
├── models/
│   ├── __init__.py
│   └── accessibility_models.py
├── services/
│   ├── __init__.py
│   ├── wcag_validator.py
│   ├── color_contrast.py
│   ├── keyboard_nav.py
│   ├── screen_reader.py
│   └── aria_validator.py
└── utilities/
    ├── __init__.py
    └── a11y_utils.py
```

---

## Services

### WCAG Validator

Validates WCAG 2.1 compliance across all guidelines:

| Guideline | Category | Description |
|-----------|----------|-------------|
| 1.1 | Perceivable | Text alternatives for non-text content |
| 1.2 | Perceivable | Time-based media alternatives |
| 1.3 | Perceivable | Adaptable content structure |
| 1.4 | Perceivable | Distinguishable content |
| 2.1 | Operable | Keyboard accessible |
| 2.2 | Operable | Enough time for interaction |
| 2.3 | Operable | Seizure prevention |
| 2.4 | Operable | Navigable content |
| 2.5 | Operable | Input modalities |
| 3.1 | Understandable | Readable content |
| 3.2 | Understandable | Predictable behavior |
| 3.3 | Understandable | Input assistance |
| 4.1 | Robust | Compatible with assistive tech |

### Color Contrast Checker

Validates color contrast ratios per WCAG requirements:

| Level | Normal Text | Large Text |
|-------|-------------|------------|
| AA | 4.5:1 | 3:1 |
| AAA | 7:1 | 4.5:1 |

**Features**:
- Color parsing (hex, rgb, hsl)
- Foreground/background detection
- Contrast ratio calculation
- Recommendations for failing elements

### Keyboard Navigation Tester

Tests keyboard accessibility:

- Focus order validation
- Keyboard trap detection
- Skip link presence
- Focus visibility
- Tab index validation

### Screen Reader Compatibility

Validates screen reader support:

- Alt text presence
- ARIA label validation
- Heading hierarchy
- Landmark regions
- Form label association
- Live region validation

### ARIA Validator

Validates ARIA implementation:

- Valid ARIA roles
- Required ARIA attributes
- Valid ARIA values
- ARIA state management
- Role/attribute compatibility

---

## Models

### WCAGLevel

```python
class WCAGLevel(Enum):
    A = "A"
    AA = "AA"
    AAA = "AAA"
```

### ViolationSeverity

```python
class ViolationSeverity(Enum):
    CRITICAL = "critical"
    SERIOUS = "serious"
    MODERATE = "moderate"
    MINOR = "minor"
```

### AccessibilityViolation

Represents a single accessibility violation with:
- Violation ID
- Description
- Impact level
- Affected elements
- Remediation suggestions

### AccessibilityReport

Aggregated report containing:
- All violations found
- Pass/fail counts
- WCAG level compliance status
- Overall accessibility score

---

## CLI Commands

```bash
# Full accessibility audit
python -m Freya accessibility audit <url>

# Color contrast check
python -m Freya accessibility contrast <url>

# Keyboard navigation test
python -m Freya accessibility keyboard <url>

# ARIA validation
python -m Freya accessibility aria <url>

# Screen reader compatibility
python -m Freya accessibility screen-reader <url>

# Options
--level [A|AA|AAA]     # WCAG compliance level
--format [text|json|markdown|html]
--output <file>
```

---

## Usage Example

```python
from Freya.Accessibility.services.wcag_validator import WCAGValidator
from Freya.Accessibility.models.accessibility_models import WCAGLevel

validator = WCAGValidator()
report = validator.validate("http://localhost:3000", level=WCAGLevel.AA)

print(f"Violations found: {len(report.violations)}")
for violation in report.violations:
    print(f"  [{violation.severity}] {violation.description}")
```

---

## Technology

Zero heavy dependencies: no axe-core / playwright-axe, no BeautifulSoup4.

- **Custom JS-injected heuristic checks**, run in-page via Playwright, for automated accessibility testing
- **Playwright** for browser automation and DOM inspection (no BeautifulSoup4)

Coverage note: these heuristics cover an estimated ~20-30% of WCAG success criteria (pending RESEARCH_01 calibration) — this is lab-data automated coverage, a tripwire, not a substitute for manual/assistive-technology testing or a full WCAG audit.
