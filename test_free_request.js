// A free-written request with no matching game posts the words as typed.
// Expiry and settle are the ones the user picked. Nothing is written: non-GET is aborted.
const {chromium} = require('/tmp/pw/node_modules/playwright-core');
const assert = require('assert');

(async () => {
  const browser = await chromium.launch({executablePath: '/usr/local/bin/google-chrome', args: ['--no-sandbox', '--disable-dev-shm-usage']});
  const page = await browser.newPage({viewport: {width: 390, height: 844}});
  const writes = [];
  await page.route('**/*', route => {
    const req = route.request();
    const m = req.method();
    if (m !== 'GET' && m !== 'HEAD' && m !== 'OPTIONS') {
      writes.push({m, url: req.url(), body: req.postData() || ''});
      return route.abort();
    }
    return route.continue();
  });
  await page.addInitScript(() => { try { localStorage.setItem('stoopids_who', 'Kentut'); } catch (e) {} });
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  await page.goto('http://127.0.0.1:8766/index.html?tab=bets', {waitUntil: 'domcontentloaded', timeout: 60000});
  await page.waitForFunction(() => window.SHARED_UI && D && D.games && typeof RQ !== 'undefined', null, {timeout: 30000});

  const text = 'High Point covers the -7.5 at St Louis';
  const prep = await page.evaluate((text) => {
    const games = (D.games || []).filter(g => g && g.home && g.away).map(g => ({id: String(g.id), g, start: g.start, status: g.status}));
    const opts = {games, now: Date.now(), today: S25.etDay(new Date()), dateFrom: S25.dateFrom, day: S25.etDay};
    const hit = SHARED_UI.tipGame(Object.assign({gid: '', text}, opts));
    const linked = SHARED_UI.tipGame(Object.assign({gid: '', text: 'Grambling covers the -7.5 at Kentucky'}, opts));
    tab = 'bets27'; OB_VIEW = 'request';
    RQ.S.f = Object.assign(RQ.S.f, {gid: '', text, rd: null, lineKind: '', to: ['Paul'], amt: 5, odds: [1, 1], mode: 'd', n: 3, expPick: true, whenPick: true, wk: 'season', est: '', parlay: false, legs: []});
    RQ.S.msg = '';
    render();
    document.querySelector('#rqForm [data-rq="send"]').dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, button: 0}));
    return {hit: hit && String(hit.id), linked: linked && String(linked.id)};
  }, text);
  assert.equal(prep.hit, null, 'the finished St Louis game is not an automatic tipoff match');
  assert.equal(prep.linked, '401921804', 'wording that names an upcoming game still matches');
  await page.waitForTimeout(900);
  const msg = await page.evaluate(() => RQ.S.msg);
  assert.ok(!/No game matches those words/.test(msg), msg);
  const posted = writes.filter(w => w.m === 'POST' && /stoopids-requests-/.test(w.url));
  assert.equal(posted.length > 0, true, 'send attempted a request write, which this test aborted');
  assert.equal(writes.some(w => /stoopids-bets-2627-/.test(w.url)), false);
  const body = JSON.parse(posted[0].body);
  const row = (body.reqs || []).slice().reverse().find(r => r && r.txt === text);
  assert.ok(row, 'posted text is the sentence as written');
  assert.equal(row.gid || '', '');
  assert.equal(row.free, 1);
  assert.equal(row.rd, undefined);
  assert.equal(row.wk, 'season');
  assert.ok(row.exp > Date.now(), 'expiry is the chosen clock time, not tipoff');
  const copy = await page.evaluate((row) => RQ.copyText(row, 'new'), row);
  assert.ok(copy.indexOf('\uD83D\uDCA3 $5 ') === 0, copy);
  assert.ok(copy.indexOf(text) > 0, copy);
  assert.ok(/Exp: /.test(copy), copy);
  assert.ok(!/Suggested winner|Tipoff|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday/.test(copy), copy);
  if (errors.length) throw new Error(errors.join('\n'));
  console.log(JSON.stringify({ok: true, copy, wk: row.wk, exp: row.exp}));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
