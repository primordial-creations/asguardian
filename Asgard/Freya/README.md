# Freya - Visual and UI Testing

Named after the Norse goddess of love and beauty, Freya provides comprehensive visual and UI testing capabilities for web applications. Like its namesake who values beauty and harmony, Freya ensures your user interfaces are visually stunning, accessible, and provide excellent user experiences.

## Overview

Freya is a visual and UI testing package that validates accessibility compliance, visual regression, responsive design, and overall user experience. It provides automated testing using Playwright to ensure web applications meet WCAG standards and provide consistent, beautiful interfaces across devices.

## Features

- **Accessibility Testing**: WCAG 2.1 compliance (A, AA, AAA), color contrast validation, keyboard navigation, screen reader compatibility, ARIA validation
- **Visual Testing**: Screenshot capture, visual regression detection, layout validation, style consistency checking
- **Responsive Testing**: Breakpoint validation, touch target sizing, viewport behavior, mobile compatibility
- **Unified Testing**: Comprehensive test suites with HTML reports, baseline management, automated site crawling

## Installation

```bash
pip install -e /path/to/Asgard
playwright install chromium
```

Or install directly:

```bash
cd /path/to/Asgard
pip install .
playwright install chromium
```

## Quick Start

### CLI Usage

```bash
# Run comprehensive test suite
python -m Freya test https://example.com

# Accessibility testing
python -m Freya accessibility audit https://example.com --level AA
python -m Freya accessibility contrast https://example.com
python -m Freya accessibility keyboard https://example.com
python -m Freya accessibility aria https://example.com

# Visual testing
python -m Freya visual capture https://example.com --output screenshot.png
python -m Freya visual compare baseline.png current.png --threshold 0.95
python -m Freya visual layout https://example.com
python -m Freya visual style https://example.com

# Responsive testing
python -m Freya responsive breakpoints https://example.com
python -m Freya responsive touch https://example.com --min-size 44
python -m Freya responsive viewport https://example.com
python -m Freya responsive mobile https://example.com --devices iphone-14 pixel-7

# Baseline management
python -m Freya baseline update https://example.com --name homepage
python -m Freya baseline compare https://example.com --name homepage
python -m Freya baseline list

# Site crawling and testing
python -m Freya crawl https://example.com --depth 3 --max-pages 50
```

### Python API Usage

```python
import asyncio
from Asgard.Freya import (
    WCAGValidator,
    AccessibilityConfig,
    WCAGLevel,
    ScreenshotCapture,
    VisualRegressionTester,
    BreakpointTester,
    UnifiedTester,
)

async def test_accessibility():
    # WCAG Accessibility Validation
    config = AccessibilityConfig(wcag_level=WCAGLevel.AA)
    validator = WCAGValidator(config)
    result = await validator.validate("https://example.com")

    print(f"Accessibility Score: {result.score:.1f}%")
    print(f"Violations: {result.total_violations}")
    for violation in result.violations:
        print(f"  - {violation.description}")

async def test_visual():
    # Screenshot Capture
    capture = ScreenshotCapture(output_directory="./screenshots")
    screenshot = await capture.capture_viewport("https://example.com")
    print(f"Screenshot saved: {screenshot.file_path}")

    # Visual Regression
    tester = VisualRegressionTester(threshold=0.05)
    comparison = tester.compare("baseline.png", "current.png")
    print(f"Match: {not comparison.has_difference}")
    print(f"Difference: {comparison.difference_percentage:.2f}%")

async def test_responsive():
    # Breakpoint Testing
    tester = BreakpointTester()
    result = await tester.test("https://example.com")
    print(f"Breakpoints tested: {len(result.breakpoints_tested)}")
    print(f"Issues found: {result.total_issues}")

async def test_unified():
    # Comprehensive Testing
    tester = UnifiedTester()
    result = await tester.test("https://example.com")
    print(f"Overall Score: {result.overall_score:.1f}/100")
    print(f"Accessibility: {result.accessibility_score:.1f}/100")
    print(f"Visual: {result.visual_score:.1f}/100")
    print(f"Responsive: {result.responsive_score:.1f}/100")

# Run tests
asyncio.run(test_accessibility())
asyncio.run(test_visual())
asyncio.run(test_responsive())
asyncio.run(test_unified())
```

## Submodules

### Accessibility Module

WCAG 2.1 compliance testing and accessibility validation.

**Services:**
- `WCAGValidator`: Complete WCAG compliance validation
- `ColorContrastChecker`: Color contrast ratio validation (AA/AAA)
- `KeyboardNavigationTester`: Keyboard accessibility testing
- `ScreenReaderValidator`: Screen reader compatibility validation
- `ARIAValidator`: ARIA implementation validation

**Key Features:**
- WCAG 2.1 Level A, AA, AAA compliance
- Automated violation detection with suggested fixes
- Element-level reporting with CSS selectors
- Severity classification (Critical, Serious, Moderate, Minor)

### Visual Module

Visual regression testing and layout validation.

**Services:**
- `ScreenshotCapture`: Screenshot capture with device emulation
- `VisualRegressionTester`: Pixel-by-pixel comparison
- `LayoutValidator`: Layout consistency validation
- `StyleValidator`: Style consistency checking

**Key Features:**
- Full-page and viewport screenshots
- Device emulation (mobile, tablet, desktop)
- Diff image generation
- Similarity threshold configuration

### Responsive Module

Responsive design testing across devices and breakpoints.

**Services:**
- `BreakpointTester`: Breakpoint behavior validation
- `TouchTargetValidator`: Touch target size validation
- `ViewportTester`: Viewport configuration testing
- `MobileCompatibilityTester`: Mobile device compatibility

**Key Features:**
- Common breakpoints (mobile, tablet, desktop, 4K)
- Touch target size validation (minimum 44x44px)
- Horizontal scroll detection
- Device-specific testing

### Integration Module

Unified testing framework and reporting.

**Services:**
- `UnifiedTester`: Combined accessibility, visual, and responsive testing
- `HTMLReporter`: Comprehensive HTML report generation
- `BaselineManager`: Visual baseline management
- `SiteCrawler`: Automated site crawling and testing
- `PlaywrightUtils`: Playwright helper utilities

**Key Features:**
- Single command for all tests
- HTML and JSON report formats
- Baseline capture and comparison
- Automated site discovery and crawling

## CLI Commands Reference

| Command | Description | Example |
|---------|-------------|---------|
| `test` | Run all tests | `python -m Freya test https://example.com` |
| `accessibility audit` | Full accessibility audit | `python -m Freya accessibility audit https://example.com` |
| `accessibility contrast` | Check color contrast | `python -m Freya accessibility contrast https://example.com` |
| `accessibility keyboard` | Test keyboard navigation | `python -m Freya accessibility keyboard https://example.com` |
| `accessibility aria` | Validate ARIA | `python -m Freya accessibility aria https://example.com` |
| `accessibility screen-reader` | Test screen reader | `python -m Freya accessibility screen-reader https://example.com` |
| `visual capture` | Capture screenshot | `python -m Freya visual capture https://example.com -o shot.png` |
| `visual compare` | Compare screenshots | `python -m Freya visual compare baseline.png current.png` |
| `visual layout` | Validate layout | `python -m Freya visual layout https://example.com` |
| `visual style` | Check style consistency | `python -m Freya visual style https://example.com` |
| `responsive breakpoints` | Test breakpoints | `python -m Freya responsive breakpoints https://example.com` |
| `responsive touch` | Validate touch targets | `python -m Freya responsive touch https://example.com` |
| `responsive viewport` | Test viewport | `python -m Freya responsive viewport https://example.com` |
| `responsive mobile` | Mobile compatibility | `python -m Freya responsive mobile https://example.com` |
| `baseline update` | Create/update baseline | `python -m Freya baseline update https://example.com --name home` |
| `baseline compare` | Compare to baseline | `python -m Freya baseline compare https://example.com --name home` |
| `baseline list` | List all baselines | `python -m Freya baseline list` |
| `baseline delete` | Delete baseline | `python -m Freya baseline delete https://example.com --name home` |
| `crawl` | Crawl and test site | `python -m Freya crawl https://example.com --depth 3` |

## Configuration Options

### Common Options

- `--level, -l`: WCAG level (A, AA, AAA) - default: AA
- `--format, -f`: Output format (text, json, markdown, html) - default: text
- `--output, -o`: Output file path
- `--severity, -s`: Minimum severity to report (critical, serious, moderate, minor)
- `--verbose, -v`: Verbose output

### Crawl Options

- `--depth, -d`: Maximum crawl depth (default: 3)
- `--max-pages, -m`: Maximum pages to crawl (default: 100)
- `--delay`: Delay between requests in seconds (default: 0.5)
- `--routes`: Additional routes to test (for SPAs)
- `--username`: Username for authentication
- `--password`: Password for authentication
- `--headless`: Run in headless mode (default: true)
- `--concurrency`: Bounded worker concurrency for the crawl test phase (default: 4)
- `--concurrency-discovery`: Bounded sibling-fetch concurrency during discovery (default: 2)
- `--min-request-interval-ms`: Minimum per-host interval between requests, in ms (default: 500)
- `--gate` / `--no-gate`: Evaluate the CI quality gate (default: on) or run report-only

### `.freyarc` Config File

`freya config init` writes a commented default `.freyarc` to the current directory. Discovery order: `--config PATH` > `./.freyarc` > `./freya.yaml` > built-in defaults. CLI flags always override values loaded from a config file.

```bash
freya config init        # write a default .freyarc
freya config show         # print the merged effective config, with source annotations
freya config validate     # validate a config file, reporting Pydantic errors with context
```

### CI Quality Gate Exit Codes

`freya crawl` (and other gated commands) use distinct exit codes so pipelines can tell a real failure from a flake:

| Code | Meaning |
|------|---------|
| `0` | Gate passed (or `--no-gate` report-only mode with no crawl errors) |
| `1` | Gate failed (fail_on severities present, grade below `min_grade`, or findings over `max_findings`) |
| `2` | Inconclusive — e.g. every page errored during the crawl, so there is nothing to grade |

## Troubleshooting

### Common Issues

**Issue: "Browser not installed"**
```bash
playwright install chromium
```

**Issue: "Page timeout"**
- Increase timeout in code: `config.page_timeout = 60000`
- Check if site is accessible
- Try with `--no-headless` to see what's happening

**Issue: "Authentication required"**
```bash
python -m Freya crawl https://example.com \
  --username user@example.com \
  --password secret \
  --login-url https://example.com/login
```

**Issue: "Out of memory during crawl"**
- Reduce `--max-pages`
- Reduce `--depth`
- Add `--exclude` patterns for large assets

### Performance Tips

- Use `--headless` mode for faster execution
- Limit crawl depth and pages in large sites
- Exclude static assets and API endpoints
- Run visual regression only on critical pages
- Use baseline comparison to detect changes quickly

## Output Formats

### Text Output
Human-readable console output with color coding and formatting.

### JSON Output
Machine-readable JSON for integration with other tools.

### HTML Output
Comprehensive HTML report with charts, screenshots, and detailed findings.

### Markdown Output
Documentation-friendly markdown format for inclusion in README files.

## Integration with CI/CD

```yaml
# GitHub Actions example
- name: Install Playwright
  run: playwright install chromium

- name: Run Freya Accessibility Tests
  run: |
    python -m Freya accessibility audit https://staging.example.com \
      --level AA \
      --format json \
      --output freya-report.json

- name: Upload Report
  uses: actions/upload-artifact@v3
  with:
    name: freya-report
    path: freya-report.json
```

## Best Practices

1. **Accessibility First**: Always test for WCAG AA compliance at minimum
2. **Baseline Management**: Create baselines for critical pages
3. **Incremental Testing**: Test on every pull request
4. **Mobile First**: Always include mobile devices in responsive tests
5. **Crawl Strategically**: Use focused crawls with appropriate depth
6. **Automate Reports**: Generate HTML reports for stakeholder visibility

## Version

Version is managed dynamically via setuptools-scm; see package metadata (`pip show asguardian`) for the installed version. Requires Python >= 3.11.

## Author

Asgard Contributors
