#!/usr/bin/env python3
"""Produce and install a Rust owner crate through a controlled sparse registry.

The registry is loopback-only qualification infrastructure, not a deployed channel.
SDK consumers use a version/checksum, never a path override or sibling source.
"""
import argparse
import functools
import hashlib
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import threading
import tomllib

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--consumer',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--target',type=Path,required=True)
p.add_argument('--engine-evidence',type=Path,required=True)
a=p.parse_args();root=Path(__file__).resolve().parents[1];consumer=a.consumer.resolve();output=a.output.resolve();target=a.target.resolve()
if consumer.is_relative_to(root) or root.is_relative_to(consumer):raise RuntimeError('External consumer required')
if subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip():raise RuntimeError('Commit scoped inputs before qualification')
consumer.mkdir(parents=True,exist_ok=False);output.mkdir(parents=True,exist_ok=False);target.mkdir(parents=True,exist_ok=True)
records=[]
env={**os.environ,'CARGO_TARGET_DIR':str(target),'CARGO_HTTP_TIMEOUT':'20','CARGO_NET_RETRY':'0'}
def run(command,cwd):
 result=subprocess.run([str(v) for v in command],cwd=cwd,env=env,capture_output=True,text=True,timeout=300)
 records.append(dict(command=[str(v) for v in command],cwd=str(cwd),exit_code=result.returncode,output=result.stdout+result.stderr))
 (output/'commands.json').write_text(json.dumps(records,indent=2)+'\n')
 if result.returncode:raise RuntimeError(result.stdout+result.stderr)
 return result.stdout
revision=run(['git','rev-parse','HEAD'],root).strip()
def blob(path):return subprocess.check_output(['git','show',revision+':'+path],cwd=root)
stage=consumer/'production-stage';stage.mkdir()
for path in run(['git','ls-tree','-r','--name-only',revision,'sdks/rust'],root).splitlines():
 dest=stage/Path(path).relative_to('sdks/rust');dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(blob(path))
metadata=json.loads(run(['cargo','metadata','--offline','--no-deps','--format-version','1','--manifest-path',stage/'Cargo.toml'],stage))['packages'][0]
run(['cargo','package','--offline','--locked','--allow-dirty','--manifest-path',stage/'Cargo.toml'],stage)
name=metadata['name'];version=metadata['version'];artifact=output/f'{name}-{version}.crate';shutil.copy(target/f'package/{artifact.name}',artifact);digest=hashlib.sha256(artifact.read_bytes()).hexdigest()
with tarfile.open(artifact) as archive:
 names=archive.getnames()
 for required in ('src/lib.rs','LICENSE'):
  if f'{name}-{version}/{required}' not in names:raise RuntimeError('Missing packaged input')
project=consumer/'project';project.mkdir();(project/'.cargo').mkdir();(project/'src').mkdir();(project/'tests').mkdir()
shutil.copy(stage/'tests/client.rs',project/'tests/client.rs');shutil.copy(stage/'examples/owner_consumer.rs',project/'src/main.rs')
(project/'Cargo.toml').write_text(f'''[package]
name = "asgard-sdk-qualification"
version = "0.0.0"
edition = "2021"
[dependencies]
gaia-asgard-sdk = {{ version = "={version}", registry = "asgard-qualification" }}
serde_json = "1.0"
libc = "0.2"
tokio = {{ version = "1.52", features = ["rt-multi-thread", "macros", "net", "io-util", "sync", "time"] }}
''')
www=output/'registry';www.mkdir()
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(www)));base=f'http://127.0.0.1:{server.server_address[1]}'
index=www/'index'/revision;index.mkdir(parents=True);registry_source='sparse+'+base+'/index/'+revision+'/';(index/'config.json').write_text(json.dumps({'dl':base+'/crates/{crate}/{version}/download'})+'\n')
deps=[]
for dep in metadata['dependencies']:
 if dep['kind']=='dev':continue
 deps.append(dict(name=dep['rename'] or dep['name'],req=dep['req'],features=dep['features'],optional=dep['optional'],default_features=dep['uses_default_features'],target=dep['target'],kind=dep['kind'] or 'normal',registry='https://github.com/rust-lang/crates.io-index',package=dep['name'] if dep['rename'] else None))
entry=index/name[:2]/name[2:4]/name;entry.parent.mkdir(parents=True);entry.write_text(json.dumps(dict(name=name,vers=version,deps=deps,cksum=digest,features=metadata['features'],yanked=False,links=None,rust_version=metadata['rust_version']))+'\n')
download=www/'crates'/name/version/'download';download.parent.mkdir(parents=True);shutil.copy(artifact,download)
(project/'.cargo/config.toml').write_text('[registries.asgard-qualification]\nindex = "'+registry_source+'"\n')
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:
 # Fetch only this immutable crate/index entry online; dependencies then resolve
 # offline from the normal third-party Cargo cache. No source replacement.
 run(['cargo','info','--registry','asgard-qualification',name+'@'+version],project)
 run(['cargo','generate-lockfile','--offline'],project)
 run(['cargo','test','--offline','--locked','--test','client'],project)
 run(['cargo','clippy','--offline','--locked','--all-targets','--','-D','warnings'],project)
 run(['cargo','build','--offline','--locked'],project)
 installed=json.loads(run(['cargo','metadata','--offline','--locked','--format-version','1'],project))
 sdk=next(pkg for pkg in installed['packages'] if pkg['name']==name)
 if sdk['source']!=registry_source:raise RuntimeError('SDK was not installed from the expected sparse registry')
 locked=next(pkg for pkg in tomllib.loads((project/'Cargo.lock').read_text())['package'] if pkg['name']==name)
 if locked.get('checksum')!=digest:raise RuntimeError('Installed SDK checksum mismatch')
 if Path(sdk['manifest_path']).is_relative_to(stage) or Path(sdk['manifest_path']).is_relative_to(root):raise RuntimeError('SDK source override detected')
 (output/'installed-sdk.json').write_text(json.dumps(dict(source=sdk['source'],manifest_path=sdk['manifest_path'],checksum=digest),indent=2)+'\n')
 installed_path=Path(sdk['manifest_path']).parent
 source=a.engine_evidence.resolve();engine=json.loads(source.read_text())
 if engine['result']!='passed' or len(engine['engines'])!=2:raise RuntimeError('Qualified engine pair required')
 for filename,expected in engine['engine_artifacts'].items():
  if hashlib.sha256((source.parent/filename).read_bytes()).hexdigest()!=expected:raise RuntimeError('Engine artifact mismatch')
 fixture=root/'sdks/contracts/process-observations-v1.json';expected=json.loads(fixture.read_text())
 shutil.copy(root/'sdks/contracts/pipe_fixture.py',project/'pipe_fixture.py')
 reports=[]
 for item in engine['engines']:
  python=Path(item['path'])/'venv/bin/python'
  origin=json.loads(run([python,'-I','-c',"import importlib.metadata as m; print(m.distribution('asguardian').read_text('direct_url.json'))"],project))
  if origin['archive_info']['hashes']['sha256']!=engine['engine_artifacts'][item['artifact']]:raise RuntimeError('Engine install mismatch')
  observations=json.loads(run([target/'debug/asgard-sdk-qualification',python,item['version']],project))
  if observations!=expected:raise RuntimeError('Rust/Python observations disagree')
  reports.append(dict(engine=item['artifact'],observations=observations))
 shutil.copy(project/'Cargo.lock',output/'consumer-Cargo.lock')
finally:
 server.shutdown();server.server_close();thread.join(5)
(output/'verification.json').write_text(json.dumps(dict(fixture_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),revision=revision,dirty=run(['git','status','--porcelain'],root),artifact=artifact.name,sha256=digest,engine_revision=engine['revision'],engine_artifacts=engine['engine_artifacts'],reports=reports,consumer=str(project),toolchain=run(['rustc','--version'],project).strip(),result='passed',classification='version/checksum-installed crate from controlled sparse registry; lifecycle fixtures and both installed file-length/hotspot engines match Python observations; full profiles/parity/bridges/migrations and durable channel pending'),indent=2)+'\n')
print('PASS independent Rust crate, lifecycle fixtures and both installed Asgard engines')
