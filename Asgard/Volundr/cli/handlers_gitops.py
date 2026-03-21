import argparse
from pathlib import Path

from Asgard.Volundr.CICD import (
    PipelineConfig,
    PipelineGenerator,
    CICDPlatform,
    PipelineStage,
    TriggerConfig,
    TriggerType,
    StepConfig,
)
from Asgard.Volundr.Helm import (
    HelmChart,
    HelmValues,
    HelmConfig,
    ChartGenerator,
    ValuesGenerator,
)
from Asgard.Volundr.Kustomize import (
    KustomizeBase,
    KustomizeOverlay,
    KustomizeConfig,
    BaseGenerator,
    OverlayGenerator,
)
from Asgard.Volundr.GitOps import (
    ArgoApplication,
    ArgoSource,
    ArgoDestination,
    ArgoCDGenerator,
    FluxGenerator,
    FluxGitRepository,
    FluxKustomization,
)


def run_cicd_generate(args: argparse.Namespace) -> int:
    """Execute CI/CD pipeline generation."""
    triggers = [
        TriggerConfig(type=TriggerType.PUSH, branches=[args.branch]),
        TriggerConfig(type=TriggerType.PULL_REQUEST, branches=[args.branch]),
    ]

    stages = [
        PipelineStage(
            name="build",
            runs_on="ubuntu-latest",
            steps=[
                StepConfig(name="Checkout", uses="actions/checkout@v4"),
                StepConfig(name="Setup Python", uses="actions/setup-python@v5", with_params={"python-version": "3.12"}),
                StepConfig(name="Install dependencies", run="pip install -r requirements.txt"),
                StepConfig(name="Run tests", run="pytest"),
            ],
        ),
    ]

    if args.docker_image:
        stages.append(PipelineStage(
            name="docker",
            runs_on="ubuntu-latest",
            needs=["build"],
            steps=[
                StepConfig(name="Checkout", uses="actions/checkout@v4"),
                StepConfig(
                    name="Build and push",
                    uses="docker/build-push-action@v5",
                    with_params={
                        "push": True,
                        "tags": args.docker_image,
                    },
                ),
            ],
        ))

    config = PipelineConfig(
        name=args.name,
        platform=CICDPlatform(args.platform),
        triggers=triggers,
        stages=stages,
        concurrency={"group": "${{ github.workflow }}-${{ github.ref }}", "cancel-in-progress": True},
    )

    generator = PipelineGenerator(output_dir=args.output_dir)
    pipeline = generator.generate(config)

    if not args.dry_run:
        file_path = generator.save_to_file(pipeline, args.output_dir)
        print(f"\nPipeline generated successfully!")
        print(f"File: {file_path}")
    else:
        print("\n[DRY RUN] Would generate pipeline")

    print(f"Platform: {pipeline.platform.value}")
    print(f"Best Practice Score: {pipeline.best_practice_score:.1f}/100")

    if pipeline.validation_results:
        print("\nValidation Issues:")
        for issue in pipeline.validation_results:
            print(f"  - {issue}")
    else:
        print("\nNo validation issues found!")

    return 0


def run_helm_init(args: argparse.Namespace) -> int:
    """Initialize a new Helm chart."""
    chart = HelmChart(
        name=args.name,
        version=args.version,
        app_version=args.app_version,
        description=args.description or f"A Helm chart for {args.name}",
    )

    values = HelmValues(
        image_repository=args.image,
        image_tag=args.app_version,
    )

    config = HelmConfig(chart=chart, values=values)
    generator = ChartGenerator(output_dir=args.output_dir)
    result = generator.generate(config)

    if not args.dry_run:
        chart_dir = generator.save_to_directory(result, args.output_dir)
        print(f"\nHelm chart initialized successfully!")
        print(f"Directory: {chart_dir}")
    else:
        print("\n[DRY RUN] Would generate Helm chart with files:")
        for filename in result.chart_files.keys():
            print(f"  - {filename}")

    print(f"Files: {result.file_count}")
    print(f"Best Practice Score: {result.best_practice_score:.1f}/100")

    return 0


def run_helm_values(args: argparse.Namespace) -> int:
    """Generate values.yaml for an environment."""
    generator = ValuesGenerator(output_dir=args.output_dir)
    values_yaml = generator.generate_yaml(
        image_repository=args.image,
        environment=args.environment,
    )

    if not args.dry_run:
        output_file = Path(args.output_dir) / f"values-{args.environment}.yaml"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(values_yaml)
        print(f"\nValues file generated successfully!")
        print(f"File: {output_file}")
    else:
        print("\n[DRY RUN] Would generate values.yaml:")
        print(values_yaml[:500] + "..." if len(values_yaml) > 500 else values_yaml)

    return 0


def run_kustomize_init(args: argparse.Namespace) -> int:
    """Initialize Kustomize base."""
    base = KustomizeBase(name=args.name, namespace=args.namespace)
    config = KustomizeConfig(
        base=base,
        image=args.image,
        container_port=args.port,
    )

    generator = BaseGenerator(output_dir=args.output_dir)
    result = generator.generate(config)

    if not args.dry_run:
        output_dir = generator.save_to_directory(result, args.output_dir)
        print(f"\nKustomize base initialized successfully!")
        print(f"Directory: {output_dir}")
    else:
        print("\n[DRY RUN] Would generate Kustomize base with files:")
        for filename in result.files.keys():
            print(f"  - {filename}")

    print(f"Files: {result.file_count}")
    print(f"Best Practice Score: {result.best_practice_score:.1f}/100")

    return 0


def run_kustomize_overlay(args: argparse.Namespace) -> int:
    """Generate Kustomize overlay."""
    overlay = KustomizeOverlay(
        name=args.env,
        bases=[args.base],
        namespace=args.namespace,
    )

    generator = OverlayGenerator(output_dir=args.output_dir)
    result = generator.generate(overlay, base_path=args.base)

    if not args.dry_run:
        output_dir = generator.save_to_directory(result, args.output_dir)
        print(f"\nKustomize overlay generated successfully!")
        print(f"Directory: {output_dir}")
    else:
        print("\n[DRY RUN] Would generate overlay with files:")
        for filename in result.files.keys():
            print(f"  - {filename}")

    print(f"Files: {result.file_count}")
    print(f"Best Practice Score: {result.best_practice_score:.1f}/100")

    return 0


def run_argocd_app(args: argparse.Namespace) -> int:
    """Generate ArgoCD Application manifest."""
    generator = ArgoCDGenerator(output_dir=args.output_dir)
    result = generator.generate_from_repo(
        name=args.name,
        repo_url=args.repo,
        path=args.path,
        target_namespace=args.namespace,
        target_revision=args.revision,
        project=args.project,
        automated=args.auto_sync,
    )

    if not args.dry_run:
        output_dir = generator.save_to_directory(result, args.output_dir)
        print(f"\nArgoCD Application generated successfully!")
        print(f"Directory: {output_dir}")
    else:
        print("\n[DRY RUN] Would generate ArgoCD Application:")
        for filename, content in result.files.items():
            print(f"\n--- {filename} ---")
            print(content[:500] + "..." if len(content) > 500 else content)

    print(f"Best Practice Score: {result.best_practice_score:.1f}/100")

    return 0


def run_flux_source(args: argparse.Namespace) -> int:
    """Generate Flux GitRepository."""
    git_repo = FluxGitRepository(
        name=args.name,
        url=args.repo,
        branch=args.branch,
        interval=args.interval,
    )

    generator = FluxGenerator(output_dir=args.output_dir)
    result = generator.generate_git_repository(git_repo)

    if not args.dry_run:
        output_dir = generator.save_to_directory(result, args.output_dir)
        print(f"\nFlux GitRepository generated successfully!")
        print(f"Directory: {output_dir}")
    else:
        print("\n[DRY RUN] Would generate Flux GitRepository")

    print(f"Best Practice Score: {result.best_practice_score:.1f}/100")

    return 0


def run_flux_kustomization(args: argparse.Namespace) -> int:
    """Generate Flux Kustomization."""
    ks = FluxKustomization(
        name=args.name,
        source_ref_name=args.source,
        path=args.path,
        target_namespace=args.namespace,
        interval=args.interval,
    )

    generator = FluxGenerator(output_dir=args.output_dir)
    result = generator.generate_kustomization(ks)

    if not args.dry_run:
        output_dir = generator.save_to_directory(result, args.output_dir)
        print(f"\nFlux Kustomization generated successfully!")
        print(f"Directory: {output_dir}")
    else:
        print("\n[DRY RUN] Would generate Flux Kustomization")

    print(f"Best Practice Score: {result.best_practice_score:.1f}/100")

    return 0
