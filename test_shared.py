#!/usr/bin/env python3
"""Run: python3 test_shared.py   (no network)
Checks that the JS port of the tally/merge logic inside index.html (run with node) gives results identical to the Python
reference (bets.package + bets.merge_shared) on the current data, on hand-written shared bets, on JS-built add/settle
operations and on randomised ledgers. Also tests the Python-side merge, validation and the backup snapshot (fail soft)."""
import json, os, random, shutil, subprocess, tempfile, unittest
import bets as B

HERE = os.path.dirname(os.path.abspath(__file__))
def _read(p):
    with open(p) as f:
        return f.read()


def _load(p):
    return json.loads(_read(p))


LED = _load(os.path.join(HERE, "bets.json"))
IMP = _load(os.path.join(HERE, "bets_imported.json"))
PEOPLE = LED["people"]
IDS = [p["id"] for p in PEOPLE]
HAVE_NODE = shutil.which("node") is not None


def run_js(cases):
    r = subprocess.run(["node", os.path.join(HERE, "test_shared_js.js")], input=json.dumps(cases), capture_output=True, text=True, timeout=120)
    if r.returncode:
        raise RuntimeError(r.stderr)
    return json.loads(r.stdout)


def py_expected(led, doc):
    return B.package(B.merge_shared(led, doc), IMP)


def vs(n, a, b, **kw):
    d = {"type": "versus", "id": "s" + n, "n": n, "text": "t" + n, "side_a": a, "side_b": b, "stake": "100K"}
    d.update(kw)
    return d


SHARED = [
    vs("1", ["mark"], ["jake"], winner="a"),
    vs("2", ["paul"], ["mark"], odds="2:1", longshot="a", winner="a"),
    vs("3", ["kurt"], ["mark", "ken"], games={"a": 1, "b": 3}),
    vs("4", ["ken"], ["jim"], stake=None, stake_item="steak dinner", winner="b"),
    vs("5", ["scott"], ["neal"], winner="wash"),
    vs("6", ["mark"], ["kurt"]),                                              # open
    {"type": "pool", "id": "s7", "n": "7", "text": "nhl pool", "participants": ["jake", "kurt", "mark", "ken", "neal", "scott"], "buy_in": "200K",
     "payouts": {"jake": "1mil", "scott": "200K"}},
    {"type": "pool", "id": "s8", "n": "8", "text": "open pool", "participants": ["jake", "kurt", "mark"], "buy_in": "100K"},
    vs("9", ["mark"], ["jake"], winner="b", stake="1.5mil", odds="3:2", longshot="b"),
    # invalid ones that must be ignored by both implementations
    {"type": "versus", "id": "bad1", "n": "10", "text": "x", "side_a": ["nobody"], "side_b": ["mark"], "stake": "100K"},
    {"type": "versus", "id": "bad2", "n": "11", "text": "x", "side_a": ["mark"], "side_b": ["jake"], "stake": "100K", "payment_account": "123"},
    {"type": "dice", "id": "bad3", "n": "12", "text": "x"},
    vs("13", ["mark"], ["mark"], winner="a"),
    {"type": "pool", "id": "bad4", "n": "14", "text": "x", "participants": ["mark", "jake"], "buy_in": "100K", "payouts": {"mark": "5mil"}},
    {"type": "versus", "id": "bad5", "n": "15", "text": "x" * 501, "side_a": ["mark"], "side_b": ["jake"], "stake": "100K"},
]


class JsMatchesPython(unittest.TestCase):
    @unittest.skipUnless(HAVE_NODE, "node not installed")
    def test_current_data_and_shared_fixture(self):
        base = B.package(LED, IMP)
        cases = [{"base": base, "shared": []}, {"base": base, "shared": SHARED}]
        dj = os.path.join(HERE, "data.json")
        if os.path.exists(dj):                       # the real built package (what the browser actually receives)
            cases.append({"base": _load(dj)["bets"], "shared": SHARED})
        for c, r in zip(cases, run_js(cases)):
            self.assertEqual(r["derived"], py_expected(LED, {"bets": c["shared"]}) if c["base"] is base else B.package(B.merge_shared(LED, {"bets": c["shared"]}), IMP))

    @unittest.skipUnless(HAVE_NODE, "node not installed")
    def test_shared_overrides_repo_bet_and_dedupes(self):
        led = json.loads(json.dumps(LED))
        led["bets"] = [vs("1", ["mark"], ["jake"]), vs("2", ["paul"], ["kurt"], winner="a")]
        for b in led["bets"]:
            b.pop("id")                                   # repo bets have no shared id -> keyed by number ("n1")
        base = B.package(led, IMP)
        shared = [dict(vs("1", ["mark"], ["jake"], winner="a"), id="n1"),    # same key as repo bet n1 -> replaces it
                  vs("3", ["ken"], ["jim"], winner="b")]
        r = run_js([{"base": base, "shared": shared}])[0]["derived"]
        self.assertEqual(r, B.package(B.merge_shared(led, {"bets": shared}), IMP))
        self.assertEqual([b["n"] for b in r["bets"] if b["src"] == "ledger"], ["1", "2", "3"])
        self.assertEqual(r["tallies"]["ledger"]["all"]["matrix"]["jake"]["mark"], 100000)

    @unittest.skipUnless(HAVE_NODE, "node not installed")
    def test_js_add_and_settle_operations(self):
        base = B.package(LED, IMP)
        ops = [{"add": {"type": "versus", "text": "Duke vs UNC", "side_a": ["mark"], "side_b": ["jake"], "stake": "100K", "winner": None}},
               {"add": {"type": "pool", "text": "pool", "participants": ["mark", "jake", "kurt"], "buy_in": "100K"}},
               {"add": {"type": "versus", "text": "series", "side_a": ["kurt"], "side_b": ["ken"], "stake": "50K"}},
               {"settle": {"key": "id1", "patch": {"winner": "a"}}},
               {"settle": {"key": "id1", "patch": {"winner": "b"}}},          # already settled -> ignored (first writer wins)
               {"settle": {"key": "id2", "patch": {"payouts": {"mark": "250K", "jake": "50K", "kurt": "0"}}}},
               {"settle": {"key": "id3", "patch": {"games": {"a": 2, "b": 5}}}},
               {"add": {"type": "versus", "text": "bad", "side_a": ["zzz"], "side_b": ["jake"], "stake": "1K"}}]
        try:
            r = run_js([{"base": base, "shared": [], "ops": ops}])[0]
        except RuntimeError as ex:
            self.assertIn("unknown person", str(ex))      # the last op must be rejected (throws)
            ops = ops[:-1]
            r = run_js([{"base": base, "shared": [], "ops": ops}])[0]
        doc = r["doc"]
        self.assertEqual([b["n"] for b in doc["bets"]], ["1", "2", "3"])
        self.assertEqual(r["derived"], B.package(B.merge_shared(LED, doc), IMP))      # Python agrees with the JS-written document
        t = r["derived"]["tallies"]["ledger"]["all"]
        self.assertEqual(t["matrix"]["jake"]["mark"], 150000)    # 100K versus win + 50K from the pool split
        self.assertEqual(t["matrix"]["kurt"]["mark"], 100000)    # pool: kurt put in 100K, got 0
        self.assertEqual(t["matrix"]["kurt"]["ken"], 150000)     # series: ken won 5 games to 2 -> 3 x 50K
        self.assertEqual(t["net"]["mark"], 250000)

    @unittest.skipUnless(HAVE_NODE, "node not installed")
    def test_fuzz(self):
        rnd = random.Random(7)
        amts = ["100K", "50K", "250,000", "1.5mil", "2juta", "33K", "0.7mil", 125000, "12.5K"]
        base = B.package(LED, IMP)
        shared = []
        for i in range(300):
            if rnd.random() < 0.6:
                a, b = rnd.sample(IDS, 2)
                a = [a] + ([x for x in rnd.sample(IDS, 1) if x not in (a, b)] if rnd.random() < .3 else [])
                bet = {"type": "versus", "id": "f%d" % i, "n": str(i + 1), "text": "fuzz", "side_a": a, "side_b": [b],
                       "winner": rnd.choice([None, "a", "b", "wash"])}
                if rnd.random() < .85:
                    bet["stake"] = rnd.choice(amts)
                else:
                    bet["stake_item"] = "beer"
                if rnd.random() < .3:
                    bet["odds"] = rnd.choice(["2:1", "3.5:1", "7:3", "1:4", "2:0", "5-2", "1.25:1"]); bet["longshot"] = rnd.choice("ab")
                if rnd.random() < .2:
                    bet["games"] = {"a": rnd.randint(0, 4), "b": rnd.randint(0, 4)}
            else:
                k = rnd.randint(2, 6)
                parts = rnd.sample(IDS, k)
                bi = rnd.choice([100000, 250000, 333333, 200000])
                pot = bi * k
                cuts = sorted(rnd.randint(0, pot) for _ in range(k - 1))
                pay = [b2 - a2 for a2, b2 in zip([0] + cuts, cuts + [pot])]
                bet = {"type": "pool", "id": "f%d" % i, "n": str(i + 1), "text": "pool", "participants": parts, "buy_in": bi}
                if rnd.random() < .8:
                    bet["payouts"] = {p: v for p, v in zip(parts, pay) if v}
            shared.append(bet)
        r = run_js([{"base": base, "shared": shared}])[0]["derived"]
        exp = py_expected(LED, {"bets": shared})
        self.assertEqual(r["tallies"], exp["tallies"])
        self.assertEqual(r["bets"], exp["bets"])
        self.assertGreater(sum(1 for b in r["bets"] if b["src"] == "ledger" and b["status"] == "settled"), 50)


class PythonSide(unittest.TestCase):
    def test_merge_skips_invalid_and_keeps_order(self):
        m = B.merge_shared(LED, {"bets": SHARED})
        ids = [b["id"] for b in m["bets"]]
        self.assertEqual(ids, ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9"])
        self.assertEqual(B.merge_shared(LED, None)["bets"], LED["bets"])

    def test_validate_new_rules(self):
        with self.assertRaises(ValueError):
            B.validate_bet(vs("1", ["mark"], ["jake"], text="x" * 501), PEOPLE)
        with self.assertRaises(ValueError):
            B.validate_bet({"type": "pool", "text": "p", "participants": ["mark", "jake"], "buy_in": "100K", "payouts": {"mark": "lots", "jake": "1K"}}, PEOPLE)
        self.assertTrue(B.validate_bet(vs("1", ["mark"], ["jake"], created_at="2026-10-26T00:00:00Z"), PEOPLE))   # id / created_at are allowed fields
        self.assertEqual(B.build_entries(vs("1", ["mark"], ["jake"], odds="2:0", longshot="a", winner="a")), [{"from": "jake", "to": "mark", "amount": 100000}])

    def test_backup_snapshot_and_fail_soft(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "bets_shared_backup.json")
        orig = B.fetch_shared
        try:
            B.fetch_shared = lambda cfg, timeout=20: {"bets": SHARED[:2] + [dict(SHARED[0], payment_account="123456", id="p1")], "junk": 1}
            cfg = {"shared_bets": {"enabled": True, "url": "http://x/y", "kind": "textdb"}}
            self.assertIn("written (3 bets)", B.backup_shared(cfg, p))
            snap = _load(p)
            self.assertEqual([sorted(b) for b in snap["bets"]][2], sorted(set(SHARED[0]) & set(B.ALLOWED["versus"])))   # unknown fields (payment_account) dropped
            self.assertNotIn("payment_account", _read(p))
            self.assertIn("unchanged", B.backup_shared(cfg, p))
            def boom(cfg, timeout=20):
                raise OSError("offline")
            B.fetch_shared = boom
            before = _read(p)
            self.assertIn("unreachable", B.backup_shared(cfg, p))        # fail soft: no exception, file untouched
            self.assertEqual(_read(p), before)
            self.assertIn("not configured", B.backup_shared({}, p))
        finally:
            B.fetch_shared = orig
            shutil.rmtree(d)


if __name__ == "__main__":
    unittest.main(verbosity=1)
