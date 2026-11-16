// Ken's request: "High Point covers the -7.5 at St Louis" must stay on game 401911251.
// Non-GET is aborted, so nothing is written to the request or bet ledger.
const {chromium} = require('/tmp/pw/node_modules/playwright-core');
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
  await page.addInitScript(() => { try { localStorage.setItem('stoopids_who', 'Kentut'); } catch (e) {} });
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  await page.goto('http://127.0.0.1:8766/index.html', {waitUntil: 'domcontentloaded', timeout: 60000});
  await page.waitForFunction(() => window.SHARED_UI && D && D.games && typeof RQ !== 'undefined' && typeof S25 !== 'undefined', null, {timeout: 30000});

  const text = 'High Point covers the -7.5 at St Louis';
  const found = await page.evaluate((text) => {
    const games = (D.games || []).filter(g => g && g.home && g.away).map(g => ({id: String(g.id), g, start: g.start, status: g.status}));
    const opts = {games, gid: '', text, now: Date.now(), today: S25.etDay(new Date()), dateFrom: S25.dateFrom, day: S25.etDay};
    const hit = SHARED_UI.tipGame(opts);
    const parsed = S25.parse(text, '2026-11-15T18:00:00Z');
    const g = (D.games || []).find(x => String(x.id) === '401911251');
    const matched = g ? b27GameMatched({rd: {k: 'spread', t: 'High Point', o: 'St Louis', l: -7.5, sp: 'mcbb', d: g.day}, status: 'open', text}) : null;
    RQ.prefill('401911251', 'sp', 0);
    const gidBefore = RQ.S.f.gid;
    RQ.S.f.text = text;
    RQ.S.f.rd = null;
    RQ.S.f.lineKind = '';
    const kept = RQ.S.f.gid;
    const still = SHARED_UI.tipGame(Object.assign({}, opts, {gid: kept}));
    const upcoming = g && g.status === 'scheduled' && Date.parse(g.start) > Date.now();
    return {
      id: hit && String(hit.id),
      upcoming,
      parsed: {k: parsed.k, t: parsed.t, o: parsed.o, l: parsed.l},
      matched: matched && String(matched.id),
      gidBefore, kept, still: still && String(still.id)
    };
  }, text);
  assert.equal(found.parsed.k, 'spread');
  assert.equal(found.parsed.t, 'High Point');
  assert.equal(found.parsed.l, -7.5);
  assert.equal(found.matched, '401911251');
  assert.equal(found.gidBefore, '401911251');
  assert.equal(found.kept, '401911251', 'rewriting the Quick bet text keeps the game id');
  if (found.upcoming) {
    assert.equal(found.id, '401911251', 'the sentence with no saved id still finds Saint Louis v High Point');
    assert.equal(found.still, '401911251');
  } else {
    assert.equal(found.id, null, 'a finished game is not used as the tipoff');
    assert.equal(found.still, '401911251', 'a picked game id is kept even after the text is rewritten');
  }

  await page.evaluate((text) => {
    tab = 'bets27'; OB_VIEW = 'request';
    RQ.S.f.gid = '';
    RQ.S.f.text = text;
    RQ.S.f.to = ['Paul'];
    RQ.S.f.amt = 5;
    RQ.S.f.odds = [1, 1];
    RQ.S.f.mode = 'start';
    RQ.S.f.wk = 'game';
    RQ.S.f.expPick = false;
    RQ.S.f.whenPick = true;
    RQ.S.msg = '';
    render();
    document.querySelector('#rqForm [data-rq="send"]').dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, button: 0}));
  }, text);
  await page.waitForTimeout(800);
  const sent = await page.evaluate(() => ({msg: RQ.S.msg, gid: RQ.S.f.gid}));
  const posted = writes.filter(w => /stoopids-requests-/.test(w));
  if (found.upcoming) {
    assert.equal(sent.msg, 'Could not send it. Try again.', 'a matched game is not blocked with Name the game');
    assert.equal(posted.length > 0, true, 'send attempted a request write, which this test aborted');
  } else {
    assert.ok(/Pick when it expires/.test(sent.msg), sent.msg);
    assert.equal(posted.length, 0);
  }

  writes.length = 0;
  await page.evaluate(() => {
    RQ.S.f.gid = '';
    RQ.S.f.text = 'zzzz no teams in this sentence';
    RQ.S.f.amt = 5;
    RQ.S.f.to = ['Paul'];
    RQ.S.msg = '';
    render();
    document.querySelector('#rqForm [data-rq="send"]').dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, button: 0}));
  });
  await page.waitForTimeout(200);
  const none = await page.evaluate(() => RQ.S.msg);
  assert.ok(/Pick when it expires/.test(none), none);
  assert.equal(writes.some(w => /stoopids-requests-/.test(w)), false);
  assert.ok(!writes.some(w => /stoopids-bets-2627-/.test(w)));
  if (errors.length) throw new Error(errors.join('\n'));
  console.log(JSON.stringify({ok: true, id: found.id, parsed: found.parsed, none}));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
