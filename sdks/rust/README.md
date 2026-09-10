# gaia-asgard-sdk (candidate 0.1.0)

Rust1.96 Unix asynchronous process client. Linux is the qualification platform;
other Unix platforms remain unqualified. Requires a live Tokio runtime and a
separately installed/pinned Asguardian engine; no HTTP, browser or engine import.

Client::new takes absolute executable argv and Options::new(engine_version).
Use the engine Python with `-I -m Asgard.sdk_protocol`. scan takes Request::new
(authorized_root,target) and a CancellationToken. Request fields are explicit;
set a host correlation_id when correlating concurrent scans. Default profile is
quality.file-length. Only advertised profiles are accepted. Returned serde_json
values preserve owner fields; complete=true/state=complete establish completion,
not an empty findings array. Valid exit1 findings/incomplete results are retained.

Timeout spans handshake and scan. stdout/stderr are separately bounded; stderr
is discarded. Cancellation or dropping an operation future cancels its background
process task. close cancels all active tasks and waits for cleanup; await it
before shutting down Tokio. Dropping Client signals shutdown but cannot await it.
Process groups are killed and direct children reaped. Host supervision is needed
for hostile children escaping their group. Host authorization and quiescent
snapshots are required; this is not a filesystem sandbox. No automatic retries.
Error.code distinguishes request/protocol/version, cancellation/close/timeout,
output limits, owner and process failures; Error.response retains owner errors.

Crate publication is disabled until distribution approval/configuration. Controlled
registry qualification is not the durable channel. Full profile coverage, shared
four-language conformance, Lexicon bridges and application migrations are pending.
