#!/usr/bin/env python3
"""Qualify a clean revision as an immutable Go file-proxy artifact in an external consumer.

This is local distribution evidence, not proof of an uploaded channel or a tag.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--consumer',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--engine-evidence',type=Path,required=True)
p.add_argument('--build-cache',type=Path,help='Optional reusable compiler cache; module cache stays isolated')
a=p.parse_args();root=Path(__file__).resolve().parents[1];consumer=a.consumer.resolve();output=a.output.resolve()
if consumer.is_relative_to(root) or root.is_relative_to(consumer):raise RuntimeError('External consumer required')
if subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip():raise RuntimeError('Commit scoped changes before qualification')
consumer.mkdir(parents=True,exist_ok=False);output.mkdir(parents=True,exist_ok=False)
records=[]
def run(args,cwd,extra=None):
 result=subprocess.run([str(x) for x in args],cwd=cwd,env={**os.environ,**(extra or {})},capture_output=True,text=True,timeout=180)
 records.append(dict(command=[str(x) for x in args],cwd=str(cwd),exit_code=result.returncode,output=result.stdout+result.stderr))
 (output/'commands.json').write_text(json.dumps(records,indent=2)+'\n')
 if result.returncode:raise RuntimeError(result.stdout+result.stderr)
 return result.stdout
revision=run(['git','rev-parse','HEAD'],root).strip()
stamp=int(run(['git','show','-s','--format=%ct',revision],root).strip())
date=datetime.datetime.fromtimestamp(stamp,datetime.timezone.utc)
version='v0.0.0-'+date.strftime('%Y%m%d%H%M%S')+'-'+revision[:12]
module='github.com/primordial-creations/asguardian/sdks/go'
escaped=''.join('!'+ch.lower() if ch.isupper() else ch for ch in module)
proxy=output/'proxy';versions=proxy/escaped/'@v';versions.mkdir(parents=True)
def blob(path):return subprocess.check_output(['git','show',revision+':'+path],cwd=root)
files=run(['git','ls-tree','-r','--name-only',revision,'sdks/go'],root).splitlines()
archive=versions/(version+'.zip')
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as target:
 for path in files:
  target.writestr(zipfile.ZipInfo(module+'@'+version+'/'+str(Path(path).relative_to('sdks/go')),date_time=(1980,1,1,0,0,0)),blob(path))
(versions/(version+'.mod')).write_bytes(blob('sdks/go/go.mod'))
(versions/(version+'.info')).write_text(json.dumps(dict(Version=version,Time=date.isoformat().replace('+00:00','Z')))+'\n')
(versions/'list').write_text(version+'\n')
env={'GOWORK':'off','GOPROXY':proxy.as_uri(),'GOSUMDB':'off','GONOSUMDB':'*','GONOPROXY':'none','GOPRIVATE':'','GOTOOLCHAIN':'local','GOFLAGS':'','GOMODCACHE':str(consumer/'module-cache'),'GOCACHE':str(a.build_cache.resolve() if a.build_cache else consumer/'build-cache')}
(consumer/'go.mod').write_text('module qualification.invalid/asgard\n\ngo 1.22\n\nrequire '+module+' '+version+'\n')
(consumer/'client_test.go').write_bytes(blob('sdks/go/client_test.go'))
(consumer/'cmd').mkdir();(consumer/'cmd/main.go').write_bytes(blob('sdks/go/qualification/main.go'))
run(['go','mod','download','-json',module+'@'+version],consumer,env)
run(['go','test','-race','-count=1','-v','.'],consumer,env)
run(['go','vet','./...'],consumer,env)
run(['go','mod','verify'],consumer,env)
binary=consumer/'owner-consumer';run(['go','build','-o',binary,'./cmd'],consumer,env)
installed=Path(run(['go','list','-m','-f','{{.Dir}}',module],consumer,env).strip())
source=a.engine_evidence.resolve();engine=json.loads(source.read_text())
if engine['result']!='passed' or len(engine['engines'])!=2:raise RuntimeError('Qualified engine pair required')
for name,digest in engine['engine_artifacts'].items():
 if hashlib.sha256((source.parent/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Engine artifact digest mismatch')
fixture=root/'sdks/contracts/process-observations-v1.json';expected=json.loads(fixture.read_text())
shutil.copy(root/'sdks/contracts/pipe_fixture.py',consumer/'pipe_fixture.py')
reports=[]
for item in engine['engines']:
 python=Path(item['path'])/'venv/bin/python'
 origin=json.loads(run([python,'-I','-c',"import importlib.metadata as m; print(m.distribution('asguardian').read_text('direct_url.json'))"],consumer,env))
 if origin['archive_info']['hashes']['sha256']!=engine['engine_artifacts'][item['artifact']]:raise RuntimeError('Engine install provenance mismatch')
 observations=json.loads(run([binary,python,item['version']],consumer,env))
 if observations!=expected:raise RuntimeError('Go/Python observations disagree')
 reports.append(dict(engine=item['artifact'],observations=observations))
artifacts={str(path.relative_to(output)):hashlib.sha256(path.read_bytes()).hexdigest() for path in versions.iterdir() if path.is_file()}
(output/'verification.json').write_text(json.dumps(dict(fixture_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),revision=revision,dirty=run(['git','status','--porcelain'],root),module=module,version=version,artifacts=artifacts,engine_revision=engine['revision'],engine_artifacts=engine['engine_artifacts'],reports=reports,consumer=str(consumer),toolchain=run(['go','version'],consumer,env).strip(),result='passed',classification='immutable local file proxy with race tests; both installed file-length engine artifacts match Python observations; other profiles/languages/bridges/migrations and durable channel pending'),indent=2)+'\n')
print('PASS immutable Go module, race tests and both installed Asgard engines')
