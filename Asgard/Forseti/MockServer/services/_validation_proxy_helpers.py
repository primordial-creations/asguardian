"""
Validation Proxy Helpers - path-template matching for `forseti mock proxy` (plan 06-B.2).

Pure, stdlib-only helpers so the proxy's routing logic is testable without
binding a real socket.
"""

import re
from typing import Optional
from urllib.parse import urlsplit

from Asgard.Forseti.LiveContract.models.live_contract_models import ProbeOperation

_PARAM_RE = re.compile(r"\{([^/{}]+)\}")


def path_template_to_regex(template: str) -> re.Pattern:
    """Convert an OpenAPI path template (`/users/{id}`) into a matching regex."""
    escaped = re.escape(template)
    # re.escape turns `{` and `}` into `\{`/`\}`; undo that before substituting.
    escaped = escaped.replace(r"\{", "{").replace(r"\}", "}")
    pattern = _PARAM_RE.sub(lambda m: f"(?P<{re.sub(r'[^A-Za-z0-9_]', '_', m.group(1))}>[^/]+)", escaped)
    return re.compile(f"^{pattern}$")


def match_operation(
    operations: list[ProbeOperation], method: str, raw_path: str
) -> Optional[ProbeOperation]:
    """Find the ProbeOperation matching an incoming request's method + path.

    Exact (non-templated) paths are preferred over templated ones when both
    would match, so `/users/active` beats `/users/{id}`.
    """
    path = urlsplit(raw_path).path
    method_upper = method.upper()
    candidates = [op for op in operations if op.method.upper() == method_upper]

    literal_matches = [op for op in candidates if "{" not in op.path and op.path == path]
    if literal_matches:
        return literal_matches[0]

    templated = [op for op in candidates if "{" in op.path]
    for op in templated:
        if path_template_to_regex(op.path).match(path):
            return op
    return None
