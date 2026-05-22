# Freya Responsive Module

## Overview

The Responsive module provides breakpoint testing, touch target validation, viewport testing, and mobile compatibility checks.

---

## Package Structure

```
Freya/Responsive/
├── __init__.py
├── models/
│   ├── __init__.py
│   └── responsive_models.py
├── services/
│   ├── __init__.py
│   ├── breakpoint_tester.py
│   ├── touch_targets.py
│   ├── viewport_tester.py
│   └── mobile_compat.py
└── utilities/
    ├── __init__.py
    └── device_profiles.py
```

---

## Services

### Breakpoint Tester

Test layouts at defined breakpoints:

- Standard breakpoint testing
- Custom breakpoint support
- Content reflow validation
- Navigation adaptation
- Image responsiveness
- Typography scaling
- Screenshot at each breakpoint

### Touch Target Validator

Validate touch target sizes:

- Minimum size validation (44x44px)
- Spacing between targets (8px)
- Clickable element detection
- Touch target overlap detection
- Gesture area validation

### Viewport Tester

Test viewport configuration:

- Viewport meta tag validation
- Initial scale settings
- User-scalable settings
- Maximum/minimum scale
- Viewport units usage
- Content overflow detection
- Orientation changes

### Mobile Compatibility

Test mobile-specific features:

- Mobile-specific CSS validation
- Touch event support
- Mobile navigation patterns
- PWA requirements
- Performance on mobile
- Network simulation

---

## Standard Breakpoints

| Name | Width | Common Devices |
|------|-------|----------------|
| xs | 320px | iPhone SE |
| sm | 375px | iPhone 12/13/14 |
| md | 414px | iPhone Plus/Max |
| lg | 768px | iPad Portrait |
| xl | 1024px | iPad Landscape |
| 2xl | 1280px | Small laptop |
| 3xl | 1440px | Standard laptop |
| 4xl | 1920px | Desktop |

---

## Touch Target Guidelines

| Element | Minimum Size | Spacing |
|---------|--------------|---------|
| Buttons | 44x44px | 8px |
| Links | 44x44px | 8px |
| Inputs | 44px height | 8px |
| Icons | 44x44px | 8px |

These guidelines follow WCAG 2.1 Success Criterion 2.5.5 (Target Size) and Apple Human Interface Guidelines.

---

## Device Profiles

Built-in device profiles include:

**Mobile**:
- iPhone SE (375x667)
- iPhone 12/13/14 (390x844)
- iPhone 14 Pro Max (430x932)
- Samsung Galaxy S21 (360x800)
- Pixel 7 (412x915)

**Tablet**:
- iPad Mini (768x1024)
- iPad (820x1180)
- iPad Pro 11" (834x1194)
- iPad Pro 12.9" (1024x1366)

**Desktop**:
- 1280x720 (HD)
- 1440x900 (Standard)
- 1920x1080 (Full HD)
- 2560x1440 (QHD)

---

## Models

### Breakpoint

```python
@dataclass
class Breakpoint:
    name: str
    width: int
    height: Optional[int] = None
```

### DeviceProfile

```python
@dataclass
class DeviceProfile:
    name: str
    width: int
    height: int
    device_scale_factor: float = 1.0
    is_mobile: bool = False
    has_touch: bool = False
```

### TouchTargetIssue

Represents touch target problems:
- Element selector
- Current size
- Required size
- Spacing issues

### ResponsiveReport

Aggregated responsive test report:
- Breakpoint results
- Touch target issues
- Viewport issues
- Mobile compatibility status

---

## CLI Commands

```bash
# Test all breakpoints
python -m Freya responsive breakpoints <url>

# Touch target validation
python -m Freya responsive touch <url>

# Viewport testing
python -m Freya responsive viewport <url>

# Mobile compatibility
python -m Freya responsive mobile <url>

# Options
--breakpoints <320,768,1024>  # Custom breakpoints
--device <iphone-14>          # Specific device profile
--format [text|json|markdown|html]
```

---

## Usage Example

```python
from Freya.Responsive.services.breakpoint_tester import BreakpointTester

tester = BreakpointTester()

# Test all standard breakpoints
results = tester.test_breakpoints("http://localhost:3000")

for breakpoint, result in results.items():
    print(f"{breakpoint.name} ({breakpoint.width}px):")
    print(f"  Issues: {len(result.issues)}")
    print(f"  Screenshot: {result.screenshot_path}")
```

---

## Technology

- **Playwright** for browser automation and device emulation
- Device emulation for accurate mobile testing
- Network throttling for realistic mobile conditions
