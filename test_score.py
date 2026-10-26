#!/usr/bin/env python3
"""Run: python3 test_score.py   (no network needed)"""
import json, os, glob, collections, unittest, copy
import score as S

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "config.json")))


def side(i, sc, win, seed=None, short=None, d1=True):
    return {"id": str(i), "short": short or "T%s" % i, "name": short or "T%s" % i, "score": sc, "win": win, "seed": seed, "d1": d1}


def game(gid, day, kind, w, l, rnd="", status="final", headline="", conf=None, home_win=True):
    h, a = (w, l) if home_win else (l, w)
    return {"id": str(gid), "day": day, "status": status, "kind": kind, "round": rnd, "headline": headline,
            "neutral": False, "confId": conf, "home": h, "away": a, "src": "espn"}


def run(games, windows, standings=None, lines=None, ov=None, cfg=None, today="2027-04-15"):
    cfg = cfg or copy.deepcopy(CFG)
    teams = {str(i): {"short": "T%s" % i} for i in range(1, 200)}
    res = S.compute(cfg, ov or {}, today, teams, windows, games, standings or {}, lines or {}, resolve=lambda n: None)
    return {o["name"]: o for o in res["owners"]}, res


W = lambda owner_tids: {"Murnane": [{"tid": str(t), "start": None, "end": None} for t in owner_tids], **{o["name"]: [] for o in CFG["owners"] if o["name"] != "Murnane"}}


class T(unittest.TestCase):
    def test_wins_and_records(self):
        g = [game(1, "2026-11-10", "reg", side(1, 80, True), side(50, 70, False)),
             game(2, "2026-11-12", "reg", side(50, 60, True), side(1, 55, False)),
             game(3, "2027-02-01", "conf", side(1, 70, True), side(51, 60, False), headline="X Tournament - Quarterfinal")]
        o, r = run(g, W([1]))
        self.assertEqual(o["Murnane"]["total"], 2)
        self.assertEqual(r["records"]["1"]["w"], 2)
        self.assertEqual(r["records"]["1"]["l"], 1)

    def test_redraft_windows(self):
        g = [game(1, "2027-01-19", "reg", side(1, 80, True), side(50, 70, False)),
             game(2, "2027-01-20", "reg", side(1, 80, True), side(50, 70, False)),
             game(3, "2027-01-21", "reg", side(1, 80, True), side(50, 70, False))]
        win = W([])
        win["Murnane"] = [{"tid": "1", "start": None, "end": "2027-01-20"}]   # dropped on Jan 20
        win["Kurt"] = [{"tid": "1", "start": "2027-01-20", "end": None}]     # added Jan 20
        o, _ = run(g, win)
        self.assertEqual(o["Murnane"]["total"], 1)   # only Jan 19 counts for the old owner
        self.assertEqual(o["Kurt"]["total"], 2)      # Jan 20 + Jan 21 for the new owner

    def test_ncaa_points_and_upset_vegas(self):
        t = lambda i, seed, win: side(i, 70 if win else 60, win, seed)
        g = [game(10, "2027-03-17", "ncaa", t(1, 11, True), t(60, 11, False), "First Four"),
             game(11, "2027-03-19", "ncaa", t(1, 11, True), t(61, 6, False), "1st Round"),     # underdog wins -> upset
             game(12, "2027-03-21", "ncaa", t(1, 11, True), t(62, 3, False), "2nd Round"),     # favorite per line -> no upset even though 11 > 3 seed
             game(13, "2027-03-26", "ncaa", t(63, 2, False), t(1, 11, True), "Sweet 16", home_win=False)]
        g.append(game(14, "2027-03-28", "ncaa", t(1, 11, False), t(64, 1, True), "Elite 8"))  # lost
        # entry via first four win; Final Four appearance not set
        lines = {"11": {"underdog_id": "1", "favorite_id": "61", "details": "T61 -2.5"},
                 "12": {"underdog_id": "62", "favorite_id": "1", "details": "T1 -1.5"},     # the SEED upset is NOT a vegas upset
                 "13": {"underdog_id": None, "favorite_id": None, "details": "PK"}}
        o, r = run(g, W([1]), lines=lines)
        by = o["Murnane"]["by_cat"]
        self.assertEqual(by["playin_win"], 1)
        self.assertEqual(by["ncaa_entry"], 5)
        self.assertEqual(by["ncaa_win"], 6)          # R1, R2, S16 (First Four is not a +2)
        self.assertEqual(by["upset"], 4)             # exactly one vegas upset
        a = {x["id"]: x for x in r["upset_audit"]}
        self.assertTrue(a["11"]["upset"]); self.assertFalse(a["12"]["upset"]); self.assertFalse(a["13"]["upset"])

    def test_upset_seed_fallback_flagged(self):
        t = lambda i, seed, win: side(i, 70 if win else 60, win, seed)
        g = [game(20, "2027-03-19", "ncaa", t(1, 12, True), t(61, 5, False), "1st Round"),
             game(21, "2027-03-21", "ncaa", t(1, 12, True), t(62, 12, False), "2nd Round")]  # equal seeds: never an upset
        o, r = run(g, W([1]), lines={})
        a = {x["id"]: x for x in r["upset_audit"]}
        self.assertTrue(a["20"]["upset"]); self.assertTrue(a["20"]["fallback"])
        self.assertFalse(a["21"]["upset"])
        ups = [i for i in o["Murnane"]["teams"][0]["items"] if i["cat"] == "upset"]
        self.assertEqual(len(ups), 1); self.assertTrue(ups[0].get("fallback"))

    def test_upset_scope_toggle(self):
        g = [game(30, "2026-12-01", "reg", side(1, 80, True), side(2, 70, False))]
        lines = {"30": {"underdog_id": "1", "favorite_id": "2"}}
        o, _ = run(g, W([1]), lines=lines)
        self.assertEqual(o["Murnane"]["by_cat"].get("upset", 0), 0)        # default: NCAA only
        cfg = copy.deepcopy(CFG); cfg["rules"]["upset_games"] = ["ncaa", "reg"]
        o, _ = run(g, W([1]), lines=lines, cfg=cfg)
        self.assertEqual(o["Murnane"]["by_cat"]["upset"], 4)

    def test_final4_champ_missed(self):
        t = lambda i, seed, win: side(i, 70 if win else 60, win, seed)
        g = []
        gid = 100
        for k in range(64):  # 64 distinct teams so the field "locks"
            gid += 1
            g.append(game(gid, "2027-03-19", "ncaa", t(70 + 2 * k, 5, True), t(71 + 2 * k, 12, False), "1st Round"))
        g.append(game(300, "2027-04-04", "ncaa", t(70, 5, True), t(72, 5, False), "Final Four"))
        g.append(game(301, "2027-04-06", "ncaa", t(70, 5, True), t(74, 5, False), "National Championship"))
        o, r = run(g, W([70, 71, 5]))
        by = o["Murnane"]["by_cat"]
        self.assertEqual(by["ncaa_entry"], 10)
        self.assertEqual(by["final4"], 3); self.assertEqual(by["champ"], 4)
        self.assertEqual(by["missed_dance"], -1)   # team 5 never played in the tournament
        self.assertTrue(r["field"]["locked"])

    def test_conf_champs(self):
        st = {"7": {"name": "Big Ten", "teams": [{"tid": "1", "name": "A", "cw": 18, "cl": 2, "seed": 1}, {"tid": "2", "name": "B", "cw": 17, "cl": 3, "seed": 2}]}}
        g = [game(40, "2027-03-11", "conf", side(2, 70, True), side(3, 60, False), "Quarterfinal", conf="7", headline="Big Ten Tournament - Quarterfinal"),
             game(41, "2027-03-15", "conf", side(2, 70, True), side(1, 60, False), "Final", conf="7", headline="Big Ten Tournament - Final")]
        o, _ = run(g, {**W([1]), "Kurt": [{"tid": "2", "start": None, "end": None}]}, standings=st)
        self.assertEqual(o["Murnane"]["by_cat"]["conf_reg"], 4)
        self.assertEqual(o["Kurt"]["by_cat"]["conf_tourn"], 4)
        self.assertNotIn("conf_reg", o["Kurt"]["by_cat"])
        # not awarded before the tournament starts
        o, _ = run([], W([1]), standings=st)
        self.assertEqual(o["Murnane"]["total"], 0)

    def test_overrides(self):
        ov = {"flags": {}, "adjustments": [{"owner": "Murnane", "team": "", "pts": -3, "note": "fine"}]}
        o, _ = run([], W([1]), ov=ov)
        self.assertEqual(o["Murnane"]["total"], -3)

    def test_preseason_zero(self):
        o, r = run([game(1, "2026-11-02", "reg", side(1, None, False), side(2, None, False), status="scheduled")], W([1]), today="2026-10-26")
        self.assertTrue(all(x["total"] == 0 for x in o.values()))
        self.assertFalse(r["field"]["locked"])


class Replay(unittest.TestCase):
    """Replay the real 2025-26 season from cache/sb/2026 and check records against ESPN's own standings."""

    def test_records_match_espn(self):
        sdir = os.path.join(HERE, "cache", "sb", "2026")
        stf = os.path.join(HERE, "cache", "standings_2026.json")
        if not (os.path.isdir(sdir) and os.path.exists(stf)):
            self.skipTest("replay cache not present")
        w, l = collections.Counter(), collections.Counter()
        for f in glob.glob(sdir + "/*.json"):
            for g in json.load(open(f))["games"]:
                if g["status"] == "final":
                    for me in (g["home"], g["away"]):
                        (w if me["win"] else l)[me["id"]] += 1
        st = json.load(open(stf))
        n = bad = 0
        for ch in st["children"]:
            for en in ch["standings"]["entries"]:
                first = {}
                for x in en["stats"]:
                    first.setdefault(x["name"], x)
                n += 1
                tid = str(en["team"]["id"])
                if (w[tid], l[tid]) != (int(first["wins"]["value"]), int(first["losses"]["value"])):
                    bad += 1
        self.assertGreater(n, 300)
        self.assertEqual(bad, 0, "%d of %d team records differ from ESPN" % (bad, n))

    def test_demo_output_sane(self):
        p = os.path.join(HERE, "demo", "data.json")
        if not os.path.exists(p):
            self.skipTest("demo not built")
        d = json.load(open(p))
        self.assertEqual(len(d["owners"]), 8)
        self.assertTrue(all(len(o["teams"]) >= 8 for o in d["owners"]))
        self.assertEqual(d["meta"]["assets"]["missing_logo"], [])


class GamesView(unittest.TestCase):
    def _w(self):
        w = {o["name"]: [] for o in CFG["owners"]}
        w["Murnane"] = [{"tid": "1", "start": None, "end": None}]
        w["Kurt"] = [{"tid": "2", "start": None, "end": None}]
        w["Poo"] = [{"tid": "3", "start": None, "end": None}, {"tid": "4", "start": None, "end": None}]
        return w

    def test_view_lines_h2h_and_upset(self):
        s = lambda i, sc, win: side(i, sc, win)
        g = [dict(game(1, "2026-11-01", "reg", s(1, 70, True), s(2, 60, False)), start="2026-11-01T23:00Z"),   # h2h, final, underdog (1) won
             dict(game(2, "2026-11-03", "reg", s(3, None, False), s(4, None, False), status="scheduled"), start="2026-11-03T01:00Z"),  # civil war, no line
             dict(game(3, "2026-11-03", "reg", s(1, None, False), s(90, None, False), status="scheduled"), start="2026-11-03T02:00Z"),  # line posted
             dict(game(4, "2026-11-03", "reg", s(91, None, False), s(92, None, False), status="scheduled"))]                           # no pool team
        lines = {"1": {"underdog_id": "1", "favorite_id": "2", "spread_home": -3.5, "provider": "DraftKings", "home_ml": 150, "away_ml": -180, "total": 140.5, "line_type": "close"},
                 "3": {"underdog_id": "90", "favorite_id": "1", "spread_home": -6.5, "provider": "DraftKings", "home_ml": -250, "away_ml": 200, "total": 150, "line_type": "current"}}
        cfg = copy.deepcopy(CFG); cfg["rules"]["upset_games"] = ["ncaa", "reg"]
        v = S.build_games_view(cfg, {}, "2026-11-02", g, lines, self._w(), 14, 10)
        by = {x["id"]: x for x in v}
        self.assertEqual(set(by), {"1", "2", "3"})                   # game 4 has no pool team
        self.assertTrue(by["1"]["h2h"]); self.assertEqual(by["1"]["home"]["owners"], ["Murnane"]); self.assertEqual(by["1"]["away"]["owners"], ["Kurt"])
        self.assertTrue(by["1"]["upset"]["is"]); self.assertTrue(by["1"]["upset"]["scored"])
        self.assertEqual(by["1"]["line"]["dog_name"], "T1")
        self.assertTrue(by["2"]["civil"]); self.assertIsNone(by["2"]["line"])   # "line not posted yet"
        self.assertEqual(by["3"]["line"]["sp"], 6.5); self.assertEqual(by["3"]["line"]["fav_name"], "T1")
        self.assertIsNone(by["3"]["upset"])
        # default scope (ncaa only): upset is shown but not scored
        v2 = {x["id"]: x for x in S.build_games_view(CFG, {}, "2026-11-02", g, lines, self._w(), 14, 10)}
        self.assertTrue(v2["1"]["upset"]["is"]); self.assertFalse(v2["1"]["upset"]["scored"])

    def test_view_window(self):
        g = [dict(game(1, "2026-01-01", "reg", side(1, 70, True), side(2, 60, False)), start=None)]
        self.assertEqual(S.build_games_view(CFG, {}, "2026-11-02", g, {}, self._w(), 14, 10), [])


class OddsParsing(unittest.TestCase):
    def test_pick_line_underdog_and_live_excluded(self):
        import refresh as R
        gm = game(9, "2026-11-02", "reg", side(1, None, False), side(2, None, False), status="scheduled")
        gm["home"], gm["away"] = side(1, None, False), side(2, None, False)
        mk = lambda name, hml, aml, spread: {"provider": {"name": name}, "details": "x", "overUnder": 150.5, "spread": spread,
             "homeTeamOdds": {"moneyLine": hml, "underdog": hml > aml}, "awayTeamOdds": {"moneyLine": aml, "underdog": aml > hml}}
        items = [mk("ESPN Bet - Live Odds", 900, -2000, 5.5), mk("DraftKings", -240, 195, -6.5)]
        ln = R.pick_line(gm, items, ["DraftKings"])
        self.assertEqual(ln["provider"], "DraftKings")
        self.assertEqual(ln["underdog_id"], "2"); self.assertEqual(ln["favorite_id"], "1")   # away team is the dog
        self.assertEqual(ln["underdog_side"], "away")
        self.assertIsNone(R.pick_line(gm, [], []))


if __name__ == "__main__":
    unittest.main(verbosity=2)
