# Asgard implementation packets

**ELI5:** Produce all the findings as before, then give agents a shorter index into the complete report. Two similar messages in different places still refer to two separate findings.

**Status:** implementation specification. Follow [local scope](README.md), LEX-01, KAI-01 archive and the [qualification manifest](../../../../GAIA/_Docs/Planning/Astra_TokenReduction/09-Qualification-Manifest.md). Asgard owns diagnostic correctness; the host owns command execution, artifact permissions and model-facing delivery. No analyzer, rule, severity or suppression policy is weakened for a token budget.

## ASG-01 — exact report adapter, starting with Forseti

**Prerequisites:** LEX-01 report/source identity and error encodings. Fake archive references permit implementation before KAI-01; production compact delivery requires a verified callable recovery adapter.

| Existing file | Role |
|---|---|
| `Asgard/Forseti/Reporting/models/finding_models.py` | Existing canonical `Finding`, coordinates, suppression state, `ReportSummary` and `ReportEnvelope`; adapt these rather than invent a competing analyzer model. |
| `Asgard/Forseti/Reporting/services/reporter_service.py` | Existing reporters sort findings and serialize complete JSON; preserve those external formats and behavior. |
| `Asgard/Forseti/Reporting/services/finding_adapter_service.py` | Existing validator-to-finding mapping; keep analysis identity and source locations intact. |
| `Asgard_Test/tests_Forseti/L0_Mocked/Reporting/test_reporters.py` | Existing exact reporter and summary checks remain independent regression evidence. |

**Proposed files:** `Asgard/Reporting/context_report.py`, `Asgard/Forseti/Reporting/services/context_report_adapter.py`, `Asgard_Test/tests_Reporting/L0_Mocked/test_context_report.py`, `Asgard_Test/tests_Forseti/L0_Mocked/Reporting/test_context_report_adapter.py`.

1. Define a generic protected original report record `{schema_version, report_id, original_digest, tool, tool_version, ruleset_version, source_snapshot_digest, completion, original_artifact_ref, findings}`. Completion is `complete`, `partial` or `unsupported`; absent source-version evidence remains explicit, never guessed from current disk.
2. Each record in `findings` contains `{finding_id, original_ordinal, original_record_ref, rule_id, severity, coordinates, message, suppressed, suppression_reason}` and retains access to the complete original record including rationale/remediation. A finding ID is scoped to immutable report identity plus original ordinal, not message text; repeated identical entries retain separate IDs.
3. For JSON originals, `original_record_ref` is an RFC 6901 pointer into the immutable archived JSON plus its digest; host expansion first verifies the digest and returns the exact record. Original byte retrieval remains available when serialization whitespace/order matters. Other report formats use verified byte ranges; do not claim JSON reserialization is byte-identical.
4. Implement a pure Forseti adapter taking the canonical findings, original serialized report, source snapshot and archive reference. It never reruns validation or reads current source to retrofit missing source identity. Preserve the original `JsonReporter` output as the machine-readable artifact.
5. Archive completion must be acknowledged before a model-facing compact response claims full recovery. An unavailable archive means ordinary existing report delivery plus explicit recovery-unavailable status; the analyzer's command result is unaffected.

**Normative fixture:** the complete Forseti report has two unsuppressed findings with the same rule/message at `api.yaml:10` and `api.yaml:40`, plus one suppressed finding. IDs `report-1/0`, `report-1/1`, `report-1/2` remain distinct; expansion of `/findings/1` returns the second complete record, including its own remediation. Summary remains two active errors and one suppressed entry. Changing `api.yaml` after analysis does not change the archived locations; it marks current-source use stale.

**Decisive checks:** complete JSON unchanged, distinct same-text findings, suppression count preserved, exact record/digest expansion, absent source version, partial analysis and archive failure. Run in the authorized Python test environment: `python -m pytest Asgard_Test/tests_Reporting/L0_Mocked/test_context_report.py Asgard_Test/tests_Forseti/L0_Mocked/Reporting/test_context_report_adapter.py Asgard_Test/tests_Forseti/L0_Mocked/Reporting/test_reporters.py`.

## ASG-02 — bounded compact views that retain every finding identity

**Prerequisites:** ASG-01; KAI-01 for end-to-end expansion. KAI-02 handles final tool-result interception; Asgard never replaces shell pipeline bytes.

**Proposed files:** `Asgard/Reporting/context_view.py`, `Asgard_Test/tests_Reporting/L0_Mocked/test_context_view.py`. Existing formatters remain available unchanged.

1. Define `build_context_view(report, budget) -> view` as a deterministic pure presentation function. A group key is `(rule_id, severity, exact message, suppression state)`; members retain their original IDs, locations and original order through paged record references. Similar wording alone is not an equivalence rule.
2. View output is `{report_id, source_snapshot_digest, completion, totals, groups, omitted_groups, omitted_findings, recovery_ref}`. Each rendered group provides a representative exact message/location, member count and a reference resolving its complete ordered membership. The complete group/member index is an artifact, not an unbounded inline list.
3. Order blocking active findings before other active findings and then suppressed findings; preserve stable original order inside each priority. Do not fabricate a numeric severity when the producer has no equivalent. The initial budget can omit groups only with exact omitted counts and recovery references; it can never omit global blocking/error status.
4. Count every rendered byte/estimated token, including IDs, metadata and recovery instructions, through the host's budget contract. If mandatory status/recovery metadata alone exceeds the requested view budget, return an explicit budget-unsatisfied result to the host for ordinary delivery; never truncate identity or claim the budget was met.
5. Use independent product repair tasks for quality/cost evaluation. A successful unit test for the renderer does not qualify issue discovery by a model.

**Normative fixture:** three unique active error groups exist but the budget fits only one. Expected view has all three errors in totals, one rendered group, `omitted_groups:2`, exact omitted finding count, failure status and callable complete-report recovery. Expanding each group reconstructs all original member IDs, including the error hidden in the middle of the report. A report containing only unsupported checks is `unsupported`, not zero-error success.

**Decisive checks:** unique-error overflow, duplicate locations, unsupported severity, budget smaller than required envelope, interrupted report and a changed source digest. Run `python -m pytest Asgard_Test/tests_Reporting/L0_Mocked/test_context_view.py`. Also retain the existing CLI exit-code tests at `Asgard_Test/tests_Heimdall/L0_Mocked/test_cli_fail_closed_exit.py` when adapting that producer.

## ASG-03 — additional producers and host registration

**Prerequisites:** ASG-01/02 and host capability manifests proving recovery availability. Each producer is a separate implementation slice; unsupported formats keep their original delivery.

**Existing entry points:** `Asgard/Heimdall/cli/handlers/_base.py` handles report output; `Asgard/Heimdall/cli/common/output_args.py` exposes formats; `Asgard/Freya/cli/_formatters.py` dispatches presentation; `Asgard/Verdandi/cli/handlers_analysis.py` owns analysis presentation. Read each actual structured result before adding its adapter.

**Proposed files:** `Asgard/Reporting/context_adapters.py`, `Asgard_Test/tests_Reporting/L0_Mocked/test_context_adapters.py`, `_Docs/Planning/Astra_TokenReduction/Producer-Support.md` in the implementing change.

1. Register an explicit adapter key `(producer, report_schema_version)` mapping to a pure complete-report adapter; unknown combinations return unsupported. Document per-field mappings, actual source-version availability, count semantics and report completion semantics for each supported producer.
2. Start with one structured result family per producer and frozen input/output fixtures. Never infer completion from formatted human prose or infer exact source relationships from same-name symbols.
3. Give the host adapter the complete report and compact-view function. The host checks recovery grants, archives original bytes and performs model-facing interception; normal CLI/JSON/SARIF consumers retain their existing format and exit code.
4. Add cross-product QUAL-01 tasks proving important findings remain discoverable and repairs pass unchanged independent checks. Costs include all expansions and any duplicated report construction.

**Normative fixture:** an unregistered producer version yields `{supported:false, reason:"UNSUPPORTED_REPORT_SCHEMA"}` and ordinary original delivery; it does not receive an inferred success summary. A registered version with missing required completion metadata is partial and cannot qualify automatic compact delivery.

**Decisive checks:** unsupported-version fallback, CLI/JSON consumers unchanged, exact source identity retained and full report recovery after handoff. Run `python -m pytest Asgard_Test/tests_Reporting/L0_Mocked/test_context_adapters.py` plus the existing reporter/CLI tests for each changed producer. Completion is the documented tested support matrix, not universal report coverage.
