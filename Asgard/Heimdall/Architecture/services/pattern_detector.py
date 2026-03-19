"""
Heimdall Pattern Detector Service

Detects design patterns in Python code.
"""

import ast
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

from Asgard.Heimdall.Architecture.models.architecture_models import (
    ArchitectureConfig,
    PatternMatch,
    PatternReport,
    PatternType,
)
from Asgard.Heimdall.Architecture.utilities.ast_utils import (
    extract_classes,
    get_class_methods,
    get_class_bases,
    get_class_decorators,
    get_constructor_params,
    is_abstract_class,
    get_abstract_methods,
    get_class_attributes,
)
from Asgard.Heimdall.Quality.utilities.file_utils import scan_directory


class PatternDetector:
    """
    Detects design patterns in Python code.

    Supports detection of:
    - Creational patterns (Singleton, Factory, Builder)
    - Structural patterns (Adapter, Decorator, Facade)
    - Behavioral patterns (Strategy, Observer, Command)
    """

    def __init__(self, config: Optional[ArchitectureConfig] = None):
        """Initialize the pattern detector."""
        self.config = config or ArchitectureConfig()

    def detect(self, scan_path: Optional[Path] = None) -> PatternReport:
        """
        Detect design patterns in the codebase.

        Args:
            scan_path: Root path to scan

        Returns:
            PatternReport with detected patterns
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()
        report = PatternReport(scan_path=str(path))

        # Collect all classes for cross-file analysis
        all_classes: Dict[str, Dict] = {}

        for file_path in scan_directory(
            path,
            exclude_patterns=self.config.exclude_patterns,
            include_extensions=self.config.include_extensions,
        ):
            try:
                source = file_path.read_text(encoding="utf-8", errors="ignore")
                classes = extract_classes(source)

                for class_node in classes:
                    all_classes[class_node.name] = {
                        "node": class_node,
                        "file_path": str(file_path),
                        "source": source,
                    }
            except (SyntaxError, Exception):
                continue

        # Detect patterns
        for class_name, class_info in all_classes.items():
            class_node = class_info["node"]
            file_path = class_info["file_path"]
            source = class_info["source"]

            # Creational patterns
            patterns = []
            patterns.extend(self._detect_singleton(class_node, file_path))
            patterns.extend(self._detect_factory(class_node, file_path, all_classes))
            patterns.extend(self._detect_builder(class_node, file_path))

            # Structural patterns
            patterns.extend(self._detect_adapter(class_node, file_path, all_classes))
            patterns.extend(self._detect_decorator(class_node, file_path, all_classes))
            patterns.extend(self._detect_facade(class_node, file_path))

            # Behavioral patterns
            patterns.extend(self._detect_strategy(class_node, file_path, all_classes))
            patterns.extend(self._detect_observer(class_node, file_path))
            patterns.extend(self._detect_command(class_node, file_path, all_classes))

            for pattern in patterns:
                report.add_pattern(pattern)

        report.scan_duration_seconds = time.time() - start_time
        return report

    def _detect_singleton(
        self,
        class_node: ast.ClassDef,
        file_path: str
    ) -> List[PatternMatch]:
        """Detect Singleton pattern."""
        patterns = []

        methods = get_class_methods(class_node)
        method_names = {m.name for m in methods}
        attributes = get_class_attributes(class_node)

        # Check for typical singleton indicators
        has_instance = "_instance" in attributes or "instance" in attributes
        has_new = "__new__" in method_names
        has_get_instance = "get_instance" in method_names or "getInstance" in method_names

        # Check class attributes for instance
        for node in class_node.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if target.id in ("_instance", "instance"):
                            has_instance = True

        if has_instance and (has_new or has_get_instance):
            confidence = 0.9 if has_new else 0.7

            patterns.append(PatternMatch(
                pattern_type=PatternType.SINGLETON,
                class_name=class_node.name,
                file_path=file_path,
                line_number=class_node.lineno,
                confidence=confidence,
                details="Uses _instance with __new__ or get_instance method",
            ))

        return patterns

    def _detect_factory(
        self,
        class_node: ast.ClassDef,
        file_path: str,
        all_classes: Dict[str, Dict]
    ) -> List[PatternMatch]:
        """Detect Factory pattern."""
        patterns = []

        # Check for factory naming convention
        if "Factory" in class_node.name:
            methods = get_class_methods(class_node)

            # Look for create methods
            create_methods = [
                m for m in methods
                if m.name.startswith(("create", "make", "build", "get"))
                and not m.name.startswith("_")
            ]

            if create_methods:
                patterns.append(PatternMatch(
                    pattern_type=PatternType.FACTORY,
                    class_name=class_node.name,
                    file_path=file_path,
                    line_number=class_node.lineno,
                    confidence=0.85,
                    participants=[m.name for m in create_methods],
                    details=f"Factory class with {len(create_methods)} creation methods",
                ))

        # Check for abstract factory
        if is_abstract_class(class_node) and "Factory" in class_node.name:
            abstract_methods = get_abstract_methods(class_node)
            create_methods = [
                m for m in abstract_methods
                if m.startswith(("create", "make", "build"))
            ]

            if len(create_methods) >= 2:
                patterns.append(PatternMatch(
                    pattern_type=PatternType.ABSTRACT_FACTORY,
                    class_name=class_node.name,
                    file_path=file_path,
                    line_number=class_node.lineno,
                    confidence=0.8,
                    participants=create_methods,
                    details="Abstract factory with multiple creation methods",
                ))

        return patterns

    def _detect_builder(
        self,
        class_node: ast.ClassDef,
        file_path: str
    ) -> List[PatternMatch]:
        """Detect Builder pattern."""
        patterns = []

        # Check for builder naming convention
        if "Builder" in class_node.name:
            methods = get_class_methods(class_node)
            method_names = [m.name for m in methods]

            # Look for fluent interface (methods returning self)
            fluent_methods = []
            for method in methods:
                if method.name.startswith("_"):
                    continue

                # Check if method returns self
                for node in ast.walk(method):
                    if isinstance(node, ast.Return):
                        if isinstance(node.value, ast.Name) and node.value.id == "self":
                            fluent_methods.append(method.name)
                            break

            has_build = "build" in method_names

            if fluent_methods and has_build:
                patterns.append(PatternMatch(
                    pattern_type=PatternType.BUILDER,
                    class_name=class_node.name,
                    file_path=file_path,
                    line_number=class_node.lineno,
                    confidence=0.9,
                    participants=fluent_methods + ["build"],
                    details=f"Builder with {len(fluent_methods)} fluent methods",
                ))

        return patterns

    def _detect_adapter(
        self,
        class_node: ast.ClassDef,
        file_path: str,
        all_classes: Dict[str, Dict]
    ) -> List[PatternMatch]:
        """Detect Adapter pattern."""
        patterns = []

        # Check for adapter naming convention
        if "Adapter" in class_node.name:
            # Check for adaptee in constructor
            params = get_constructor_params(class_node)
            if params:
                patterns.append(PatternMatch(
                    pattern_type=PatternType.ADAPTER,
                    class_name=class_node.name,
                    file_path=file_path,
                    line_number=class_node.lineno,
                    confidence=0.8,
                    participants=params,
                    details=f"Adapter wrapping: {', '.join(params)}",
                ))

        # Check for delegation pattern (wraps another object)
        bases = get_class_bases(class_node)
        if bases:
            methods = get_class_methods(class_node)
            for method in methods:
                if method.name == "__init__":
                    continue

                # Check if method delegates to wrapped object
                for node in ast.walk(method):
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Attribute):
                            if isinstance(node.func.value, ast.Attribute):
                                if isinstance(node.func.value.value, ast.Name):
                                    if node.func.value.value.id == "self":
                                        # self.wrapped.method() pattern
                                        patterns.append(PatternMatch(
                                            pattern_type=PatternType.ADAPTER,
                                            class_name=class_node.name,
                                            file_path=file_path,
                                            line_number=class_node.lineno,
                                            confidence=0.6,
                                            details="Delegates to wrapped object",
                                        ))
                                        break

        return patterns

    def _detect_decorator(
        self,
        class_node: ast.ClassDef,
        file_path: str,
        all_classes: Dict[str, Dict]
    ) -> List[PatternMatch]:
        """Detect Decorator pattern (not Python decorators)."""
        patterns = []

        bases = get_class_bases(class_node)
        if not bases:
            return patterns

        # Check if class has same base and wraps instance of base
        params = get_constructor_params(class_node)

        for base in bases:
            # Check if constructor takes instance of base type
            base_lower = base.lower()
            for param in params:
                if base_lower in param.lower() or "component" in param.lower() or "wrapped" in param.lower():
                    # Likely decorator pattern
                    patterns.append(PatternMatch(
                        pattern_type=PatternType.DECORATOR,
                        class_name=class_node.name,
                        file_path=file_path,
                        line_number=class_node.lineno,
                        confidence=0.75,
                        participants=[base, param],
                        details=f"Decorates {base} via {param}",
                    ))
                    break

        return patterns

    def _detect_facade(
        self,
        class_node: ast.ClassDef,
        file_path: str
    ) -> List[PatternMatch]:
        """Detect Facade pattern."""
        patterns = []

        # Check for facade naming convention
        if "Facade" in class_node.name or "Service" in class_node.name:
            params = get_constructor_params(class_node)

            # Facade typically has multiple dependencies
            if len(params) >= 3:
                patterns.append(PatternMatch(
                    pattern_type=PatternType.FACADE,
                    class_name=class_node.name,
                    file_path=file_path,
                    line_number=class_node.lineno,
                    confidence=0.7,
                    participants=params,
                    details=f"Facade coordinating {len(params)} subsystems",
                ))

        return patterns

    def _detect_strategy(
        self,
        class_node: ast.ClassDef,
        file_path: str,
        all_classes: Dict[str, Dict]
    ) -> List[PatternMatch]:
        """Detect Strategy pattern."""
        patterns = []

        # Check if this is an abstract strategy
        if is_abstract_class(class_node):
            abstract_methods = get_abstract_methods(class_node)

            # Strategy typically has one main abstract method
            if len(abstract_methods) == 1:
                # Find implementations
                implementations = []
                for name, info in all_classes.items():
                    node = info["node"]
                    bases = get_class_bases(node)
                    if class_node.name in bases:
                        implementations.append(name)

                if implementations:
                    patterns.append(PatternMatch(
                        pattern_type=PatternType.STRATEGY,
                        class_name=class_node.name,
                        file_path=file_path,
                        line_number=class_node.lineno,
                        confidence=0.85,
                        participants=implementations,
                        details=f"Strategy interface with {len(implementations)} implementations",
                    ))

        # Check for naming convention
        if "Strategy" in class_node.name:
            patterns.append(PatternMatch(
                pattern_type=PatternType.STRATEGY,
                class_name=class_node.name,
                file_path=file_path,
                line_number=class_node.lineno,
                confidence=0.7,
                details="Named as strategy",
            ))

        return patterns

    def _detect_observer(
        self,
        class_node: ast.ClassDef,
        file_path: str
    ) -> List[PatternMatch]:
        """Detect Observer pattern."""
        patterns = []

        methods = get_class_methods(class_node)
        method_names = {m.name for m in methods}

        # Subject indicators
        has_subscribe = any(
            name in method_names
            for name in ["subscribe", "attach", "add_observer", "register"]
        )
        has_unsubscribe = any(
            name in method_names
            for name in ["unsubscribe", "detach", "remove_observer", "unregister"]
        )
        has_notify = any(
            name in method_names
            for name in ["notify", "notify_observers", "emit", "dispatch"]
        )

        if has_subscribe and has_unsubscribe and has_notify:
            patterns.append(PatternMatch(
                pattern_type=PatternType.OBSERVER,
                class_name=class_node.name,
                file_path=file_path,
                line_number=class_node.lineno,
                confidence=0.9,
                details="Subject with subscribe/unsubscribe/notify methods",
            ))

        # Observer indicators
        has_update = "update" in method_names or "on_notify" in method_names

        if has_update and ("Observer" in class_node.name or "Listener" in class_node.name):
            patterns.append(PatternMatch(
                pattern_type=PatternType.OBSERVER,
                class_name=class_node.name,
                file_path=file_path,
                line_number=class_node.lineno,
                confidence=0.8,
                details="Observer with update method",
            ))

        return patterns

    def _detect_command(
        self,
        class_node: ast.ClassDef,
        file_path: str,
        all_classes: Dict[str, Dict]
    ) -> List[PatternMatch]:
        """Detect Command pattern."""
        patterns = []

        methods = get_class_methods(class_node)
        method_names = {m.name for m in methods}

        # Command indicators
        has_execute = "execute" in method_names or "__call__" in method_names
        has_undo = "undo" in method_names or "rollback" in method_names

        if has_execute:
            confidence = 0.85 if has_undo else 0.65

            # Check if this is a base command
            if is_abstract_class(class_node):
                # Find implementations
                implementations = []
                for name, info in all_classes.items():
                    node = info["node"]
                    bases = get_class_bases(node)
                    if class_node.name in bases:
                        implementations.append(name)

                if implementations:
                    patterns.append(PatternMatch(
                        pattern_type=PatternType.COMMAND,
                        class_name=class_node.name,
                        file_path=file_path,
                        line_number=class_node.lineno,
                        confidence=confidence,
                        participants=implementations,
                        details=f"Command interface with {len(implementations)} commands",
                    ))
            elif "Command" in class_node.name:
                patterns.append(PatternMatch(
                    pattern_type=PatternType.COMMAND,
                    class_name=class_node.name,
                    file_path=file_path,
                    line_number=class_node.lineno,
                    confidence=confidence,
                    details="Concrete command with execute method",
                ))

        return patterns

    def detect_in_class(
        self,
        class_source: str,
        class_name: Optional[str] = None
    ) -> PatternReport:
        """
        Detect patterns in a single class.

        Args:
            class_source: Python source code
            class_name: Optional specific class name

        Returns:
            PatternReport with detected patterns
        """
        report = PatternReport()

        classes = extract_classes(class_source)
        if class_name:
            classes = [c for c in classes if c.name == class_name]

        # Build class info dict for pattern detection
        all_classes = {
            c.name: {
                "node": c,
                "file_path": "<string>",
                "source": class_source,
            }
            for c in classes
        }

        for class_node in classes:
            patterns = []
            patterns.extend(self._detect_singleton(class_node, "<string>"))
            patterns.extend(self._detect_factory(class_node, "<string>", all_classes))
            patterns.extend(self._detect_builder(class_node, "<string>"))
            patterns.extend(self._detect_adapter(class_node, "<string>", all_classes))
            patterns.extend(self._detect_decorator(class_node, "<string>", all_classes))
            patterns.extend(self._detect_facade(class_node, "<string>"))
            patterns.extend(self._detect_strategy(class_node, "<string>", all_classes))
            patterns.extend(self._detect_observer(class_node, "<string>"))
            patterns.extend(self._detect_command(class_node, "<string>", all_classes))

            for pattern in patterns:
                report.add_pattern(pattern)

        return report

    def generate_report(self, result: PatternReport, format: str = "text") -> str:
        """
        Generate a formatted report.

        Args:
            result: PatternReport to format
            format: Output format ("text", "json", "markdown")

        Returns:
            Formatted report string
        """
        if format == "json":
            return self._generate_json_report(result)
        elif format == "markdown":
            return self._generate_markdown_report(result)
        else:
            return self._generate_text_report(result)

    def _generate_text_report(self, result: PatternReport) -> str:
        """Generate text format report."""
        lines = []
        lines.append("")
        lines.append("=" * 70)
        lines.append("  HEIMDALL DESIGN PATTERNS REPORT")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"  Scan Path:       {result.scan_path}")
        lines.append(f"  Patterns Found:  {result.total_patterns}")
        lines.append("")

        for pattern_type, matches in result.patterns_by_type.items():
            if matches:
                lines.append("-" * 70)
                lines.append(f"  {pattern_type.value.upper().replace('_', ' ')}")
                lines.append("-" * 70)
                lines.append("")

                for match in matches:
                    lines.append(f"  {match.class_name}")
                    lines.append(f"    File: {match.file_path}:{match.line_number}")
                    lines.append(f"    Confidence: {match.confidence:.0%}")
                    if match.participants:
                        lines.append(f"    Participants: {', '.join(match.participants)}")
                    if match.details:
                        lines.append(f"    Details: {match.details}")
                    lines.append("")

        lines.append("=" * 70)
        return "\n".join(lines)

    def _generate_json_report(self, result: PatternReport) -> str:
        """Generate JSON format report."""
        output = {
            "scan_path": result.scan_path,
            "scanned_at": result.scanned_at.isoformat(),
            "total_patterns": result.total_patterns,
            "patterns": [
                {
                    "pattern_type": p.pattern_type.value,
                    "class_name": p.class_name,
                    "file_path": p.file_path,
                    "line_number": p.line_number,
                    "confidence": p.confidence,
                    "participants": p.participants,
                    "details": p.details,
                }
                for p in result.patterns
            ],
        }

        return json.dumps(output, indent=2)

    def _generate_markdown_report(self, result: PatternReport) -> str:
        """Generate Markdown format report."""
        lines = []
        lines.append("# Heimdall Design Patterns Report")
        lines.append("")
        lines.append(f"- **Scan Path:** `{result.scan_path}`")
        lines.append(f"- **Patterns Found:** {result.total_patterns}")
        lines.append("")

        for pattern_type, matches in result.patterns_by_type.items():
            if matches:
                lines.append(f"## {pattern_type.value.replace('_', ' ').title()}")
                lines.append("")
                lines.append("| Class | File | Confidence | Details |")
                lines.append("|-------|------|------------|---------|")

                for match in matches:
                    lines.append(
                        f"| {match.class_name} | {match.file_path}:{match.line_number} | "
                        f"{match.confidence:.0%} | {match.details} |"
                    )

                lines.append("")

        return "\n".join(lines)
