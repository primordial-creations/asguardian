# gaia-asgard-sdk (candidate 0.1.0)

Dependency-free Python >=3.11 POSIX process client. Install the separately pinned
Asguardian engine in its own environment; this SDK does not install engine tools
or browsers. Windows support is pending, not emulated with incomplete cleanup.

```python
from asgard_sdk import Client

with Client(["/opt/asgard/bin/python", "-m", "Asgard.sdk_protocol"],
            engine_version="YOUR_INSTALLED_ENGINE_VERSION") as scanner:
    result = scanner.scan(authorized_root="/authorized/snapshot",
                          target="/authorized/snapshot/source")
    if result["complete"]:
        print(result["findings"])
    else:
        print("Incomplete scan", result["errors"])
```

The host must authorize targets and provide a quiescent snapshot; containment
checks do not replace authorization or a filesystem sandbox. Only the engine's
advertised profiles are supported. Currently quality.file-length and security.hotspots are implemented;
remaining audited scans and consumer migrations are pending. No remote service,
implicit executable search, shell interpolation or automatic retry is used.

Each scan uses one total timeout across handshake and execution, with separate
stdout/stderr byte limits. A threading.Event passed as cancel interrupts work.
ScanError.code distinguishes cancelled, closed, timeout, output_limit,
engine_unavailable, engine_version_mismatch, version_mismatch, malformed_response,
unsupported_operation and engine_error (whose response retains the owner error).
Valid nonzero findings and incomplete responses are returned intact. close kills
active process groups and waits for direct children; descendants must not escape
the process group. This is lifecycle management, not hostile-process supervision.
Do not call blocking methods on an event-loop thread. Use host thread execution
and signal cancellation explicitly when an async host is cancelled.

Source-execution engines with null version metadata are rejected. Candidate
artifacts are not released; intended channel and engine compatibility pins must
be qualified before rollout. Existing CLI consumers remain unchanged.

security.hotspots reports manual review candidates, preserving owner priority,
review status and guidance; it does not turn them into confirmed vulnerabilities.
Strict parse/read/configuration failures stay incomplete. Additional operations
used by Kairos/Hercules still require qualification and migration.
