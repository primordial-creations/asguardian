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
    report=service_type(SecurityScanConfig(strict_io=True, exclude_patterns=[])).scan(tmp_path)
    assert report.analysis_errors==[{'stage':'read','file_path':str(bad),'error_type':'UnicodeDecodeError'}]
    assert report.findings==[]

def test_partial_findings_survive_aggregation(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from Asgard.Heimdall.Security.models.security_models import SecurityReport
    finding=object()
    partial=SimpleNamespace(findings=[finding],analysis_errors=[{'stage':'read','file_path':'bad.py','error_type':'OSError'}])
    report=SecurityReport(scan_path=str(tmp_path),scan_config=SecurityScanConfig(strict_io=True, exclude_patterns=[]))
    result=StaticSecurityService._scan_domain(report,'crypto',lambda path:partial,tmp_path)
    assert result.findings==[finding]
    assert report.domain_errors[0]['domain']=='crypto'
    assert report.domain_errors[0]['stage']=='read'

@pytest.mark.parametrize('service_type',[CryptographicValidationService,InjectionDetectionService,SecretsDetectionService])
def test_real_discovery_preserves_symlink_error(tmp_path,service_type):
    target=tmp_path/'source.py';target.write_text('value = 1\n')
    (tmp_path/'link.py').symlink_to(target)
    report=service_type(SecurityScanConfig(strict_io=True, exclude_patterns=[])).scan(tmp_path)
    assert any(e['error_type']=='SymlinkSkipped' for e in report.analysis_errors)
    assert report.total_files_scanned==1

def test_injection_size_limit_is_not_clean(tmp_path):
    (tmp_path/'large.py').write_text('x'*(1_048_576+1))
    report=InjectionDetectionService(SecurityScanConfig(strict_io=True, exclude_patterns=[])).scan(tmp_path)
    assert len(report.analysis_errors)==1

def test_directory_error_is_recorded(tmp_path,monkeypatch):
    from Asgard.Heimdall.Security.utilities import _scan_utils
    def denied(path):raise PermissionError('controlled denial')
    monkeypatch.setattr(_scan_utils.os,'scandir',denied)
    errors=[]
    assert list(_scan_utils.iter_confined_files(tmp_path,analysis_errors=errors))==[]
    assert errors==[{'stage':'discovery','file_path':str(tmp_path),'error_type':'PermissionError'}]
