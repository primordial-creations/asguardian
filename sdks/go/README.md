# Asgard Go process SDK (unreleased)

Module: github.com/primordial-creations/asguardian/sdks/go. Go >=1.22, no dependencies.
Linux/Darwin process-group implementation; Linux is the qualification platform.
Other platforms currently return an explicit unsupported configuration error.

New takes absolute executable argv and Options{EngineVersion: "1.2.3.dev719"}.
Use the pinned independent engine Python with `-I -m Asgard.sdk_protocol`.
Scan takes context.Context and Request{AuthorizedRoot: ..., Target: ...}.
Caller cancellation and the total handshake/scan timeout produce typed Error
codes cancelled/timeout. Close cancels active operations and drains them.
Response retains JSON owner fields (numbers are json.Number); complete=true and
state=complete are required before treating results as complete. Valid exit1
findings and incomplete results are preserved. Error.Response retains owner
errors. There are no retries, shell interpolation, implicit executable search,
engine imports or SDK credentials. stdout/stderr each have bounded byte limits;
stderr is discarded. Children must stay in their process group; escaping hostile
processes require host supervision. Hosts authorize targets and supply quiescent
snapshots; this is not an authorization service or filesystem sandbox.

Initial profiles: quality.file-length and security.hotspots. Other audited profiles, bridges and
application migrations remain pending. Immutable local module proxy qualification
is not proof of publication or the intended durable distribution channel.

Request.MaxFindings is optional (*int): nil selects 1000, while explicit zero is
sent to the engine and rejected. This corrects the unreleased candidate API;
existing candidate users must take an int address when supplying a limit.
Pipe draining uses the same operation deadline, not a separate shorter cutoff.

security.hotspots reports manual review candidates, preserving owner priority,
review status and guidance; it does not turn them into confirmed vulnerabilities.
Strict parse/read/configuration failures stay incomplete. Additional operations
used by Kairos/Hercules still require qualification and migration.

Optional Request.LogicalRoot (*string) supplies an original absolute path label for a physical snapshot.
Only advertised logical_paths profiles support it; unsupported mappings fail.
The label affects findings/context matching only, never filesystem access.
Omission preserves existing scan behavior. Host authorization/capture remain required.
