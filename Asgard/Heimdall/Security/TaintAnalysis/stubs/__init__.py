"""
Framework stub loader.

Stubs are YAML files modeling framework routing decorators, sources, sinks,
and sanitizers (RESEARCH_02: framework-native modeling is where commercial
taint engines win). Loading is best-effort: a missing file or missing PyYAML
degrades to the core catalog silently.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Sequence, Tuple

from Asgard.Heimdall.Security.TaintAnalysis.catalog.sinks import SinkSpec
from Asgard.Heimdall.Security.TaintAnalysis.catalog.sources import SourceSpec
from Asgard.Heimdall.Security.TaintAnalysis.models.taint_models import (
    TaintSinkType,
    TaintSourceType,
)

_STUB_DIR = Path(__file__).parent


@dataclass
class FrameworkStubs:
    """Merged stub model across the requested frameworks."""
    frameworks: List[str] = field(default_factory=list)
    route_decorators: List[str] = field(default_factory=list)
    source_specs: List[SourceSpec] = field(default_factory=list)
    sink_specs: List[SinkSpec] = field(default_factory=list)
    sanitizer_names: List[str] = field(default_factory=list)  # exact sanitizers


def load_framework_stubs(frameworks: Sequence[str]) -> FrameworkStubs:
    """Load and merge stub YAMLs for the given framework names."""
    merged = FrameworkStubs()
    try:
        import yaml
    except ImportError:
        return merged

    for name in frameworks:
        stub_path = _STUB_DIR / f"{name}.yml"
        if not stub_path.exists():
            continue
        try:
            data = yaml.safe_load(stub_path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        merged.frameworks.append(data.get("framework", name))
        merged.route_decorators.extend(data.get("route_decorators") or [])
        for src in data.get("sources") or []:
            try:
                merged.source_specs.append(SourceSpec(
                    pattern=src["pattern"],
                    source_type=TaintSourceType(src["type"]),
                    confidence=float(src.get("confidence", 0.8)),
                ))
            except (KeyError, ValueError):
                continue
        for sink in data.get("sinks") or []:
            try:
                merged.sink_specs.append(SinkSpec(
                    pattern=sink["pattern"],
                    sink_type=TaintSinkType(sink["type"]),
                    severity=str(sink.get("severity", "high")),
                    confidence=float(sink.get("confidence", 0.8)),
                ))
            except (KeyError, ValueError):
                continue
        for san in data.get("sanitizers") or []:
            pattern = san.get("pattern") if isinstance(san, dict) else san
            if pattern:
                merged.sanitizer_names.append(pattern)
    return merged
