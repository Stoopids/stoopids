// Layout contract shared by both leagues. No network, no live data.
const fs=require('fs'),assert=require('assert');
const css=fs.readFileSync('shared/ui.css','utf8');
const html=fs.readFileSync('index.html','utf8');
const js=fs.readFileSync('shared/ui.js','utf8');
assert.ok(css.includes('PARITY-LAYOUT'));
assert.ok(css.includes('grid-template-columns:repeat(auto-fit,minmax(96px,1fr))'));
assert.ok(css.includes('grid-template-columns:repeat(4,minmax(0,1fr))'));
assert.ok(css.includes('.gf2.gfpills'));
assert.ok(html.includes('gf2 gfpills'));
assert.ok(html.includes('shared/ui.css?v=1.27.0'));
assert.ok(js.includes("MQ='(max-width:700px)'"));
assert.equal(fs.readFileSync('shared/VERSION','utf8').trim(),'1.8.8');
console.log('test_parity_layout: ok');
