"""Intra-function taint engine.

Performs a linear scan of a single function body tracking tainted variables
from source patterns through propagators to sinks.

Limitations: intra-function only; inter-function flows and aliasing are not tracked.
"""

import re
from dataclasses import dataclass, field

from Asgard.Heimdall.Quality.services.taint._taint_models import TaintPath
from Asgard.Heimdall.Quality.services.taint._catalogues import CATALOGUES


@dataclass
class _CompiledCatalogue:
    sources: list
    propagators: list
    sinks: list
    sanitizer_pattern: re.Pattern


def _compile(language: str) -> _CompiledCatalogue:
    cat = CATALOGUES.get(language, CATALOGUES["python"])
    sanitizer_re = re.compile(
        r"\b(" + "|".join(re.escape(s) for s in cat["sanitizers"]) + r")\s*\(",
        re.IGNORECASE,
    )
    return _CompiledCatalogue(
        sources=[(p, re.compile(p, re.IGNORECASE)) for p in cat["sources"]],
        propagators=[(p, re.compile(p, re.IGNORECASE)) for p in cat["propagators"]],
        sinks=[(p, re.compile(p, re.IGNORECASE)) for p in cat["sinks"]],
        sanitizer_pattern=sanitizer_re,
    )


def _extract_vars_from_line(line: str) -> list[str]:
    """Return all bare identifiers (including PHP $-vars) present on the line."""
    return re.findall(r"\$?\b[a-zA-Z_]\w*\b", line)


class TaintEngine:
    """
    Walks a function body line-by-line to detect source→sink taint flows.

    No control-flow graph is built; this is a best-effort linear analysis.
    """

    def analyze_function(
        self,
        source_text: str,
        language: str,
        function_node_text: str = "",
    ) -> list[TaintPath]:
        """Analyse one function body and return all discovered taint paths."""
        text = function_node_text if function_node_text else source_text
        lines = text.splitlines()
        compiled = _compile(language)

        # variable → (confidence, source_line_number, source_pattern)
        taint_vars: dict[str, tuple[float, int, str]] = {}
        paths: list[TaintPath] = []

        for lineno, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line or line.startswith(("#", "//", "/*", "*")):
                continue

            # Sanitizer calls kill taint for variables passed to them — we
            # conservatively untaint any variable that appears as an argument
            # to a known sanitizer on this line.
            if compiled.sanitizer_pattern.search(line):
                # Find the variable immediately after the sanitizer call and
                # remove it; also mark any lhs that captures the result.
                lhs_match = re.match(r"\$?\b(\w+)\b\s*(?:=|:=)", line)
                if lhs_match:
                    taint_vars.pop(lhs_match.group(1), None)
                    taint_vars.pop("$" + lhs_match.group(1), None)
                continue

            # --- Source detection ---
            for src_pattern, src_re in compiled.sources:
                m = src_re.search(line)
                if m:
                    var = m.group(1)
                    taint_vars[var] = (1.0, lineno, src_pattern)

            # --- Propagator detection ---
            for prop_pattern, prop_re in compiled.propagators:
                m = prop_re.search(line)
                if m:
                    groups = [g for g in m.groups() if g]
                    if len(groups) < 2:
                        continue
                    lhs = groups[0]
                    # Any group after the first is a potential RHS variable
                    rhs_vars = groups[1:]
                    max_conf = max(
                        (taint_vars[v][0] for v in rhs_vars if v in taint_vars),
                        default=0.0,
                    )
                    if max_conf > 0:
                        best_rhs = max(
                            (v for v in rhs_vars if v in taint_vars),
                            key=lambda v: taint_vars[v][0],
                        )
                        src_lineno, src_pat = taint_vars[best_rhs][1], taint_vars[best_rhs][2]
                        new_conf = max_conf * 0.9
                        existing = taint_vars.get(lhs)
                        if existing is None or new_conf > existing[0]:
                            taint_vars[lhs] = (new_conf, src_lineno, src_pat)

            # --- Sink detection ---
            for sink_pattern, sink_re in compiled.sinks:
                m = sink_re.search(line)
                if m:
                    # Check all identifiers on this line against taint_vars
                    all_vars = _extract_vars_from_line(line)
                    for var in all_vars:
                        if var in taint_vars:
                            conf, src_lineno, src_pat = taint_vars[var]
                            paths.append(TaintPath(
                                source_line=src_lineno,
                                sink_line=lineno,
                                variable=var,
                                confidence=conf,
                                source_pattern=src_pat,
                                sink_pattern=sink_pattern,
                                language=language,
                            ))
                    break  # one sink match per line is enough

        return paths
