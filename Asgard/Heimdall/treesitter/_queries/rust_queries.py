"""Tree-sitter S-expression queries for Rust."""

STRUCT_ITEM = """
(struct_item name: (type_identifier) @struct.name) @struct.def
"""

ENUM_ITEM = """
(enum_item name: (type_identifier) @enum.name) @enum.def
"""

IMPL_ITEM = """
(impl_item type: (type_identifier) @impl.type) @impl.def
"""

TRAIT_ITEM = """
(trait_item name: (type_identifier) @trait.name) @trait.def
"""

FUNCTION_ITEM = """
(function_item name: (identifier) @func.name) @func.def
"""

PUBLIC_FUNCTION_ITEM = """
(function_item
  (visibility_modifier)
  name: (identifier) @func.name) @func.pub
"""

USE_DECLARATION = """
(use_declaration) @use
"""

STRUCT_EXPRESSION = """
(struct_expression name: (type_identifier) @type.name) @struct.expr
"""

CALL_EXPRESSION = """
(call_expression function: (identifier) @call.name) @call
"""

METHOD_CALL_EXPRESSION = """
(method_call_expression name: (field_identifier) @call.name) @call.method
"""

UNSAFE = """
(unsafe_block) @unsafe
"""

MACRO_INVOCATION = """
(macro_invocation macro: (identifier) @macro.name) @macro
"""

TYPE_ALIAS = """
(type_item name: (type_identifier) @type.name) @type.alias
"""
