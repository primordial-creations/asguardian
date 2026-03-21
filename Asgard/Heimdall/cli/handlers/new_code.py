import argparse
import json
from datetime import datetime
from pathlib import Path

from Asgard.Heimdall.common.new_code_period import (
    NewCodePeriodConfig,
    NewCodePeriodDetector,
    NewCodePeriodType,
)


def run_new_code_detect(args: argparse.Namespace, verbose: bool = False) -> int:
    scan_path = Path(getattr(args, "path", ".")).resolve()
    output_format = getattr(args, "format", "text")

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    since_date_str = getattr(args, "since_date", None)
    since_branch = getattr(args, "since_branch", None)
    since_version = getattr(args, "since_version", None)

    if since_date_str:
        period_type = NewCodePeriodType.SINCE_DATE
        try:
            ref_date = datetime.strptime(since_date_str, "%Y-%m-%d")
        except ValueError:
            print(f"Error: Invalid date format '{since_date_str}'. Use YYYY-MM-DD.")
            return 1
        config = NewCodePeriodConfig(
            period_type=period_type,
            reference_date=ref_date,
        )
    elif since_branch:
        config = NewCodePeriodConfig(
            period_type=NewCodePeriodType.SINCE_BRANCH_POINT,
            reference_branch=since_branch,
        )
    elif since_version:
        config = NewCodePeriodConfig(
            period_type=NewCodePeriodType.SINCE_VERSION,
            reference_version=since_version,
        )
    else:
        config = NewCodePeriodConfig(
            period_type=NewCodePeriodType.SINCE_LAST_ANALYSIS,
        )

    detector = NewCodePeriodDetector()
    result = detector.detect(str(scan_path), config)

    if output_format == "json":
        data = {
            "period_type": str(result.period_type),
            "reference_point": result.reference_point,
            "new_files": result.new_files,
            "modified_files": result.modified_files,
            "new_lines_count": result.new_lines_count,
            "total_new_code_files": result.total_new_code_files,
            "detected_at": result.detected_at.isoformat(),
        }
        print(json.dumps(data, indent=2))
        return 0

    print("")
    print("=" * 70)
    print(f"  NEW CODE PERIOD: {scan_path}")
    print("=" * 70)
    print("")
    print(f"  Reference point: {result.reference_point}")
    print(f"  Total new code files: {result.total_new_code_files}")
    print(f"  New files added: {len(result.new_files)}")
    print(f"  Files modified: {len(result.modified_files)}")
    print("")

    if result.new_files:
        print("  New Files:")
        for f in result.new_files:
            print(f"    + {f}")
        print("")

    if result.modified_files:
        print("  Modified Files:")
        for f in result.modified_files:
            print(f"    M {f}")
        print("")

    print("=" * 70)
    return 0
