// Write it Up offers End game, same as Request. Non-GET aborted.
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
  await page.addInitScript(() => { try { localStorage.setItem('stoopids_who', 'Paul'); } catch (e) {} });
  await page.goto('http://127.0.0.1:8768/index.html', {waitUntil: 'domcontentloaded', timeout: 60000});
  await page.waitForFunction(() => window.SHARED_UI && D && D.owners, null, {timeout: 30000});
  const phone = await page.evaluate(() => {
    tab = 'bets27'; OB_VIEW = 'form'; U.kind = 'bet'; U.wk = 'unknown'; U.est = ''; render();
    const labels = sel => [...document.querySelectorAll(sel + ' [data-when]')].map(el => el.getAttribute('data-when') + ':' + el.textContent + ':' + getComputedStyle(el).display + ':' + el.getAttribute('aria-pressed'));
    const wiu = labels('.entry-wiu');
    OB_VIEW = 'request'; render();
    const rq = labels('#rqForm');
    OB_VIEW = 'form'; render();
    const before = JSON.stringify(U.doc.bets);
    document.querySelector('.entry-wiu [data-when="game"]').click();
    const pack = SHARED_UI.whenPack(U.wk, U.est, '');
    return {wiu, rq, wk: U.wk, pack, betsSame: before === JSON.stringify(U.doc.bets), pressed: document.querySelector('.entry-wiu [data-when="game"]').getAttribute('aria-pressed')};
  });
  assert.deepEqual(phone.wiu.map(x => x.split(':').slice(0, 2).join(':')), phone.rq.map(x => x.split(':').slice(0, 2).join(':')));
  assert.ok(phone.wiu.some(x => x.startsWith('game:End game:') && !x.includes(':none')));
  assert.ok(phone.wiu.some(x => x.startsWith('unknown:Not sure yet') && x.endsWith(':true')));
  assert.equal(phone.wk, 'game');
  assert.deepEqual(phone.pack, {wk: 'game', est: null, sid: null});
  assert.equal(phone.pressed, 'true');
  assert.equal(phone.betsSame, true);
  await page.setViewportSize({width: 1280, height: 900});
  const desk = await page.evaluate(() => {
    render();
    const el = document.querySelector('.entry-wiu [data-when="game"]');
    return {text: el.textContent, display: getComputedStyle(el).display, pressed: el.getAttribute('aria-pressed')};
  });
  assert.equal(desk.text, 'End game');
  assert.notEqual(desk.display, 'none');
  assert.equal(desk.pressed, 'true');
  await page.setViewportSize({width: 390, height: 844});
  await page.evaluate(() => {
    const s = document.createElement('style'); s.textContent = '#chat,.chat{display:none!important}'; document.head.appendChild(s);
    const el = document.querySelector('.entry-wiu .b27-when');
    const y = el.getBoundingClientRect().top + window.scrollY - 80;
    window.scrollTo(0, Math.max(0, y));
    window.render = function(){};
  });
  fs.mkdirSync('/opt/cursor/artifacts', {recursive: true});
  await page.screenshot({path: '/opt/cursor/artifacts/wiu-end-game-phone.png'});
  assert.ok(!writes.some(u => /stoopids-(bets|requests|chat)-/.test(u)), writes.join(','));
  if (errors.length) throw new Error(errors.join('\n'));
  console.log(JSON.stringify({ok: true, wiu: phone.wiu, pack: phone.pack}));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
