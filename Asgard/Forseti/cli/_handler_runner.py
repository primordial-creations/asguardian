"""
Handler Runner - shared load -> run -> report -> exit-code logic for CLI handlers.

Exit-code policy (plan 08, uniform across commands):
    2 = input/config error (missing file, unparseable document)
    1 = gate failure (active ERROR findings; or WARNINGs under --strict/ci)
    0 = otherwise

Profiles modulate blocking: 'never' (ide) always exits 0 on findings,
'soft'/'hard' block on errors, 'report' (audit) never blocks.
"""

import argparse
import sys
from typing import Optional, Sequence

from Asgard.Forseti.Reporting.models.finding_models import Finding
from Asgard.Forseti.Reporting.services.reporter_service import select_reporter
from Asgard.Forseti.Rules import RULESET_VERSION
from Asgard.Forseti.Rules.models._rule_base_models import Severity

EXIT_OK = 0
EXIT_GATE_FAILURE = 1
EXIT_INPUT_ERROR = 2


def compute_exit_code(
    findings: Sequence[Finding],
    *,
    strict: bool = False,
    blocking: str = "hard",
    input_error: bool = False,
) -> int:
    """Map findings and gate policy to the uniform 0/1/2 exit codes."""
    if input_error:
        return EXIT_INPUT_ERROR
    if blocking in ("never", "report"):
        return EXIT_OK
    active = [f for f in findings if not f.suppressed]
    if any(f.severity == Severity.ERROR for f in active):
        return EXIT_GATE_FAILURE
    if strict and any(f.severity == Severity.WARNING for f in active):
        return EXIT_GATE_FAILURE
    return EXIT_OK


def wants_unified_output(args: argparse.Namespace) -> bool:
    """Whether the invocation opted into the unified finding pipeline."""
    return bool(
        getattr(args, "format", "text") in ("sarif", "github")
        or getattr(args, "quiet", False)
        or getattr(args, "explain", False)
        or getattr(args, "profile", None)
    )


def run_and_report(
    findings: list[Finding],
    args: argparse.Namespace,
    *,
    rule_metas: Optional[Sequence[object]] = None,
    input_error: bool = False,
    blocking: str = "hard",
) -> int:
    """Render findings with the selected reporter and return the exit code."""
    reporter = select_reporter(
        getattr(args, "format", "text"),
        explain=getattr(args, "explain", False),
        quiet=getattr(args, "quiet", False),
    )
    output = reporter.render(
        findings,
        ruleset_version=RULESET_VERSION,
        rule_metas=rule_metas,
    )
    sys.stdout.write(output + ("\n" if output and not output.endswith("\n") else ""))
    return compute_exit_code(
        findings,
        strict=getattr(args, "strict", False),
        blocking=blocking,
        input_error=input_error,
    )
