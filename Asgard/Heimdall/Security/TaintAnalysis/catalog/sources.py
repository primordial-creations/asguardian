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


# --------------------------------------------------------------------------
# JavaScript / TypeScript (Express/Node) -- DEEPTHINK_04 top-level catalogue.
# --------------------------------------------------------------------------
JS_SOURCE_SPECS: Tuple[SourceSpec, ...] = (
    SourceSpec("req.query", TaintSourceType.HTTP_PARAMETER, 1.0),
    SourceSpec("req.body", TaintSourceType.HTTP_PARAMETER, 1.0),
    SourceSpec("req.params", TaintSourceType.PATH_PARAMETER, 1.0),
    SourceSpec("request.query", TaintSourceType.HTTP_PARAMETER, 1.0),
    SourceSpec("request.body", TaintSourceType.HTTP_PARAMETER, 1.0),
    SourceSpec("request.params", TaintSourceType.PATH_PARAMETER, 1.0),
    SourceSpec("req.cookies", TaintSourceType.COOKIE, 1.0),
    SourceSpec("req.headers", TaintSourceType.HEADER, 0.8),
    SourceSpec("req.get", TaintSourceType.HEADER, 0.8, is_call=True),
    SourceSpec("process.env", TaintSourceType.ENV_VAR, 0.8),
    SourceSpec("process.argv", TaintSourceType.COMMAND_LINE_ARG, 1.0),
    SourceSpec("location.search", TaintSourceType.HTTP_PARAMETER, 0.8),
    SourceSpec("location.hash", TaintSourceType.HTTP_PARAMETER, 0.8),
    SourceSpec("window.location", TaintSourceType.HTTP_PARAMETER, 0.6),
    SourceSpec("document.location", TaintSourceType.HTTP_PARAMETER, 0.6),
    SourceSpec("localStorage.getItem", TaintSourceType.USER_INPUT, 0.6, is_call=True),
    SourceSpec("URLSearchParams", TaintSourceType.HTTP_PARAMETER, 0.6),
)

# --------------------------------------------------------------------------
# Java (Servlet/Spring) -- DEEPTHINK_04 top-level catalogue.
# --------------------------------------------------------------------------
JAVA_SOURCE_SPECS: Tuple[SourceSpec, ...] = (
    SourceSpec("request.getParameter", TaintSourceType.HTTP_PARAMETER, 1.0, is_call=True),
    SourceSpec("request.getParameterValues", TaintSourceType.HTTP_PARAMETER, 1.0, is_call=True),
    SourceSpec("request.getQueryString", TaintSourceType.HTTP_PARAMETER, 1.0, is_call=True),
    SourceSpec("request.getHeader", TaintSourceType.HEADER, 0.8, is_call=True),
    SourceSpec("request.getCookies", TaintSourceType.COOKIE, 1.0, is_call=True),
    SourceSpec("request.getInputStream", TaintSourceType.HTTP_PARAMETER, 0.8, is_call=True),
    SourceSpec("request.getReader", TaintSourceType.HTTP_PARAMETER, 0.8, is_call=True),
    SourceSpec("request.getRequestURI", TaintSourceType.HTTP_PARAMETER, 0.8, is_call=True),
    SourceSpec("System.getenv", TaintSourceType.ENV_VAR, 0.8, is_call=True),
    SourceSpec("System.getProperty", TaintSourceType.ENV_VAR, 0.6, is_call=True),
    # Spring MVC-annotated parameters are seeded separately (ROUTE_PARAM_CONFIDENCE)
    # by the CST visitor when a method carries @RequestMapping/@GetMapping/etc.
)


# --------------------------------------------------------------------------
# Go (net/http) -- plan 04 multi-language extension.
# --------------------------------------------------------------------------
GO_SOURCE_SPECS: Tuple[SourceSpec, ...] = (
    SourceSpec("r.URL.Query.Get", TaintSourceType.HTTP_PARAMETER, 1.0, is_call=True),
    SourceSpec("r.URL.Query", TaintSourceType.HTTP_PARAMETER, 0.8),
    SourceSpec("r.FormValue", TaintSourceType.HTTP_PARAMETER, 1.0, is_call=True),
    SourceSpec("r.PostFormValue", TaintSourceType.HTTP_PARAMETER, 1.0, is_call=True),
    SourceSpec("r.Form", TaintSourceType.HTTP_PARAMETER, 0.8),
    SourceSpec("r.PostForm", TaintSourceType.HTTP_PARAMETER, 0.8),
    SourceSpec("r.Header.Get", TaintSourceType.HEADER, 0.8, is_call=True),
    SourceSpec("r.Header", TaintSourceType.HEADER, 0.6),
    SourceSpec("r.Cookie", TaintSourceType.COOKIE, 0.8, is_call=True),
    SourceSpec("r.URL.Path", TaintSourceType.PATH_PARAMETER, 0.8),
    SourceSpec("r.URL.RawQuery", TaintSourceType.HTTP_PARAMETER, 0.8),
    SourceSpec("r.Body", TaintSourceType.HTTP_PARAMETER, 0.6),
    SourceSpec("mux.Vars", TaintSourceType.PATH_PARAMETER, 0.8, is_call=True),
    SourceSpec("os.Getenv", TaintSourceType.ENV_VAR, 0.8, is_call=True),
    SourceSpec("os.LookupEnv", TaintSourceType.ENV_VAR, 0.8, is_call=True),
    SourceSpec("os.Args", TaintSourceType.COMMAND_LINE_ARG, 1.0),
)


# --------------------------------------------------------------------------
# C (libc) -- bounded first pass, intra-procedural only.
#
# HONEST GAP: ``getenv`` is a normal return-value source ("taint the LHS of
# ``x = getenv(...)``"), which this visitor already handles like any other
# call-as-source. But ``fgets``/``scanf``/``read``/``recv``/``gets`` are
# "mutating sources" -- they taint an OUTPUT ARGUMENT (a caller-owned buffer
# pointer), not their return value. The CST visitor's source model is
# call-site/return-value oriented and does not implement argument-mutation
# tainting for C, so these are NOT modeled as sources in this bounded first
# pass. This is a documented false-negative: `char buf[64]; fgets(buf, 64,
# stdin); system(buf);` will NOT be flagged. Left as a known follow-up
# (would need a "call taints its Nth argument, not its return" source
# variant threaded through `_walk`'s call-statement handling).
# --------------------------------------------------------------------------
C_SOURCE_SPECS: Tuple[SourceSpec, ...] = (
    SourceSpec("getenv", TaintSourceType.ENV_VAR, 1.0, is_call=True),
    SourceSpec("secure_getenv", TaintSourceType.ENV_VAR, 1.0, is_call=True),
)


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
