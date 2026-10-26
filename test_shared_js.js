// Node helper for test_shared.py (no dependencies): runs the SHARED-BETS-CORE block of index.html (the JS port of the
// bets.py tally/merge logic) on the cases piped in as JSON and prints the results as JSON.
//   input : [{"base": <bets.package() output>, "shared": [bets...], "ops": [{"add": bet}|{"settle": {"key":..,"patch":{..}}}, ...]}]
//   output: [{"doc": {"bets": [...]}, "derived": <derivePackage result>}]
const fs = require('fs'), path = require('path');
const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
const m = html.match(/\/\*<SHARED-BETS-CORE>\*\/([\s\S]*?)\/\*<\/SHARED-BETS-CORE>\*\//);
if (!m) { console.error('core block not found in index.html'); process.exit(2); }
const C = new Function(m[1] + '; return {derivePackage,mergeLedger,buildEntries,tallyJS,parseAmount,validateBetJS,addMutator,settleMutator,betKey,round2};')();
const cases = JSON.parse(fs.readFileSync(0, 'utf8'));
const out = cases.map(c => {
  let doc = { bets: JSON.parse(JSON.stringify(c.shared || [])) };
  const repo = c.base.bets.filter(b => b.src === 'ledger').map(b => b.spec || {});
  const people = c.base.people;
  let seq = 0;
  for (const op of (c.ops || [])) {
    let nd;
    if (op.add) nd = C.addMutator(doc, repo, op.add, 'id' + (++seq), people, { season: '2026-27', date: '2026-10-26', now: '2026-10-26T00:00:00Z' });
    else {
      const spec = (c.base.bets.find(b => b.src === 'ledger' && (b.spec && b.spec.id ? String(b.spec.id) : 'n' + b.n) === op.settle.key) || {}).spec;
      try { nd = C.settleMutator(doc, op.settle.key, op.settle.patch, spec, people); } catch (e) { nd = doc; }
    }
    if (nd) doc = nd;
  }
  return { doc, derived: C.derivePackage(c.base, doc.bets) };
});
process.stdout.write(JSON.stringify(out));
