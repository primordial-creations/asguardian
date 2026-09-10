"""L3 contracts for the MCP JSON-RPC and server-configuration boundary."""

import pytest
from pydantic import ValidationError

from Asgard.MCP.models.mcp_models import (
    MCPRequest,
    MCPResponse,
    MCPServerConfig,
    MCPTool,
    MCPToolParam,
)


def _parameter(**overrides: object) -> MCPToolParam:
    payload = {
        "name": "path",
        "description": "Project-relative path to scan",
        "type": "string",
    }
    payload.update(overrides)
    return MCPToolParam.model_validate(payload)


class TestMCPToolParamContract:
    @pytest.mark.parametrize("missing", ("name", "description", "type"))
    def test_requires_the_parameter_schema_fields(self, missing: str):
        payload = _parameter().model_dump()
        payload.pop(missing)

        with pytest.raises(ValidationError):
            MCPToolParam.model_validate(payload)

    def test_optional_values_survive_a_json_round_trip(self):
        parameter = _parameter(required=False, default="src")

        restored = MCPToolParam.model_validate_json(parameter.model_dump_json())

        assert restored == parameter
        assert restored.required is False
        assert restored.default == "src"


class TestMCPToolContract:
    def test_nested_parameter_documents_are_validated(self):
        tool = MCPTool.model_validate(
            {
                "name": "asgard_quality_analyze",
                "description": "Analyze a project",
                "parameters": [_parameter().model_dump()],
            }
        )

        assert tool.parameters == [_parameter()]
        assert isinstance(tool.parameters[0], MCPToolParam)

    def test_rejects_a_malformed_nested_parameter(self):
        with pytest.raises(ValidationError):
            MCPTool.model_validate(
                {
                    "name": "asgard_quality_analyze",
                    "description": "Analyze a project",
                    "parameters": [{"name": "path"}],
                }
            )

    def test_parameter_lists_are_isolated_between_documents(self):
        first = MCPTool(name="first", description="First", parameters=[])
        second = MCPTool(name="second", description="Second", parameters=[])

        first.parameters.append(_parameter())

        assert second.parameters == []


class TestMCPRequestContract:
    def test_minimal_request_receives_json_rpc_defaults(self):
        request = MCPRequest.model_validate({"method": "tools/list"})

        assert request.jsonrpc == "2.0"
        assert request.id is None
        assert request.params is None

    @pytest.mark.parametrize("request_id", (17, "request-17", None))
    def test_supported_ids_survive_a_json_round_trip(self, request_id: object):
        request = MCPRequest(
            id=request_id,
            method="tools/call",
            params={"name": "asgard_quality_analyze", "arguments": {}},
        )

        restored = MCPRequest.model_validate_json(request.model_dump_json())

        assert restored == request
        assert restored.id == request_id

    def test_requires_a_method(self):
        with pytest.raises(ValidationError):
            MCPRequest.model_validate({"jsonrpc": "2.0", "id": 1})

    def test_rejects_non_mapping_params(self):
        with pytest.raises(ValidationError):
            MCPRequest.model_validate({"method": "tools/call", "params": []})


class TestMCPResponseContract:
    def test_result_document_survives_a_json_round_trip(self):
        response = MCPResponse(
            id="request-17",
            result={"tools": [{"name": "asgard_quality_analyze"}]},
        )

        restored = MCPResponse.model_validate_json(response.model_dump_json())

        assert restored == response
        assert restored.error is None

    def test_error_document_survives_a_json_round_trip(self):
        response = MCPResponse(
            id=17,
            error={"code": -32601, "message": "Method not found"},
        )

        restored = MCPResponse.model_validate_json(response.model_dump_json())

        assert restored == response
        assert restored.result is None

    def test_rejects_a_non_mapping_error(self):
        with pytest.raises(ValidationError):
            MCPResponse.model_validate({"id": 1, "error": "failed"})


class TestMCPServerConfigContract:
    def test_defaults_are_stable_and_local_only(self):
        config = MCPServerConfig.model_validate({})

        assert config.model_dump() == {
            "host": "localhost",
            "port": 8765,
            "project_path": ".",
            "enable_quality": True,
            "enable_security": True,
            "enable_sbom": True,
            "enable_gate": True,
            "enable_ratings": True,
            "auth_token": None,
            "expose": False,
            "max_body_bytes": 1_048_576,
        }

    def test_custom_security_and_feature_settings_round_trip(self):
        config = MCPServerConfig(
            host="127.0.0.1",
            port=9000,
            project_path="/workspace/project",
            enable_security=False,
            auth_token="test-token",
            expose=True,
            max_body_bytes=4096,
        )

        restored = MCPServerConfig.model_validate_json(config.model_dump_json())

        assert restored == config

    @pytest.mark.parametrize(
        ("field", "value"),
        (("port", "not-a-port"), ("max_body_bytes", "unbounded")),
    )
    def test_rejects_non_numeric_server_limits(self, field: str, value: object):
        with pytest.raises(ValidationError):
            MCPServerConfig.model_validate({field: value})
