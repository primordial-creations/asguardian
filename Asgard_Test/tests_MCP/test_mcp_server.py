"""
Tests for Asgard MCP Server

Unit and integration tests for the JSON-RPC MCP server, covering protocol
handling via both direct method calls on AsgardMCPServer and HTTP requests
to a live server instance running in a background thread.
"""

import json
import socket
import threading
import time
import urllib.error
import urllib.request

import pytest

from Asgard.MCP.models.mcp_models import MCPRequest, MCPResponse, MCPServerConfig, MCPTool
from Asgard.MCP.server.asgard_mcp_server import AsgardMCPServer


def _get_free_port() -> int:
    """Return a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _post_json(url: str, payload: dict) -> dict:
    """POST a JSON payload to url and return the parsed response dict."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post_raw(url: str, raw_body: bytes) -> dict:
    """POST raw bytes to url and return the parsed response dict."""
    req = urllib.request.Request(
        url,
        data=raw_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read().decode("utf-8"))


class TestMCPServerConfig:
    """Tests for MCPServerConfig model."""

    def test_default_host(self):
        """Test that the default host is localhost."""
        config = MCPServerConfig()
        assert config.host == "localhost"

    def test_default_port(self):
        """Test that the default port is 8765."""
        config = MCPServerConfig()
        assert config.port == 8765

    def test_custom_port(self):
        """Test that a custom port is accepted."""
        config = MCPServerConfig(port=9000)
        assert config.port == 9000

    def test_default_project_path(self):
        """Test that the default project_path is '.'."""
        config = MCPServerConfig()
        assert config.project_path == "."


class TestAsgardMCPServerHandleRequest:
    """Tests for AsgardMCPServer.handle_request() method (no network required)."""

    def _make_server(self) -> AsgardMCPServer:
        config = MCPServerConfig(host="localhost", port=_get_free_port(), project_path=".")
        return AsgardMCPServer(config)

    def test_initialize_returns_server_info(self):
        """Test that the initialize method returns serverInfo."""
        server = self._make_server()
        request = MCPRequest(method="initialize", id=1)
        response = server.handle_request(request)

        assert response.error is None
        assert response.result is not None
        assert "serverInfo" in response.result

    def test_initialize_returns_capabilities(self):
        """Test that the initialize method returns capabilities."""
        server = self._make_server()
        request = MCPRequest(method="initialize", id=2)
        response = server.handle_request(request)

        assert response.result is not None
        assert "capabilities" in response.result

    def test_tools_list_returns_tools_key(self):
        """Test that tools/list response contains a 'tools' key."""
        server = self._make_server()
        request = MCPRequest(method="tools/list", id=3)
        response = server.handle_request(request)

        assert response.error is None
        assert response.result is not None
        assert "tools" in response.result

    def test_tools_list_contains_quality_analyze(self):
        """Test that tools/list includes asgard_quality_analyze."""
        server = self._make_server()
        request = MCPRequest(method="tools/list", id=4)
        response = server.handle_request(request)

        tool_names = [t["name"] for t in response.result["tools"]]
        assert "asgard_quality_analyze" in tool_names

    def test_tools_list_contains_security_scan(self):
        """Test that tools/list includes asgard_security_scan."""
        server = self._make_server()
        request = MCPRequest(method="tools/list", id=5)
        response = server.handle_request(request)

        tool_names = [t["name"] for t in response.result["tools"]]
        assert "asgard_security_scan" in tool_names

    def test_tools_list_contains_all_expected_tools(self):
        """Test that tools/list includes all seven expected Asgard tools."""
        server = self._make_server()
        request = MCPRequest(method="tools/list", id=6)
        response = server.handle_request(request)

        tool_names = [t["name"] for t in response.result["tools"]]
        expected = [
            "asgard_quality_analyze",
            "asgard_security_scan",
            "asgard_quality_gate",
            "asgard_ratings",
            "asgard_sbom",
            "asgard_list_issues",
            "asgard_compliance_report",
        ]
        for name in expected:
            assert name in tool_names

    def test_tools_list_tools_have_name_and_description(self):
        """Test that each tool in tools/list has name and description fields."""
        server = self._make_server()
        request = MCPRequest(method="tools/list", id=7)
        response = server.handle_request(request)

        for tool in response.result["tools"]:
            assert "name" in tool
            assert "description" in tool

    def test_tools_list_tools_have_input_schema(self):
        """Test that each tool in tools/list has an inputSchema field."""
        server = self._make_server()
        request = MCPRequest(method="tools/list", id=8)
        response = server.handle_request(request)

        for tool in response.result["tools"]:
            assert "inputSchema" in tool

    def test_tools_call_unknown_tool_returns_error_in_result(self):
        """Test that calling an unknown tool returns isError=True in the result."""
        server = self._make_server()
        request = MCPRequest(
            method="tools/call",
            id=9,
            params={"name": "nonexistent_tool", "arguments": {}},
        )
        response = server.handle_request(request)

        assert response.error is None
        assert response.result is not None
        assert response.result.get("isError") is True

    def test_tools_call_unknown_tool_error_content(self):
        """Test that calling an unknown tool includes informative error content."""
        server = self._make_server()
        request = MCPRequest(
            method="tools/call",
            id=10,
            params={"name": "does_not_exist", "arguments": {}},
        )
        response = server.handle_request(request)

        content_text = response.result["content"][0]["text"]
        assert "does_not_exist" in content_text or "Unknown tool" in content_text

    def test_unknown_method_returns_error_response(self):
        """Test that an unrecognised method returns a JSON-RPC error."""
        server = self._make_server()
        request = MCPRequest(method="no.such.method", id=11)
        response = server.handle_request(request)

        assert response.error is not None
        assert response.error["code"] == -32601

    def test_response_id_matches_request_id(self):
        """Test that the response id mirrors the request id."""
        server = self._make_server()
        request = MCPRequest(method="tools/list", id=42)
        response = server.handle_request(request)

        assert response.id == 42

    def test_response_jsonrpc_version(self):
        """Test that responses carry jsonrpc version 2.0."""
        server = self._make_server()
        request = MCPRequest(method="tools/list", id=1)
        response = server.handle_request(request)

        assert response.jsonrpc == "2.0"


class TestAsgardMCPServerHTTP:
    """Integration tests for AsgardMCPServer running over HTTP in a background thread."""

    @pytest.fixture(autouse=True)
    def start_server(self):
        """Start the MCP server on a free port before each test and stop after."""
        port = _get_free_port()
        config = MCPServerConfig(host="127.0.0.1", port=port, project_path=".")
        self._server = AsgardMCPServer(config)
        self._base_url = f"http://127.0.0.1:{port}"

        thread = threading.Thread(target=self._server.run, daemon=True)
        thread.start()
        time.sleep(0.1)
        yield
        # The daemon thread will stop when the test process exits.

    def test_tools_list_over_http(self):
        """Test tools/list returns a valid response over HTTP."""
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        response = _post_json(self._base_url, payload)

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        assert "tools" in response["result"]

    def test_tools_list_contains_quality_analyze_over_http(self):
        """Test that tools/list over HTTP includes asgard_quality_analyze."""
        payload = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        response = _post_json(self._base_url, payload)

        tool_names = [t["name"] for t in response["result"]["tools"]]
        assert "asgard_quality_analyze" in tool_names

    def test_tools_list_contains_security_scan_over_http(self):
        """Test that tools/list over HTTP includes asgard_security_scan."""
        payload = {"jsonrpc": "2.0", "id": 3, "method": "tools/list"}
        response = _post_json(self._base_url, payload)

        tool_names = [t["name"] for t in response["result"]["tools"]]
        assert "asgard_security_scan" in tool_names

    def test_tools_call_unknown_tool_over_http(self):
        """Test that calling an unknown tool over HTTP returns an error result."""
        payload = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "unknown_tool", "arguments": {}},
        }
        response = _post_json(self._base_url, payload)

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        assert response["result"].get("isError") is True

    def test_invalid_json_returns_parse_error_over_http(self):
        """Test that sending malformed JSON returns a parse error."""
        raw = b"this is not json {{"
        response = _post_raw(self._base_url, raw)

        assert "error" in response
        assert response["error"]["code"] == -32700

    def test_unknown_method_over_http_returns_error(self):
        """Test that an unrecognised method returns a method-not-found error over HTTP."""
        payload = {"jsonrpc": "2.0", "id": 5, "method": "not.a.method"}
        response = _post_json(self._base_url, payload)

        assert "error" in response
        assert response["error"]["code"] == -32601

    def test_initialize_over_http(self):
        """Test that the initialize method works over HTTP."""
        payload = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "initialize",
            "params": {},
        }
        response = _post_json(self._base_url, payload)

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        assert "serverInfo" in response["result"]

    def test_response_id_mirrors_request_id_over_http(self):
        """Test that the response id matches the request id over HTTP."""
        payload = {"jsonrpc": "2.0", "id": 999, "method": "tools/list"}
        response = _post_json(self._base_url, payload)

        assert response["id"] == 999
