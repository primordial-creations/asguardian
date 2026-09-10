#!/usr/bin/env python3
"""Build wheel from sdist and test each in independent external consumers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scratch-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    if subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip():raise RuntimeError('Clean source revision required')
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    scratch=args.scratch_root.resolve();scratch.mkdir(parents=True,exist_ok=True)
    if scratch.is_relative_to(root):raise RuntimeError('Consumer scratch must be outside repository')
    records=[];env={**os.environ,'PYTHONPATH':''}
    def run(command,cwd):
        result=subprocess.run([str(v) for v in command],cwd=cwd,env=env,capture_output=True,text=True,timeout=600)
        records.append(dict(command=[str(v) for v in command],cwd=str(cwd),exit_code=result.returncode,output=result.stdout+result.stderr))
        (output/'commands.json').write_text(json.dumps(records,indent=2)+'\n')
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        return result.stdout.strip()
    run([sys.executable,'-m','build','--outdir',output,root/'sdks/python'],root)
    artifacts=[*output.glob('*.whl'),*output.glob('*.tar.gz')]
    if len(artifacts)!=2:raise RuntimeError('Expected wheel and sdist')
    consumers=[]
    for artifact in artifacts:
        consumer=Path(tempfile.mkdtemp(prefix='asgard-python-',dir=scratch));python=consumer/'venv/bin/python'
        run([sys.executable,'-m','venv',consumer/'venv'],consumer)
        run([python,'-m','pip','install',artifact],consumer)
        run([python,'-m','pip','check'],consumer)
        shutil.copy(root/'sdks/python/tests/test_client.py',consumer/'test_client.py')
        run([python,'test_client.py'],consumer)
        run([python,'-c',"import sys,asgard_sdk,importlib.resources; assert not any(n in sys.modules for n in ('Lexicon','Asgard','pydantic','httpx','playwright')); assert importlib.resources.files('asgard_sdk').joinpath('py.typed').is_file(); from pathlib import Path; assert Path(asgard_sdk.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()); import importlib.metadata; assert not importlib.metadata.requires('gaia-asgard-sdk')"],consumer)
        consumers.append(dict(artifact=artifact.name,path=str(consumer),packages=run([python,'-m','pip','freeze'],consumer).splitlines()))
    evidence=dict(revision=run(['git','rev-parse','HEAD'],root),runtime=run([sys.executable,'--version'],root),artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts},consumers=consumers,result='passed',classification='independent wheel/sdist process/lifecycle fixtures; installed owner engine, cross-language parity, distribution channel and consumer migration pending')
    (output/'verification.json').write_text(json.dumps(evidence,indent=2)+'\n');print('Both Asgard Python artifacts passed')

if __name__=='__main__':main()
