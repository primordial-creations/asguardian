# Freya - Visual/UI Testing Package

## Overview

Freya is GAIA's visual and UI testing package. Named after the Norse goddess of beauty, Freya provides comprehensive testing for what users SEE and experience, complementing Heimdall's code quality analysis.

## Why a Separate Package?

Freya is separate from Heimdall because:

1. **Different Domain**: Tests what users SEE, not code structure
2. **Different Tools**: Requires Playwright, screenshot comparison, visual regression
3. **Different Execution Model**: Requires running apps/browsers
4. **Different Dependencies**: Heavy on UI automation libraries

## Why "Freya"?

- **Goddess of Beauty** - Perfect for visual testing
- **Associated with fertility and abundance** - Ensuring rich, complete UI experiences
- **Single deity name** - Matches GAIA patterns (Iris, Athena, Themis, Heimdall)

---

## Package Structure

```
Asgard/
└── Freya/
    ├── setup.py
    ├── pyproject.toml
    ├── README.md
    └── Freya/
        ├── __init__.py
        ├── __main__.py
        ├── cli.py
        │
        ├── Accessibility/              # WCAG Compliance Testing
        │   ├── __init__.py
        │   ├── models/
        │   │   └── accessibility_models.py
        │   ├── services/
        │   │   ├── wcag_validator.py       # WCAG 2.1 compliance
        │   │   ├── color_contrast.py       # Color contrast checking
        │   │   ├── keyboard_nav.py         # Keyboard navigation testing
        │   │   ├── screen_reader.py        # Screen reader compatibility
        │   │   └── aria_validator.py       # ARIA attribute validation
        │   └── utilities/
        │
        ├── Visual/                     # Visual Testing
        │   ├── __init__.py
        │   ├── models/
        │   │   └── visual_models.py
        │   ├── services/
        │   │   ├── screenshot_capture.py   # Screenshot automation
        │   │   ├── visual_regression.py    # Visual diff detection
        │   │   ├── layout_validator.py     # Layout consistency
        │   │   └── style_validator.py      # CSS consistency
        │   └── utilities/
        │       └── image_utils.py
        │
        ├── Responsive/                 # Responsive Design Testing
        │   ├── __init__.py
        │   ├── models/
        │   │   └── responsive_models.py
        │   ├── services/
        │   │   ├── breakpoint_tester.py    # Breakpoint testing
        │   │   ├── touch_targets.py        # Touch target validation
        │   │   ├── viewport_tester.py      # Viewport testing
        │   │   └── mobile_compat.py        # Mobile compatibility
        │   └── utilities/
        │
        └── Integration/                # Unified Testing & Site Crawling
            ├── __init__.py
            ├── models/
            │   └── integration_models.py
            ├── services/
            │   ├── unified_tester.py       # Combined test orchestration
            │   ├── site_crawler.py         # Site-wide crawling and testing
            │   ├── html_reporter.py        # HTML report generation
            │   └── baseline_manager.py     # Visual baseline management
            └── utilities/
```

---

## Submodule Overview

| Submodule | Purpose | Services |
|-----------|---------|----------|
| Accessibility | WCAG 2.1 compliance, contrast, keyboard, ARIA | 5 validators |
| Visual | Screenshots, regression, layout, style | 4 services |
| Responsive | Breakpoints, touch targets, viewport, mobile | 4 testers |
| Integration | Unified testing, site crawling, reporting | 4 services |

---

## Features

### Accessibility Module

| Service | Purpose |
|---------|---------|
| WCAG Validator | Validate WCAG 2.1 Level A/AA/AAA compliance |
| Color Contrast | Check color contrast ratios (4.5:1, 3:1 requirements) |
| Keyboard Navigation | Test full keyboard accessibility |
| Screen Reader | Validate screen reader compatibility |
| ARIA Validator | Validate ARIA roles, states, and properties |

**WCAG Levels**:
- **Level A**: Basic web accessibility
- **Level AA**: Standard compliance (recommended)
- **Level AAA**: Enhanced accessibility

### Visual Module

| Service | Purpose |
|---------|---------|
| Screenshot Capture | Automated screenshot generation |
| Visual Regression | Detect unintended visual changes |
| Layout Validator | Ensure consistent element positioning |
| Style Validator | Validate CSS consistency and theme adherence |

**Visual Diff Methods**:
- Pixel-by-pixel comparison
- Perceptual diff (ignores anti-aliasing differences)
- Structural comparison (DOM-based)

### Responsive Module

| Service | Purpose |
|---------|---------|
| Breakpoint Tester | Test layouts at defined breakpoints |
| Touch Targets | Validate minimum touch target sizes (44x44px) |
| Viewport Tester | Test various viewport sizes |
| Mobile Compatibility | Test mobile-specific features |

**Standard Breakpoints**:
- Mobile: 320px, 375px, 414px
- Tablet: 768px, 1024px
- Desktop: 1280px, 1440px, 1920px

### Integration Module

| Service | Purpose |
|---------|---------|
| Unified Tester | Orchestrate all test categories together |
| Site Crawler | Crawl and test entire sites with authentication |
| HTML Reporter | Generate comprehensive HTML test reports |
| Baseline Manager | Manage visual regression baselines |

**Crawl Features**:
- Automatic link discovery and traversal
- SPA route handling with manual route specification
- Authentication support with custom selectors
- Configurable depth and page limits
- Include/exclude URL patterns
- Screenshot capture per page

---

## CLI Interface

```bash
# Main entry point
python -m Freya <command> [options]

# Accessibility testing
python -m Freya accessibility audit <url>           # Full accessibility audit
python -m Freya accessibility contrast <url>        # Color contrast check
python -m Freya accessibility keyboard <url>        # Keyboard navigation test
python -m Freya accessibility aria <url>            # ARIA validation
python -m Freya accessibility screen-reader <url>   # Screen reader compatibility

# Visual testing
python -m Freya visual capture <url>                # Capture screenshots
python -m Freya visual compare <baseline> <current> # Visual diff
python -m Freya visual layout <url>                 # Layout validation
python -m Freya visual style <url>                  # Style consistency

# Responsive testing
python -m Freya responsive breakpoints <url>        # Test all breakpoints
python -m Freya responsive touch <url>              # Touch target validation
python -m Freya responsive viewport <url>           # Viewport testing
python -m Freya responsive mobile <url>             # Mobile compatibility

# Site crawling
python -m Freya crawl <url>                         # Crawl and test entire site
python -m Freya crawl <url> --depth 3 --max-pages 50
python -m Freya crawl <url> --username user --password pass --login-url /login

# Baseline management
python -m Freya baseline update <url> --name homepage
python -m Freya baseline compare <url> --name homepage
python -m Freya baseline list
python -m Freya baseline delete <url> --name homepage

# Unified testing
python -m Freya test <url>                          # Run ALL tests
python -m Freya test <url> --format html            # HTML report
python -m Freya test <url> --skip-accessibility     # Skip specific tests
```

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Browser Automation | Playwright |
| Screenshot Comparison | Pillow, pixelmatch |
| Accessibility Testing | axe-core (via playwright-axe) |
| HTML Parsing | BeautifulSoup4 |
| CSS Parsing | cssutils |

---

## Integration Points

### With Heimdall
- Share file discovery utilities
- Coordinate exclude patterns
- Unified reporting format

### With GAIA Front-ends
- Zeus (Web): Primary target for visual testing
- Helios (Mobile): Responsive and touch testing
- Harmonia (Office): Limited visual testing scope

### With CI/CD
- Pre-commit hooks for visual regression
- PR checks for accessibility compliance
- Baseline management for visual comparison

---

## Asgard Organization

Heimdall and Freya are now organized under the "Asgard" umbrella folder, following the Norse mythology theme:

```
Asgard/
├── Heimdall/    # Code quality analysis
├── Freya/       # Visual/UI testing
├── Tyr/         # Legal/compliance (potential future)
└── Bragi/       # Documentation quality (potential future)
```

---

## Implementation Status

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | COMPLETE | Foundation, Accessibility module |
| Phase 2 | COMPLETE | Visual module |
| Phase 3 | COMPLETE | Responsive module |
| Phase 4 | COMPLETE | Integration module, CLI, site crawler |

---

## Testing

Freya is tested through the Hercules Testing Framework with comprehensive L0 Quality Assurance tests.

### Test Location

```
Hercules/tests/L0_unit/freya/
├── __init__.py
├── test_cli.py                          # CLI parser and commands
├── accessibility/
│   ├── __init__.py
│   └── test_wcag_validator.py           # WCAG validation, severity levels
├── visual/
│   ├── __init__.py
│   └── test_visual_regression.py        # Visual comparison, diff detection
├── responsive/
│   ├── __init__.py
│   └── test_viewport_tester.py          # Viewport testing, issue detection
└── integration/
    ├── __init__.py
    └── test_site_crawler.py             # Site crawling, config, progress
```

### Running Freya Tests

```bash
# Run all Freya L0 tests
python -m pytest Hercules/tests/L0_unit/freya -v

# Run with freya marker
python -m pytest -m freya

# Run specific module tests
python -m pytest Hercules/tests/L0_unit/freya/accessibility -v
python -m pytest Hercules/tests/L0_unit/freya/visual -v
python -m pytest Hercules/tests/L0_unit/freya/responsive -v
python -m pytest Hercules/tests/L0_unit/freya/integration -v
```

### Test Markers

Tests use the following pytest markers:
- `@pytest.mark.L0` - Quality Assurance level
- `@pytest.mark.freya` - Freya module
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.fast` - Fast execution tests
