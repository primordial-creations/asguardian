"""Domain policy for interpreting metric direction."""

_LOWER_IS_BETTER_METRICS = frozenset(
    {
        "duplication_percentage",
        "cyclomatic_complexity",
        "technical_debt_hours",
        "critical_vulnerabilities",
        "high_vulnerabilities",
        "naming_violations",
        "savd_critical",
        "savd_high",
        "savd_medium",
        "savd_low",
    }
)


def get_lower_is_better_metrics() -> frozenset[str]:
    """Return metrics whose decrease represents an improvement."""
    return _LOWER_IS_BETTER_METRICS
