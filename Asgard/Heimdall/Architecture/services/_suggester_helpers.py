"""
Heimdall Pattern Suggester Helpers

Module-level helpers, constants, and class analysis logic extracted from pattern_suggester.py.
"""

import ast
from typing import List, Set

from Asgard.Heimdall.Architecture.models.architecture_models import (
    PatternSuggestion,
    PatternType,
)
from Asgard.Heimdall.Architecture.services._suggester_ast_helpers import (
    concrete_instantiations_in_init,
    count_isinstance,
    count_optional_params,
    get_responsibility_groups,
    has_scattered_notifications,
    max_if_chain,
    snippet_lineno,
)
from Asgard.Heimdall.Architecture.utilities.ast_utils import (
    get_class_methods,
    get_constructor_params,
    get_public_methods,
)


def analyse_class(
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

    if init_method:
        total_params = len(init_method.args.args) - 1
        optional_count = count_optional_params(init_method)
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

    for method in methods:
        chain_len = max_if_chain(method)
        isinstance_count = count_isinstance(method)

        if chain_len >= 4 or isinstance_count >= 3:
            is_visitor = isinstance_count >= 3
            pattern = PatternType.VISITOR if is_visitor else PatternType.STRATEGY
            rationale_parts = [f"`{class_node.name}.{method.name}` contains"]
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
                confidence=0.75,
                benefit=(
                    "Replace the conditional with polymorphism: define an abstract "
                    + ("Visitor" if is_visitor else "Strategy")
                    + " interface and move each branch into a concrete class."
                ),
            ))

    if init_method:
        known_instantiations = concrete_instantiations_in_init(init_method, all_class_names)
        unique_deps = list(dict.fromkeys(known_instantiations))
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

    notification_count = has_scattered_notifications(class_node)
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

    if public_methods:
        responsibility_groups = get_responsibility_groups(public_methods)
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
