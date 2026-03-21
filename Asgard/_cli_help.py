"""
Asgard CLI - Comprehensive help text.
"""

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
  asguardian setup-hooks             # Install pre-commit hooks (add --vscode for editor config)
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

  asguardian setup-hooks [--pre-push] [--vscode] [--path <dir>]

  Install pre-commit as a git hook so that linting, formatting, and type
  checks run automatically before bad code reaches a reviewer.

    --pre-push   Also add a pre-push hook (catches issues before git push).
    --vscode     Write .vscode/settings.json + extensions.json so the editor
                 runs ruff format-on-save and recommends the right extensions.
    --path <dir> Target project root (defaults to current directory).

  Requires pre-commit to be installed: pip install pre-commit
  The project must already have a .pre-commit-config.yaml file.

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
