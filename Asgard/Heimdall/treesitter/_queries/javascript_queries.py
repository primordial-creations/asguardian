"""Tree-sitter S-expression queries for JavaScript."""

CLASS_DECLARATION = """
(class_declaration name: (identifier) @class.name) @class.def
"""

CLASS_EXPRESSION = """
(class name: (identifier) @class.name) @class.expr
"""

METHOD_DEFINITION = """
(method_definition name: (property_identifier) @method.name) @method.def
"""

FUNCTION_DECLARATION = """
(function_declaration name: (identifier) @func.name) @func.def
"""

ARROW_FUNCTION = """
(arrow_function) @arrow.func
"""

IMPORT_STATEMENT = """
(import_statement) @import
"""

IMPORT_SPECIFIER = """
(import_statement source: (string) @import.source) @import
"""

NEW_EXPRESSION = """
(new_expression constructor: (identifier) @type.name) @new.expr
"""

INSTANCEOF_EXPRESSION = """
(binary_expression operator: "instanceof" right: (identifier) @type.name) @instanceof
"""

CALL_EXPRESSION = """
(call_expression function: (identifier) @call.name) @call
"""

MEMBER_CALL_EXPRESSION = """
(call_expression
  function: (member_expression property: (property_identifier) @call.name)) @call
"""

VARIABLE_DECLARATION = """
(variable_declarator name: (identifier) @var.name) @var.decl
"""
