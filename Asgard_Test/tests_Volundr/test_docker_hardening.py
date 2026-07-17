"""
Volundr Docker hardening tests (plan 03).

Covers BuildKit syntax directive, digest pinning + Renovate pairing,
secret mounts + plaintext-secret refusal, SHELL pipefail, non-root
scaffold, package hygiene, COPY ordering + .dockerignore, Compose dedup
shim, healthcheck-gated depends_on, loopback/edge port policy, and
skip-if-unavailable external-tool gates (hadolint / docker compose).
"""

import shutil
import subprocess

import pytest
import yaml

from Asgard.Volundr.Docker import (
    BuildStage,
    ComposeConfig,
    ComposeServiceConfig,
    DockerfileConfig,
    DockerfileGenerator,
)
from Asgard.Volundr.Docker.models.docker_models import NonRootUser, SecretMount
from Asgard.Volundr.Compose import (
    ComposeProject,
    ComposeProjectGenerator,
    ComposeService,
)
from Asgard.Volundr.Validation import Suppression


def generate(config):
    return DockerfileGenerator().generate(config)


def simple_config(**kwargs):
    stages = kwargs.pop("stages", [BuildStage(name="app", base_image="python:3.12-slim")])
    return DockerfileConfig(name="app", stages=stages, **kwargs)


class TestSyntaxAndDigest:
    def test_first_line_is_syntax_directive(self):
        result = generate(simple_config())
        assert result.dockerfile_content.splitlines()[0] == (
            "# syntax=docker/dockerfile:1.7"
        )

    def test_digest_pinning_renders_at_digest(self):
        digest = "sha256:" + "a" * 64
        config = simple_config(stages=[BuildStage(
            name="app", base_image="python:3.12-slim", base_image_digest=digest,
        )])
        result = generate(config)
        assert f"FROM python:3.12-slim@{digest} AS app" in result.dockerfile_content

    def test_tag_only_from_emits_digest_finding(self):
        result = generate(simple_config())
        assert any("VOL-DOCKER-DIGEST" in r for r in result.validation_results)

    def test_renovate_snippet_pairing(self):
        result = generate(simple_config(emit_renovate_config=True))
        assert result.renovate_snippet is not None
        assert "docker:pinDigests" in result.renovate_snippet


class TestSecretHandling:
    def test_secret_mount_rendered(self):
        config = simple_config(stages=[BuildStage(
            name="app", base_image="python:3.12-slim",
            run_commands=["pip install --no-cache-dir ."],
            secret_mounts=[SecretMount(id="pypi", target="/run/secrets/pypi")],
        )])
        result = generate(config)
        assert (
            "RUN --mount=type=secret,id=pypi,target=/run/secrets/pypi"
            in result.dockerfile_content
        )

    def test_ssh_mount_rendered(self):
        config = simple_config(stages=[BuildStage(
            name="app", base_image="python:3.12-slim",
            run_commands=["git clone git@example.com:org/repo.git"],
            ssh_mount=True,
        )])
        result = generate(config)
        assert "--mount=type=ssh" in result.dockerfile_content

    def test_plaintext_secret_env_refused(self):
        """Adversarial (plan 03 §5): secret-looking ENV fails generation."""
        config = simple_config(stages=[BuildStage(
            name="app", base_image="python:3.12-slim",
            env_vars={"AWS_SECRET_ACCESS_KEY": "AKIA123456789"},
        )])
        with pytest.raises(ValueError, match="VOL-DOCKER-SECRET-ENV"):
            generate(config)

    def test_plaintext_secret_arg_refused(self):
        config = simple_config(args={"API_TOKEN": "abcdef"})
        with pytest.raises(ValueError):
            generate(config)

    def test_suppression_allows_secret_env_with_receipt(self):
        config = simple_config(
            stages=[BuildStage(
                name="app", base_image="python:3.12-slim",
                env_vars={"DUMMY_TOKEN": "not-a-real-secret"},
            )],
            suppressions=[Suppression(
                rule="VOL-DOCKER-SECRET-ENV", target="DUMMY_TOKEN",
                reason="JIRA-42: placeholder token for tests only",
            )],
        )
        result = generate(config)
        assert "VOL-DOCKER-SECRET-ENV" in result.applied_suppressions
        assert "# volundr:suppress=VOL-DOCKER-SECRET-ENV" in result.dockerfile_content


class TestShellAndUser:
    def test_pipefail_before_piped_run(self):
        config = simple_config(stages=[BuildStage(
            name="app", base_image="python:3.12-slim",
            run_commands=["curl -fsSL https://example.com/x.sh | sh"],
        )])
        result = generate(config)
        content = result.dockerfile_content
        assert 'SHELL ["/bin/bash", "-o", "pipefail", "-c"]' in content
        assert content.index("SHELL") < content.index("curl -fsSL")

    def test_alpine_uses_ash_for_pipefail(self):
        config = simple_config(stages=[BuildStage(
            name="app", base_image="python:3.12-alpine",
            run_commands=["wget -qO- https://example.com | tar xz"],
        )])
        result = generate(config)
        assert 'SHELL ["/bin/ash", "-o", "pipefail", "-c"]' in result.dockerfile_content

    def test_no_shell_without_pipes(self):
        result = generate(simple_config(stages=[BuildStage(
            name="app", base_image="python:3.12-slim",
            run_commands=["pip install --no-cache-dir ."],
        )]))
        assert "SHELL [" not in result.dockerfile_content

    def test_useradd_l_scaffold_debian(self):
        result = generate(simple_config())
        assert "RUN useradd -l -u 65532 -m appuser" in result.dockerfile_content
        assert "USER appuser" in result.dockerfile_content

    def test_adduser_scaffold_alpine(self):
        config = simple_config(stages=[BuildStage(name="app", base_image="alpine:3.19")])
        result = generate(config)
        assert "RUN adduser -D -u 65532 appuser" in result.dockerfile_content

    def test_distroless_numeric_user_no_run(self):
        config = simple_config(stages=[BuildStage(
            name="app", base_image="gcr.io/distroless/python3",
        )])
        result = generate(config)
        assert "USER 65532:65532" in result.dockerfile_content
        assert "useradd" not in result.dockerfile_content

    def test_custom_non_root_user(self):
        config = simple_config(non_root=NonRootUser(name="svc", uid=70000))
        result = generate(config)
        assert "RUN useradd -l -u 70000 -m svc" in result.dockerfile_content
        assert "USER svc" in result.dockerfile_content


class TestPackageHygieneAndCopyOrdering:
    def test_apt_gets_recommends_flag_and_list_cleanup(self):
        config = simple_config(stages=[BuildStage(
            name="app", base_image="python:3.12-slim",
            run_commands=["apt-get update", "apt-get install -y curl"],
        )])
        result = generate(config)
        assert "--no-install-recommends" in result.dockerfile_content
        assert "rm -rf /var/lib/apt/lists/*" in result.dockerfile_content

    def test_apk_gets_no_cache(self):
        config = simple_config(stages=[BuildStage(
            name="app", base_image="alpine:3.19",
            run_commands=["apk add curl"],
        )])
        result = generate(config)
        assert "apk add --no-cache curl" in result.dockerfile_content

    def test_unpinned_packages_reported(self):
        config = simple_config(stages=[BuildStage(
            name="app", base_image="python:3.12-slim",
            run_commands=["apt-get install -y curl"],
        )])
        result = generate(config)
        assert any("DL3008" in r for r in result.validation_results)

    def test_dependency_manifests_copied_before_source(self):
        config = simple_config(stages=[BuildStage(
            name="app", base_image="python:3.12-slim",
            copy_commands=[
                {"src": ".", "dst": "."},
                {"src": "requirements.txt", "dst": "."},
            ],
        )])
        result = generate(config)
        content = result.dockerfile_content
        assert content.index("COPY requirements.txt") < content.index("COPY . .")

    def test_whole_context_copy_generates_dockerignore(self):
        config = simple_config(stages=[BuildStage(
            name="app", base_image="python:3.12-slim",
            copy_commands=[{"src": ".", "dst": "."}],
        )])
        result = generate(config)
        assert result.dockerignore_content is not None
        assert ".git" in result.dockerignore_content

    def test_scan_workflow_pairing(self):
        result = generate(simple_config(emit_scan_workflow=True))
        assert result.scan_workflow_content is not None
        assert "trivy" in result.scan_workflow_content.lower()
        assert "cyclonedx" in result.scan_workflow_content.lower()


class TestComposeDedup:
    def test_shim_import_still_works(self):
        from Asgard.Volundr.Docker import ComposeGenerator  # noqa: F401

    def test_shim_emits_deprecation_warning(self):
        from Asgard.Volundr.Docker import ComposeGenerator
        with pytest.warns(DeprecationWarning):
            ComposeGenerator()

    def test_shim_output_has_no_version_key(self):
        from Asgard.Volundr.Docker import ComposeGenerator
        with pytest.warns(DeprecationWarning):
            generator = ComposeGenerator()
        config = ComposeConfig(
            services=[ComposeServiceConfig(name="api", image="myapp:1.0")],
        )
        result = generator.generate(config)
        parsed = yaml.safe_load(result.compose_content)
        assert "version" not in parsed
        assert "api" in parsed["services"]


class TestComposeEngine:
    def project(self, **kwargs):
        services = kwargs.pop("services", None) or [
            ComposeService(name="api", image="myapp:1.0", depends_on=["db"],
                           ports=["8000:8000"]),
            ComposeService(name="db", image="postgres:16",
                           ports=["5432:5432"]),
        ]
        return ComposeProject(name="stack", services=services, **kwargs)

    def test_no_version_key_in_main_or_override(self):
        generator = ComposeProjectGenerator()
        result = generator.generate_with_override(self.project(), "production")
        assert "version" not in yaml.safe_load(result.compose_content)
        assert "version" not in yaml.safe_load(result.override_content)

    def test_known_image_gets_auto_healthcheck(self):
        result = ComposeProjectGenerator().generate(self.project())
        parsed = yaml.safe_load(result.compose_content)
        assert "pg_isready" in str(parsed["services"]["db"]["healthcheck"]["test"])

    def test_depends_on_gated_on_service_healthy(self):
        result = ComposeProjectGenerator().generate(self.project())
        parsed = yaml.safe_load(result.compose_content)
        assert parsed["services"]["api"]["depends_on"] == {
            "db": {"condition": "service_healthy"}
        }

    def test_depends_on_without_healthcheck_falls_back_to_started(self):
        project = self.project(services=[
            ComposeService(name="api", image="myapp:1.0", depends_on=["worker"]),
            ComposeService(name="worker", image="mycorp/worker:1.0"),
        ])
        result = ComposeProjectGenerator().generate(project)
        parsed = yaml.safe_load(result.compose_content)
        assert parsed["services"]["api"]["depends_on"] == {
            "worker": {"condition": "service_started"}
        }
        assert any("VOL-COMPOSE-0008" in r for r in result.validation_results)

    def test_edge_policy_rewrites_non_edge_ports_to_loopback(self):
        result = ComposeProjectGenerator().generate(
            self.project(edge_services=["api"])
        )
        parsed = yaml.safe_load(result.compose_content)
        assert parsed["services"]["api"]["ports"] == ["8000:8000"]
        assert parsed["services"]["db"]["ports"] == ["127.0.0.1:5432:5432"]

    def test_exposed_datastore_flagged_high(self):
        result = ComposeProjectGenerator().generate(self.project())
        assert any("VOL-COMPOSE-EXPOSED" in r for r in result.validation_results)
        # An un-suppressed HIGH security finding caps the composite at 70.
        assert result.best_practice_score <= 70

    def test_loopback_bound_datastore_not_flagged(self):
        result = ComposeProjectGenerator().generate(
            self.project(edge_services=["api"])
        )
        assert not any(
            "VOL-COMPOSE-EXPOSED" in r for r in result.validation_results
        )

    def test_bind_mount_flagged(self):
        project = self.project(services=[
            ComposeService(name="api", image="myapp:1.0",
                           volumes=["./data:/app/data"]),
        ])
        result = ComposeProjectGenerator().generate(project)
        assert any("VOL-COMPOSE-0006" in r for r in result.validation_results)

    def test_restart_defaults_to_unless_stopped(self):
        result = ComposeProjectGenerator().generate(self.project())
        parsed = yaml.safe_load(result.compose_content)
        assert parsed["services"]["api"]["restart"] == "unless-stopped"


@pytest.mark.skipif(
    shutil.which("hadolint") is None, reason="hadolint not installed"
)
class TestHadolintContract:
    def test_generated_dockerfile_passes_hadolint_errors(self):
        """L3_Contract gate: no hadolint error-level findings."""
        result = generate(simple_config(stages=[BuildStage(
            name="app", base_image="python:3.12-slim",
            run_commands=["pip install --no-cache-dir ."],
        )]))
        proc = subprocess.run(
            ["hadolint", "--failure-threshold", "error", "-"],
            input=result.dockerfile_content, capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr


@pytest.mark.skipif(
    shutil.which("docker") is None, reason="docker not installed"
)
class TestComposeConfigContractGate:
    def test_docker_compose_config_accepts_output(self, tmp_path):
        """L3_Contract gate: `docker compose config --quiet` accepts output."""
        project = ComposeProject(name="gate", services=[
            ComposeService(name="db", image="postgres:16"),
        ])
        result = ComposeProjectGenerator().generate(project)
        compose_file = tmp_path / "docker-compose.yaml"
        compose_file.write_text(result.compose_content)
        proc = subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "config", "--quiet"],
            capture_output=True, text=True,
        )
        if "is not a docker command" in proc.stderr:
            pytest.skip("docker compose plugin unavailable")
        assert proc.returncode == 0, proc.stderr
