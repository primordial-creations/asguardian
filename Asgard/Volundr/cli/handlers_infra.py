import argparse

from Asgard.Volundr.Kubernetes import (
    ManifestConfig,
    ManifestGenerator,
    WorkloadType,
    SecurityProfile,
    EnvironmentType,
    PortConfig,
)
from Asgard.Volundr.Terraform import (
    ModuleConfig,
    ModuleBuilder,
    CloudProvider,
    ResourceCategory,
    ModuleComplexity,
    VariableConfig,
    OutputConfig,
)
from Asgard.Volundr.Docker import (
    DockerfileConfig,
    DockerfileGenerator,
    ComposeConfig,
    ComposeGenerator,
    ComposeServiceConfig,
    BuildStage,
)
from Asgard.Volundr.Docker.models.docker_models import SecretMount


def _parse_suppressions(raw: list) -> list:
    """Parse repeatable --suppress RULE:TARGET:REASON flags."""
    from Asgard.Volundr.Validation.models.suppression_models import Suppression

    suppressions = []
    for item in raw or []:
        parts = item.split(":", 2)
        if len(parts) != 3:
            raise ValueError(
                f"Invalid --suppress '{item}': expected RULE:TARGET:REASON "
                "(reason is mandatory)"
            )
        suppressions.append(
            Suppression(rule=parts[0], target=parts[1], reason=parts[2])
        )
    return suppressions


def run_kubernetes_generate(args: argparse.Namespace) -> int:
    """Execute Kubernetes manifest generation."""
    try:
        suppressions = _parse_suppressions(getattr(args, "suppress", []))
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    config = ManifestConfig(
        name=args.name,
        namespace=args.namespace,
        workload_type=WorkloadType(args.type),
        image=args.image,
        image_digest=getattr(args, "digest", None),
        replicas=args.replicas,
        environment=EnvironmentType(args.environment),
        security_profile=SecurityProfile(args.security_profile),
        ports=[PortConfig(container_port=args.port)],
        target_k8s_version=getattr(args, "target_k8s_version", "1.30"),
        suppressions=suppressions,
    )

    generator = ManifestGenerator(output_dir=args.output_dir)
    manifest = generator.generate(config)

    if not args.dry_run:
        file_path = generator.save_to_file(manifest, args.output_dir)
        print(f"\nManifest generated successfully!")
        print(f"File: {file_path}")
    else:
        print("\n[DRY RUN] Would generate manifest:")
        print(manifest.yaml_content[:500] + "..." if len(manifest.yaml_content) > 500 else manifest.yaml_content)

    print(f"Best Practice Score: {manifest.best_practice_score:.1f}/100")

    if manifest.validation_results:
        print("\nValidation Issues:")
        for issue in manifest.validation_results:
            print(f"  - {issue}")
    else:
        print("\nNo validation issues found!")

    return 0


def run_terraform_generate(args: argparse.Namespace) -> int:
    """Execute Terraform module generation."""
    try:
        suppressions = _parse_suppressions(getattr(args, "suppress", []))
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    variables = []
    outputs = []
    resources = []
    data_sources = []

    if args.provider == "aws":
        if args.category == "compute":
            variables.extend([
                VariableConfig(name="instance_type", type="string", description="EC2 instance type", default="t3.micro"),
                VariableConfig(name="instance_name", type="string", description="Name for the EC2 instance"),
            ])
            resources.append("aws_instance")
            data_sources.extend(["aws_ami", "aws_vpc", "aws_subnets"])
            outputs.extend([
                OutputConfig(name="instance_id", description="The ID of the EC2 instance", value="aws_instance.main.id"),
                OutputConfig(name="instance_arn", description="The ARN of the EC2 instance", value="aws_instance.main.arn"),
            ])
        elif args.category == "storage":
            variables.append(VariableConfig(name="bucket_name", type="string", description="Name of the S3 bucket"))
            resources.append("aws_s3_bucket")
            outputs.extend([
                OutputConfig(name="bucket_id", description="The ID of the S3 bucket", value="aws_s3_bucket.main.id"),
                OutputConfig(name="bucket_arn", description="The ARN of the S3 bucket", value="aws_s3_bucket.main.arn"),
            ])

    config = ModuleConfig(
        name=args.name,
        provider=CloudProvider(args.provider),
        category=ResourceCategory(args.category),
        complexity=ModuleComplexity(args.complexity),
        description=args.description or f"Terraform module for {args.category} resources on {args.provider}",
        variables=variables,
        outputs=outputs,
        resources=resources,
        data_sources=data_sources,
        tags={"ManagedBy": "Terraform", "Module": args.name},
        environment_profile=getattr(args, "environment", "production"),
        suppressions=suppressions,
        kms_encryption=getattr(args, "kms_encryption", False),
    )

    builder = ModuleBuilder(output_dir=args.output_dir)
    module = builder.generate(config)

    if module.score_report is not None:
        print(f"Composite Score: {module.score_report.composite:.1f}/100 ({module.score_report.grade})")
        if module.score_report.veto_applied:
            print(f"Security veto applied: {module.score_report.veto_applied}")

    if not args.dry_run:
        module_dir = builder.save_to_directory(module, args.output_dir)
        print(f"\nModule generated successfully!")
        print(f"Directory: {module_dir}")
    else:
        print("\n[DRY RUN] Would generate module with files:")
        for filename in module.module_files.keys():
            print(f"  - {filename}")

    print(f"Files: {module.file_count}")
    print(f"Best Practice Score: {module.best_practice_score:.1f}/100")

    if module.validation_results:
        print("\nValidation Issues:")
        for issue in module.validation_results:
            print(f"  - {issue}")
    else:
        print("\nNo validation issues found!")

    return 0


def run_docker_dockerfile(args: argparse.Namespace) -> int:
    """Execute Dockerfile generation."""
    stages = []

    if args.multi_stage:
        stages.append(BuildStage(
            name="builder",
            base_image=args.base,
            workdir=args.workdir,
            copy_commands=[{"src": "requirements.txt", "dst": "."}],
            run_commands=["pip install --no-cache-dir -r requirements.txt"],
        ))
        stages.append(BuildStage(
            name="runtime",
            base_image=args.base.replace(":latest", "-slim") if ":latest" in args.base else args.base,
            workdir=args.workdir,
            user=args.user,
            copy_from="builder",
            copy_src="/usr/local/lib/python",
            copy_dst="/usr/local/lib/python",
            copy_commands=[{"src": ".", "dst": ".", "chown": f"{args.user}:{args.user}"}],
            expose_ports=[args.port],
            cmd=["python", "main.py"],
        ))
    else:
        stages.append(BuildStage(
            name="",
            base_image=args.base,
            workdir=args.workdir,
            user=args.user,
            copy_commands=[{"src": ".", "dst": "."}],
            run_commands=[
                "adduser --disabled-password --gecos '' " + args.user,
                "chown -R " + args.user + ":" + args.user + " " + args.workdir,
            ],
            expose_ports=[args.port],
            cmd=["python", "main.py"],
        ))

    secret_mounts = []
    for spec in getattr(args, "secret_mounts", None) or []:
        parts = spec.split(":", 1)
        secret_mounts.append(SecretMount(
            id=parts[0],
            target=parts[1] if len(parts) > 1 else None,
        ))

    digest = getattr(args, "digest", None)
    if digest:
        for stage in stages:
            if stage.base_image == args.base:
                stage.base_image_digest = digest
    if secret_mounts:
        # Build-time secrets belong on the build (first) stage.
        stages[0].secret_mounts = secret_mounts

    config = DockerfileConfig(
        name=args.name,
        stages=stages,
        labels={
            "org.opencontainers.image.title": args.name,
            "org.opencontainers.image.source": "https://github.com/your-org/your-repo",
        },
        healthcheck={
            "test": ["CMD", "curl", "-f", f"http://localhost:{args.port}/health"],
            "interval": "30s",
            "timeout": "10s",
            "retries": 3,
        },
    )

    generator = DockerfileGenerator(output_dir=args.output_dir)
    docker_config = generator.generate(config)

    if not args.dry_run:
        file_path = generator.save_to_file(docker_config, args.output_dir)
        print(f"\nDockerfile generated successfully!")
        print(f"File: {file_path}")
    else:
        print("\n[DRY RUN] Would generate Dockerfile")

    print(f"Best Practice Score: {docker_config.best_practice_score:.1f}/100")

    if docker_config.validation_results:
        print("\nValidation Issues:")
        for issue in docker_config.validation_results:
            print(f"  - {issue}")
    else:
        print("\nNo validation issues found!")

    return 0


def run_docker_compose(args: argparse.Namespace) -> int:
    """Execute docker-compose.yml generation."""
    services = []
    for svc_name in args.services:
        services.append(ComposeServiceConfig(
            name=svc_name,
            build={"context": f"./{svc_name}", "dockerfile": "Dockerfile"},
            ports=[f"8080:8080"],
            restart="unless-stopped",
            healthcheck={
                "test": ["CMD", "curl", "-f", "http://localhost:8080/health"],
                "interval": "30s",
                "timeout": "10s",
                "retries": 3,
            },
        ))

    config = ComposeConfig(services=services)

    generator = ComposeGenerator(output_dir=args.output_dir)
    compose_config = generator.generate(config)

    if not args.dry_run:
        file_path = generator.save_to_file(compose_config, args.output_dir)
        print(f"\ndocker-compose.yml generated successfully!")
        print(f"File: {file_path}")
    else:
        print("\n[DRY RUN] Would generate docker-compose.yml")

    print(f"Best Practice Score: {compose_config.best_practice_score:.1f}/100")

    if compose_config.validation_results:
        print("\nValidation Issues:")
        for issue in compose_config.validation_results:
            print(f"  - {issue}")
    else:
        print("\nNo validation issues found!")

    return 0
