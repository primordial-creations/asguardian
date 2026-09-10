"""Protocol preparation: read failures must survive domain aggregation."""
import pytest
from Asgard.Heimdall.Security.models.security_models import SecurityScanConfig
from Asgard.Heimdall.Security.services.cryptographic_validation_service import CryptographicValidationService
from Asgard.Heimdall.Security.services.injection_detection_service import InjectionDetectionService
from Asgard.Heimdall.Security.services.secrets_detection_service import SecretsDetectionService
from Asgard.Heimdall.Security.services.static_security_service import StaticSecurityService

@pytest.mark.parametrize('service_type',[CryptographicValidationService,InjectionDetectionService,SecretsDetectionService])
def test_strict_read_failure_is_recorded(tmp_path,monkeypatch,service_type):
    import importlib
    module=importlib.import_module(service_type.__module__)
    bad=tmp_path/'bad.py';bad.write_bytes(b'\xff')
    monkeypatch.setattr(module,'scan_directory_for_security',lambda *a,**kw:iter([bad]))
    report=service_type(SecurityScanConfig(strict_io=True)).scan(tmp_path)
    assert report.analysis_errors==[{'stage':'read','file_path':str(bad),'error_type':'UnicodeDecodeError'}]
    assert report.findings==[]

def test_partial_findings_survive_aggregation(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from Asgard.Heimdall.Security.models.security_models import SecurityReport
    finding=object()
    partial=SimpleNamespace(findings=[finding],analysis_errors=[{'stage':'read','file_path':'bad.py','error_type':'OSError'}])
    report=SecurityReport(scan_path=str(tmp_path),scan_config=SecurityScanConfig(strict_io=True))
    result=StaticSecurityService._scan_domain(report,'crypto',lambda path:partial,tmp_path)
    assert result.findings==[finding]
    assert report.domain_errors[0]['domain']=='crypto'
    assert report.domain_errors[0]['stage']=='read'
