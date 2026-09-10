"""Offline contracts for the disabled L8 performance workflow."""

import shlex
from pathlib import Path

import tomllib

import yaml


ROOT = Path(__file__).resolve().parents[1]
L8_WORKFLOW = ROOT / ".github/workflows/l8-perf-budgets.yml"
CI_WORKFLOW = ROOT / ".github/workflows/ci.yml"
L8_SUITES = tuple(
    sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "Asgard_Test").glob("tests_*/L8_Performance")
        if path.is_dir()
    )
)


def _workflow(path: Path) -> dict:
    """Load workflow YAML while tolerating PyYAML's YAML 1.1 `on` coercion."""
    with path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def test_l8_job_remains_explicitly_disabled() -> None:
    workflow = _workflow(L8_WORKFLOW)

    assert workflow["jobs"]["l8-budgets"]["if"] is False


def test_l8_workflow_collects_every_current_performance_suite() -> None:
    command = next(
        step["run"]
        for step in _workflow(L8_WORKFLOW)["jobs"]["l8-budgets"]["steps"]
        if step.get("name") == "Gated pytest-benchmark suites"
    )

    selected = {
        token
        for token in shlex.split(command)
        if token.startswith("Asgard_Test/tests_")
        and token.endswith("/L8_Performance")
    }

    assert L8_SUITES
    assert selected == set(L8_SUITES)


def test_l8_dependency_extra_matches_package_free_pr_install() -> None:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    expected = set(project["dependencies"])
    project_name = project["name"]
    for requirement in project["optional-dependencies"]["l8"]:
        self_extra_prefix = f"{project_name}["
        if requirement.startswith(self_extra_prefix) and requirement.endswith("]"):
            extras = requirement[len(self_extra_prefix) : -1].split(",")
            for extra in extras:
                expected.update(project["optional-dependencies"][extra])
        else:
            expected.add(requirement)
    workflow = _workflow(L8_WORKFLOW)
    steps = workflow["jobs"]["l8-budgets"]["steps"]
    pr_install = next(
        step["run"]
        for step in steps
        if step.get("name") == "Install test deps without editable package (pull_request)"
    )

    assert 'pip install -e ".[l8]"' in next(
        step["run"] for step in steps if step.get("name", "").startswith("Install package")
    )
    install_command = pr_install[pr_install.index('pip install "') :]
    actual = {token for token in shlex.split(install_command)[2:] if token.strip()}
    assert actual == expected


def test_l8_changes_trigger_the_draft_workflow() -> None:
    text = L8_WORKFLOW.read_text(encoding="utf-8")

    for path in (
        ".github/workflows/l8-perf-budgets.yml",
        "pyproject.toml",
        "_Docs/Testing/L8_Perf_Budget_Policy.md",
    ):
        assert f'      - "{path}"' in text


def test_normal_ci_excludes_every_l8_suite_from_test_and_coverage() -> None:
    workflow = _workflow(CI_WORKFLOW)
    steps = workflow["jobs"]["test"]["steps"]
    commands = [
        step["run"]
        for step in steps
        if step.get("name") in {"Run tests", "Run tests with coverage"}
    ]

    assert len(commands) == 2
    for command in commands:
        assert "--ignore=Asgard_Test/L8_PerfBudgets" in command
        assert "--ignore-glob='Asgard_Test/**/L8_Performance'" in command
