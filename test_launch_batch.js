'use strict';
const assert=require('assert');
const fs=require('fs');
const vm=require('vm');
const html=fs.readFileSync('index.html','utf8');
const css=fs.readFileSync('shared/ui.css','utf8');
const ui=fs.readFileSync('shared/ui.js','utf8');
const yml=fs.readFileSync('.github/workflows/refresh.yml','utf8');

assert.ok(html.includes('gf2 gfwhen'), 'month/day/search sit on the next row');
assert.ok(css.includes('.gf2.gfwhen'));
assert.ok(css.includes('grid-template-columns:minmax(0,1fr) minmax(0,max-content) minmax(0,1fr)'));
assert.ok(!/function s12ShareSite[\s\S]{0,500}navigator\.share/.test(html), 'header Share does not open the native sheet');
assert.ok(html.includes('data-s12="copy"')&&html.includes('data-s12="wa"'));
assert.ok(html.includes("searchParams.set('view','1')"));
assert.ok(/function chatNavBadge\(\)\{[^}]*querySelectorAll\('a\.nt \.nu'\)/.test(html));
assert.ok(html.includes('b27SetStatus')&&html.includes('s25Confirm'));
assert.ok(html.includes('setInterval(()=>load(),2*60*1000)'));
assert.ok(yml.includes('*/10 * * * *')&&yml.includes('GITHUB_TOKEN'));
assert.ok(html.includes('id="wme"')&&html.includes('Waiting on me'));
assert.ok(html.includes('shared/ui.js?v=1.53.0'));
assert.ok(html.includes('SHARED_UI.whenApply'));
assert.ok(!/function b27ActionItem[\s\S]{0,900}if\(later\)/.test(html));
assert.ok(html.includes('shared/ui.css?v=1.30.0'));
assert.ok(html.includes('function b27When('));
assert.ok(html.includes("['dueseason','End of season']"));
assert.ok(!html.includes('h+=wmeHtml'), 'Waiting on me stays a filter, not a second request list');
assert.ok(!html.includes('data-s24-edit='));
assert.ok(html.includes('function b27AssertTerms'));
assert.ok(html.includes('Once a bet is posted, its terms stay as written'));
assert.ok(html.includes("OB_VIEW='form'"));
assert.ok(!html.includes('data-ob="open"'));
assert.ok(html.includes('Write it Up or Request'));
assert.ok(css.includes('.entry-pair'));
assert.ok(ui.includes('Already agreed on a bet?'));
assert.ok(ui.includes('Nothing agreed yet.'));
assert.ok(html.includes('function entryPair()'));
assert.ok(ui.includes('💣')&&ui.includes('💥')&&ui.includes('rq_open_seen:'));
assert.ok(!ui.includes('Bet Requested:'), 'old WhatsApp heading is gone');
assert.ok(/function qbPick\(id,k,i\)\{qbGo\(id,k,i\)\}/.test(html), 'older Quick bet side tap uses Request');
assert.ok(!/function qbGo[\s\S]{0,700}Object\.assign\(U,/.test(html), 'Quick bet does not fill Write it Up');
assert.ok(html.includes("OB_VIEW='request'"));

const store={};
const localStorage={getItem:k=>Object.prototype.hasOwnProperty.call(store,k)?store[k]:null,setItem:(k,v)=>{store[k]=String(v)},removeItem:k=>{delete store[k]}};
const ctx={console,setTimeout,clearTimeout,localStorage,navigator:{},document:{readyState:'loading',head:{appendChild(){}},addEventListener(){},querySelector:()=>null,querySelectorAll:()=>[],createElement:()=>({style:{},setAttribute(){},select(){},remove(){},appendChild(){}}),body:{appendChild(){}}}};
ctx.window=ctx;ctx.globalThis=ctx;
vm.createContext(ctx);
vm.runInContext(ui,ctx);
const names={ken:'Ken',paul:'Paul',a:'Ana',b:'Bea',c:'Cal'};
let me='paul';
const R=ctx.SHARED_UI.Requests({
  me:()=>me,nick:id=>names[id]||id,real:id=>names[id]||id,others:()=>[],games:()=>[],
  get:async()=>'[]',render(){},canWrite:()=>false,placeBet:async()=>{},change:'',e:s=>String(s==null?'':s)
});
const now=Date.now();
const base={id:'r1',status:'open',by:'paul',to:['ken'],amt:5,odds:[1,1],slots:1,txt:'Duke +5.5 vs UConn -5.5',lab:'Duke +5.5',exp:now+3*3600000,took:[],dec:[],gid:'g',start:new Date(now+86400000).toISOString()};
const named=R.waText(base,'new');
assert.strictEqual(named,'💣 $5 Paul v Ken 💣\nDuke +5.5 vs UConn -5.5\nExpires in 3h');
assert.ok(!/even/i.test(named));
const many=R.waText(Object.assign({},base,{to:['ken','a','b'],slots:3}),'new');
assert.strictEqual(many.split('\n')[0],'💣 $5 Paul v Open to 3 stoops 💣');
const odds=R.waText(Object.assign({},base,{odds:[3,1]}),'new');
assert.ok(odds.includes('at 3-1'));
assert.strictEqual((odds.match(/3-1/g)||[]).length,1);
const acc=R.waText(base,'acc','ken');
assert.strictEqual(acc,'💥 $5 Paul v Ken — Accepted 💥\nDuke +5.5 vs UConn -5.5');
assert.ok(!/Expires/.test(acc));
R.S.list=[base,Object.assign({},base,{id:'r2',by:'ken',to:['paul']})];
assert.strictEqual(R.openN(),2);
R.view('open');
assert.strictEqual(R.openN(),0,'viewing Open marks them seen');
R.S.list.push(Object.assign({},base,{id:'r3',by:'a',to:['paul']}));
assert.strictEqual(R.openN(),1,'a new id counts again');
me='ken';
assert.strictEqual(R.openN(),3,'another account has its own seen list');
const S=ctx.SHARED_UI;
const today='2026-11-06';
const rows=S.estSort([
  {id:'old',status:'open',est:'2026-11-01',created_at:'2026-11-01T00:00:00Z'},
  {id:'new',status:'open',est:'2026-11-06',created_at:'2026-10-01T00:00:00Z'},
  {id:'tieB',status:'open',est:'2026-11-06',created_at:'2026-11-02T00:00:00Z'},
  {id:'tieA',status:'open',est:'2026-11-06',created_at:'2026-11-02T00:00:00Z'},
  {id:'fut',status:'open',est:'2026-12-01',created_at:'2026-11-01T00:00:00Z'},
  {id:'none',status:'open',created_at:'2026-11-05T00:00:00Z'},
  {id:'done',status:'backer',est:'2026-11-06',created_at:'2026-11-06T00:00:00Z'}
], today);
assert.deepStrictEqual(rows.map(x=>x.id),['tieA','tieB','new','old','fut','none','done']);
assert.strictEqual(S.estLabel('2026-11-06'),'Nov 6, 2026');
assert.strictEqual(S.estToday(new Date(2026,10,6,0,30)),'2026-11-06');
assert.strictEqual(S.estToday(new Date(2026,10,6,23,30)),'2026-11-06');
assert.strictEqual(S.estOk('2026-02-29'),false);
assert.strictEqual(S.estOk('2024-02-29'),true);
assert.strictEqual(S.estOk('2026-11-31'),false);
assert.strictEqual(S.dueClass('2026-11-05','2026-11-06'),'over');
assert.strictEqual(S.dueClass('2026-11-06','2026-11-06'),'today');
assert.strictEqual(S.dueClass('2026-11-07','2026-11-06'),'up');
assert.strictEqual(S.dueClass('','2026-11-06'),'none');
assert.strictEqual(S.dueClass('2026-02-31','2026-11-06'),'none');
assert.strictEqual(S.dueText('2026-11-07','2026-11-06'),'Settle by: Nov 7, 2026 · Upcoming');
assert.ok(ui.includes('When can this be settled?'));
assert.ok(ui.includes('End of season'));
assert.ok(ui.includes('Not sure yet'));
const season=S.whenPack('season','2026-11-01','2026-27');
assert.strictEqual(season.wk,'season');
assert.strictEqual(season.est,null);
assert.strictEqual(season.sid,'2026-27');
assert.strictEqual(S.whenPack('season','2026-11-01','April 6').sid,null);
assert.strictEqual(S.whenKind({est:'2026-11-06'}),'date');
assert.strictEqual(S.whenKind({}),'unknown');
assert.strictEqual(S.whenKind({wk:'date',est:'2026-02-31'}),'unknown');
const kept=S.whenApply({id:'b',text:'Duke',amt:5,odds:{a:1,b:1},backer:'paul',status:'open',est:'2026-01-01'},{wk:'season',est:'2099-01-01',sid:'2026-27',text:'changed'});
assert.strictEqual(kept.text,'Duke');
assert.strictEqual(kept.amt,5);
assert.strictEqual(kept.est,null);
assert.strictEqual(kept.sid,'2026-27');
assert.strictEqual(S.whenApply({id:'b',text:'Duke'},{wk:'nope'}),null);
assert.strictEqual(S.whenText({wk:'season',sid:'2026-27'}),'When: End of season · 2026-27');
assert.ok(!/2027-0[34]-/.test(S.whenText({wk:'season',sid:'2026-27'})));
const timed=S.estSort([
  {id:'late',status:'open',wk:'date',est:'2026-12-01',created_at:'2026-11-01T00:00:00Z'},
  {id:'sea',status:'open',wk:'season',sid:'2026-27',est:'2026-01-01',created_at:'2026-11-01T00:00:00Z'},
  {id:'ask',status:'reported',wk:'unknown',created_at:'2026-10-01T00:00:00Z'},
  {id:'unk',status:'open',created_at:'2026-11-05T00:00:00Z'},
  {id:'due',status:'open',wk:'date',est:'2026-11-06',created_at:'2026-10-02T00:00:00Z'}
], today);
assert.deepStrictEqual(timed.map(x=>x.id),['ask','due','late','sea','unk']);
console.log('launch batch checks ok');
