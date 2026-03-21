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
    MockServerConfig,
    MockServerDefinition,
    MockServerGenerationResult,
)
from Asgard.Forseti.MockServer.services.mock_data_generator import MockDataGeneratorService
from Asgard.Forseti.MockServer.services._mock_server_generator_helpers import (
    generate_express_route,
    generate_fastapi_route,
    generate_flask_main,
    generate_flask_routes,
    generate_response_data,
)
from Asgard.Forseti.MockServer.services._mock_server_parse_helpers import (
    parse_asyncapi_channels,
    parse_openapi_endpoints,
)


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
        self.config = config or MockServerConfig()
        self.data_generator = MockDataGeneratorService()

    def generate_from_openapi(
        self,
        spec_path: str | Path,
        output_dir: Optional[str | Path] = None,
    ) -> MockServerGenerationResult:
        start_time = time.time()
        spec_path = Path(spec_path)
        warnings: list[str] = []
        errors: list[str] = []
        try:
            spec_data = self._load_spec_file(spec_path)
        except Exception as e:
            errors.append(f"Failed to load specification: {e}")
            return MockServerGenerationResult(
                success=False,
                server_definition=MockServerDefinition(title="Error", endpoints=[]),
                errors=errors,
                generation_time_ms=(time.time() - start_time) * 1000,
            )
        endpoints = parse_openapi_endpoints(spec_data, self.data_generator, warnings)
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
        generated_files = self._generate_server_files(server_def)
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
        output_dir: Optional[str | Path] = None,
    ) -> MockServerGenerationResult:
        start_time = time.time()
        spec_path = Path(spec_path)
        warnings: list[str] = []
        errors: list[str] = []
        try:
            spec_data = self._load_spec_file(spec_path)
        except Exception as e:
            errors.append(f"Failed to load specification: {e}")
            return MockServerGenerationResult(
                success=False,
                server_definition=MockServerDefinition(title="Error", endpoints=[]),
                errors=errors,
                generation_time_ms=(time.time() - start_time) * 1000,
            )
        endpoints = parse_asyncapi_channels(spec_data, self.data_generator, warnings)
        info = spec_data.get("info", {})
        server_def = MockServerDefinition(
            title=info.get("title", "Mock Message Server"),
            description=info.get("description"),
            version=info.get("version", "1.0.0"),
            endpoints=endpoints,
            config=self.config,
            source_spec=str(spec_path),
        )
        generated_files = self._generate_flask_server(server_def)
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

    def generate_definition(self, spec_path: str | Path) -> MockServerDefinition:
        spec_data = self._load_spec_file(Path(spec_path))
        warnings: list[str] = []
        if "openapi" in spec_data:
            endpoints = parse_openapi_endpoints(spec_data, self.data_generator, warnings)
        elif "asyncapi" in spec_data:
            endpoints = parse_asyncapi_channels(spec_data, self.data_generator, warnings)
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
        content = spec_path.read_text(encoding="utf-8")
        try:
            return cast(dict[str, Any], yaml.safe_load(content))
        except yaml.YAMLError:
            return cast(dict[str, Any], json.loads(content))

    def _get_base_url(self, spec_data: dict[str, Any]) -> str:
        servers = spec_data.get("servers", [])
        if servers:
            return cast(str, servers[0].get("url", ""))
        return ""

    def _generate_server_files(self, server_def: MockServerDefinition) -> list[GeneratedFile]:
        if self.config.server_framework == "fastapi":
            return self._generate_fastapi_server(server_def)
        elif self.config.server_framework == "express":
            return self._generate_express_server(server_def)
        else:
            return self._generate_flask_server(server_def)

    def _generate_flask_server(self, server_def: MockServerDefinition) -> list[GeneratedFile]:
        files = []
        files.append(GeneratedFile(
            path="server.py",
            content=generate_flask_main(server_def, self.config),
            file_type="python",
            is_entry_point=True,
        ))
        files.append(GeneratedFile(
            path="routes.py",
            content=generate_flask_routes(server_def, self.config),
            file_type="python",
        ))
        files.append(GeneratedFile(
            path="mock_data.py",
            content=generate_response_data(server_def),
            file_type="python",
        ))
        files.append(GeneratedFile(
            path="requirements.txt",
            content="flask>=2.0.0\nflask-cors>=3.0.0\n",
            file_type="text",
        ))
        return files

    def _generate_fastapi_server(self, server_def: MockServerDefinition) -> list[GeneratedFile]:
        files = []
        routes = [generate_fastapi_route(ep, self.config) for ep in server_def.endpoints]
        routes_str = "\n\n".join(routes)
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
        files.append(GeneratedFile(path="server.py", content=server_code, file_type="python", is_entry_point=True))
        files.append(GeneratedFile(path="mock_data.py", content=generate_response_data(server_def), file_type="python"))
        files.append(GeneratedFile(path="requirements.txt", content="fastapi>=0.100.0\nuvicorn>=0.20.0\n", file_type="text"))
        return files

    def _generate_express_server(self, server_def: MockServerDefinition) -> list[GeneratedFile]:
        files = []
        routes = [generate_express_route(ep, self.config) for ep in server_def.endpoints]
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
        files.append(GeneratedFile(path="server.js", content=server_code, file_type="javascript", is_entry_point=True))
        mock_data = {}
        for endpoint in server_def.endpoints:
            default_status = endpoint.default_response or "200"
            response_key = f"{endpoint.method.value}_{endpoint.path}_{default_status}"
            if default_status in endpoint.responses:
                mock_data[response_key] = endpoint.responses[default_status].body
        files.append(GeneratedFile(path="mockData.json", content=json.dumps(mock_data, indent=2), file_type="json"))
        package_json = {
            "name": server_def.title.lower().replace(" ", "-"),
            "version": server_def.version,
            "description": server_def.description or "Mock server",
            "main": "server.js",
            "scripts": {"start": "node server.js"},
            "dependencies": {"express": "^4.18.0", "cors": "^2.8.5"},
        }
        files.append(GeneratedFile(path="package.json", content=json.dumps(package_json, indent=2), file_type="json"))
        return files

    def _write_files(self, files: list[GeneratedFile], output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        for file in files:
            file_path = output_dir / file.path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(file.content, encoding="utf-8")
