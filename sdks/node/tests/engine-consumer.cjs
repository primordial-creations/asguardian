const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const os=require('node:os');
const {Client}=require('@gaia/asgard-sdk');
(async()=>{
 const root=await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(),'scan fixtures ')));
 const target=path.join(root,'source with spaces');await fs.mkdir(target);
 const source=path.join(target,'sample.py');await fs.writeFile(source,'value = 1\n');
 const command=[process.argv[2],'-I','-m','Asgard.sdk_protocol'],engineVersion=process.argv[3];
 const c=new Client(command,{engineVersion}),observations={};
 const scan=(extra={})=>c.scan({authorizedRoot:root,target,...extra});
 try{
  const hello=await c.handshake();assert.equal(hello.engine_version,engineVersion);
  assert.deepEqual(hello.capabilities.profiles,['quality.file-length']);
  const clean=await scan({correlationId:'clean'});assert.equal(clean.complete,true);assert.equal(clean.findings.length,0);assert.equal(clean.correlation_id,'clean');observations.clean=clean.state;
  await fs.writeFile(source,'value = 1\n'.repeat(301));
  const finding=await scan();assert.equal(finding.complete,true);assert.equal(finding.findings.length,1);assert.equal(finding.findings[0].relative_path,'sample.py');assert.equal(finding.findings[0].lines_over,1);observations.finding=finding.findings[0].lines_over;
  await fs.writeFile(path.join(target,'second.py'),'value = 1\n'.repeat(302));
  const capped=await scan({maxFindings:1});assert.equal(capped.complete,false);assert.equal(capped.truncated,true);assert.equal(capped.findings.length,1);assert.equal(capped.summary.files_exceeding_threshold,2);observations.truncated=capped.state;
  for(const invalid of [path.join(root,'missing'),path.dirname(root)])await assert.rejects(scan({target:invalid}),e=>e.code==='engine_error'&&e.response.errors[0].code==='invalid_request');
  observations.invalid_target='invalid_request';
  await assert.rejects(scan({maxFindings:0}),e=>{observations.zero_limit=e.response?.errors[0].code;return e.code==='engine_error'&&observations.zero_limit==='invalid_request';});
  const linked=path.join(root,'linked');await fs.mkdir(linked);await fs.symlink(source,path.join(linked,'escape.py'));
  const partial=await scan({authorizedRoot:linked,target:linked});assert.equal(partial.complete,false);assert.equal(partial.findings.length,0);assert.equal(partial.errors[0].code,'scan_io_failure');observations.symlink=partial.state;
  const wrong=new Client(command,{engineVersion:engineVersion+'-wrong'});try{await assert.rejects(wrong.handshake(),e=>{observations.mismatch=e.code;return e.code==='engine_version_mismatch';});}finally{await wrong.close();}
  const closed=new Client(command,{engineVersion});await closed.close();const cancelled=new AbortController();cancelled.abort();await assert.rejects(closed.handshake({signal:cancelled.signal}),e=>{observations.closed_cancel=e.code;return e.code==='closed';});
  const pipes=new Client([process.argv[2],'-I',path.resolve('pipe_fixture.py'),engineVersion],{engineVersion});try{observations.pipe_drain=(await pipes.handshake()).state;}finally{await pipes.close();}
  console.log(JSON.stringify(observations));
 }finally{await c.close();await fs.rm(root,{recursive:true});}
})().catch(error=>{console.error(error);process.exitCode=1;});
