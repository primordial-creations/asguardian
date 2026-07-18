"""Multi-language LCOM4 / CBO cohesion & coupling metrics via the CIR.

Per ``_Docs/Planning/Heimdall/05_Cohesion_Coupling.md``: "Multi-language
arrives free once plan 02's CIR exists — LCOM4 needs only
``MethodInfo.all_identifiers ∩ ClassInfo.fields`` and method-call name
intersection." This module is the non-Python counterpart to
``Asgard/Bragi/OOP/services/cohesion_analyzer.py`` /
``coupling_analyzer.py`` (which stay ``ast``-based for Python, the reference
language). It degrades gracefully (returns ``[]``) when tree-sitter or a
CIR builder for the language is unavailable — there is no regex fallback
for cohesion/coupling since no prior implementation existed for these
languages.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from Asgard.Bragi.Architecture.cir.builder import build_file_cir
from Asgard.Bragi.Architecture.cir.models import ClassInfo
from Asgard.Bragi.Architecture.evaluators._lcom4 import lcom4, lcom4_components
from Asgard.Bragi.OOP.services._cohesion_thresholds import (
    CohesionThresholds,
    resolve_thresholds,
)
from Asgard.Bragi.Quality.utilities.file_utils import scan_directory
from Asgard.Shared.common.language_registry import EXTENSION_TO_LANGUAGE

# Suffixes that identify "our own" classes vs. stdlib/framework noise are not
# knowable without a resolved symbol table; CBO here counts every distinct
# instantiated/field-typed name, matching SonarQube S1200's default
# aggressiveness (profile can relax) per plan 05.
#
# Kept as module constants for backward compatibility; callers that want
# profile-driven thresholds should pass a ``CohesionThresholds`` (see
# ``_cohesion_thresholds.py``) into ``metrics_for_class``/``analyze_file``.
CBO_THRESHOLD = 20
LCOM4_THRESHOLD = 1


@dataclass
class CIRClassMetrics:
    """LCOM4/CBO/RFC for a single class extracted via the CIR."""

    class_name: str
    file_path: str
    language: str
    lcom4: int
    lcom4_components: List[Set[str]] = field(default_factory=list)
    cbo: int = 0
    coupled_types: Set[str] = field(default_factory=set)
    rfc: int = 0
    method_count: int = 0
    thresholds: CohesionThresholds = field(default_factory=CohesionThresholds)

    @property
    def is_low_cohesion(self) -> bool:
        return self.lcom4 > self.thresholds.lcom4

    @property
    def is_high_coupling(self) -> bool:
        return self.cbo > self.thresholds.cbo

    @property
    def is_high_rfc(self) -> bool:
        return self.rfc > self.thresholds.rfc

    def explain(self) -> str:
        """``heimdall oop cohesion <path> --explain <Class>``: prints the
        LCOM4 component partition and CBO coupling set for this class."""
        comp_desc = " | ".join(
            "{" + ", ".join(sorted(c)) + "}" for c in self.lcom4_components if c
        )
        return (
            f"{self.class_name}: LCOM4={self.lcom4} ({comp_desc or 'n/a'}); "
            f"CBO={self.cbo} ({', '.join(sorted(self.coupled_types)) or 'none'}); "
            f"RFC={self.rfc}"
        )


def metrics_for_class(cls: ClassInfo, thresholds: Optional[CohesionThresholds] = None) -> CIRClassMetrics:
    """Compute LCOM4/CBO/RFC for a single :class:`ClassInfo`."""
    components = lcom4_components(cls)

    coupled_types: Set[str] = set()
    invoked_methods: Set[str] = set()
    for method in cls.methods:
        coupled_types |= method.instantiations
        coupled_types |= method.param_types
        invoked_methods |= (method.method_calls - {m.name for m in cls.methods})
    coupled_types -= {cls.name}

    rfc = cls.method_count + len(invoked_methods)

    return CIRClassMetrics(
        class_name=cls.name,
        file_path=cls.filepath,
        language=cls.language,
        lcom4=len(components),
        lcom4_components=components,
        cbo=len(coupled_types),
        coupled_types=coupled_types,
        rfc=rfc,
        method_count=cls.method_count,
        thresholds=thresholds or CohesionThresholds(),
    )


def analyze_file(
    file_path: str, source: str, language: str,
    thresholds: Optional[CohesionThresholds] = None,
) -> List[CIRClassMetrics]:
    """Return :class:`CIRClassMetrics` for every class in *file_path*.

    Returns ``[]`` when the language has no CIR builder or tree-sitter is
    unavailable.
    """
    file_info = build_file_cir(file_path, source, language)
    if file_info is None:
        return []
    return [metrics_for_class(cls, thresholds) for cls in file_info.classes]


def explain_class(
    scan_path: Path, class_name: str,
    extensions: Optional[List[str]] = None,
) -> Optional[str]:
    """``heimdall oop cohesion <path> --explain <Class>`` (multi-language
    side): find *class_name* under *scan_path* and return its LCOM4
    component partition / CBO explanation, or ``None`` if not found."""
    for _file_path, metrics_list in analyze_path(scan_path, extensions=extensions).items():
        for m in metrics_list:
            if m.class_name == class_name:
                return m.explain()
    return None


def analyze_path(
    scan_path: Path,
    exclude_patterns: Optional[List[str]] = None,
    extensions: Optional[List[str]] = None,
    thresholds: Optional[CohesionThresholds] = None,
) -> Dict[str, List[CIRClassMetrics]]:
    """Scan *scan_path* for non-Python source files and compute CIR metrics.

    Returns ``{file_path: [CIRClassMetrics, ...]}``. Files/languages without
    a CIR builder are silently skipped (empty result for that file).
    """
    scan_path = Path(scan_path).resolve()
    target_extensions = extensions or [
        ".java", ".js", ".ts", ".jsx", ".tsx",
    ]
    results: Dict[str, List[CIRClassMetrics]] = {}

    for file_path in scan_directory(
        scan_path,
        exclude_patterns=exclude_patterns or [
            "__pycache__", ".git", "node_modules", "build", "dist", "vendor",
        ],
        include_extensions=target_extensions,
    ):
        language = EXTENSION_TO_LANGUAGE.get(file_path.suffix.lower())
        if not language or language == "python":
            continue
        try:
            source = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        metrics = analyze_file(str(file_path), source, language, thresholds)
        if metrics:
            results[str(file_path)] = metrics

    return results
