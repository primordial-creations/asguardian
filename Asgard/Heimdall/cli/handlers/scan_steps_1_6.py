import json

from Asgard.Heimdall.Quality.models.analysis_models import AnalysisConfig
from Asgard.Heimdall.Quality.services.file_length_analyzer import FileAnalyzer
from Asgard.Heimdall.Quality.models.complexity_models import ComplexityConfig
from Asgard.Heimdall.Quality.services.complexity_analyzer import ComplexityAnalyzer
from Asgard.Heimdall.Quality.models.lazy_import_models import LazyImportConfig
from Asgard.Heimdall.Quality.services.lazy_import_scanner import LazyImportScanner
from Asgard.Heimdall.Quality.models.env_fallback_models import EnvFallbackConfig
from Asgard.Heimdall.Quality.services.env_fallback_scanner import EnvFallbackScanner
from Asgard.Heimdall.Quality.models.type_check_models import TypeCheckConfig
from Asgard.Heimdall.Quality.services.type_checker import TypeChecker
from Asgard.Heimdall.Security.models.security_models import SecurityScanConfig
from Asgard.Heimdall.Security.services.static_security_service import StaticSecurityService


def _run_scan_steps_1_to_6(scan_path, exclude_patterns, include_tests, output_format, verbose, scan_results, step_reports):
    overall_exit = 0

    print("[1/11] Quality: File Length Analysis...")
    try:
        config = AnalysisConfig(
            scan_path=scan_path,
            default_threshold=300,
            exclude_patterns=exclude_patterns,
            output_format=output_format,
            verbose=verbose,
        )
        analyzer = FileAnalyzer(config)
        result = analyzer.analyze()
        scan_results["file_length"] = {
            "violations": result.files_exceeding_threshold,
            "files_scanned": result.total_files_scanned,
            "compliance_rate": result.compliance_rate,
            "status": "PASS" if not result.has_violations else "FAIL",
        }
        if result.has_violations:
            overall_exit = 1
        print(f"       {result.files_exceeding_threshold} violations in {result.total_files_scanned} files")
        fl_lines = [
            "", "=" * 70, "  FILE LENGTH ANALYSIS", "=" * 70, "",
            f"  Scan Path:              {result.scan_path}",
            f"  Files Scanned:          {result.total_files_scanned}",
            f"  Files Over Threshold:   {result.files_exceeding_threshold}",
            f"  Compliance Rate:        {result.compliance_rate:.1f}%", "",
        ]
        if not result.has_violations:
            fl_lines.extend(["  All files are within the threshold.", ""])
        else:
            sorted_viol = sorted(result.violations, key=lambda x: x.line_count, reverse=True)
            fl_lines.extend(["-" * 70, "  VIOLATIONS (longest first)", "  " + "-" * 47, ""])
            for v in sorted_viol:
                fl_lines.append(f"  {v.relative_path}   {v.line_count} lines  (limit: {v.threshold}, over by {v.lines_over})")
            fl_lines.append("")
        fl_lines.extend(["=" * 70, ""])
        step_reports["file_length"] = "\n".join(fl_lines)
    except Exception as e:
        scan_results["file_length"] = {"status": "ERROR", "error": str(e)}
        print(f"       Error: {e}")

    print("[2/11] Quality: Complexity Analysis...")
    try:
        complexity_config = ComplexityConfig(
            scan_path=scan_path, include_tests=include_tests,
            exclude_patterns=exclude_patterns, verbose=verbose,
        )
        complexity_analyzer = ComplexityAnalyzer(complexity_config)
        complexity_result = complexity_analyzer.analyze()
        violation_count = len(complexity_result.violations) if hasattr(complexity_result, "violations") else 0
        scan_results["complexity"] = {
            "violations": violation_count,
            "status": "PASS" if not complexity_result.has_violations else "FAIL",
        }
        if complexity_result.has_violations:
            overall_exit = 1
        print(f"       {violation_count} violations found")
        try:
            step_reports["complexity"] = complexity_analyzer.generate_report(complexity_result, "text")
        except Exception:
            step_reports["complexity"] = f"Complexity Analysis\n\n{json.dumps(scan_results['complexity'], indent=2)}"
    except Exception as e:
        scan_results["complexity"] = {"status": "ERROR", "error": str(e)}
        print(f"       Error: {e}")

    print("[3/11] Quality: Lazy Import Detection...")
    try:
        lazy_config = LazyImportConfig(
            scan_path=scan_path, include_tests=include_tests,
            exclude_patterns=exclude_patterns, verbose=verbose,
        )
        lazy_scanner = LazyImportScanner(lazy_config)
        lazy_result = lazy_scanner.analyze(scan_path)
        lazy_count = lazy_result.total_violations
        scan_results["lazy_imports"] = {
            "violations": lazy_count,
            "files_scanned": lazy_result.files_scanned,
            "status": "PASS" if not lazy_result.has_violations else "FAIL",
        }
        if lazy_result.has_violations:
            overall_exit = 1
        print(f"       {lazy_count} violations in {lazy_result.files_scanned} files")
        try:
            step_reports["lazy_imports"] = lazy_scanner.generate_report(lazy_result, "text")
        except Exception:
            step_reports["lazy_imports"] = f"Lazy Import Detection\n\n{json.dumps(scan_results['lazy_imports'], indent=2)}"
    except Exception as e:
        scan_results["lazy_imports"] = {"status": "ERROR", "error": str(e)}
        print(f"       Error: {e}")

    print("[4/11] Quality: Environment Variable Fallback Detection...")
    try:
        env_config = EnvFallbackConfig(
            scan_path=scan_path, include_tests=include_tests,
            exclude_patterns=exclude_patterns, verbose=verbose,
        )
        env_scanner = EnvFallbackScanner(env_config)
        env_result = env_scanner.analyze(scan_path)
        env_count = env_result.total_violations
        scan_results["env_fallbacks"] = {
            "violations": env_count,
            "files_scanned": env_result.files_scanned,
            "status": "PASS" if not env_result.has_violations else "FAIL",
        }
        if env_result.has_violations:
            overall_exit = 1
        print(f"       {env_count} violations in {env_result.files_scanned} files")
        try:
            step_reports["env_fallbacks"] = env_scanner.generate_report(env_result, "text")
        except Exception:
            step_reports["env_fallbacks"] = f"Env Fallback Detection\n\n{json.dumps(scan_results['env_fallbacks'], indent=2)}"
    except Exception as e:
        scan_results["env_fallbacks"] = {"status": "ERROR", "error": str(e)}
        print(f"       Error: {e}")

    print("[5/11] Quality: Static Type Checking (mypy)...")
    try:
        type_config = TypeCheckConfig(
            engine="mypy",
            include_tests=include_tests,
            exclude_patterns=exclude_patterns,
            include_warnings=False,
            verbose=verbose,
        )
        type_checker = TypeChecker(type_config)
        type_result = type_checker.analyze(scan_path)
        scan_results["type_check"] = {
            "errors": type_result.total_errors,
            "warnings": type_result.total_warnings,
            "files_analyzed": type_result.files_scanned,
            "files_with_errors": type_result.files_with_errors,
            "errors_by_category": type_result.errors_by_category,
            "status": "PASS" if type_result.is_compliant else "FAIL",
        }
        if type_result.has_violations:
            overall_exit = 1
        print(f"       {type_result.total_errors} errors, {type_result.total_warnings} warnings in {type_result.files_scanned} files")
        try:
            step_reports["type_check"] = type_checker.generate_report(type_result, "text")
        except Exception:
            step_reports["type_check"] = f"Static Type Checking\n\n{json.dumps({k: v for k, v in scan_results['type_check'].items() if k != 'errors_by_category'}, indent=2)}"
    except Exception as e:
        scan_results["type_check"] = {"status": "ERROR", "error": str(e)}
        print(f"       Error: {e}")

    print("[6/11] Security: Vulnerability Scan...")
    try:
        sec_config = SecurityScanConfig(
            scan_path=scan_path, min_severity="low",
            include_tests=include_tests, exclude_patterns=exclude_patterns, verbose=verbose,
        )
        sec_service = StaticSecurityService(sec_config)
        sec_result = sec_service.scan(scan_path)
        sec_total = sec_result.total_findings if hasattr(sec_result, "total_findings") else 0
        sec_critical = sec_result.critical_count if hasattr(sec_result, "critical_count") else 0
        scan_results["security"] = {
            "total_findings": sec_total,
            "critical": sec_critical,
            "status": "PASS" if sec_total == 0 else "FAIL",
        }
        if sec_total > 0:
            overall_exit = 1
        print(f"       {sec_total} findings ({sec_critical} critical)")
        try:
            step_reports["security"] = sec_service.generate_report(sec_result, "text")
        except Exception:
            step_reports["security"] = f"Security Analysis\n\n{json.dumps(scan_results['security'], indent=2)}"
    except Exception as e:
        scan_results["security"] = {"status": "ERROR", "error": str(e)}
        print(f"       Error: {e}")

    return overall_exit
