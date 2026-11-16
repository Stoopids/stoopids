"""Offline checks: a failed source keeps its ranks, and a last-season NET list is not applied."""
import unittest

import ranks_refresh as R


def base():
    return {"meta": {"ranks_fetch": {"kenpom_snapshot": "2026-11-02"}},
            "ranks": {"teams": {"57": {"ap": 1, "net": 4, "kenpom": 2, "stoopid": None},
                                 "150": {"ap": 2, "net": 2, "kenpom": 1, "stoopid": 1}},
                      "sources": {"ap": {}, "net": {}, "kenpom": {"as_of": "2026-11-02"}}}}


class RefreshTests(unittest.TestCase):
    def test_failed_ap_keeps_ranks(self):
        data = base()
        out = R.apply_ap(data, {"ok": False, "error": "down"})
        self.assertEqual(out["status"], "kept")
        self.assertEqual(data["ranks"]["teams"]["57"]["ap"], 1)

    def test_ap_poll_date_and_rank_change(self):
        data = base()
        out = R.apply_ap(data, {"ok": True, "poll_date": "2026-11-16", "fetched_at": "2026-11-16T14:00:00Z",
                                "ranks": {"57": 3, "150": 1}})
        self.assertEqual(out["status"], "updated")
        self.assertEqual(data["ranks"]["teams"]["57"]["ap"], 3)
        self.assertEqual(data["ranks"]["teams"]["150"]["ap"], 1)
        self.assertEqual(data["ranks"]["sources"]["ap"]["poll_date"], "2026-11-16")

    def test_same_ap_poll_does_not_mark_a_change(self):
        data = base()
        data["ranks"]["sources"]["ap"]["poll_date"] = "2026-11-09"
        out = R.apply_ap(data, {"ok": True, "poll_date": "2026-11-09", "fetched_at": "2026-11-16T14:00:00Z",
                                "ranks": {"57": 1, "150": 2}})
        self.assertEqual(out["status"], "unchanged")
        self.assertNotIn("fetched_at", data["ranks"]["sources"]["ap"])

    def test_last_season_net_is_kept(self):
        data = base()
        out = R.apply_net(data, {"ok": True, "last_season": True, "updated": "Through Games Apr. 06 2026",
                                 "ranks": {"57": 1}}, "/tmp/does-not-write-net.json")
        self.assertEqual(out["status"], "kept")
        self.assertEqual(data["ranks"]["teams"]["57"]["net"], 4)

    def test_kenpom_date_drops_the_weekday(self):
        html = ('Data through games of <a href="fanmatch.php?d=2026-11-15">Sunday, November 15</a>'
                '<td class="hard_left">1</td><td class="next_left"><a href="team.php?team=Florida">Florida</a></td>')
        as_of, rows = R.parse_kenpom_html(html)
        self.assertEqual(as_of, "2026-11-15")
        self.assertEqual(rows, [{"rank": 1, "team": "Florida"}])

    def test_kenpom_failure_keeps_snapshot(self):
        data = base()
        out = R.apply_kenpom(data, {"ok": False, "error": "HTTP 403"})
        self.assertEqual(out["status"], "kept")
        self.assertEqual(data["ranks"]["teams"]["150"]["kenpom"], 1)
        self.assertEqual(out["as_of"], "2026-11-02")


if __name__ == "__main__":
    unittest.main()
