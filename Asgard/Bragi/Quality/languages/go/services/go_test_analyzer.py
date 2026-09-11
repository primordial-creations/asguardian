"""
Go test result parsing via go test -json.

Orchestrates `go test ./... -json`, the Go toolchain's own structured test
event stream, rather than scraping `go test`'s human-oriented text output.
Verified against real `go test -json` for three shapes: an ordinary
assertion failure (`Action: "fail"` with a `Test` field, preceded by
`Action: "output"` lines carrying the `t.Errorf`/`t.Fatal` message), a
package that fails to compile for testing at all, and a panicking test
(recovered per-test by the `testing` package and reported through the
same per-test `fail` action as an ordinary failure, not a special case).

The compile-failure shape itself differs by Go toolchain version. Go
1.24+ emits a dedicated `Action: "build-fail"` event carrying `ImportPath`,
preceded by `Action: "build-output"` lines with the real compiler
diagnostic in `file:line:col: message` shape -- verified against real
`go test -json` on go1.24.7. Go versions before that (verified on
go1.22.2) emit no such structured event at all: the compiler diagnostic
goes to stderr as plain text (a `# <import path>` header line followed by
`file:line:col: message` lines), and the JSON stream on stdout carries
only an ordinary package-level `Action: "output"` line containing
`FAIL\t<import path> [build failed]` followed by a package-level
`Action: "fail"` with no `Test` field and no `FailedBuild` flag --
indistinguishable, without inspecting that output text, from a package
that failed without a specific failing test (e.g. a bad `TestMain` exit).
`_looks_like_build_failure` and `_stderr_diagnostics_by_package` exist to
recover the same `go-test::build-failed` finding on those older
toolchains, sourcing diagnostics from stderr's `# <import path>` blocks
since none reach the JSON stream in that shape.

The stream has no guaranteed message order (see golang.org/x/vuln's own
Message doc for the equivalent caveat on a different tool), so this
buffers `output`/`build-output` lines by key and only turns them into
findings once fully collected.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from Asgard.Bragi.Quality.languages.common.tool_models import (
    ToolCategory,
    ToolFinding,
    ToolReport,
    ToolSeverity,
)
from Asgard.Bragi.Quality.languages.common.tool_runner import (
    find_manifest_dirs,
    require_executable,
    run_tool,
)
from Asgard.Bragi.Quality.languages.go.models.go_toolchain_models import GoTestConfig
from Asgard.Bragi.Quality.languages.go.services._go_diagnostics import parse_diagnostics

INSTALL_HINT = "Install Go from https://go.dev/dl (go test ships with the go command)."

_SOURCE_LINE_RE = re.compile(r"(?P<file>[A-Za-z0-9_./-]+\.go):(?P<line>\d+):")
_BUILD_FAILED_MARKER_RE = re.compile(r"\[build failed\]")
_STDERR_PACKAGE_HEADER_RE = re.compile(r"^#\s+(?P<import_path>\S+)\s*$")


class GoTestAnalyzer:
    """Runs go test -json over every module found under a scan path and normalises the output."""

    def __init__(self, config: Optional[GoTestConfig] = None) -> None:
        self._config = config or GoTestConfig()

    def analyze(self, scan_path: Optional[Path] = None) -> ToolReport:
        """
        Run go test -json against every Go module found under scan_path.

        Raises ToolNotAvailableError if go is not on PATH.
        """
        path = Path(scan_path) if scan_path else self._config.scan_path
        path = path.resolve()
        start = datetime.now()

        report = ToolReport(scan_path=str(path), language="go", tool="go-test")

        go_bin = require_executable("go", path, INSTALL_HINT)

        module_dirs = find_manifest_dirs(path, "go.mod")
        if not module_dirs:
            report.tools_unavailable.append(f"No go.mod found under {path}; skipping go test.")
            report.scan_duration_seconds = (datetime.now() - start).total_seconds()
            return report

        report.files_analyzed = len(module_dirs)

        for module_dir in module_dirs:
            self._test_module(go_bin, module_dir, path, report)
            if self._config.max_findings and report.total_findings >= self._config.max_findings:
                break

        report.scan_duration_seconds = (datetime.now() - start).total_seconds()
        return report

    def _test_module(self, go_bin: str, module_dir: Path, root: Path, report: ToolReport) -> None:
        cmd = [go_bin, "test", "./...", "-json"]
        result = run_tool(cmd, cwd=module_dir, timeout=self._config.timeout_seconds)

        if result.timed_out:
            report.tools_unavailable.append(
                f"go test timed out after {self._config.timeout_seconds}s in {module_dir}"
            )
            report.tool_failed = True
            return

        module_name = self._module_name(module_dir)
        test_output: Dict[Tuple[str, str], List[str]] = {}
        build_output: Dict[str, List[str]] = {}
        package_test_fails: Dict[str, Set[str]] = {}
        events_parsed = 0
        findings_before = report.total_findings
        stderr_diagnostics = self._stderr_diagnostics_by_package(result.stderr or "")

        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            events_parsed += 1
            action = event.get("Action")

            if action == "output":
                package = event.get("Package", "")
                test = event.get("Test", "")
                test_output.setdefault((package, test), []).append(event.get("Output") or "")
            elif action == "build-output":
                import_path = event.get("ImportPath", "")
                build_output.setdefault(import_path, []).append(event.get("Output") or "")
            elif action == "build-fail":
                import_path = event.get("ImportPath", "")
                self._add_build_fail_finding(import_path, build_output.get(import_path, []), module_dir, root, report)
            elif action == "fail":
                package = event.get("Package", "")
                test = event.get("Test")
                if test:
                    package_test_fails.setdefault(package, set()).add(test)
                    output_lines = test_output.get((package, test), [])
                    self._add_test_fail_finding(
                        package, test, output_lines, module_name, module_dir, root, report
                    )
                elif not event.get("FailedBuild"):
                    # Package-level rollup fail with no specific failing test
                    # and no compile failure: only report it if nothing else
                    # already accounts for the failure, or a real failure
                    # (e.g. TestMain exiting non-zero directly) would be
                    # silently dropped.
                    if not package_test_fails.get(package):
                        output_lines = test_output.get((package, ""), [])
                        if self._looks_like_build_failure(output_lines):
                            # Go toolchains before 1.24 never emit a
                            # structured build-fail/build-output event for
                            # this shape (see module docstring) -- the only
                            # signal on stdout is this package-level fail
                            # plus a "[build failed]" marker in its Output.
                            # Recover the real diagnostic from stderr, where
                            # it was printed as plain text instead.
                            self._add_build_fail_finding(
                                package,
                                stderr_diagnostics.get(package, output_lines),
                                module_dir,
                                root,
                                report,
                            )
                        else:
                            self._add_package_fail_finding(package, output_lines, report)

            if self._config.max_findings and report.total_findings >= self._config.max_findings:
                return

        if events_parsed == 0:
            # Nothing on stdout parsed as a go test -json event at all. A
            # clean/passing run always emits at least a "start" event, so
            # zero events with a nonzero exit means go test itself failed
            # before running anything (a malformed go.mod, a module that
            # cannot be loaded) -- and even a zero exit with zero events is
            # not a real "no tests" pass, since "no test files" still
            # emits a "start"+"skip" pair.
            detail_lines = (result.stderr or result.stdout or "").strip().splitlines()
            detail = detail_lines[-1] if detail_lines else "produced no parseable test events"
            report.tools_unavailable.append(
                f"go test failed to run in {module_dir} (exit {result.returncode}): {detail}"
            )
            report.tool_failed = True
            return

        if result.returncode != 0 and report.total_findings == findings_before:
            # The run reported failure but no failing test/build finding was
            # extracted from the event stream -- an unrecognised failure
            # shape must not be presented as a clean pass.
            report.tools_unavailable.append(
                f"go test exited {result.returncode} in {module_dir} without a parseable failure event"
            )
            report.tool_failed = True

    def _add_test_fail_finding(
        self,
        package: str,
        test: str,
        output_lines: List[str],
        module_name: str,
        module_dir: Path,
        root: Path,
        report: ToolReport,
    ) -> None:
        description = "".join(output_lines).strip() or f"{test} failed"
        file_path, line_number = self._source_hint(output_lines, package, module_name, module_dir, root)
        report.add_finding(
            ToolFinding(
                file_path=file_path,
                line_number=line_number,
                column=0,
                rule_id=f"go-test::{test}",
                category=ToolCategory.BUG,
                severity=ToolSeverity.ERROR,
                title=f"{test} failed" + (f" ({package})" if package else ""),
                description=description,
                code_snippet="",
                fix_suggestion="",
                tool="go-test",
            )
        )

    def _add_build_fail_finding(
        self, import_path: str, output_lines: List[str], module_dir: Path, root: Path, report: ToolReport
    ) -> None:
        combined = "".join(output_lines)
        diagnostics = parse_diagnostics(combined, module_dir, root)
        if diagnostics:
            for diagnostic in diagnostics:
                report.add_finding(
                    ToolFinding(
                        file_path=diagnostic.file_path,
                        line_number=diagnostic.line_number,
                        column=diagnostic.column,
                        rule_id="go-test::build-failed",
                        category=ToolCategory.BUG,
                        severity=ToolSeverity.ERROR,
                        title=f"Test build failed: {diagnostic.message[:150]}",
                        description=diagnostic.message,
                        code_snippet="",
                        fix_suggestion="",
                        tool="go-test",
                    )
                )
        else:
            report.add_finding(
                ToolFinding(
                    file_path=import_path or "go.mod",
                    line_number=0,
                    column=0,
                    rule_id="go-test::build-failed",
                    category=ToolCategory.BUG,
                    severity=ToolSeverity.ERROR,
                    title=f"Test build failed for {import_path}",
                    description=combined.strip() or "go test could not build this package's tests.",
                    code_snippet="",
                    fix_suggestion="",
                    tool="go-test",
                )
            )

    @staticmethod
    def _looks_like_build_failure(output_lines: List[str]) -> bool:
        """True if a package-level fail's buffered Output carries go test's own "[build failed]" marker."""
        return any(_BUILD_FAILED_MARKER_RE.search(line) for line in output_lines)

    @staticmethod
    def _stderr_diagnostics_by_package(stderr: str) -> Dict[str, List[str]]:
        """
        Split go test's stderr into per-package diagnostic blocks.

        On Go toolchains before 1.24, a package that fails to build for
        testing prints its compiler diagnostics to stderr as plain text,
        headed by a `# <import path>` line (the same shape `go build`
        itself uses), rather than through the JSON event stream on stdout.
        """
        diagnostics: Dict[str, List[str]] = {}
        current: Optional[str] = None
        for line in stderr.splitlines():
            header = _STDERR_PACKAGE_HEADER_RE.match(line)
            if header:
                current = header.group("import_path")
                diagnostics.setdefault(current, [])
                continue
            if current is not None:
                diagnostics[current].append(line + "\n")
        return diagnostics

    def _add_package_fail_finding(self, package: str, output_lines: List[str], report: ToolReport) -> None:
        description = "".join(output_lines).strip() or f"{package} failed without a specific failing test"
        report.add_finding(
            ToolFinding(
                file_path=package or "go.mod",
                line_number=0,
                column=0,
                rule_id="go-test::package-failed",
                category=ToolCategory.BUG,
                severity=ToolSeverity.ERROR,
                title=f"{package} failed",
                description=description,
                code_snippet="",
                fix_suggestion="",
                tool="go-test",
            )
        )

    @staticmethod
    def _module_name(module_dir: Path) -> str:
        """Read the `module <path>` directive from module_dir/go.mod."""
        try:
            text = (module_dir / "go.mod").read_text(encoding="utf-8")
        except OSError:
            return ""
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("module "):
                return line[len("module "):].strip()
        return ""

    @staticmethod
    def _source_hint(
        output_lines: List[str], package: str, module_name: str, module_dir: Path, root: Path
    ) -> Tuple[str, int]:
        # go test's runtime reports a failing source file as a bare
        # filename (e.g. "add_test.go"), relative to the package's own
        # directory, not the module root -- so the package's import path
        # (minus the module prefix) must be joined back in to resolve a
        # subpackage's file correctly.
        package_subdir = ""
        if module_name and package.startswith(module_name):
            package_subdir = package[len(module_name):].lstrip("/")

        for entry in output_lines:
            match = _SOURCE_LINE_RE.search(entry)
            if match:
                try:
                    absolute = (module_dir / package_subdir / match.group("file")).resolve()
                    relative_path = str(absolute.relative_to(root))
                except ValueError:
                    relative_path = match.group("file")
                return relative_path, int(match.group("line"))

        try:
            package_dir = (module_dir / package_subdir).resolve()
            relative_module = str(package_dir.relative_to(root))
        except ValueError:
            relative_module = str(module_dir)
        return relative_module, 0
