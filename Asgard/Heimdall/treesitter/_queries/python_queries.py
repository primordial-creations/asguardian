"""Tree-sitter S-expression queries for Python."""

CLASS_DEFINITION = """
(class_definition name: (identifier) @class.name) @class.def
"""

FUNCTION_DEFINITION = """
(function_definition name: (identifier) @func.name) @func.def
"""

ASYNC_FUNCTION_DEFINITION = """
(decorated_definition
  definition: (function_definition name: (identifier) @func.name)) @func.decorated
"""

IMPORT_STATEMENT = """
(import_statement) @import
"""

IMPORT_FROM_STATEMENT = """
(import_from_statement) @import.from
"""

IMPORT_FROM_MODULE = """
(import_from_statement module_name: (dotted_name) @import.module) @import.from
"""

CALL = """
(call function: (identifier) @call.name) @call
"""

ATTRIBUTE_CALL = """
(call function: (attribute attribute: (identifier) @call.name)) @call.attr
"""

ASSIGNMENT = """
(assignment left: (identifier) @var.name) @assignment
"""

DECORATED_FUNCTION = """
(decorated_definition
  (decorator) @decorator
  definition: (function_definition name: (identifier) @func.name)) @func.decorated
"""

EXCEPTION_HANDLER = """
(except_clause type: (identifier) @exception.type) @except
"""
