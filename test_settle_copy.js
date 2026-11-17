// PAUL-l: Copy on a bet that is ready for someone else to settle.
// Non-GET is aborted, so nothing is written to the bet ledger.
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
  await page.addInitScript(() => { try { localStorage.setItem('stoopids_who', 'Kurmoji'); } catch (e) {} });
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  await page.goto('http://127.0.0.1:8766/index.html?tab=bets', {waitUntil: 'domcontentloaded', timeout: 60000});
  await page.waitForFunction(() => window.SHARED_UI && D && D.games && typeof RQ !== 'undefined' && typeof s29eCopyText === 'function' && b27Who(), null, {timeout: 30000});

  const out = await page.evaluate(() => {
    const g = (D.games || []).find(x => String(x.id) === '401916305');
    const rd = {k: 'spread', t: 'Minnesota', o: 'Cincinnati', l: -1.5, sp: 'mcbb', d: g.day};
    const bet = {id: 'fixture-settle', n: 5, backer: 'Paul', other: 'Kurmoji', amt: 5, odds: {a: 1, b: 1},
      text: 'Minnesota -1.5 vs Cincinnati +1.5', status: 'open', wk: 'game', rd, created_at: '2026-11-09T20:00:00Z', gid: g.id, start: g.start, date: g.day};
    const pushRd = Object.assign({}, rd, {l: -2});
    const push = Object.assign({}, bet, {n: 6, rd: pushRd, text: 'Minnesota -2 vs Cincinnati +2'});
    const season = Object.assign({}, bet, {n: 7, wk: 'season', rd: null, text: 'Paul outscores Kurt in league points'});
    const mine = s29eCopyText(bet);
    const open = s29eOpenCopy(bet);
    const pushed = s29eCopyText(push);
    const later = s29eCopyText(season);
    const seasonOpen = s29eOpenCopy(season);
    const req = RQ.copyText({by: 'Paul', to: ['Kurmoji'], amt: 5, odds: [1, 1], rd, n: 5, wk: 'game'}, 'bet');
    const prev = PS.who;
    PS.who = 'Paul';
    const asSettler = s29eCopyText(bet);
    PS.who = prev;
    return {who: b27Who(), only: 'Only ' + PN(bet.backer) + ' can enter result.', mine, open, pushed, later, seasonOpen, req, asSettler,
      ready: b27Ready(bet), other: b27NeedsOther(bet, 'Kurmoji'), win: s29eSettleWin(bet), pushWin: s29eSettleWin(push)};
  });
  assert.equal(out.who, 'Kurmoji');
  assert.equal(out.ready, true);
  assert.equal(out.other, true);
  assert.equal(out.win, 'Paul');
  const lines = out.mine.split('\n');
  assert.equal(lines.length, 4, out.mine);
  assert.equal(lines[0], '🎉 Bet #5 · Paul Won 🎉');
  assert.equal(lines[1], 'Hey Paul, settle this bet!');
  assert.equal(lines[2], 'Minnesota -1.5 v Cincinnati');
  assert.equal(lines[3], 'Nov 9');
  assert.ok(!/Exp:|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b/.test(out.mine), out.mine);
  assert.ok(!/[\$💥💣]/.test(out.mine), out.mine);
  const pushLines = out.pushed.split('\n');
  assert.equal(pushLines[0], '🎉 Bet #6 🎉', out.pushed);
  assert.equal(pushLines.length, 4);
  assert.equal(out.later, out.seasonOpen, 'a bet that is not ready stays on the ordinary copy');
  assert.ok(out.later.indexOf('💣') === 0 || out.later.indexOf('💥') === 0, out.later);
  assert.equal(out.asSettler, out.open, 'the settler still gets the ordinary copy');
  assert.ok(out.req.indexOf('💣') === 0 && /Exp:/.test(out.req), out.req);
  assert.equal(writes.some(w => /stoopids-bets-2627-/.test(w) || /stoopids-requests-/.test(w)), false);
  if (errors.length) throw new Error(errors.join('\n'));
  console.log(JSON.stringify({ok: true, copy: out.mine, push: pushLines[0], settlerSame: out.asSettler === out.open}));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
