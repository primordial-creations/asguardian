"""
Heimdall Gap Analyzer - multi-language collection helpers.

Walks a scan path for JS/TS/Go source and test files, extracts production
methods and test "signals" via
``Asgard.Bragi.Coverage.utilities.multilang_extractor``, and reports honest
per-language status (ok / insufficient_data / unsupported) so callers never
silently show a fabricated 0% or 100% for a language that wasn't actually
measured.
"""
from pathlib import Path
from typing import Dict, List, Tuple

from Asgard.Bragi.Coverage.models.coverage_models import (
    ClassCoverage,
    CoverageConfig,
    MethodInfo,
)
from Asgard.Bragi.Coverage.services._gap_analysis_helpers import (
    build_test_name_set,
    is_method_covered,
)
from Asgard.Bragi.Coverage.utilities.multilang_extractor import (
    SUPPORTED_LANGUAGES,
    extract_production_methods,
    extract_test_signal_methods,
    is_test_file,
)
from Asgard.Bragi.Quality.utilities.file_utils import scan_directory
from Asgard.Heimdall.treesitter._language_loader import is_available
from Asgard.Shared.common.language_registry import EXTENSION_TO_LANGUAGE

#: Non-Python extensions worth walking for coverage. Only languages in
#: multilang_extractor.SUPPORTED_LANGUAGES are actually measured; the rest
#: (java, csharp, ruby, php, rust, cpp — CIR-supported for OOP but without
#: coverage test-file conventions wired here yet) are still walked so they
#: are surfaced honestly as "unsupported" in language_status rather than
#: silently skipped and absent from the report.
_ML_EXTENSIONS = [
    ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".go",
    ".java", ".cs", ".rb", ".php", ".rs", ".cpp", ".cxx", ".cc", ".hpp",
]


def collect_multilang_methods(
    scan_path: Path, config: CoverageConfig
) -> Tuple[List[MethodInfo], List[MethodInfo], Dict[str, str]]:
    """Return (production_methods, test_signal_methods, language_status).

    ``language_status`` maps language name to one of:
    - "ok": grammar available, files found and parsed.
    - "insufficient_data: tree-sitter grammar unavailable": files of this
      language exist but couldn't be parsed.
    - "unsupported: no coverage heuristics implemented yet": files of this
      language exist but multilang_extractor has no support for it.
    """
    production: List[MethodInfo] = []
    tests: List[MethodInfo] = []
    status: Dict[str, str] = {}

    exclude_patterns = list(config.exclude_patterns)
    exclude_patterns.extend(["node_modules", "vendor", "dist", "build"])

    for file_path in scan_directory(
        scan_path,
        exclude_patterns=exclude_patterns,
        include_extensions=_ML_EXTENSIONS,
    ):
        language = EXTENSION_TO_LANGUAGE.get(file_path.suffix.lower())
        if not language:
            continue

        if language not in SUPPORTED_LANGUAGES:
            status.setdefault(
                language,
                "unsupported: no coverage heuristics implemented yet",
            )
            continue

        if not is_available(language):
            status[language] = "insufficient_data: tree-sitter grammar unavailable"
            continue

        try:
            source = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        if is_test_file(file_path, language):
            tests.extend(extract_test_signal_methods(source, str(file_path), language))
        else:
            production.extend(extract_production_methods(source, str(file_path), language))

        status[language] = "ok"

    return production, tests, status


def multilang_class_coverage(
    production_methods: List[MethodInfo],
    test_methods: List[MethodInfo],
) -> List[ClassCoverage]:
    """Class-level coverage for non-Python class/struct methods.

    Groups the multi-language production methods that belong to a class
    (``class_name`` set — i.e. not top-level functions) by
    ``(class_name, file_path)`` and reuses the same string-matching
    coverage helpers the Python path uses.
    """
    test_names = build_test_name_set(test_methods)

    grouped: Dict[Tuple[str, str], List[MethodInfo]] = {}
    for method in production_methods:
        if not method.class_name:
            continue
        grouped.setdefault((method.class_name, method.file_path), []).append(method)

    result: List[ClassCoverage] = []
    for (class_name, file_path), methods in grouped.items():
        covered = [m for m in methods if is_method_covered(m, test_names)]
        uncovered = [m.name for m in methods if not is_method_covered(m, test_names)]
        coverage_pct = (len(covered) / len(methods)) * 100 if methods else 100

        result.append(ClassCoverage(
            class_name=class_name,
            file_path=file_path,
            total_methods=len(methods),
            covered_methods=len(covered),
            uncovered_methods=uncovered,
            coverage_percent=coverage_pct,
        ))

    return result
