"""
Freya Epistemic-Status Language

Standing disclaimers mandated by DEEPTHINK_03 (lab vs field) and
DEEPTHINK_06 (observable signals vs actual posture). Every new report
surface must carry the appropriate label so scores are never read as
stronger claims than the evidence supports.
"""

LAB_DATA_DISCLAIMER = (
    "Epistemic status: Lab Data / Synthetic Baseline. Results reflect a "
    "single automated run in a controlled environment, not real-user field "
    "data. Use for regression detection and triage, not as proof of "
    "real-world experience."
)

ACCESSIBILITY_DISCLAIMER = (
    "Automated scans evaluate machine-readable syntax (~20-30% of WCAG "
    "criteria). A passing score reduces exposure to automated compliance "
    "litigation; it does not guarantee meaningful access. Manual "
    "screen-reader testing is required."
)

TREND_INDICATOR_NOTE = (
    "Average scores are trend indicators only; the headline grade is capped "
    "by the worst unresolved finding and is never an average."
)

NEEDS_REVIEW_NOTE = (
    "Items marked 'Needs Review' are claims automation cannot decide; a "
    "page with such items must not be reported as fully passing."
)
