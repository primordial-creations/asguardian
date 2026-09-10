"""Versioned, single-request process transport around the Asgard engine.

Run with ``python -m Asgard.sdk_protocol``. Host authorization is required;
this transport is not a sandbox for concurrently hostile filesystem changes.
"""

from __future__ import annotations

import contextlib
import importlib.metadata
import json
from pathlib import Path
import sys
import time
import uuid

PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 65536
PROFILE = "quality.file-length"


def engine_version():
    try:
        return importlib.metadata.version("asguardian")
    except importlib.metadata.PackageNotFoundError:
        return None  # Source execution is diagnostic, not an installed version pin.


def target_path(request):
    """Check the host-supplied root and target without expanding their scope."""
    root, target = Path(request["authorized_root"]), Path(request["target"])
    if not root.is_absolute() or not target.is_absolute():
        raise ValueError("authorized_root and target must be absolute")
    if ".." in root.parts or ".." in target.parts:
        raise ValueError("parent traversal is not supported")
    # Check every lexical component; resolving first would conceal symlinks.
    for candidate in (root, target):
        if any(part.is_symlink() for part in (candidate, *candidate.parents)):
            raise ValueError("target and root ancestors must not be symlinks")
    resolved_root, resolved_target = root.resolve(strict=True), target.resolve(strict=True)
    if not resolved_target.is_relative_to(resolved_root):
        raise ValueError("target is outside authorized_root")
    if not resolved_root.is_dir() or not resolved_target.is_dir():
        raise ValueError("root and target must be directories")
    return resolved_target


def respond(request):
    started = time.monotonic()
    response = {
        "protocol_version": PROTOCOL_VERSION,
        "engine_version": engine_version(),
        "scan_id": str(uuid.uuid4()),
        "correlation_id": None,
        "state": "error",
        "complete": False,
        "truncated": False,
        "findings": [],
        "errors": [],
    }
    try:
        if not isinstance(request, dict):
            raise ValueError("request must be an object")
        correlation = request.get("correlation_id")
        if not isinstance(correlation, str) or not 1 <= len(correlation) <= 256:
            raise ValueError("correlation_id must contain 1–256 characters")
        response["correlation_id"] = correlation
        if type(request.get("protocol_version")) is not int or request["protocol_version"] != PROTOCOL_VERSION:
            response["errors"] = [{"code": "version_mismatch"}]
            return response, 2
        operation = request.get("operation")
        if operation == "handshake":
            response.update(state="ready", complete=True, capabilities={
                "profiles": [PROFILE], "transport": "single-request-stdio",
                "progress": False, "remote": False, "max_request_bytes": MAX_REQUEST_BYTES,
                "target_policy": "host-authorized-quiescent-directory-no-symlinks",
            })
            return response, 0
        if operation != "scan" or request.get("profile") != PROFILE:
            response["errors"] = [{"code": "unsupported_operation"}]
            return response, 2
        if set(request) - {"protocol_version", "correlation_id", "operation", "profile",
                           "authorized_root", "target", "max_findings"}:
            raise ValueError("unknown scan request fields")
        limit = request.get("max_findings", 1000)
        if type(limit) is not int or not 1 <= limit <= 10000:
            raise ValueError("max_findings must be an integer from 1 to 10000")
        target = target_path(request)
        # Lazy engine import keeps handshake independent from optional engine tools.
        from Asgard.Bragi.Quality.services.file_length_analyzer import FileAnalyzer

        result = FileAnalyzer().analyze(target, strict_io=True)
        response["findings"] = [finding.model_dump(mode="json") for finding in result.violations[:limit]]
        response["truncated"] = len(result.violations) > limit
        response["errors"] = [{"code": "scan_io_failure", "message": error}
                              for error in result.analysis_errors]
        response["complete"] = result.analysis_complete and not response["truncated"]
        response["state"] = "complete" if response["complete"] else "incomplete"
        response["summary"] = {
            "total_files_scanned": result.total_files_scanned,
            "files_exceeding_threshold": result.files_exceeding_threshold,
            "default_threshold": result.default_threshold,
            "extension_thresholds": result.extension_thresholds,
        }
        return response, (0 if response["complete"] and not response["findings"] else 1)
    except (ValueError, KeyError, TypeError, OSError) as error:
        response["errors"] = [{"code": "invalid_request", "message": str(error)}]
        return response, 2
    except ImportError:
        response["errors"] = [{"code": "engine_unavailable"}]
        return response, 2
    except Exception as error:
        response["errors"] = [{"code": "engine_error", "type": type(error).__name__}]
        return response, 2
    finally:
        response["elapsed_seconds"] = time.monotonic() - started


def main():
    raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    try:
        if len(raw) > MAX_REQUEST_BYTES:
            raise ValueError("request too large")
        request = json.loads(raw)
    except (ValueError, UnicodeError):
        request = None
    with contextlib.redirect_stdout(sys.stderr):
        response, code = respond(request)
    print(json.dumps(response, allow_nan=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
