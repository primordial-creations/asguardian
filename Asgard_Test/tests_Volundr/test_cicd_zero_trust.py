"""
Zero-trust CI/CD generation tests (Volundr plan 04).

Structural invariants (DEEPTHINK_04):
- every emitted GitHub job has an explicit permissions block and timeout
- zero ``${{`` inside any rendered ``run:`` string (injection immunity)
- every well-known ``uses:`` is SHA-pinned with a version comment
- OIDC over static secrets; build/deploy trust split; SLSA provenance
- reified suppressions with comment receipts and warning annihilation
"""

import os
import re
import shutil
import subprocess

import pytest
import yaml

from Asgard.Volundr.CICD import (
    CICDPlatform,
    OIDCConfig,
    OIDCProvider,
    PipelineConfig,
    PipelineGenerator,
    PipelineStage,
    StepConfig,
    TriggerConfig,
    TriggerType,
)
from Asgard.Volundr.CICD.services.action_pins import (
    KNOWN_ACTION_PINS,
    is_sha_pinned,
    resolve_action_ref,
)
from Asgard.Volundr.CICD.services.context_hardening import (
    find_untrusted_interpolations,
    harden_step,
)
from Asgard.Volundr.CICD.services.pipeline_generator_helpers import (
    JENKINS_PROVENANCE_ERROR,
    generate_jenkins,
)
from Asgard.Volundr.Validation.models.suppression_models import Suppression
from Asgard.Volundr.Validation.services.validation_engine import ValidationEngine

GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")
SHA_RE = re.compile(r"@[0-9a-f]{40}$")


def _iter_jobs(content: str):
    for job_name, job in (yaml.safe_load(content).get("jobs") or {}).items():
        yield job_name, job


def _iter_steps(content: str):
    for _job_name, job in _iter_jobs(content):
        for step in job.get("steps") or []:
            yield step


@pytest.fixture
def generator():
    return PipelineGenerator()


@pytest.fixture
def full_config():
    """Representative config touching every zero-trust surface."""
    return PipelineConfig(
        name="CI",
        platform=CICDPlatform.GITHUB_ACTIONS,
        triggers=[
            TriggerConfig(type=TriggerType.PUSH, branches=["main"]),
            TriggerConfig(type=TriggerType.PULL_REQUEST, branches=["main"]),
        ],
        stages=[
            PipelineStage(
                name="Build",
                steps=[
                    StepConfig(name="Checkout", uses="actions/checkout@v4"),
                    StepConfig(
                        name="Setup Python",
                        uses="actions/setup-python@v5",
                        with_params={"python-version": "3.12"},
                    ),
                    StepConfig(name="Test", run="pytest"),
                    StepConfig(name="Upload", uses="actions/upload-artifact@v4"),
                ],
            ),
            PipelineStage(
                name="Deploy",
                needs=["Build"],
                environment="production",
                steps=[StepConfig(name="Deploy", run="make deploy")],
            ),
        ],
        oidc=OIDCConfig(
            provider=OIDCProvider.AWS,
            role="arn:aws:iam::123456789012:role/deploy",
            region="eu-west-1",
        ),
        provenance=True,
        sbom=True,
        harden_runner=True,
    )


class TestStructuralInvariants:
    """Every emitted GitHub workflow satisfies the zero-trust invariants."""

    def test_workflow_level_permissions_empty(self, generator, full_config):
        result = generator.generate(full_config)
        for content in result.files.values():
            assert yaml.safe_load(content)["permissions"] == {}

    def test_every_job_has_permissions_and_timeout(self, generator, full_config):
        result = generator.generate(full_config)
        for content in result.files.values():
            for job_name, job in _iter_jobs(content):
                assert "permissions" in job, f"job {job_name} lacks permissions"
                assert "timeout-minutes" in job, f"job {job_name} lacks timeout"

    def test_zero_interpolation_in_run(self, generator, full_config):
        """Structural injection-immunity invariant: no ${{ in any run:."""
        result = generator.generate(full_config)
        for content in result.files.values():
            for step in _iter_steps(content):
                if "run" in step:
                    assert "${{" not in step["run"]

    def test_all_uses_sha_pinned(self, generator, full_config):
        result = generator.generate(full_config)
        for content in result.files.values():
            for step in _iter_steps(content):
                if "uses" in step:
                    assert SHA_RE.search(step["uses"]), step["uses"]

    def test_pinned_uses_carry_version_comment(self, generator, full_config):
        result = generator.generate(full_config)
        content = result.pipeline_content
        for line in content.splitlines():
            if "uses: actions/checkout@" in line:
                assert "# v4.2.2" in line

    def test_default_concurrency_cancels_pr_builds(self, generator, full_config):
        result = generator.generate(full_config)
        concurrency = yaml.safe_load(result.pipeline_content)["concurrency"]
        assert concurrency["cancel-in-progress"] is True

    def test_rendered_workflow_scores_clean(self, generator, full_config):
        result = generator.generate(full_config)
        assert result.best_practice_score == 100.0


class TestActionPins:
    def test_known_tag_resolves_to_sha(self):
        ref, version = resolve_action_ref("actions/checkout@v4")
        assert SHA_RE.search(ref)
        assert version == "v4.2.2"

    def test_already_pinned_passes_through(self):
        sha_ref = "some/action@" + "a" * 40
        assert resolve_action_ref(sha_ref) == (sha_ref, None)

    def test_unknown_mutable_tag_passes_through(self):
        assert resolve_action_ref("wild/unknown@v1") == ("wild/unknown@v1", None)

    def test_local_action_passes_through(self):
        assert resolve_action_ref("./local/action") == ("./local/action", None)

    def test_all_pins_are_full_shas(self):
        for tag, (sha, version) in KNOWN_ACTION_PINS.items():
            assert re.fullmatch(r"[0-9a-f]{40}", sha), tag
            assert version.startswith("v"), tag

    def test_is_sha_pinned(self):
        assert is_sha_pinned("a/b@" + "0" * 40)
        assert not is_sha_pinned("a/b@v4")
        assert not is_sha_pinned("a/b")


class TestInjectionImmunity:
    def test_adversarial_issue_title_is_rewritten(self, generator):
        """User-supplied injection primitive is rewritten, not emitted verbatim."""
        config = PipelineConfig(
            name="Adversarial",
            platform=CICDPlatform.GITHUB_ACTIONS,
            triggers=[TriggerConfig(type=TriggerType.PULL_REQUEST, branches=["main"])],
            stages=[PipelineStage(name="Build", steps=[
                StepConfig(name="Echo", run="echo ${{ github.event.issue.title }}"),
            ])],
        )
        result = generator.generate(config)
        for step in _iter_steps(result.pipeline_content):
            if "run" in step:
                assert "${{" not in step["run"]
                assert '"$GITHUB_EVENT_ISSUE_TITLE"' in step["run"]
                assert step["env"]["GITHUB_EVENT_ISSUE_TITLE"] == (
                    "${{ github.event.issue.title }}"
                )

    def test_multiple_expressions_get_distinct_vars(self):
        step = StepConfig(
            name="s",
            run="echo ${{ github.head_ref }} ${{ github.event.pull_request.title }}",
        )
        hardened = harden_step(step)
        assert "${{" not in hardened.run
        assert len(hardened.env) == 2

    def test_existing_env_var_is_reused(self):
        step = StepConfig(
            name="s",
            run="echo ${{ github.head_ref }}",
            env={"BRANCH": "${{ github.head_ref }}"},
        )
        hardened = harden_step(step)
        assert hardened.run == 'echo "$BRANCH"'
        assert hardened.env == {"BRANCH": "${{ github.head_ref }}"}

    def test_untrusted_context_detection(self):
        found = find_untrusted_interpolations(
            "echo ${{ github.event.issue.title }} ${{ github.sha }}"
        )
        assert found == [
            ("github.event.issue.title", True),
            ("github.sha", False),
        ]

    def test_engine_flags_verbatim_injection_as_critical(self):
        """The validation engine catches injection in third-party workflows."""
        hostile = (
            "jobs:\n  build:\n    runs-on: ubuntu-latest\n"
            "    permissions: {contents: read}\n    timeout-minutes: 10\n"
            "    steps:\n"
            "    - name: bad\n"
            "      run: echo ${{ github.event.pull_request.title }}\n"
        )
        report = ValidationEngine().validate_pipeline(hostile)
        assert any(r.rule_id == "VOL-CICD-0004" for r in report.results)


class TestOIDCAndStaticSecrets:
    def test_oidc_step_and_id_token_permission(self, generator, full_config):
        result = generator.generate(full_config)
        deploy = [c for p, c in result.files.items() if p.endswith("-deploy.yml")][0]
        job = yaml.safe_load(deploy)["jobs"]["deploy"]
        assert job["permissions"]["id-token"] == "write"
        assert any(
            "configure-aws-credentials" in (s.get("uses") or "")
            for s in job["steps"]
        )

    @pytest.mark.parametrize("provider,marker", [
        (OIDCProvider.GCP, "google-github-actions/auth"),
        (OIDCProvider.AZURE, "azure/login"),
        (OIDCProvider.VAULT, "hashicorp/vault-action"),
    ])
    def test_other_oidc_providers(self, generator, provider, marker):
        config = PipelineConfig(
            name="CI", platform=CICDPlatform.GITHUB_ACTIONS,
            triggers=[TriggerConfig(type=TriggerType.PUSH, branches=["main"])],
            stages=[PipelineStage(name="Deploy", environment="prod",
                                  steps=[StepConfig(name="d", run="make deploy")])],
            oidc=OIDCConfig(provider=provider, role="some-role"),
            split_trust=False,
        )
        result = generator.generate(config)
        assert marker in result.pipeline_content

    def test_static_cloud_secret_yields_finding(self, generator):
        config = PipelineConfig(
            name="CI", platform=CICDPlatform.GITHUB_ACTIONS,
            triggers=[TriggerConfig(type=TriggerType.PUSH, branches=["main"])],
            stages=[PipelineStage(name="Build",
                                  steps=[StepConfig(name="b", run="make")])],
            secrets=["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
        )
        result = generator.generate(config)
        assert any("VOL-CICD-0005" in issue for issue in result.validation_results)

    def test_engine_flags_static_secret_env(self):
        content = (
            "jobs:\n  deploy:\n    runs-on: ubuntu-latest\n"
            "    permissions: {contents: read}\n    timeout-minutes: 10\n"
            "    steps:\n"
            "    - name: d\n      run: aws s3 sync . s3://bucket\n"
            "      env:\n"
            "        AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}\n"
        )
        report = ValidationEngine().validate_pipeline(content)
        assert any(r.rule_id == "VOL-CICD-0005" for r in report.results)


class TestSplitTrust:
    def test_build_workflow_has_no_secrets_or_oidc(self, generator, full_config):
        result = generator.generate(full_config)
        build = result.pipeline_content
        assert "secrets." not in build
        assert "configure-aws-credentials" not in build
        assert "id-token" not in yaml.safe_load(build)["jobs"]["build"]["permissions"]

    def test_deploy_workflow_triggers_on_workflow_run_only(self, generator, full_config):
        result = generator.generate(full_config)
        deploy = [c for p, c in result.files.items() if p.endswith("-deploy.yml")][0]
        on = yaml.safe_load(deploy)["on"]
        assert list(on.keys()) == ["workflow_run"]
        assert on["workflow_run"]["workflows"] == ["CI"]

    def test_no_split_when_disabled(self, generator, full_config):
        full_config.split_trust = False
        result = generator.generate(full_config)
        assert len(result.files) == 1
        assert "deploy:" in result.pipeline_content

    def test_no_split_without_deploy_stage(self, generator):
        config = PipelineConfig(
            name="CI", platform=CICDPlatform.GITHUB_ACTIONS,
            triggers=[TriggerConfig(type=TriggerType.PUSH, branches=["main"])],
            stages=[PipelineStage(name="Build",
                                  steps=[StepConfig(name="b", run="make")])],
        )
        result = generator.generate(config)
        assert len(result.files) == 1

    def test_save_to_file_writes_all_files(self, generator, full_config, tmp_path):
        result = generator.generate(full_config)
        generator.save_to_file(result, str(tmp_path))
        for rel_path in result.files:
            assert (tmp_path / rel_path).exists()


class TestProvenanceAndSBOM:
    def test_provenance_job_permissions(self, generator, full_config):
        result = generator.generate(full_config)
        job = yaml.safe_load(result.pipeline_content)["jobs"]["provenance"]
        assert job["permissions"] == {
            "id-token": "write", "attestations": "write", "contents": "read",
        }
        assert any(
            "attest-build-provenance" in (s.get("uses") or "") for s in job["steps"]
        )

    def test_sbom_step_in_build_job(self, generator, full_config):
        result = generator.generate(full_config)
        build = yaml.safe_load(result.pipeline_content)["jobs"]["build"]
        assert any("sbom-action" in (s.get("uses") or "") for s in build["steps"])

    def test_jenkins_provenance_refused_with_actionable_message(self):
        config = PipelineConfig(
            name="CI", platform=CICDPlatform.JENKINS,
            stages=[PipelineStage(name="Build",
                                  steps=[StepConfig(name="b", run="make")])],
            provenance=True,
        )
        with pytest.raises(ValueError, match="Tekton Chains"):
            generate_jenkins(config)
        with pytest.raises(ValueError, match="Tekton Chains"):
            PipelineGenerator().generate(config)
        assert "Tekton Chains" in JENKINS_PROVENANCE_ERROR

    def test_gitlab_provenance_variable(self, generator):
        config = PipelineConfig(
            name="CI", platform=CICDPlatform.GITLAB_CI,
            stages=[PipelineStage(name="Build",
                                  steps=[StepConfig(name="b", run="make")])],
            provenance=True,
        )
        result = generator.generate(config)
        assert "RUNNER_GENERATE_ARTIFACTS_METADATA" in result.pipeline_content


class TestOtherPlatformHardening:
    def test_gitlab_jobs_have_timeout(self, generator):
        config = PipelineConfig(
            name="CI", platform=CICDPlatform.GITLAB_CI,
            stages=[PipelineStage(name="Build",
                                  steps=[StepConfig(name="b", run="make")])],
        )
        result = generator.generate(config)
        parsed = yaml.safe_load(result.pipeline_content)
        assert parsed["build"]["timeout"] == "30 minutes"
        assert "Zero-trust notes" in result.pipeline_content

    def test_azure_jobs_have_timeout(self, generator):
        config = PipelineConfig(
            name="CI", platform=CICDPlatform.AZURE_DEVOPS,
            triggers=[TriggerConfig(type=TriggerType.PUSH, branches=["main"])],
            stages=[PipelineStage(name="Build",
                                  steps=[StepConfig(name="b", run="make")])],
        )
        result = generator.generate(config)
        parsed = yaml.safe_load(result.pipeline_content)
        job = parsed["stages"][0]["jobs"][0]
        assert job["timeoutInMinutes"] == 30

    def test_jenkins_has_stage_timeouts(self, generator):
        config = PipelineConfig(
            name="CI", platform=CICDPlatform.JENKINS,
            stages=[PipelineStage(name="Build", timeout_minutes=17,
                                  steps=[StepConfig(name="b", run="make")])],
        )
        result = generator.generate(config)
        assert "timeout(time: 17, unit: 'MINUTES')" in result.pipeline_content

    def test_circleci_emitter_exists_and_is_valid_yaml(self, generator):
        config = PipelineConfig(
            name="CI", platform=CICDPlatform.CIRCLECI,
            stages=[
                PipelineStage(name="Build",
                              steps=[StepConfig(name="b", run="make")]),
                PipelineStage(name="Deploy", needs=["Build"], environment="prod",
                              steps=[StepConfig(name="d", run="make deploy")]),
            ],
        )
        result = generator.generate(config)
        parsed = yaml.safe_load(result.pipeline_content)
        assert parsed["version"] == 2.1
        assert "build" in parsed["jobs"]
        assert result.file_path == ".circleci/config.yml"
        # Deploy job restricted to protected branch + context.
        wf_jobs = parsed["workflows"]["ci"]["jobs"]
        deploy_entry = [j for j in wf_jobs if isinstance(j, dict) and "deploy" in j][0]
        assert deploy_entry["deploy"]["filters"]["branches"]["only"] == ["main"]


class TestSuppressions:
    def _config_with_unknown_action(self, suppressions):
        return PipelineConfig(
            name="CI", platform=CICDPlatform.GITHUB_ACTIONS,
            triggers=[TriggerConfig(type=TriggerType.PUSH, branches=["main"])],
            stages=[PipelineStage(name="Build", steps=[
                StepConfig(name="Checkout", uses="actions/checkout@v4"),
                StepConfig(name="Custom", uses="acme/internal-action@v1"),
            ])],
            suppressions=suppressions,
        )

    def test_unknown_mutable_action_yields_pin_finding(self, generator):
        result = generator.generate(self._config_with_unknown_action([]))
        assert any("VOL-CICD-0002" in issue for issue in result.validation_results)
        assert result.best_practice_score < 100.0

    def test_suppression_annihilates_finding_and_leaves_receipt(self, generator):
        suppression = Suppression(
            rule="VOL-CICD-0002", target="build",
            reason="internal action, repo is access-controlled (TICKET-42)",
        )
        result = generator.generate(self._config_with_unknown_action([suppression]))
        assert not any(
            "VOL-CICD-0002" in issue for issue in result.validation_results
        )
        assert result.best_practice_score == 100.0
        assert (
            "# volundr:suppress=VOL-CICD-0002 internal action, repo is "
            "access-controlled (TICKET-42)"
        ) in result.pipeline_content

    def test_stale_suppression_yields_hygiene_warning(self, generator):
        suppression = Suppression(
            rule="VOL-CICD-0002", target="nonexistent-job", reason="stale",
        )
        result = generator.generate(self._config_with_unknown_action([suppression]))
        assert any("VOL-SUPPRESS-STALE" in issue for issue in result.validation_results)


class TestGoldenFiles:
    """Snapshot of the full rendered output; diffs reviewed like code.

    Regenerate deliberately with:
    UPDATE_GOLDEN=1 python3 -m pytest Asgard_Test/tests_Volundr/test_cicd_zero_trust.py -k golden
    """

    def test_github_zero_trust_golden(self, generator, full_config):
        result = generator.generate(full_config)
        for rel_path, content in result.files.items():
            golden_path = os.path.join(GOLDEN_DIR, os.path.basename(rel_path))
            if os.environ.get("UPDATE_GOLDEN"):
                os.makedirs(GOLDEN_DIR, exist_ok=True)
                with open(golden_path, "w", encoding="utf-8") as f:
                    f.write(content)
            assert os.path.exists(golden_path), (
                f"golden file missing: {golden_path} (run with UPDATE_GOLDEN=1)"
            )
            with open(golden_path, encoding="utf-8") as f:
                assert content == f.read(), f"golden drift in {rel_path}"


class TestExternalLint:
    """actionlint contract check on rendered output (skip-if-unavailable)."""

    def test_actionlint_clean_on_generated_workflows(self, generator, full_config, tmp_path):
        if shutil.which("actionlint") is None:
            pytest.skip("actionlint not installed")
        result = generator.generate(full_config)
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        for rel_path, content in result.files.items():
            (workflows / os.path.basename(rel_path)).write_text(content)
        proc = subprocess.run(
            ["actionlint"], cwd=tmp_path, capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
