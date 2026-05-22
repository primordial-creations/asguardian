# Verdandi Web Module

## Overview

The Web module provides Core Web Vitals analysis and web performance metrics using Google's standard thresholds. It analyzes runtime performance data to rate user experience quality.

## Services

### 1. Core Web Vitals Calculator

**Purpose**: Calculates and rates Core Web Vitals metrics using Google's thresholds.

**Metrics Supported**:

| Metric | Full Name | Good | Needs Improvement | Poor |
|--------|-----------|------|-------------------|------|
| LCP | Largest Contentful Paint | <= 2500ms | <= 4000ms | > 4000ms |
| FID | First Input Delay | <= 100ms | <= 300ms | > 300ms |
| CLS | Cumulative Layout Shift | <= 0.1 | <= 0.25 | > 0.25 |
| INP | Interaction to Next Paint | <= 200ms | <= 500ms | > 500ms |
| TTFB | Time to First Byte | <= 800ms | <= 1800ms | > 1800ms |
| FCP | First Contentful Paint | <= 1800ms | <= 3000ms | > 3000ms |

**Vitals Rating Enum**:
```python
class VitalsRating(str, Enum):
    GOOD = "good"
    NEEDS_IMPROVEMENT = "needs_improvement"
    POOR = "poor"
```

**Score Calculation**:
- GOOD metric = 100/3 points each
- NEEDS_IMPROVEMENT = 50/3 points each
- POOR = 20/3 points each
- Overall score: sum of individual metric scores

**Usage**:
```python
from Verdandi.Web import CoreWebVitalsCalculator, VitalsRating

calculator = CoreWebVitalsCalculator()

# Calculate with all core metrics
result = calculator.calculate(
    lcp_ms=2500,
    fid_ms=100,
    cls=0.1
)

print(f"LCP Rating: {result.lcp_rating}")      # VitalsRating.GOOD
print(f"FID Rating: {result.fid_rating}")      # VitalsRating.GOOD
print(f"CLS Rating: {result.cls_rating}")      # VitalsRating.GOOD
print(f"Overall: {result.overall_rating}")     # VitalsRating.GOOD
print(f"Score: {result.score}/100")            # 100

# Calculate with extended metrics
result = calculator.calculate(
    lcp_ms=2500,
    fid_ms=100,
    cls=0.1,
    inp_ms=150,
    ttfb_ms=500,
    fcp_ms=1500
)

# Partial metrics (optional)
result = calculator.calculate(lcp_ms=3000)
print(f"LCP: {result.lcp_rating}")  # NEEDS_IMPROVEMENT
print(f"FID: {result.fid_rating}")  # None (not provided)
```

**Recommendations**:
The calculator generates recommendations for poor metrics:
```python
result = calculator.calculate(lcp_ms=5000, cls=0.5)
for rec in result.recommendations:
    print(rec)
# "LCP is poor (5000ms). Consider optimizing images, reducing render-blocking resources."
# "CLS is poor (0.5). Add size attributes to images/embeds, avoid inserting content above existing content."
```

---

### 2. Navigation Timing Analyzer

**Purpose**: Analyzes page load phases from Navigation Timing API data.

**Timing Phases**:
| Phase | Calculation |
|-------|-------------|
| DNS Lookup | domainLookupEnd - domainLookupStart |
| TCP Connect | connectEnd - connectStart |
| SSL/TLS | connectEnd - secureConnectionStart |
| Request | responseStart - requestStart |
| Response | responseEnd - responseStart |
| DOM Processing | domContentLoadedEventEnd - responseEnd |
| Load Event | loadEventEnd - loadEventStart |

**Key Metrics**:
- **Time to First Byte (TTFB)**: responseStart - requestStart
- **DOM Content Loaded**: domContentLoadedEventEnd - navigationStart
- **Page Load Time**: loadEventEnd - navigationStart

**Usage**:
```python
from Verdandi.Web import NavigationTimingAnalyzer

analyzer = NavigationTimingAnalyzer()

timing_data = {
    "navigationStart": 0,
    "domainLookupStart": 10,
    "domainLookupEnd": 30,
    "connectStart": 30,
    "connectEnd": 60,
    "requestStart": 60,
    "responseStart": 150,
    "responseEnd": 200,
    "domContentLoadedEventStart": 400,
    "domContentLoadedEventEnd": 450,
    "loadEventStart": 500,
    "loadEventEnd": 520
}

result = analyzer.analyze(timing_data)
print(f"DNS Lookup: {result.dns_lookup_ms}ms")
print(f"TTFB: {result.ttfb_ms}ms")
print(f"Page Load: {result.page_load_ms}ms")

# Phase breakdown
for phase, duration in result.phases.items():
    print(f"  {phase}: {duration}ms")
```

---

### 3. Resource Timing Analyzer

**Purpose**: Analyzes individual resource loading performance from Resource Timing API data.

**Resource Metrics**:
- **Fetch Start**: Time resource fetch started
- **DNS Time**: DNS lookup duration
- **Connect Time**: TCP connection duration
- **Request Time**: Time from request to first byte
- **Response Time**: Time from first byte to completion
- **Total Duration**: Total resource load time

**Resource Categories**:
- **script**: JavaScript files
- **link**: CSS stylesheets
- **img**: Images
- **font**: Web fonts
- **fetch/xmlhttprequest**: API calls
- **other**: Miscellaneous resources

**Usage**:
```python
from Verdandi.Web import ResourceTimingAnalyzer

analyzer = ResourceTimingAnalyzer()

resources = [
    {
        "name": "https://example.com/app.js",
        "initiatorType": "script",
        "startTime": 100,
        "fetchStart": 100,
        "domainLookupStart": 100,
        "domainLookupEnd": 120,
        "connectStart": 120,
        "connectEnd": 150,
        "requestStart": 150,
        "responseStart": 200,
        "responseEnd": 400,
        "transferSize": 150000,
        "encodedBodySize": 140000,
        "decodedBodySize": 500000
    },
    # ... more resources
]

result = analyzer.analyze(resources)

print(f"Total Resources: {result.total_count}")
print(f"Total Size: {result.total_size_bytes / 1024:.1f}KB")
print(f"Total Duration: {result.total_duration_ms}ms")

# By category
for category, stats in result.by_category.items():
    print(f"\n{category}:")
    print(f"  Count: {stats.count}")
    print(f"  Size: {stats.total_size_bytes / 1024:.1f}KB")
    print(f"  Avg Duration: {stats.avg_duration_ms:.1f}ms")

# Slowest resources
print("\nSlowest Resources:")
for resource in result.slowest_resources[:5]:
    print(f"  {resource.name}: {resource.duration_ms}ms")
```

---

## CLI Usage

```bash
# Core Web Vitals calculation
python -m Verdandi web vitals --lcp=2500 --fid=100 --cls=0.1
python -m Verdandi web vitals --lcp=2500 --fid=100 --cls=0.1 --inp=200 --ttfb=800

# Navigation timing analysis
python -m Verdandi web navigation timing_data.json
python -m Verdandi web navigation timing.json --format=json

# Resource timing analysis
python -m Verdandi web resources resource_timing.json
python -m Verdandi web resources data.json --top=10 --format=markdown
```

---

## Models Reference

### CoreWebVitalsInput
```python
class CoreWebVitalsInput(BaseModel):
    lcp_ms: Optional[float] = None    # Largest Contentful Paint
    fid_ms: Optional[float] = None    # First Input Delay
    cls: Optional[float] = None       # Cumulative Layout Shift
    inp_ms: Optional[float] = None    # Interaction to Next Paint
    ttfb_ms: Optional[float] = None   # Time to First Byte
    fcp_ms: Optional[float] = None    # First Contentful Paint
```

### WebVitalsResult
```python
class WebVitalsResult(BaseModel):
    lcp_rating: Optional[VitalsRating] = None
    fid_rating: Optional[VitalsRating] = None
    cls_rating: Optional[VitalsRating] = None
    inp_rating: Optional[VitalsRating] = None
    ttfb_rating: Optional[VitalsRating] = None
    fcp_rating: Optional[VitalsRating] = None
    overall_rating: VitalsRating
    score: int  # 0-100
    recommendations: List[str]
```

### NavigationTimingResult
```python
class NavigationTimingResult(BaseModel):
    dns_lookup_ms: float
    tcp_connect_ms: float
    ssl_tls_ms: Optional[float]
    request_ms: float
    response_ms: float
    dom_processing_ms: float
    load_event_ms: float
    ttfb_ms: float
    dom_content_loaded_ms: float
    page_load_ms: float
    phases: Dict[str, float]
```

### ResourceTimingResult
```python
class ResourceTimingResult(BaseModel):
    total_count: int
    total_size_bytes: int
    total_duration_ms: float
    by_category: Dict[str, ResourceCategoryStats]
    slowest_resources: List[ResourceInfo]
    largest_resources: List[ResourceInfo]
```

---

## Google Thresholds Reference

### Core Web Vitals (Required for Search Ranking)

| Metric | Good | Needs Improvement | Poor |
|--------|------|-------------------|------|
| LCP | <= 2.5s | <= 4.0s | > 4.0s |
| FID | <= 100ms | <= 300ms | > 300ms |
| CLS | <= 0.1 | <= 0.25 | > 0.25 |

### Additional Web Vitals

| Metric | Good | Needs Improvement | Poor |
|--------|------|-------------------|------|
| INP | <= 200ms | <= 500ms | > 500ms |
| TTFB | <= 800ms | <= 1800ms | > 1800ms |
| FCP | <= 1.8s | <= 3.0s | > 3.0s |

**Note**: INP (Interaction to Next Paint) replaced FID as a Core Web Vital in March 2024.
