import argparse
from pathlib import Path

from Asgard.Heimdall.Quality.models.complexity_models import ComplexityConfig
from Asgard.Heimdall.Quality.services.complexity_analyzer import ComplexityAnalyzer
from Asgard.Heimdall.Quality.models.duplication_models import DuplicationConfig
from Asgard.Heimdall.Quality.services.duplication_detector import DuplicationDetector
from Asgard.Heimdall.Quality.models.smell_models import (
    SmellConfig,
    SmellSeverity,
    SmellThresholds,
)
from Asgard.Heimdall.Quality.models.debt_models import DebtConfig, TimeHorizon
from Asgard.Heimdall.Quality.services.technical_debt_analyzer import TechnicalDebtAnalyzer
from Asgard.Heimdall.Quality.models.maintainability_models import (
    MaintainabilityConfig,
    LanguageProfile,
)
from Asgard.Heimdall.Quality.services.code_smell_detector import CodeSmellDetector
from Asgard.Heimdall.Quality.services.maintainability_analyzer import MaintainabilityAnalyzer


def run_complexity_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    config = ComplexityConfig(
        scan_path=scan_path,
        cyclomatic_threshold=args.cyclomatic_threshold,
        cognitive_threshold=args.cognitive_threshold,
        include_tests=getattr(args, 'include_tests', False),
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        analyzer = ComplexityAnalyzer(config)
        result = analyzer.analyze()
        report = analyzer.generate_report(result, args.format)
        print(report)
        return 1 if result.has_violations else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_duplication_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    config = DuplicationConfig(
        scan_path=scan_path,
        min_block_size=getattr(args, 'min_lines', 6),
        similarity_threshold=getattr(args, 'min_tokens', 50) / 100.0,
        output_format=args.format,
        include_tests=getattr(args, 'include_tests', False),
        exclude_patterns=exclude_patterns,
        verbose=verbose,
    )

    try:
        detector = DuplicationDetector(config)
        result = detector.analyze()
        report = detector.generate_report(result, args.format)
        print(report)
        return 1 if result.has_duplicates else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_smell_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    thresholds = SmellThresholds(
        long_method_lines=getattr(args, 'long_method_lines', 50),
        large_class_methods=getattr(args, 'large_class_methods', 20),
        long_parameter_list=getattr(args, 'long_parameter_list', 5),
    )

    config = SmellConfig(
        scan_path=scan_path,
        smell_categories=getattr(args, 'categories', None),
        severity_filter=SmellSeverity(args.severity),
        thresholds=thresholds,
        output_format=args.format,
        include_tests=getattr(args, 'include_tests', False),
        exclude_patterns=exclude_patterns,
        verbose=verbose,
    )

    try:
        detector = CodeSmellDetector(config)
        result = detector.analyze(scan_path)
        report = detector.generate_report(result, args.format)
        print(report)
        return 1 if result.has_smells else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_debt_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    config = DebtConfig(
        scan_path=scan_path,
        debt_types=getattr(args, 'debt_types', None),
        time_horizon=TimeHorizon(getattr(args, 'time_horizon', 'sprint')),
        include_tests=getattr(args, 'include_tests', False),
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        analyzer = TechnicalDebtAnalyzer(config)
        result = analyzer.analyze(scan_path)
        report = analyzer.generate_report(result, args.format)
        print(report)
        return 1 if result.has_debt else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_maintainability_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    config = MaintainabilityConfig(
        scan_path=scan_path,
        include_halstead=not getattr(args, 'no_halstead', False),
        include_comments=not getattr(args, 'no_comments', False),
        language_profile=LanguageProfile(getattr(args, 'language', 'python')),
        include_tests=getattr(args, 'include_tests', False),
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        analyzer = MaintainabilityAnalyzer(config)
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
