import json, os, tempfile, unittest
from unittest import mock
import ranks as R

TMAP = R.load_team_map()
AP = {"rankings": [{"name": "AP Top 25", "type": "ap", "ranks": [{"current": i + 1, "team": {"id": tid}} for i, tid in enumerate(
    ["57", "150", "356", "41"] + [t for t in TMAP if t not in ("57", "150", "356", "41")][:21])]}]}
NET = {"data": [{"Rank": str(i + 1), "School": t["net_names"][0]} for i, t in enumerate(TMAP.values()) if t["net_names"]]}


def fake_get(url, timeout=25):
    return AP if "espn" in url else NET


class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); R.DELAY = 0

    def test_parse_ap(self):
        r = R.parse_ap(AP); self.assertEqual(len(r), 25); self.assertEqual(r["57"], 1)

    def test_parse_net(self):
        r, miss = R.parse_net(NET, TMAP); self.assertGreaterEqual(len(r), 360); self.assertEqual(miss, [])

    def test_shape_and_stoopid(self):
        with mock.patch.object(R, "_get", fake_get):
            ranks, meta = R.get_ranks(self.d, "2026-11-02")
        self.assertEqual(set(ranks["150"]), {"ap", "net", "kenpom", "stoopid"})
        self.assertEqual([ranks[t]["stoopid"] for t in ("150", "57", "356", "130", "41")], [1, 2, 5, 26, 4])
        self.assertTrue(all(v["kenpom"] is None for v in ranks.values()))
        self.assertEqual(meta["ap"]["status"], "fresh"); self.assertTrue(meta["ap"]["fetched_at"].endswith("Z"))

    def test_no_network_when_cached(self):
        with mock.patch.object(R, "_get", fake_get):
            R.get_ranks(self.d, "2026-11-02")
        with mock.patch.object(R, "_get", side_effect=AssertionError("network")):
            ranks, meta = R.get_ranks(self.d, "2026-11-02")
        self.assertEqual(meta["net"]["status"], "cached"); self.assertEqual(ranks["57"]["ap"], 1)

    def test_keep_last_good_on_failure(self):
        with mock.patch.object(R, "_get", fake_get):
            R.get_ranks(self.d, "2026-11-01")
        with mock.patch.object(R, "_get", side_effect=OSError("down")):
            ranks, meta = R.get_ranks(self.d, "2026-11-02")
        self.assertEqual(meta["ap"]["status"], "stale"); self.assertEqual(ranks["57"]["ap"], 1)
        self.assertFalse(os.path.exists(os.path.join(self.d, "ap-2026-11-02.json")))

    def test_invalid_data_not_swapped(self):
        with mock.patch.object(R, "_get", fake_get):
            R.get_ranks(self.d, "2026-11-01")
        bad = {"rankings": [{"type": "ap", "ranks": [{"current": 99, "team": {"id": "57"}}]}], "data": [{"Rank": "1", "School": "Duke"}]}
        with mock.patch.object(R, "_get", lambda u, timeout=25: bad):
            ranks, meta = R.get_ranks(self.d, "2026-11-02")
        self.assertEqual(meta["ap"]["status"], "stale"); self.assertEqual(meta["net"]["status"], "stale")
        self.assertEqual(ranks["57"]["ap"], 1)


if __name__ == "__main__":
    unittest.main()
