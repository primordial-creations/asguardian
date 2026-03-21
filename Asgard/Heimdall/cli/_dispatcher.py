"""
Heimdall CLI - Command dispatcher.

Routes parsed CLI arguments to the appropriate handler modules.
"""

from Asgard.Heimdall.cli._dispatch_analysis import dispatch_analysis, handles
from Asgard.Heimdall.cli._dispatch_management import dispatch_management


def dispatch(args, verbose: bool) -> None:
    """Route parsed args to the appropriate handler. Calls sys.exit on completion."""
    if handles(args.command):
        dispatch_analysis(args, verbose)
    else:
        dispatch_management(args, verbose)
