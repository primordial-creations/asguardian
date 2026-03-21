"""
OpenAPI Spec Generator Helpers.

Helper functions for SpecGeneratorService.
"""

import ast
from pathlib import Path
from typing import Any, Optional, cast


def annotation_to_schema(annotation: ast.expr) -> dict[str, Any]:
    """
    Convert a type annotation to a JSON schema.

    Args:
        annotation: AST annotation node.

    Returns:
        JSON schema dictionary.
    """
    if isinstance(annotation, ast.Name):
        type_name = annotation.id
        type_map = {
            "str": {"type": "string"},
            "int": {"type": "integer"},
            "float": {"type": "number"},
            "bool": {"type": "boolean"},
            "list": {"type": "array"},
            "dict": {"type": "object"},
            "List": {"type": "array"},
            "Dict": {"type": "object"},
        }
        return type_map.get(type_name, {"type": "string"})

    elif isinstance(annotation, ast.Subscript):
        if isinstance(annotation.value, ast.Name):
            container = annotation.value.id
            if container in ["List", "list"]:
                return {
                    "type": "array",
                    "items": annotation_to_schema(annotation.slice),
                }
            elif container == "Optional":
                schema = annotation_to_schema(annotation.slice)
                schema["nullable"] = True
                return schema
            elif container in ["Dict", "dict"]:
                return {"type": "object"}

    return {"type": "string"}


def build_operation(
    func_node: ast.FunctionDef,
    decorator: ast.Call,
) -> dict[str, Any]:
    """
    Build an operation object from function and decorator.

    Args:
        func_node: Function AST node.
        decorator: Decorator AST node.

    Returns:
        Operation dictionary.
    """
    operation: dict[str, Any] = {
        "operationId": func_node.name,
        "responses": {
            "200": {
                "description": "Successful response",
            }
        }
    }

    docstring = ast.get_docstring(func_node)
    if docstring:
        lines = docstring.strip().split("\n")
        operation["summary"] = lines[0]
        if len(lines) > 1:
            operation["description"] = "\n".join(lines[1:]).strip()

    parameters = []
    for arg in func_node.args.args:
        if arg.arg not in ["self", "request", "db", "session"]:
            param: dict[str, Any] = {
                "name": arg.arg,
                "in": "query",
                "required": True,
                "schema": {"type": "string"},
            }

            if arg.annotation:
                param["schema"] = annotation_to_schema(arg.annotation)

            parameters.append(param)

    if parameters:
        operation["parameters"] = parameters

    for keyword in decorator.keywords:
        if keyword.arg == "tags":
            if isinstance(keyword.value, ast.List):
                tags = []
                for elt in keyword.value.elts:
                    if isinstance(elt, ast.Constant):
                        tags.append(elt.value)
                operation["tags"] = tags
        elif keyword.arg == "summary":
            if isinstance(keyword.value, ast.Constant):
                operation["summary"] = keyword.value.value
        elif keyword.arg == "description":
            if isinstance(keyword.value, ast.Constant):
                operation["description"] = keyword.value.value

    return operation


def extract_route_info(
    node: ast.FunctionDef,
) -> Optional[tuple[str, str, dict[str, Any]]]:
    """
    Extract route information from a function definition.

    Args:
        node: AST function definition node.

    Returns:
        Tuple of (path, method, operation) or None.
    """
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Call):
            func = decorator.func
            if isinstance(func, ast.Attribute):
                method = func.attr
                if method in ["get", "post", "put", "delete", "patch", "options", "head"]:
                    if decorator.args:
                        path_arg = decorator.args[0]
                        if isinstance(path_arg, ast.Constant):
                            path = cast(str, path_arg.value)
                            operation = build_operation(node, decorator)
                            return path, method.upper(), operation
    return None


def extract_pydantic_schema(
    node: ast.ClassDef,
) -> Optional[tuple[str, dict[str, Any]]]:
    """
    Extract Pydantic model as JSON schema.

    Args:
        node: AST class definition node.

    Returns:
        Tuple of (name, schema) or None.
    """
    is_pydantic = False
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id in ["BaseModel", "Schema"]:
            is_pydantic = True
            break
        elif isinstance(base, ast.Attribute) and base.attr in ["BaseModel", "Schema"]:
            is_pydantic = True
            break

    if not is_pydantic:
        return None

    schema: dict[str, Any] = {
        "type": "object",
        "properties": {},
    }
    required = []

    docstring = ast.get_docstring(node)
    if docstring:
        schema["description"] = docstring

    for item in node.body:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            field_name = item.target.id
            if field_name.startswith("_"):
                continue

            field_schema = annotation_to_schema(item.annotation)

            if item.value is None:
                required.append(field_name)
            elif isinstance(item.value, ast.Call):
                pass

            schema["properties"][field_name] = field_schema

    if required:
        schema["required"] = required

    return node.name, schema


def analyze_fastapi_file(
    file_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Analyze a FastAPI file for routes and models.

    Args:
        file_path: Path to the Python file.

    Returns:
        Tuple of (paths dict, schemas dict).
    """
    paths: dict[str, Any] = {}
    schemas: dict[str, Any] = {}

    content = file_path.read_text(encoding="utf-8")
    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            route_info = extract_route_info(node)
            if route_info:
                path, method, operation = route_info
                if path not in paths:
                    paths[path] = {}
                paths[path][method.lower()] = operation

        elif isinstance(node, ast.ClassDef):
            schema_info = extract_pydantic_schema(node)
            if schema_info:
                name, schema = schema_info
                schemas[name] = schema

    return paths, schemas
