"""
L0 Unit Tests for Volundr CLI

Tests the command-line interface argument parsing and routing.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import argparse
import sys

from Asgard.Volundr.cli import (
    create_parser,
    main,
)


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestCLIParserCreation:
    """Test CLI parser creation"""

    def test_create_parser_returns_parser(self):
        """Test that create_parser returns ArgumentParser"""
        parser = create_parser()

        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog == "volundr"

    def test_parser_has_version_flag(self):
        """Test that parser has version flag"""
        parser = create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(['--version'])

    def test_parser_has_common_flags(self):
        """Test that parser has common flags"""
        parser = create_parser()

        args = parser.parse_args(['kubernetes', 'generate', '--name', 'test', '--image', 'nginx', '--format', 'json'])

        assert hasattr(args, 'format')
        assert args.format == 'json'

    def test_parser_dry_run_flag(self):
        """--dry-run is a global flag and must come before the subcommand."""
        parser = create_parser()

        args = parser.parse_args(['--dry-run', 'kubernetes', 'generate', '--name', 'test', '--image', 'nginx'])

        assert hasattr(args, 'dry_run')
        assert args.dry_run is True

    def test_parser_output_flag(self):
        """-o is a global flag and must come before the subcommand."""
        parser = create_parser()

        args = parser.parse_args(['-o', '/tmp/out', 'kubernetes', 'generate', '--name', 'test', '--image', 'nginx'])

        assert hasattr(args, 'output')
        assert args.output == '/tmp/out'


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestCLIKubernetesCommands:
    """Test Kubernetes CLI commands"""

    def test_kubernetes_command_exists(self):
        """Test kubernetes command exists"""
        parser = create_parser()

        args = parser.parse_args(['kubernetes', 'generate', '--name', 'test', '--image', 'nginx'])

        assert args.command == 'kubernetes'
        assert args.k8s_command == 'generate'

    def test_kubernetes_alias_works(self):
        """Test k8s alias for kubernetes"""
        parser = create_parser()

        args = parser.parse_args(['k8s', 'generate', '--name', 'test', '--image', 'nginx'])

        assert args.command == 'k8s'

    def test_kubernetes_generate_required_args(self):
        """Test kubernetes generate requires name and image"""
        parser = create_parser()

        args = parser.parse_args(['kubernetes', 'generate', '--name', 'myapp', '--image', 'nginx:latest'])

        assert args.name == 'myapp'
        assert args.image == 'nginx:latest'

    def test_kubernetes_generate_optional_args(self):
        """Test kubernetes generate accepts optional arguments"""
        parser = create_parser()

        args = parser.parse_args([
            'kubernetes', 'generate',
            '--name', 'myapp',
            '--image', 'nginx',
            '--namespace', 'production',
            '--replicas', '3',
            '--port', '8080'
        ])

        assert args.namespace == 'production'
        assert args.replicas == 3
        assert args.port == 8080


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestCLITerraformCommands:
    """Test Terraform CLI commands"""

    def test_terraform_command_exists(self):
        """Test terraform command exists"""
        parser = create_parser()

        args = parser.parse_args([
            'terraform', 'generate',
            '--name', 'test-module',
            '--provider', 'aws',
            '--category', 'compute'
        ])

        assert args.command == 'terraform'
        assert args.tf_command == 'generate'

    def test_terraform_alias_works(self):
        """Test tf alias for terraform"""
        parser = create_parser()

        args = parser.parse_args([
            'tf', 'generate',
            '--name', 'test',
            '--provider', 'aws',
            '--category', 'compute'
        ])

        assert args.command == 'tf'

    def test_terraform_generate_required_args(self):
        """Test terraform generate requires name, provider, category"""
        parser = create_parser()

        args = parser.parse_args([
            'terraform', 'generate',
            '--name', 'vpc-module',
            '--provider', 'aws',
            '--category', 'networking'
        ])

        assert args.name == 'vpc-module'
        assert args.provider == 'aws'
        assert args.category == 'networking'


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestCLIDockerCommands:
    """Test Docker CLI commands"""

    def test_docker_dockerfile_command(self):
        """Test docker dockerfile command"""
        parser = create_parser()

        args = parser.parse_args([
            'docker', 'dockerfile',
            '--name', 'myapp',
            '--base', 'python:3.12-slim'
        ])

        assert args.command == 'docker'
        assert args.docker_command == 'dockerfile'
        assert args.name == 'myapp'
        assert args.base == 'python:3.12-slim'

    def test_docker_compose_command(self):
        """Test docker compose command"""
        parser = create_parser()

        args = parser.parse_args([
            'docker', 'compose',
            '--name', 'myproject',
            '--services', 'web', 'api', 'db'
        ])

        assert args.docker_command == 'compose'
        assert args.name == 'myproject'
        assert args.services == ['web', 'api', 'db']

    def test_docker_dockerfile_multi_stage_flag(self):
        """Test docker dockerfile multi-stage flag"""
        parser = create_parser()

        args = parser.parse_args([
            'docker', 'dockerfile',
            '--name', 'app',
            '--base', 'python:3.12',
            '--multi-stage'
        ])

        assert args.multi_stage is True


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestCLICICDCommands:
    """Test CI/CD CLI commands"""

    def test_cicd_generate_command(self):
        """Test cicd generate command"""
        parser = create_parser()

        args = parser.parse_args([
            'cicd', 'generate',
            '--name', 'build-deploy',
            '--platform', 'github_actions'
        ])

        assert args.command == 'cicd'
        assert args.cicd_command == 'generate'
        assert args.name == 'build-deploy'
        assert args.platform == 'github_actions'

    def test_cicd_with_docker_image(self):
        """Test cicd generate with docker image"""
        parser = create_parser()

        args = parser.parse_args([
            'cicd', 'generate',
            '--name', 'pipeline',
            '--docker-image', 'ghcr.io/org/app:latest'
        ])

        assert args.docker_image == 'ghcr.io/org/app:latest'


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestCLIHelmCommands:
    """Test Helm CLI commands"""

    def test_helm_init_command(self):
        """Test helm init command"""
        parser = create_parser()

        args = parser.parse_args([
            'helm', 'init',
            'mychart',
            '--image', 'nginx'
        ])

        assert args.command == 'helm'
        assert args.helm_command == 'init'
        assert args.name == 'mychart'
        assert args.image == 'nginx'

    def test_helm_values_command(self):
        """Test helm values command"""
        parser = create_parser()

        args = parser.parse_args([
            'helm', 'values',
            'mychart',
            '--image', 'nginx',
            '--environment', 'production'
        ])

        assert args.helm_command == 'values'
        assert args.chart == 'mychart'
        assert args.environment == 'production'


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestCLIScaffoldCommands:
    """Test Scaffold CLI commands"""

    def test_scaffold_microservice_command(self):
        """Test scaffold microservice command"""
        parser = create_parser()

        args = parser.parse_args([
            'scaffold', 'microservice',
            'myservice',
            '--language', 'python',
            '--framework', 'fastapi'
        ])

        assert args.command == 'scaffold'
        assert args.scaffold_command == 'microservice'
        assert args.name == 'myservice'
        assert args.language == 'python'
        assert args.framework == 'fastapi'

    def test_scaffold_monorepo_command(self):
        """Test scaffold monorepo command"""
        parser = create_parser()

        args = parser.parse_args([
            'scaffold', 'monorepo',
            'myproject',
            '--services', 'api', 'worker', 'frontend',
            '--language', 'typescript'
        ])

        assert args.scaffold_command == 'monorepo'
        assert args.name == 'myproject'
        assert args.services == ['api', 'worker', 'frontend']
        assert args.language == 'typescript'


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestCLIValidateCommands:
    """Test Validate CLI commands"""

    def test_validate_kubernetes_command(self):
        """Test validate kubernetes command"""
        parser = create_parser()

        args = parser.parse_args([
            'validate', 'kubernetes',
            './manifests'
        ])

        assert args.command == 'validate'
        assert args.validate_command == 'kubernetes'
        assert args.path == './manifests'

    def test_validate_terraform_command(self):
        """Test validate terraform command"""
        parser = create_parser()

        args = parser.parse_args([
            'validate', 'terraform',
            './modules'
        ])

        assert args.validate_command == 'terraform'
        assert args.path == './modules'

    def test_validate_dockerfile_command(self):
        """Test validate dockerfile command"""
        parser = create_parser()

        args = parser.parse_args([
            'validate', 'dockerfile',
            './Dockerfile'
        ])

        assert args.validate_command == 'dockerfile'
        assert args.path == './Dockerfile'


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestCLIMainFunction:
    """Test main function routing"""

    def test_main_no_command_shows_help(self):
        """Test main with no command shows help and exits"""
        with patch('sys.argv', ['volundr']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    @patch('Asgard.Volundr.cli.run_kubernetes_generate')
    def test_main_routes_kubernetes_generate(self, mock_run):
        """Test main routes to kubernetes generate handler"""
        mock_run.return_value = 0

        with patch('sys.argv', ['volundr', 'kubernetes', 'generate', '--name', 'test', '--image', 'nginx']):
            with pytest.raises(SystemExit) as exc_info:
                main()

            mock_run.assert_called_once()
            assert exc_info.value.code == 0

    @patch('Asgard.Volundr.cli.run_terraform_generate')
    def test_main_routes_terraform_generate(self, mock_run):
        """Test main routes to terraform generate handler"""
        mock_run.return_value = 0

        with patch('sys.argv', [
            'volundr', 'terraform', 'generate',
            '--name', 'test', '--provider', 'aws', '--category', 'compute'
        ]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            mock_run.assert_called_once()

    @patch('Asgard.Volundr.cli.run_docker_dockerfile')
    def test_main_routes_docker_dockerfile(self, mock_run):
        """Test main routes to docker dockerfile handler"""
        mock_run.return_value = 0

        with patch('sys.argv', [
            'volundr', 'docker', 'dockerfile',
            '--name', 'test', '--base', 'python:3.12-slim'
        ]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            mock_run.assert_called_once()

    @patch('Asgard.Volundr.cli.run_scaffold_microservice')
    def test_main_routes_scaffold_microservice(self, mock_run):
        """Test main routes to scaffold microservice handler"""
        mock_run.return_value = 0

        with patch('sys.argv', [
            'volundr', 'scaffold', 'microservice',
            'test', '--language', 'python'
        ]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            mock_run.assert_called_once()

    def test_main_with_args_parameter(self):
        """Test main can accept args parameter"""
        with pytest.raises(SystemExit):
            main([])


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestCLIEdgeCases:
    """Test CLI edge cases and error handling"""

    def test_parser_handles_missing_required_args(self):
        """Test parser fails gracefully with missing required args"""
        parser = create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(['kubernetes', 'generate', '--name', 'test'])

    def test_parser_handles_invalid_command(self):
        """Test parser handles invalid command"""
        parser = create_parser()

        args = parser.parse_args([])
        assert args.command is None

    def test_main_handles_invalid_command(self):
        """Test main handles invalid top-level command"""
        with patch('sys.argv', ['volundr', 'invalid-command']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            # argparse exits with code 2 when an unknown subcommand is given.
            assert exc_info.value.code == 2

    def test_kubernetes_without_subcommand(self):
        """Test kubernetes command without subcommand prints error"""
        with patch('sys.argv', ['volundr', 'kubernetes']):
            with pytest.raises(SystemExit):
                main()

    def test_docker_without_subcommand(self):
        """Test docker command without subcommand prints error"""
        with patch('sys.argv', ['volundr', 'docker']):
            with pytest.raises(SystemExit):
                main()

    def test_output_flag_sets_output_dir(self):
        """Test that --output flag sets output_dir for commands"""
        parser = create_parser()

        args = parser.parse_args([
            '--output', '/custom/path',
            'kubernetes', 'generate',
            '--name', 'test',
            '--image', 'nginx',
            '--output-dir', '/default/path'
        ])

        assert args.output == '/custom/path'
        assert args.output_dir == '/default/path'
