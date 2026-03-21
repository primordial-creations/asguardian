import argparse
import json
from pathlib import Path

from Asgard.Heimdall.Coverage.models.coverage_models import CoverageConfig
from Asgard.Heimdall.Coverage.services.coverage_analyzer import CoverageAnalyzer


def run_coverage_analysis(args: argparse.Namespace, verbose: bool = False, analysis_type: str = "all") -> int:
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    test_path = None
    if hasattr(args, 'test_path') and args.test_path:
        test_path = Path(args.test_path).resolve()

    config = CoverageConfig(
        scan_path=scan_path,
        include_private=getattr(args, 'include_private', False),
        exclude_patterns=exclude_patterns,
    )

    try:
        analyzer = CoverageAnalyzer(config)

        if analysis_type == "gaps":
            gaps = analyzer.get_gaps(scan_path)
            if args.format == "json":
                print(json.dumps([{
                    "method": g.method.full_name,
                    "file": g.file_path,
                    "severity": g.severity.value,
                    "message": g.message,
                } for g in gaps], indent=2))
            else:
                print(f"\nCoverage Gaps Found: {len(gaps)}")
                for g in gaps[:20]:
                    print(f"  [{g.severity.value.upper()}] {g.method.full_name}")
                if len(gaps) > 20:
                    print(f"  ... and {len(gaps) - 20} more")
            return 1 if gaps else 0
        elif analysis_type == "suggestions":
            max_suggestions = getattr(args, 'max_suggestions', 10)
            suggestions = analyzer.get_suggestions(scan_path, max_suggestions)
            if args.format == "json":
                print(json.dumps([{
                    "test_name": s.test_name,
                    "method": s.method.full_name,
                    "priority": s.priority.value,
                    "description": s.description,
                } for s in suggestions], indent=2))
            else:
                print(f"\nTest Suggestions ({len(suggestions)}):")
                for s in suggestions:
                    print(f"  [{s.priority.value.upper()}] {s.test_name}")
                    print(f"    {s.description}")
            return 0
        else:
            result = analyzer.analyze(scan_path, test_path)
            report = analyzer.generate_report(result, args.format)
            print(report)
            return 1 if result.has_gaps else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1
