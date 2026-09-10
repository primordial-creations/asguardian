#!/usr/bin/env python3
"""Require matching revision, pinned engines and explicit common observations."""
import argparse
import hashlib
import json
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
for language in ('python','node','go','rust'):p.add_argument('--'+language,type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();root=Path(__file__).resolve().parents[1]
fixture=root/'sdks/contracts/process-observations-v1.json';expected=json.loads(fixture.read_text());digest=hashlib.sha256(fixture.read_bytes()).hexdigest()
reports={language:json.loads(getattr(a,language).read_text()) for language in ('python','node','go','rust')}
revision=reports['python']['revision'];engines=reports['python']['engine_artifacts']
if reports['python']['sdk_revision']!=revision:raise RuntimeError('Python producer revision mismatch')
for language,report in reports.items():
 if report['result']!='passed' or report['revision']!=revision or report['fixture_sha256']!=digest:raise RuntimeError('Unqualified revision/fixture: '+language)
 if report['engine_artifacts']!=engines:raise RuntimeError('Engine artifact mismatch: '+language)
 if language!='python' and report['engine_revision']!=revision:raise RuntimeError('Engine producer mismatch: '+language)
 if len(report['reports'])!=(4 if language=='python' else 2):raise RuntimeError('Missing artifact combination: '+language)
 for result in report['reports']:
  if result['engine'] not in engines or result['observations']!=expected:raise RuntimeError('Observation mismatch: '+language)
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps(dict(result='passed',revision=revision,fixture_sha256=digest,engine_artifacts=engines,observations=expected,artifact_combinations=10,classification='fifteen actual-engine/negotiation cases plus closed/cancel precedence and controlled delayed-pipe fixture; not full protocol/profile/lifecycle/bridge parity'),indent=2)+'\n')
print('All four installed SDKs match the shared process fixture')
