"""
Freya Spatial Focus-Order Analysis

DEEPTHINK_01 "spatial vs DOM analysis": compare the 2D rendered
coordinates of focusable elements to their DOM/tab traversal order.
Erratic X/Y jumps produce a "High-Risk Disorientation" heuristic WARNING
even when WCAG 1.3.2 technically passes. Never a hard FAIL - this is a
heuristic.

The core is a pure function over coordinate lists so it can be tested
without Playwright.
"""

from typing import Any, Dict, List, Optional

from Asgard.Freya.Accessibility.models._accessibility_enums import (
    KeyboardIssueType,
    ViolationSeverity,
)
from Asgard.Freya.Accessibility.models._accessibility_report_models import KeyboardIssue

#: Vertical delta (px) above which a step is treated as moving to a new row.
LINE_THRESHOLD_PX = 24.0

#: Leftward jump within a row larger than this fraction of viewport width
#: counts as a regression.
LEFTWARD_JUMP_FRACTION = 0.4

#: Regression ratio above which the disorientation warning is emitted.
REGRESSION_RATIO_THRESHOLD = 0.25


def count_focus_order_regressions(
    centers: List[Dict[str, float]],
    viewport_width: float = 1920.0,
) -> Dict[str, Any]:
    """
    Count reading-flow regressions along a focus sequence.

    Args:
        centers: element centers in tab order, each {"x": float, "y": float}
        viewport_width: viewport width in px

    Returns:
        {"steps": int, "regressions": int, "ratio": float}
    """
    steps = max(0, len(centers) - 1)
    regressions = 0
    for previous, current in zip(centers, centers[1:]):
        dy = float(current["y"]) - float(previous["y"])
        dx = float(current["x"]) - float(previous["x"])
        if dy < -LINE_THRESHOLD_PX:
            # Jumped up a row.
            regressions += 1
        elif abs(dy) <= LINE_THRESHOLD_PX and dx < -(LEFTWARD_JUMP_FRACTION * viewport_width):
            # Large leftward jump within the same row.
            regressions += 1
    ratio = (regressions / steps) if steps else 0.0
    return {"steps": steps, "regressions": regressions, "ratio": ratio}


def analyze_focus_order_spatial(
    centers: List[Dict[str, float]],
    viewport_width: float = 1920.0,
    ratio_threshold: float = REGRESSION_RATIO_THRESHOLD,
) -> Optional[KeyboardIssue]:
    """
    Analyze spatial focus order; return a heuristic WARNING issue when the
    regression ratio exceeds the threshold, else None.
    """
    stats = count_focus_order_regressions(centers, viewport_width)
    if stats["steps"] < 3 or stats["ratio"] <= ratio_threshold:
        return None

    return KeyboardIssue(
        issue_type=KeyboardIssueType.TAB_ORDER_ISSUE,
        element_selector="body",
        description=(
            "High-Risk Disorientation: visual focus order diverges from DOM order "
            f"({stats['regressions']}/{stats['steps']} steps regress against reading flow). "
            "Heuristic finding (wcag.1.3.2.spatial) - not a hard failure."
        ),
        severity=ViolationSeverity.SERIOUS,
        wcag_reference="1.3.2",
        suggested_fix=(
            "Reorder the DOM (or remove positive tabindex values) so keyboard "
            "traversal follows the visual reading flow."
        ),
    )


def centers_from_focusables(focusable_elements: List[dict]) -> List[Dict[str, float]]:
    """Extract element centers from keyboard-nav focusable element dicts."""
    centers = []
    for elem in focusable_elements:
        box = elem.get("box")
        if not box:
            continue
        try:
            centers.append({
                "x": float(box["x"]) + float(box.get("width", 0)) / 2,
                "y": float(box["y"]) + float(box.get("height", 0)) / 2,
            })
        except (KeyError, TypeError, ValueError):
            continue
    return centers
