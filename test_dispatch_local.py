# -*- coding: utf-8 -*-
import unittest
from datetime import datetime, timezone

import dispatch_local


class LocalDispatcherTests(unittest.TestCase):
    def test_unposted_entries_are_exhausted_before_any_repeat(self):
        entries = [
            {"path": "a.mp4", "sha256": "a" * 64},
            {"path": "b.mp4", "sha256": "b" * 64},
            {"path": "c.mp4", "sha256": "c" * 64},
        ]
        state = {"attempts": [{"sha256": "a" * 64, "status": "success"}]}
        for _ in range(20):
            chosen = dispatch_local.select_entry(entries, state, set())
            self.assertIn(chosen["sha256"], {"b" * 64, "c" * 64})

    def test_remote_posted_filename_is_not_selected(self):
        entries = [
            {"path": "already.mp4", "sha256": "a" * 64},
            {"path": "fresh.mp4", "sha256": "b" * 64},
        ]
        chosen = dispatch_local.select_entry(entries, {"attempts": []}, {"already.mp4"})
        self.assertEqual("fresh.mp4", chosen["path"])

    def test_failed_items_do_not_block_unattempted_items(self):
        entries = [
            {"path": "failed.mp4", "sha256": "a" * 64},
            {"path": "new.mp4", "sha256": "b" * 64},
        ]
        state = {"attempts": [{"sha256": "a" * 64, "status": "failed"}]}
        chosen = dispatch_local.select_entry(entries, state, set())
        self.assertEqual("new.mp4", chosen["path"])

    def test_reuse_waits_for_cooldown_and_chooses_oldest(self):
        entries = [
            {"path": "old.mp4", "sha256": "a" * 64},
            {"path": "recent.mp4", "sha256": "b" * 64},
        ]
        state = {"attempts": [
            {"sha256": "a" * 64, "status": "success", "at_jst": "2026-08-01 00:00:00 JST"},
            {"sha256": "b" * 64, "status": "success", "at_jst": "2026-08-20 00:00:00 JST"},
        ]}
        now = datetime(2026, 9, 1, tzinfo=timezone.utc).astimezone(dispatch_local.JST)
        chosen = dispatch_local.select_entry(entries, state, set(), min_repost_days=14, now=now)
        self.assertEqual("old.mp4", chosen["path"])


if __name__ == "__main__":
    unittest.main()
