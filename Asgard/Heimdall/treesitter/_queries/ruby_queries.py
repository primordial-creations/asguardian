"""Tree-sitter S-expression queries for Ruby."""

CLASS_DEFINITION = """
(class name: (constant) @class.name) @class.def
"""

MODULE_DEFINITION = """
(module name: (constant) @module.name) @module.def
"""

METHOD_DEFINITION = """
(method name: (identifier) @method.name) @method.def
"""

SINGLETON_METHOD = """
(singleton_method name: (identifier) @method.name) @method.singleton
"""

REQUIRE = """
(call method: (identifier) @_method
  (#eq? @_method "require")
  arguments: (argument_list (string) @require.path)) @require
"""

REQUIRE_RELATIVE = """
(call method: (identifier) @_method
  (#eq? @_method "require_relative")
  arguments: (argument_list (string) @require.path)) @require.relative
"""

SEND = """
(call method: (identifier) @call.name) @call
"""

SEND_WITH_RECEIVER = """
(call receiver: (_) object: (identifier) @receiver method: (identifier) @call.name) @call.recv
"""

CONSTANT_ASSIGNMENT = """
(assignment left: (constant) @const.name) @const.assign
"""

ATTR_ACCESSOR = """
(call method: (identifier) @_method
  (#match? @_method "^attr_")
  arguments: (argument_list) @attr.list) @attr.accessor
"""
