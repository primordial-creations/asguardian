"""
Mock Server Parse Helpers.

Parsing helper functions for MockServerGeneratorService.
"""

from typing import Any

from Asgard.Forseti.MockServer.models.mock_models import (
    HttpMethod,
    MockEndpoint,
    MockParameter,
    MockRequestBody,
    MockResponse,
    MockServerDefinition,
)
from Asgard.Forseti.MockServer.services.mock_data_generator import MockDataGeneratorService


def parse_parameters(params: list[dict[str, Any]]) -> list[MockParameter]:
    """Parse OpenAPI parameters into MockParameters."""
    result = []
    for param in params:
        if not isinstance(param, dict):
            continue
        mock_param = MockParameter(
            name=param.get("name", ""),
            location=param.get("in", "query"),
            required=param.get("required", False),
            schema=param.get("schema", {}),
            example=param.get("example"),
        )
        result.append(mock_param)
    return result


def parse_request_body(request_body: dict[str, Any]) -> MockRequestBody:
    """Parse OpenAPI request body into MockRequestBody."""
    content = request_body.get("content", {})
    content_type = "application/json"
    schema = {}
    example = None
    for ct, ct_data in content.items():
        content_type = ct
        schema = ct_data.get("schema", {})
        example = ct_data.get("example")
        break
    return MockRequestBody(
        content_type=content_type,
        required=request_body.get("required", False),
        schema=schema,
        example=example,
    )


def parse_responses(
    responses: dict[str, Any],
    data_generator: MockDataGeneratorService,
    warnings: list[str],
) -> dict[str, MockResponse]:
    """Parse OpenAPI responses into MockResponses with generated data."""
    result = {}
    for status_code, response_data in responses.items():
        if not isinstance(response_data, dict):
            continue
        content = response_data.get("content", {})
        content_type = "application/json"
        body = None
        body_schema = None
        for ct, ct_data in content.items():
            content_type = ct
            body_schema = ct_data.get("schema")
            if ct_data.get("example"):
                body = ct_data["example"]
            elif body_schema:
                try:
                    body_result = data_generator.generate_from_schema(body_schema)
                    body = body_result.data
                    warnings.extend(body_result.warnings)
                except Exception as e:
                    warnings.append(f"Failed to generate data for {status_code}: {e}")
            break
        mock_response = MockResponse(
            status_code=int(status_code) if status_code.isdigit() else 200,
            content_type=content_type,
            body=body,
            body_schema=body_schema,
        )
        result[status_code] = mock_response
    return result


def parse_openapi_endpoints(
    spec_data: dict[str, Any],
    data_generator: MockDataGeneratorService,
    warnings: list[str],
) -> list[MockEndpoint]:
    """Parse OpenAPI paths into mock endpoints."""
    endpoints = []
    paths = spec_data.get("paths", {})
    http_methods = ["get", "post", "put", "patch", "delete", "options", "head"]
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        path_params = parse_parameters(path_item.get("parameters", []))
        for method in http_methods:
            if method not in path_item:
                continue
            operation = path_item[method]
            if not isinstance(operation, dict):
                continue
            op_params = parse_parameters(operation.get("parameters", []))
            all_params = path_params + op_params
            request_body = None
            if "requestBody" in operation:
                request_body = parse_request_body(operation["requestBody"])
            responses = parse_responses(operation.get("responses", {}), data_generator, warnings)
            default_response = "200"
            if method == "post":
                default_response = "201"
            elif method == "delete":
                default_response = "204"
            endpoint = MockEndpoint(
                path=path,
                method=HttpMethod(method.upper()),
                operation_id=operation.get("operationId"),
                summary=operation.get("summary"),
                description=operation.get("description"),
                tags=operation.get("tags", []),
                parameters=all_params,
                request_body=request_body,
                responses=responses,
                default_response=default_response,
                security=operation.get("security", []),
            )
            endpoints.append(endpoint)
    return endpoints


def channel_to_endpoint(
    channel_name: str,
    method: HttpMethod,
    operation: dict[str, Any],
    data_generator: MockDataGeneratorService,
    warnings: list[str],
) -> MockEndpoint:
    """Convert an AsyncAPI channel operation to a mock endpoint."""
    message = operation.get("message", {})
    payload_schema = message.get("payload", {})
    body = None
    if payload_schema:
        try:
            body_result = data_generator.generate_from_schema(payload_schema)
            body = body_result.data
        except Exception as e:
            warnings.append(f"Failed to generate data for {channel_name}: {e}")
    responses = {
        "200": MockResponse(
            status_code=200,
            content_type="application/json",
            body=body,
            body_schema=payload_schema,
        )
    }
    path = "/" + channel_name.lstrip("/")
    return MockEndpoint(
        path=path,
        method=method,
        operation_id=operation.get("operationId"),
        summary=operation.get("summary"),
        description=operation.get("description"),
        tags=operation.get("tags", []),
        parameters=[],
        responses=responses,
        default_response="200",
    )


def parse_asyncapi_channels(
    spec_data: dict[str, Any],
    data_generator: MockDataGeneratorService,
    warnings: list[str],
) -> list[MockEndpoint]:
    """Parse AsyncAPI channels into mock endpoints for HTTP simulation."""
    endpoints = []
    channels = spec_data.get("channels", {})
    for channel_name, channel_data in channels.items():
        if not isinstance(channel_data, dict):
            continue
        if "subscribe" in channel_data:
            endpoint = channel_to_endpoint(channel_name, HttpMethod.GET, channel_data["subscribe"], data_generator, warnings)
            endpoints.append(endpoint)
        if "publish" in channel_data:
            endpoint = channel_to_endpoint(channel_name, HttpMethod.POST, channel_data["publish"], data_generator, warnings)
            endpoints.append(endpoint)
    return endpoints
