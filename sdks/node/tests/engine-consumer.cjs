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
  assert.deepEqual(hello.capabilities.profiles,['quality.file-length','security.hotspots']);
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
  const hotroot=path.join(root,'hotspot scope');await fs.mkdir(hotroot);const config=path.join(hotroot,'.heimdall.yml');await fs.writeFile(config,'test_context_enabled: false\n');await fs.writeFile(path.join(hotroot,'main.py'),"import hashlib\nhashlib.md5(b'x')\n");
  const hotoptions={authorizedRoot:hotroot,target:hotroot,profile:'security.hotspots'};
  const saved=await fs.readFile(path.join(hotroot,'main.py'));await fs.writeFile(path.join(hotroot,'main.py'),'value = 1\n');const cleanhot=await c.scan(hotoptions);assert.equal(cleanhot.complete,true);assert.equal(cleanhot.findings.length,0);observations.hotspot_clean=cleanhot.state;await fs.writeFile(path.join(hotroot,'main.py'),saved);
  const hot=await c.scan(hotoptions);assert.equal(hot.complete,true);assert.equal(hot.findings.length,1);const item=hot.findings[0];observations.hotspot={kind:hot.finding_kind,category:item.category,priority:item.review_priority,review_status:item.review_status};
  await fs.writeFile(path.join(hotroot,'broken.py'),'def broken(:\n');const hotpartial=await c.scan(hotoptions);assert.equal(hotpartial.complete,false);assert.equal(hotpartial.findings.length,1);assert.equal(hotpartial.errors[0].stage,'parse');observations.hotspot_parse=hotpartial.state;
  await fs.writeFile(path.join(hotroot,'broken.py'),Buffer.from([255]));const hotread=await c.scan(hotoptions);assert.equal(hotread.complete,false);assert.equal(hotread.findings.length,1);assert.equal(hotread.errors[0].error_type,'UnicodeDecodeError');observations.hotspot_read=hotread.state;
  await fs.writeFile(config,'test_context_enabled: []\n');const hotinvalid=await c.scan(hotoptions);assert.equal(hotinvalid.complete,false);observations.hotspot_config=hotinvalid.errors[0].code;
  const logical='/tests/nonexistent-asgard-logical-fixture';await fs.unlink(path.join(hotroot,'broken.py'));await fs.writeFile(config,'strict_scan_paths: ["^/tests/nonexistent-asgard-logical-fixture/"]\n');
  const mapped=await c.scan({...hotoptions,logicalRoot:logical});assert.equal(mapped.complete,true);assert.equal(mapped.findings.length,1);assert.equal(mapped.findings[0].context_tag,'production');
  observations.logical_context={priority:mapped.findings[0].review_priority,path:mapped.findings[0].file_path===logical+'/main.py'};
  await assert.rejects(c.scan({...hotoptions,logicalRoot:'relative'}),e=>{observations.logical_invalid=e.response?.errors[0].code;return e.code==='engine_error'&&observations.logical_invalid==='invalid_request';});
  await assert.rejects(c.scan({...hotoptions,profile:'quality.file-length',logicalRoot:logical}),e=>{observations.logical_unsupported=e.code;return e.code==='unsupported_operation';});
  console.log(JSON.stringify(observations));
 }finally{await c.close();await fs.rm(root,{recursive:true});}
})().catch(error=>{console.error(error);process.exitCode=1;});
