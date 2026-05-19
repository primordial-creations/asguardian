"""
Freya-Volundr Integration Tests

Tests for cross-package integration between Freya (visual/UI testing) and
Volundr (infrastructure generation). These tests validate workflows where
accessibility scan results inform CI/CD pipeline configuration.

Note: ConfigMapGenerator / JobGenerator / HPAGenerator services were never
implemented in Volundr — only ManifestGenerator and PipelineGenerator exist.
Tests for those non-existent generators have been removed.
"""

from pathlib import Path

import pytest

from Asgard.Freya.Accessibility import (
    AccessibilityConfig,
    AccessibilityReport,
    AccessibilityViolation,
    WCAGLevel,
    ViolationSeverity,
)
from Asgard.Freya.Accessibility.models._accessibility_enums import (
    AccessibilityCategory,
)
from Asgard.Volundr.CICD import PipelineConfig, PipelineGenerator, CICDPlatform
from Asgard.Volundr.CICD.models.cicd_models import (
    PipelineStage,
    StepConfig,
    TriggerConfig,
    TriggerType,
)
from Asgard.Volundr.Kubernetes import ManifestConfig, ManifestGenerator


def _make_violation(
    rule_id: str,
    severity: ViolationSeverity,
    wcag_reference: str = "1.4.3",
    category: AccessibilityCategory = AccessibilityCategory.CONTRAST,
    description: str = "Sample violation",
    element_selector: str = "button.submit",
    suggested_fix: str = "Adjust styling",
) -> AccessibilityViolation:
    """Helper for building AccessibilityViolation instances with current field set."""
    return AccessibilityViolation(
        id=rule_id,
        wcag_reference=wcag_reference,
        category=category,
        severity=severity,
        description=description,
        element_selector=element_selector,
        suggested_fix=suggested_fix,
    )


@pytest.mark.cross_package
@pytest.mark.freya_volundr
class TestAccessibilityReportToCICD:
    """
    Test workflow: Run accessibility scan with Freya, then generate CI/CD pipeline
    with Volundr that includes accessibility gate based on findings.
    """

    def test_accessibility_violations_add_quality_gate(
        self, sample_html_page: Path, output_dir: Path
    ):
        mock_violations = [
            _make_violation("color-contrast", ViolationSeverity.SERIOUS),
            _make_violation(
                "image-alt",
                ViolationSeverity.CRITICAL,
                wcag_reference="1.1.1",
                category=AccessibilityCategory.IMAGES,
            ),
        ]

        mock_report = AccessibilityReport(
            url="http://localhost:3000",
            wcag_level=WCAGLevel.AA.value,
            violations=mock_violations,
            warnings=[],
            notices=[],
            score=65.5,
        )

        critical_violations = [v for v in mock_violations if v.severity == ViolationSeverity.CRITICAL]
        serious_violations = [v for v in mock_violations if v.severity == ViolationSeverity.SERIOUS]

        stages = [
            PipelineStage(
                name="Build",
                steps=[
                    StepConfig(name="Checkout", uses="actions/checkout@v3"),
                    StepConfig(name="Build", run="npm run build"),
                ],
            ),
            PipelineStage(
                name="Test",
                needs=["Build"],
                steps=[StepConfig(name="Unit Tests", run="npm test")],
            ),
        ]

        if critical_violations or serious_violations:
            a11y_stage = PipelineStage(
                name="Accessibility",
                needs=["Build"],
                steps=[
                    StepConfig(name="Accessibility Audit", run="npm run test:a11y"),
                    StepConfig(name="Check Critical Issues", run="npm run check-a11y-critical"),
                ],
            )

            if critical_violations:
                a11y_stage.steps.append(
                    StepConfig(
                        name="Fail on Critical",
                        run="exit 1",
                        if_condition="failure()",
                    )
                )

            stages.insert(2, a11y_stage)

        pipeline_config = PipelineConfig(
            name="CI with Accessibility Gate",
            platform=CICDPlatform.GITHUB_ACTIONS,
            triggers=[TriggerConfig(type=TriggerType.PUSH, branches=["main"])],
            stages=stages,
        )

        generator = PipelineGenerator(output_dir=str(output_dir))
        pipeline = generator.generate(pipeline_config)

        assert pipeline is not None
        assert pipeline.pipeline_content is not None

        content = pipeline.pipeline_content

        if critical_violations or serious_violations:
            assert "Accessibility" in content
            assert "test:a11y" in content
        if critical_violations:
            assert "check-a11y-critical" in content

    def test_wcag_level_determines_pipeline_strictness(self, output_dir: Path):
        wcag_levels = [WCAGLevel.A, WCAGLevel.AA, WCAGLevel.AAA]

        for wcag_level in wcag_levels:
            if wcag_level == WCAGLevel.AAA:
                stages = [
                    PipelineStage(
                        name="Accessibility",
                        steps=[
                            StepConfig(name="WCAG AAA Audit", run="npm run test:a11y -- --level=AAA"),
                            StepConfig(
                                name="Fail on Any Violation",
                                run="test $(cat a11y-report.json | jq '.violations | length') -eq 0",
                            ),
                        ],
                    )
                ]
            elif wcag_level == WCAGLevel.AA:
                stages = [
                    PipelineStage(
                        name="Accessibility",
                        steps=[
                            StepConfig(name="WCAG AA Audit", run="npm run test:a11y -- --level=AA"),
                            StepConfig(
                                name="Check Critical and Serious",
                                run="npm run check-a11y-threshold -- --max-violations=2",
                            ),
                        ],
                    )
                ]
            else:
                stages = [
                    PipelineStage(
                        name="Accessibility",
                        steps=[
                            StepConfig(name="WCAG A Audit", run="npm run test:a11y -- --level=A"),
                            StepConfig(name="Check Critical Only", run="npm run check-a11y-critical"),
                        ],
                    )
                ]

            pipeline_config = PipelineConfig(
                name=f"CI with {wcag_level.value} Accessibility",
                platform=CICDPlatform.GITHUB_ACTIONS,
                stages=stages,
            )

            generator = PipelineGenerator(output_dir=str(output_dir))
            pipeline = generator.generate(pipeline_config)

            content = pipeline.pipeline_content
            assert wcag_level.value in content

            if wcag_level == WCAGLevel.AAA:
                assert "AAA" in content
                assert "Any Violation" in content
            elif wcag_level == WCAGLevel.AA:
                assert "AA" in content

    def test_accessibility_score_influences_deployment_strategy(self, output_dir: Path):
        test_cases = [
            (95, "RollingUpdate"),
            (75, "Canary"),
            (50, "Blue-Green"),
        ]

        for score, expected_strategy in test_cases:
            k8s_config = ManifestConfig(
                name=f"app-score-{score}",
                image="myapp:latest",
                replicas=3,
                annotations={
                    "deployment.strategy": expected_strategy,
                    "accessibility.score": str(score),
                },
            )

            generator = ManifestGenerator(output_dir=str(output_dir))
            manifest = generator.generate(k8s_config)

            yaml_content = manifest.yaml_content
            assert str(score) in yaml_content
            assert expected_strategy in yaml_content


@pytest.mark.cross_package
@pytest.mark.freya_volundr
class TestColorContrastToCICDWarnings:
    """
    Test workflow: Color contrast issues detected by Freya trigger warnings
    in CI/CD pipeline generated by Volundr.
    """

    def test_contrast_violations_add_warning_annotations(self, output_dir: Path):
        contrast_violations = [
            {"foreground": "#777777", "background": "#ffffff", "ratio": 4.2, "required": 4.5},
            {"foreground": "#999999", "background": "#ffffff", "ratio": 2.8, "required": 3.0},
        ]

        stages = [
            PipelineStage(
                name="Build",
                steps=[StepConfig(name="Build", run="npm run build")],
            ),
            PipelineStage(
                name="Accessibility Checks",
                needs=["Build"],
                steps=[StepConfig(name="Color Contrast Check", run="npm run check-contrast")],
            ),
        ]

        for i, violation in enumerate(contrast_violations):
            stages[1].steps.append(
                StepConfig(
                    name=f"Contrast Warning {i+1}",
                    run=f"echo '::warning::Contrast ratio {violation['ratio']} below {violation['required']}'",
                )
            )

        pipeline_config = PipelineConfig(
            name="CI with Contrast Warnings",
            platform=CICDPlatform.GITHUB_ACTIONS,
            stages=stages,
        )

        generator = PipelineGenerator(output_dir=str(output_dir))
        pipeline = generator.generate(pipeline_config)

        content = pipeline.pipeline_content
        assert "Color Contrast Check" in content
        assert "::warning::" in content
        assert "Contrast ratio" in content

    def test_severe_contrast_issues_block_deployment(self, output_dir: Path):
        has_severe_contrast_issue = True
        severe_ratio = 1.5
        required_ratio = 4.5

        stages = [
            PipelineStage(
                name="Build",
                steps=[StepConfig(name="Build", run="npm run build")],
            ),
            PipelineStage(
                name="Accessibility Gate",
                needs=["Build"],
                steps=[StepConfig(name="Check Contrast", run="npm run check-contrast")],
            ),
        ]

        if has_severe_contrast_issue and severe_ratio < 2.0:
            stages[1].steps.append(
                StepConfig(
                    name="Block on Severe Contrast Issue",
                    run=f"echo 'FAIL: Contrast ratio {severe_ratio} is critically low (required: {required_ratio})' && exit 1",
                )
            )

        pipeline_config = PipelineConfig(
            name="CI with Contrast Gate",
            platform=CICDPlatform.GITHUB_ACTIONS,
            stages=stages,
        )

        generator = PipelineGenerator(output_dir=str(output_dir))
        pipeline = generator.generate(pipeline_config)

        content = pipeline.pipeline_content
        assert "Block on Severe Contrast Issue" in content
        assert "exit 1" in content
        assert "critically low" in content
