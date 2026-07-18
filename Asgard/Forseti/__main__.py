"""
Forseti CLI entry point.

This module allows running Forseti as a module:
    python -m Forseti --help
    python -m Forseti openapi validate spec.yaml
    python -m Forseti audit ./api
"""

import sys

from Asgard.Forseti.cli import main

if __name__ == "__main__":
    sys.exit(main())
