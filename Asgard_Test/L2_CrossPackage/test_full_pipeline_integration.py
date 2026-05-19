"""
Full Pipeline Integration Tests

Tests for complete multi-package workflows that span all five Asgard packages:
Heimdall, Forseti, Volundr, Freya, and Verdandi.

These tests validate end-to-end development workflows from code analysis through
deployment configuration, UI testing, and performance monitoring.
"""

import json
from pathlib import Path

import pytest
import yaml

from Asgard.Heimdall.Quality import FileAnalyzer, AnalysisConfig
from Asgard.Heimdall.Security import StaticSecurityService
from Asgard.Heimdall.Dependencies import DependencyAnalyzer, DependencyConfig
from Asgard.Forseti.OpenAPI import SpecValidatorService
from Asgard.Volundr.Kubernetes import ManifestConfig, ManifestGenerator, SecurityProfile
from Asgard.Volundr.Docker import DockerfileConfig, DockerfileGenerator
from Asgard.Volundr.Docker.models.docker_models import BuildStage
from Asgard.Volundr.CICD import PipelineConfig, PipelineGenerator, CICDPlatform
from Asgard.Volundr.CICD.models.cicd_models import (
    PipelineStage,
    StepConfig,
    TriggerConfig,
    TriggerType
)
from Asgard.Verdandi.Analysis import SLAChecker, SLAConfig, ApdexCalculator, ApdexConfig


@pytest.mark.cross_package
@pytest.mark.full_pipeline
@pytest.mark.slow
class TestCompleteDevWorkflow:
    """
    Test complete development workflow using all 5 Asgard packages.

    Workflow:
    1. Heimdall: Analyze code quality, security, and dependencies
    2. Forseti: Validate API contracts and schemas
    3. Volundr: Generate deployment configs, Dockerfiles, and CI/CD pipeline
    4. Freya: Mock UI accessibility testing
    5. Verdandi: Set up performance monitoring thresholds
    """

    def test_end_to_end_microservice_deployment(
        self,
        sample_python_project: Path,
        sample_openapi_spec: Path,
        output_dir: Path,
        reports_dir: Path
    ):
        """
        Test complete microservice deployment pipeline.

        This test simulates a real-world workflow where a development team:
        - Analyzes their code
        - Validates their API spec
        - Generates infrastructure
        - Sets up monitoring
        - Deploys to Kubernetes

        All outputs should be consistent and reference each other appropriately.
        """
        # ===================================================================
        # PHASE 1: HEIMDALL - CODE ANALYSIS
        # ===================================================================
        print("\n=== Phase 1: Code Analysis with Heimdall ===")

        # 1a. Quality Analysis
        quality_config = AnalysisConfig(
            scan_path=str(sample_python_project),
            threshold=100
        )
        quality_analyzer = FileAnalyzer(quality_config)
        quality_result = quality_analyzer.analyze()

        assert quality_result.total_files_scanned > 0
        print(f"Files scanned: {quality_result.total_files_scanned}")
        print(f"Compliance rate: {quality_result.compliance_rate:.2f}%")

        # 1b. Security Analysis
        security_service = StaticSecurityService()
        security_report = security_service.scan(str(sample_python_project))

        assert security_report is not None
        print(f"Security score: {security_report.security_score}/100")
        print(f"Vulnerabilities found: {security_report.total_issues}")

        # 1c. Dependency Analysis
        dep_config = DependencyConfig(
            scan_path=sample_python_project / "src"
        )
        dep_analyzer = DependencyAnalyzer(dep_config)
        dep_report = dep_analyzer.analyze(sample_python_project / "src")

        assert dep_report.total_modules > 0
        print(f"Modules analyzed: {dep_report.total_modules}")
        print(f"Circular dependencies: {dep_report.total_cycles}")

        # Save Heimdall reports
        heimdall_report = {
            "quality": {
                "files_scanned": quality_result.total_files_scanned,
                "compliance_rate": quality_result.compliance_rate,
                "violations": quality_result.files_exceeding_threshold
            },
            "security": {
                "score": security_report.security_score,
                "vulnerability_count": security_report.total_issues,
                "critical_count": security_report.critical_issues
            },
            "dependencies": {
                "module_count": dep_report.total_modules,
                "circular_dependencies": dep_report.total_cycles,
                "modularity_score": dep_report.modularity.modularity_score
            }
        }

        heimdall_report_file = reports_dir / "heimdall_analysis.json"
        heimdall_report_file.write_text(json.dumps(heimdall_report, indent=2))
        assert heimdall_report_file.exists()

        # ===================================================================
        # PHASE 2: FORSETI - API CONTRACT VALIDATION
        # ===================================================================
        print("\n=== Phase 2: API Validation with Forseti ===")

        # 2a. Validate OpenAPI Specification
        openapi_validator = SpecValidatorService()
        openapi_result = openapi_validator.validate(str(sample_openapi_spec))

        assert openapi_result.is_valid
        print(f"OpenAPI spec valid: {openapi_result.is_valid}")
        print(f"OpenAPI version: {openapi_result.openapi_version}")

        # 2b. Parse API details
        with open(sample_openapi_spec, 'r') as f:
            api_spec = yaml.safe_load(f)

        api_info = api_spec.get('info', {})
        api_paths = api_spec.get('paths', {})
        endpoint_count = sum(len(methods) for methods in api_paths.values())

        print(f"API: {api_info.get('title', 'Unknown')}")
        print(f"Version: {api_info.get('version', 'Unknown')}")
        print(f"Endpoints: {endpoint_count}")

        # Save Forseti report
        forseti_report = {
            "openapi_valid": openapi_result.is_valid,
            "api_version": openapi_result.openapi_version,
            "api_title": api_info.get('title'),
            "api_version_number": api_info.get('version'),
            "endpoint_count": endpoint_count
        }

        forseti_report_file = reports_dir / "forseti_validation.json"
        forseti_report_file.write_text(json.dumps(forseti_report, indent=2))
        assert forseti_report_file.exists()

        # ===================================================================
        # PHASE 3: VOLUNDR - INFRASTRUCTURE GENERATION
        # ===================================================================
        print("\n=== Phase 3: Infrastructure Generation with Volundr ===")

        app_name = "sample-microservice"

        # 3a. Determine resource requirements based on Heimdall analysis
        complexity_score = 100 - quality_result.compliance_rate

        if complexity_score > 50:
            cpu_request = "500m"
            cpu_limit = "1000m"
            memory_request = "512Mi"
            memory_limit = "1Gi"
        else:
            cpu_request = "250m"
            cpu_limit = "500m"
            memory_request = "256Mi"
            memory_limit = "512Mi"

        # 3b. Determine security profile based on security analysis
        if security_report.security_score < 70:
            security_profile = SecurityProfile.STRICT
        elif security_report.security_score < 90:
            security_profile = SecurityProfile.ENHANCED
        else:
            security_profile = SecurityProfile.BASIC

        print(f"Calculated resources: CPU={cpu_request}/{cpu_limit}, Memory={memory_request}/{memory_limit}")
        print(f"Security profile: {security_profile.value}")

        # 3c. Generate Kubernetes Deployment
        from Asgard.Volundr.Kubernetes.models.kubernetes_models import (
            ResourceRequirements,
            PortConfig
        )

        k8s_config = ManifestConfig(
            name=app_name,
            namespace="default",
            image=f"{app_name}:v1.0.0",
            replicas=2,
            security_profile=security_profile,
            resources=ResourceRequirements(
                cpu_request=cpu_request,
                cpu_limit=cpu_limit,
                memory_request=memory_request,
                memory_limit=memory_limit
            ),
            ports=[
                PortConfig(
                    name="http",
                    container_port=8000,
                    service_port=80
                )
            ],
            annotations={
                "heimdall.quality.compliance": f"{quality_result.compliance_rate:.2f}",
                "heimdall.security.score": str(security_report.security_score),
                "forseti.api.version": api_info.get('version', 'unknown')
            }
        )

        k8s_generator = ManifestGenerator(output_dir=str(output_dir))
        k8s_manifest = k8s_generator.generate(k8s_config)

        assert k8s_manifest is not None
        k8s_file = output_dir / "deployment.yaml"
        k8s_file.write_text(k8s_manifest.yaml_content)
        assert k8s_file.exists()
        print(f"Generated Kubernetes manifest: {k8s_file}")

        # 3d. Generate Dockerfile based on dependencies
        requirements_file = sample_python_project / "requirements.txt"
        requirements_content = requirements_file.read_text()
        requirements_list = [
            line.strip() for line in requirements_content.split("\n")
            if line.strip() and not line.startswith("#")
        ]

        docker_config = DockerfileConfig(
            name=app_name,
            base_image="python:3.11-slim",
            stages=[
                BuildStage(
                    name="builder",
                    base_image="python:3.11-slim",
                    workdir="/app",
                    copy_commands=[
                        {"src": "requirements.txt", "dst": "/app/"}
                    ],
                    run_commands=[
                        "pip install --no-cache-dir --upgrade pip",
                        f"pip install --no-cache-dir {' '.join(requirements_list)}"
                    ]
                ),
                BuildStage(
                    name="runtime",
                    base_image="python:3.11-slim",
                    workdir="/app",
                    copy_from="builder",
                    copy_src="/usr/local/lib/python3.11/site-packages",
                    copy_dst="/usr/local/lib/python3.11/site-packages",
                    copy_commands=[
                        {"src": "src/", "dst": "/app/src/"}
                    ],
                    expose_ports=[8000],
                    cmd=["python", "-m", "uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
                )
            ],
            labels={
                "app": app_name,
                "heimdall.security.score": str(security_report.security_score),
                "heimdall.modules": str(dep_report.total_modules)
            }
        )

        docker_generator = DockerfileGenerator(output_dir=str(output_dir))
        dockerfile_result = docker_generator.generate(docker_config)

        assert dockerfile_result is not None
        dockerfile = output_dir / "Dockerfile"
        dockerfile.write_text(dockerfile_result.dockerfile_content)
        assert dockerfile.exists()
        print(f"Generated Dockerfile: {dockerfile}")

        # 3e. Generate CI/CD Pipeline
        pipeline_stages = [
            PipelineStage(
                name="Code Analysis",
                runs_on="ubuntu-latest",
                steps=[
                    StepConfig(name="Checkout", uses="actions/checkout@v3"),
                    StepConfig(
                        name="Heimdall Quality Check",
                        run="python -m Heimdall quality analyze ./src"
                    ),
                    StepConfig(
                        name="Heimdall Security Scan",
                        run="python -m Heimdall security scan ./src"
                    ),
                ]
            ),
            PipelineStage(
                name="API Validation",
                runs_on="ubuntu-latest",
                needs=["Code Analysis"],
                steps=[
                    StepConfig(
                        name="Validate OpenAPI Spec",
                        run="python -m Forseti openapi validate openapi.yaml"
                    ),
                ]
            ),
            PipelineStage(
                name="Build",
                runs_on="ubuntu-latest",
                needs=["API Validation"],
                steps=[
                    StepConfig(
                        name="Build Docker Image",
                        run=f"docker build -t {app_name}:${{{{ github.sha }}}} ."
                    ),
                    StepConfig(
                        name="Push to Registry",
                        run=f"docker push {app_name}:${{{{ github.sha }}}}"
                    ),
                ]
            ),
            PipelineStage(
                name="Deploy",
                runs_on="ubuntu-latest",
                needs=["Build"],
                steps=[
                    StepConfig(
                        name="Deploy to Kubernetes",
                        run="kubectl apply -f deployment.yaml"
                    ),
                    StepConfig(
                        name="Wait for Rollout",
                        run=f"kubectl rollout status deployment/{app_name}"
                    ),
                ]
            ),
        ]

        # Add accessibility stage if needed (mock)
        pipeline_stages.insert(3, PipelineStage(
            name="Accessibility",
            runs_on="ubuntu-latest",
            needs=["Build"],
            steps=[
                StepConfig(
                    name="Accessibility Audit",
                    run="npm run test:a11y"
                ),
            ]
        ))

        pipeline_config = PipelineConfig(
            name=f"{app_name} CI/CD",
            platform=CICDPlatform.GITHUB_ACTIONS,
            triggers=[
                TriggerConfig(type=TriggerType.PUSH, branches=["main"]),
                TriggerConfig(type=TriggerType.PULL_REQUEST, branches=["main"]),
            ],
            stages=pipeline_stages,
            env={
                "APP_NAME": app_name,
                "HEIMDALL_THRESHOLD": "100",
            }
        )

        pipeline_generator = PipelineGenerator(output_dir=str(output_dir))
        pipeline_result = pipeline_generator.generate(pipeline_config)

        assert pipeline_result is not None
        pipeline_file = output_dir / "ci-cd-pipeline.yaml"
        pipeline_file.write_text(pipeline_result.pipeline_content)
        assert pipeline_file.exists()
        print(f"Generated CI/CD pipeline: {pipeline_file}")

        # ===================================================================
        # PHASE 4: FREYA - UI TESTING CONFIGURATION (MOCKED)
        # ===================================================================
        print("\n=== Phase 4: UI Testing Configuration (Mocked) ===")

        # In a real scenario, would use Freya to test the deployed app
        # For this test, we mock the accessibility results
        mock_a11y_score = 85.0
        mock_wcag_level = "AA"

        print(f"Mocked accessibility score: {mock_a11y_score}")
        print(f"Mocked WCAG level: {mock_wcag_level}")

        freya_report = {
            "accessibility_score": mock_a11y_score,
            "wcag_level": mock_wcag_level,
            "violations": 3,
            "passes": 45
        }

        freya_report_file = reports_dir / "freya_accessibility.json"
        freya_report_file.write_text(json.dumps(freya_report, indent=2))
        assert freya_report_file.exists()

        # ===================================================================
        # PHASE 5: VERDANDI - PERFORMANCE MONITORING SETUP
        # ===================================================================
        print("\n=== Phase 5: Performance Monitoring with Verdandi ===")

        # 5a. Configure SLA based on API complexity (from Forseti)
        if endpoint_count > 10:
            target_success_rate = 0.98
            max_response_time_ms = 1000
        else:
            target_success_rate = 0.99
            max_response_time_ms = 500

        sla_config = SLAConfig(
            threshold_ms=max_response_time_ms,
            target_percentile=99,
        )

        print(f"SLA threshold: {sla_config.threshold_ms}ms")

        # 5b. Configure Apdex based on operation types
        apdex_config = ApdexConfig(threshold_ms=100)

        print(f"Apdex threshold: {apdex_config.threshold_ms}ms")

        # Save Verdandi configuration
        verdandi_report = {
            "sla_config": {
                "threshold_ms": sla_config.threshold_ms,
                "target_percentile": sla_config.target_percentile,
            },
            "apdex_config": {
                "threshold_ms": apdex_config.threshold_ms,
                "frustration_threshold_ms": apdex_config.frustration_threshold_ms,
            },
        }

        verdandi_report_file = reports_dir / "verdandi_monitoring.json"
        verdandi_report_file.write_text(json.dumps(verdandi_report, indent=2))
        assert verdandi_report_file.exists()

        # ===================================================================
        # VERIFICATION: ALL OUTPUTS ARE CONSISTENT
        # ===================================================================
        print("\n=== Verification: Cross-Package Consistency ===")

        # Verify all reports exist
        assert heimdall_report_file.exists()
        assert forseti_report_file.exists()
        assert freya_report_file.exists()
        assert verdandi_report_file.exists()

        # Verify all infrastructure files exist
        assert k8s_file.exists()
        assert dockerfile.exists()
        assert pipeline_file.exists()

        # Verify Kubernetes manifest contains Heimdall annotations
        k8s_content = k8s_file.read_text()
        assert str(quality_result.compliance_rate)[:4] in k8s_content
        assert str(security_report.security_score) in k8s_content

        # Verify Dockerfile contains dependency information
        dockerfile_content = dockerfile.read_text()
        assert "pip install" in dockerfile_content
        assert any(pkg.split(">=")[0] in dockerfile_content for pkg in requirements_list)

        # Verify CI/CD pipeline references all phases
        pipeline_content = pipeline_file.read_text()
        assert "Heimdall" in pipeline_content
        assert "Forseti" in pipeline_content
        assert "Accessibility" in pipeline_content

        print("\n=== All phases completed successfully! ===")
        print(f"Reports directory: {reports_dir}")
        print(f"Output directory: {output_dir}")

    def test_integration_consistency_across_packages(
        self,
        sample_python_project: Path,
        sample_openapi_spec: Path,
        output_dir: Path
    ):
        """
        Test that information flows consistently between packages.

        Verify that data from one package correctly influences another package.
        """
        # Analyze with Heimdall
        quality_config = AnalysisConfig(
            scan_path=str(sample_python_project),
            threshold=100
        )
        quality_analyzer = FileAnalyzer(quality_config)
        quality_result = quality_analyzer.analyze()

        # Validate with Forseti
        openapi_validator = SpecValidatorService()
        openapi_result = openapi_validator.validate(str(sample_openapi_spec))

        # Generate with Volundr using data from both
        app_name = "integration-test-app"

        # Quality influences resources
        compliance_rate = quality_result.compliance_rate
        if compliance_rate < 80:
            replicas = 3  # More replicas for less reliable code
        else:
            replicas = 2

        # API validity influences deployment strategy
        if openapi_result.is_valid:
            annotations = {"api.validated": "true"}
        else:
            annotations = {"api.validated": "false", "deployment.strategy": "canary"}

        k8s_config = ManifestConfig(
            name=app_name,
            image=f"{app_name}:latest",
            replicas=replicas,
            annotations=annotations
        )

        k8s_generator = ManifestGenerator(output_dir=str(output_dir))
        k8s_manifest = k8s_generator.generate(k8s_config)

        # Verify consistency
        yaml_content = k8s_manifest.yaml_content
        assert f"replicas: {replicas}" in yaml_content
        assert "api.validated" in yaml_content

        # Configure Verdandi based on deployment
        # More replicas = higher traffic expected = more lenient SLA
        if replicas > 2:
            max_response_time = 1000
        else:
            max_response_time = 500

        sla_config = SLAConfig(
            threshold_ms=max_response_time,
            target_percentile=95,
        )

        assert sla_config.threshold_ms == max_response_time


@pytest.mark.cross_package
@pytest.mark.full_pipeline
class TestCrossCuttingConcerns:
    """
    Test cross-cutting concerns that affect all packages.

    These tests verify that common requirements like naming conventions,
    output formats, and error handling are consistent across packages.
    """

    def test_consistent_naming_conventions(
        self,
        sample_python_project: Path,
        output_dir: Path
    ):
        """
        Test that all packages use consistent naming conventions.

        Resource names should follow kebab-case, labels should use dots.
        """
        app_name = "test-app"

        # Generate resources from multiple packages
        k8s_config = ManifestConfig(
            name=app_name,
            image=f"{app_name}:latest"
        )

        k8s_generator = ManifestGenerator(output_dir=str(output_dir))
        k8s_manifest = k8s_generator.generate(k8s_config)

        # Verify naming convention
        assert app_name in k8s_manifest.yaml_content
        assert "test_app" not in k8s_manifest.yaml_content  # No underscores
        assert "testApp" not in k8s_manifest.yaml_content   # No camelCase

    def test_consistent_output_formats(
        self,
        sample_python_project: Path,
        output_dir: Path
    ):
        """
        Test that all packages produce valid YAML/JSON output.

        All generated configurations should be parseable.
        """
        # Generate K8s manifest
        k8s_config = ManifestConfig(
            name="format-test",
            image="nginx:latest"
        )
        k8s_generator = ManifestGenerator(output_dir=str(output_dir))
        k8s_manifest = k8s_generator.generate(k8s_config)

        # Verify YAML is parseable (manifest may contain multiple documents).
        docs = [d for d in yaml.safe_load_all(k8s_manifest.yaml_content) if d]
        assert docs, "Expected at least one YAML document"
        first = docs[0]
        assert "apiVersion" in first
        assert "kind" in first

        # Generate pipeline
        pipeline_config = PipelineConfig(
            name="format-test",
            platform=CICDPlatform.GITHUB_ACTIONS,
            stages=[
                PipelineStage(
                    name="Test",
                    runs_on="ubuntu-latest",
                    steps=[StepConfig(name="Test", run="echo test")]
                )
            ]
        )
        pipeline_generator = PipelineGenerator(output_dir=str(output_dir))
        pipeline = pipeline_generator.generate(pipeline_config)

        # Verify pipeline YAML is parseable
        pipeline_data = yaml.safe_load(pipeline.pipeline_content)
        assert pipeline_data is not None
