"""Tree-sitter S-expression queries for PHP."""

CLASS_DECLARATION = """
(class_declaration name: (name) @class.name) @class.def
"""

METHOD_DECLARATION = """
(method_declaration name: (name) @method.name) @method.def
"""

PUBLIC_METHOD = """
(method_declaration
  (visibility_modifier) @_vis
  (#eq? @_vis "public")
  name: (name) @method.name) @method.def
"""

INTERFACE_DECLARATION = """
(interface_declaration name: (name) @interface.name) @interface.def
"""

TRAIT_DECLARATION = """
(trait_declaration name: (name) @trait.name) @trait.def
"""

NAMESPACE_USE_DECLARATION = """
(namespace_use_declaration) @use
"""

NAMESPACE_DECLARATION = """
(namespace_definition name: (namespace_name) @namespace.name) @namespace.def
"""

OBJECT_CREATION_EXPRESSION = """
(object_creation_expression (named_type (name) @type.name)) @new.expr
"""

FUNCTION_CALL = """
(function_call_expression function: (name) @call.name) @call
"""

METHOD_CALL = """
(method_call_expression name: (name) @call.name) @call.method
"""
