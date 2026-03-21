"""
TypeScript Generator Parse Helpers.

Parsing helper functions for TypeScriptGeneratorService.
"""

from typing import Any, cast

from Asgard.Forseti.CodeGen.models.codegen_models import (
    MethodDefinition,
    ParameterDefinition,
    TypeDefinition,
)


def json_type_to_ts(schema: dict[str, Any]) -> str:
    """Convert JSON Schema type to TypeScript type."""
    if "$ref" in schema:
        ref = cast(str, schema["$ref"])
        return ref.split("/")[-1]

    schema_type = schema.get("type", "any")

    if schema_type == "string":
        return "string"
    elif schema_type == "integer" or schema_type == "number":
        return "number"
    elif schema_type == "boolean":
        return "boolean"
    elif schema_type == "array":
        items = schema.get("items", {})
        item_type = json_type_to_ts(items)
        return f"{item_type}[]"
    elif schema_type == "object":
        if "additionalProperties" in schema:
            value_type = json_type_to_ts(schema["additionalProperties"])
            return f"Record<string, {value_type}>"
        return "Record<string, unknown>"
    elif isinstance(schema_type, list):
        ts_types = [json_type_to_ts({"type": t}) for t in schema_type if t != "null"]
        if "null" in schema_type:
            ts_types.append("null")
        return " | ".join(ts_types)

    if "oneOf" in schema or "anyOf" in schema:
        variants = schema.get("oneOf") or schema.get("anyOf", [])
        ts_types = [json_type_to_ts(v) for v in variants]
        return " | ".join(ts_types)

    return "unknown"


def parse_ts_parameters(params: list[dict[str, Any]]) -> list[ParameterDefinition]:
    """Parse OpenAPI parameters into ParameterDefinition objects."""
    result: list[ParameterDefinition] = []

    for param in params:
        if not isinstance(param, dict):
            continue

        param_def = ParameterDefinition(
            name=param.get("name", ""),
            location=param.get("in", "query"),
            type_name=json_type_to_ts(param.get("schema", {})),
            description=param.get("description"),
            required=param.get("required", False),
            default_value=param.get("schema", {}).get("default"),
        )
        result.append(param_def)

    return result


def generate_ts_type_imports(methods: list[MethodDefinition], types: dict[str, TypeDefinition]) -> set[str]:
    """Get the set of types that need to be imported."""
    imports: set[str] = set()

    for method in methods:
        if method.request_body_type and method.request_body_type in types:
            imports.add(method.request_body_type)

        if method.response_type:
            response_type = method.response_type.rstrip("[]")
            if response_type in types:
                imports.add(response_type)

        for param in method.parameters:
            param_type = param.type_name.rstrip("[]")
            if param_type in types:
                imports.add(param_type)

    return imports


def ts_operation_to_method(
    path: str,
    http_method: str,
    operation: dict[str, Any],
    path_params: list[ParameterDefinition],
    generate_method_name_fn: Any,
    to_camel_case_fn: Any,
) -> MethodDefinition:
    """Convert an OpenAPI operation to a MethodDefinition."""
    op_params = parse_ts_parameters(operation.get("parameters", []))
    all_params = path_params + op_params

    request_body_type = None
    if "requestBody" in operation:
        content = operation["requestBody"].get("content", {})
        for content_type, media in content.items():
            if "schema" in media:
                request_body_type = json_type_to_ts(media["schema"])
                break

    response_type = None
    responses = operation.get("responses", {})
    for status_code in ["200", "201", "default"]:
        if status_code in responses:
            content = responses[status_code].get("content", {})
            for content_type, media in content.items():
                if "schema" in media:
                    response_type = json_type_to_ts(media["schema"])
                    break
            if response_type:
                break

    method_name = operation.get("operationId")
    if not method_name:
        method_name = generate_method_name_fn(path, http_method)

    return MethodDefinition(
        name=to_camel_case_fn(method_name),
        http_method=http_method.upper(),
        path=path,
        description=operation.get("summary") or operation.get("description"),
        parameters=all_params,
        request_body_type=request_body_type,
        response_type=response_type,
        tags=operation.get("tags", []),
        deprecated=operation.get("deprecated", False),
    )
