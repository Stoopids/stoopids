// Expires defaults to at tipoff only when a game is attached. Non-GET is aborted.
const {chromium} = require('/tmp/pw/node_modules/playwright-core');
const fs = require('fs');
const assert = require('assert');

(async () => {
  const browser = await chromium.launch({executablePath: '/usr/local/bin/google-chrome', args: ['--no-sandbox', '--disable-dev-shm-usage']});
  const page = await browser.newPage({viewport: {width: 390, height: 844}});
  const writes = [];
  await page.route('**/*', route => {
    const m = route.request().method();
    if (m !== 'GET' && m !== 'HEAD' && m !== 'OPTIONS') { writes.push(m + ' ' + route.request().url()); return route.abort(); }
    return route.continue();
  });
  await page.addInitScript(() => { try { localStorage.setItem('stoopids_who', 'Paul'); } catch (e) {} });
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  await page.goto('http://127.0.0.1:8766/index.html', {waitUntil: 'domcontentloaded', timeout: 60000});
  await page.waitForFunction(() => window.SHARED_UI && D && D.games && typeof RQ !== 'undefined', null, {timeout: 30000});
  const blank = await page.evaluate(() => {
    tab = 'bets27'; OB_VIEW = 'request';
    RQ.S.f = {gid: '', side: '', cov: 'game', odds: [1, 1], amt: null, amtTxt: '', to: [], mode: 'h', n: 3, at: '', est: '', wk: 'unknown', expPick: false};
    RQ.S.msg = ''; render();
    const sel = document.querySelector('#rqForm select[data-rq-in="mode"]');
    return {value: sel.value, text: sel.selectedOptions[0].textContent, hasStart: [...sel.options].some(o => o.value === 'start')};
  });
  assert.equal(blank.value, 'start');
  assert.equal(blank.text, 'Tipoff');
  assert.equal(blank.hasStart, true);
  const withGame = await page.evaluate(() => {
    const g = (D.games || []).find(x => x && x.status === 'scheduled' && x.home && x.away && x.start);
    RQ.prefill(g.id, null, 0);
    render();
    const sel = document.querySelector('#rqForm select[data-rq-in="mode"]');
    const betBefore = JSON.stringify((U.doc && U.doc.bets) || []);
    return {id: String(g.id), value: sel.value, text: sel.selectedOptions[0].textContent, pick: RQ.S.f.expPick, bets: betBefore === JSON.stringify(U.doc.bets)};
  });
  assert.equal(withGame.value, 'start');
  assert.equal(withGame.text, 'Tipoff');
  assert.equal(withGame.pick, false);
  assert.equal(withGame.bets, true);
  const kept = await page.evaluate(() => {
    const sel = document.querySelector('#rqForm select[data-rq-in="mode"]');
    sel.value = 'd';
    sel.dispatchEvent(new Event('change', {bubbles: true}));
    const after = document.querySelector('#rqForm select[data-rq-in="mode"]');
    const gid = RQ.S.f.gid;
    RQ.prefill(gid, null, 0);
    RQ.S.f.mode = 'd';
    RQ.S.f.expPick = true;
    render();
    const held = document.querySelector('#rqForm select[data-rq-in="mode"]');
    return {changed: after.value, held: held.value, pick: RQ.S.f.expPick};
  });
  assert.equal(kept.changed, 'd');
  assert.equal(kept.held, 'd');
  assert.equal(kept.pick, true);
  await page.setViewportSize({width: 1280, height: 900});
  const desk = await page.evaluate(() => {
    RQ.prefill(RQ.S.f.gid, null, 0);
    render();
    const sel = document.querySelector('#rqForm select[data-rq-in="mode"]');
    const when = [...document.querySelectorAll('#rqForm [data-when]')].map(el => el.getAttribute('data-when') + ':' + el.textContent);
    return {value: sel.value, opts: [...sel.options].map(o => o.value), when};
  });
  await page.setViewportSize({width: 390, height: 844});
  const phone = await page.evaluate(() => {
    render();
    const sel = document.querySelector('#rqForm select[data-rq-in="mode"]');
    const when = [...document.querySelectorAll('#rqForm [data-when]')].map(el => el.getAttribute('data-when') + ':' + el.textContent + ':' + getComputedStyle(el).display);
    return {value: sel.value, opts: [...sel.options].map(o => o.value), when};
  });
  assert.equal(phone.value, 'start');
  assert.equal(desk.value, 'start');
  assert.deepEqual(phone.opts, desk.opts);
  assert.ok(phone.opts.includes('start'));
  assert.deepEqual(phone.when.map(x => x.split(':').slice(0, 2).join(':')), desk.when);
  assert.ok(phone.when.every(x => !x.endsWith(':none')));
  await page.evaluate(() => { const el = document.querySelector('#rqForm .rq-exp'); const y = el.getBoundingClientRect().top + window.scrollY - 120; window.scrollTo(0, Math.max(0, y)); });
  fs.mkdirSync('/opt/cursor/artifacts', {recursive: true});
  await page.screenshot({path: '/opt/cursor/artifacts/expires-tipoff-phone.png'});
  assert.ok(!writes.some(u => /stoopids-(bets|requests|chat)-/.test(u)), writes.join(','));
  if (errors.length) throw new Error(errors.join('\n'));
  console.log(JSON.stringify({ok: true, phone: phone.value, desk: desk.value, opts: phone.opts}));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
