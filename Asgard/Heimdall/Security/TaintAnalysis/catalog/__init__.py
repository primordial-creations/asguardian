"""
Taint catalog: sources, sinks, and sanitizers with per-entry confidence.

Replaces the flat name lists in ``_taint_patterns.py`` (which is kept as a
backwards-compatible facade). Every entry carries the confidence the
DEEPTHINK_03 model assigns it; sinks additionally carry keyword-argument
semantics (``shell=False`` drops a flow; ``Loader=SafeLoader`` drops a
yaml.load flow) and sanitizers are a taxonomy, not a boolean.
"""

from Asgard.Heimdall.Security.TaintAnalysis.catalog.sources import (
    SOURCE_SPECS,
    SourceSpec,
    lookup_source,
)
from Asgard.Heimdall.Security.TaintAnalysis.catalog.sinks import (
    SINK_SPECS,
    SinkSpec,
    lookup_sink,
)
from Asgard.Heimdall.Security.TaintAnalysis.catalog.sanitizers import (
    EXACT_SANITIZERS,
    HEURISTIC_SANITIZER_FACTOR,
    SanitizerMatch,
    classify_sanitizer,
)

__all__ = [
    "SOURCE_SPECS", "SourceSpec", "lookup_source",
    "SINK_SPECS", "SinkSpec", "lookup_sink",
    "EXACT_SANITIZERS", "HEURISTIC_SANITIZER_FACTOR",
    "SanitizerMatch", "classify_sanitizer",
]
