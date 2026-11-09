// Batch E layout checks. Non-GET aborted.
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
  await page.goto('http://127.0.0.1:8767/index.html', {waitUntil: 'domcontentloaded', timeout: 60000});
  await page.waitForFunction(() => document.querySelector('nav#nav a') && D && D.owners, null, {timeout: 30000});
  await page.evaluate(() => { const m = document.querySelector('.s26k-bd'); if (m) m.remove(); window.render = function(){}; });
  const before = await page.evaluate(() => document.querySelector('.hero').getBoundingClientRect().height);
  await page.click('.hero');
  const open = await page.evaluate(() => ({h: document.querySelector('.hero').getBoundingClientRect().height, on: document.querySelector('.hero').classList.contains('hero-open')}));
  await page.keyboard.press('Escape');
  const closed = await page.evaluate(() => document.querySelector('.hero').classList.contains('hero-open'));
  assert.equal(open.on, true);
  assert.ok(open.h > before + 40, open.h + ' vs ' + before);
  assert.equal(closed, false);
  await page.evaluate(() => window.scrollTo(0, 500));
  const nav = await page.evaluate(() => {
    const n = document.querySelector('nav#nav').getBoundingClientRect();
    const hero = document.querySelector('.hero').getBoundingClientRect();
    return {navTop: n.top, heroBottom: hero.bottom, pos: getComputedStyle(document.querySelector('nav#nav')).position};
  });
  assert.equal(nav.pos, 'sticky');
  assert.ok(nav.navTop <= 1, JSON.stringify(nav));
  assert.ok(nav.heroBottom < 0, JSON.stringify(nav));
  await page.evaluate(() => { tab = 'teams'; if (typeof render === 'function') {} });
  await page.evaluate(() => { window.render = function(){ const m=document.getElementById('main'); if(!m)return; }; });
  // restore render by reloading the function from the page... call the original by re-executing navigation through the link
  await page.reload({waitUntil: 'domcontentloaded'});
  await page.waitForFunction(() => document.querySelector('nav#nav a[data-tab="teams"]'));
  await page.evaluate(() => { const m = document.querySelector('.s26k-bd'); if (m) m.remove(); });
  await page.click('nav#nav a[data-tab="teams"]');
  await page.waitForSelector('.tapf button');
  const teams = await page.evaluate(() => {
    const btns = [...document.querySelectorAll('.tapf button')];
    const cs = getComputedStyle(document.querySelector('.tapf'));
    const b0 = getComputedStyle(btns[0]);
    const td = document.querySelector('.card.tap.s27-rk td:first-child');
    const pad = getComputedStyle(document.body).paddingBottom;
    return {n: btns.length, labels: btns.map(b => b.textContent), cols: cs.gridTemplateColumns, wrap: b0.whiteSpace, sticky: td ? getComputedStyle(td).position : '', pad};
  });
  assert.equal(teams.labels[0], 'All');
  assert.equal(teams.n, 9);
  assert.equal(teams.cols.split(' ').filter(Boolean).length, 4, teams.cols);
  assert.equal(teams.wrap, 'normal');
  assert.equal(teams.sticky, 'sticky');
  assert.ok(parseFloat(teams.pad) <= 70, teams.pad);
  fs.mkdirSync('/opt/cursor/artifacts', {recursive: true});
  await page.evaluate(() => { const el = document.querySelector('.tapf'); if (el) el.scrollIntoView({block:'start'}); });
  await page.screenshot({path: '/opt/cursor/artifacts/batch-e-phone.png'});
  assert.ok(!writes.some(u => /stoopids-(bets|requests|chat)-/.test(u)));
  if (errors.length) throw new Error(errors.join('\n'));
  console.log(JSON.stringify({ok: true, labels: teams.labels, pad: teams.pad, nav}));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
