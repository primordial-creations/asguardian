from __future__ import annotations

import json
import math
import os
from pathlib import Path
import selectors
import signal
import subprocess
import threading
import time
from typing import Any, Sequence
import uuid


class ScanError(Exception):
    def __init__(self, code: str, response: dict[str, Any] | None = None):
        super().__init__(code)
        self.code = code
        self.response = response


class Client:
    """POSIX process client. The host authorizes targets and supplies the engine.

    A scan negotiates capabilities first; both processes share one deadline.
    Cancellation uses a threading.Event. close interrupts active operations.
    Engine stderr is bounded and discarded; errors never include credentials/logs.
    """

    def __init__(self, command: Sequence[str], *, engine_version: str,
                 timeout: float = 120, max_output_bytes: int = 20 * 1024 * 1024):
        if os.name != "posix":
            raise ValueError("This client currently requires POSIX process groups")
        if isinstance(command, (str, bytes)) or not command or not all(
            isinstance(item, str) and item and "\0" not in item for item in command
        ) or not Path(command[0]).is_absolute():
            raise ValueError("command must be argv with an absolute executable")
        if not isinstance(engine_version, str) or not engine_version:
            raise ValueError("an installed engine version pin is required")
        if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        if type(max_output_bytes) is not int or max_output_bytes < 1024:
            raise ValueError("max_output_bytes must be an integer >= 1024")
        self._command = tuple(command)
        self._version = engine_version
        self._timeout = timeout
        self._limit = max_output_bytes
        self._closed = threading.Event()
        self._lock = threading.Lock()
        self._active: set[subprocess.Popen] = set()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @staticmethod
    def _kill(process):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def close(self):
        with self._lock:
            self._closed.set()
            for process in self._active:
                self._kill(process)
                process.wait()

    def _check(self, deadline, cancel):
        if self._closed.is_set():
            raise ScanError("closed")
        if cancel is not None and cancel.is_set():
            raise ScanError("cancelled")
        if time.monotonic() >= deadline:
            raise ScanError("timeout")

    def _invoke(self, request, deadline, cancel):
        self._check(deadline, cancel)
        raw = json.dumps(request, allow_nan=False).encode()
        if len(raw) > 65536:
            raise ScanError("request_too_large")
        with self._lock:
            self._check(deadline, cancel)
            try:
                process = subprocess.Popen(self._command, stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            except OSError as error:
                raise ScanError("engine_unavailable") from error
            self._active.add(process)
        output = bytearray()
        sizes = {"stdout": 0, "stderr": 0}
        pending = memoryview(raw)
        try:
            with selectors.DefaultSelector() as selector:
                for stream, name in ((process.stdout, "stdout"), (process.stderr, "stderr")):
                    os.set_blocking(stream.fileno(), False)
                    selector.register(stream, selectors.EVENT_READ, name)
                os.set_blocking(process.stdin.fileno(), False)
                selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
                while selector.get_map() or process.poll() is None:
                    self._check(deadline, cancel)
                    for key, _ in selector.select(min(0.05, max(0, deadline - time.monotonic()))):
                        if key.data == "stdin":
                            try:
                                written = os.write(key.fd, pending)
                                pending = pending[written:]
                            except BrokenPipeError:
                                pending = pending[:0]
                            if not pending:
                                selector.unregister(key.fileobj)
                                key.fileobj.close()
                            continue
                        chunk = os.read(key.fd, 65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        sizes[key.data] += len(chunk)
                        if sizes[key.data] > self._limit:
                            raise ScanError("output_limit")
                        if key.data == "stdout":
                            output.extend(chunk)
            self._check(deadline, cancel)
            return self._decode(output, process.returncode, request)
        finally:
            # Also kill descendants which kept pipes open after the parent exited.
            with self._lock:
                self._kill(process)
                process.wait()
                self._active.discard(process)
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()

    def _decode(self, output, exit_code, request):
        try:
            response = json.loads(output, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            if not isinstance(response, dict):
                raise ValueError()
            if type(response.get("protocol_version")) is not int or response["protocol_version"] != 1:
                raise ScanError("version_mismatch")
            if response.get("engine_version") != self._version:
                raise ScanError("engine_version_mismatch")
            if response.get("correlation_id") != request["correlation_id"]:
                raise ValueError()
            if not isinstance(response.get("scan_id"), str) or not response["scan_id"]:
                raise ValueError()
            if any(type(response.get(key)) is not bool for key in ("complete", "truncated")):
                raise ValueError()
            if not isinstance(response.get("findings"), list) or not isinstance(response.get("errors"), list):
                raise ValueError()
            if any(not isinstance(item, dict) for item in response["findings"] + response["errors"]):
                raise ValueError()
            state = response.get("state")
            if state == "error" and exit_code == 2 and not response["complete"] and response["errors"]:
                raise ScanError("engine_error", response)
            if request["operation"] == "handshake":
                valid = (state == "ready" and exit_code == 0 and response["complete"]
                    and not response["truncated"] and not response["errors"] and not response["findings"])
                caps = response.get("capabilities", {})
                valid = valid and isinstance(caps, dict) and isinstance(caps.get("profiles"), list)
                valid = valid and caps.get("transport") == "single-request-stdio"
            else:
                valid = ((state == "complete" and response["complete"] and not response["truncated"]
                    and not response["errors"] and exit_code == (1 if response["findings"] else 0))
                    or (state == "incomplete" and not response["complete"] and exit_code == 1
                        and (response["truncated"] or response["errors"])))
            if not valid:
                raise ValueError()
            return response
        except (ValueError, TypeError, UnicodeError) as error:
            raise ScanError("malformed_response") from error

    def handshake(self, *, cancel: threading.Event | None = None):
        return self._invoke(dict(protocol_version=1, operation="handshake",
            correlation_id=str(uuid.uuid4())), time.monotonic() + self._timeout, cancel)

    def scan(self, *, authorized_root: str, target: str, profile: str = "quality.file-length",
             max_findings: int = 1000, correlation_id: str | None = None,
             cancel: threading.Event | None = None):
        deadline = time.monotonic() + self._timeout
        correlation = str(uuid.uuid4()) if correlation_id is None else correlation_id
        if not isinstance(correlation, str) or not 1 <= len(correlation) <= 256:
            raise ValueError("correlation_id must contain 1–256 characters")
        hello = self._invoke(dict(protocol_version=1, operation="handshake",
            correlation_id=correlation), deadline, cancel)
        if profile not in hello["capabilities"]["profiles"]:
            raise ScanError("unsupported_operation")
        return self._invoke(dict(protocol_version=1, operation="scan", correlation_id=correlation,
            profile=profile, authorized_root=authorized_root, target=target,
            max_findings=max_findings), deadline, cancel)
