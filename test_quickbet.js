// Quick bet + Request a bet. In-memory adapter only: no network, no live ledger.
//   node test_quickbet.js
const assert=require('assert'),fs=require('fs'),path=require('path'),vm=require('vm');
const listeners={};
function el(){return {style:{},value:'',hidden:false,setAttribute(){},addEventListener(){},appendChild(){},remove(){},select(){},classList:{add(){},toggle(){},contains(){return false}},querySelector(){return null},querySelectorAll(){return []},set textContent(v){this._t=v},get textContent(){return this._t||''}}}
const document={
  readyState:'loading',
  addEventListener(type,fn){(listeners[type]=listeners[type]||[]).push(fn)},
  createElement:el,head:{appendChild(){}},body:{appendChild(){}},
  querySelector(){return null},querySelectorAll(){return []},execCommand(){return true},
  getElementById(){return null}
};
const NOW=Date.parse('2026-11-06T18:00:00Z');
const START=Date.parse('2026-11-07T01:00:00Z'); // 20:00 ET the same evening: a real tip, not 00:00/23:59
const TBD='2026-11-11T05:00:00Z'; // midnight ET
let now=NOW;
const realNow=Date.now;
Date.now=()=>now;
const sandbox={console,setTimeout,clearTimeout,Date,Intl,Math,JSON,Object,Array,String,Number,isFinite,isNaN,document,navigator:{clipboard:null},globalThis:null};
sandbox.globalThis=sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(__dirname,'shared/ui.js'),'utf8'),sandbox,{filename:'shared/ui.js'});
const UI=sandbox.SHARED_UI;
const duke={id:'d',short:'Duke'},uconn={id:'u',short:'UConn'};
const lineGame={away:duke,home:uconn,line:{fav:'u',sp:5.5,ou:140,aml:120,hml:-140}};
const opts=UI.qbOptions(lineGame,{name:s=>s.short,date:'Sat Nov 7'});
const sp=opts.find(o=>o.k==='sp');
assert.ok(sp&&sp.s.length===2,'spread has both sides');
assert.equal(sp.s[0].txt,'UConn -5.5 vs Duke +5.5, Sat Nov 7');
assert.equal(sp.s[1].txt,'Duke +5.5 vs UConn -5.5, Sat Nov 7');
assert.ok(sp.s[1].txt.startsWith('Duke +5.5'),'chosen underdog keeps the positive points');
assert.equal(UI.qbOptions({away:duke,home:uconn,line:null},{name:s=>s.short,date:'Sat Nov 7'}).length,0,'no posted odds -> no generated sides');
assert.equal(UI.qbBlankText({away:duke,home:uconn},{name:s=>s.short,date:'Sat Nov 7'}),'Duke vs UConn, Sat Nov 7');
const sheet=UI.qbSheet({away:duke,home:uconn},[],{e:s=>s,name:s=>s.short,date:'Sat Nov 7',close:()=>'',blank:()=>'data-blank="1"',pick:()=>''});
assert.match(sheet,/No odds posted/);
assert.match(sheet,/Request a bet/);
assert.doesNotMatch(sheet,/data-rq="send"/,'the picker does not submit');

const games=[];
let doc={v:1,reqs:[]};
const placed=[];
const sets=[];
const A={
  e:s=>String(s==null?'':s),me:()=>'paul',
  others:()=>[{id:'murf',emoji:'',nick:'Murf'},{id:'stock',emoji:'',nick:'Stock'},{id:'kentut',emoji:'',nick:'Kentut'}],
  nick:id=>id,real:id=>id,canWrite:()=>true,amounts:[5,10,20,25,50],maxText:140,
  games:()=>games,tname:s=>s.short||s.name||s.id,dateET:()=>'Sat Nov 7',
  get:async()=>JSON.stringify(doc),
  set:async txt=>{sets.push(txt);doc=JSON.parse(txt)},
  placeBet:async(r,me)=>{placed.push({r,me})},
  render(){}
};
function add(g){games.push(g);return g}
add({id:'g-line',g:lineGame,start:new Date(START).toISOString(),status:'scheduled',tbd:false});
add({id:'g-none',g:{away:duke,home:uconn,line:null},start:new Date(START).toISOString(),status:'scheduled',tbd:false});
add({id:'g-tbd',g:{away:{id:'a',short:'Pine'},home:{id:'b',short:'UCLA'},line:null},start:TBD,status:'scheduled',tbd:true});
add({id:'g-live',g:lineGame,start:new Date(NOW-3600000).toISOString(),status:'live',tbd:false});
const RQ=UI.Requests(A);RQ.S.at=now;
function fire(type,dataset){
  const t={dataset,closest(sel){return sel==='[data-rq]'||sel==='[data-rq-in]'?t:null}};
  (listeners[type]||[]).forEach(fn=>fn({target:t,preventDefault(){}}));
}
async function click(k,v){fire('click',{rq:k,v:v==null?'':String(v)});await settle()}
async function settle(){for(let i=0;i<30;i++){await new Promise(r=>setTimeout(r,80));if(!RQ.S.busy)return}throw new Error('still busy '+RQ.S.msg)}
function html(){return RQ.view()}

(async()=>{
  const before=sets.length;
  RQ.prefill('g-line','sp',1);
  assert.equal(RQ.S.f.text,'Duke +5.5 vs UConn -5.5, Sat Nov 7');
  assert.equal(RQ.S.f.cov,'game','full game stays the default');
  assert.equal(sets.length,before,'prefill does not post');
  assert.match(html(),/At tip-off/);
  assert.match(html(),/value="Duke \+5\.5 vs UConn -5\.5, Sat Nov 7"/);
  RQ.S.f.text='1st half: Duke +5.5 vs UConn -5.5';
  assert.match(html(),/value="1st half: Duke \+5\.5 vs UConn -5\.5"/,'period bets stay free text');
  RQ.S.f.text='Duke +5.5 vs UConn -5.5, Sat Nov 7';
  await click('to','murf');await click('to','stock');
  assert.deepEqual(RQ.S.f.to,['murf','stock']);
  await click('fslot+');
  assert.equal(RQ.S.f.slots,2,'acceptance limit can be raised to the invitees');
  await click('amt','10');
  RQ.S.f.mode='start';
  const postsBefore=sets.length,placedBefore=placed.length;
  await click('send');
  assert.equal(placed.length,placedBefore,'Request bet does not accept a bet by itself');
  assert.ok(sets.length>postsBefore,'the request is stored only after Request bet');
  const saved=doc.reqs[doc.reqs.length-1];
  assert.equal(saved.exp,START,'At tip-off expiry is the scheduled start');
  assert.deepEqual(saved.to,['murf','stock']);
  assert.equal(saved.slots,2);
  assert.equal(saved.txt,'Duke +5.5 vs UConn -5.5, Sat Nov 7');
  assert.equal(saved.by,'paul');
  assert.match(RQ.waText(saved),/Bet Requested: 10\$/);
  // nobody can accept once the start is reached, and it must not become a bet
  saved.by='stock';saved.to=['paul','murf'];RQ.S.list=doc.reqs.map(r=>Object.assign({},r));
  now=START;
  await click('acc',saved.id);
  assert.equal(placed.length,placedBefore);
  assert.match(RQ.S.msg,/already started/);
  now=START+60000;
  await click('acc',saved.id);
  assert.equal(placed.length,placedBefore);
  assert.match(RQ.S.msg,/already started/);
  // a minute before tip-off the same request can still be accepted (in memory only)
  now=START-60000;
  await click('acc',saved.id);
  assert.equal(placed.length,placedBefore+1);
  assert.equal(placed[0].me,'paul');
  // no odds: editable matchup, and At tip-off still comes from the real start
  now=NOW;doc={v:1,reqs:[]};RQ.S.list=[];
  RQ.prefill('g-none','',0);
  assert.equal(RQ.S.f.text,'Duke vs UConn, Sat Nov 7');
  RQ.S.f.text='Duke +3.5 vs UConn -3.5';
  assert.match(html(),/At tip-off/);
  await click('to','kentut');await click('amt','5');
  RQ.S.f.mode='start';
  await click('send');
  assert.equal(doc.reqs[0].txt.startsWith('Duke +3.5 vs UConn -3.5'),true);
  assert.equal(doc.reqs[0].exp,START);
  assert.deepEqual(doc.reqs[0].to,['kentut']);
  // TBD: At tip-off is not offered and a forced start mode is not stored as the placeholder
  RQ.prefill('g-tbd','',0);
  const tbdHtml=html();
  assert.doesNotMatch(tbdHtml,/At tip-off/);
  assert.match(tbdHtml,/>hours</);
  RQ.S.f.mode='start';RQ.S.f.text='Pine vs UCLA, pick a line';
  const n=doc.reqs.length;
  await click('to','murf');await click('amt','5');await click('send');
  assert.equal(doc.reqs.length,n,'TBD At tip-off does not post a made-up timestamp');
  assert.match(RQ.S.msg,/expires/);
  RQ.S.f.mode='h';RQ.S.f.n=4;
  await click('send');
  assert.equal(doc.reqs.length,n+1);
  assert.notEqual(doc.reqs[doc.reqs.length-1].exp,Date.parse(TBD));
  assert.ok(doc.reqs[doc.reqs.length-1].exp>now);
  console.log('test_quickbet: ok');
  Date.now=realNow;
  process.exit(0);
})().catch(e=>{console.error(e);process.exit(1)});
