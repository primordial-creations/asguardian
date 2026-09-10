# Wiring consumer repositories into the quality gate

The reusable workflow is tracked on main. The revised workflow must be committed
and made reachable before consumers select its SHA; local source tests do not
prove a consumer Actions run. Existing native CI gates remain required.

## Installed command names

Use `asguardian` for the unified CLI, `asguardian-dashboard` for the dashboard,
and `asguardian-mcp` for the MCP server. The `asgard`, `asgard-dashboard`, and
`asgard-mcp` spellings are compatibility aliases to the same package entrypoints.
Module commands such as `heimdall` remain supported. The reusable gate invokes
the unified CLI with its own Python interpreter, explicitly importing Asgard
from the verified checkout containing the gate helper. It does not resolve a
`heimdall` console script through PATH. Python environment overrides and implicit
working-directory imports are disabled for that subprocess; installed runtime
dependencies remain available, including the interpreter's user site.

The source tests load the declared entrypoints and exercise real help and
argument parsing without starting servers or analyzers. Trusted push CI also
checks the installed console scripts outside the repository directory. Actual
consumer installation and execution on arc-x86 remain required.

The unified aliases expose the local-source Hercules adapter as
`scan --contract-version hercules-l13/v1 --target DIR --output FILE`. The
version flag is required. The target must be an existing local directory;
URLs and system names fail with scanner execution code 3. Hercules must inject
its checked-out repository directory for this provider. `--severity` applies
a final minimum threshold to normalized findings from every domain. The
adapter does not advertise custom exclusions because Heimdall's aggregate
domains do not implement them consistently.

Successful v1 output is UTF-8 JSONL with zero to 500
`HERCULES_FINDINGS:` objects followed by one `HERCULES_SCAN:` completion
object. The producer enforces Hercules's document, record, and string routing
bounds against both compact provider output and Hercules's reserialized
records, with headroom for the captured test log, before atomically replacing
the output. It fails instead of truncating findings. It also refuses missing
domain reports, inconsistent native counts, symlinked or unreadable analyzer
inputs, and inputs that hit Heimdall's injection-analysis byte or line caps,
so `clean` means all enabled local static domains completed within those
limits. Dependency advisories use the bundled local database only; the adapter
disables network lookups.

The older unversioned/legacy invocation shapes used by language packages are
not implemented by this provider. Deploy the Asgard adapter only with a
Hercules revision that injects `HERCULES_ASGUARDIAN_CONTRACT_VERSION` as
`hercules-l13/v1`, passes a local checkout directory as the target, validates
the same bounds, and routes all accepted records without truncation.

## Source identity

Pin each caller's `uses:` to a reviewed full 40-character commit SHA. The gate
checks out and verifies `job.workflow_repository` at `job.workflow_sha`, so the
installed analyzer belongs to that same workflow revision. It never uses
`github.sha`, `github.workflow_sha`, or a floating `main` checkout for the analyzer.
GitHub documents that the `github` context belongs to the caller, while the
[`job.workflow_*` properties identify the called workflow](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#job-context).

GitHub Enterprise Server does not expose these job identity properties. There,
set `asguardian-ref` to the same full SHA used in `uses:`; branch/tag/short SHA
inputs are rejected. If job identity is available, a differing explicit input is
rejected. GHES cannot independently verify equality to the outer `uses:` ref;
that remains a caller review requirement. Missing identity and missing fallback
fail before either checkout. An optional `asguardian-token` secret can supply
read access to private analyzer source; the default caller token may lack that
cross-repository permission. Credentials are not persisted in either checkout.

The caller is checked out under `caller/`, and analyzer source under
`.asguardian-src/`. Scan paths are confined to the caller checkout, including
resolved symlinks. This prevents analyzer fixture projects from being selected
when the caller lacks a manifest. Each job targets one explicit project root;
use a job per project for monorepositories.

## Project and tool contract

| Language | Required inputs and committed files |
| --- | --- |
| Node | `package.json`, npm lockfile, and locked devDependencies; selected `node-lint` needs local ESLint config, selected `node-typecheck` needs `tsconfig.json` and TypeScript |
| Rust | `Cargo.toml`, exact `rust-toolchain` release; `rust-audit` additionally requires `Cargo.lock` and exact `cargo-audit-version` |
| Go | `go.mod` supplies the Go toolchain; `go-vuln` additionally requires exact `govulncheck-version` |

Empty `checks` selects all checks for the language. Set an explicit subset for
projects without TypeScript or another intentionally unused check. Unknown,
cross-language, empty-list entries and duplicate checks fail configuration.
Requested checks cannot report missing tools/configuration as a passing result.
The runner checks report identity, errors, unavailable tools, subprocess status
and JSON validity, and attempts every selected check before failing the job.
The scan path must be a nonempty string and the error count an integer; JSON
booleans or floating-point zero cannot stand in for a valid zero-error report.
Finding limits remain bounded: reaching a Node, Rust, Go vulnerability or Go formatting finding cap marks the
remaining output unverified and fails the gate, including warnings-only output.
Nonzero TypeScript/Clippy results without parsed errors also fail; startup or
manifest errors cannot become an empty successful scan.

Node installs use `npm ci --include=dev --ignore-scripts`; neither global latest
ESLint/TypeScript nor downloaded npx cache entries substitute for declared
project tools. The committed wrappers force the analyzer to use local npx
resolution after installed-binary validation. Lifecycle scripts do not run.
Projects requiring generated artifacts or native dependency install hooks need
a reviewed CI preparation path before adopting this reusable gate; a failed
install/check must not be changed to an ignored failure. This workflow currently
supports npm lockfiles, not guessed Yarn/pnpm installation commands.

For npm workspaces, `node-install-path` may point at the ancestor lockfile root,
while `scan-path` selects a member with its own manifest/config. Run `node-audit`
in a separate job targeting the lockfile root. Private registry and external
source dependencies must already have a supported authentication/preparation
path; the gate does not invent private dependency checkouts or credentials.

Rust audit installs are version-selected with `cargo install --locked`, and Go
vulnerability tooling requires an exact module release; no `latest` fallback
exists. Consumers choose reviewed supported tool versions rather than copying
an unverified release from this document. The selected Rust release is also
passed as `RUSTUP_TOOLCHAIN` to audit-tool
installation and analyzer subprocesses, taking precedence over caller
`rust-toolchain.toml` files and rustup directory overrides. Runtime Python dependencies are
installed from the selected analyzer's project metadata. They retain the
package's declared version ranges; the immutable analyzer commit is not a claim
of a fully locked Python environment or immutable vulnerability databases.

## Caller templates

Replace `REVIEWED_40_CHARACTER_SHA` with a reachable commit containing this change.
The placeholders intentionally do not masquerade as verified releases.

```yaml
jobs:
  node-quality:
    uses: primordial-creations/asguardian/.github/workflows/reusable-quality-gate.yml@REVIEWED_40_CHARACTER_SHA
    with:
      language: node
      scan-path: path/to/package
      checks: node-lint,node-typecheck
      node-version: '20'
```

For Rust, set `language: rust`, the actual Cargo project `scan-path`, an exact
`rust-toolchain: 'X.Y.Z'`, and (when selecting `rust-audit`) a reviewed
`cargo-audit-version: 'X.Y.Z'`. For Go, set `language: go`, the actual Go module
`scan-path`, and (when selecting `go-vuln`) a reviewed
`govulncheck-version: 'vX.Y.Z'`. These version placeholders must be replaced.

Candidate project roots from the initial inventory are GVR-Database (`.`),
Lexicon (`LexiconRust`, `LexiconGo`, `LexiconTypescript`), Kairos (Node roots),
Panoptes (`.` for Go), Minos (`streaming`), Hercules (`language-packages/go`),
and GAIA (`Keryx`). Revalidate each current manifest, lockfile and external
module dependency before wiring. In particular, GAIA's Lexicon path must be
materialized by its actual CI dependency contract; a local nested checkout
is not evidence that a clean runner contains that path. Talos needs a current
Node project inventory; the old Rust premise was not supported by source.

## Evidence still required for rollout

Run real consumer CI at the selected revisions for at least one Rust, Node and
Go project. Retain analyzer checkout SHA, dependency/tool versions and check
reports. Exercise a deliberate violation, missing configuration and missing
tool as failing cases, including a workspace Node project and a private-source
consumer where applicable. Confirm runner permissions, checkout access, private
package access and caller branch protection independently. Local helper tests
cover dispatch, source selection and fail-closed results; they do not establish
these external conditions or prove project quality.
