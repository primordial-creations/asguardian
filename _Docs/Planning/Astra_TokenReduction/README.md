# Asgard — compact diagnostics with complete evidence

**ELI5:** Asgard can give agents precise computed findings instead of pages of repeated tool output. The agent can open the original report whenever a finding needs more explanation, and all the normal checks still run.

**Status:** planned producer/adapter work. [Suite plan](../../../../GAIA/_Docs/Planning/Astra_TokenReduction/README.md) and [shared result contract](../../../../GAIA/_Docs/Planning/Astra_TokenReduction/01-Shared-Command-And-Context-Contract.md) define interoperability.

**Design basis:** [repetition can be reduced without repeating the analysis](../../../../GAIA/_Docs/Planning/Astra_TokenReduction/05-First-Principles-Design.md), but the original findings and their locations must remain exact and accessible. Asgard therefore separates complete diagnostic production from the shorter view shown to an agent.

## Existing owners

Use [Heimdall](../../../Asgard/Heimdall/README.md) for source diagnostics, [Forseti](../../../Asgard/Forseti/README.md) for contracts, [Freya](../../../Asgard/Freya/README.md) for UI/web evidence and [Verdandi](../../../Asgard/Verdandi/README.md) for measured performance evidence. Asgard supplies analysis; the agent host owns model context and shell execution.

## Work packages

Use the [implementation packets](01-Implementation-Packets.md) for the initial report family, full/compact finding schemas and formatter tests, together with the [SOL guide](../../../../GAIA/_Docs/Planning/Astra_TokenReduction/07-SOL-Execution-Guide.md).

1. **Structured finding envelopes.** Preserve rule ID, severity, affected source/range, source revision, tool version, complete count and exact diagnostic. Mark uncertain/unsupported checks and partial runs explicitly.
2. **Original-report references.** Let the host archive full reports or refer to an existing protected artifact. Expose stable offsets/record IDs for exact expansion; keep machine-readable reports intact for their downstream consumers.
3. **Compact diagnostic views.** Group repeated findings in the model-facing view with occurrence counts and recovery links. Keep all distinct failures and blocking conditions; do not change analysis scope or suppress warnings solely to improve a token counter.
4. **Connect code context.** Link diagnostics and contract changes to the versioned evidence identity shared by dependency retrieval, repository maps and language operations. Language-service references can help locate a fix, while Asgard retains its own independent validation outcome.
5. **Qualify both views.** Product-owned suites compare full versus compact reports for issue discovery, successful repair, regressions and end-to-end cost. Keep unchanged analysis/test commands so savings are attributable to presentation and retrieval.

## Acceptance / dependencies

Prove that every compact finding expands to its exact original and that important middle-of-report context remains recoverable. Test duplicate messages with different locations, stale source after analysis, malformed reports, unsupported checks and interrupted scans.

Adopt Lexicon envelopes through an adapter and run the [suite qualification](../../../../GAIA/_Docs/Planning/Astra_TokenReduction/02-Qualification-And-Rollout.md) through existing product/Hercules integration. Source-analysis correctness and required validation coverage must not be reduced to hit a budget.
