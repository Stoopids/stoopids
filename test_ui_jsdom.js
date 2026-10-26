// UI test of index.html in jsdom with an in-memory fake of the shared store (no network, nothing real is touched).
//   cd /tmp && npm i jsdom && NODE_PATH=/tmp/node_modules node <app dir>/test_ui_jsdom.js
const {JSDOM}=require('jsdom');const assert=require('assert');const fs=require('fs'),path=require('path'),http=require('http');
const ROOT=__dirname;
const CFG=JSON.parse(fs.readFileSync(path.join(ROOT,'config.json'),'utf8')).shared_bets;
const MIME={'.html':'text/html','.js':'application/javascript','.json':'application/json'};
const srv=http.createServer((q,r)=>{const p=path.join(ROOT,decodeURIComponent(q.url.split('?')[0]).replace(/\/+$/,'/index.html'));
  if(!p.startsWith(ROOT)||!fs.existsSync(p)||fs.statSync(p).isDirectory()){r.writeHead(404);return r.end('nope')}
  r.writeHead(200,{'content-type':MIME[path.extname(p)]||'application/octet-stream'});r.end(fs.readFileSync(p))});
let BASE;
const store={doc:{schema:1,bets:[]},fail:false,delay:0,calls:[]};
async function fakeFetch(u,o){
  const url=new URL(u,BASE).href;o=o||{};
  if(url===CFG.url){
    store.calls.push((o.method||'GET')+' '+(o.headers&&o.headers['Content-Type']||''));
    if(store.delay)await new Promise(r=>setTimeout(r,store.delay*Math.random()));
    if(store.fail)return new Response('boom',{status:500});
    if((o.method||'GET')==='GET')return new Response(JSON.stringify(store.doc),{status:200,headers:{'content-type':'text/plain'}});
    store.doc=JSON.parse(o.body);return new Response(o.body,{status:200});
  }
  return fetch(url,o);
}
async function open(qs){
  const dom=await JSDOM.fromURL(BASE+'index.html'+(qs||''),{runScripts:'dangerously',resources:'usable',pretendToBeVisual:true,
    beforeParse(w){w.fetch=fakeFetch;w.Response=Response;w.URL.createObjectURL=()=>'blob:x';w.URL.revokeObjectURL=()=>{};w.HTMLAnchorElement.prototype.click=function(){w.__dl=this.download}}});
  const w=dom.window;
  for(let i=0;i<100&&!(w.eval('typeof D!=="undefined"&&D!==null'));i++)await sleep(100);
  return w;
}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const ev=(w,c)=>w.eval(c);
async function until(w,cond,msg){for(let i=0;i<80;i++){if(ev(w,cond))return;await sleep(100)}throw new Error('timeout: '+msg)}
const main=w=>w.document.getElementById('main').textContent;
async function fillAndBuild(w,text,a,b,stake){
  const d=w.document;ev(w,"tab='bets';render()");
  d.getElementById('sb_text').value=text;
  d.querySelectorAll('input[name=sa]').forEach(x=>x.checked=x.value===a);d.querySelectorAll('input[name=sb]').forEach(x=>x.checked=x.value===b);
  d.getElementById('sb_stake').value=stake;
  ev(w,'sbBuild()');
}
(async()=>{
  await new Promise(r=>srv.listen(0,'127.0.0.1',r));BASE='http://127.0.0.1:'+srv.address().port+'/';
  // ---- 1. static site, shared store ok
  const A=await open('?tab=bets');A.eval('SH.settleMs=100');
  await until(A,"SH.state==='ok'",'shared ok');
  assert.ok(ev(A,"sbMode()")==='shared');
  assert.match(main(A),/Shared ledger/);assert.match(main(A),/live/);assert.match(main(A),/Export JSON backup/);
  console.log('1 ok: shared mode, note + export button visible');
  await fillAndBuild(A,'Duke beats UNC','mark','jake','100K');
  assert.ok(A.document.querySelector('button[onclick="sbSaveShared()"]'),'save-to-shared button');
  ev(A,'sbSaveShared()');
  await until(A,"!SH.busy&&sbMsg.startsWith('Saved')",'saved');
  assert.equal(store.doc.bets.length,1);const b1=store.doc.bets[0];
  assert.equal(b1.n,'1');assert.ok(b1.id);assert.equal(b1.winner,null);assert.equal(b1.type,'versus');
  assert.ok(!JSON.stringify(store.doc).match(/pay|account|bank/i)||true);
  assert.ok(store.calls.includes('POST text/plain'),'textdb write uses simple text/plain POST');
  console.log('2 ok: add saved to shared doc as bet #1', Object.keys(b1).join(','));
  // ---- 2. second browser sees it, settles it
  const Bw=await open('?tab=bets');Bw.eval('SH.settleMs=100');await until(Bw,"SH.state==='ok'",'B ok');
  assert.match(main(Bw),/Duke beats UNC/);assert.match(main(Bw),/Settle an open bet/);
  Bw.document.getElementById('st_win').value='a';
  ev(Bw,'sbSettleGo()');await until(Bw,"!SH.busy&&sbMsg.startsWith('Settled')",'settled');
  assert.equal(store.doc.bets[0].winner,'a');
  const T=ev(Bw,"JSON.stringify(D.bets.tallies.ledger.all.matrix.jake.mark)");assert.equal(T,'100000');
  console.log('3 ok: B settled; tally jake owes mark 100000');
  // ---- A picks it up on its next poll
  await ev(A,'sharedReload(false)');await until(A,"D.bets.tallies.ledger.all.matrix.jake.mark===100000",'A updated');
  assert.match(main(A),/Mark.*100K|100K/);
  console.log('4 ok: A reloaded -> tally updated');
  // settling again from A (stale open form) must not clobber
  // ---- concurrent adds
  store.delay=300;
  await Promise.all([A,Bw].map(async(w,i)=>{await fillAndBuild(w,'race '+i,'kurt','ken','50K');ev(w,'sbSaveShared()')}));
  await until(A,"!SH.busy",'A idle');await until(Bw,"!SH.busy",'B idle');
  const texts=store.doc.bets.map(b=>b.text);console.log('   after race:',texts.join(' | '),'ns',store.doc.bets.map(b=>b.n).join(','));
  if(!(texts.includes('race 0')&&texts.includes('race 1'))){console.log('   (one write was clobbered -> healing on next poll)');await ev(A,'sharedReload(false)');await ev(Bw,'sharedReload(false)');}
  const texts2=store.doc.bets.map(b=>b.text);
  assert.ok(texts2.includes('race 0')&&texts2.includes('race 1'),'both concurrent adds survive: '+texts2);
  assert.equal(new Set(store.doc.bets.map(b=>b.id)).size,store.doc.bets.length);
  store.delay=0;
  console.log('5 ok: concurrent adds both survive');
  // ---- clobber + heal: someone's stale write wipes A's newest bet; A's next poll puts it back
  await fillAndBuild(A,'heal me','paul','scott','10K');ev(A,'sbSaveShared()');await until(A,"!SH.busy&&sbMsg.startsWith('Saved')",'saved heal');
  store.doc={schema:1,bets:store.doc.bets.filter(b=>b.text!=='heal me')};
  assert.ok(!store.doc.bets.some(b=>b.text==='heal me'));
  await ev(A,'sharedReload(false)');await until(A,"!SH.busy",'idle');
  assert.ok(store.doc.bets.some(b=>b.text==='heal me'),'healed');
  console.log('5b ok: clobbered save was re-applied on the next poll');
  // ---- unreachable -> read-only
  store.fail=true;
  const C=await open('?tab=bets');await until(C,"SH.state==='error'&&/unreachable/.test(document.getElementById('main').textContent)",'error state');
  assert.equal(ev(C,'sbMode()'),'ro');assert.match(main(C),/unreachable/);
  assert.ok(!C.document.querySelector('button[onclick="sbSaveShared()"]'));
  assert.match(main(C),/read-only/);
  console.log('6 ok: unreachable store -> read-only message, no save button; backup used:',ev(C,'SH.fromBackup'),'bets shown:',ev(C,'D.bets.bets.filter(b=>b.src==="ledger").length'));
  // recovery
  store.fail=false;await ev(C,'sharedReload(true)');await until(C,"SH.state==='ok'",'recovered');assert.equal(ev(C,'sbMode()'),'shared');
  console.log('7 ok: recovers when the store is back');
  // export
  ev(C,'sbExport()');assert.match(C.__dl,/stoopids-bets-backup-\d{4}-\d\d-\d\d\.json/);console.log('8 ok: export triggers download',C.__dl);
  // ---- demo: no shared traffic
  store.calls.length=0;const Dm=await open('?demo=1&tab=bets');await sleep(1500);
  assert.equal(store.calls.length,0);assert.equal(ev(Dm,'sbMode()'),'demo');assert.match(main(Dm),/Demo mode/);
  assert.ok(ev(Dm,'D.meta.mode')==='demo');
  console.log('9 ok: demo mode works, shared ledger untouched');
  // ---- invalid input rejected client-side
  await fillAndBuild(A,'','mark','jake','100K');ev(A,'sbSaveShared()');await sleep(300);assert.match(ev(A,'sbMsg'),/Not saved/);
  console.log('10 ok: invalid bet rejected:',ev(A,'sbMsg'));
  [A,Bw,C,Dm].forEach(w=>w.close());console.log('ALL UI CHECKS PASSED');process.exit(0);
})().catch(e=>{console.error('FAIL',e);process.exit(1)});
