"""Tree-sitter S-expression queries for Go."""

TYPE_DECLARATION = """
(type_declaration (type_spec name: (type_identifier) @type.name)) @type.def
"""

STRUCT_DEFINITION = """
(type_declaration
  (type_spec
    name: (type_identifier) @struct.name
    type: (struct_type))) @struct.def
"""

INTERFACE_DEFINITION = """
(type_declaration
  (type_spec
    name: (type_identifier) @interface.name
    type: (interface_type))) @interface.def
"""

METHOD_DECLARATION = """
(method_declaration name: (field_identifier) @method.name) @method.def
"""

FUNCTION_DECLARATION = """
(function_declaration name: (identifier) @func.name) @func.def
"""

IMPORT_DECLARATION = """
(import_declaration) @import
"""

TYPE_SWITCH_STATEMENT = """
(type_switch_statement) @type.switch
"""

COMPOSITE_LITERAL = """
(composite_literal type: (type_identifier) @type.name) @composite.literal
"""

SHORT_VAR_DECLARATION = """
(short_var_declaration left: (expression_list (identifier) @var.name)) @short.var
"""

CALL_EXPRESSION = """
(call_expression function: (selector_expression field: (field_identifier) @call.name)) @call
"""
