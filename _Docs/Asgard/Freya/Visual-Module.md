# Freya Visual Module

## Overview

The Visual module provides screenshot capture, visual regression detection, layout validation, and style consistency checking.

---

## Package Structure

```
Freya/Visual/
├── __init__.py
├── models/
│   ├── __init__.py
│   └── visual_models.py
├── services/
│   ├── __init__.py
│   ├── screenshot_capture.py
│   ├── visual_regression.py
│   ├── layout_validator.py
│   └── style_validator.py
└── utilities/
    ├── __init__.py
    └── image_utils.py
```

---

## Services

### Screenshot Capture

Automated screenshot generation:

- Full page screenshots
- Element-specific screenshots
- Viewport-based capture
- Multiple device emulation
- Timestamp-based naming
- Baseline management

### Visual Regression

Detect unintended visual changes:

- Pixel-by-pixel comparison
- Perceptual diff (pixelmatch)
- Anti-aliasing tolerance
- Threshold-based detection
- Diff image generation
- Change highlighting

### Layout Validator

Ensure consistent element positioning:

- Element position validation
- Spacing consistency
- Alignment checking
- Overflow detection
- Z-index conflicts
- Grid/flexbox validation

### Style Validator

Validate CSS consistency:

- Theme consistency checking
- CSS variable usage
- Color palette adherence
- Typography consistency
- Spacing system adherence
- Shadow/border consistency

---

## Visual Diff Methods

### Pixel-by-Pixel

- Exact match required
- Fast but sensitive to anti-aliasing
- Good for exact reproducibility

### Perceptual Diff

- Uses pixelmatch algorithm
- Ignores anti-aliasing differences
- Configurable threshold (default: 0.1)

### Structural (DOM-based)

- Compares DOM structure
- Ignores styling differences
- Good for content verification

---

## Models

### DiffResult

Represents visual comparison results:
- Match percentage
- Diff pixel count
- Diff image path
- Threshold used

### ScreenshotConfig

Configuration for screenshot capture:
- Viewport dimensions
- Device emulation
- Full page vs viewport
- Element selector

### LayoutIssue

Represents layout problems:
- Issue type (overflow, alignment, spacing)
- Affected element
- Expected vs actual values
- Severity

### VisualReport

Aggregated visual test report:
- Screenshots captured
- Regressions detected
- Layout issues found
- Style violations

---

## CLI Commands

```bash
# Capture screenshots
python -m Freya visual capture <url>

# Compare two images
python -m Freya visual compare <baseline> <current>

# Layout validation
python -m Freya visual layout <url>

# Style consistency check
python -m Freya visual style <url>

# Options
--threshold <0.0-1.0>    # Diff threshold
--output <directory>     # Output directory
--full-page              # Full page screenshot
--selector <css>         # Element selector
```

---

## Usage Example

```python
from Freya.Visual.services.visual_regression import VisualRegression

regression = VisualRegression()

# Capture baseline
baseline = regression.capture("http://localhost:3000", name="homepage")

# Later, compare against baseline
result = regression.compare(baseline, "http://localhost:3000")

if result.has_differences:
    print(f"Visual regression detected: {result.diff_percentage}% different")
    print(f"Diff image saved to: {result.diff_image_path}")
```

---

## Technology

Zero heavy dependencies: no Pillow, no pixelmatch library.

- **Playwright** for browser automation and screenshots
- **Pure-Python PNG codec + pixel-diff/SSIM/pHash** (`Visual/services/image_ops.py`) for image comparison — a hand-rolled equivalent of Pillow + pixelmatch
