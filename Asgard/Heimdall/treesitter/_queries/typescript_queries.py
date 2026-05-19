"""Tree-sitter S-expression queries for TypeScript (extends JavaScript queries)."""

# --- re-export JS queries so callers can import from one place ---
from Asgard.Heimdall.treesitter._queries.javascript_queries import (  # noqa: F401
    CLASS_DECLARATION,
    CLASS_EXPRESSION,
    METHOD_DEFINITION,
    FUNCTION_DECLARATION,
    ARROW_FUNCTION,
    IMPORT_STATEMENT,
    IMPORT_SPECIFIER,
    NEW_EXPRESSION,
    INSTANCEOF_EXPRESSION,
    CALL_EXPRESSION,
    MEMBER_CALL_EXPRESSION,
    VARIABLE_DECLARATION,
)

# --- TypeScript-specific ---

INTERFACE_DECLARATION = """
(interface_declaration name: (type_identifier) @interface.name) @interface.def
"""

TYPE_ALIAS_DECLARATION = """
(type_alias_declaration name: (type_identifier) @type.name) @type.alias
"""

TYPE_ANNOTATION = """
(type_annotation) @type.annotation
"""

TYPE_ASSERTION = """
(as_expression type: (type_identifier) @type.name) @type.assertion
"""

ENUM_DECLARATION = """
(enum_declaration name: (identifier) @enum.name) @enum.def
"""

DECORATOR = """
(decorator) @decorator
"""

ABSTRACT_CLASS = """
(abstract_class_declaration name: (type_identifier) @class.name) @class.abstract
"""
