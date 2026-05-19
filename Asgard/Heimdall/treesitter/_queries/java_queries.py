"""Tree-sitter S-expression queries for Java."""

CLASS_DEFINITION = """
(class_declaration name: (identifier) @class.name) @class.def
"""

METHOD_DEFINITION = """
(method_declaration name: (identifier) @method.name) @method.def
"""

PUBLIC_METHOD = """
(method_declaration
  (modifiers "public")
  name: (identifier) @method.name) @method.def
"""

INTERFACE_DEFINITION = """
(interface_declaration name: (identifier) @interface.name) @interface.def
"""

INTERFACE_METHOD = """
(interface_declaration
  body: (interface_body
    (method_declaration name: (identifier) @method.name)))
"""

NEW_EXPRESSION = """
(object_creation_expression type: (type_identifier) @type.name) @new.expr
"""

IMPORT_STATEMENT = """
(import_declaration) @import
"""

INSTANCEOF_CHECK = """
(instanceof_expression) @instanceof
"""

TYPE_PATTERN_SWITCH = """
(switch_expression) @switch
"""

STRING_LITERAL = """
(string_literal) @string
"""

FIELD_DECLARATION = """
(field_declaration declarator: (variable_declarator name: (identifier) @field.name)) @field
"""

METHOD_INVOCATION = """
(method_invocation name: (identifier) @call.name) @call
"""
