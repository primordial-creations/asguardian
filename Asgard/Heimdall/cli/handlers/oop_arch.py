import argparse
from pathlib import Path

from Asgard.Bragi.OOP.models.oop_models import OOPConfig
from Asgard.Bragi.OOP.services.oop_analyzer import OOPAnalyzer
from Asgard.Bragi.Architecture.models.architecture_models import ArchitectureConfig
from Asgard.Bragi.Architecture.services.architecture_analyzer import ArchitectureAnalyzer


def run_oop_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    if getattr(args, "explain", None):
        return run_oop_explain(args, verbose)

    exclude_patterns = list(args.exclude) if args.exclude else []

    config = OOPConfig(
        scan_path=scan_path,
        cbo_threshold=args.cbo_threshold,
        lcom_threshold=args.lcom_threshold,
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        analyzer = OOPAnalyzer(config)
        result = analyzer.analyze(scan_path)
        report = analyzer.generate_report(result, args.format)
        print(report)
        return 1 if result.has_issues else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_oop_explain(args: argparse.Namespace, verbose: bool = False) -> int:
    """`heimdall oop cohesion <path> --explain <ClassName>`.

    Explains the LCOM4/CBO composition for a single class using
    Bragi's CIR metrics engine (component partition / coupling detail).
    """
    from Asgard.Bragi.OOP.services.cir_metrics import explain_class

    scan_path = Path(args.path).resolve()
    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    try:
        explanation = explain_class(scan_path, args.explain)
    except Exception as e:
        print(f"Error: {e}")
        return 1

    if explanation is None:
        print(f"Error: Class not found: {args.explain}")
        return 1

    print(explanation)
    return 0


def run_arch_explain(args: argparse.Namespace, verbose: bool = False) -> int:
    """`heimdall architecture layers <path> --explain <file>` (Plan 03)."""
    from Asgard.Bragi.Architecture.services.hexagonal_analyzer import HexagonalAnalyzer

    scan_path = Path(args.path).resolve()
    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    try:
        analyzer = HexagonalAnalyzer(
            ArchitectureConfig(scan_path=scan_path),
        )
        print(analyzer.explain_file(args.explain, scan_path))
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_arch_analysis(args: argparse.Namespace, verbose: bool = False, analysis_type: str = "all") -> int:
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    config = ArchitectureConfig(scan_path=scan_path)
    if args.exclude:
        config.exclude_patterns = list(set(config.exclude_patterns) | set(args.exclude))

    try:
        analyzer = ArchitectureAnalyzer(config)

        validate_solid = not getattr(args, 'no_solid', False) if analysis_type == "all" else analysis_type == "solid"
        analyze_layers = not getattr(args, 'no_layers', False) if analysis_type == "all" else analysis_type == "layers"
        detect_patterns = not getattr(args, 'no_patterns', False) if analysis_type == "all" else analysis_type == "patterns"
        analyze_hexagonal = getattr(args, 'hexagonal', False) if analysis_type == "all" else analysis_type == "hexagonal"

        result = analyzer.analyze(
            scan_path,
            validate_solid=validate_solid,
            analyze_layers=analyze_layers,
            detect_patterns=detect_patterns,
            analyze_hexagonal=analyze_hexagonal,
        )
        report = analyzer.generate_report(result, args.format)
        print(report)
        return 1 if not result.is_healthy else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1
