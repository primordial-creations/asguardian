"""Heimdall Requirements Checker -- validates imports against requirements files."""

import ast
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from Asgard.Bragi.Dependencies.models.requirements_models import (
    ImportInfo,
    PackageInfo,
    RequirementsConfig,
    RequirementsIssue,
    RequirementsIssueType,
    RequirementsResult,
    RequirementsSeverity,
)
from Asgard.Bragi.Dependencies.services._requirements_data import (
    IMPORT_TO_PACKAGE_MAP,
    STDLIB_MODULES,
    ImportVisitor,
)
from Asgard.Bragi.Dependencies.services._requirements_reporter import (
    generate_json_report,
    generate_markdown_report,
    generate_text_report,
)


class RequirementsChecker:
    """Validates requirements.txt against actual imports in the codebase."""

    def __init__(self, config: RequirementsConfig):
        self.config = config
        self._import_to_package = IMPORT_TO_PACKAGE_MAP.copy()

    def analyze(self) -> RequirementsResult:
        """Run requirements analysis on the configured path."""
        start_time = time.time()
        scan_path = Path(self.config.scan_path).resolve()
        if not scan_path.exists():
            raise FileNotFoundError(f"Path not found: {scan_path}")
        requirements, req_files = self._parse_requirements(scan_path)
        imports, files_scanned = self._scan_imports(scan_path)
        issues = self._find_issues(requirements, imports)
        return RequirementsResult(
            scan_path=str(scan_path), scanned_at=datetime.now(),
            scan_duration_seconds=time.time() - start_time,
            config=self.config, requirements=requirements,
            requirements_files_found=req_files, imports=imports,
            files_scanned=files_scanned, issues=issues,
            import_to_package_map=self._import_to_package,
        )

    def sync(self, result: RequirementsResult, target_file: str = "requirements.txt") -> int:
        """Synchronize requirements.txt based on analysis. Returns number of changes."""
        scan_path = Path(self.config.scan_path).resolve()
        req_file = scan_path / target_file
        changes = 0
        existing_lines = []
        if req_file.exists():
            existing_lines = req_file.read_text().strip().split("\n")
        for pkg in result.get_suggested_additions():
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
        packages = []
        found_files = []
        for req_file in self.config.requirements_files:
            req_path = scan_path / req_file
            if req_path.exists():
                found_files.append(req_file)
                packages.extend(self._parse_requirements_file(req_path))
        return packages, found_files

    def _parse_requirements_file(self, req_path: Path) -> List[PackageInfo]:
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
            name=name.lower(), version=version, version_spec=version_spec,
            source_file=source_file, line_number=line_number,
            extras=extras, is_editable=is_editable,
        )

    def _parse_package_name_from_line(self, line: str) -> Optional[str]:
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
        imports = []
        files_scanned = 0
        for ext in self.config.include_extensions:
            for file_path in scan_path.glob(f"**/*{ext}"):
                if self._should_include_file(file_path):
                    imports.extend(self._extract_imports(file_path, scan_path))
                    files_scanned += 1
        return imports, files_scanned

    def _should_include_file(self, file_path: Path) -> bool:
        path_str = str(file_path)
        for pattern in self.config.exclude_patterns:
            if pattern in path_str:
                return False
        return True

    def _extract_imports(self, file_path: Path, scan_path: Path) -> List[ImportInfo]:
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
                    file_path=rel_path, line_number=imp["line_number"],
                    import_type=imp["import_type"],
                ))
        except (SyntaxError, UnicodeDecodeError):
            pass
        return imports

    def _find_issues(
        self, requirements: List[PackageInfo], imports: List[ImportInfo]
    ) -> List[RequirementsIssue]:
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
                        severity=RequirementsSeverity.ERROR, package_name=pkg,
                        message=f"Package '{pkg}' is imported but not in requirements",
                        details={"locations": locations[:5], "total_imports": len(locations)},
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
                        severity=RequirementsSeverity.WARNING, package_name=pkg_name,
                        message=f"Package '{pkg_name}' in requirements but not imported",
                        details={"file": pkg.source_file, "line": pkg.line_number},
                    ))
        return issues

    def _is_local_package(self, package_name: str, scan_path: Path) -> bool:
        pkg_dir = scan_path / package_name
        if pkg_dir.is_dir() and (pkg_dir / "__init__.py").exists():
            return True
        return (scan_path / f"{package_name}.py").exists()

    def generate_report(self, result: RequirementsResult, output_format: str = "text") -> str:
        """Generate a formatted report."""
        if output_format == "json":
            return generate_json_report(result)
        elif output_format == "markdown":
            return generate_markdown_report(result)
        return generate_text_report(result)
