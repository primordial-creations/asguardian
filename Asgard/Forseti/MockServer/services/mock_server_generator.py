"""
Mock Server Generator Service.

Generates mock server code from OpenAPI and AsyncAPI specifications.
"""

import json
import time
from pathlib import Path
from typing import Any, Optional, cast

import yaml  # type: ignore[import-untyped]

from Asgard.Forseti.MockServer.models.mock_models import (
    GeneratedFile,
    HttpMethod,
    MockEndpoint,
    MockParameter,
    MockRequestBody,
    MockResponse,
    MockServerConfig,
    MockServerDefinition,
    MockServerGenerationResult,
)
from Asgard.Forseti.MockServer.services.mock_data_generator import MockDataGeneratorService


class MockServerGeneratorService:
    """
    Service for generating mock servers from API specifications.

    Generates complete mock server code from OpenAPI or AsyncAPI
    specifications, including endpoints, response data, and validation.

    Usage:
        generator = MockServerGeneratorService()
        result = generator.generate_from_openapi("api.yaml")
        for file in result.generated_files:
            print(f"Generated: {file.path}")
    """

    def __init__(self, config: Optional[MockServerConfig] = None):
        """
        Initialize the mock server generator.

        Args:
            config: Optional configuration for server generation.
        """
        self.config = config or MockServerConfig()
        self.data_generator = MockDataGeneratorService()

    def generate_from_openapi(
        self,
        spec_path: str | Path,
        output_dir: Optional[str | Path] = None
    ) -> MockServerGenerationResult:
        """
        Generate a mock server from an OpenAPI specification.

        Args:
            spec_path: Path to the OpenAPI specification file.
            output_dir: Optional output directory for generated files.

        Returns:
            MockServerGenerationResult with generated server files.
        """
        start_time = time.time()
        spec_path = Path(spec_path)
        warnings: list[str] = []
        errors: list[str] = []

        # Load specification
        try:
            spec_data = self._load_spec_file(spec_path)
        except Exception as e:
            errors.append(f"Failed to load specification: {e}")
            return MockServerGenerationResult(
                success=False,
                server_definition=MockServerDefinition(
                    title="Error",
                    endpoints=[],
                ),
                errors=errors,
                generation_time_ms=(time.time() - start_time) * 1000,
            )

        # Parse endpoints from OpenAPI
        endpoints = self._parse_openapi_endpoints(spec_data, warnings)

        # Create server definition
        info = spec_data.get("info", {})
        server_def = MockServerDefinition(
            title=info.get("title", "Mock API"),
            description=info.get("description"),
            version=info.get("version", "1.0.0"),
            base_url=self._get_base_url(spec_data),
            endpoints=endpoints,
            config=self.config,
            source_spec=str(spec_path),
        )

        # Generate server files
        generated_files = self._generate_server_files(server_def)

        # Write files if output directory specified
        if output_dir:
            self._write_files(generated_files, Path(output_dir))

        return MockServerGenerationResult(
            success=len(errors) == 0,
            server_definition=server_def,
            generated_files=generated_files,
            warnings=warnings,
            errors=errors,
            generation_time_ms=(time.time() - start_time) * 1000,
        )

    def generate_from_asyncapi(
        self,
        spec_path: str | Path,
        output_dir: Optional[str | Path] = None
    ) -> MockServerGenerationResult:
        """
        Generate a mock server from an AsyncAPI specification.

        Args:
            spec_path: Path to the AsyncAPI specification file.
            output_dir: Optional output directory for generated files.

        Returns:
            MockServerGenerationResult with generated server files.
        """
        start_time = time.time()
        spec_path = Path(spec_path)
        warnings: list[str] = []
        errors: list[str] = []

        # Load specification
        try:
            spec_data = self._load_spec_file(spec_path)
        except Exception as e:
            errors.append(f"Failed to load specification: {e}")
            return MockServerGenerationResult(
                success=False,
                server_definition=MockServerDefinition(
                    title="Error",
                    endpoints=[],
                ),
                errors=errors,
                generation_time_ms=(time.time() - start_time) * 1000,
            )

        # Parse channels from AsyncAPI into mock endpoints
        endpoints = self._parse_asyncapi_channels(spec_data, warnings)

        # Create server definition
        info = spec_data.get("info", {})
        server_def = MockServerDefinition(
            title=info.get("title", "Mock Message Server"),
            description=info.get("description"),
            version=info.get("version", "1.0.0"),
            endpoints=endpoints,
            config=self.config,
            source_spec=str(spec_path),
        )

        # Generate server files
        generated_files = self._generate_message_server_files(server_def, spec_data)

        # Write files if output directory specified
        if output_dir:
            self._write_files(generated_files, Path(output_dir))

        return MockServerGenerationResult(
            success=len(errors) == 0,
            server_definition=server_def,
            generated_files=generated_files,
            warnings=warnings,
            errors=errors,
            generation_time_ms=(time.time() - start_time) * 1000,
        )

    def generate_definition(
        self,
        spec_path: str | Path
    ) -> MockServerDefinition:
        """
        Generate just the server definition without code generation.

        Args:
            spec_path: Path to the specification file.

        Returns:
            MockServerDefinition object.
        """
        spec_data = self._load_spec_file(Path(spec_path))
        warnings: list[str] = []

        # Detect spec type
        if "openapi" in spec_data:
            endpoints = self._parse_openapi_endpoints(spec_data, warnings)
        elif "asyncapi" in spec_data:
            endpoints = self._parse_asyncapi_channels(spec_data, warnings)
        else:
            endpoints = []

        info = spec_data.get("info", {})
        return MockServerDefinition(
            title=info.get("title", "Mock API"),
            description=info.get("description"),
            version=info.get("version", "1.0.0"),
            endpoints=endpoints,
            config=self.config,
            source_spec=str(spec_path),
        )

    def _load_spec_file(self, spec_path: Path) -> dict[str, Any]:
        """Load a specification file (YAML or JSON)."""
        content = spec_path.read_text(encoding="utf-8")

        try:
            return cast(dict[str, Any], yaml.safe_load(content))
        except yaml.YAMLError:
            return cast(dict[str, Any], json.loads(content))

    def _get_base_url(self, spec_data: dict[str, Any]) -> str:
        """Extract base URL from OpenAPI spec."""
        servers = spec_data.get("servers", [])
        if servers:
            return cast(str, servers[0].get("url", ""))
        return ""

    def _parse_openapi_endpoints(
        self,
        spec_data: dict[str, Any],
        warnings: list[str]
    ) -> list[MockEndpoint]:
        """Parse OpenAPI paths into mock endpoints."""
        endpoints = []
        paths = spec_data.get("paths", {})
        http_methods = ["get", "post", "put", "patch", "delete", "options", "head"]

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            # Get path-level parameters
            path_params = self._parse_parameters(path_item.get("parameters", []))

            for method in http_methods:
                if method not in path_item:
                    continue

                operation = path_item[method]
                if not isinstance(operation, dict):
                    continue

                # Combine path and operation parameters
                op_params = self._parse_parameters(operation.get("parameters", []))
                all_params = path_params + op_params

                # Parse request body
                request_body = None
                if "requestBody" in operation:
                    request_body = self._parse_request_body(operation["requestBody"])

                # Parse responses
                responses = self._parse_responses(
                    operation.get("responses", {}),
                    spec_data,
                    warnings
                )

                # Determine default response
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

    def _parse_parameters(self, params: list[dict[str, Any]]) -> list[MockParameter]:
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

    def _parse_request_body(self, request_body: dict[str, Any]) -> MockRequestBody:
        """Parse OpenAPI request body into MockRequestBody."""
        content = request_body.get("content", {})

        # Get the first content type
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

    def _parse_responses(
        self,
        responses: dict[str, Any],
        spec_data: dict[str, Any],
        warnings: list[str]
    ) -> dict[str, MockResponse]:
        """Parse OpenAPI responses into MockResponses with generated data."""
        result = {}

        for status_code, response_data in responses.items():
            if not isinstance(response_data, dict):
                continue

            # Get content
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
                    # Generate mock data from schema
                    try:
                        body_result = self.data_generator.generate_from_schema(body_schema)
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

    def _parse_asyncapi_channels(
        self,
        spec_data: dict[str, Any],
        warnings: list[str]
    ) -> list[MockEndpoint]:
        """Parse AsyncAPI channels into mock endpoints for HTTP simulation."""
        endpoints = []
        channels = spec_data.get("channels", {})

        for channel_name, channel_data in channels.items():
            if not isinstance(channel_data, dict):
                continue

            # Convert channel to REST-like endpoint for mock purposes
            # Subscribe becomes GET, Publish becomes POST
            if "subscribe" in channel_data:
                operation = channel_data["subscribe"]
                endpoint = self._channel_to_endpoint(
                    channel_name,
                    HttpMethod.GET,
                    operation,
                    spec_data,
                    warnings
                )
                endpoints.append(endpoint)

            if "publish" in channel_data:
                operation = channel_data["publish"]
                endpoint = self._channel_to_endpoint(
                    channel_name,
                    HttpMethod.POST,
                    operation,
                    spec_data,
                    warnings
                )
                endpoints.append(endpoint)

        return endpoints

    def _channel_to_endpoint(
        self,
        channel_name: str,
        method: HttpMethod,
        operation: dict[str, Any],
        spec_data: dict[str, Any],
        warnings: list[str]
    ) -> MockEndpoint:
        """Convert an AsyncAPI channel operation to a mock endpoint."""
        # Parse message for response body
        message = operation.get("message", {})
        payload_schema = message.get("payload", {})

        body = None
        if payload_schema:
            try:
                body_result = self.data_generator.generate_from_schema(payload_schema)
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

        # Convert channel path to REST path
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

    def _generate_server_files(
        self,
        server_def: MockServerDefinition
    ) -> list[GeneratedFile]:
        """Generate server code files based on framework."""
        if self.config.server_framework == "fastapi":
            return self._generate_fastapi_server(server_def)
        elif self.config.server_framework == "express":
            return self._generate_express_server(server_def)
        else:
            return self._generate_flask_server(server_def)

    def _generate_flask_server(
        self,
        server_def: MockServerDefinition
    ) -> list[GeneratedFile]:
        """Generate Flask mock server code."""
        files = []

        # Main server file
        server_code = self._generate_flask_main(server_def)
        files.append(GeneratedFile(
            path="server.py",
            content=server_code,
            file_type="python",
            is_entry_point=True,
        ))

        # Routes file
        routes_code = self._generate_flask_routes(server_def)
        files.append(GeneratedFile(
            path="routes.py",
            content=routes_code,
            file_type="python",
        ))

        # Response data file
        data_code = self._generate_response_data(server_def)
        files.append(GeneratedFile(
            path="mock_data.py",
            content=data_code,
            file_type="python",
        ))

        # Requirements file
        requirements = "flask>=2.0.0\nflask-cors>=3.0.0\n"
        files.append(GeneratedFile(
            path="requirements.txt",
            content=requirements,
            file_type="text",
        ))

        return files

    def _generate_flask_main(self, server_def: MockServerDefinition) -> str:
        """Generate Flask main server file."""
        cors_import = "from flask_cors import CORS" if self.config.enable_cors else ""
        cors_init = "CORS(app)" if self.config.enable_cors else ""

        return f'''"""
{server_def.title} - Mock Server
Generated by Forseti MockServer

{server_def.description or ""}
"""

from flask import Flask, jsonify
{cors_import}
from routes import register_routes

app = Flask(__name__)
{cors_init}

# Register all routes
register_routes(app)


@app.errorhandler(404)
def not_found(e):
    return jsonify({{"error": "Not found"}}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({{"error": "Internal server error"}}), 500


if __name__ == "__main__":
    app.run(
        host="{self.config.host}",
        port={self.config.port},
        debug=True
    )
'''

    def _generate_flask_routes(self, server_def: MockServerDefinition) -> str:
        """Generate Flask routes file."""
        routes = []

        for endpoint in server_def.endpoints:
            route_code = self._generate_flask_route(endpoint)
            routes.append(route_code)

        routes_str = "\n\n".join(routes)

        return f'''"""
API Routes for {server_def.title}
"""

import time
from flask import Flask, jsonify, request
from mock_data import MOCK_RESPONSES


def register_routes(app: Flask):
    """Register all mock routes with the Flask app."""

{routes_str}
'''

    def _generate_flask_route(self, endpoint: MockEndpoint) -> str:
        """Generate a single Flask route."""
        # Convert OpenAPI path params to Flask format
        flask_path = endpoint.path.replace("{", "<").replace("}", ">")
        method_lower = endpoint.method.value.lower()
        func_name = self._endpoint_to_function_name(endpoint)

        # Get default response
        default_status = endpoint.default_response or "200"
        response_key = f"{endpoint.method.value}_{endpoint.path}_{default_status}"

        delay_code = ""
        if self.config.response_delay_ms > 0:
            delay_code = f"\n        time.sleep({self.config.response_delay_ms / 1000})"

        return f'''    @app.route("{flask_path}", methods=["{endpoint.method.value}"])
    def {func_name}(**kwargs):
        """{endpoint.summary or endpoint.description or f"Mock {endpoint.method.value} {endpoint.path}"}"""{delay_code}
        response_data = MOCK_RESPONSES.get("{response_key}", {{}})
        return jsonify(response_data), {default_status}'''

    def _generate_fastapi_server(
        self,
        server_def: MockServerDefinition
    ) -> list[GeneratedFile]:
        """Generate FastAPI mock server code."""
        files = []

        # Main server file
        routes = []
        for endpoint in server_def.endpoints:
            route = self._generate_fastapi_route(endpoint)
            routes.append(route)

        routes_str = "\n\n".join(routes)
        default_status = "200"

        server_code = f'''"""
{server_def.title} - Mock Server (FastAPI)
Generated by Forseti MockServer

{server_def.description or ""}
"""

import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mock_data import MOCK_RESPONSES

app = FastAPI(
    title="{server_def.title}",
    description="{server_def.description or ""}",
    version="{server_def.version}",
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

{routes_str}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="{self.config.host}", port={self.config.port})
'''

        files.append(GeneratedFile(
            path="server.py",
            content=server_code,
            file_type="python",
            is_entry_point=True,
        ))

        # Response data file
        data_code = self._generate_response_data(server_def)
        files.append(GeneratedFile(
            path="mock_data.py",
            content=data_code,
            file_type="python",
        ))

        # Requirements file
        requirements = "fastapi>=0.100.0\nuvicorn>=0.20.0\n"
        files.append(GeneratedFile(
            path="requirements.txt",
            content=requirements,
            file_type="text",
        ))

        return files

    def _generate_fastapi_route(self, endpoint: MockEndpoint) -> str:
        """Generate a single FastAPI route."""
        method_lower = endpoint.method.value.lower()
        func_name = self._endpoint_to_function_name(endpoint)
        default_status = endpoint.default_response or "200"
        response_key = f"{endpoint.method.value}_{endpoint.path}_{default_status}"

        delay_code = ""
        if self.config.response_delay_ms > 0:
            delay_code = f"\n    time.sleep({self.config.response_delay_ms / 1000})"

        return f'''@app.{method_lower}("{endpoint.path}")
async def {func_name}():{delay_code}
    """{endpoint.summary or endpoint.description or f"Mock {endpoint.method.value} {endpoint.path}"}"""
    return MOCK_RESPONSES.get("{response_key}", {{}})'''

    def _generate_express_server(
        self,
        server_def: MockServerDefinition
    ) -> list[GeneratedFile]:
        """Generate Express.js mock server code."""
        files = []

        routes = []
        for endpoint in server_def.endpoints:
            route = self._generate_express_route(endpoint)
            routes.append(route)

        routes_str = "\n\n".join(routes)

        server_code = f'''/**
 * {server_def.title} - Mock Server (Express)
 * Generated by Forseti MockServer
 *
 * {server_def.description or ""}
 */

const express = require('express');
const cors = require('cors');
const mockData = require('./mockData.json');

const app = express();
const PORT = {self.config.port};

// Middleware
app.use(cors());
app.use(express.json());

{routes_str}

// Error handlers
app.use((req, res) => {{
    res.status(404).json({{ error: 'Not found' }});
}});

app.listen(PORT, () => {{
    console.log(`Mock server running at http://localhost:${{PORT}}`);
}});
'''

        files.append(GeneratedFile(
            path="server.js",
            content=server_code,
            file_type="javascript",
            is_entry_point=True,
        ))

        # Mock data JSON file
        mock_data = {}
        for endpoint in server_def.endpoints:
            default_status = endpoint.default_response or "200"
            response_key = f"{endpoint.method.value}_{endpoint.path}_{default_status}"
            if default_status in endpoint.responses:
                mock_data[response_key] = endpoint.responses[default_status].body

        files.append(GeneratedFile(
            path="mockData.json",
            content=json.dumps(mock_data, indent=2),
            file_type="json",
        ))

        # Package.json
        package_json = {
            "name": server_def.title.lower().replace(" ", "-"),
            "version": server_def.version,
            "description": server_def.description or "Mock server",
            "main": "server.js",
            "scripts": {
                "start": "node server.js"
            },
            "dependencies": {
                "express": "^4.18.0",
                "cors": "^2.8.5"
            }
        }
        files.append(GeneratedFile(
            path="package.json",
            content=json.dumps(package_json, indent=2),
            file_type="json",
        ))

        return files

    def _generate_express_route(self, endpoint: MockEndpoint) -> str:
        """Generate a single Express.js route."""
        # Convert OpenAPI path params to Express format (:param)
        express_path = endpoint.path
        for param in endpoint.path_parameters:
            express_path = express_path.replace(
                f"{{{param.name}}}", f":{param.name}"
            )

        method_lower = endpoint.method.value.lower()
        default_status = endpoint.default_response or "200"
        response_key = f"{endpoint.method.value}_{endpoint.path}_{default_status}"

        delay_code = ""
        if self.config.response_delay_ms > 0:
            delay_code = f'''
    await new Promise(resolve => setTimeout(resolve, {self.config.response_delay_ms}));'''

        return f'''// {endpoint.summary or f"{endpoint.method.value} {endpoint.path}"}
app.{method_lower}('{express_path}', {"async " if delay_code else ""}(req, res) => {{{delay_code}
    const response = mockData['{response_key}'] || {{}};
    res.status({default_status}).json(response);
}});'''

    def _generate_response_data(self, server_def: MockServerDefinition) -> str:
        """Generate Python mock data file."""
        mock_data = {}

        for endpoint in server_def.endpoints:
            for status_code, response in endpoint.responses.items():
                response_key = f"{endpoint.method.value}_{endpoint.path}_{status_code}"
                mock_data[response_key] = response.body

        data_json = json.dumps(mock_data, indent=4, default=str)

        return f'''"""
Mock response data for {server_def.title}
"""

MOCK_RESPONSES = {data_json}
'''

    def _generate_message_server_files(
        self,
        server_def: MockServerDefinition,
        spec_data: dict[str, Any]
    ) -> list[GeneratedFile]:
        """Generate message server files for AsyncAPI."""
        # For AsyncAPI, we generate a WebSocket-based mock server
        return self._generate_flask_server(server_def)

    def _endpoint_to_function_name(self, endpoint: MockEndpoint) -> str:
        """Convert an endpoint to a valid function name."""
        if endpoint.operation_id:
            # Clean operation ID
            name = cast(str, endpoint.operation_id).replace("-", "_").replace(".", "_")
            return name

        # Generate from path and method
        path_parts = endpoint.path.strip("/").replace("{", "").replace("}", "")
        path_parts = path_parts.replace("/", "_").replace("-", "_")
        return f"{endpoint.method.value.lower()}_{path_parts}"

    def _write_files(
        self,
        files: list[GeneratedFile],
        output_dir: Path
    ) -> None:
        """Write generated files to disk."""
        output_dir.mkdir(parents=True, exist_ok=True)

        for file in files:
            file_path = output_dir / file.path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(file.content, encoding="utf-8")
