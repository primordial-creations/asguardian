"""
Validation Proxy Service (plan 06-B.2, Prism-style).

Forwards requests to `--upstream`, validates the observed response against
the OpenAPI spec (reusing the same `check_response` drift-checking logic as
`forseti contract test`), and accumulates the violations into a
`DriftReport`. Stdlib-only (`urllib`, `http.server`) - Cost: NETWORK,
explicit opt-in only (never invoked implicitly).
"""

import json
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Optional

from Asgard.Forseti.LiveContract.models.live_contract_models import DriftReport, ProbeOperation, ProbeResult
from Asgard.Forseti.LiveContract.services._dependency_helpers import extract_operations
from Asgard.Forseti.LiveContract.services._response_check_helpers import check_response
from Asgard.Forseti.MockServer.services._validation_proxy_helpers import match_operation

# (status_code, headers, body_bytes)
FetchResult = tuple[int, dict[str, str], bytes]
Fetcher = Callable[[str, str, dict[str, str], bytes, float], FetchResult]


def urllib_fetch(method: str, url: str, headers: dict[str, str], body: bytes, timeout_s: float) -> FetchResult:
    """Default `Fetcher`: forward the request upstream via stdlib `urllib`."""
    req = urllib.request.Request(url, data=body or None, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            resp_body = resp.read()
            return resp.status, dict(resp.headers.items()), resp_body
    except urllib.error.HTTPError as e:
        resp_body = e.read()
        return e.code, dict(e.headers.items()) if e.headers else {}, resp_body


class ValidationProxyService:
    """Prism-style validation proxy: forward + validate + report drift.

    Usage:
        service = ValidationProxyService(openapi_doc, upstream="http://localhost:9000")
        status, headers, body, findings = service.handle_request("GET", "/users/1", {}, b"")
        report = service.report()  # accumulated DriftReport across all handled requests
    """

    def __init__(
        self,
        openapi_doc: dict[str, Any],
        upstream: str,
        timeout_s: float = 5.0,
        fetcher: Optional[Fetcher] = None,
    ):
        self.upstream = upstream.rstrip("/")
        self.timeout_s = timeout_s
        self.operations: list[ProbeOperation] = extract_operations(openapi_doc)
        self._fetch: Fetcher = fetcher or urllib_fetch
        self._report = DriftReport(base_url=upstream)

    def handle_request(
        self, method: str, path: str, headers: dict[str, str], body: bytes
    ) -> tuple[int, dict[str, str], bytes, list]:
        """Forward one request upstream and validate the response against the spec.

        Returns (status_code, response_headers, response_body, findings) so a
        thin HTTP layer can relay the upstream response to its own client
        while this service records drift findings on the side.
        """
        operation = match_operation(self.operations, method, path)
        url = f"{self.upstream}{path}"
        status_code, resp_headers, resp_body = self._fetch(method, url, dict(headers), body, self.timeout_s)

        findings: list = []
        if operation is not None:
            parsed_body: Any = None
            if resp_body:
                try:
                    parsed_body = json.loads(resp_body)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    parsed_body = None
            findings = check_response(operation, status_code, parsed_body)
            self._report.results.append(
                ProbeResult(
                    operation_id=operation.operation_id,
                    method=operation.method,
                    path=operation.path,
                    request_url=url,
                    status_code=status_code,
                    body=parsed_body,
                    findings=findings,
                )
            )
            self._report.operations_attempted += 1
            if status_code is not None and status_code < 400:
                self._report.operations_succeeded += 1
            self._report.findings.extend(findings)

        return status_code, resp_headers, resp_body, findings

    def report(self) -> DriftReport:
        """The `DriftReport` accumulated across all requests handled so far."""
        return self._report


class _ProxyHTTPHandler(BaseHTTPRequestHandler):
    """Thin `http.server` adapter delegating to a `ValidationProxyService`."""

    service: ValidationProxyService  # set by `make_handler`
    protocol_version = "HTTP/1.1"

    def _handle(self) -> None:
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else b""
        headers = {k: v for k, v in self.headers.items() if k.lower() != "content-length"}
        status, resp_headers, resp_body, _findings = self.service.handle_request(
            self.command, self.path, headers, body
        )
        self.send_response(status)
        for key, value in resp_headers.items():
            if key.lower() in ("content-length", "transfer-encoding", "connection"):
                continue
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(resp_body)))
        self.end_headers()
        if resp_body:
            self.wfile.write(resp_body)

    def do_GET(self) -> None: self._handle()
    def do_POST(self) -> None: self._handle()
    def do_PUT(self) -> None: self._handle()
    def do_PATCH(self) -> None: self._handle()
    def do_DELETE(self) -> None: self._handle()

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: D401 - quiet by default
        pass


def make_handler(service: ValidationProxyService) -> type:
    """Bind a `ValidationProxyService` instance to a fresh handler class."""
    return type("_BoundProxyHTTPHandler", (_ProxyHTTPHandler,), {"service": service})


def run_proxy_server(service: ValidationProxyService, host: str = "0.0.0.0", port: int = 8080) -> ThreadingHTTPServer:
    """Start a blocking (until KeyboardInterrupt) stdlib HTTP proxy server.

    Cost: NETWORK - only called from the explicit `forseti mock proxy` CLI
    command, never implicitly.
    """
    server = ThreadingHTTPServer((host, port), make_handler(service))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return server
