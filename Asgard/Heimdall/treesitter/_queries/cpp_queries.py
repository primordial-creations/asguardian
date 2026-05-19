"""Tree-sitter S-expression queries for C++."""

CLASS_SPECIFIER = """
(class_specifier name: (type_identifier) @class.name) @class.def
"""

STRUCT_SPECIFIER = """
(struct_specifier name: (type_identifier) @struct.name) @struct.def
"""

FUNCTION_DEFINITION = """
(function_definition declarator: (function_declarator
  declarator: (identifier) @func.name)) @func.def
"""

METHOD_DEFINITION = """
(function_definition declarator: (function_declarator
  declarator: (field_identifier) @method.name)) @method.def
"""

CALL_EXPRESSION = """
(call_expression function: (identifier) @call.name) @call
"""

MEMBER_CALL_EXPRESSION = """
(call_expression function: (field_expression field: (field_identifier) @call.name)) @call.member
"""

NEW_EXPRESSION = """
(new_expression type: (type_identifier) @type.name) @new.expr
"""

DECLARATION = """
(declaration declarator: (init_declarator
  declarator: (identifier) @var.name)) @declaration
"""

INCLUDE_DIRECTIVE = """
(preproc_include path: (string_literal) @include.path) @include
"""

NAMESPACE_DEFINITION = """
(namespace_definition name: (identifier) @namespace.name) @namespace.def
"""

TEMPLATE_DECLARATION = """
(template_declaration) @template.def
"""
