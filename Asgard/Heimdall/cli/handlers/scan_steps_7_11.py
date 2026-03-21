import json

from Asgard.Heimdall.Performance.models.performance_models import PerformanceScanConfig
from Asgard.Heimdall.Performance.services.static_performance_service import StaticPerformanceService
from Asgard.Heimdall.OOP.models.oop_models import OOPConfig
from Asgard.Heimdall.OOP.services.oop_analyzer import OOPAnalyzer
from Asgard.Heimdall.Architecture.models.architecture_models import ArchitectureConfig
from Asgard.Heimdall.Architecture.services.architecture_analyzer import ArchitectureAnalyzer
from Asgard.Heimdall.Dependencies.models.dependency_models import DependencyConfig
from Asgard.Heimdall.Dependencies.services.dependency_analyzer import DependencyAnalyzer
from Asgard.Heimdall.Coverage.models.coverage_models import CoverageConfig
from Asgard.Heimdall.Coverage.services.coverage_analyzer import CoverageAnalyzer


def _run_scan_steps_7_to_11(scan_path, exclude_patterns, include_tests, verbose, scan_results, step_reports):
    overall_exit = 0

    print("[7/11] Performance: Pattern Analysis...")
    try:
        perf_config = PerformanceScanConfig(
            scan_path=scan_path, include_tests=include_tests,
            exclude_patterns=exclude_patterns, verbose=verbose,
        )
        perf_service = StaticPerformanceService(perf_config)
        perf_result = perf_service.scan(scan_path)
        perf_total = perf_result.total_findings if hasattr(perf_result, "total_findings") else 0
        scan_results["performance"] = {
            "total_findings": perf_total,
            "status": "PASS" if perf_total == 0 else "FAIL",
        }
        if perf_total > 0:
            overall_exit = 1
        print(f"       {perf_total} findings")
        try:
            step_reports["performance"] = perf_service.generate_report(perf_result, "text")
        except Exception:
            step_reports["performance"] = f"Performance Analysis\n\n{json.dumps(scan_results['performance'], indent=2)}"
    except Exception as e:
        scan_results["performance"] = {"status": "ERROR", "error": str(e)}
        print(f"       Error: {e}")

    print("[8/11] OOP: Coupling/Cohesion Metrics...")
    try:
        oop_config = OOPConfig(
            scan_path=scan_path, include_tests=include_tests,
            exclude_patterns=exclude_patterns, verbose=verbose,
        )
        oop_analyzer = OOPAnalyzer(oop_config)
        oop_result = oop_analyzer.analyze(scan_path)
        oop_violations = oop_result.total_violations if hasattr(oop_result, "total_violations") else 0
        scan_results["oop"] = {
            "violations": oop_violations,
            "status": "PASS" if oop_violations == 0 else "FAIL",
        }
        if oop_violations > 0:
            overall_exit = 1
        print(f"       {oop_violations} violations")
        try:
            step_reports["oop"] = oop_analyzer.generate_report(oop_result, "text")
        except Exception:
            step_reports["oop"] = f"OOP Metrics\n\n{json.dumps(scan_results['oop'], indent=2)}"
    except Exception as e:
        scan_results["oop"] = {"status": "ERROR", "error": str(e)}
        print(f"       Error: {e}")

    print("[9/11] Architecture: SOLID/Layer Analysis...")
    try:
        arch_config = ArchitectureConfig(scan_path=scan_path, exclude_patterns=exclude_patterns)
        arch_analyzer = ArchitectureAnalyzer(arch_config)
        arch_result = arch_analyzer.analyze(scan_path)
        arch_violations = arch_result.total_violations if hasattr(arch_result, "total_violations") else 0
        scan_results["architecture"] = {
            "violations": arch_violations,
            "status": "PASS" if arch_violations == 0 else "FAIL",
        }
        if arch_violations > 0:
            overall_exit = 1
        print(f"       {arch_violations} violations")
        try:
            step_reports["architecture"] = arch_analyzer.generate_report(arch_result, "text")
        except Exception:
            step_reports["architecture"] = f"Architecture Analysis\n\n{json.dumps(scan_results['architecture'], indent=2)}"
    except Exception as e:
        scan_results["architecture"] = {"status": "ERROR", "error": str(e)}
        print(f"       Error: {e}")

    print("[10/11] Dependencies: Circular Import Detection...")
    try:
        deps_config = DependencyConfig(
            scan_path=scan_path, include_tests=include_tests,
            exclude_patterns=exclude_patterns, verbose=verbose,
        )
        deps_analyzer = DependencyAnalyzer(deps_config)
        deps_result = deps_analyzer.analyze(scan_path)
        deps_cycles = deps_result.cycle_count if hasattr(deps_result, "cycle_count") else 0
        scan_results["dependencies"] = {
            "circular_imports": deps_cycles,
            "status": "PASS" if deps_cycles == 0 else "FAIL",
        }
        if deps_cycles > 0:
            overall_exit = 1
        print(f"       {deps_cycles} circular dependencies")
        try:
            step_reports["dependencies"] = deps_analyzer.generate_report(deps_result, "text")
        except Exception:
            step_reports["dependencies"] = f"Dependency Analysis\n\n{json.dumps(scan_results['dependencies'], indent=2)}"
    except Exception as e:
        scan_results["dependencies"] = {"status": "ERROR", "error": str(e)}
        print(f"       Error: {e}")

    print("[11/11] Test Coverage: Gap Analysis...")
    try:
        coverage_config = CoverageConfig(scan_path=scan_path, exclude_patterns=exclude_patterns)
        coverage_analyzer = CoverageAnalyzer(coverage_config)
        coverage_result = coverage_analyzer.analyze(scan_path)
        method_coverage = coverage_result.metrics.method_coverage_percent
        total_gaps = coverage_result.total_gaps
        scan_results["test_coverage"] = {
            "method_coverage_percent": round(method_coverage, 1),
            "total_gaps": total_gaps,
            "status": "PASS" if method_coverage >= coverage_config.min_method_coverage else "FAIL",
        }
        if method_coverage < coverage_config.min_method_coverage:
            overall_exit = 1
        print(f"       {method_coverage:.1f}% method coverage, {total_gaps} gaps")
        try:
            step_reports["test_coverage"] = coverage_analyzer.generate_report(coverage_result, "text")
        except Exception:
            step_reports["test_coverage"] = f"Test Coverage\n\n{json.dumps(scan_results['test_coverage'], indent=2)}"
    except Exception as e:
        scan_results["test_coverage"] = {"status": "ERROR", "error": str(e)}
        print(f"       Error: {e}")

    return overall_exit
