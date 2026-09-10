# Initial process conformance v1

process-observations-v1.json defines expected observations independently of client
responses. Each owner qualifier checks it; compare_process_sdk_conformance.py
requires all four languages, one source revision, exact engine artifact hashes
and all ten installed artifact combinations (Python wheel/sdist × engine
wheel/sdist, plus Node/Go/Rust × engine wheel/sdist).

Seven cases use the actual installed quality.file-length engine: clean, finding,
truncated, invalid/outside target, version mismatch, escaping child symlink and
explicit zero finding limit. Closed-plus-pre-cancelled checks client lifecycle
precedence without launching an engine. pipe_fixture.py is a controlled protocol
process whose child retains pipes for 0.5 seconds after parent exit; the clients
must permit draining within the operation deadline. It is not a scanner engine.

The fixture fixes three known differences: Go's explicit zero is no longer an
omitted limit (MaxFindings is now *int); Rust reports closed ahead of precancelled;
Go drains pipes under the operation deadline rather than a 200ms extra cutoff.
These are unreleased candidate corrections, not changes to a published package.

Existing per-language transport/lifecycle tests run in addition. Full malformed
wire/optional-value/error and cancellation-race parity remains open, as do other
profiles, neutral Scanning, host migrations and durable distribution. This gate
must not be presented as complete WP05 or arbitrary scanning-provider parity.

Five additional actual-engine observations cover security.hotspots: clean scan,
manual-review finding (kind/category/priority/status), Python parse failure,
unreadable UTF-8 input, and invalid configuration. Parse/read failures retain the
other successfully detected hotspot while marking the result incomplete. These
bring the shared fixture to14observations (12actual-engine plus2lifecycle cases).
