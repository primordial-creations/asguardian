"""Offline workflow source-selection, project preflight and dispatch contracts."""

import importlib.util
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/reusable-quality-gate.yml").read_text())
STEPS = WORKFLOW["jobs"]["quality-gate"]["steps"]
SPEC = importlib.util.spec_from_file_location("reusable_gate", ROOT / "scripts/reusable_quality_gate.py")
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def step(name):
    return next(item for item in STEPS if item["name"] == name)


def select_source(tmp_path, called, requested="", repository="primordial-creations/asguardian"):
    output = tmp_path / "output"
    result = subprocess.run(
        ["bash", "-c", step("Resolve immutable analyzer source")["run"]],
        env={
            **os.environ,
            "GITHUB_OUTPUT": str(output),
            "CALLED_SHA": called,
            "CALLED_REPOSITORY": repository,
            "REQUESTED_SHA": requested,
            "GITHUB_SHA": "b" * 40,
        },
        capture_output=True,
        text=True,
        check=False,
    )
    return result, output.read_text() if output.exists() else ""


@pytest.mark.parametrize("requested", ["", "a" * 40])
def test_called_workflow_sha_wins_over_different_caller_sha(tmp_path, requested):
    result, output = select_source(tmp_path, "a" * 40, requested)
    assert result.returncode == 0, result.stderr
    assert f"sha={'a' * 40}\n" in output
    assert "b" * 40 not in output
    source_env = step("Resolve immutable analyzer source")["env"]
    assert source_env["CALLED_SHA"] == "${{ job.workflow_sha }}"
    assert source_env["CALLED_REPOSITORY"] == "${{ job.workflow_repository }}"


@pytest.mark.parametrize("value", ["main", "v1.2.3", "a" * 7, "", "a" * 40 + "\nsha=main", "$(touch owned)"])
def test_missing_called_identity_requires_full_immutable_fallback(tmp_path, value):
    result, output = select_source(tmp_path, "", value)
    assert result.returncode != 0
    assert output == ""


def test_ghes_explicit_sha_fallback(tmp_path):
    result, output = select_source(tmp_path, "", "a" * 40, "")
    assert result.returncode == 0
    assert "repository=primordial-creations/asguardian\n" in output


def test_mismatched_explicit_override_cannot_select_different_analyzer(tmp_path):
    result, output = select_source(tmp_path, "a" * 40, "c" * 40)
    assert result.returncode != 0
    assert "must match" in result.stderr
    assert output == ""


def test_checkout_uses_validated_selection_and_is_verified(tmp_path):
    checkout = step("Checkout asguardian")["with"]
    assert checkout["ref"] == "${{ steps.source.outputs.sha }}"
    assert checkout["repository"] == "${{ steps.source.outputs.repository }}"
    caller_path = Path(step("Checkout caller repo")["with"]["path"])
    assert not Path(checkout["path"]).is_relative_to(caller_path)
    subprocess.run(["git", "init", "-q", str(tmp_path / ".asguardian-src")], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path / ".asguardian-src"),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "--allow-empty",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    sha = subprocess.check_output(
        ["git", "-C", str(tmp_path / ".asguardian-src"), "rev-parse", "HEAD"], text=True
    ).strip()
    for expected, status in [(sha, 0), ("0" * 40, 1)]:
        result = subprocess.run(
            ["bash", "-c", step("Verify analyzer checkout")["run"]],
            cwd=tmp_path,
            env={**os.environ, "ANALYZER_SHA": expected},
            check=False,
        )
        assert result.returncode == status


@pytest.fixture
def caller(tmp_path):
    root = tmp_path / "caller"
    root.mkdir()
    return root


def node_project(path):
    (path / "package.json").write_text('{"name":"fixture","private":true}')
    (path / "package-lock.json").write_text('{"lockfileVersion":3}')
    (path / "eslint.config.js").write_text("export default [];\n")
    (path / "tsconfig.json").write_text("{}")


def test_default_node_checks_require_and_select_real_caller(caller):
    node_project(caller)
    result = gate.plan(caller, {"GATE_LANGUAGE": "node"})
    assert result["checks"] == "node-lint,node-audit,node-typecheck"
    assert result["scan-path"] == "caller"
    assert result["rust-audit"] == result["go-vuln"] == "false"


@pytest.mark.parametrize("missing", ["package.json", "package-lock.json", "eslint.config.js", "tsconfig.json"])
def test_requested_node_check_missing_config_fails_before_install(caller, missing):
    node_project(caller)
    (caller / missing).unlink()
    with pytest.raises(ValueError):
        gate.plan(caller, {"GATE_LANGUAGE": "node"})


def test_javascript_project_can_explicitly_select_only_applicable_checks(caller):
    node_project(caller)
    (caller / "tsconfig.json").unlink()
    result = gate.plan(caller, {"GATE_LANGUAGE": "node", "GATE_CHECKS": "node-lint,node-audit"})
    assert result["checks"] == "node-lint,node-audit"


@pytest.mark.parametrize("checks", ["node-lint,", "node-lint,node-lint", "go-vet", "$(touch owned)", " "])
def test_invalid_check_selection_is_rejected(caller, checks):
    node_project(caller)
    with pytest.raises(ValueError, match="Checks must"):
        gate.plan(caller, {"GATE_LANGUAGE": "node", "GATE_CHECKS": checks})


@pytest.mark.parametrize("scan", ["../.asguardian-src", "..", "/tmp", "missing", "link", ".\nchecks=go-vet"])
def test_scan_cannot_escape_or_select_scanner_fixtures(caller, scan):
    scanner = caller.parent / ".asguardian-src"
    scanner.mkdir()
    node_project(scanner)
    (caller / "link").symlink_to(scanner, target_is_directory=True)
    with pytest.raises(ValueError):
        gate.plan(caller, {"GATE_LANGUAGE": "node", "GATE_SCAN_PATH": scan})


def test_manifestless_root_does_not_discover_scanner_or_nested_fixture(caller):
    fixture = caller / "fixtures"
    fixture.mkdir()
    node_project(fixture)
    with pytest.raises(ValueError, match=r"package\.json"):
        gate.plan(caller, {"GATE_LANGUAGE": "node"})


def test_workspace_install_root_and_scan_member_are_separate(caller):
    node_project(caller)
    member = caller / "member"
    member.mkdir()
    node_project(member)
    (member / "package-lock.json").unlink()
    env = {
        "GATE_LANGUAGE": "node",
        "GATE_SCAN_PATH": "member",
        "GATE_NODE_INSTALL_PATH": ".",
        "GATE_CHECKS": "node-lint,node-typecheck",
    }
    outputs = gate.plan(caller, env)
    assert outputs["node-install-path"] == "caller"
    assert outputs["scan-path"] == "caller/member"
    with pytest.raises(ValueError, match="lockfile root"):
        gate.plan(caller, {**env, "GATE_CHECKS": "node-audit"})


@pytest.mark.parametrize("version", ["", "latest", "^1.2.3", "1.2", "v1.2.3;echo hacked"])
def test_selected_go_vulnerability_tool_requires_exact_version(caller, version):
    (caller / "go.mod").write_text("module example.invalid/fixture\ngo 1.24\n")
    with pytest.raises(ValueError, match="govulncheck-version"):
        gate.plan(caller, {"GATE_LANGUAGE": "go", "GATE_GOVULNCHECK_VERSION": version})


def test_subset_does_not_install_unrequested_audit_tools(caller):
    (caller / "go.mod").write_text("module example.invalid/fixture\ngo 1.24\n")
    result = gate.plan(caller, {"GATE_LANGUAGE": "go", "GATE_CHECKS": "go-fmt"})
    assert result["go-vuln"] == "false"
    assert step("Install selected govulncheck version")["if"] == "steps.plan.outputs.go-vuln == 'true'"
    assert step("Install selected cargo-audit version")["if"] == "steps.plan.outputs.rust-audit == 'true'"


def test_rust_release_and_audit_lock_are_required(caller):
    (caller / "Cargo.toml").write_text('[package]\nname = "fixture"\nversion = "0.1.0"\n')
    env = {"GATE_LANGUAGE": "rust", "GATE_RUST_TOOLCHAIN": "1.90.0", "GATE_CARGO_AUDIT_VERSION": "0.22.2"}
    with pytest.raises(ValueError, match=r"Cargo\.lock"):
        gate.plan(caller, env)
    (caller / "Cargo.lock").write_text("version = 4\n")
    assert gate.plan(caller, env)["rust-audit"] == "true"
    with pytest.raises(ValueError, match="exact supported release"):
        gate.plan(caller, {**env, "GATE_RUST_TOOLCHAIN": "stable"})
    with pytest.raises(ValueError, match="cargo-audit-version"):
        gate.plan(caller, {**env, "GATE_CARGO_AUDIT_VERSION": "latest"})


@pytest.mark.parametrize("timeout", ["0", "-1", "3.1", "20; exit 0", "\n20"])
def test_invalid_timeout_fails_preflight(caller, timeout):
    with pytest.raises(ValueError, match="positive integer"):
        gate.plan(caller, {"GATE_LANGUAGE": "go", "GATE_CHECKS": "go-fmt", "GATE_TIMEOUT": timeout})


def clean_report(scan):
    return {"scan_path": str(scan), "tool_failed": False, "tools_unavailable": [], "error_count": 0}


@pytest.mark.parametrize(
    "change",
    [
        {"tools_unavailable": ["No tool or configuration"]},
        {"tool_failed": True},
        {"error_count": 1},
        {"scan_path": "/wrong/project"},
        {"tool_failed": "false"},
        {"error_count": False},
        {"error_count": 0.0},
        {"scan_path": ""},
    ],
)
def test_even_zero_exit_cannot_pass_incomplete_or_wrong_scan(caller, monkeypatch, change):
    report = {**clean_report(caller), **change}
    execute = Mock(return_value=subprocess.CompletedProcess([], 0, json.dumps(report), ""))
    monkeypatch.setattr(gate.subprocess, "run", execute)
    assert gate.run_checks(caller, ["go-fmt"], "", caller) == 1


@pytest.mark.parametrize("output", ["", "not json", "[]", "{}", "null"])
def test_invalid_reports_fail(caller, monkeypatch, output):
    monkeypatch.setattr(gate.subprocess, "run", Mock(return_value=subprocess.CompletedProcess([], 0, output, "")))
    assert gate.run_checks(caller, ["go-fmt"], "", caller) == 1


def test_all_checks_attempted_and_exit_failure_preserved(caller, monkeypatch):
    execute = Mock(
        side_effect=[
            subprocess.CompletedProcess([], 2, json.dumps(clean_report(caller)), "tool failed"),
            subprocess.CompletedProcess([], 0, json.dumps(clean_report(caller)), ""),
        ]
    )
    monkeypatch.setattr(gate.subprocess, "run", execute)
    assert gate.run_checks(caller, ["go-vet", "go-fmt"], "45", caller) == 1
    for call, check in zip(execute.call_args_list, ("go-vet", "go-fmt"), strict=True):
        assert call.args[0][:4] == [sys.executable, "-E", "-P", "-c"]
        assert call.args[0][5:9] == [str(ROOT), "heimdall", "quality", check]
    assert execute.call_args_list[1].args[0][-2:] == ["--timeout", "45"]


def test_clean_executed_report_passes(caller, monkeypatch):
    monkeypatch.setattr(
        gate.subprocess,
        "run",
        Mock(return_value=subprocess.CompletedProcess([], 0, json.dumps(clean_report(caller)), "")),
    )
    assert gate.run_checks(caller, ["go-fmt"], "", caller) == 0


def test_path_console_script_cannot_substitute_a_clean_report(caller, monkeypatch):
    fake_bin = caller.parent / "fake-bin"
    fake_bin.mkdir()
    marker = caller.parent / "wrong-scanner-ran"
    scanner = fake_bin / "heimdall"
    scanner.write_text(
        f"#!/bin/sh\ntouch {shlex.quote(str(marker))}\nprintf '%s\\n' {shlex.quote(json.dumps(clean_report(caller)))}\n"
    )
    scanner.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.chdir(caller.parent)

    # No manifest: the actual source CLI must reject this request before any
    # tool runs. A stray old console script would supply the fake clean report.
    assert gate.run_checks(caller, ["go-fmt"], "", caller) == 1
    assert not marker.exists()


@pytest.mark.parametrize("injection", ["cwd", "pythonpath"])
def test_source_dispatch_ignores_other_asgard_imports(caller, monkeypatch, injection):
    shadow_root = caller.parent / "shadow"
    shadow_package = shadow_root / "Asgard"
    shadow_package.mkdir(parents=True)
    marker = caller.parent / "wrong-package-imported"
    (shadow_package / "__init__.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\n"
        "raise RuntimeError('shadow Asgard must never be imported')\n"
    )
    monkeypatch.chdir(shadow_root if injection == "cwd" else caller.parent)
    monkeypatch.setenv("PYTHONPATH", str(shadow_root) if injection == "pythonpath" else "")
    real_run = subprocess.run
    results = []

    def record_run(*args, **kwargs):
        result = real_run(*args, **kwargs)
        results.append(result)
        return result

    monkeypatch.setattr(gate.subprocess, "run", record_run)
    assert gate.run_checks(caller, ["go-fmt"], "", caller) == 1
    assert not marker.exists()
    assert len(results) == 1
    report = json.loads(results[0].stdout)
    assert report["scan_path"] == str(caller)
    assert report["tools_unavailable"]


@pytest.mark.parametrize("check", ["node-lint", "node-typecheck"])
def test_missing_installed_node_tool_fails_without_npx_cache_fallback(caller, monkeypatch, check):
    execute = Mock()
    monkeypatch.setattr(gate.subprocess, "run", execute)
    with pytest.raises(ValueError, match="installed devDependencies"):
        gate.run_checks(caller, [check], "", caller)
    execute.assert_not_called()


def test_node_dispatch_uses_locked_tool_wrappers_before_global_tools(caller, monkeypatch):
    tool_dir = caller / "node_modules/.bin"
    tool_dir.mkdir(parents=True)
    (tool_dir / "tsc").symlink_to("/bin/true")
    execute = Mock(return_value=subprocess.CompletedProcess([], 0, json.dumps(clean_report(caller)), ""))
    monkeypatch.setattr(gate.subprocess, "run", execute)
    assert gate.run_checks(caller, ["node-typecheck"], "", caller) == 0
    first_path = execute.call_args.kwargs["env"]["PATH"].split(os.pathsep)[0]
    assert Path(first_path) == ROOT / "scripts/locked-node-bin"
    assert os.access(Path(first_path) / "tsc", os.X_OK)


def test_real_cli_json_is_a_single_document_without_html_footer(caller):
    # No tool is needed: a missing-config report still exercises the real CLI
    # parser, handler, JSON serializer and finally block that emitted the footer.
    result = subprocess.run(
        [sys.executable, "-m", "Asgard.Heimdall", "quality", "node-typecheck", str(caller), "--format", "json"],
        cwd=caller.parent,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        check=False,
    )
    report = json.loads(result.stdout)
    assert report["scan_path"] == str(caller)
    assert report["tools_unavailable"]
    assert "Report saved:" in result.stderr
    assert list((caller.parent / ".asgard/reports").glob("heimdall_report_*.html"))


def test_selected_rust_release_overrides_caller_files_and_inherited_environment(caller, monkeypatch):
    (caller / "Cargo.toml").write_text('[package]\nname="fixture"\nversion="0.1.0"\n')
    (caller / "rust-toolchain.toml").write_text('[toolchain]\nchannel="nightly"\n')
    monkeypatch.setenv("RUSTUP_TOOLCHAIN", "nightly")
    outputs = gate.plan(
        caller,
        {
            "GATE_LANGUAGE": "rust",
            "GATE_CHECKS": "rust-clippy",
            "GATE_RUST_TOOLCHAIN": "1.90.0",
        },
    )
    execute = Mock(return_value=subprocess.CompletedProcess([], 0, json.dumps(clean_report(caller)), ""))
    monkeypatch.setattr(gate.subprocess, "run", execute)
    assert gate.run_checks(caller, ["rust-clippy"], "", caller, outputs["rust-toolchain"]) == 0
    assert execute.call_args.kwargs["env"]["RUSTUP_TOOLCHAIN"] == "1.90.0"
    assert (
        step("Run required quality checks")["env"]["GATE_RUST_TOOLCHAIN"] == "${{ steps.plan.outputs.rust-toolchain }}"
    )
    assert (
        step("Install selected cargo-audit version")["env"]["RUSTUP_TOOLCHAIN"]
        == "${{ steps.plan.outputs.rust-toolchain }}"
    )


@pytest.mark.parametrize("version", ["", "stable", "nightly", "1.90"])
def test_rust_dispatch_cannot_fall_back_to_callers_toolchain(caller, monkeypatch, version):
    execute = Mock()
    monkeypatch.setattr(gate.subprocess, "run", execute)
    with pytest.raises(ValueError, match="validated exact"):
        gate.run_checks(caller, ["rust-clippy"], "", caller, version)
    execute.assert_not_called()
