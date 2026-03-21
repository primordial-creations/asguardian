"""
Golang Generator Helpers.

Type and model generation helper functions for GolangGeneratorService.
"""

from typing import Any, cast

from Asgard.Forseti.CodeGen.models.codegen_models import (
    CodeGenConfig,
    GeneratedFile,
    MethodDefinition,
    ParameterDefinition,
    TargetLanguage,
    TypeDefinition,
)


def json_type_to_go(schema: dict[str, Any], required: bool = True) -> str:
    """Convert JSON Schema type to Go type."""
    if "$ref" in schema:
        type_name = cast(str, schema["$ref"]).split("/")[-1]
        return f"*{type_name}" if not required else type_name

    schema_type = schema.get("type", "interface{}")
    nullable = schema.get("nullable", False)

    if schema_type == "string":
        format_type = schema.get("format")
        base = "time.Time" if format_type in ("date", "date-time") else "string"
        return f"*{base}" if nullable or not required else base

    elif schema_type == "integer":
        format_type = schema.get("format")
        if format_type == "int64":
            base = "int64"
        elif format_type == "int32":
            base = "int32"
        else:
            base = "int"
        return f"*{base}" if nullable or not required else base

    elif schema_type == "number":
        format_type = schema.get("format")
        base = "float32" if format_type == "float" else "float64"
        return f"*{base}" if nullable or not required else base

    elif schema_type == "boolean":
        return "*bool" if nullable or not required else "bool"

    elif schema_type == "array":
        items = schema.get("items", {})
        item_type = json_type_to_go(items, True)
        return f"[]{item_type}"

    elif schema_type == "object":
        if "additionalProperties" in schema:
            value_type = json_type_to_go(schema["additionalProperties"], True)
            return f"map[string]{value_type}"
        return "map[string]interface{}"

    return "interface{}"


def parse_go_parameters(params: list[dict[str, Any]]) -> list[ParameterDefinition]:
    """Parse OpenAPI parameters into ParameterDefinition objects."""
    result: list[ParameterDefinition] = []

    for param in params:
        if not isinstance(param, dict):
            continue

        param_def = ParameterDefinition(
            name=param.get("name", ""),
            location=param.get("in", "query"),
            type_name=json_type_to_go(param.get("schema", {}), param.get("required", False)),
            description=param.get("description"),
            required=param.get("required", False),
            default_value=param.get("schema", {}).get("default"),
        )
        result.append(param_def)

    return result


def generate_go_type(type_def: TypeDefinition, include_documentation: bool, to_pascal_case_fn: Any) -> list[str]:
    """Generate Go code for a type definition."""
    lines: list[str] = []

    if type_def.description and include_documentation:
        lines.append(f"// {type_def.name} {type_def.description}")

    if type_def.is_enum:
        lines.append(f"type {type_def.name} string")
        lines.append("")
        lines.append("const (")
        for value in type_def.enum_values:
            if isinstance(value, str):
                const_name = f"{type_def.name}{value.replace('-', '').replace('_', '').title()}"
                lines.append(f'\t{const_name} {type_def.name} = "{value}"')
            else:
                const_name = f"{type_def.name}{value}"
                lines.append(f"\t{const_name} {type_def.name} = {value}")
        lines.append(")")
    else:
        lines.append(f"type {type_def.name} struct {{")

        for prop_name, prop_def in type_def.properties.items():
            go_name = to_pascal_case_fn(prop_name)
            json_tag = f'`json:"{prop_name},omitempty"`'

            if prop_def.description and include_documentation:
                lines.append(f"\t// {prop_def.description}")

            lines.append(f"\t{go_name} {prop_def.type_name} {json_tag}")

        lines.append("}")

    return lines


def go_operation_to_method(
    path: str,
    http_method: str,
    operation: dict[str, Any],
    path_params: list[ParameterDefinition],
    generate_method_name_fn: Any,
    to_pascal_case_fn: Any,
) -> MethodDefinition:
    """Convert an OpenAPI operation to a MethodDefinition."""
    op_params = parse_go_parameters(operation.get("parameters", []))
    all_params = path_params + op_params

    request_body_type = None
    if "requestBody" in operation:
        content = operation["requestBody"].get("content", {})
        for content_type, media in content.items():
            if "schema" in media:
                request_body_type = json_type_to_go(media["schema"])
                break

    response_type = None
    responses = operation.get("responses", {})
    for status_code in ["200", "201", "default"]:
        if status_code in responses:
            content = responses[status_code].get("content", {})
            for content_type, media in content.items():
                if "schema" in media:
                    response_type = json_type_to_go(media["schema"])
                    break
            if response_type:
                break

    method_name = operation.get("operationId")
    if not method_name:
        method_name = generate_method_name_fn(path, http_method)

    return MethodDefinition(
        name=to_pascal_case_fn(method_name),
        http_method=http_method.upper(),
        path=path,
        description=operation.get("summary") or operation.get("description"),
        parameters=all_params,
        request_body_type=request_body_type,
        response_type=response_type,
        tags=operation.get("tags", []),
        deprecated=operation.get("deprecated", False),
    )


def generate_go_models_file(types: dict[str, TypeDefinition], spec_data: dict[str, Any], config: CodeGenConfig, to_pascal_case_fn: Any) -> GeneratedFile:
    """Generate the models.go file."""
    lines: list[str] = []
    info = spec_data.get("info", {})

    lines.append(f"// {info.get('title', 'API')} - Model Definitions")
    lines.append("//")
    lines.append("// Generated by Forseti CodeGen")
    if info.get("version"):
        lines.append(f"// API Version: {info.get('version')}")
    lines.append("")
    lines.append(f"package {config.package_name}")
    lines.append("")

    needs_time = any(
        "time.Time" in prop_def.type_name
        for type_def in types.values()
        for prop_def in type_def.properties.values()
    )

    if needs_time:
        lines.append('import "time"')
        lines.append("")

    for type_name, type_def in types.items():
        type_code = generate_go_type(type_def, config.include_documentation, to_pascal_case_fn)
        lines.extend(type_code)
        lines.append("")

    content = "\n".join(lines)

    return GeneratedFile(
        path="models.go",
        content=content,
        language=TargetLanguage.GOLANG,
        file_type="models",
        line_count=len(lines),
    )
