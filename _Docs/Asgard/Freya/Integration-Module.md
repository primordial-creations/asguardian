# Freya Integration Module

## Overview

The Integration module provides unified testing orchestration, site-wide crawling with authentication support, HTML report generation, and visual baseline management.

---

## Package Structure

```
Freya/Integration/
├── __init__.py
├── models/
│   ├── __init__.py
│   └── integration_models.py
├── services/
│   ├── __init__.py
│   ├── unified_tester.py
│   ├── site_crawler.py
│   ├── html_reporter.py
│   └── baseline_manager.py
└── utilities/
    └── __init__.py
```

---

## Services

### Unified Tester

Orchestrates all test categories:

- Combines Accessibility, Visual, and Responsive testing
- Aggregates results into single report
- Severity-based filtering
- Category selection options
- Parallel test execution

### Site Crawler

Crawls and tests entire sites:

- Automatic link discovery and traversal
- SPA route handling with manual route specification
- **SPA Item Discovery**: Automatically finds and clicks list items (boards, notes, cards, etc.) to discover detail pages
- Authentication support with custom selectors
- **localStorage Token Support**: Preserves auth tokens for SPAs using token-based authentication (like Keycloak)
- Configurable depth and page limits
- Include/exclude URL patterns
- Screenshot capture per page
- Progress tracking with loading state detection

### HTML Reporter

Generates comprehensive HTML reports:

- Interactive features
- Screenshot galleries
- Before/after comparisons
- Collapsible violations
- Device preview tabs
- GAIA theme styling
- Export to PDF option

### Baseline Manager

Manages visual regression baselines:

- Baseline storage system
- Comparison workflow
- Update commands
- Versioning
- Diff reports

---

## Integration with GAIA Front-ends

### Zeus (Web)

- Full accessibility testing
- Visual regression
- Responsive breakpoints
- All viewport sizes

### Helios (Mobile)

- Touch target validation
- Mobile viewport testing
- Device-specific testing
- Orientation testing

### Harmonia (Office)

- Limited visual testing scope
- Accessibility compliance

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Browser Automation | Playwright |
| Screenshot Comparison | pixelmatch, Pillow |
| Accessibility Testing | axe-core |
| HTML Parsing | BeautifulSoup4 |
| CSS Parsing | cssutils |
| Image Processing | Pillow |
| Reporting | Jinja2 |

---

## SPA Item Discovery

The Site Crawler includes automatic discovery of clickable items in Single Page Applications. This feature:

1. **Finds List Items**: Detects clickable elements like boards, notes, cards, events, and tasks
2. **Clicks First Instance**: Clicks the first visible item of each type to trigger navigation
3. **Detects Navigation**: Waits for URL changes or modal dialogs to appear
4. **Tests Detail Pages**: Discovered detail pages are added to the crawl queue and tested

### Supported Selectors

The crawler looks for items using these patterns:

| Pattern Type | Selectors |
|--------------|-----------|
| Data-testid | `[data-testid*="item"]`, `[data-testid*="card"]`, `[data-testid*="board"]` |
| ARIA Roles | `[role="listitem"]`, `[role="row"]`, `[role="option"]` |
| CSS Classes | `.card`, `.list-item`, `.board-item`, `.note-item`, `.boards-card` |
| MUI Components | `.MuiCard-root`, `.MuiListItem-root`, `.MuiTableRow-root` |

### How It Works

```
1. Navigate to page (e.g., /boards)
2. Wait for content to load (networkidle + loading indicators)
3. For each selector pattern:
   a. Find matching elements
   b. Click first visible item
   c. Wait for navigation or modal
   d. If URL changed: add new URL to discovered pages
   e. If modal opened: record modal discovery
   f. Navigate back and continue
4. Test all discovered pages
```

### Authentication for SPAs

Zeus and similar SPAs store authentication tokens in localStorage (not cookies). The crawler:

1. Performs login on the auth page
2. Saves localStorage state after successful login
3. Restores localStorage to new pages before navigation
4. This ensures all crawled pages maintain authentication

---

## CLI Commands

### Unified Testing

```bash
# Run all tests on a URL
python -m Freya test <url>

# HTML report output
python -m Freya test <url> --format html --output report.html

# Test specific devices
python -m Freya test <url> --devices iphone-14,ipad

# Skip specific test categories
python -m Freya test <url> --skip-accessibility
python -m Freya test <url> --skip-visual
python -m Freya test <url> --skip-responsive
```

### Site Crawling

```bash
# Basic crawl
python -m Freya crawl <url>

# With depth and page limits
python -m Freya crawl <url> --depth 3 --max-pages 50

# With authentication
python -m Freya crawl <url> \
    --username user \
    --password pass \
    --login-url /login \
    --username-selector '#username' \
    --password-selector '#password' \
    --submit-selector '#login-button'

# With route specification (for SPAs)
python -m Freya crawl <url> --routes /home --routes /settings --routes /profile

# Enable/disable SPA item discovery (enabled by default)
python -m Freya crawl <url> --discover-items      # Enable (default)
python -m Freya crawl <url> --no-discover-items   # Disable

# Include/exclude patterns
python -m Freya crawl <url> --include '/app/*' --exclude '/api/*'

# Output directory
python -m Freya crawl <url> --output ./my_report
```

### Zeus Site Crawl Example

```bash
# Full Zeus crawl with authentication
python -m Freya crawl http://localhost:3000 \
    --username claudetest \
    --password "your-password" \
    --login-url http://localhost:3000/login \
    --username-selector '[data-testid="auth-login-username-input"]' \
    --password-selector '[data-testid="auth-login-password-input"]' \
    --submit-selector '[data-testid="auth-login-submit-button"]' \
    --routes /notes \
    --routes /calendar \
    --routes /boards \
    --routes /todolist \
    --routes /aichat \
    --routes /promptbuilder \
    --routes /settings \
    --depth 2 \
    --max-pages 30 \
    --output ./zeus_freya_report
```

### Baseline Management

```bash
# Update baseline for a page
python -m Freya baseline update <url> --name homepage

# Compare against baseline
python -m Freya baseline compare <url> --name homepage

# List all baselines
python -m Freya baseline list

# Delete a baseline
python -m Freya baseline delete <url> --name homepage
```

### Configuration

```bash
# Show current configuration
python -m Freya config show

# Initialize configuration file
python -m Freya config init
```

---

## Usage Example

### Unified Testing

```python
from Freya.Integration.services.unified_tester import UnifiedTester

tester = UnifiedTester()
report = tester.run_all_tests(
    url="http://localhost:3000",
    skip_visual=False,
    skip_accessibility=False,
    skip_responsive=False
)

print(f"Total issues: {report.total_issues}")
print(f"Critical: {report.critical_count}")
print(f"Score: {report.overall_score}/100")
```

### Site Crawling

```python
import asyncio
from Freya.Integration import SiteCrawler, CrawlConfig

config = CrawlConfig(
    start_url="http://localhost:3000",
    max_depth=3,
    max_pages=50,
    additional_routes=["/boards", "/notes", "/calendar"],
    discover_items=True,  # Auto-discover clickable items in SPAs
    include_patterns=[],
    exclude_patterns=["/api/*", "/static/*"],
    auth_config={
        "login_url": "http://localhost:3000/login",
        "username": "testuser",
        "password": "testpass",
        "username_selector": '[data-testid="auth-login-username-input"]',
        "password_selector": '[data-testid="auth-login-password-input"]',
        "submit_selector": '[data-testid="auth-login-submit-button"]',
    },
    output_directory="./freya_output"
)

crawler = SiteCrawler(config)

# Progress callback (optional)
def on_progress(message, current, total):
    print(f"[{current}/{total}] {message}")

crawler.set_progress_callback(on_progress)

# Run the crawl
report = asyncio.run(crawler.crawl_and_test())

# Access results
print(f"Pages discovered: {report.pages_discovered}")
print(f"Pages tested: {report.pages_tested}")
print(f"Average score: {report.average_overall_score}/100")
print(f"Critical issues: {report.total_critical}")

for page in report.page_results:
    print(f"  {page.url}: {page.overall_score}/100")
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Visual Testing
on: [push, pull_request]

jobs:
  visual-test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3

    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'

    - name: Install dependencies
      run: |
        pip install -e ./Asgard/Freya
        python -m playwright install

    - name: Run Freya tests
      run: |
        python -m Freya test http://localhost:3000 \
          --format html \
          --output freya-report.html

    - name: Upload report
      uses: actions/upload-artifact@v3
      with:
        name: freya-report
        path: freya-report.html
```

### Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

# Run visual regression on changed pages
python -m Freya baseline compare http://localhost:3000 --name homepage
if [ $? -ne 0 ]; then
    echo "Visual regression detected. Review changes before committing."
    exit 1
fi
```
