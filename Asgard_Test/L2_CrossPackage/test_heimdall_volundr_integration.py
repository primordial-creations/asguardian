"""
Heimdall-Volundr Integration Tests

Tests for cross-package integration between Heimdall (code analysis) and
Volundr (infrastructure generation). These tests validate workflows where
code analysis results influence infrastructure configuration generation.
"""

from pathlib import Path

import pytest

from Asgard.Bragi.Quality import FileAnalyzer, AnalysisConfig
from Asgard.Heimdall.Security import StaticSecurityService, SecurityScanConfig
from Asgard.Bragi.Dependencies import DependencyAnalyzer, DependencyConfig
from Asgard.Volundr.Kubernetes import ManifestConfig, ManifestGenerator, WorkloadType, SecurityProfile
from Asgard.Volundr.Docker import DockerfileConfig, DockerfileGenerator
from Asgard.Volundr.Docker.models.docker_models import BuildStage


@pytest.mark.cross_package
@pytest.mark.heimdall_volundr
class TestQualityReportToDeployment:
    """
    Test workflow: Analyze code quality with Heimdall, then generate Kubernetes
    deployment with Volundr where resource limits reflect code complexity.
    """

    def test_complexity_influences_resource_allocation(
        self, sample_python_project: Path, output_dir: Path
    ):
        """
        Test that code complexity analysis influences K8s resource allocation.

        Workflow:
        1. Analyze code quality/complexity with Heimdall
        2. Calculate appropriate resource limits based on complexity
        3. Generate K8s deployment with Volundr using calculated resources
        4. Verify deployment has appropriate resource configuration
        """
        # Step 1: Analyze code with Heimdall
        config = AnalysisConfig(
            scan_path=str(sample_python_project),
            threshold=100
        )
        analyzer = FileAnalyzer(config)
        result = analyzer.analyze()

        # Verify analysis completed
        assert result.total_files_scanned > 0
        assert result.scan_path == str(sample_python_project)

        # Step 2: Calculate resource needs based on complexity
        # Higher complexity = more CPU/memory needed
        complexity_score = 100 - result.compliance_rate

        # Base resources
        base_cpu = "100m"
        base_memory = "128Mi"

        # Scale resources based on complexity
        if complexity_score > 50:
            cpu_request = "500m"
            cpu_limit = "1000m"
            memory_request = "512Mi"
            memory_limit = "1Gi"
        elif complexity_score > 20:
            cpu_request = "250m"
            cpu_limit = "500m"
            memory_request = "256Mi"
            memory_limit = "512Mi"
        else:
            cpu_request = base_cpu
            cpu_limit = "200m"
            memory_request = base_memory
            memory_limit = "256Mi"

        # Step 3: Generate K8s manifest with Volundr
        from Asgard.Volundr.Kubernetes.models.kubernetes_models import ResourceRequirements

        k8s_config = ManifestConfig(
            name="analyzed-app",
            image="myapp:latest",
            replicas=1,
            resources=ResourceRequirements(
                cpu_request=cpu_request,
                cpu_limit=cpu_limit,
                memory_request=memory_request,
                memory_limit=memory_limit
            )
        )

        generator = ManifestGenerator(output_dir=str(output_dir))
        manifest = generator.generate(k8s_config)

        # Step 4: Verify manifest reflects complexity
        assert manifest is not None
        assert manifest.yaml_content is not None

        # Verify resources are in the manifest
        yaml_content = manifest.yaml_content
        assert cpu_request in yaml_content
        assert memory_request in yaml_content

        # Verify manifest can be saved
        manifest_file = output_dir / "deployment.yaml"
        manifest_file.write_text(yaml_content)
        assert manifest_file.exists()
        assert manifest_file.stat().st_size > 0

    def test_file_count_influences_replicas(
        self, sample_python_project: Path, output_dir: Path
    ):
        """
        Test that codebase size influences replica count in deployment.

        Larger codebases might benefit from more replicas for load distribution.
        """
        # Analyze codebase
        config = AnalysisConfig(
            scan_path=str(sample_python_project),
            threshold=100
        )
        analyzer = FileAnalyzer(config)
        result = analyzer.analyze()

        # Calculate replicas based on file count
        file_count = result.total_files_scanned

        if file_count > 50:
            replicas = 5
        elif file_count > 20:
            replicas = 3
        else:
            replicas = 1

        # Generate deployment
        k8s_config = ManifestConfig(
            name="scaled-app",
            image="myapp:latest",
            replicas=replicas
        )

        generator = ManifestGenerator(output_dir=str(output_dir))
        manifest = generator.generate(k8s_config)

        # Verify replicas
        assert manifest is not None
        assert f"replicas: {replicas}" in manifest.yaml_content


@pytest.mark.cross_package
@pytest.mark.heimdall_volundr
class TestSecurityScanToNetworkPolicy:
    """
    Test workflow: Run security scan with Heimdall, then generate Kubernetes
    network policies with Volundr based on discovered vulnerabilities.
    """

    def test_security_scan_to_strict_profile(
        self, sample_python_project: Path, output_dir: Path
    ):
        """
        Test that security vulnerabilities trigger strict security profile.

        Workflow:
        1. Run Heimdall security scan
        2. Determine security profile based on findings
        3. Generate K8s manifest with appropriate security settings
        4. Verify security context is applied
        """
        # Step 1: Security scan with Heimdall
        security_config = SecurityScanConfig(
            scan_path=str(sample_python_project)
        )
        security_service = StaticSecurityService()
        security_report = security_service.scan(str(sample_python_project))

        # Verify scan completed
        assert security_report is not None
        assert security_report.security_score is not None

        # Step 2: Determine security profile based on score
        if security_report.security_score < 60:
            security_profile = SecurityProfile.ZERO_TRUST
        elif security_report.security_score < 80:
            security_profile = SecurityProfile.STRICT
        elif security_report.security_score < 90:
            security_profile = SecurityProfile.ENHANCED
        else:
            security_profile = SecurityProfile.BASIC

        # Step 3: Generate manifest with appropriate security
        k8s_config = ManifestConfig(
            name="secure-app",
            image="myapp:latest",
            security_profile=security_profile
        )

        generator = ManifestGenerator(output_dir=str(output_dir))
        manifest = generator.generate(k8s_config)

        # Step 4: Verify security settings
        assert manifest is not None
        yaml_content = manifest.yaml_content

        # Should have security context
        assert "securityContext" in yaml_content

        # If strict or zero-trust, should have restrictive settings
        if security_profile in [SecurityProfile.STRICT, SecurityProfile.ZERO_TRUST]:
            assert "readOnlyRootFilesystem: true" in yaml_content
            assert "runAsNonRoot: true" in yaml_content

    def test_vulnerability_count_affects_pod_security(
        self, sample_python_project: Path, output_dir: Path
    ):
        """Test that vulnerability count influences pod security policies."""
        # Run security scan
        security_service = StaticSecurityService()
        security_report = security_service.scan(str(sample_python_project))

        # Count vulnerabilities (SecurityReport aggregates per-severity totals).
        vuln_count = security_report.total_issues

        # More vulnerabilities = stricter security
        if vuln_count > 10:
            run_as_non_root = True
            read_only_fs = True
            allow_privilege_escalation = False
        elif vuln_count > 5:
            run_as_non_root = True
            read_only_fs = False
            allow_privilege_escalation = False
        else:
            run_as_non_root = False
            read_only_fs = False
            allow_privilege_escalation = True

        # Generate manifest
        from Asgard.Volundr.Kubernetes.models.kubernetes_models import SecurityContext

        k8s_config = ManifestConfig(
            name="vuln-aware-app",
            image="myapp:latest",
            security_context=SecurityContext(
                run_as_non_root=run_as_non_root,
                read_only_root_filesystem=read_only_fs,
                allow_privilege_escalation=allow_privilege_escalation
            )
        )

        generator = ManifestGenerator(output_dir=str(output_dir))
        manifest = generator.generate(k8s_config)

        # Verify security context
        assert manifest is not None
        yaml_content = manifest.yaml_content

        if run_as_non_root:
            assert "runAsNonRoot: true" in yaml_content


@pytest.mark.cross_package
@pytest.mark.heimdall_volundr
class TestDependencyAnalysisToDocker:
    """
    Test workflow: Analyze dependencies with Heimdall, then generate Dockerfile
    with Volundr that includes correct requirements.
    """

    def test_dependency_detection_to_dockerfile(
        self, sample_python_project: Path, output_dir: Path
    ):
        """
        Test that Heimdall dependency analysis informs Dockerfile generation.

        Workflow:
        1. Analyze project dependencies with Heimdall
        2. Extract Python package requirements
        3. Generate Dockerfile with correct pip install commands
        4. Verify Dockerfile contains dependency installation
        """
        # Step 1: Analyze dependencies with Heimdall
        dep_config = DependencyConfig(
            scan_path=sample_python_project / "src"
        )
        dep_analyzer = DependencyAnalyzer(dep_config)
        dep_report = dep_analyzer.analyze(sample_python_project / "src")

        # Verify dependency analysis
        assert dep_report is not None
        assert dep_report.total_modules > 0

        # Step 2: Read requirements.txt (simulating extraction)
        requirements_file = sample_python_project / "requirements.txt"
        assert requirements_file.exists()

        requirements_content = requirements_file.read_text()
        requirements_list = [
            line.strip() for line in requirements_content.split("\n")
            if line.strip() and not line.startswith("#")
        ]

        # Step 3: Generate Dockerfile with dependencies
        docker_config = DockerfileConfig(
            name="python-app",
            base_image="python:3.11-slim",
            stages=[
                BuildStage(
                    name="builder",
                    base_image="python:3.11-slim",
                    workdir="/app",
                    run_commands=[
                        "apt-get update && apt-get install -y --no-install-recommends gcc",
                        "pip install --no-cache-dir --upgrade pip"
                    ],
                    copy_commands=[
                        {"src": "requirements.txt", "dst": "/app/requirements.txt"}
                    ]
                ),
                BuildStage(
                    name="runtime",
                    base_image="python:3.11-slim",
                    workdir="/app",
                    copy_from="builder",
                    copy_src="/app",
                    copy_dst="/app",
                    run_commands=[
                        f"pip install --no-cache-dir {' '.join(requirements_list)}"
                    ],
                    cmd=["python", "-m", "src.app.service"]
                )
            ]
        )

        generator = DockerfileGenerator(output_dir=str(output_dir))
        result = generator.generate(docker_config)

        # Step 4: Verify Dockerfile
        assert result is not None
        assert result.dockerfile_content is not None

        dockerfile_content = result.dockerfile_content

        # Verify it's a multi-stage build
        assert "FROM python:3.11-slim AS builder" in dockerfile_content

        # Verify requirements installation
        assert "pip install" in dockerfile_content

        # Verify at least some packages from requirements
        assert any(pkg.split(">=")[0] in dockerfile_content for pkg in requirements_list)

    def test_circular_dependencies_add_healthcheck(
        self, sample_python_project: Path, output_dir: Path
    ):
        """
        Test that circular dependencies detected by Heimdall add healthchecks to Docker.

        Circular dependencies might cause initialization issues, so add healthchecks.
        """
        # Analyze dependencies
        dep_config = DependencyConfig(
            scan_path=sample_python_project / "src"
        )
        dep_analyzer = DependencyAnalyzer(dep_config)
        dep_report = dep_analyzer.analyze(sample_python_project / "src")

        # Check for circular dependencies
        has_circular_deps = dep_report.total_cycles > 0

        # Generate Dockerfile
        health_check_cmd = None
        if has_circular_deps:
            health_check_cmd = "curl --fail http://localhost:8000/health || exit 1"

        docker_config = DockerfileConfig(
            name="python-app",
            base_image="python:3.11-slim",
            healthcheck_cmd=health_check_cmd,
            healthcheck_interval="30s",
            healthcheck_timeout="3s",
            healthcheck_retries=3,
            stages=[
                BuildStage(
                    name="runtime",
                    base_image="python:3.11-slim",
                    workdir="/app",
                    cmd=["python", "-m", "src.app.service"]
                )
            ]
        )

        generator = DockerfileGenerator(output_dir=str(output_dir))
        result = generator.generate(docker_config)

        # Verify healthcheck if circular deps exist
        dockerfile_content = result.dockerfile_content

        if has_circular_deps and health_check_cmd:
            assert "HEALTHCHECK" in dockerfile_content

    def test_modularity_score_affects_build_strategy(
        self, sample_python_project: Path, output_dir: Path
    ):
        """
        Test that modularity score influences multi-stage build complexity.

        High modularity = simpler build, low modularity = more careful staging.
        """
        # Analyze dependencies
        dep_config = DependencyConfig(
            scan_path=sample_python_project / "src"
        )
        dep_analyzer = DependencyAnalyzer(dep_config)
        dep_report = dep_analyzer.analyze(sample_python_project / "src")

        # Get modularity score (0-100). DependencyReport.modularity holds the
        # aggregated ModularityMetrics; modularity_score is 0-1 (higher better).
        modularity_score = dep_report.modularity.modularity_score * 100

        # Determine build stages based on modularity
        if modularity_score > 70:
            # High modularity: simple single-stage build
            stages = [
                BuildStage(
                    name="runtime",
                    base_image="python:3.11-slim",
                    workdir="/app",
                    copy_commands=[{"src": ".", "dst": "/app"}],
                    run_commands=["pip install -r requirements.txt"],
                    cmd=["python", "-m", "src.app.service"]
                )
            ]
        else:
            # Low modularity: multi-stage with careful separation
            stages = [
                BuildStage(
                    name="deps",
                    base_image="python:3.11-slim",
                    workdir="/app",
                    copy_commands=[{"src": "requirements.txt", "dst": "/app/"}],
                    run_commands=["pip install --user -r requirements.txt"]
                ),
                BuildStage(
                    name="runtime",
                    base_image="python:3.11-slim",
                    workdir="/app",
                    copy_from="deps",
                    copy_src="/root/.local",
                    copy_dst="/root/.local",
                    copy_commands=[{"src": ".", "dst": "/app"}],
                    cmd=["python", "-m", "src.app.service"]
                )
            ]

        # Generate Dockerfile
        docker_config = DockerfileConfig(
            name="modular-app",
            base_image="python:3.11-slim",
            stages=stages
        )

        generator = DockerfileGenerator(output_dir=str(output_dir))
        result = generator.generate(docker_config)

        # Verify stage count
        assert result is not None
        stage_count = result.dockerfile_content.count("FROM ")
        expected_stages = len(stages)
        assert stage_count == expected_stages
