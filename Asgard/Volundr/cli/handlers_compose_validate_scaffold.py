import argparse
from pathlib import Path

from Asgard.common.output_formatter import OutputFormat, UnifiedFormatter
from Asgard.Volundr.Compose import (
    ComposeProject,
    ComposeService,
    ComposeProjectGenerator,
    ComposeValidator,
    HealthCheckConfig,
)
from Asgard.Volundr.Validation import (
    KubernetesValidator,
    TerraformValidator,
    DockerfileValidator,
    ValidationContext,
)
from Asgard.Volundr.Scaffold import (
    ServiceConfig,
    ProjectConfig,
    MicroserviceScaffold,
    MonorepoScaffold,
    Language,
    Framework,
    ProjectType,
)


def run_compose_generate(args: argparse.Namespace) -> int:
    """Generate docker-compose.yaml."""
    services = []
    if args.services:
        for svc_def in args.services:
            parts = svc_def.split(":")
            name = parts[0]
            image = parts[1] if len(parts) > 1 else f"{name}:latest"
            port = int(parts[2]) if len(parts) > 2 else 8080

            services.append(ComposeService(
                name=name,
                image=image,
                ports=[f"{port}:{port}"],
                healthcheck=HealthCheckConfig(
                    test=["CMD", "curl", "-f", f"http://localhost:{port}/health"],
                ),
            ))
    else:
        services.append(ComposeService(
            name=args.name,
            build={"context": ".", "dockerfile": "Dockerfile"},
            ports=["8080:8080"],
        ))

    project = ComposeProject(name=args.name, services=services)
    generator = ComposeProjectGenerator(output_dir=args.output_dir)
    result = generator.generate_with_override(project, args.environment)

    if not args.dry_run:
        file_path = generator.save_to_file(result, args.output_dir)
        print(f"\ndocker-compose.yaml generated successfully!")
        print(f"File: {file_path}")
    else:
        print("\n[DRY RUN] Would generate docker-compose.yaml")

    print(f"Best Practice Score: {result.best_practice_score:.1f}/100")

    return 0


def run_compose_validate(args: argparse.Namespace) -> int:
    """Validate docker-compose.yaml."""
    validator = ComposeValidator()
    report = validator.validate_file(args.file)

    formatter = UnifiedFormatter(OutputFormat.TEXT)
    print(formatter.format_report(report))

    return 0 if not report.error_count else 1


def run_validate_kubernetes(args: argparse.Namespace) -> int:
    """Validate Kubernetes manifests."""
    context = ValidationContext(strict_mode=args.strict) if hasattr(args, 'strict') else None
    validator = KubernetesValidator(context=context)

    path = Path(args.path)
    if path.is_file():
        report = validator.validate_file(args.path)
    else:
        report = validator.validate_directory(args.path)

    formatter = UnifiedFormatter(OutputFormat.TEXT)
    print(formatter.format_report(report))

    print(f"\nValidation Score: {report.score:.1f}/100")
    print(f"Files validated: {report.total_files}")

    return 0 if report.passed else 1


def run_validate_terraform(args: argparse.Namespace) -> int:
    """Validate Terraform configurations."""
    validator = TerraformValidator()

    path = Path(args.path)
    if path.is_file():
        report = validator.validate_file(args.path)
    else:
        report = validator.validate_directory(args.path)

    formatter = UnifiedFormatter(OutputFormat.TEXT)
    print(formatter.format_report(report))

    print(f"\nValidation Score: {report.score:.1f}/100")

    return 0 if report.passed else 1


def run_validate_dockerfile(args: argparse.Namespace) -> int:
    """Validate Dockerfile."""
    validator = DockerfileValidator()

    path = Path(args.path)
    if path.is_file():
        report = validator.validate_file(args.path)
    else:
        report = validator.validate_directory(args.path)

    formatter = UnifiedFormatter(OutputFormat.TEXT)
    print(formatter.format_report(report))

    print(f"\nValidation Score: {report.score:.1f}/100")

    return 0 if report.passed else 1


def run_scaffold_microservice(args: argparse.Namespace) -> int:
    """Scaffold a microservice."""
    config = ServiceConfig(
        name=args.name,
        description=args.description or f"A {args.language} microservice",
        language=Language(args.language),
        framework=Framework(args.framework),
        port=args.port,
    )

    scaffold = MicroserviceScaffold(output_dir=args.output_dir)
    report = scaffold.generate(config)

    if not args.dry_run:
        output_path = scaffold.save_to_directory(report, args.output_dir)
        print(f"\nMicroservice scaffolded successfully!")
        print(f"Directory: {output_path}")
    else:
        print("\n[DRY RUN] Would create files:")
        for f in report.files[:10]:
            print(f"  - {f.path}")
        if len(report.files) > 10:
            print(f"  ... and {len(report.files) - 10} more files")

    print(f"\nTotal files: {report.file_count}")
    print(f"Total directories: {report.total_directories}")

    if report.next_steps:
        print("\nNext steps:")
        for step in report.next_steps:
            if step:
                print(f"  {step}")

    return 0


def run_scaffold_monorepo(args: argparse.Namespace) -> int:
    """Scaffold a monorepo."""
    services = []
    if args.services:
        for svc_name in args.services:
            services.append(ServiceConfig(
                name=svc_name,
                language=Language(args.language),
                framework=Framework.FASTAPI if args.language == "python" else Framework.EXPRESS,
            ))

    config = ProjectConfig(
        name=args.name,
        description=args.description or f"A {args.language} monorepo",
        services=services,
        monorepo=True,
    )

    scaffold = MonorepoScaffold(output_dir=args.output_dir)
    report = scaffold.generate(config)

    if not args.dry_run:
        output_path = scaffold.save_to_directory(report, args.output_dir)
        print(f"\nMonorepo scaffolded successfully!")
        print(f"Directory: {output_path}")
    else:
        print("\n[DRY RUN] Would create structure with:")
        print(f"  - {len(report.directories)} directories")
        print(f"  - {len(report.files)} files")

    print(f"\nTotal files: {report.file_count}")
    print(f"Total directories: {report.total_directories}")

    if report.next_steps:
        print("\nNext steps:")
        for step in report.next_steps:
            if step:
                print(f"  {step}")

    return 0
