"""
OpenAPI Spec Parser Helpers.

Helper functions for SpecParserService.
"""

from typing import Any


def convert_security_definition(sec_def: dict[str, Any]) -> dict[str, Any]:
    """Convert a Swagger 2.0 security definition to OpenAPI 3.0."""
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

        if flow_type == "implicit":
            flows["implicit"] = flow_data
        elif flow_type == "password":
            flows["password"] = flow_data
        elif flow_type == "application":
            flows["clientCredentials"] = flow_data
        elif flow_type == "accessCode":
            flows["authorizationCode"] = flow_data

        return {
            "type": "oauth2",
            "flows": flows,
        }

    return sec_def


def convert_operation(operation: dict[str, Any]) -> dict[str, Any]:
    """Convert a Swagger 2.0 operation to OpenAPI 3.0."""
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
                        "schema": param.get("schema", {}),
                    }
                }
            }
        elif param.get("in") == "formData":
            if request_body is None:
                request_body = {
                    "content": {
                        "application/x-www-form-urlencoded": {
                            "schema": {
                                "type": "object",
                                "properties": {},
                            }
                        }
                    }
                }
            content = request_body["content"]["application/x-www-form-urlencoded"]
            content["schema"]["properties"][param["name"]] = {
                "type": param.get("type", "string"),
                "description": param.get("description", ""),
            }
        else:
            converted_param: dict[str, Any] = {
                "name": param.get("name"),
                "in": param.get("in"),
                "description": param.get("description", ""),
                "required": param.get("required", False),
                "schema": {
                    "type": param.get("type", "string"),
                }
            }
            if "format" in param:
                converted_param["schema"]["format"] = param["format"]
            if "enum" in param:
                converted_param["schema"]["enum"] = param["enum"]
            parameters.append(converted_param)

    if parameters:
        converted["parameters"] = parameters
    if request_body:
        converted["requestBody"] = request_body

    for status_code, response in operation.get("responses", {}).items():
        converted_response: dict[str, Any] = {
            "description": response.get("description", ""),
        }
        if "schema" in response:
            converted_response["content"] = {
                "application/json": {
                    "schema": response["schema"],
                }
            }
        if "headers" in response:
            converted_response["headers"] = response["headers"]
        converted["responses"][status_code] = converted_response

    return converted


def convert_path_item(path_item: dict[str, Any]) -> dict[str, Any]:
    """Convert a Swagger 2.0 path item to OpenAPI 3.0."""
    converted = {}
    http_methods = ["get", "put", "post", "delete", "options", "head", "patch"]

    for method in http_methods:
        if method in path_item:
            converted[method] = convert_operation(path_item[method])

    for key in ["summary", "description", "parameters"]:
        if key in path_item:
            converted[key] = path_item[key]

    return converted


def convert_swagger_to_openapi(spec_data: dict[str, Any]) -> dict[str, Any]:
    """Convert a Swagger 2.0 specification to OpenAPI 3.0 format."""
    converted: dict[str, Any] = {
        "openapi": "3.0.0",
        "info": spec_data.get("info", {}),
        "paths": {},
        "components": {
            "schemas": spec_data.get("definitions", {}),
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

    paths = spec_data.get("paths", {})
    for path, path_item in paths.items():
        converted["paths"][path] = convert_path_item(path_item)

    security_defs = spec_data.get("securityDefinitions", {})
    for name, sec_def in security_defs.items():
        converted["components"]["securitySchemes"][name] = (
            convert_security_definition(sec_def)
        )

    return converted
