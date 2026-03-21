"""
OpenAPI Spec Converter Helpers: Swagger 2.0 to OpenAPI 3.x.
"""

from typing import Any, Callable


def convert_schema_2_to_3(schema: dict[str, Any], recurse_fn: Callable) -> dict[str, Any]:
    """Convert a schema from Swagger 2.0 to OpenAPI 3.0."""
    converted = dict(schema)

    if "$ref" in converted:
        ref = converted["$ref"]
        if ref.startswith("#/definitions/"):
            converted["$ref"] = ref.replace("#/definitions/", "#/components/schemas/")

    for key in ["items", "additionalProperties"]:
        if key in converted and isinstance(converted[key], dict):
            converted[key] = recurse_fn(converted[key])

    if "properties" in converted:
        for prop_name, prop_schema in converted["properties"].items():
            if isinstance(prop_schema, dict):
                converted["properties"][prop_name] = recurse_fn(prop_schema)

    for key in ["allOf", "oneOf", "anyOf"]:
        if key in converted:
            converted[key] = [
                recurse_fn(s) if isinstance(s, dict) else s
                for s in converted[key]
            ]

    return converted


def convert_parameter_2_to_3(param: dict[str, Any]) -> dict[str, Any]:
    """Convert a parameter from Swagger 2.0 to OpenAPI 3.0."""
    converted: dict[str, Any] = {
        "name": param.get("name"),
        "in": param.get("in"),
    }

    if "description" in param:
        converted["description"] = param["description"]
    if "required" in param:
        converted["required"] = param["required"]

    schema: dict[str, Any] = {}
    for key in ["type", "format", "enum", "default", "minimum", "maximum",
                "minLength", "maxLength", "pattern", "items"]:
        if key in param:
            schema[key] = param[key]

    if schema:
        converted["schema"] = schema

    return converted


def convert_operation_2_to_3(
    operation: dict[str, Any],
    convert_schema_fn: Callable,
    convert_param_fn: Callable,
) -> dict[str, Any]:
    """Convert an operation from Swagger 2.0 to OpenAPI 3.0."""
    converted: dict[str, Any] = {
        "responses": {},
    }

    for key in ["operationId", "summary", "description", "tags", "deprecated", "security"]:
        if key in operation:
            converted[key] = operation[key]

    parameters = []
    request_body = None

    for param in operation.get("parameters", []):
        if param.get("in") == "body":
            request_body = {
                "description": param.get("description", ""),
                "required": param.get("required", False),
                "content": {
                    "application/json": {
                        "schema": convert_schema_fn(param.get("schema", {})),
                    }
                }
            }
        elif param.get("in") == "formData":
            if request_body is None:
                consumes = operation.get("consumes", ["application/x-www-form-urlencoded"])
                media_type = consumes[0] if consumes else "application/x-www-form-urlencoded"
                request_body = {
                    "content": {
                        media_type: {
                            "schema": {
                                "type": "object",
                                "properties": {},
                            }
                        }
                    }
                }
            content_type = list(request_body["content"].keys())[0]
            schema = request_body["content"][content_type]["schema"]
            schema["properties"][param["name"]] = {
                "type": param.get("type", "string"),
            }
            if param.get("format"):
                schema["properties"][param["name"]]["format"] = param["format"]
            if param.get("required"):
                if "required" not in schema:
                    schema["required"] = []
                schema["required"].append(param["name"])
        else:
            parameters.append(convert_param_fn(param))

    if parameters:
        converted["parameters"] = parameters
    if request_body:
        converted["requestBody"] = request_body

    produces = operation.get("produces", ["application/json"])
    media_type = produces[0] if produces else "application/json"

    for status_code, response in operation.get("responses", {}).items():
        converted_response = {
            "description": response.get("description", ""),
        }
        if "schema" in response:
            converted_response["content"] = {
                media_type: {
                    "schema": convert_schema_fn(response["schema"]),
                }
            }
        if "headers" in response:
            converted_response["headers"] = response["headers"]
        converted["responses"][status_code] = converted_response

    return converted


def convert_path_item_2_to_3(
    path_item: dict[str, Any],
    convert_operation_fn: Callable,
    convert_param_fn: Callable,
) -> dict[str, Any]:
    """Convert a path item from Swagger 2.0 to OpenAPI 3.0."""
    converted: dict[str, Any] = {}
    http_methods = ["get", "put", "post", "delete", "options", "head", "patch"]

    for method in http_methods:
        if method in path_item:
            converted[method] = convert_operation_fn(path_item[method])

    for key in ["summary", "description"]:
        if key in path_item:
            converted[key] = path_item[key]

    if "parameters" in path_item:
        converted["parameters"] = [
            convert_param_fn(p)
            for p in path_item["parameters"]
            if p.get("in") != "body"
        ]

    return converted


def convert_security_def_2_to_3(sec_def: dict[str, Any]) -> dict[str, Any]:
    """Convert a security definition from Swagger 2.0 to OpenAPI 3.0."""
    sec_type = sec_def.get("type")

    if sec_type == "basic":
        return {
            "type": "http",
            "scheme": "basic",
        }
    elif sec_type == "apiKey":
        return {
            "type": "apiKey",
            "in": sec_def.get("in"),
            "name": sec_def.get("name"),
        }
    elif sec_type == "oauth2":
        flows = {}
        flow_type = sec_def.get("flow")
        flow_data: dict[str, Any] = {
            "scopes": sec_def.get("scopes", {}),
        }
        if "authorizationUrl" in sec_def:
            flow_data["authorizationUrl"] = sec_def["authorizationUrl"]
        if "tokenUrl" in sec_def:
            flow_data["tokenUrl"] = sec_def["tokenUrl"]

        flow_map = {
            "implicit": "implicit",
            "password": "password",
            "application": "clientCredentials",
            "accessCode": "authorizationCode",
        }
        if flow_type in flow_map:
            flows[flow_map[flow_type]] = flow_data

        return {
            "type": "oauth2",
            "flows": flows,
        }

    return sec_def


def convert_2_to_3_0(
    spec_data: dict[str, Any],
    convert_schema_fn: Callable,
    convert_path_item_fn: Callable,
    convert_security_def_fn: Callable,
) -> dict[str, Any]:
    """Convert Swagger 2.0 to OpenAPI 3.0."""
    converted: dict[str, Any] = {
        "openapi": "3.0.3",
        "info": spec_data.get("info", {}),
        "paths": {},
        "components": {
            "schemas": {},
            "securitySchemes": {},
        },
    }

    host = spec_data.get("host", "localhost")
    base_path = spec_data.get("basePath", "/")
    schemes = spec_data.get("schemes", ["https"])
    converted["servers"] = [
        {"url": f"{scheme}://{host}{base_path}"}
        for scheme in schemes
    ]

    definitions = spec_data.get("definitions", {})
    for name, schema in definitions.items():
        converted["components"]["schemas"][name] = convert_schema_fn(schema)

    paths = spec_data.get("paths", {})
    for path, path_item in paths.items():
        converted["paths"][path] = convert_path_item_fn(path_item)

    security_defs = spec_data.get("securityDefinitions", {})
    for name, sec_def in security_defs.items():
        converted["components"]["securitySchemes"][name] = convert_security_def_fn(sec_def)

    if "security" in spec_data:
        converted["security"] = spec_data["security"]

    if "tags" in spec_data:
        converted["tags"] = spec_data["tags"]

    if "externalDocs" in spec_data:
        converted["externalDocs"] = spec_data["externalDocs"]

    return converted


def convert_nullable_to_type_array(obj: Any) -> None:
    """Recursively convert nullable: true to type arrays (3.0 to 3.1)."""
    if isinstance(obj, dict):
        if obj.get("nullable") is True and "type" in obj:
            obj["type"] = [obj["type"], "null"]
            del obj["nullable"]
        for value in obj.values():
            convert_nullable_to_type_array(value)
    elif isinstance(obj, list):
        for item in obj:
            convert_nullable_to_type_array(item)


def convert_exclusive_bounds(obj: Any) -> None:
    """Convert exclusive bounds from boolean to number (3.0 to 3.1)."""
    if isinstance(obj, dict):
        if obj.get("exclusiveMinimum") is True and "minimum" in obj:
            obj["exclusiveMinimum"] = obj.pop("minimum")
        if obj.get("exclusiveMaximum") is True and "maximum" in obj:
            obj["exclusiveMaximum"] = obj.pop("maximum")
        for value in obj.values():
            convert_exclusive_bounds(value)
    elif isinstance(obj, list):
        for item in obj:
            convert_exclusive_bounds(item)
