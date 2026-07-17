"""
L1 Integration Tests for LiveValidatorService against an in-process HTTP server.

Self-referential harness (plan 06 testing notes): a tiny stdlib
`http.server` plays the "live implementation." A conformant handler must
produce zero drift findings; a deliberately mutated handler (extra field
dropped requirement, undocumented 500, wrong type) must be flagged with
the expected `drift.*` / `negative.*` rule ids. No external network is
used - the server binds to 127.0.0.1 on an ephemeral port.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from Asgard.Forseti.LiveContract.models.live_contract_models import ProbeConfig
from Asgard.Forseti.LiveContract.services.live_validator_service import (
    LiveValidatorService,
)
from Asgard.Forseti.LiveContract.services.probe_planner_service import (
    ProbePlannerService,
)

SPEC = {
    "paths": {
        "/pets": {
            "post": {
                "operationId": "createPet",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name"],
                                "properties": {"name": {"type": "string"}},
                            }
                        }
                    }
                },
                "responses": {
                    "201": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["id", "name"],
                                    "properties": {
                                        "id": {"type": "string"},
                                        "name": {"type": "string"},
                                    },
                                }
                            }
                        }
                    }
                },
            }
        },
        "/pets/{petId}": {
            "get": {
                "operationId": "getPet",
                "parameters": [{"name": "petId", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["id", "name"],
                                    "properties": {
                                        "id": {"type": "string"},
                                        "name": {"type": "string"},
                                    },
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


class ConformantHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        json.loads(self.rfile.read(length) or b"{}")
        body = {"id": "abc123", "name": "Rex"}
        payload = json.dumps(body).encode()
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        body = {"id": "abc123", "name": "Rex"}
        payload = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class DriftingHandler(BaseHTTPRequestHandler):
    """Emits an undocumented 500 on POST and a schema-mismatched GET body."""

    def log_message(self, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        self.send_response(500)
        self.send_header("Content-Type", "application/json")
        payload = b"{}"
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        # Missing required "name" field -> schema mismatch.
        body = {"id": "abc123"}
        payload = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class EchoInvalidHandler(BaseHTTPRequestHandler):
    """Accepts anything (including mutated/invalid input) as 201 -> negative-pass violation."""

    def log_message(self, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        body = {"id": "abc123", "name": "Rex"}
        payload = json.dumps(body).encode()
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        body = {"id": "abc123", "name": "Rex"}
        payload = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@pytest.fixture
def conformant_server():
    server, thread = _make_server(ConformantHandler)
    yield server
    server.shutdown()
    thread.join(timeout=2)


@pytest.fixture
def drifting_server():
    server, thread = _make_server(DriftingHandler)
    yield server
    server.shutdown()
    thread.join(timeout=2)


@pytest.fixture
def echo_server():
    server, thread = _make_server(EchoInvalidHandler)
    yield server
    server.shutdown()
    thread.join(timeout=2)


class TestConformantImplementation:
    def test_zero_drift_findings(self, conformant_server):
        base_url = f"http://127.0.0.1:{conformant_server.server_port}"
        plan = ProbePlannerService().plan(SPEC)
        config = ProbeConfig(base_url=base_url, max_requests=10)
        report = LiveValidatorService(config).run(plan)
        assert report.findings == []
        assert report.operations_attempted == 2
        assert report.operations_succeeded == 2


class TestDriftDetection:
    def test_undocumented_status_and_schema_mismatch_flagged(self, drifting_server):
        base_url = f"http://127.0.0.1:{drifting_server.server_port}"
        plan = ProbePlannerService().plan(SPEC)
        config = ProbeConfig(base_url=base_url, max_requests=10)
        report = LiveValidatorService(config).run(plan)
        rule_ids = {f.rule_id for f in report.findings}
        assert "drift.undocumented-status" in rule_ids
        assert "drift.schema-mismatch" in rule_ids
        assert report.has_errors is True


class TestNegativePass:
    def test_echoing_invalid_input_as_2xx_is_flagged(self, echo_server):
        base_url = f"http://127.0.0.1:{echo_server.server_port}"
        plan = ProbePlannerService().plan(SPEC)
        config = ProbeConfig(base_url=base_url, max_requests=10, negative=True)
        report = LiveValidatorService(config).run(plan)
        rule_ids = {f.rule_id for f in report.findings}
        assert "negative.expected-4xx" in rule_ids
