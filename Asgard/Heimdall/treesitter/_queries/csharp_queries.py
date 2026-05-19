"""Tree-sitter S-expression queries for C#."""

CLASS_DECLARATION = """
(class_declaration name: (identifier) @class.name) @class.def
"""

METHOD_DECLARATION = """
(method_declaration name: (identifier) @method.name) @method.def
"""

PUBLIC_METHOD = """
(method_declaration
  (modifier) @_mod
  (#eq? @_mod "public")
  name: (identifier) @method.name) @method.def
"""

INTERFACE_DECLARATION = """
(interface_declaration name: (identifier) @interface.name) @interface.def
"""

RECORD_DECLARATION = """
(record_declaration name: (identifier) @record.name) @record.def
"""

USING_DIRECTIVE = """
(using_directive) @using
"""

NAMESPACE_DECLARATION = """
(namespace_declaration name: (identifier) @namespace.name) @namespace.def
"""

OBJECT_CREATION_EXPRESSION = """
(object_creation_expression type: (identifier) @type.name) @new.expr
"""

IS_PATTERN_EXPRESSION = """
(is_pattern_expression) @is.pattern
"""

PROPERTY_DECLARATION = """
(property_declaration name: (identifier) @property.name) @property.def
"""

LAMBDA_EXPRESSION = """
(lambda_expression) @lambda
"""

ATTRIBUTE = """
(attribute name: (identifier) @attribute.name) @attribute
"""
