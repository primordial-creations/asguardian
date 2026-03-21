"""
Heimdall New Code Period Detection

Defines what constitutes "new code" for the purpose of separate metric tracking.
New code can be defined relative to the last analysis, a date, a branch point, or
a tagged version. This mirrors SonarQube's New Code Period concept.

New code gets separate metrics that can be more strictly gated, allowing teams to
enforce quality on new code without requiring immediate cleanup of existing issues.
"""

from Asgard.Heimdall.common._new_code_models import (
    NewCodePeriodConfig,
    NewCodePeriodResult,
    NewCodePeriodType,
)
from Asgard.Heimdall.common._new_code_git import (
    git_available,
    detect_since_last_analysis,
    detect_since_date,
    detect_since_branch_point,
    detect_since_version,
    detect_by_mtime,
)

__all__ = [
    "NewCodePeriodConfig",
    "NewCodePeriodResult",
    "NewCodePeriodType",
    "NewCodePeriodDetector",
]


class NewCodePeriodDetector:
    """
    Detects which files constitute new code relative to a configured reference point.

    Uses git to identify changed files wherever git is available. Falls back to
    file modification timestamps when git is not available.

    Usage:
        config = NewCodePeriodConfig(
            period_type=NewCodePeriodType.SINCE_BRANCH_POINT,
            reference_branch="main",
        )
        detector = NewCodePeriodDetector()
        result = detector.detect("./src", config)
        print(f"New files: {result.new_files}")
        print(f"Modified files: {result.modified_files}")
    """

    def detect(self, scan_path: str, config: NewCodePeriodConfig) -> NewCodePeriodResult:
        """
        Detect new code relative to the configured reference point.

        Args:
            scan_path: Root directory of the project to analyse.
            config: Configuration specifying the new code period type.

        Returns:
            NewCodePeriodResult with lists of new and modified files.
        """
        period_type: str = (
            config.period_type.value
            if isinstance(config.period_type, NewCodePeriodType)
            else config.period_type
        )

        if not git_available(scan_path):
            return detect_by_mtime(scan_path, config)

        if period_type == NewCodePeriodType.SINCE_LAST_ANALYSIS.value:
            return detect_since_last_analysis(scan_path, config)
        elif period_type == NewCodePeriodType.SINCE_DATE.value:
            return detect_since_date(scan_path, config)
        elif period_type == NewCodePeriodType.SINCE_BRANCH_POINT.value:
            return detect_since_branch_point(scan_path, config)
        elif period_type == NewCodePeriodType.SINCE_VERSION.value:
            return detect_since_version(scan_path, config)
        else:
            return detect_since_last_analysis(scan_path, config)
