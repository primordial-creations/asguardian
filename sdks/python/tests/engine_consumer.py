"""Run only from an independent installed SDK consumer against an installed engine."""
import json
from pathlib import Path
import sys
import tempfile
import threading
from asgard_sdk import Client, ScanError

command = [sys.argv[1], '-I', '-m', 'Asgard.sdk_protocol']
version = sys.argv[2]
observations = {}
with tempfile.TemporaryDirectory(prefix='scan fixtures ') as temporary:
    root = Path(temporary).resolve()
    source = root / 'source with spaces'
    source.mkdir()
    file = source / 'sample.py'
    file.write_text('value = 1\n')
    with Client(command, engine_version=version) as client:
        hello = client.handshake()
        assert hello['engine_version'] == version
        assert hello['capabilities']['profiles'] == ['quality.file-length']
        clean = client.scan(authorized_root=str(root), target=str(source), correlation_id='clean')
        assert clean['complete'] and not clean['findings'] and clean['correlation_id'] == 'clean'
        observations['clean'] = clean['state']
        file.write_text('value = 1\n' * 301)
        finding = client.scan(authorized_root=str(root), target=str(source))
        assert finding['complete'] and len(finding['findings']) == 1
        assert finding['findings'][0]['relative_path'] == 'sample.py'
        assert finding['findings'][0]['lines_over'] == 1
        observations['finding'] = finding['findings'][0]['lines_over']
        (source / 'second.py').write_text('value = 1\n' * 302)
        capped = client.scan(authorized_root=str(root), target=str(source), max_findings=1)
        assert not capped['complete'] and capped['truncated'] and len(capped['findings']) == 1
        assert capped['summary']['files_exceeding_threshold'] == 2
        observations['truncated'] = capped['state']
        for target in (root / 'missing', root.parent):
            try:
                client.scan(authorized_root=str(root), target=str(target))
                raise AssertionError('invalid target accepted')
            except ScanError as error:
                assert error.code == 'engine_error'
                assert error.response['errors'][0]['code'] == 'invalid_request'
        observations['invalid_target'] = 'invalid_request'
        try:
            client.scan(authorized_root=str(root), target=str(source), max_findings=0)
            raise AssertionError('explicit zero limit accepted')
        except ScanError as error:
            assert error.code == 'engine_error'
            observations['zero_limit'] = error.response['errors'][0]['code']

        linked = root / 'linked'; linked.mkdir()
        (linked / 'escape.py').symlink_to(file)
        partial = client.scan(authorized_root=str(linked), target=str(linked))
        assert partial['state'] == 'incomplete' and not partial['complete'] and not partial['findings']
        assert partial['errors'][0]['code'] == 'scan_io_failure'
        observations['symlink'] = partial['state']
    with Client(command, engine_version=version + '-wrong') as mismatch:
        try:
            mismatch.handshake()
            raise AssertionError('wrong engine accepted')
        except ScanError as error:
            assert error.code == 'engine_version_mismatch'
            observations['mismatch'] = error.code

closed = Client(command, engine_version=version)
closed.close()
cancel = threading.Event(); cancel.set()
try:
    closed.handshake(cancel=cancel)
    raise AssertionError('closed client accepted')
except ScanError as error:
    observations['closed_cancel'] = error.code
with Client([sys.argv[1], '-I', str(Path('pipe_fixture.py').resolve()), version], engine_version=version) as pipes:
    observations['pipe_drain'] = pipes.handshake()['state']
print(json.dumps(observations, sort_keys=True))
