import datetime as dt, json, os, shutil, tempfile, unittest
import ranks_live as L

TM = {str(i): {"school": "School %d" % i, "net_names": ["School %d" % i]} for i in range(1, 366)}
NOW = dt.datetime(2026, 11, 2, 15, 0, tzinfo=dt.timezone.utc)


def prov(ap=25, net=365, stoopid=None, boom=False):
    def p(cache, day):
        if boom:
            raise RuntimeError("network down")
        r = {t: {"ap": int(t) if int(t) <= ap else None, "net": int(t) if int(t) <= net else None, "kenpom": None,
                 "stoopid": (stoopid or {}).get(t)} for t in TM}
        return r, {s: {"status": "fresh"} for s in ("ap", "net", "stoopid")}
    return p


class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); os.makedirs(os.path.join(self.d, "data"))
        self.kp = os.path.join(self.d, "kp.json")
        json.dump([{"rank": i, "team": "School %d" % (366 - i)} for i in range(1, 366)], open(self.kp, "w"))
        self._k = L.KENPOM_SNAPSHOT; L.KENPOM_SNAPSHOT = self.kp

    def tearDown(self):
        L.KENPOM_SNAPSHOT = self._k; shutil.rmtree(self.d)

    def run1(self, p, prev=None, now=NOW):
        out = {"meta": {}}
        orig = L.kenpom_snapshot
        L.apply(out, prev, out_dir=self.d, cache_dir=self.d, now=now, provider=p, team_map=TM)
        return out

    def test_writes_shape(self):
        o = self.run1(prov(stoopid={"7": 3}))
        t = o["ranks"]["teams"]["7"]
        self.assertEqual((t["ap"], t["net"], t["stoopid"], t["stoopid_current"]), (7, 7, 3, 3))
        self.assertEqual(t["kenpom"], 359)
        self.assertIn("sources", o["ranks"]); self.assertTrue(o["meta"]["ranks_fetch"]["called"])
        self.assertNotIn("stoopid_blend", t)

    def test_once_per_et_day(self):
        o = self.run1(prov())
        o2 = self.run1(prov(boom=True), prev=o, now=NOW + dt.timedelta(hours=2))
        self.assertFalse(o2["meta"]["ranks_fetch"]["called"])
        self.assertEqual(o2["ranks"], o["ranks"])

    def test_next_et_day_fetches(self):
        o = self.run1(prov())
        o2 = self.run1(prov(), prev=o, now=NOW + dt.timedelta(days=1))
        self.assertTrue(o2["meta"]["ranks_fetch"]["called"])

    def test_retry_after_3h(self):
        o = self.run1(prov(boom=True))
        self.assertEqual(o["meta"]["ranks_fetch"]["state"]["status"], "fail")
        self.assertFalse(L.should_fetch(o["meta"]["ranks_fetch"]["state"], NOW + dt.timedelta(hours=2))[0])
        self.assertTrue(L.should_fetch(o["meta"]["ranks_fetch"]["state"], NOW + dt.timedelta(hours=3, minutes=1))[0])

    def test_short_ap_keeps_previous(self):
        o = self.run1(prov())
        o2 = self.run1(prov(ap=10), prev=o, now=NOW + dt.timedelta(days=1))
        self.assertEqual(o2["ranks"]["teams"]["20"]["ap"], 20)
        self.assertEqual(o2["ranks"]["sources"]["ap"]["used"], "kept")

    def test_short_net_keeps_previous_and_no_net_write(self):
        o = self.run1(prov())
        p = os.path.join(self.d, "data", "net.json"); m = os.path.getmtime(p)
        o2 = self.run1(prov(net=100), prev=o, now=NOW + dt.timedelta(days=1))
        self.assertEqual(o2["ranks"]["teams"]["300"]["net"], 300)
        self.assertEqual(os.path.getmtime(p), m)

    def test_net_json_only_when_changed(self):
        o = self.run1(prov())
        self.assertTrue(o["meta"]["ranks_fetch"]["net_json_written"])
        o2 = self.run1(prov(), prev=o, now=NOW + dt.timedelta(days=1))
        self.assertFalse(o2["meta"]["ranks_fetch"]["net_json_written"])
        o3 = self.run1(prov(net=364), prev=o2, now=NOW + dt.timedelta(days=2))
        self.assertTrue(o3["meta"]["ranks_fetch"]["net_json_written"])

    def test_kenpom_never_blanked(self):
        o = self.run1(prov())
        json.dump([], open(self.kp, "w"))
        o2 = self.run1(prov(), prev=o, now=NOW + dt.timedelta(days=1))
        self.assertEqual(o2["ranks"]["teams"]["7"]["kenpom"], 359)

    def test_stoopid_hand_set_kept(self):
        o = self.run1(prov(stoopid={"7": 3}))
        o2 = self.run1(prov(stoopid={}), prev=o, now=NOW + dt.timedelta(days=1))
        self.assertEqual(o2["ranks"]["teams"]["7"]["stoopid"], 3)
        self.assertEqual(L.STOOPID_SOURCE, "current")

    def test_provider_crash_keeps_previous_data(self):
        o = self.run1(prov())
        o2 = self.run1(prov(boom=True), prev=o, now=NOW + dt.timedelta(days=1))
        self.assertEqual(o2["ranks"], o["ranks"]); self.assertIn("error", o2["meta"]["ranks_fetch"])

    def test_real_snapshot_maps(self):
        L.KENPOM_SNAPSHOT = self._k
        tm = json.load(open(os.path.join(L.HERE, "team_map.json")))["teams"]
        kp, miss = L.kenpom_snapshot(tm, self._k)
        self.assertEqual(miss, []); self.assertEqual(len(kp), 365); self.assertEqual(sorted(kp.values())[0], 1)


if __name__ == "__main__":
    unittest.main()
