"""
Heimdall Requirements Checker Service

Validates that all imported packages are listed in requirements files
and identifies unused packages.
"""

import ast
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from Asgard.Heimdall.Dependencies.models.requirements_models import (
    ImportInfo,
    PackageInfo,
    RequirementsConfig,
    RequirementsIssue,
    RequirementsIssueType,
    RequirementsResult,
    RequirementsSeverity,
)
from Asgard.Heimdall.Dependencies.services._requirements_data import (
    IMPORT_TO_PACKAGE_MAP,
    STDLIB_MODULES,
    ImportVisitor,
)
from Asgard.Heimdall.Dependencies.services._requirements_reporter import (
    generate_json_report,
    generate_markdown_report,
    generate_text_report,
)


class RequirementsChecker:
    """
    Validates requirements.txt against actual imports in the codebase.

    Features:
    - Detects missing packages (imported but not in requirements)
    - Detects unused packages (in requirements but not imported)
    - Handles import name to package name mapping
    - Supports multiple requirements files
    """

    def __init__(self, config: RequirementsConfig):
        """Initialize the requirements checker."""
        self.config = config
        self._import_to_package = IMPORT_TO_PACKAGE_MAP.copy()

    def analyze(self) -> RequirementsResult:
        """
        Run requirements analysis on the configured path.

        Returns:
            RequirementsResult with all findings
        """
        start_time = time.time()
        scan_path = Path(self.config.scan_path).resolve()

        if not scan_path.exists():
            raise FileNotFoundError(f"Path not found: {scan_path}")

        requirements, req_files = self._parse_requirements(scan_path)
        imports, files_scanned = self._scan_imports(scan_path)
        issues = self._find_issues(requirements, imports)
        duration = time.time() - start_time

        return RequirementsResult(
            scan_path=str(scan_path),
            scanned_at=datetime.now(),
            scan_duration_seconds=duration,
            config=self.config,
            requirements=requirements,
            requirements_files_found=req_files,
            imports=imports,
            files_scanned=files_scanned,
            issues=issues,
            import_to_package_map=self._import_to_package,
        )

    def sync(self, result: RequirementsResult, target_file: str = "requirements.txt") -> int:
        """
        Synchronize requirements.txt based on analysis.

        Returns number of changes made.
        """
        scan_path = Path(self.config.scan_path).resolve()
        req_file = scan_path / target_file
        changes = 0

        existing_lines = []
        if req_file.exists():
            existing_lines = req_file.read_text().strip().split("\n")

        additions = result.get_suggested_additions()
        for pkg in additions:
            if not any(pkg.lower() in line.lower() for line in existing_lines):
                existing_lines.append(pkg)
                changes += 1

        if self.config.check_unused:
            removals = set(result.get_suggested_removals())
            new_lines = []
            for line in existing_lines:
                pkg_name = self._parse_package_name_from_line(line)
                if pkg_name and pkg_name.lower() in [r.lower() for r in removals]:
                    changes += 1
                    continue
                new_lines.append(line)
            existing_lines = new_lines

        if changes > 0:
            req_file.write_text("\n".join(existing_lines) + "\n")

        return changes

    def _parse_requirements(self, scan_path: Path) -> tuple[List[PackageInfo], List[str]]:
        """Parse all requirements files."""
        packages = []
        found_files = []

        for req_file in self.config.requirements_files:
            req_path = scan_path / req_file
            if req_path.exists():
                found_files.append(req_file)
                packages.extend(self._parse_requirements_file(req_path))

        return packages, found_files

    def _parse_requirements_file(self, req_path: Path) -> List[PackageInfo]:
        """Parse a single requirements file."""
        packages = []
        content = req_path.read_text()

        for line_num, line in enumerate(content.split("\n"), 1):
            line = line.strip()

            if not line or line.startswith("#"):
                continue
            if line.startswith("-r") or line.startswith("--requirement"):
                continue

            is_editable = line.startswith("-e") or line.startswith("--editable")
            if is_editable:
                line = line.split(None, 1)[1] if " " in line else ""

            pkg_info = self._parse_package_line(line, str(req_path), line_num, is_editable)
            if pkg_info:
                packages.append(pkg_info)

        return packages

    def _parse_package_line(
        self, line: str, source_file: str, line_number: int, is_editable: bool
    ) -> Optional[PackageInfo]:
        """Parse a single package line from requirements."""
        if not line:
            return None

        extras = []
        extras_match = re.search(r"\[([^\]]+)\]", line)
        if extras_match:
            extras = [e.strip() for e in extras_match.group(1).split(",")]
            line = line[:extras_match.start()] + line[extras_match.end():]

        version = None
        version_spec = None
        for op in ["===", "~=", "==", ">=", "<=", "!=", ">", "<"]:
            if op in line:
                parts = line.split(op, 1)
                name = parts[0].strip()
                version_spec = op + parts[1].split(";")[0].strip()
                version = parts[1].split(";")[0].strip()
                break
        else:
            name = line.split(";")[0].strip()

        if not name:
            return None

        return PackageInfo(
            name=name.lower(),
            version=version,
            version_spec=version_spec,
            source_file=source_file,
            line_number=line_number,
            extras=extras,
            is_editable=is_editable,
        )

    def _parse_package_name_from_line(self, line: str) -> Optional[str]:
        """Extract package name from a requirements line."""
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            return None

        if "[" in line:
            line = line.split("[")[0]

        for op in ["===", "~=", "==", ">=", "<=", "!=", ">", "<"]:
            if op in line:
                line = line.split(op)[0]
                break

        if ";" in line:
            line = line.split(";")[0]

        return line.strip()

    def _scan_imports(self, scan_path: Path) -> tuple[List[ImportInfo], int]:
        """Scan all Python files for imports."""
        imports = []
        files_scanned = 0

        for ext in self.config.include_extensions:
            pattern = f"**/*{ext}"
            for file_path in scan_path.glob(pattern):
                if self._should_include_file(file_path):
                    file_imports = self._extract_imports(file_path, scan_path)
                    imports.extend(file_imports)
                    files_scanned += 1

        return imports, files_scanned

    def _should_include_file(self, file_path: Path) -> bool:
        """Check if a file should be included in analysis."""
        path_str = str(file_path)
        for pattern in self.config.exclude_patterns:
            if pattern in path_str:
                return False
        return True

    def _extract_imports(self, file_path: Path, scan_path: Path) -> List[ImportInfo]:
        """Extract imports from a single file."""
        imports = []

        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
            visitor = ImportVisitor()
            visitor.visit(tree)

            rel_path = str(file_path.relative_to(scan_path))

            for imp in visitor.imports:
                imports.append(ImportInfo(
                    package_name=imp["package_name"],
                    import_statement=imp["import_statement"],
                    file_path=rel_path,
                    line_number=imp["line_number"],
                    import_type=imp["import_type"],
                ))
        except (SyntaxError, UnicodeDecodeError):
            pass

        return imports

    def _find_issues(
        self, requirements: List[PackageInfo], imports: List[ImportInfo]
    ) -> List[RequirementsIssue]:
        """Find discrepancies between requirements and imports."""
        issues = []
        req_packages = {pkg.name.lower() for pkg in requirements}

        imported_packages: Set[str] = set()
        import_locations: Dict[str, List[str]] = {}

        for imp in imports:
            pkg = imp.package_name.lower()

            if pkg in STDLIB_MODULES:
                continue

            mapped_pkg = self._import_to_package.get(pkg, pkg).lower()
            imported_packages.add(mapped_pkg)

            if mapped_pkg not in import_locations:
                import_locations[mapped_pkg] = []
            import_locations[mapped_pkg].append(f"{imp.file_path}:{imp.line_number}")

        for pkg in imported_packages:
            if pkg not in req_packages:
                if not self._is_local_package(pkg, Path(self.config.scan_path)):
                    locations = import_locations.get(pkg, [])
                    issues.append(RequirementsIssue(
                        issue_type=RequirementsIssueType.MISSING,
                        severity=RequirementsSeverity.ERROR,
                        package_name=pkg,
                        message=f"Package '{pkg}' is imported but not in requirements",
                        details={
                            "locations": locations[:5],
                            "total_imports": len(locations),
                        },
                    ))

        if self.config.check_unused:
            for pkg in requirements:
                pkg_name = pkg.name.lower()
                is_used = pkg_name in imported_packages

                for import_name, package_name in self._import_to_package.items():
                    if package_name.lower() == pkg_name and import_name.lower() in {
                        i.package_name.lower() for i in imports
                    }:
                        is_used = True
                        break

                if not is_used:
                    issues.append(RequirementsIssue(
                        issue_type=RequirementsIssueType.UNUSED,
                        severity=RequirementsSeverity.WARNING,
                        package_name=pkg_name,
                        message=f"Package '{pkg_name}' in requirements but not imported",
                        details={
                            "file": pkg.source_file,
                            "line": pkg.line_number,
                        },
                    ))

        return issues

    def _is_local_package(self, package_name: str, scan_path: Path) -> bool:
        """Check if a package name corresponds to a local package/module."""
        pkg_dir = scan_path / package_name
        if pkg_dir.is_dir() and (pkg_dir / "__init__.py").exists():
            return True

        pkg_file = scan_path / f"{package_name}.py"
        if pkg_file.exists():
            return True

        return False

    def generate_report(self, result: RequirementsResult, output_format: str = "text") -> str:
        """Generate a formatted report."""
        if output_format == "json":
            return generate_json_report(result)
        elif output_format == "markdown":
            return generate_markdown_report(result)
        else:
            return generate_text_report(result)
