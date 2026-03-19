"""
Heimdall Pattern Suggester Service

Analyses Python classes for structural code smells and signals that indicate
a Gang of Four design pattern would improve the design.

This is complementary to PatternDetector (which finds patterns already implemented).
PatternSuggester identifies pattern *candidates* — code that would benefit from
applying a pattern that has not yet been used.

Signal → Pattern mapping:
  Constructor with 5+ optional params           → Builder
  Long if/elif chain (4+) in a method           → Strategy (or Visitor if isinstance-heavy)
  3+ isinstance() checks in one method          → Visitor
  3+ concrete class instantiations in __init__  → Factory Method
  6+ constructor dependencies                   → Facade or Mediator
  Scattered notification/callback calls         → Observer
  God class spanning 3+ responsibility groups   → Facade
"""

import ast
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

from Asgard.Heimdall.Architecture.models.architecture_models import (
    ArchitectureConfig,
    PatternSuggestion,
    PatternSuggestionReport,
    PatternType,
)
from Asgard.Heimdall.Architecture.utilities.ast_utils import (
    extract_classes,
    get_class_methods,
    get_public_methods,
    get_class_bases,
    get_constructor_params,
    is_abstract_class,
    get_abstract_methods,
    get_class_attributes,
)
from Asgard.Heimdall.Quality.utilities.file_utils import scan_directory


# Pattern-name fragments — classes already named after a pattern are skipped
_PATTERN_NAME_FRAGMENTS = frozenset({
    "Factory", "Builder", "Singleton", "Observer", "Strategy", "Command",
    "Adapter", "Facade", "Decorator", "Visitor", "Mediator", "Template",
    "Proxy", "Repository", "Handler", "Manager",
})

# Responsibility prefix groups used for god-class detection
_RESPONSIBILITY_GROUPS: Dict[frozenset, str] = {
    frozenset({"validate", "check", "verify", "assert_"}): "validation",
    frozenset({"create", "build", "make", "generate", "produce"}): "creation",
    frozenset({"parse", "process", "transform", "convert", "encode", "decode"}): "processing",
    frozenset({"save", "load", "read", "write", "store", "persist", "fetch", "delete"}): "persistence",
    frozenset({"send", "receive", "notify", "dispatch", "emit", "publish", "broadcast"}): "communication",
    frozenset({"render", "display", "show", "format", "print", "draw"}): "presentation",
    frozenset({"calculate", "compute", "analyze", "score", "measure", "estimate"}): "computation",
}

# Notification-call prefixes that suggest Observer pattern
_NOTIFICATION_PREFIXES = frozenset({
    "on_", "handle_", "notify_", "dispatch_", "emit_", "trigger_", "fire_",
})


def _snippet_lineno(method: ast.FunctionDef) -> int:
    return method.lineno


def _max_if_chain(method: ast.FunctionDef) -> int:
    """Return the length of the longest if/elif chain in the method."""
    max_chain = 0
    for node in ast.walk(method):
        if isinstance(node, ast.If):
            length = 1
            current = node
            while (
                current.orelse
                and len(current.orelse) == 1
                and isinstance(current.orelse[0], ast.If)
            ):
                length += 1
                current = current.orelse[0]
            max_chain = max(max_chain, length)
    return max_chain


def _count_isinstance(method: ast.FunctionDef) -> int:
    """Count isinstance() calls inside a method."""
    return sum(
        1
        for node in ast.walk(method)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "isinstance"
    )


def _concrete_instantiations_in_init(
    init_method: ast.FunctionDef,
    known_class_names: Set[str],
) -> List[str]:
    """
    Return names of classes directly instantiated inside __init__
    that also exist in the scanned codebase (strong signal).
    """
    seen: List[str] = []
    for node in ast.walk(init_method):
        if isinstance(node, ast.Call):
            name: Optional[str] = None
            if isinstance(node.func, ast.Name) and node.func.id[0].isupper():
                name = node.func.id
            elif isinstance(node.func, ast.Attribute) and node.func.attr[0].isupper():
                name = node.func.attr
            if name and name not in ("True", "False", "None", "super") and name in known_class_names:
                seen.append(name)
    return seen


def _count_optional_params(init_method: ast.FunctionDef) -> int:
    """Return the number of parameters with default values in __init__."""
    return len(init_method.args.defaults) + len(
        [d for d in init_method.args.kw_defaults if d is not None]
    )


def _has_scattered_notifications(class_node: ast.ClassDef) -> int:
    """Count callback/notification calls scattered across the class."""
    count = 0
    for node in ast.walk(class_node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if any(node.func.attr.startswith(p) for p in _NOTIFICATION_PREFIXES):
                count += 1
    return count


def _get_responsibility_groups(methods: List[ast.FunctionDef]) -> Set[str]:
    """Return the set of distinct responsibility groups inferred from method names."""
    groups: Set[str] = set()
    for method in methods:
        if method.name.startswith("_"):
            continue
        first_word = method.name.split("_")[0].lower()
        for word_set, group_name in _RESPONSIBILITY_GROUPS.items():
            if first_word in word_set:
                groups.add(group_name)
                break
    return groups


class PatternSuggester:
    """
    Analyses Python code for structural signals that suggest GoF design pattern candidates.

    Unlike PatternDetector (which reports patterns that ARE implemented),
    PatternSuggester reports code that COULD benefit from applying a pattern.

    Each suggestion includes:
    - The recommended pattern type
    - The class and file where the smell was detected
    - A human-readable rationale explaining why the pattern fits
    - The observable signals (code properties) that triggered the suggestion
    - The expected benefit of applying the pattern
    - A confidence score (0.0–1.0)
    """

    def __init__(self, config: Optional[ArchitectureConfig] = None) -> None:
        self.config = config or ArchitectureConfig()

    def suggest(self, scan_path: Optional[Path] = None) -> PatternSuggestionReport:
        """
        Scan the codebase and return pattern candidate suggestions.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            PatternSuggestionReport with all suggestions.
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start = time.time()
        report = PatternSuggestionReport(scan_path=str(path))

        # Pass 1: collect all class names for cross-file instantiation analysis
        all_class_names: Set[str] = set()
        class_data: Dict[str, Dict] = {}

        for file_path in scan_directory(
            path,
            exclude_patterns=self.config.exclude_patterns,
            include_extensions=self.config.include_extensions,
        ):
            try:
                source = file_path.read_text(encoding="utf-8", errors="ignore")
                classes = extract_classes(source)
                for cls in classes:
                    all_class_names.add(cls.name)
                    class_data[cls.name] = {
                        "node": cls,
                        "file_path": str(file_path),
                    }
            except (SyntaxError, Exception):
                continue

        # Pass 2: analyse each class for pattern candidates
        for class_name, info in class_data.items():
            class_node: ast.ClassDef = info["node"]
            file_path_str: str = info["file_path"]

            # Skip classes whose names already indicate a pattern implementation
            if any(fragment in class_name for fragment in _PATTERN_NAME_FRAGMENTS):
                continue

            # Skip abstract base classes — they ARE part of a pattern (interface role)
            if is_abstract_class(class_node):
                continue

            for suggestion in self._analyse_class(class_node, file_path_str, all_class_names):
                report.add_suggestion(suggestion)

        report.scan_duration_seconds = time.time() - start
        return report

    def _analyse_class(
        self,
        class_node: ast.ClassDef,
        file_path: str,
        all_class_names: Set[str],
    ) -> List[PatternSuggestion]:
        """Analyse a single class and return any pattern suggestions."""
        suggestions: List[PatternSuggestion] = []

        methods = get_class_methods(class_node)
        public_methods = get_public_methods(class_node)
        constructor_params = get_constructor_params(class_node)
        init_method = next((m for m in methods if m.name == "__init__"), None)

        # ── Signal 1: Complex constructor with many optional params → Builder ──
        if init_method:
            total_params = len(init_method.args.args) - 1  # exclude self
            optional_count = _count_optional_params(init_method)
            if optional_count >= 4 and total_params >= 5:
                suggestions.append(PatternSuggestion(
                    pattern_type=PatternType.BUILDER,
                    class_name=class_node.name,
                    file_path=file_path,
                    line_number=class_node.lineno,
                    rationale=(
                        f"`{class_node.name}.__init__` has {total_params} parameters "
                        f"({optional_count} optional). Constructors with many optional "
                        "parameters produce difficult-to-read call sites and force callers "
                        "to understand the full parameter space. The Builder pattern separates "
                        "construction from representation and provides a fluent, self-documenting API."
                    ),
                    signals=[
                        f"{total_params} constructor parameters",
                        f"{optional_count} are optional (have default values)",
                    ],
                    confidence=0.80,
                    benefit=(
                        f"Replace `{class_node.name}(a, b, c, d=..., e=...)` call sites with "
                        f"`{class_node.name}Builder().with_a(v).with_b(v).build()`."
                    ),
                ))

        # ── Signal 2: Long if/elif chains in methods → Strategy or Visitor ────
        for method in methods:
            chain_len = _max_if_chain(method)
            isinstance_count = _count_isinstance(method)

            if chain_len >= 4 or isinstance_count >= 3:
                is_visitor = isinstance_count >= 3
                pattern = PatternType.VISITOR if is_visitor else PatternType.STRATEGY
                confidence = 0.75

                rationale_parts = [
                    f"`{class_node.name}.{method.name}` contains"
                ]
                if chain_len >= 4:
                    rationale_parts.append(f"a {chain_len}-branch if/elif chain")
                if isinstance_count >= 3:
                    rationale_parts.append(f"{isinstance_count} isinstance() checks")

                rationale = (
                    " ".join(rationale_parts) + ". "
                    + (
                        "Multiple isinstance() checks to dispatch behaviour by type are the "
                        "primary signal for the Visitor pattern, which uses double-dispatch to "
                        "eliminate the type-checking chain."
                        if is_visitor else
                        "Long conditional chains that vary behaviour by mode or variant are the "
                        "primary signal for the Strategy pattern, replacing each branch with "
                        "a concrete strategy implementation."
                    )
                )

                suggestions.append(PatternSuggestion(
                    pattern_type=pattern,
                    class_name=class_node.name,
                    file_path=file_path,
                    line_number=method.lineno,
                    rationale=rationale,
                    signals=[
                        *(
                            [f"{chain_len}-branch if/elif chain in `{method.name}`"]
                            if chain_len >= 4 else []
                        ),
                        *(
                            [f"{isinstance_count} isinstance() calls in `{method.name}`"]
                            if isinstance_count >= 3 else []
                        ),
                    ],
                    confidence=confidence,
                    benefit=(
                        "Replace the conditional with polymorphism: define an abstract "
                        + ("Visitor" if is_visitor else "Strategy")
                        + " interface and move each branch into a concrete class."
                    ),
                ))

        # ── Signal 3: Direct instantiation of known classes in __init__ → Factory ─
        if init_method:
            known_instantiations = _concrete_instantiations_in_init(init_method, all_class_names)
            unique_deps = list(dict.fromkeys(known_instantiations))  # preserve order, deduplicate
            if len(unique_deps) >= 3:
                suggestions.append(PatternSuggestion(
                    pattern_type=PatternType.FACTORY,
                    class_name=class_node.name,
                    file_path=file_path,
                    line_number=class_node.lineno,
                    rationale=(
                        f"`{class_node.name}.__init__` directly instantiates "
                        f"{len(unique_deps)} concrete classes: "
                        f"{', '.join(unique_deps[:5])}{'...' if len(unique_deps) > 5 else ''}. "
                        "Direct instantiation couples this class to concrete implementations, "
                        "violating the Dependency Inversion Principle. Factory Method "
                        "or a Dependency Injection container would decouple construction from use."
                    ),
                    signals=[
                        f"Direct `ClassName()` instantiation of: {', '.join(unique_deps[:5])}",
                        "Dependency Inversion Principle (DIP) violation",
                    ],
                    confidence=0.70,
                    benefit=(
                        "Accept dependencies as constructor parameters (DI) or use a Factory "
                        "to create them — making the class testable with mock implementations."
                    ),
                ))

        # ── Signal 4: Many constructor parameters → Facade or Mediator ────────
        if len(constructor_params) >= 6:
            pattern = PatternType.MEDIATOR if len(constructor_params) >= 9 else PatternType.FACADE
            param_preview = ", ".join(constructor_params[:5])
            if len(constructor_params) > 5:
                param_preview += "..."

            suggestions.append(PatternSuggestion(
                pattern_type=pattern,
                class_name=class_node.name,
                file_path=file_path,
                line_number=class_node.lineno,
                rationale=(
                    f"`{class_node.name}` has {len(constructor_params)} constructor dependencies "
                    f"({param_preview}). "
                    + (
                        "This level of coupling suggests the class coordinates too many "
                        "objects — a Mediator centralises inter-object communication, "
                        "reducing the fan-out from each collaborator."
                        if pattern == PatternType.MEDIATOR else
                        "High constructor arity is a strong signal that the class acts as a "
                        "coordinator for many subsystems. A Facade simplifies a complex "
                        "subsystem behind a focused, unified interface."
                    )
                ),
                signals=[
                    f"{len(constructor_params)} constructor dependencies",
                    "High coupling / large parameter list",
                ],
                confidence=0.65,
                benefit=(
                    f"Introduce a {'Mediator' if pattern == PatternType.MEDIATOR else 'Facade'} "
                    "to coordinate the dependencies, reducing this class's coupling."
                ),
            ))

        # ── Signal 5: Scattered notification/callback calls → Observer ────────
        notification_count = _has_scattered_notifications(class_node)
        if notification_count >= 3:
            suggestions.append(PatternSuggestion(
                pattern_type=PatternType.OBSERVER,
                class_name=class_node.name,
                file_path=file_path,
                line_number=class_node.lineno,
                rationale=(
                    f"`{class_node.name}` makes {notification_count} callback/notification "
                    "calls (methods prefixed with `on_`, `handle_`, `notify_`, `dispatch_`, "
                    "etc.) scattered across its methods. This pattern of direct calls to "
                    "listener-style methods is the primary signal for the Observer pattern, "
                    "which decouples notifiers from their listeners."
                ),
                signals=[
                    f"{notification_count} notification/callback calls (on_*, handle_*, notify_*)",
                    "Direct coupling between event source and event handlers",
                ],
                confidence=0.70,
                benefit=(
                    "Replace scattered direct calls with an event/observer system: "
                    "maintain a subscriber list and call `notify_all(event)` once, "
                    "letting each subscriber react independently."
                ),
            ))

        # ── Signal 6: God class spanning multiple responsibility groups → Facade ─
        if public_methods:
            responsibility_groups = _get_responsibility_groups(public_methods)
            if len(responsibility_groups) >= 3 and len(public_methods) >= 8:
                group_list = ", ".join(sorted(responsibility_groups))
                suggestions.append(PatternSuggestion(
                    pattern_type=PatternType.FACADE,
                    class_name=class_node.name,
                    file_path=file_path,
                    line_number=class_node.lineno,
                    rationale=(
                        f"`{class_node.name}` has {len(public_methods)} public methods "
                        f"spanning {len(responsibility_groups)} distinct responsibility "
                        f"groups: {group_list}. This is a God class — a Facade can "
                        "delegate each responsibility group to a dedicated collaborator "
                        "class, producing smaller, focused, more testable units."
                    ),
                    signals=[
                        f"{len(public_methods)} public methods",
                        f"Responsibility groups detected: {group_list}",
                        "Single Responsibility Principle (SRP) violation",
                    ],
                    confidence=0.70,
                    benefit=(
                        "Extract each responsibility group into its own class, then make "
                        f"`{class_node.name}` a Facade that delegates to them."
                    ),
                ))

        return suggestions

    def suggest_for_class(
        self,
        class_source: str,
        class_name: Optional[str] = None,
    ) -> PatternSuggestionReport:
        """
        Suggest patterns for a single class source string (useful for API callers).

        Args:
            class_source: Python source code containing the class.
            class_name: Optional — restrict to a specific class name.

        Returns:
            PatternSuggestionReport with suggestions.
        """
        report = PatternSuggestionReport()
        classes = extract_classes(class_source)
        if class_name:
            classes = [c for c in classes if c.name == class_name]

        all_names = {c.name for c in classes}
        for cls in classes:
            for s in self._analyse_class(cls, "<string>", all_names):
                report.add_suggestion(s)
        return report

    # ── Report generation ─────────────────────────────────────────────────────

    def generate_report(self, result: PatternSuggestionReport, format: str = "text") -> str:
        """Generate a formatted report from a PatternSuggestionReport."""
        if format == "json":
            return self._generate_json_report(result)
        elif format == "markdown":
            return self._generate_markdown_report(result)
        return self._generate_text_report(result)

    def _generate_text_report(self, result: PatternSuggestionReport) -> str:
        lines = []
        lines.append("")
        lines.append("=" * 70)
        lines.append("  HEIMDALL PATTERN CANDIDATE SUGGESTIONS")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"  Scan Path:          {result.scan_path}")
        lines.append(f"  Suggestions Found:  {result.total_suggestions}")
        lines.append(f"  Duration:           {result.scan_duration_seconds:.2f}s")
        lines.append("")

        if not result.suggestions:
            lines.append("  No pattern candidates found.")
            lines.append("  The codebase appears to already apply patterns appropriately,")
            lines.append("  or classes are small enough that patterns are not needed.")
            lines.append("")
            lines.append("=" * 70)
            return "\n".join(lines)

        for pattern_type, suggestions in result.suggestions_by_pattern.items():
            label = pattern_type.value.upper().replace("_", " ")
            lines.append("-" * 70)
            lines.append(f"  {label} PATTERN CANDIDATES  ({len(suggestions)} found)")
            lines.append("-" * 70)
            lines.append("")
            for s in suggestions:
                lines.append(f"  {s.class_name}  (confidence: {s.confidence:.0%})")
                lines.append(f"    File:    {s.file_path}:{s.line_number}")
                lines.append(f"    Why:     {s.rationale}")
                if s.signals:
                    lines.append(f"    Signals: {'; '.join(s.signals)}")
                if s.benefit:
                    lines.append(f"    Benefit: {s.benefit}")
                lines.append("")

        lines.append("=" * 70)
        return "\n".join(lines)

    def _generate_json_report(self, result: PatternSuggestionReport) -> str:
        output = {
            "scan_path": result.scan_path,
            "scanned_at": result.scanned_at.isoformat(),
            "scan_duration_seconds": result.scan_duration_seconds,
            "total_suggestions": result.total_suggestions,
            "suggestions": [
                {
                    "pattern_type": s.pattern_type.value,
                    "class_name": s.class_name,
                    "file_path": s.file_path,
                    "line_number": s.line_number,
                    "confidence": s.confidence,
                    "rationale": s.rationale,
                    "signals": s.signals,
                    "benefit": s.benefit,
                }
                for s in result.suggestions
            ],
        }
        return json.dumps(output, indent=2)

    def _generate_markdown_report(self, result: PatternSuggestionReport) -> str:
        lines = []
        lines.append("# Heimdall Pattern Candidate Suggestions")
        lines.append("")
        lines.append(f"- **Scan Path:** `{result.scan_path}`")
        lines.append(f"- **Scanned At:** {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- **Total Suggestions:** {result.total_suggestions}")
        lines.append("")

        if not result.suggestions:
            lines.append(
                "_No pattern candidates found. The codebase appears to apply patterns "
                "appropriately, or classes are small enough that patterns are not needed._"
            )
            return "\n".join(lines)

        for pattern_type, suggestions in result.suggestions_by_pattern.items():
            lines.append(f"## {pattern_type.value.replace('_', ' ').title()} Candidates")
            lines.append("")
            for s in suggestions:
                lines.append(f"### `{s.class_name}` — {s.confidence:.0%} confidence")
                lines.append("")
                lines.append(f"**File:** `{s.file_path}:{s.line_number}`")
                lines.append("")
                lines.append(f"**Why:** {s.rationale}")
                lines.append("")
                if s.signals:
                    lines.append("**Signals detected:**")
                    for sig in s.signals:
                        lines.append(f"- {sig}")
                    lines.append("")
                if s.benefit:
                    lines.append(f"**Benefit:** {s.benefit}")
                    lines.append("")

        return "\n".join(lines)
