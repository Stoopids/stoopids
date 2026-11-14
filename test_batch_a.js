// Batch A checks. Local page only. Non-GET requests are aborted, including presence and ledgers.
const {chromium} = require('/tmp/pw/node_modules/playwright-core');
const fs = require('fs');
const assert = require('assert');

(async () => {
  const browser = await chromium.launch({executablePath: '/usr/local/bin/google-chrome', args: ['--no-sandbox', '--disable-dev-shm-usage']});
  const page = await browser.newPage({viewport: {width: 390, height: 844}});
  const writes = [];
  await page.route('**/*', route => {
    const m = route.request().method();
    if (m !== 'GET' && m !== 'HEAD' && m !== 'OPTIONS') {
      writes.push(m + ' ' + route.request().url());
      return route.abort();
    }
    return route.continue();
  });
  await page.addInitScript(() => { try { localStorage.setItem('stoopids_who', 'Paul'); } catch (e) {} });
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  await page.goto('http://127.0.0.1:8765/index.html', {waitUntil: 'domcontentloaded', timeout: 60000});
  await page.waitForFunction(() => window.SHARED_UI && typeof S25 !== 'undefined' && typeof RQ !== 'undefined' && D && D.owners, null, {timeout: 30000});

  const logic = await page.evaluate(() => {
    const out = {};
    const settled = {status: 'backer', wk: 'date', est: '2026-11-07', text: 'Devils beat Islanders tomorrow'};
    const open = {status: 'open', wk: 'date', est: '2026-11-07'};
    out.settledText = SHARED_UI.whenText(settled);
    out.settledShow = SHARED_UI.whenShow(settled);
    out.settledClass = SHARED_UI.whenClass(settled);
    out.openText = SHARED_UI.whenText(open);
    out.openClass = SHARED_UI.whenClass(open);
    out.filterStillOver = s24WhenOk(settled, 'over');
    out.washText = SHARED_UI.whenText({status: 'push', wk: 'date', est: '2026-11-01'});
    const text = 'Over 142.5 vs Under 142.5, Houston v California, Sun Nov 8';
    const rd = S25.parse(text, '2026-11-08T18:00:00Z');
    out.rd = rd;
    out.over = S25.result(rd, 80, 70);
    out.underMiss = S25.result(rd, 60, 70);
    out.push = S25.result(rd, 70, 72.5);
    const under = S25.parse('Under 142.5 vs Over 142.5, Houston v California, Sun Nov 8', '2026-11-08T18:00:00Z');
    out.underRd = {k: under.k, ou: under.ou, l: under.l, t: under.t, o: under.o};
    out.underHits = S25.result(under, 60, 70);
    out.oldTotal = S25.parse('Duke vs Kansas over 145.5', '2026-11-08T18:00:00Z');
    const bet = {id: 'b43', n: 43, status: 'open', text, rd: {k: 'manual'}, backer: 'Paul', other: 'Murf', amt: 5, odds: {a: 1, b: 1}, wk: 'game', est: null, created_at: '2026-11-08T18:00:00Z'};
    out.betRd = s25BetRd(bet);
    const key = s25Key(out.betRd);
    S25P.games[key] = {st: 'ok', at: Date.now(), sb: {events: [{id: 'g43', competitions: [{competitors: [
      {team: {shortDisplayName: 'Houston', displayName: 'Houston', location: 'Houston'}, score: '80'},
      {team: {shortDisplayName: 'California', displayName: 'California', location: 'California'}, score: '70'}
    ], status: {type: {name: 'STATUS_FINAL', completed: true, state: 'post'}}}]}]}};
    out.game = s25Game(bet);
    out.storedStillManual = bet.rd.k;
    U.doc = U.doc || {bets: []};
    const fake = {id: 'local-only', status: 'open', text: 'Local fixture', amt: 5, odds: {a: 1, b: 1}, backer: 'Paul', other: 'Murf', wk: 'unknown', est: null, kind: 'bet'};
    U.doc.bets = [fake];
    U.tapUntil = 0;
    U.askSettle = null;
    b27Ask(fake.id, 'backer');
    out.armed = U.askSettle && U.askSettle.what;
    b27Ask(fake.id, 'push');
    out.repeatIgnored = U.askSettle && U.askSettle.what;
    U.tapUntil = 0;
    U.askSettle = {id: fake.id, what: 'backer', terms: b27Terms(fake)};
    b27DropStale();
    out.dropKept = !!(U.askSettle && U.askSettle.id === fake.id);
    fake.amt = 9;
    b27DropStale();
    out.dropCleared = !U.askSettle;
    U.tapUntil = 0;
    const oldTerms = b27Terms(Object.assign({}, fake, {amt: 5, text: 'Local fixture'}));
    U.askSettle = {id: fake.id, what: 'backer', terms: oldTerms};
    b27SetStatus(fake.id, 'backer');
    out.staleMsg = U.msg;
    out.askCleared = !U.askSettle;
    out.noWriteFromStale = U.busy === false;
    return out;
  });

  assert.equal(logic.settledText, 'When: Nov 7, 2026');
  assert.equal(logic.settledShow, 'done');
  assert.equal(logic.settledClass, 'over');
  assert.ok(logic.openText.includes('Overdue'));
  assert.equal(logic.openClass, 'over');
  assert.equal(logic.filterStillOver, true);
  assert.equal(logic.washText, 'When: Nov 1, 2026');
  assert.equal(logic.rd.k, 'total');
  assert.equal(logic.rd.ou, 'o');
  assert.equal(logic.rd.l, 142.5);
  assert.equal(logic.rd.t, 'Houston');
  assert.equal(logic.rd.o, 'California');
  assert.equal(logic.over.r, 'backer');
  assert.ok(logic.over.why.includes('hits'));
  assert.equal(logic.underMiss.r, 'other');
  assert.equal(logic.push.r, 'push');
  assert.ok(logic.push.why.includes('push on 142.5'));
  assert.equal(logic.underRd.ou, 'u');
  assert.equal(logic.underHits.r, 'backer');
  assert.equal(logic.oldTotal.k, 'total');
  assert.equal(logic.betRd.k, 'total');
  assert.equal(logic.storedStillManual, 'manual');
  assert.ok(logic.game && logic.game.p && logic.game.p.r === 'backer', JSON.stringify(logic.game));
  assert.equal(logic.staleMsg, 'That bet changed. Review it again.');
  assert.equal(logic.askCleared, true);
  assert.equal(logic.armed, 'backer');
  assert.equal(logic.repeatIgnored, 'backer');
  assert.equal(logic.dropKept, true);
  assert.equal(logic.dropCleared, true);
  await page.waitForTimeout(4000);

  const writesBefore = writes.length;
  const cancel = await page.evaluate(() => {
    RQ.S.loading = true;
    RQ.S.at = Date.now();
    RQ.S.busy = false;
    RQ.S.lockUntil = 0;
    RQ.S.arm = null;
    RQ.S.list.push({id: 'rq-fixture-only', by: 'Paul', to: ['Murf'], status: 'open', took: [], dec: [], lab: 'Fixture only', txt: 'Fixture only', amt: 5, odds: [1, 1], exp: Date.now() + 86400000, at: Date.now(), wk: 'unknown', slots: 1});
    const realFetch = window.fetch;
    window.fetch = function(url, opts){
      const u = typeof url === 'string' ? url : (url && url.url) || '';
      const method = (opts && opts.method) || (url && url.method) || 'GET';
      if (String(u).includes('stoopids-requests-2627') && String(method).toUpperCase() === 'GET') {
        return Promise.resolve({ok: true, status: 200, text: () => Promise.resolve(JSON.stringify({v: 1, reqs: RQ.S.list}))});
      }
      return realFetch.apply(this, arguments);
    };
    tab = 'bets27';
    OB_VIEW = 'all';
    render();
    const btn = document.querySelector('[data-rq-id="rq-fixture-only"] [data-rq="cancel"]');
    return {label: btn ? btn.textContent : '', stamp: btn ? btn.getAttribute('data-st') : ''};
  });
  assert.equal(cancel.label, 'Delete');
  await page.click('[data-rq-id="rq-fixture-only"] [data-rq="cancel"]');
  const armed = await page.locator('[data-rq-id="rq-fixture-only"] [data-rq="cancel"]').textContent();
  assert.equal(armed.trim(), 'Tap again to delete');
  assert.equal(writes.length, writesBefore, 'first delete tap must not write: ' + writes.slice(writesBefore).join(','));
  await page.waitForTimeout(500);
  await page.click('[data-rq-id="rq-fixture-only"] [data-rq="cancel"]');
  await page.waitForTimeout(800);
  const attempted = writes.slice(writesBefore);
  assert.ok(attempted.some(u => u.includes('stoopids-requests-2627') && u.startsWith('POST')), 'second tap should attempt the blocked delete: ' + attempted.join(','));

  await page.evaluate(() => { tab = 'bets27'; OB_VIEW = 'request'; const g = (D.games || []).find(x => x && x.status === 'scheduled' && x.home && x.away); if (g) RQ.S.f.gid = String(g.id); render(); });
  await page.waitForSelector('#rqForm [data-when="game"]');
  const phone = await page.evaluate(() => {
    const when = [...document.querySelectorAll('#rqForm [data-when]')].map(el => ({id: el.getAttribute('data-when'), text: el.textContent, display: getComputedStyle(el).display}));
    const exp = [...document.querySelectorAll('#rqForm select[data-rq-in="mode"] option')].map(o => o.value + ':' + o.textContent);
    return {when, exp};
  });
  await page.setViewportSize({width: 1280, height: 900});
  await page.evaluate(() => render());
  const desk = await page.evaluate(() => {
    const when = [...document.querySelectorAll('#rqForm [data-when]')].map(el => ({id: el.getAttribute('data-when'), text: el.textContent, display: getComputedStyle(el).display}));
    const exp = [...document.querySelectorAll('#rqForm select[data-rq-in="mode"] option')].map(o => o.value + ':' + o.textContent);
    return {when, exp};
  });
  assert.deepEqual(phone.exp, desk.exp);
  assert.ok(phone.exp.some(x => x.startsWith('start:Tipoff')), phone.exp.join('|'));
  assert.deepEqual(phone.when.map(x => x.id + ':' + x.text), desk.when.map(x => x.id + ':' + x.text));
  assert.ok(phone.when.some(x => x.id === 'game' && x.display !== 'none'));
  assert.ok(desk.when.some(x => x.id === 'game' && x.display !== 'none'));

  await page.setViewportSize({width: 390, height: 844});
  await page.evaluate(() => { const el = document.querySelector('#rqForm .rq-exp') || document.querySelector('#rqForm [data-when="game"]'); if (el) el.scrollIntoView({block: 'center'}); });
  fs.mkdirSync('/opt/cursor/artifacts', {recursive: true});
  await page.screenshot({path: '/opt/cursor/artifacts/batch-a-phone.png'});
  if (errors.length) throw new Error(errors.join('\n'));
  console.log(JSON.stringify({ok: true, phoneExp: phone.exp, phoneWhen: phone.when, writes: writes.length, suggestion: logic.game.p}, null, 2));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
