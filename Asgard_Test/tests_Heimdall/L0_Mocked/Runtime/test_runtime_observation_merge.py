"""Tests for the WS7 runtime/IAST observation schema + offline merge pipeline."""

import json

import pytest

from Asgard.Heimdall.Security.TaintAnalysis.models.taint_models import (
    TaintFlow,
    TaintFlowStep,
    TaintReport,
    TaintSinkType,
    TaintSourceType,
)
from Asgard.Heimdall.Security.runtime.ingest import (
    load_observations,
    load_observations_from_file,
    merge_runtime_observations,
)
from Asgard.Heimdall.Security.runtime.models import (
    RuntimeConfidence,
    RuntimeObservation,
    RuntimeObservationBatch,
)


def _make_static_flow(
    sink_file="app/routes.py",
    sink_line=42,
    sink_type=TaintSinkType.SQL_QUERY,
    cwe_id="CWE-89",
) -> TaintFlow:
    return TaintFlow(
        source_type=TaintSourceType.HTTP_PARAMETER,
        sink_type=sink_type,
        severity="high",
        confidence=0.6,
        confidence_bucket="possible",
        source_location=TaintFlowStep(
            file_path="app/routes.py", line_number=10, function_name="handler",
            step_type="source",
        ),
        sink_location=TaintFlowStep(
            file_path=sink_file, line_number=sink_line, function_name="handler",
            step_type="sink",
        ),
        title="Possible SQL injection",
        description="user param flows into query",
        cwe_id=cwe_id,
    )


def _make_observation(
    sink_file="app/routes.py",
    sink_line=42,
    sink_type=TaintSinkType.SQL_QUERY,
    cwe_id="CWE-89",
    trace_id="trace-1",
    confidence_marker=RuntimeConfidence.CONFIRMED_AT_RUNTIME,
) -> RuntimeObservation:
    return RuntimeObservation(
        source_type=TaintSourceType.HTTP_PARAMETER,
        source_file="app/routes.py",
        source_line=10,
        sink_type=sink_type,
        sink_file=sink_file,
        sink_line=sink_line,
        tainted_value_fingerprint="sha256:deadbeef",
        trace_id=trace_id,
        stack_frames=["handler", "build_query", "execute"],
        timestamp_in=1700000000.0,
        confidence_marker=confidence_marker,
        cwe_id=cwe_id,
        agent="pytest-mock-agent",
        language="python",
    )


class TestRuntimeObservationSchema:
    def test_requires_non_empty_sink_file(self):
        with pytest.raises(Exception):
            RuntimeObservation(
                source_type=TaintSourceType.HTTP_PARAMETER,
                source_file="a.py",
                sink_type=TaintSinkType.SQL_QUERY,
                sink_file="",
                sink_line=1,
                tainted_value_fingerprint="fp",
                trace_id="t1",
                timestamp_in=1.0,
            )

    def test_confidence_marker_defaults_to_confirmed(self):
        obs = _make_observation()
        assert obs.confidence_marker == RuntimeConfidence.CONFIRMED_AT_RUNTIME.value

    def test_timestamp_is_passed_in_not_computed(self):
        obs = _make_observation()
        assert obs.timestamp_in == 1700000000.0


class TestOfflineIngestion:
    def test_loads_bare_json_array(self):
        raw = json.dumps([_make_observation().model_dump()])
        obs = load_observations(raw)
        assert len(obs) == 1
        assert obs[0].sink_file == "app/routes.py"

    def test_loads_batch_envelope(self):
        batch = RuntimeObservationBatch(
            generated_by="test-agent", observations=[_make_observation()]
        )
        raw = batch.model_dump_json()
        obs = load_observations(raw)
        assert len(obs) == 1

    def test_loads_jsonl(self):
        o1 = _make_observation(trace_id="t1").model_dump_json()
        o2 = _make_observation(trace_id="t2", sink_line=99).model_dump_json()
        raw = f"{o1}\n{o2}\n"
        obs = load_observations(raw)
        assert len(obs) == 2
        assert {o.trace_id for o in obs} == {"t1", "t2"}

    def test_empty_input_yields_empty_list(self):
        assert load_observations("") == []

    def test_load_from_file(self, tmp_path):
        path = tmp_path / "observations.json"
        path.write_text(json.dumps([_make_observation().model_dump()]))
        obs = load_observations_from_file(path)
        assert len(obs) == 1


class TestMergeRuntimeObservations:
    def test_matching_observation_confirms_static_finding(self):
        static_flow = _make_static_flow()
        report = TaintReport(scan_path=".", files_analyzed=1)
        report.add_flow(static_flow)

        obs = [_make_observation()]
        merged = merge_runtime_observations(report, obs)

        assert merged.total_flows == 1
        confirmed = merged.flows[0]
        assert confirmed.confirmed_at_runtime is True
        assert "trace-1" in confirmed.runtime_trace_ids
        assert confirmed.origin == "static"

    def test_original_report_not_mutated(self):
        static_flow = _make_static_flow()
        report = TaintReport(scan_path=".", files_analyzed=1)
        report.add_flow(static_flow)

        merge_runtime_observations(report, [_make_observation()])

        assert report.flows[0].confirmed_at_runtime is False

    def test_runtime_only_observation_adds_new_finding(self):
        report = TaintReport(scan_path=".", files_analyzed=1)
        # No static flows at all -- e.g. a reflection-based dispatch static
        # analysis could never resolve.
        obs = [_make_observation(sink_file="app/dynamic.py", sink_line=7, cwe_id="CWE-502",
                                  sink_type=TaintSinkType.EVAL_EXEC)]

        merged = merge_runtime_observations(report, obs)

        assert merged.total_flows == 1
        new_flow = merged.flows[0]
        assert new_flow.origin == "runtime"
        assert new_flow.confirmed_at_runtime is True
        assert new_flow.sink_location.file_path == "app/dynamic.py"
        assert new_flow.sink_location.line_number == 7

    def test_absence_of_observation_never_downgrades_static_finding(self):
        static_flow = _make_static_flow()
        original_confidence = static_flow.confidence
        original_severity = static_flow.severity
        original_bucket = static_flow.confidence_bucket
        report = TaintReport(scan_path=".", files_analyzed=1)
        report.add_flow(static_flow)

        # No observations at all this run.
        merged = merge_runtime_observations(report, [])

        assert merged.total_flows == 1
        flow = merged.flows[0]
        assert flow.confirmed_at_runtime is False
        assert flow.confidence == original_confidence
        assert flow.severity == original_severity
        assert flow.confidence_bucket == original_bucket

    def test_unmatched_observation_and_matched_observation_both_handled(self):
        static_flow = _make_static_flow()
        report = TaintReport(scan_path=".", files_analyzed=1)
        report.add_flow(static_flow)

        matching_obs = _make_observation(trace_id="match-1")
        extra_obs = _make_observation(
            trace_id="extra-1", sink_file="app/other.py", sink_line=100, cwe_id="CWE-78",
            sink_type=TaintSinkType.SHELL_COMMAND,
        )

        merged = merge_runtime_observations(report, [matching_obs, extra_obs])

        assert merged.total_flows == 2
        by_origin = {f.origin: f for f in merged.flows}
        assert by_origin["static"].confirmed_at_runtime is True
        assert by_origin["runtime"].sink_location.file_path == "app/other.py"

    def test_tolerant_fallback_matches_on_cwe_when_line_diverges(self):
        static_flow = _make_static_flow(sink_line=42)
        report = TaintReport(scan_path=".", files_analyzed=1)
        report.add_flow(static_flow)

        # Runtime reports a different (resolved-frame) line but same file,
        # sink type, and CWE -- should still match via the tolerant fallback.
        obs = [_make_observation(sink_line=45)]
        merged = merge_runtime_observations(report, obs)

        assert merged.flows[0].confirmed_at_runtime is True

    def test_different_sink_type_does_not_match(self):
        static_flow = _make_static_flow(sink_type=TaintSinkType.SQL_QUERY)
        report = TaintReport(scan_path=".", files_analyzed=1)
        report.add_flow(static_flow)

        obs = [_make_observation(sink_type=TaintSinkType.SHELL_COMMAND, cwe_id="CWE-78")]
        merged = merge_runtime_observations(report, obs)

        # No match: static finding unconfirmed, new runtime-only finding added.
        assert merged.total_flows == 2
        assert merged.flows[0].confirmed_at_runtime is False
        assert any(f.origin == "runtime" for f in merged.flows)

    def test_low_confidence_marker_yields_possible_bucket_not_certain(self):
        report = TaintReport(scan_path=".", files_analyzed=1)
        obs = [_make_observation(
            sink_file="app/susp.py", sink_line=5, cwe_id="CWE-94",
            sink_type=TaintSinkType.EVAL_EXEC,
            confidence_marker=RuntimeConfidence.SUSPECTED,
        )]
        merged = merge_runtime_observations(report, obs)

        flow = merged.flows[0]
        assert flow.confirmed_at_runtime is False
        assert flow.confidence_bucket == "possible"
