// Batch B bets page structure. Non-GET aborted. Fixture bets stay in the page only.
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
  await page.addInitScript(() => { try { localStorage.setItem('stoopids_who', 'Paul'); localStorage.setItem('stoopids_b27_status', 'open'); } catch (e) {} });
  await page.goto('http://127.0.0.1:8769/index.html', {waitUntil: 'domcontentloaded', timeout: 60000});
  await page.waitForFunction(() => window.SHARED_UI && D && D.owners && U && U.doc, null, {timeout: 30000});
  const info = await page.evaluate(() => {
    const base = {backer: 'Paul', other: 'Murf', amt: 5, odds: {a: 1, b: 1}, kind: 'bet', rd: {k: 'manual'}};
    const rows = [
      Object.assign({id: 'a', n: 1, status: 'open', text: 'Past date bet', wk: 'date', est: '2020-01-02', created_at: '2026-01-01T00:00:00Z'}, base),
      Object.assign({id: 'b', n: 2, status: 'open', text: 'Future date bet', wk: 'date', est: '2027-06-01', created_at: '2026-02-01T00:00:00Z'}, base),
      Object.assign({id: 'c', n: 3, status: 'open', text: 'End game bet', wk: 'game', est: null, created_at: '2026-03-01T00:00:00Z'}, base),
      Object.assign({id: 'd', n: 4, status: 'backer', text: 'Settled fixture', wk: 'date', est: '2026-01-02', created_at: '2026-01-02T00:00:00Z'}, base)
    ];
    const sorted = SHARED_UI.estSort(rows, '2026-11-10').map(b => b.id);
    U.doc.bets = rows;
    U.state = 'ok';
    tab = 'bets27'; OB_VIEW = 'all';
    render();
    window.render = function () {};
    const html = document.getElementById('main').innerHTML;
    const ready = document.querySelector('#b27Ready');
    const card = document.querySelector('#bet-a');
    return {
      sorted,
      readyText: ready ? ready.innerText : '',
      hasFold: html.includes('tally-fold'),
      pending: html.includes('Pending requests'),
      groups: [...document.querySelectorAll('.b27-gh')].map(el => el.textContent),
      status: document.querySelector('#sbStatus option[value="open"]').textContent,
      badge: card.querySelector('.st').textContent,
      details: !!card.querySelector('.b27-more'),
      confirm: card.innerHTML.includes('b27Ask') || card.innerHTML.includes('b27SetStatus'),
      settledOnAll: !!document.getElementById('bet-d'),
      readyClass: card.classList.contains('b27-ready')
    };
  });
  assert.deepEqual(info.sorted, ['a', 'b', 'c', 'd']);
  assert.ok(info.readyText.includes('Ready to settle') && info.readyText.includes('Past date bet'));
  assert.equal(info.readyClass, true);
  assert.equal(info.hasFold, false);
  assert.equal(info.settledOnAll, false);
  assert.ok(info.groups.includes('Set date') && info.groups.includes('End of game'));
  assert.equal(info.status, 'Unsettled bets');
  assert.equal(info.badge, 'Unsettled');
  assert.equal(info.details, true);
  assert.equal(info.confirm, true);
  await page.evaluate(() => { window.render = null; });
  await page.reload({waitUntil: 'domcontentloaded'});
  await page.waitForFunction(() => D && D.owners && U && U.doc);
  await page.evaluate(() => {
    U.doc.bets = [{id: 'd', n: 4, status: 'backer', text: 'Settled fixture', wk: 'date', est: '2026-01-02', created_at: '2026-01-02T00:00:00Z', backer: 'Paul', other: 'Murf', amt: 5, odds: {a: 1, b: 1}, kind: 'bet'}];
    U.state = 'ok'; tab = 'bets27'; OB_VIEW = 'tally'; render(); window.render = function () {};
  });
  const tally = await page.evaluate(() => document.getElementById('main').innerText);
  assert.ok(tally.includes('Settled bets') && tally.includes('Settled fixture'));
  fs.mkdirSync('/opt/cursor/artifacts', {recursive: true});
  await page.screenshot({path: '/opt/cursor/artifacts/batch-b-phone.png', fullPage: true});
  assert.ok(!writes.some(u => /stoopids-(bets|requests|chat)-/.test(u)), writes.join(','));
  if (errors.length) throw new Error(errors.join('\n'));
  console.log(JSON.stringify({ok: true, sorted: info.sorted, groups: info.groups}));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
