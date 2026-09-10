#!/usr/bin/env python3
"""Install the npm artifact independently and compare real engine observations."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine-evidence',type=Path,required=True)
    parser.add_argument('--scratch-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    if subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip():raise RuntimeError('Clean source required')
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    scratch=args.scratch_root.resolve();scratch.mkdir(parents=True,exist_ok=True)
    if scratch.is_relative_to(root):raise RuntimeError('External consumer required')
    source=args.engine_evidence.resolve();engine=json.loads(source.read_text())
    if engine['result']!='passed' or len(engine['engines'])!=2:raise RuntimeError('Qualified engine pair required')
    for name,digest in engine['engine_artifacts'].items():
        if hashlib.sha256((source.parent/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Engine digest mismatch')
    records=[];env={**os.environ,'PYTHONPATH':'','NODE_PATH':''}
    def run(command,cwd):
        command=[str(x) for x in command]
        result=subprocess.run(command,cwd=cwd,env=env,capture_output=True,text=True,timeout=600)
        records.append(dict(command=command,cwd=str(cwd),exit_code=result.returncode,output=result.stdout+result.stderr))
        (output/'commands.json').write_text(json.dumps(records,indent=2)+'\n')
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        return result.stdout.strip()
    packed=json.loads(run(['npm','pack','--ignore-scripts','--json','--pack-destination',output],root/'sdks/node'))[0]
    artifact=output/packed['filename']
    consumer=Path(tempfile.mkdtemp(prefix='asgard-node-',dir=scratch))
    (consumer/'package.json').write_text('{"private":true}')
    run(['npm','install','--ignore-scripts','--no-audit','--no-fund',artifact],consumer)
    run(['npm','ls','--omit=dev','--json'],consumer)
    test=(root/'sdks/node/tests/client.test.cjs').read_text().replace("require('../index.cjs')","require('@gaia/asgard-sdk')").replace("import('../index.mjs')","import('@gaia/asgard-sdk')")
    (consumer/'client.test.cjs').write_text(test)
    run(['node','--test','client.test.cjs'],consumer)
    run(['node','-e',"const p=require.resolve('@gaia/asgard-sdk');if(!p.startsWith(process.cwd()+'/node_modules/'))throw Error('source import');const m=require('./node_modules/@gaia/asgard-sdk/package.json');if(Object.keys(m.dependencies||{}).length)throw Error('heavy dependencies')"],consumer)
    run(['npm','install','--ignore-scripts','--no-audit','--no-fund','--save-dev','typescript@5.9.3','@types/node@22'],consumer)
    smoke="import {Client, ScanError, type Response} from '@gaia/asgard-sdk'; const client=new Client(['/engine'],{engineVersion:'1'}); const result:Promise<Response>=client.scan({authorizedRoot:'/root',target:'/root',signal:new AbortController().signal}); void result; void ScanError; void client.close();\n"
    for mode in ('cts','mts'):(consumer/f'smoke.{mode}').write_text(smoke)
    run([consumer/'node_modules/.bin/tsc','--strict','--noEmit','--module','NodeNext','--moduleResolution','NodeNext','--target','ES2022','smoke.cts','smoke.mts'],consumer)
    shutil.copy(root/'sdks/node/tests/engine-consumer.cjs',consumer/'engine-consumer.cjs')
    fixture=root/'sdks/contracts/process-observations-v1.json';expected=json.loads(fixture.read_text())
    shutil.copy(root/'sdks/contracts/pipe_fixture.py',consumer/'pipe_fixture.py')
    reports=[]
    for installed in engine['engines']:
        python=Path(installed['path'])/'venv/bin/python'
        origin=json.loads(run([python,'-I','-c',"import importlib.metadata as m; print(m.distribution('asguardian').read_text('direct_url.json'))"],consumer))
        if origin['archive_info']['hashes']['sha256']!=engine['engine_artifacts'][installed['artifact']]:raise RuntimeError('Installed engine provenance mismatch')
        observations=json.loads(run(['node','engine-consumer.cjs',python,installed['version']],consumer))
        if observations!=expected:raise RuntimeError('Node/Python engine observations disagree')
        reports.append(dict(engine=installed['artifact'],observations=observations))
    evidence=dict(fixture_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),revision=run(['git','rev-parse','HEAD'],root),engine_revision=engine['revision'],engine_artifacts=engine['engine_artifacts'],artifact=artifact.name,sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),consumer=str(consumer),reports=reports,result='passed',classification='Node CJS/ESM/types/lifecycle and installed file-length engines; Python observation equality; other profiles/languages/bridges/migrations/channel pending')
    (output/'verification.json').write_text(json.dumps(evidence,indent=2)+'\n');print('Node SDK artifact and both installed engines passed')

if __name__=='__main__':main()
