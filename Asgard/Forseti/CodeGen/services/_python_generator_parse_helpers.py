"""
Python Generator Parse Helpers.

Parsing helper functions for PythonGeneratorService.
"""

from typing import Any, cast

from Asgard.Forseti.CodeGen.models.codegen_models import (
    MethodDefinition,
    ParameterDefinition,
)


def json_type_to_python(schema: dict[str, Any]) -> str:
    """Convert JSON Schema type to Python type."""
    if "$ref" in schema:
        ref = cast(str, schema["$ref"])
        return ref.split("/")[-1]

    schema_type = schema.get("type", "Any")

    if schema_type == "string":
        format_type = schema.get("format")
        if format_type == "date":
            return "date"
        elif format_type == "date-time":
            return "datetime"
        return "str"
    elif schema_type == "integer":
        return "int"
    elif schema_type == "number":
        return "float"
    elif schema_type == "boolean":
        return "bool"
    elif schema_type == "array":
        items = schema.get("items", {})
        item_type = json_type_to_python(items)
        return f"list[{item_type}]"
    elif schema_type == "object":
        if "additionalProperties" in schema:
            value_type = json_type_to_python(schema["additionalProperties"])
            return f"dict[str, {value_type}]"
        return "dict[str, Any]"
    elif isinstance(schema_type, list):
        py_types = [json_type_to_python({"type": t}) for t in schema_type if t != "null"]
        if "null" in schema_type:
            py_types.append("None")
        return " | ".join(py_types)

    if "oneOf" in schema or "anyOf" in schema:
        variants = schema.get("oneOf") or schema.get("anyOf", [])
        py_types = [json_type_to_python(v) for v in variants]
        return " | ".join(py_types)

    return "Any"


def parse_parameters(params: list[dict[str, Any]]) -> list[ParameterDefinition]:
    """Parse OpenAPI parameters into ParameterDefinition objects."""
    result: list[ParameterDefinition] = []

    for param in params:
        if not isinstance(param, dict):
            continue

        param_def = ParameterDefinition(
            name=param.get("name", ""),
            location=param.get("in", "query"),
            type_name=json_type_to_python(param.get("schema", {})),
            description=param.get("description"),
            required=param.get("required", False),
            default_value=param.get("schema", {}).get("default"),
        )
        result.append(param_def)

    return result


def operation_to_method(
    path: str,
    http_method: str,
    operation: dict[str, Any],
    path_params: list[ParameterDefinition],
    generate_method_name_fn: Any,
    to_snake_case_fn: Any,
) -> MethodDefinition:
    """Convert an OpenAPI operation to a MethodDefinition."""
    op_params = parse_parameters(operation.get("parameters", []))
    all_params = path_params + op_params

    request_body_type = None
    if "requestBody" in operation:
        request_body = operation["requestBody"]
        content = request_body.get("content", {})
        for content_type, media in content.items():
            if "schema" in media:
                request_body_type = json_type_to_python(media["schema"])
                break

    response_type = None
    responses = operation.get("responses", {})
    for status_code in ["200", "201", "default"]:
        if status_code in responses:
            response = responses[status_code]
            content = response.get("content", {})
            for content_type, media in content.items():
                if "schema" in media:
                    response_type = json_type_to_python(media["schema"])
                    break
            if response_type:
                break

    method_name = operation.get("operationId")
    if not method_name:
        method_name = generate_method_name_fn(path, http_method)

    return MethodDefinition(
        name=to_snake_case_fn(method_name),
        http_method=http_method.upper(),
        path=path,
        description=operation.get("summary") or operation.get("description"),
        parameters=all_params,
        request_body_type=request_body_type,
        response_type=response_type,
        tags=operation.get("tags", []),
        deprecated=operation.get("deprecated", False),
    )
