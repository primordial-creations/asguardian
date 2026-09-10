"""Validate and execute the reusable gate; planning needs only the standard library."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

CHECKS = {
    "rust": ("rust-clippy", "rust-audit"),
    "node": ("node-lint", "node-audit", "node-typecheck"),
    "go": ("go-vet", "go-build", "go-fmt", "go-test", "go-vuln"),
}
ESLINT_CONFIGS = (
    "eslint.config.js",
    "eslint.config.mjs",
    "eslint.config.cjs",
    "eslint.config.ts",
    ".eslintrc.js",
    ".eslintrc.cjs",
    ".eslintrc.json",
    ".eslintrc.yml",
    ".eslintrc.yaml",
    ".eslintrc",
)
ANALYZER_ROOT = Path(__file__).resolve().parent.parent
ANALYZER_ENTRYPOINT = (
    "import sys; sys.path.insert(0, sys.argv.pop(1)); from Asgard.cli import main; raise SystemExit(main())"
)


def confined_directory(root: Path, value: str) -> Path:
    if not value or "\n" in value or "\r" in value or Path(value).is_absolute():
        raise ValueError("Project paths must be nonempty relative directories within the caller checkout")
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_dir():
        raise ValueError(f"Project directory does not exist inside the caller checkout: {value}")
    return path


def require_file(path: Path) -> None:
    if not path.is_file():
        raise ValueError(f"Required project configuration is missing: {path}")


def plan(root: Path, env: dict[str, str]) -> dict[str, str]:
    language = env.get("GATE_LANGUAGE", "")
    if language not in CHECKS:
        raise ValueError(f"Unknown language: {language!r}; choose rust, node, or go")
    raw_checks = env.get("GATE_CHECKS", "")
    checks = tuple(check.strip() for check in raw_checks.split(",")) if raw_checks else CHECKS[language]
    if any(check not in CHECKS[language] for check in checks) or len(set(checks)) != len(checks):
        raise ValueError(f"Checks must be unique members of {','.join(CHECKS[language])}")
    timeout = env.get("GATE_TIMEOUT", "")
    if timeout and not re.fullmatch(r"[1-9][0-9]*", timeout):
        raise ValueError("timeout-seconds must be a positive integer")
    scan = confined_directory(root, env.get("GATE_SCAN_PATH", "."))
    manifest = {"rust": "Cargo.toml", "node": "package.json", "go": "go.mod"}[language]
    require_file(scan / manifest)
    install = scan
    if language == "node":
        install = confined_directory(root, env.get("GATE_NODE_INSTALL_PATH") or env.get("GATE_SCAN_PATH", "."))
        if not scan.is_relative_to(install):
            raise ValueError("node-install-path must be the scan directory or its npm workspace ancestor")
        require_file(install / "package.json")
        if not any((install / name).is_file() for name in ("package-lock.json", "npm-shrinkwrap.json")):
            raise ValueError(f"Commit an npm lockfile in {install}; this gate installs with npm ci")
        if "node-lint" in checks:
            package = json.loads((scan / "package.json").read_text())
            if not any((scan / name).is_file() for name in ESLINT_CONFIGS) and "eslintConfig" not in package:
                raise ValueError(f"node-lint requires an ESLint configuration in {scan}")
        if "node-typecheck" in checks:
            require_file(scan / "tsconfig.json")
        if "node-audit" in checks and install != scan:
            raise ValueError("node-audit must scan the lockfile root; use a separate gate for workspace audit")
    if language == "rust" and not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", env.get("GATE_RUST_TOOLCHAIN", "")):
        raise ValueError("rust-toolchain must name an exact supported release (X.Y.Z)")
    for check, key, pattern, hint in (
        ("rust-audit", "GATE_CARGO_AUDIT_VERSION", r"[0-9]+\.[0-9]+\.[0-9]+", "cargo-audit-version (X.Y.Z)"),
        ("go-vuln", "GATE_GOVULNCHECK_VERSION", r"v[0-9]+\.[0-9]+\.[0-9]+", "govulncheck-version (vX.Y.Z)"),
    ):
        if check in checks and not re.fullmatch(pattern, env.get(key, "")):
            raise ValueError(f"{check} requires an exact {hint}; floating versions are not accepted")
    if "rust-audit" in checks:
        require_file(scan / "Cargo.lock")
    return {
        "checks": ",".join(checks),
        "scan-path": str(scan.relative_to(root.parent.resolve())),
        "node-install-path": str(install.relative_to(root.parent.resolve())),
        "rust-audit": str("rust-audit" in checks).lower(),
        "go-vuln": str("go-vuln" in checks).lower(),
        "rust-toolchain": env.get("GATE_RUST_TOOLCHAIN", "") if language == "rust" else "",
    }


def run_checks(scan: Path, checks: list[str], timeout: str, install: Path, rust_toolchain: str = "") -> int:
    # Do not let npx satisfy a missing dependency from its download cache.
    for check, tool in (("node-lint", "eslint"), ("node-typecheck", "tsc")):
        if check in checks and not any(
            os.access(directory / "node_modules" / ".bin" / tool, os.X_OK)
            for directory in (scan, *scan.parents)
            if directory.is_relative_to(install)
        ):
            raise ValueError(f"{check} requires locked {tool} in the project's installed devDependencies")
    env = dict(os.environ)
    if any(check.startswith("rust-") for check in checks):
        if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", rust_toolchain):
            raise ValueError("Rust checks require the validated exact rust-toolchain release")
        # rustup default alone loses to rust-toolchain files and directory
        # overrides in the caller. Its explicit environment override wins.
        env["RUSTUP_TOOLCHAIN"] = rust_toolchain
    # The analyser normally prefers global tools. CI must use the project's
    # lockfile versions even if a persistent runner has global eslint/tsc.
    wrapper_path = Path(__file__).resolve().parent / "locked-node-bin"
    env["PATH"] = f"{wrapper_path}{os.pathsep}{env.get('PATH', '')}"
    failed = False
    for check in checks:
        # Use this interpreter and the verified checkout containing this helper.
        # Ignore Python environment overrides and implicit working-directory
        # imports; installed dependencies (including the interpreter's user
        # site) remain available. A PATH console script is not source identity.
        argv = [
            sys.executable,
            "-E",
            "-P",
            "-c",
            ANALYZER_ENTRYPOINT,
            str(ANALYZER_ROOT),
            "heimdall",
            "quality",
            check,
            str(scan),
            "--format",
            "json",
        ]
        if timeout:
            argv += ["--timeout", timeout]
        print(f"Running {check} against {scan}", flush=True)
        result = subprocess.run(argv, capture_output=True, text=True, check=False, env=env)
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        try:
            report = json.loads(result.stdout)
            valid = isinstance(report, dict) and all(
                key in report for key in ("scan_path", "tool_failed", "tools_unavailable", "error_count")
            )
            clean = valid and (
                isinstance(report["scan_path"], str)
                and bool(report["scan_path"])
                and Path(report["scan_path"]).resolve() == scan.resolve()
                and report["tool_failed"] is False
                and report["tools_unavailable"] == []
                and type(report["error_count"]) is int
                and report["error_count"] == 0
            )
        except (ValueError, TypeError):
            clean = False
        if result.returncode != 0 or not clean:
            print(f"Required check {check} failed, did not run, or returned an invalid report", file=sys.stderr)
            failed = True
    return int(failed)


def main() -> int:
    try:
        mode, caller = sys.argv[1:]
        root = Path(caller).resolve()
        if mode == "plan":
            outputs = plan(root, dict(os.environ))
            with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
                output.writelines(f"{key}={value}\n" for key, value in outputs.items())
            return 0
        if mode != "run":
            raise ValueError("Choose plan or run")
        scan = confined_directory(root.parent, os.environ["GATE_SCAN_PATH"])
        install = confined_directory(root.parent, os.environ["GATE_NODE_INSTALL_PATH"])
        if not scan.is_relative_to(root) or not install.is_relative_to(root):
            raise ValueError("Run paths must stay within the caller checkout")
        checks = os.environ["GATE_CHECKS"].split(",")
        if not checks or any(check not in sum(CHECKS.values(), ()) for check in checks):
            raise ValueError("Invalid required checks")
        return run_checks(
            scan, checks, os.environ.get("GATE_TIMEOUT", ""), install, os.environ.get("GATE_RUST_TOOLCHAIN", "")
        )
    except (ValueError, OSError, KeyError) as exc:
        print(f"Quality gate configuration error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
