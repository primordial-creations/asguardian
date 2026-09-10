"""Imported production regressions: missing analysis is never a perfect scan."""
from unittest.mock import Mock

import pytest

from Asgard.Bragi.Performance.models.performance_models import (
    MemoryReport, CpuReport, DatabaseReport, CacheReport, PerformanceScanConfig,
)
from Asgard.Bragi.Performance.services.static_performance_service import StaticPerformanceService

REPORTS = {'memory': MemoryReport, 'cpu': CpuReport, 'database': DatabaseReport, 'cache': CacheReport}


def service_with_empty_results(path, config=None):
    service = StaticPerformanceService(config)
    for name, model in REPORTS.items():
        setattr(service, name + '_service', Mock(scan=Mock(return_value=model(scan_path=str(path)))))
    return service


@pytest.mark.parametrize('failed', list(REPORTS) + ['all'])
def test_required_failure_is_incomplete_and_has_no_numeric_score(tmp_path, failed):
    service = service_with_empty_results(tmp_path)
    for name in REPORTS:
        if name == failed or failed == 'all':
            getattr(service, name + '_service').scan.side_effect = RuntimeError('synthetic-private-diagnostic')
    result = service.scan(tmp_path)
    assert result.performance_score is None
    assert not result.is_healthy
    assert not result.is_complete
    assert 'synthetic-private-diagnostic' not in result.model_dump_json()
    assert 'INCOMPLETE' in service.generate_report(result)


def test_complete_empty_scan_and_disabled_optional_analysis(tmp_path):
    service = service_with_empty_results(tmp_path, PerformanceScanConfig(scan_cache=False))
    result = service.scan(tmp_path)
    assert result.is_complete
    assert result.performance_score == 100
    assert result.analyzer_outcomes['cache'].status == 'skipped'
    service.cache_service.scan.assert_not_called()


def test_invalid_analyzer_output_is_not_success(tmp_path):
    service = service_with_empty_results(tmp_path)
    service.memory_service.scan.return_value = None
    result = service.scan(tmp_path)
    assert not result.is_complete
    assert result.performance_score is None
    assert result.analyzer_outcomes['memory'].status == 'failed'

@pytest.mark.parametrize('domain', REPORTS)
def test_single_domain_scan_narrows_requiredness_without_mutating_config(tmp_path, domain):
    service = service_with_empty_results(tmp_path)
    result = getattr(service, 'scan_' + domain + '_only')(tmp_path)
    assert result.is_complete
    assert result.performance_score == 100
    for name in REPORTS:
        assert getattr(service.config, 'scan_' + name)
        assert result.analyzer_outcomes[name].status == ('succeeded' if name == domain else 'skipped')


def test_json_and_cli_reject_incomplete_report(tmp_path, monkeypatch, capsys):
    import argparse
    import json
    from Asgard.Heimdall.cli.handlers import performance
    service = service_with_empty_results(tmp_path)
    service.memory_service.scan.side_effect = ImportError('synthetic-private-diagnostic')
    result = service.scan(tmp_path)
    payload = json.loads(service.generate_report(result, 'json'))
    assert payload['performance_score'] is None
    assert payload['is_complete'] is False
    assert payload['analyzer_outcomes']['memory']['status'] == 'unavailable'
    monkeypatch.setattr(performance, 'StaticPerformanceService', lambda config: service)
    args = argparse.Namespace(path=str(tmp_path), exclude=[], severity='low', format='json')
    assert performance.run_performance_analysis(args) == 1
    assert json.loads(capsys.readouterr().out)['is_complete'] is False


def test_full_scan_step_keeps_partial_findings_and_incomplete_status(tmp_path, monkeypatch):
    from Asgard.Heimdall.cli.handlers import scan_steps_7_11 as steps
    from Asgard.Bragi.Performance.models.performance_models import MemoryFinding, MemoryIssueType, PerformanceSeverity
    service = service_with_empty_results(tmp_path)
    service.memory_service.scan.return_value.add_finding(MemoryFinding(
        file_path='fixture.py', line_number=1, issue_type=MemoryIssueType.MEMORY_LEAK,
        severity=PerformanceSeverity.HIGH, description='Observed fixture leak', recommendation='Close resource',
    ))
    service.cpu_service.scan.side_effect = RuntimeError('unavailable fixture')
    monkeypatch.setattr(steps, 'StaticPerformanceService', lambda config: service)
    for name in ('OOPAnalyzer', 'ArchitectureAnalyzer', 'DependencyAnalyzer', 'CoverageAnalyzer'):
        monkeypatch.setattr(steps, name, Mock(side_effect=RuntimeError('unrelated analyzer excluded from fixture')))
    results, reports = {}, {}
    assert steps._run_scan_steps_7_to_11(tmp_path, [], False, False, results, reports) == 1
    assert results['performance'] == {
        'total_findings': 1, 'status': 'INCOMPLETE', 'is_complete': False, 'performance_score': None,
    }
    assert 'INCOMPLETE' in reports['performance']
