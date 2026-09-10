#!/usr/bin/env python3
"""Build and install engine wheel/sdist, then exercise installed SDK consumers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk-evidence', type=Path, required=True)
    parser.add_argument('--scratch-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip():
        raise RuntimeError('Clean engine source required')
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    scratch = args.scratch_root.resolve(); scratch.mkdir(parents=True, exist_ok=True)
    if scratch.is_relative_to(root):
        raise RuntimeError('Consumers must be outside repository')
    fixture = root / 'sdks/contracts/process-observations-v1.json'
    expected = json.loads(fixture.read_text())
    sdk_evidence = args.sdk_evidence.resolve()
    sdk = json.loads(sdk_evidence.read_text())
    if sdk['result'] != 'passed' or len(sdk['consumers']) != 2:
        raise RuntimeError('Both SDK artifacts must pass first')
    for name, digest in sdk['artifacts'].items():
        if hashlib.sha256((sdk_evidence.parent / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError('SDK artifact digest mismatch')
    records = []
    env = {**os.environ, 'PYTHONPATH': ''}
    def run(command, cwd):
        command = [str(item) for item in command]
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=600)
        records.append(dict(command=command, cwd=str(cwd), exit_code=result.returncode,
                            output=result.stdout + result.stderr))
        (output / 'commands.json').write_text(json.dumps(records, indent=2) + '\n')
        if result.returncode:
            raise RuntimeError(result.stdout[-4000:] + result.stderr[-4000:])
        return result.stdout.strip()
    revision = run(['git', 'rev-parse', 'HEAD'], root)
    run([sys.executable, '-m', 'build', '--outdir', output, root], root)
    artifacts = [*output.glob('*.whl'), *output.glob('*.tar.gz')]
    if len(artifacts) != 2:
        raise RuntimeError('Expected engine wheel and sdist')
    wheel = next(output.glob('*.whl'))
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        if 'Asgard/sdk_protocol.py' not in names:
            raise RuntimeError('Engine protocol missing')
        if any(not (name.startswith('Asgard/') or '.dist-info/' in name) for name in names):
            raise RuntimeError('Unexpected engine wheel namespace')
    with tarfile.open(next(output.glob('*.tar.gz'))) as archive:
        if any('/sdks/' in name for name in archive.getnames()):
            raise RuntimeError('Engine sdist includes separate SDK sources')
    engines, reports = [], []
    for artifact in artifacts:
        consumer = Path(tempfile.mkdtemp(prefix='asgard-engine-', dir=scratch))
        python = consumer / 'venv/bin/python'
        run([sys.executable, '-m', 'venv', consumer / 'venv'], consumer)
        run([python, '-m', 'pip', 'install', artifact], consumer)
        run([python, '-m', 'pip', 'check'], consumer)
        version = run([python, '-I', '-c', "import importlib.metadata as m; import Asgard; import sys; from pathlib import Path; assert Path(Asgard.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()); assert not any(str(f).startswith(('sdks/', 'asgard_sdk/')) for f in m.files('asguardian')); print(m.version('asguardian'))"], consumer)
        engines.append(dict(artifact=artifact.name, path=str(consumer), version=version,
                            packages=run([python, '-m', 'pip', 'freeze'], consumer).splitlines()))
        for client in sdk['consumers']:
            client_root = Path(client['path'])
            client_python = client_root / 'venv/bin/python'
            # Reassert the installed SDK's immutable provenance before using it.
            origin = json.loads(run([client_python, '-I', '-c', "import importlib.metadata as m; print(m.distribution('gaia-asgard-sdk').read_text('direct_url.json'))"], client_root))
            if origin['archive_info']['hashes']['sha256'] != sdk['artifacts'][client['artifact']]:
                raise RuntimeError('Installed SDK provenance mismatch')
            shutil.copy(root / 'sdks/python/tests/engine_consumer.py', client_root / 'engine_consumer.py')
            shutil.copy(root / 'sdks/contracts/pipe_fixture.py', client_root / 'pipe_fixture.py')
            observations = json.loads(run([client_python, '-I', client_root / 'engine_consumer.py', python, version], client_root))
            if observations != expected: raise RuntimeError('Shared process conformance mismatch')
            reports.append(dict(engine=artifact.name, sdk=client['artifact'], observations=observations))
    if any(report['observations'] != reports[0]['observations'] for report in reports):
        raise RuntimeError('Artifact combinations disagree')
    result = dict(fixture_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(), revision=revision, sdk_revision=sdk['revision'], sdk_artifacts=sdk['artifacts'],
                  engine_artifacts={item.name: hashlib.sha256(item.read_bytes()).hexdigest() for item in artifacts},
                  engines=engines, reports=reports, result='passed',
                  classification='four installed engine/SDK artifact combinations, actual file-length engine; other profiles, languages, CI/channel and migrations pending')
    (output / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print('All four installed engine/SDK combinations passed')


if __name__ == '__main__':
    main()
