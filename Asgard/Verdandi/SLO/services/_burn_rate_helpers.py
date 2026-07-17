"""
Helpers for BurnRateAnalyzer.

Contains recommendation generation functions extracted from the burn rate analyzer.
"""

import math
from typing import List, Optional


def minimum_traffic_for_target(target: float) -> int:
    """
    Minimum events per alert window for a burn-rate alert to be
    statistically valid: 10 / (1 - target) (DEEPTHINK_04).

    Args:
        target: SLO target as a fraction (0.999 for 99.9%)

    Returns:
        Minimum event count (e.g. 10,000 for a 99.9% target)
    """
    if not 0.0 <= target < 1.0:
        raise ValueError(f"target must be a fraction in [0, 1), got {target}")
    # Round before ceiling so float artifacts (10/(1-0.999) = 10000.0000002)
    # do not inflate the requirement by one event.
    return math.ceil(round(10.0 / (1.0 - target), 6))


def full_outage_burn_rate(target: float) -> float:
    """
    Burn rate during a 100% outage: 1 / (1 - target).

    E.g. a 99.9% SLO burns at 1000x during a full outage.
    """
    if not 0.0 <= target < 1.0:
        raise ValueError(f"target must be a fraction in [0, 1), got {target}")
    return 1.0 / (1.0 - target)


def min_detectable_outage_seconds(
    target: float,
    threshold: float,
    window_hours: float,
) -> float:
    """
    Detection limit: the shortest full outage that trips a burn-rate
    threshold over a given window.

    time_to_breach = threshold * window / full_outage_burn_rate
    (99.9% target, 14.4x, 1h window -> 51.84 s; 5m guard -> 4.32 s)
    """
    return threshold * window_hours * 3600.0 / full_outage_burn_rate(target)


def generate_burn_rate_recommendations(
    burn_rate: float,
    is_critical: bool,
    is_warning: bool,
    time_to_exhaustion: Optional[float],
    elevated_threshold: float = 1.0,
) -> List[str]:
    """Generate recommendations based on burn rate analysis."""
    recommendations = []

    if is_critical:
        recommendations.append(
            f"CRITICAL: Error budget burning at {burn_rate:.1f}x sustainable rate. "
            "Immediate action required."
        )
        if time_to_exhaustion:
            recommendations.append(
                f"Budget will be exhausted in approximately {time_to_exhaustion:.1f} hours "
                "at current rate."
            )
        recommendations.append(
            "Review recent deployments, rollback if necessary, and investigate error sources."
        )
    elif is_warning:
        recommendations.append(
            f"Warning: Error budget burning at {burn_rate:.1f}x sustainable rate. "
            "Investigation recommended."
        )
        recommendations.append(
            "Create ticket to investigate elevated error rates before budget exhaustion."
        )
    elif burn_rate > elevated_threshold:
        recommendations.append(
            f"Error budget consumption elevated at {burn_rate:.1f}x sustainable rate. "
            "Monitor closely."
        )

    return recommendations


def generate_multi_window_recommendations(
    short_burn_rate: float,
    long_burn_rate: float,
    is_critical: bool,
    is_warning: bool,
    warning_threshold: float,
) -> List[str]:
    """Generate recommendations for multi-window analysis."""
    recommendations = []

    if is_critical:
        recommendations.append(
            f"CRITICAL: Both short ({short_burn_rate:.1f}x) and long ({long_burn_rate:.1f}x) "
            "windows show critical burn rate. Page on-call immediately."
        )
    elif is_warning:
        recommendations.append(
            f"Warning: Both windows show elevated burn rate "
            f"(short: {short_burn_rate:.1f}x, long: {long_burn_rate:.1f}x). "
            "Create ticket for investigation."
        )
    elif short_burn_rate >= warning_threshold > long_burn_rate:
        recommendations.append(
            f"Short window burn rate elevated ({short_burn_rate:.1f}x) but long window "
            f"still acceptable ({long_burn_rate:.1f}x). Monitor for persistence."
        )
    elif short_burn_rate < long_burn_rate and long_burn_rate > 1.0:
        recommendations.append(
            "Burn rate improving recently. Continue monitoring recovery."
        )

    return recommendations


def calculate_time_to_exhaustion(
    burn_rate: float,
    slo_window_hours: float,
) -> Optional[float]:
    """Calculate hours until budget exhaustion at current burn rate."""
    if burn_rate <= 0:
        return None

    if burn_rate <= 1.0:
        return None

    return slo_window_hours / burn_rate


def determine_burn_rate_severity(
    burn_rate: float,
    critical_threshold: float,
    warning_threshold: float,
    elevated_threshold: float,
) -> str:
    """Determine alert severity from burn rate."""
    if burn_rate >= critical_threshold:
        return "critical"
    elif burn_rate >= warning_threshold:
        return "warning"
    elif burn_rate >= elevated_threshold:
        return "elevated"
    return "none"
