"""
L1 Integration Tests for WorkflowRunnerService against an in-process HTTP server
(plan 06-C, Arazzo-lite workflow runner).

Mirrors `test_live_validator_integration.py`'s self-referential harness: a
tiny stdlib `http.server` plays the "live implementation," binding to
127.0.0.1 on an ephemeral port - no external network.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from Asgard.Forseti.LiveContract.models.live_contract_models import ProbeConfig, Workflow
from Asgard.Forseti.LiveContract.services.workflow_runner_service import WorkflowRunnerService

SPEC = {
    "paths": {
        "/login": {
            "post": {
                "operationId": "login",
                "responses": {
                    "201": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"access_token": {"type": "string"}},
                                }
                            }
                        }
                    }
                },
            }
        },
        "/profile": {
            "get": {
                "operationId": "getProfile",
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"name": {"type": "string"}},
                                }
                            }
                        }
                    }
                },
            }
        },
    }
}


def _make_server(handler_cls):
    server = HTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


class HappyPathHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        body = {"access_token": "tok-123"}
        payload = json.dumps(body).encode()
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        body = {"name": "Ada"}
        payload = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class WrongStatusHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        payload = b"{}"
        self.send_response(500)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        payload = b"{}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@pytest.fixture
def happy_server():
    server, thread = _make_server(HappyPathHandler)
    yield server
    server.shutdown()
    thread.join(timeout=2)


@pytest.fixture
def wrong_status_server():
    server, thread = _make_server(WrongStatusHandler)
    yield server
    server.shutdown()
    thread.join(timeout=2)


WORKFLOW = Workflow.model_validate(
    {
        "steps": [
            {
                "operationId": "login",
                "extract": {"token": "$.body.access_token"},
                "expect": {"status": 201},
            },
            {
                "operationId": "getProfile",
                "parameters": {},
                "extract": {"name": "$.body.name"},
                "expect": {"status": 200},
            },
        ]
    }
)


class TestWorkflowHappyPath:
    def test_token_extracted_and_threaded_into_next_step(self, happy_server):
        base_url = f"http://127.0.0.1:{happy_server.server_port}"
        config = ProbeConfig(base_url=base_url, auth_header=None)
        runner = WorkflowRunnerService(SPEC, config)
        report = runner.run(WORKFLOW)
        assert report.has_errors is False
        assert report.steps[0].extracted == {"token": "tok-123"}
        assert report.steps[1].status_code == 200
        assert report.steps[1].extracted == {"name": "Ada"}


class TestWorkflowExpectationFailure:
    def test_wrong_status_flagged(self, wrong_status_server):
        base_url = f"http://127.0.0.1:{wrong_status_server.server_port}"
        config = ProbeConfig(base_url=base_url)
        runner = WorkflowRunnerService(SPEC, config)
        report = runner.run(WORKFLOW)
        rule_ids = {f.rule_id for f in report.findings}
        assert "workflow.unexpected-status" in rule_ids
        assert report.has_errors is True


class TestUnknownOperation:
    def test_unknown_operation_id_flagged(self, happy_server):
        base_url = f"http://127.0.0.1:{happy_server.server_port}"
        config = ProbeConfig(base_url=base_url)
        runner = WorkflowRunnerService(SPEC, config)
        bad_workflow = Workflow.model_validate({"steps": [{"operationId": "doesNotExist"}]})
        report = runner.run(bad_workflow)
        assert report.has_errors is True
        assert report.steps[0].error is not None
        assert {f.rule_id for f in report.findings} == {"workflow.unknown-operation"}
