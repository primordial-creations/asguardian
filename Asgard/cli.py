"""
Asgard CLI - Unified command-line interface for development tools.

Usage:
    asguardian <module> [command] [options]
    asguardian init [--format yaml|toml|json]
    asguardian init-backend <folder_name>
    asguardian heimdall analyze <path>
    asguardian freya crawl <url>
    asguardian forseti validate <spec>
    asguardian verdandi metrics <path>
    asguardian volundr generate <type>
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional, cast

from Asgard.BackendInit.service import init_backend
from Asgard.Forseti.cli import main as forseti_main
from Asgard.Freya.cli import main as freya_main
from Asgard.Heimdall.cli import main as heimdall_main
from Asgard.Verdandi.cli import main as verdandi_main
from Asgard.Volundr.cli import main as volundr_main
from Asgard.config.loader import AsgardConfigLoader


def handle_install_browsers(args: argparse.Namespace) -> int:
    """Install Playwright browser binaries required for Freya."""
    browsers = getattr(args, "browsers", ["chromium"])

    print("Installing Playwright browsers for Freya...")
    print(f"Browsers: {', '.join(browsers)}")
    print()

    try:
        cmd = ["playwright", "install"] + browsers
        result = subprocess.run(cmd, check=False)

        if result.returncode == 0:
            print()
            print("Browser installation complete!")
            print("You can now use Freya's browser-based features:")
            print("  asguardian freya performance audit <url>")
            print("  asguardian freya visual capture <url>")
            print("  asguardian freya accessibility audit <url>")
            return 0
        else:
            print(f"Browser installation failed with exit code {result.returncode}")
            return result.returncode

    except FileNotFoundError:
        print("Error: 'playwright' command not found.")
        print("Please ensure Asgard is installed: pip install Asgard")
        return 1
    except Exception as e:
        print(f"Error installing browsers: {e}")
        return 1


COMPREHENSIVE_HELP = """
================================================================================
                         ASGUARDIAN - Universal Development Tools Suite
                                    Version 1.0.0
================================================================================

Asgard is a comprehensive suite of development tools for code quality, testing,
API validation, performance metrics, and infrastructure generation.

--------------------------------------------------------------------------------
                                  QUICK START
--------------------------------------------------------------------------------

  asguardian init                    # Generate configuration file (asgard.yaml)
  asguardian init-backend <folder>   # Scaffold a standard backend project structure
  asguardian install-browsers        # Install Chromium for Freya (run once after install)
  asguardian heimdall quality <path> # Run code quality analysis
  asguardian heimdall security <path> # Run security scanning
  asguardian freya crawl <url>        # Visual regression testing
  asguardian forseti validate <spec>  # API schema validation
  asguardian verdandi web vitals      # Web performance metrics
  asguardian volundr generate k8s     # Generate Kubernetes manifests

================================================================================
                                   MODULES
================================================================================

--------------------------------------------------------------------------------
  INIT - Configuration Management
--------------------------------------------------------------------------------

  asguardian init [--format yaml|toml|json] [--force]

  Generate a default Asgard configuration file in your project root.
  Configuration controls thresholds, excluded paths, and scanner behavior.

  asguardian init-backend <folder_name>

  Scaffold a standard backend project structure inside the named folder.
  Creates: apis/, models/, services/, prompts/, tests/, utilities/,
  coding_standards.md, readme.md, .env, .env.example, and .gitignore.
  Existing files are never overwritten (except .gitignore which is updated
  to ensure .claude, "Claude Team", and .env are excluded).

--------------------------------------------------------------------------------
  HEIMDALL - Code Quality & Security Analysis
--------------------------------------------------------------------------------

  The watchman who guards code quality. Provides static analysis, security
  scanning, and code health metrics.

  QUALITY COMMANDS:
  -----------------
  heimdall quality lazy-imports <path>     Detect imports inside functions
  heimdall quality complexity <path>       Cyclomatic complexity analysis
  heimdall quality coupling <path>         Module coupling detection
  heimdall quality naming <path>           Naming convention violations
  heimdall quality dead-code <path>        Unused code detection
  heimdall quality forbidden-imports <path> Detect forbidden library imports
  heimdall quality datetime <path>         Detect deprecated datetime patterns
  heimdall quality typing <path>           Type annotation coverage analysis

  SECURITY COMMANDS:
  ------------------
  heimdall security scan <path>            Security vulnerability scanning
  heimdall security secrets <path>         Hardcoded secrets detection
  heimdall security sql <path>             SQL injection detection
  heimdall security xss <path>             XSS vulnerability detection

  OOP COMMANDS:
  -------------
  heimdall oop analyze <path>              OOP structure analysis
  heimdall oop inheritance <path>          Inheritance depth analysis
  heimdall oop cohesion <path>             Class cohesion metrics

  COMMON FLAGS:
  -------------
  --format text|json|github                Output format (default: text)
  --exclude <patterns>                     Comma-separated exclude patterns
  --config <path>                          Custom config file path
  --parallel / -P                          Enable parallel processing
  --workers / -W <n>                       Number of parallel workers
  --incremental / -I                       Only scan changed files
  --no-cache                               Disable result caching
  --baseline <path>                        Filter against baseline file

  INIT-LINTER COMMAND:
  --------------------
  heimdall init-linter <path>              Generate linting configs for a project
  heimdall init-linter <path> --type python  Force Python configs only
  heimdall init-linter <path> --type typescript  Force TypeScript configs only
  heimdall init-linter <path> --type both  Generate configs for both languages
  heimdall init-linter <path> --name <pkg> Set the project/package name
  heimdall init-linter <path> --force      Overwrite existing config files

  BASELINE COMMANDS:
  ------------------
  heimdall baseline create <path>          Create baseline from current violations
  heimdall baseline show                   Show baselined entries

--------------------------------------------------------------------------------
  FREYA - Visual & UI Testing
--------------------------------------------------------------------------------

  The goddess of beauty who ensures UI quality through visual testing and
  accessibility validation.

  COMMANDS:
  ---------
  freya crawl <url>                        Crawl site and capture screenshots
  freya compare <baseline> <current>       Compare visual snapshots
  freya accessibility <url>                Run accessibility audit
  freya responsive <url>                   Test responsive breakpoints

  FLAGS:
  ------
  --viewport <width>x<height>              Browser viewport size
  --delay <ms>                             Wait time between captures
  --threshold <percent>                    Diff threshold percentage

--------------------------------------------------------------------------------
  FORSETI - API & Schema Validation
--------------------------------------------------------------------------------

  The god of justice who validates API contracts and schema compliance.

  COMMANDS:
  ---------
  forseti validate <spec>                  Validate OpenAPI/JSON Schema
  forseti compare <old> <new>              Detect breaking changes
  forseti mock <spec>                      Generate mock server from spec
  forseti generate <spec>                  Generate client/server code

  FLAGS:
  ------
  --format openapi|jsonschema              Specification format
  --strict                                 Enable strict validation

--------------------------------------------------------------------------------
  VERDANDI - Runtime Performance Metrics
--------------------------------------------------------------------------------

  The Norn who measures the present moment. Provides performance analysis
  and web vitals calculation.

  WEB COMMANDS:
  -------------
  verdandi web vitals                      Calculate Core Web Vitals ratings
    --lcp <ms>                             Largest Contentful Paint
    --fid <ms>                             First Input Delay
    --cls <score>                          Cumulative Layout Shift
    --inp <ms>                             Interaction to Next Paint
    --ttfb <ms>                            Time to First Byte
    --fcp <ms>                             First Contentful Paint

  ANALYSIS COMMANDS:
  ------------------
  verdandi analyze percentiles --data <values>  Calculate percentile distribution
  verdandi analyze apdex --data <values>        Calculate Apdex score
    --threshold <ms>                            Apdex T threshold (default: 500)
  verdandi analyze sla --data <values>          Check SLA compliance
    --threshold <ms>                            SLA threshold
    --percentile <n>                            Target percentile (default: 95)

  CACHE COMMANDS:
  ---------------
  verdandi cache metrics                   Calculate cache hit rate
    --hits <n>                             Number of cache hits
    --misses <n>                           Number of cache misses
    --hit-latency <ms>                     Average hit latency
    --miss-latency <ms>                    Average miss latency

  COMMON FLAGS:
  -------------
  --format text|json                       Output format
  --verbose / -v                           Verbose output

--------------------------------------------------------------------------------
  VOLUNDR - Infrastructure Generation
--------------------------------------------------------------------------------

  The master smith who forges infrastructure. Generates deployment configs
  and infrastructure code.

  COMMANDS:
  ---------
  volundr generate kubernetes <name>       Generate Kubernetes manifests
  volundr generate docker <name>           Generate Dockerfile
  volundr generate compose <name>          Generate docker-compose.yaml
  volundr generate terraform <name>        Generate Terraform configs
  volundr probe <host>                     Health probe utilities

  FLAGS:
  ------
  --output <dir>                           Output directory
  --template <name>                        Template to use

================================================================================
                              CONFIGURATION
================================================================================

Asgard looks for configuration in the following locations (in order):

  1. Environment variables (ASGARD_*)
  2. CLI flags
  3. asgard.yaml in current directory
  4. pyproject.toml [tool.asguardian] section
  5. .asgardrc (JSON format)
  6. Default values

Run 'asguardian init' to generate a default configuration file.

================================================================================
                              OUTPUT FORMATS
================================================================================

  text     Human-readable output with colors and formatting
  json     Machine-readable JSON output
  github   GitHub Actions workflow commands (::error, ::warning, ::notice)

================================================================================
                                EXAMPLES
================================================================================

  # Initialize configuration
  asguardian init --format yaml

  # Run full quality analysis on a directory
  asguardian heimdall quality lazy-imports ./src --format json

  # Check type annotation coverage
  asguardian heimdall quality typing ./src --threshold 80

  # Scan for security issues
  asguardian heimdall security scan ./src --format github

  # Create a baseline of current violations
  asguardian heimdall baseline create ./src

  # Run analysis excluding baselined issues
  asguardian heimdall quality lazy-imports ./src --baseline .asgard-baseline.json

  # Calculate web performance score
  asguardian verdandi web vitals --lcp 2100 --fid 50 --cls 0.05

  # Check SLA compliance
  asguardian verdandi analyze sla --data "100,150,200,600,800" --threshold 500

  # Generate Kubernetes manifests
  asguardian volundr generate kubernetes myapp --output ./k8s

================================================================================
                              MORE HELP
================================================================================

  asguardian <module> --help           Show help for a specific module
  asguardian heimdall quality --help   Show help for quality commands
  asguardian heimdall security --help  Show help for security commands

================================================================================
"""


def handle_init_backend(args: argparse.Namespace) -> int:
    """Handle the 'init-backend' command to scaffold a backend project."""
    return cast(int, init_backend(args.folder_name))


def handle_init(args: argparse.Namespace) -> int:
    """Handle the 'init' command to generate configuration file."""
    output_format = getattr(args, "format", "yaml")
    output_path = Path.cwd()

    if output_format == "yaml":
        content = AsgardConfigLoader.generate_default_yaml()
        filename = "asgard.yaml"
    elif output_format == "toml":
        content = AsgardConfigLoader.generate_default_toml()
        filename = "pyproject.toml.asguardian"
        print(f"Note: Add the following to your pyproject.toml [tool.asguardian] section:")
    elif output_format == "json":
        content = AsgardConfigLoader.generate_default_json()
        filename = ".asgardrc"
    else:
        print(f"Unknown format: {output_format}")
        return 1

    output_file = output_path / filename

    if output_file.exists() and not getattr(args, "force", False):
        print(f"File {filename} already exists. Use --force to overwrite.")
        return 1

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Created {filename}")
    return 0


def main(args: Optional[list] = None) -> int:
    """Main entry point for the Asgard CLI."""
    parser = argparse.ArgumentParser(
        prog="asguardian",
        description="Asgard - Universal Development Tools Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Subcommands:
  init              Initialize Asgard configuration file
  init-backend      Scaffold a standard backend project structure
  install-browsers  Install Playwright browsers for Freya
  heimdall          Code quality control and static analysis
  freya             Visual and UI testing
  forseti           API and schema specification
  verdandi          Runtime performance metrics
  volundr           Infrastructure generation

Examples:
  asguardian init --format yaml
  asguardian init-backend my_service
  asguardian install-browsers              # Required once for Freya
  asguardian heimdall analyze ./src
  asguardian freya crawl http://localhost:3000
  asguardian forseti validate openapi.yaml
  asguardian verdandi report ./metrics
  asguardian volundr generate kubernetes --name myapp
        """,
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0",
    )

    parser.add_argument(
        "--help-all",
        action="store_true",
        help="Show comprehensive help for all modules and commands",
    )

    subparsers = parser.add_subparsers(
        dest="module",
        title="modules",
        description="Available Asgard modules",
    )

    # Init subcommand
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize Asgard configuration file",
        description="Generate a default Asgard configuration file",
    )
    init_parser.add_argument(
        "--format",
        choices=["yaml", "toml", "json"],
        default="yaml",
        help="Configuration file format (default: yaml)",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing configuration file",
    )

    # Init-backend subcommand
    init_backend_parser = subparsers.add_parser(
        "init-backend",
        help="Scaffold a standard backend project structure",
        description=(
            "Create a new backend project directory with a standard layout: "
            "apis, models, services, prompts, tests, utilities, and supporting files."
        ),
    )
    init_backend_parser.add_argument(
        "folder_name",
        help="Name of the folder to create (or populate if it already exists)",
    )

    # Install-browsers subcommand
    browsers_parser = subparsers.add_parser(
        "install-browsers",
        help="Install Playwright browsers for Freya",
        description="Download and install browser binaries required for Freya's visual testing",
    )
    browsers_parser.add_argument(
        "browsers",
        nargs="*",
        default=["chromium"],
        help="Browsers to install (default: chromium). Options: chromium, firefox, webkit",
    )

    # Heimdall subcommand
    heimdall_parser = subparsers.add_parser(
        "heimdall",
        help="Code quality control and static analysis",
        description="Heimdall - The watchman who guards code quality",
    )
    heimdall_parser.add_argument(
        "heimdall_args",
        nargs=argparse.REMAINDER,
        help="Arguments to pass to heimdall",
    )

    # Freya subcommand
    freya_parser = subparsers.add_parser(
        "freya",
        help="Visual and UI testing",
        description="Freya - The goddess of beauty who ensures UI quality",
    )
    freya_parser.add_argument(
        "freya_args",
        nargs=argparse.REMAINDER,
        help="Arguments to pass to freya",
    )

    # Forseti subcommand
    forseti_parser = subparsers.add_parser(
        "forseti",
        help="API and schema specification",
        description="Forseti - The god of justice who validates contracts",
    )
    forseti_parser.add_argument(
        "forseti_args",
        nargs=argparse.REMAINDER,
        help="Arguments to pass to forseti",
    )

    # Verdandi subcommand
    verdandi_parser = subparsers.add_parser(
        "verdandi",
        help="Runtime performance metrics",
        description="Verdandi - The Norn who measures the present",
    )
    verdandi_parser.add_argument(
        "verdandi_args",
        nargs=argparse.REMAINDER,
        help="Arguments to pass to verdandi",
    )

    # Volundr subcommand
    volundr_parser = subparsers.add_parser(
        "volundr",
        help="Infrastructure generation",
        description="Volundr - The master smith who forges infrastructure",
    )
    volundr_parser.add_argument(
        "volundr_args",
        nargs=argparse.REMAINDER,
        help="Arguments to pass to volundr",
    )

    parsed_args = parser.parse_args(args)

    # Handle --help-all before anything else
    if getattr(parsed_args, "help_all", False):
        print(COMPREHENSIVE_HELP)
        return 0

    if parsed_args.module is None:
        parser.print_help()
        return 0

    # Handle init command directly
    if parsed_args.module == "init":
        return handle_init(parsed_args)

    # Handle init-backend command
    if parsed_args.module == "init-backend":
        return handle_init_backend(parsed_args)

    # Handle install-browsers command
    if parsed_args.module == "install-browsers":
        return handle_install_browsers(parsed_args)

    # Dispatch to the appropriate module CLI
    if parsed_args.module == "heimdall":
        return cast(int, heimdall_main(parsed_args.heimdall_args))

    elif parsed_args.module == "freya":
        return cast(int, freya_main(parsed_args.freya_args))

    elif parsed_args.module == "forseti":
        return cast(int, forseti_main(parsed_args.forseti_args))

    elif parsed_args.module == "verdandi":
        return cast(int, verdandi_main(parsed_args.verdandi_args))

    elif parsed_args.module == "volundr":
        return cast(int, volundr_main(parsed_args.volundr_args))

    return 0


if __name__ == "__main__":
    sys.exit(main())
