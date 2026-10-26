#!/usr/bin/env python3
"""Run: python3 test_bets.py  (no network)"""
import json, os, shutil, tempfile, unittest
import bets as B

HERE = os.path.dirname(os.path.abspath(__file__))
LED = json.load(open(os.path.join(HERE, "bets.json")))
PEOPLE = LED["people"]


class Amounts(unittest.TestCase):
    def test_shorthand(self):
        self.assertEqual(B.parse_amount("100K"), 100000)
        self.assertEqual(B.parse_amount("500k"), 500000)
        self.assertEqual(B.parse_amount("2juta"), 2000000)
        self.assertEqual(B.parse_amount("1.5mil"), 1500000)
        self.assertEqual(B.parse_amount("3 mil"), 3000000)
        self.assertEqual(B.parse_amount("250,000"), 250000)
        self.assertEqual(B.parse_amount("100", default_k=True), 100000)
        self.assertIsNone(B.parse_amount("lots"))

    def test_format(self):
        self.assertEqual(B.fmt_amount(100000, LED["currency"]), "100K")
        self.assertEqual(B.fmt_amount(1250000, LED["currency"]), "1250K")


class Entries(unittest.TestCase):
    def test_flat(self):
        e = B.build_entries({"type": "versus", "side_a": ["mark"], "side_b": ["jake"], "stake": "100K", "winner": "a"})
        self.assertEqual(e, [{"from": "jake", "to": "mark", "amount": 100000}])

    def test_open_and_wash_have_no_entries(self):
        self.assertEqual(B.build_entries({"type": "versus", "side_a": ["mark"], "side_b": ["jake"], "stake": "100K"}), [])
        self.assertEqual(B.build_entries({"type": "versus", "side_a": ["mark"], "side_b": ["jake"], "stake": "100K", "winner": "wash"}), [])

    def test_odds_longshot_paid_at_odds(self):
        base = {"type": "versus", "side_a": ["paul"], "side_b": ["mark"], "stake": "100K", "odds": "2:1", "longshot": "a"}
        self.assertEqual(B.build_entries(dict(base, winner="a")), [{"from": "mark", "to": "paul", "amount": 200000}])   # longshot wins 2x
        self.assertEqual(B.build_entries(dict(base, winner="b")), [{"from": "paul", "to": "mark", "amount": 100000}])   # longshot loses 1x
        self.assertEqual(B.build_entries({"type": "versus", "side_a": ["mark"], "side_b": ["paul"], "stake": "100K", "odds": "20:1", "longshot": "b", "winner": "b"}),
                         [{"from": "mark", "to": "paul", "amount": 2000000}])

    def test_multi_party_each(self):
        e = B.build_entries({"type": "versus", "side_a": ["mark"], "side_b": ["jim", "kurt"], "stake": "100K", "winner": "b"})
        self.assertEqual(sorted((x["from"], x["to"], x["amount"]) for x in e), [("mark", "jim", 100000), ("mark", "kurt", 100000)])

    def test_per_game_series(self):
        e = B.build_entries({"type": "versus", "side_a": ["kurt"], "side_b": ["mark"], "stake": "100K", "games": {"a": 1, "b": 2}})
        self.assertEqual(e, [{"from": "kurt", "to": "mark", "amount": 100000}])
        e = B.build_entries({"type": "versus", "side_a": ["kurt"], "side_b": ["mark"], "stake": "100K", "games": {"a": 0, "b": 3}})
        self.assertEqual(e[0]["amount"], 300000)
        self.assertEqual(B.build_entries({"type": "versus", "side_a": ["kurt"], "side_b": ["mark"], "stake": "100K", "games": {"a": 1, "b": 1}}), [])   # even series = wash

    def test_non_cash(self):
        e = B.build_entries({"type": "versus", "side_a": ["ken"], "side_b": ["jim"], "stake_item": "steak dinner", "winner": "b"})
        self.assertEqual(e, [{"from": "ken", "to": "jim", "item": "steak dinner"}])
        t = B.tally(PEOPLE, [{"n": 1, "_entries": e}])
        self.assertEqual(t["items"][0]["item"], "steak dinner"); self.assertEqual(sum(t["lost"].values()), 0)

    def test_pool_winner_and_runner_up_money_back(self):
        pool = {"type": "pool", "participants": ["jake", "kurt", "mark", "ken"], "buy_in": "200K", "payouts": {"jake": 600000, "kurt": 200000}}
        e = B.build_entries(pool)
        net = {}
        for x in e:
            net[x["to"]] = net.get(x["to"], 0) + x["amount"]; net[x["from"]] = net.get(x["from"], 0) - x["amount"]
        self.assertEqual(net, {"jake": 400000, "mark": -200000, "ken": -200000})     # runner-up got money back: nets 0
        self.assertEqual(B.build_entries({"type": "pool", "participants": ["jake", "kurt"], "buy_in": "200K"}), [])   # open until payouts exist

    def test_tally_zero_sum_and_hide_paid(self):
        bets = [{"n": 1, "_entries": [{"from": "mark", "to": "jake", "amount": 100000}, {"from": "kurt", "to": "jake", "amount": 50000, "paid": True}]}]
        t = B.tally(PEOPLE, bets)
        self.assertAlmostEqual(sum(t["net"].values()), 0)
        self.assertEqual(t["won"]["jake"], 150000); self.assertEqual(t["bets"]["jake"], 1)
        self.assertEqual(B.tally(PEOPLE, bets, hide_paid=True)["won"]["jake"], 100000)


class Parser(unittest.TestCase):
    def p(self, outcome, wager=""):
        return B.parse_outcome(outcome, wager, PEOPLE)

    def test_simple_and_aliases(self):
        r = self.p("Cowboys cover. Jim owes Murph 100K")
        self.assertEqual(r["status"], "settled"); self.assertEqual(r["entries"], [{"from": "jim", "to": "neal", "amount": 100000}])
        self.assertEqual(self.p("Burns owes Schwartz 100k")["entries"], [{"from": "scott", "to": "ken", "amount": 100000}])
        self.assertEqual(self.p("HAHAHA - Paul owes Mark 2juta")["entries"][0]["amount"], 2000000)

    def test_multi_party_each(self):
        r = self.p("JJ live up to the hype, Mark and Scott owe Kurt 100k each.")
        self.assertEqual(sorted((e["from"], e["to"]) for e in r["entries"]), [("mark", "kurt"), ("scott", "kurt")])
        r = self.p("Miami wins by 10. Mark owes Jim and Kurt 100K each")
        self.assertEqual(len(r["entries"]), 2)
        r = self.p("Ken owes Paul 100K, Murf owes Paul 200K, Mark owes Paul 100K")
        self.assertEqual(len(r["entries"]), 3)                            # all three clauses, none silently dropped

    def test_assumptions_are_flagged(self):
        r = self.p("Kurt, Mark,Jake, Ken,Scott owe Murf 200K")
        self.assertEqual(len(r["entries"]), 5); self.assertTrue(r["notes"])
        r = self.p("duke dookies on michigan, ken owes kurt 100", "poo takes michigan over kurt duke 100k")
        self.assertEqual(r["entries"][0]["amount"], 100000); self.assertTrue(r["notes"])

    def test_paid_and_multi_line(self):
        r = self.p("Ken owes Paul 200K (paid)\nMurf owes Jake 200K")
        self.assertTrue(r["entries"][0].get("paid")); self.assertFalse(r["entries"][1].get("paid"))

    def test_wash_open_unparsed(self):
        self.assertEqual(self.p("Wash")["status"], "wash")
        self.assertEqual(self.p("")["status"], "open")
        u = self.p("Arizona with the win. Kujo owes Burns 100k")           # unknown alias: flagged, never guessed
        self.assertEqual(u["status"], "unparsed"); self.assertEqual(u["entries"], []); self.assertIn("Kujo", u["notes"][0])
        self.assertEqual(self.p("Everyone owes Jake 200K")["status"], "unparsed")
        self.assertEqual(self.p("Bears win 31-27. Kurt owes Jim 100K")["status"], "settled")    # score text is not a payment

    def test_item(self):
        r = self.p("Mark owes Jake a t-shirt")
        self.assertEqual(r["entries"][0].get("item"), "t-shirt")

    def test_import_ignores_payment_columns(self):
        rows = [[""] * 17 for _ in range(4)]
        rows[0][0] = "NEW BETS START HERE"
        rows[1][0], rows[1][1], rows[1][9] = "1", "Mark bets Jake 100K", "Jake owes Mark 100K"
        rows[1][15], rows[1][16] = "MARK", "PAYPAL @secret"
        import csv, io
        buf = io.StringIO(); csv.writer(buf).writerows(rows)
        out = B.import_sheet(buf.getvalue(), PEOPLE)
        self.assertEqual(len(out), 1)
        self.assertNotIn("secret", json.dumps(out).lower())


class Ledger(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.p = os.path.join(self.d, "bets.json")
        led = dict(LED); led["bets"] = []; json.dump(led, open(self.p, "w"))

    def tearDown(self):
        shutil.rmtree(self.d)

    def test_add_update_validate(self):
        n = B.add_bet({"type": "versus", "text": "Kurt vs Ken 100K", "side_a": ["kurt"], "side_b": ["ken"], "stake": "100K", "winner": None}, self.p)
        self.assertEqual(n, "1")
        with self.assertRaises(ValueError): B.add_bet({"type": "versus", "text": "x", "side_a": ["nobody"], "side_b": ["ken"], "stake": "1K"}, self.p)
        with self.assertRaises(ValueError): B.add_bet({"type": "versus", "text": "x", "side_a": ["kurt"], "side_b": ["kurt"], "stake": "1K"}, self.p)
        with self.assertRaises(ValueError): B.add_bet({"type": "versus", "text": "x", "side_a": ["kurt"], "side_b": ["ken"], "stake": "lots"}, self.p)
        with self.assertRaises(ValueError): B.add_bet({"type": "versus", "text": "x", "side_a": ["kurt"], "side_b": ["ken"], "stake": "1K", "evil": 1}, self.p)
        B.update_bet("1", {"winner": "a"}, self.p)
        led = json.load(open(self.p))
        self.assertEqual(B.derive(led)[0]["_status"], "settled")
        self.assertEqual(B.derive(led)[0]["_entries"], [{"from": "ken", "to": "kurt", "amount": 100000}])
        with self.assertRaises(ValueError): B.update_bet("1", {"type": "pool"}, self.p)
        with self.assertRaises(ValueError): B.update_bet("999", {"winner": "a"}, self.p)
        with self.assertRaises(ValueError):
            B.add_bet({"type": "pool", "text": "pool", "participants": ["jake", "kurt"], "buy_in": "100K", "payouts": {"jake": "300K"}}, self.p)   # pot 200K != 300K


class Coverage(unittest.TestCase):
    def test_imported_file_if_present(self):
        p = os.path.join(HERE, "bets_imported.json")
        if not os.path.exists(p):
            self.skipTest("no import yet")
        d = json.load(open(p)); c = d["coverage"]
        self.assertEqual(c["total"], len(d["bets"]))
        self.assertEqual(c["settled"] + c["wash"] + c["open"] + c["unparsed"], c["total"])
        self.assertNotIn("paypal", json.dumps(d).lower()); self.assertNotIn("venmo", json.dumps(d).lower())
        t = B.tally(PEOPLE, [dict(b, _entries=b["entries"]) for b in d["bets"] if b["parse"]["status"] == "settled"])
        self.assertAlmostEqual(sum(t["net"].values()), 0, places=3)


if __name__ == "__main__":
    unittest.main(verbosity=1)
