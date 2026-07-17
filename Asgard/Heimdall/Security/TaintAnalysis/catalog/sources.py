"""
Taint sources with per-entry confidence (DEEPTHINK_03 s1).

    1.0  exact framework API access (request.args, sys.argv, input())
    0.8  conventional access (request.values, os.environ)
    0.6  heuristic parameter name on a route-decorated function
    0.5  generic suspicious parameter name
"""

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from Asgard.Heimdall.Security.TaintAnalysis.models.taint_models import TaintSourceType


@dataclass(frozen=True)
class SourceSpec:
    """A taint source pattern with the confidence of its identification."""
    pattern: str                    # dotted attribute/call chain prefix
    source_type: TaintSourceType
    confidence: float
    is_call: bool = False           # matches only as a call (e.g. input())


SOURCE_SPECS: Tuple[SourceSpec, ...] = (
    # Exact framework request-data APIs -> 1.0
    SourceSpec("request.args", TaintSourceType.HTTP_PARAMETER, 1.0),
    SourceSpec("request.form", TaintSourceType.HTTP_PARAMETER, 1.0),
    SourceSpec("request.json", TaintSourceType.HTTP_PARAMETER, 1.0),
    SourceSpec("request.data", TaintSourceType.HTTP_PARAMETER, 1.0),
    SourceSpec("request.GET", TaintSourceType.HTTP_PARAMETER, 1.0),
    SourceSpec("request.POST", TaintSourceType.HTTP_PARAMETER, 1.0),
    SourceSpec("request.cookies", TaintSourceType.COOKIE, 1.0),
    # Alias-resolved forms ('from flask import request' canonicalizes the
    # chain to flask.request.*; same for django.http shortcuts).
    SourceSpec("flask.request.args", TaintSourceType.HTTP_PARAMETER, 1.0),
    SourceSpec("flask.request.form", TaintSourceType.HTTP_PARAMETER, 1.0),
    SourceSpec("flask.request.json", TaintSourceType.HTTP_PARAMETER, 1.0),
    SourceSpec("flask.request.data", TaintSourceType.HTTP_PARAMETER, 1.0),
    SourceSpec("flask.request.values", TaintSourceType.HTTP_PARAMETER, 0.8),
    SourceSpec("flask.request.cookies", TaintSourceType.COOKIE, 1.0),
    SourceSpec("flask.request.headers", TaintSourceType.HEADER, 0.8),
    SourceSpec("sys.argv", TaintSourceType.COMMAND_LINE_ARG, 1.0),
    SourceSpec("input", TaintSourceType.USER_INPUT, 1.0, is_call=True),
    # Conventional access -> 0.8
    SourceSpec("request.values", TaintSourceType.HTTP_PARAMETER, 0.8),
    SourceSpec("request.params", TaintSourceType.HTTP_PARAMETER, 0.8),
    SourceSpec("request.headers", TaintSourceType.HEADER, 0.8),
    SourceSpec("os.environ", TaintSourceType.ENV_VAR, 0.8),
    SourceSpec("os.getenv", TaintSourceType.ENV_VAR, 0.8),
    SourceSpec("environ.get", TaintSourceType.ENV_VAR, 0.8),
    SourceSpec("args.parse_args", TaintSourceType.COMMAND_LINE_ARG, 0.8),
    SourceSpec("parser.parse_args", TaintSourceType.COMMAND_LINE_ARG, 0.8),
    SourceSpec("argparse.parse_args", TaintSourceType.COMMAND_LINE_ARG, 0.8),
)

# Confidence assigned to a function parameter treated as a source because the
# enclosing function carries a route decorator (framework stubs supply the
# decorator list). Heuristic per DEEPTHINK_03: 0.6.
ROUTE_PARAM_CONFIDENCE = 0.6


def lookup_source(
    chain: str,
    is_call: bool = False,
    extra_specs: Sequence[SourceSpec] = (),
) -> Optional[SourceSpec]:
    """
    Match a dotted chain against the source catalog.

    ``request.args.get`` matches the ``request.args`` prefix. Call-only
    entries (``input``) match only when the chain is being called.
    """
    for spec in tuple(SOURCE_SPECS) + tuple(extra_specs):
        if spec.is_call and not is_call:
            continue
        if chain == spec.pattern or chain.startswith(spec.pattern + "."):
            return spec
    return None
