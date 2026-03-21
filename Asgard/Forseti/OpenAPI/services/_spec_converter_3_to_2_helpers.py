"""
OpenAPI Spec Converter Helpers: OpenAPI 3.x to Swagger 2.0.
"""

import re
from typing import Any, Callable


def convert_schema_3_to_2(schema: dict[str, Any], recurse_fn: Callable) -> dict[str, Any]:
    """Convert a schema from OpenAPI 3.0 to Swagger 2.0."""
    converted = dict(schema)

    if "$ref" in converted:
        ref = converted["$ref"]
        if ref.startswith("#/components/schemas/"):
            converted["$ref"] = ref.replace("#/components/schemas/", "#/definitions/")

    converted.pop("nullable", None)

    for key in ["items", "additionalProperties"]:
        if key in converted and isinstance(converted[key], dict):
            converted[key] = recurse_fn(converted[key])

    if "properties" in converted:
        for prop_name, prop_schema in converted["properties"].items():
            if isinstance(prop_schema, dict):
                converted["properties"][prop_name] = recurse_fn(prop_schema)

    return converted


def convert_operation_3_to_2(
    operation: dict[str, Any],
    convert_schema_fn: Callable,
) -> dict[str, Any]:
    """Convert an operation from OpenAPI 3.0 to Swagger 2.0."""
    converted: dict[str, Any] = {
        "responses": {},
    }

    for key in ["operationId", "summary", "description", "tags", "deprecated", "security"]:
        if key in operation:
            converted[key] = operation[key]

    parameters = list(operation.get("parameters", []))

    if "requestBody" in operation:
        req_body = operation["requestBody"]
        content = req_body.get("content", {})
        for media_type, media_content in content.items():
            body_param: dict[str, Any] = {
                "name": "body",
                "in": "body",
                "required": req_body.get("required", False),
                "schema": convert_schema_fn(media_content.get("schema", {})),
            }
            if "description" in req_body:
                body_param["description"] = req_body["description"]
            parameters.append(body_param)
            break

    if parameters:
        converted["parameters"] = parameters

    for status_code, response in operation.get("responses", {}).items():
        converted_response = {
            "description": response.get("description", ""),
        }
        content = response.get("content", {})
        for media_type, media_content in content.items():
            if "schema" in media_content:
                converted_response["schema"] = convert_schema_fn(media_content["schema"])
            break
        converted["responses"][status_code] = converted_response

    return converted


def convert_path_item_3_to_2(
    path_item: dict[str, Any],
    convert_operation_fn: Callable,
) -> dict[str, Any]:
    """Convert a path item from OpenAPI 3.0 to Swagger 2.0."""
    converted: dict[str, Any] = {}
    http_methods = ["get", "put", "post", "delete", "options", "head", "patch"]

    for method in http_methods:
        if method in path_item:
            converted[method] = convert_operation_fn(path_item[method])

    for key in ["summary", "description", "parameters"]:
        if key in path_item:
            converted[key] = path_item[key]

    return converted


def convert_security_scheme_3_to_2(sec_scheme: dict[str, Any]) -> dict[str, Any]:
    """Convert a security scheme from OpenAPI 3.0 to Swagger 2.0."""
    sec_type = sec_scheme.get("type")

    if sec_type == "http" and sec_scheme.get("scheme") == "basic":
        return {"type": "basic"}
    elif sec_type == "apiKey":
        return {
            "type": "apiKey",
            "in": sec_scheme.get("in"),
            "name": sec_scheme.get("name"),
        }
    elif sec_type == "oauth2":
        flows = sec_scheme.get("flows", {})
        result: dict[str, Any] = {"type": "oauth2"}

        flow_map = {
            "implicit": "implicit",
            "password": "password",
            "clientCredentials": "application",
            "authorizationCode": "accessCode",
        }

        for flow_name, flow_type in flow_map.items():
            if flow_name in flows:
                result["flow"] = flow_type
                flow = flows[flow_name]
                if "authorizationUrl" in flow:
                    result["authorizationUrl"] = flow["authorizationUrl"]
                if "tokenUrl" in flow:
                    result["tokenUrl"] = flow["tokenUrl"]
                if "scopes" in flow:
                    result["scopes"] = flow["scopes"]
                break

        return result

    return sec_scheme


def convert_3_0_to_2(
    spec_data: dict[str, Any],
    convert_schema_fn: Callable,
    convert_path_item_fn: Callable,
    convert_security_scheme_fn: Callable,
) -> dict[str, Any]:
    """Convert OpenAPI 3.0 to Swagger 2.0."""
    converted: dict[str, Any] = {
        "swagger": "2.0",
        "info": spec_data.get("info", {}),
        "paths": {},
        "definitions": {},
        "securityDefinitions": {},
    }

    servers = spec_data.get("servers", [])
    if servers:
        server_url = servers[0].get("url", "https://localhost/")
        match = re.match(r"(https?)://([^/]+)(.*)", server_url)
        if match:
            converted["schemes"] = [match.group(1)]
            converted["host"] = match.group(2)
            converted["basePath"] = match.group(3) or "/"

    schemas = spec_data.get("components", {}).get("schemas", {})
    for name, schema in schemas.items():
        converted["definitions"][name] = convert_schema_fn(schema)

    paths = spec_data.get("paths", {})
    for path, path_item in paths.items():
        converted["paths"][path] = convert_path_item_fn(path_item)

    sec_schemes = spec_data.get("components", {}).get("securitySchemes", {})
    for name, sec_scheme in sec_schemes.items():
        converted["securityDefinitions"][name] = convert_security_scheme_fn(sec_scheme)

    for key in ["security", "tags", "externalDocs"]:
        if key in spec_data:
            converted[key] = spec_data[key]

    return converted


def convert_type_array_to_nullable(obj: Any) -> None:
    """Recursively convert type arrays to nullable: true (3.1 to 3.0)."""
    if isinstance(obj, dict):
        if isinstance(obj.get("type"), list) and "null" in obj["type"]:
            types = [t for t in obj["type"] if t != "null"]
            if len(types) == 1:
                obj["type"] = types[0]
                obj["nullable"] = True
        for value in obj.values():
            convert_type_array_to_nullable(value)
    elif isinstance(obj, list):
        for item in obj:
            convert_type_array_to_nullable(item)
