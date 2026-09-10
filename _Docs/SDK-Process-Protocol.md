# Asgard process protocol candidate v1

Entry point: `python -m Asgard.sdk_protocol`, using the separately installed
`asguardian` engine's Python executable. One bounded JSON request on stdin, EOF,
one JSON response on stdout, then process exit. Engine logs go to stderr.
No remote service is assumed. These are initial WP05 profiles, not the complete
scan API or a replacement for the concurrent Hercules L13 contract integration.

Every request requires integer `protocol_version: 1`, a nonempty string
`correlation_id` (maximum 256 characters) and `operation`. `handshake` returns
explicit capabilities. `scan` accepts `profile: "quality.file-length"` or `"security.hotspots"`,
absolute `authorized_root` and `target` directories and optional `max_findings`
(1–10000, default 1000). Unknown scan fields fail; fix/mutation flags are not
accepted. Requests are limited to 65536 bytes. The finding limit bounds returned
findings, not engine computation; clients must impose process/time/output limits.

The host must authorize the root and target before invoking the client. This
protocol verifies target containment and rejects symlink ancestors. Strict engine
discovery rejects non-excluded child symlinks and records read/traversal failures.
Existing default engine exclusions and extension thresholds apply. Targets must
be quiescent for the scan: these path checks are not an OS sandbox or protection
against hostile concurrent replacement of filesystem entries. A host scanning
mutable untrusted workspaces must supply an isolated snapshot/sandbox.

Response fields include protocol/installed engine versions, scan/correlation IDs,
elapsed seconds, state, complete, truncated, owner findings, errors and summary.
`engine_version: null` means source execution without installed distribution
metadata; it is not evidence of client/installed-engine compatibility.
State is `ready`, `complete`, `incomplete` or `error`. An empty findings array is
never proof of a clean scan without `state: complete` and `complete: true`.
Read/traversal failures retain findings already produced. Output truncation is
incomplete. Original owner finding details and threshold semantics are retained;
Lexicon neutral mappings belong in its optional adapter.

Exit 0: handshake or complete scan without findings. Exit 1: complete scan with
findings, or incomplete scan (possibly with findings). Exit 2: request/version,
unavailable-engine or engine failure. Clients must parse valid exit-1 responses.
No retries, progress stream or remote transport are currently supported. Killing
an unfinished process cannot be interpreted as a successful empty result.

`FileAnalyzer.analyze(strict_io=True)` is the owner engine seam behind this
profile. Its `analysis_complete` property asserts only absence of observed I/O
failures within the documented scan scope. Legacy default calls preserve their
I/O fallback behavior and report `io_completeness_checked: false`; they must not
be used as strict completeness evidence.

Compatibility: v1 remains an unreleased candidate until SDK/engine artifacts and
the required consumers qualify together. Existing CLI and Hercules contracts
remain supported; this module does not replace their dispatch or change their
arguments. Future profiles must be advertised explicitly and preserve their
own incomplete/tool-failure semantics. Protocol-breaking changes require a new
major protocol version; callers must reject unsupported versions.

Four lightweight owner SDKs and isolated artifact/process gates are implemented
under `sdks/` and `scripts/`. Intended channels and CI execution remain pending.

Pending: full process/input parity,
remaining Heimdall/Forseti/Freya operation inventory and profiles, missing-tool
fixtures, installed engine pin/qualification, Lexicon Scanning, Kairos/Hercules
migrations, release jobs and intended distribution-channel checks.

The security.hotspots profile reuses HotspotDetector and the CLI's .heimdall.yml
settings (test_context_enabled and strict_scan_paths), with strict validation.
Its finding_kind is security_hotspot: review_priority/review_status/guidance are
manual-review information, not confirmed vulnerability severity. Existing CLI
exit policy is unchanged; the process protocol consistently uses exit1 for any
returned findings and for incomplete analysis. SDKs parse those valid responses.

Strict hotspot scans retain successfully detected hotspots when another file
cannot be read or parsed. Invalid configuration, excluded-scope escape links and
truncation never become clean empty scans. Default language/test-context/exclusion
rules remain owner rules. No target tool execution or review-state mutation is
introduced. Legacy detector traversal/fallback compatibility remains available;
its report does not assert strict completeness. Protocol clients always opt in.

For security.hotspots, an optional logical_root absolute path label preserves
original workspace locations/context rules when a host scans a private snapshot.
The engine reads configuration and file contents ONLY from target under
 authorized_root; logical_root is never resolved, opened or used for traversal.
Relative paths within the physical target are appended to that label for findings,
parse/read diagnostics, test-context matching and strict_scan_paths regexes.
The host controls this label and remains responsible for authorization and snapshot
capture. It is not a second filesystem root or an access grant.

Handshake logical_paths lists the profiles supporting this optional behavior.
All SDKs reject an unadvertised mapping with unsupported_operation. Omitted labels
preserve existing behavior; malformed labels fail invalid_request. Other profiles
must not accept or silently ignore it. Node logicalRoot, Python logical_root,
Go Request.LogicalRoot (*string), Rust Request.logical_root (Option<String>) map
to the one owner field. Existing required engine version pins still apply.
