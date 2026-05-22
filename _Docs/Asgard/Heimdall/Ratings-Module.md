# Heimdall Ratings Module

## Overview

The Ratings module calculates A-E letter ratings across three quality dimensions — Maintainability, Reliability, and Security — from existing Heimdall analysis reports. An overall rating is derived as the worst of the three dimensions.

## Rating Scale

| Rating | Description |
|--------|-------------|
| A | Excellent — no or minimal issues |
| B | Good — minor issues only |
| C | Adequate — moderate issues present |
| D | Poor — significant issues present |
| E | Critical — severe issues present |

## Dimensions

### Maintainability Rating
Derived from the technical debt ratio (debt hours / estimated development hours).

| Debt Ratio | Rating |
|-----------|--------|
| 0-5% | A |
| 5-10% | B |
| 10-20% | C |
| 20-50% | D |
| >50% | E |

### Reliability Rating
Derived from the worst severity issue found in quality/reliability analysis.

| Worst Issue | Rating |
|-------------|--------|
| No bugs | A |
| Minor bug | B |
| Major bug | C |
| Critical bug | D |
| Blocker bug | E |

### Security Rating
Derived from the worst severity vulnerability found.

| Worst Vulnerability | Rating |
|--------------------|--------|
| No vulnerabilities | A |
| Low severity | B |
| Medium severity | C |
| High severity | D |
| Critical severity | E |

## Programmatic Usage

```python
from Asgard.Heimdall.Ratings import RatingsCalculator
from Asgard.Heimdall.Ratings.models import RatingsConfig

calculator = RatingsCalculator()

ratings = calculator.calculate_from_reports(
    scan_path="./src",
    debt_report=debt_report,          # Optional: from TechnicalDebtAnalyzer
    quality_report=quality_report,    # Optional: reliability signals
    security_report=security_report,  # Optional: from StaticSecurityService
)

print(f"Overall:          {ratings.overall_rating}")
print(f"Maintainability:  {ratings.maintainability.rating} ({ratings.maintainability.rationale})")
print(f"Reliability:      {ratings.reliability.rating}")
print(f"Security:         {ratings.security.rating}")
```

## Customising Thresholds

```python
from Asgard.Heimdall.Ratings.models import DebtThresholds, RatingsConfig

config = RatingsConfig(
    debt_thresholds=DebtThresholds(
        a_max=3.0,   # 0-3% = A
        b_max=8.0,   # 3-8% = B
        c_max=15.0,  # 8-15% = C
        d_max=40.0,  # 15-40% = D
        # >40% = E
    )
)
calculator = RatingsCalculator(config=config)
```

## CLI Usage

```bash
python -m Heimdall ratings calculate <path>       # Calculate all ratings
python -m Heimdall ratings show <path>            # Show ratings with rationale
```

## Integration with Quality Gate

The Ratings module feeds directly into the Quality Gate module. Letter ratings are evaluated using ordinal comparison (A=1, E=5), so a gate condition of `SecurityRating <= B` means A or B are both acceptable.
