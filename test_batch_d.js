// Batch D display checks. Non-GET aborted. No ledger writes.
const {chromium} = require('/tmp/pw/node_modules/playwright-core');
const fs = require('fs');
const assert = require('assert');
(async () => {
  const browser = await chromium.launch({executablePath: '/usr/local/bin/google-chrome', args: ['--no-sandbox', '--disable-dev-shm-usage']});
  const page = await browser.newPage({viewport: {width: 390, height: 844}});
  const writes = [];
  await page.route('**/*', route => {
    const m = route.request().method();
    if (m !== 'GET' && m !== 'HEAD' && m !== 'OPTIONS') { writes.push(route.request().url()); return route.abort(); }
    return route.continue();
  });
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  await page.goto('http://127.0.0.1:8767/index.html', {waitUntil: 'domcontentloaded', timeout: 60000});
  await page.waitForFunction(() => window.SHARED_UI && D && D.games && U && U.doc, null, {timeout: 30000});
  const logic = await page.evaluate(() => {
    const bet = {id: 'local', n: 34, status: 'open', kind: 'bet', backer: 'Paul', other: 'Kurmoji', amt: 5, odds: {a: 2, b: 1}, text: 'Morehead St +21 vs Louisville -21', wk: 'game', est: null, created_at: '2026-11-07T12:00:00Z', rd: {k: 'spread', t: 'Morehead St', o: 'Louisville', l: 21, d: '2026-11-07', sp: 'mcbb'}};
    const copy = s29eOpenCopy(bet);
    const settled = s29eCopyText(Object.assign({}, bet, {status: 'backer'}));
    const wash = b27Card(Object.assign({}, bet, {status: 'push', n: 28, id: 'w28', created_at: '2026-11-07T12:00:00Z'}), null);
    const line = lineTxt({fav_name: 'Louisville', sp: 21, ou: 142.5}, 'Morehead St', 'Louisville', false);
    const qb = qbOpts({away: {id: 'a', short: 'A'}, home: {id: 'h', short: 'H'}, line: {fav: 'a', sp: 3, ou: 140}}).map(x => x.t);
    const g = (D.games || []).find(x => x && x.id);
    U.doc.bets = [Object.assign({}, bet, {src: {g: String(g.id), sc: '1-0'}}), {id: 'nope', n: 99, status: 'open', kind: 'bet', text: 'unrelated', rd: {k: 'manual'}}];
    gBetCache = null;
    const html = gBetLinkHtml(g);
    const other = (D.games || []).find(x => x && String(x.id) !== String(g.id));
    gBetCache = null;
    const none = other ? gBetLinkHtml(other) : '';
    const shown = html.replace(/<[^>]+>/g, '');
    return {copy, settledStarts: settled.slice(0, 12), washHas: wash.includes('💦'), washWord: /Wash/.test(wash), line, qb, html, shown, noneHas99: none.includes('#99')};
  });
  assert.equal(logic.copy, '💣 $5 Paul v Kurt · 2–1 💣\nMorehead St +21 v Louisville\nSat Nov 7 · Exp: Tip');
  assert.ok(logic.settledStarts.startsWith('💥 Bet #'));
  assert.equal(logic.washHas, true);
  assert.equal(logic.washWord, false);
  assert.ok(logic.line.includes('O/U 142.5') && !logic.line.includes('Over/under'));
  assert.ok(logic.qb.includes('Over/under'));
  assert.equal(logic.shown.trim(), '#34');
  assert.equal(logic.noneHas99, false);
  await page.evaluate(() => { tab = 'games'; render(); window.render = function(){}; });
  await page.waitForSelector('.gl, .ggrid');
  const desk = await page.evaluate(() => {
    const el = document.querySelector('.ggrid .gow');
    if (!el) return null;
    const cs = getComputedStyle(el);
    const pill = el.querySelector('.opill');
    return {whiteSpace: cs.whiteSpace, overflow: cs.overflow, names: pill ? pill.textContent : ''};
  });
  await page.setViewportSize({width: 1280, height: 900});
  const wide = await page.evaluate(() => {
    const el = document.querySelector('.ggrid .gow:not([aria-hidden="true"])');
    if (!el) return null;
    const cs = getComputedStyle(el);
    return {whiteSpace: cs.whiteSpace, overflow: cs.overflow, col: cs.gridColumn, text: el.textContent.trim().slice(0, 40)};
  });
  if (desk) assert.equal(desk.whiteSpace, 'normal');
  if (wide) { assert.equal(wide.whiteSpace, 'normal'); assert.notEqual(wide.overflow, 'hidden'); }
  fs.mkdirSync('/opt/cursor/artifacts', {recursive: true});
  await page.setViewportSize({width: 390, height: 844});
  await page.screenshot({path: '/opt/cursor/artifacts/batch-d-phone.png'});
  assert.ok(!writes.some(u => /stoopids-(bets|requests|chat)-/.test(u)), writes.join(','));
  if (errors.length) throw new Error(errors.join('\n'));
  console.log(JSON.stringify({ok: true, copy: logic.copy, wide}));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
