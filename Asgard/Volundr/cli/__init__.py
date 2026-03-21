import sys

from Asgard.Volundr.cli._parser import create_parser
from Asgard.Volundr.cli.handlers_infra import (
    run_kubernetes_generate,
    run_terraform_generate,
    run_docker_dockerfile,
    run_docker_compose,
)
from Asgard.Volundr.cli.handlers_gitops import (
    run_cicd_generate,
    run_helm_init,
    run_helm_values,
    run_kustomize_init,
    run_kustomize_overlay,
    run_argocd_app,
    run_flux_source,
    run_flux_kustomization,
)
from Asgard.Volundr.cli.handlers_compose_validate_scaffold import (
    run_compose_generate,
    run_compose_validate,
    run_validate_kubernetes,
    run_validate_terraform,
    run_validate_dockerfile,
    run_scaffold_microservice,
    run_scaffold_monorepo,
)


def main(args=None) -> int:
    """Main entry point.

    Args:
        args: Optional list of arguments. If None, uses sys.argv.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    parser = create_parser()
    parsed_args = parser.parse_args(args)

    if hasattr(parsed_args, 'output') and parsed_args.output:
        if hasattr(parsed_args, 'output_dir'):
            parsed_args.output_dir = parsed_args.output

    if hasattr(parsed_args, 'dry_run'):
        pass

    if parsed_args.command is None:
        parser.print_help()
        sys.exit(1)

    if parsed_args.command in ("kubernetes", "k8s"):
        if not hasattr(parsed_args, "k8s_command") or parsed_args.k8s_command is None:
            print("Error: Please specify a kubernetes command (e.g., 'generate')")
            sys.exit(1)
        if parsed_args.k8s_command == "generate":
            sys.exit(run_kubernetes_generate(parsed_args))

    elif parsed_args.command in ("terraform", "tf"):
        if not hasattr(parsed_args, "tf_command") or parsed_args.tf_command is None:
            print("Error: Please specify a terraform command (e.g., 'generate')")
            sys.exit(1)
        if parsed_args.tf_command == "generate":
            sys.exit(run_terraform_generate(parsed_args))

    elif parsed_args.command == "docker":
        if not hasattr(parsed_args, "docker_command") or parsed_args.docker_command is None:
            print("Error: Please specify a docker command (e.g., 'dockerfile', 'compose')")
            sys.exit(1)
        if parsed_args.docker_command == "dockerfile":
            sys.exit(run_docker_dockerfile(parsed_args))
        elif parsed_args.docker_command == "compose":
            sys.exit(run_docker_compose(parsed_args))

    elif parsed_args.command == "cicd":
        if not hasattr(parsed_args, "cicd_command") or parsed_args.cicd_command is None:
            print("Error: Please specify a cicd command (e.g., 'generate')")
            sys.exit(1)
        if parsed_args.cicd_command == "generate":
            sys.exit(run_cicd_generate(parsed_args))

    elif parsed_args.command == "helm":
        if not hasattr(parsed_args, "helm_command") or parsed_args.helm_command is None:
            print("Error: Please specify a helm command (e.g., 'init', 'values')")
            sys.exit(1)
        if parsed_args.helm_command == "init":
            sys.exit(run_helm_init(parsed_args))
        elif parsed_args.helm_command == "values":
            sys.exit(run_helm_values(parsed_args))

    elif parsed_args.command == "kustomize":
        if not hasattr(parsed_args, "kustomize_command") or parsed_args.kustomize_command is None:
            print("Error: Please specify a kustomize command (e.g., 'init', 'overlay')")
            sys.exit(1)
        if parsed_args.kustomize_command == "init":
            sys.exit(run_kustomize_init(parsed_args))
        elif parsed_args.kustomize_command == "overlay":
            sys.exit(run_kustomize_overlay(parsed_args))

    elif parsed_args.command == "argocd":
        if not hasattr(parsed_args, "argocd_command") or parsed_args.argocd_command is None:
            print("Error: Please specify an argocd command (e.g., 'app')")
            sys.exit(1)
        if parsed_args.argocd_command == "app":
            sys.exit(run_argocd_app(parsed_args))

    elif parsed_args.command == "flux":
        if not hasattr(parsed_args, "flux_command") or parsed_args.flux_command is None:
            print("Error: Please specify a flux command (e.g., 'source', 'kustomization')")
            sys.exit(1)
        if parsed_args.flux_command == "source":
            sys.exit(run_flux_source(parsed_args))
        elif parsed_args.flux_command == "kustomization":
            sys.exit(run_flux_kustomization(parsed_args))

    elif parsed_args.command == "compose":
        if not hasattr(parsed_args, "compose_command") or parsed_args.compose_command is None:
            print("Error: Please specify a compose command (e.g., 'generate', 'validate')")
            sys.exit(1)
        if parsed_args.compose_command == "generate":
            sys.exit(run_compose_generate(parsed_args))
        elif parsed_args.compose_command == "validate":
            sys.exit(run_compose_validate(parsed_args))

    elif parsed_args.command == "validate":
        if not hasattr(parsed_args, "validate_command") or parsed_args.validate_command is None:
            print("Error: Please specify a validate command (e.g., 'kubernetes', 'terraform', 'dockerfile')")
            sys.exit(1)
        if parsed_args.validate_command in ("kubernetes", "k8s"):
            sys.exit(run_validate_kubernetes(parsed_args))
        elif parsed_args.validate_command in ("terraform", "tf"):
            sys.exit(run_validate_terraform(parsed_args))
        elif parsed_args.validate_command == "dockerfile":
            sys.exit(run_validate_dockerfile(parsed_args))

    elif parsed_args.command == "scaffold":
        if not hasattr(parsed_args, "scaffold_command") or parsed_args.scaffold_command is None:
            print("Error: Please specify a scaffold command (e.g., 'microservice', 'monorepo')")
            sys.exit(1)
        if parsed_args.scaffold_command == "microservice":
            sys.exit(run_scaffold_microservice(parsed_args))
        elif parsed_args.scaffold_command == "monorepo":
            sys.exit(run_scaffold_monorepo(parsed_args))

    else:
        print(f"Unknown command: {parsed_args.command}")
        sys.exit(1)

    return 0


if __name__ == "__main__":
    main()
