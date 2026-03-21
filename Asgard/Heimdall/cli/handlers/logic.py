import argparse
from pathlib import Path

from Asgard.Heimdall.Quality.models.duplication_models import DuplicationConfig
from Asgard.Heimdall.Quality.services.duplication_detector import DuplicationDetector
from Asgard.Heimdall.Quality.models.smell_models import SmellConfig, SmellSeverity
from Asgard.Heimdall.Quality.services.code_smell_detector import CodeSmellDetector
from Asgard.Heimdall.Quality.models.complexity_models import ComplexityConfig
from Asgard.Heimdall.Quality.services.complexity_analyzer import ComplexityAnalyzer


def run_logic_analysis(args: argparse.Namespace, verbose: bool = False, analysis_type: str = "audit") -> int:
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []
    issues_found = False

    if analysis_type in ("duplication", "audit"):
        config = DuplicationConfig(
            scan_path=scan_path,
            min_block_size=getattr(args, 'min_similarity', 0.8) * 10,
            similarity_threshold=getattr(args, 'min_similarity', 0.8),
            output_format=args.format,
            exclude_patterns=exclude_patterns,
            verbose=verbose,
        )
        try:
            detector = DuplicationDetector(config)
            result = detector.analyze()
            if analysis_type == "duplication":
                report = detector.generate_report(result, args.format)
                print(report)
            else:
                print(f"\n[Duplication] Found {result.total_clone_families} clone families")
            if result.has_duplicates:
                issues_found = True
        except Exception as e:
            print(f"Duplication analysis error: {e}")

    if analysis_type in ("patterns", "audit"):
        config = SmellConfig(
            scan_path=scan_path,
            severity_filter=SmellSeverity(args.severity),
            output_format=args.format,
            exclude_patterns=exclude_patterns,
            verbose=verbose,
        )
        try:
            detector = CodeSmellDetector(config)
            result = detector.analyze(scan_path)
            if analysis_type == "patterns":
                report = detector.generate_report(result, args.format)
                print(report)
            else:
                print(f"[Patterns] Found {result.total_smells} code smells")
            if result.has_smells:
                issues_found = True
        except Exception as e:
            print(f"Pattern analysis error: {e}")

    if analysis_type in ("complexity", "audit"):
        config = ComplexityConfig(
            scan_path=scan_path,
            cyclomatic_threshold=10,
            cognitive_threshold=15,
            output_format=args.format,
            exclude_patterns=exclude_patterns,
            verbose=verbose,
        )
        try:
            analyzer = ComplexityAnalyzer(config)
            result = analyzer.analyze()
            if analysis_type == "complexity":
                report = analyzer.generate_report(result, args.format)
                print(report)
            else:
                print(f"[Complexity] Found {result.total_violations} violations")
            if result.has_violations:
                issues_found = True
        except Exception as e:
            print(f"Complexity analysis error: {e}")

    return 1 if issues_found else 0
