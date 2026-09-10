const { test } = require('node:test');
const assert = require('node:assert/strict');
const { Client } = require('../index.cjs');
const fixture = `
let input=''; process.stdin.on('data', chunk=>input+=chunk); process.stdin.on('end',()=>{
 const req=JSON.parse(input),mode=process.argv[1];
 if(mode==='sleep'){setInterval(()=>{},1000);return;}
 if(mode==='stdout'||mode==='stderr'){process[mode].write('x'.repeat(100000));setInterval(()=>{},1000);return;}
 if(mode==='malformed'){console.log('null');return;}
 const r={protocol_version:1,engine_version:'fixture',scan_id:'id',correlation_id:req.correlation_id,state:'ready',complete:true,truncated:false,findings:[],errors:[],capabilities:{profiles:['quality.file-length'],transport:'single-request-stdio'}};
 let code=0;
 if(req.operation==='scan'){
  r.state='complete';
  if(mode==='finding'){r.findings=[{relative_path:'sample.py'}];code=1;}
  if(mode==='incomplete'){r.state='incomplete';r.complete=false;r.truncated=true;code=1;}
  if(mode==='lying'){r.errors=[{code:'missing_tool'}];}
  if(mode==='error'){r.state='error';r.complete=false;r.errors=[{code:'invalid_request'}];code=2;}
 }
 if(mode==='version')r.engine_version='other';
 console.log(JSON.stringify(r));process.exitCode=code;
});`;
const create = (mode='clean', options={}) => new Client([process.execPath,'-e',fixture,mode],{engineVersion:'fixture',...options});
const scan = (client,options={}) => client.scan({authorizedRoot:'/fixture',target:'/fixture/source',...options});
const code = expected => error => error.code === expected;
test('complete, findings, incomplete preserve owner truth',async()=>{
 for(const mode of ['clean','finding','incomplete']){
  const c=create(mode);try{const r=await scan(c);assert.equal(r.complete,mode!=='incomplete');assert.equal(r.findings.length,mode==='finding'?1:0);}finally{await c.close();}
 }
});
test('protocol and owner errors remain failures',async()=>{
 for(const [mode,expected] of [['malformed','malformed_response'],['lying','malformed_response'],['version','engine_version_mismatch'],['error','engine_error']]){
  const c=create(mode);try{await assert.rejects(scan(c),code(expected));}finally{await c.close();}
 }
});
test('timeout and both output bounds',async()=>{
 for(const mode of ['sleep','stdout','stderr']){
  const c=create(mode,{timeoutMs:300,maxOutputBytes:1024});try{await assert.rejects(scan(c),code(mode==='sleep'?'timeout':'output_limit'));}finally{await c.close();}
 }
});
test('abort and close interrupt active work and settle',async()=>{
 for(const closed of [false,true]){
  const c=create('sleep'),abort=new AbortController();
  const pending=assert.rejects(scan(c,{signal:abort.signal}),code(closed?'closed':'cancelled'));
  await new Promise(r=>setTimeout(r,70));
  if(closed)await c.close();else abort.abort();
  await pending;await c.close();await assert.rejects(scan(c),code('closed'));
 }
});
test('preabort, independent instances, unsupported profile and missing engine',async()=>{
 const first=create(),second=create(),abort=new AbortController();abort.abort();
 try{await assert.rejects(scan(first,{signal:abort.signal}),code('cancelled'));await first.close();assert.equal((await scan(second)).complete,true);await assert.rejects(scan(second,{profile:'other'}),code('unsupported_operation'));}finally{await first.close();await second.close();}
 const missing=new Client(['/nonexistent/asgard'],{engineVersion:'fixture'});try{await assert.rejects(missing.handshake(),code('engine_unavailable'));}finally{await missing.close();}
});
test('ESM delegates to the same CommonJS classes',async()=>{
 const esm=await import('../index.mjs');assert.equal(esm.Client,Client);
});
test('invalid cancellation input fails before starting a process',async()=>{
 const c=create('sleep');
 try{await assert.rejects(scan(c,{signal:{aborted:false}}),TypeError);}finally{await c.close();}
});
test('timeout terminates child processes in the group',async()=>{
 const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'asgard-child-')),marker=path.join(dir,'pid');
 const script=`const fs=require('node:fs');const child=require('node:child_process').spawn(process.execPath,['-e','setInterval(()=>{},1000)']);fs.writeFileSync(process.argv[1],String(child.pid));setInterval(()=>{},1000);`;
 const c=new Client([process.execPath,'-e',script,marker],{engineVersion:'fixture',timeoutMs:500});
 try{
  await assert.rejects(c.handshake(),code('timeout'));
  const pid=fs.readFileSync(marker,'utf8'),stat=`/proc/${pid}/stat`;
  if(process.platform==='linux')assert.ok(!fs.existsSync(stat)||fs.readFileSync(stat,'utf8').split(' ')[2]==='Z');
 }finally{await c.close();fs.rmSync(dir,{recursive:true});}
});
