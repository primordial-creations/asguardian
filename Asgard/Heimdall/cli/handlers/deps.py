import argparse
import json
from pathlib import Path

from Asgard.Heimdall.Dependencies.models.dependency_models import DependencyConfig
from Asgard.Heimdall.Dependencies.services.dependency_analyzer import DependencyAnalyzer
from Asgard.Heimdall.Dependencies.services.graph_builder import GraphBuilder


def run_deps_analysis(args: argparse.Namespace, verbose: bool = False, analysis_type: str = "all") -> int:
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    config = DependencyConfig(
        scan_path=scan_path,
        max_depth=getattr(args, 'max_depth', 10),
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        analyzer = DependencyAnalyzer(config)

        if analysis_type == "cycles":
            result = analyzer.find_cycles(scan_path)
            report = analyzer.generate_cycles_report(result, args.format)
            print(report)
            return 1 if result else 0
        elif analysis_type == "modularity":
            result = analyzer.analyze_modularity(scan_path)
            report = analyzer.generate_modularity_report(result, args.format)
            print(report)
            return 1 if result.has_issues else 0
        else:
            result = analyzer.analyze(scan_path)
            direction = getattr(args, "direction", "LR")
            report = analyzer.generate_report(result, args.format, direction)
            print(report)
            return 1 if result.has_issues else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_deps_export(args: argparse.Namespace, verbose: bool = False) -> int:
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    config = DependencyConfig(
        scan_path=scan_path,
        exclude_patterns=exclude_patterns,
    )

    try:
        builder = GraphBuilder(config)
        export_format = getattr(args, "export_format", "mermaid")
        output_path = Path(args.output) if getattr(args, "output", None) else None
        direction = getattr(args, "direction", "LR")

        if export_format in ("dot", "graphviz"):
            result = builder.export_dot(scan_path, output_path, direction)
        elif export_format == "json":
            result = json.dumps(builder.export_json(scan_path), indent=2)
            if output_path:
                output_path.write_text(result)
        elif export_format == "mermaid":
            result = builder.export_mermaid(scan_path, output_path, direction)
        else:
            print(f"Unknown export format: {export_format}")
            return 1

        if output_path:
            print(f"Exported {export_format} graph to {output_path}")
        else:
            print(result)

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1
