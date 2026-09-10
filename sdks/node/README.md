# @gaia/asgard-sdk (candidate 0.1.0)

Dependency-free Node >=22 POSIX client. CommonJS and ESM share one implementation;
TypeScript declarations ship for both. Install the pinned Asguardian engine
separately; no browser/engine installation occurs through this package.

```js
import { Client } from '@gaia/asgard-sdk';
const client = new Client(['/opt/asgard/bin/python', '-I', '-m', 'Asgard.sdk_protocol'],
  { engineVersion: '1.2.3.dev719' });
try {
  const result = await client.scan({ authorizedRoot: '/authorized/snapshot', target: '/authorized/snapshot/source' });
  // Only complete=true/state=complete establishes completion; inspect findings.
  console.log(result);
} finally { await client.close(); }
```

The host authorizes the target and supplies a quiescent snapshot. Path checks
are not a filesystem sandbox. Protocol1 supports quality.file-length and security.hotspots;
full audited scan profiles and application migrations remain pending.

scan negotiates capabilities and executes under one timeoutMs budget. Optional
AbortSignal cancels work. close interrupts active work and awaits process pipe
closure. Process groups are killed on failure/exit, including child processes
which retain pipes; children escaping the group require host supervision.
Windows support is pending. There are no retries, shell interpolation or implicit
executable searches. stdout and stderr each have maxOutputBytes bounds; stderr
is discarded and never attached to errors. ScanError.code distinguishes timeout,
cancelled, closed, output_limit, engine_unavailable, malformed_response,
version_mismatch, engine_version_mismatch, unsupported_operation and engine_error
(with owner response). Transport/cleanup failures remain explicit errors.
Valid exit1 findings and incomplete results are returned without converting them
to clean defaults. Candidate artifact/channel and consumer rollout remain gated.

security.hotspots reports manual review candidates, preserving owner priority,
review status and guidance; it does not turn them into confirmed vulnerabilities.
Strict parse/read/configuration failures stay incomplete. Additional operations
used by Kairos/Hercules still require qualification and migration.
