import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cloud_source
import cloud_watchdog
import cloud_watchdog_retry


class CloudRuntimeTests(unittest.TestCase):
    def test_cloud_selection_prefers_new_then_oldest(self):
        inventory = [SimpleNamespace(path=x) for x in ["recent.mp4", "old.mp4", "new.mp4", "ignored.txt"]]
        posts = [{"post_id": "1", "file": "old.mp4", "posted_at": "2026-01-01"},
                 {"post_id": "2", "file": "recent.mp4", "posted_at": "2026-02-01"}]
        self.assertEqual([x.path for x in cloud_source.candidate_order(inventory, posts)],
                         ["new.mp4", "old.mp4", "recent.mp4"])

    def test_one_download_without_persistent_cookies(self):
        with tempfile.TemporaryDirectory() as directory:
            class Provider:
                def download_folder(self, **kwargs):
                    self.discovery = kwargs
                    return [SimpleNamespace(path="new.mp4", id="public-media")]
                def download(self, **kwargs):
                    self.acquisition = kwargs
                    Path(kwargs["output"]).write_bytes(b"video")
            provider = Provider()
            self.assertEqual(len(cloud_source.download_one(provider, "public-folder", output=directory)), 1)
            self.assertTrue(provider.discovery["skip_download"])
            self.assertFalse(provider.discovery["use_cookies"])
            self.assertFalse(provider.acquisition["use_cookies"])

    def test_no_duplicate_dispatch_while_recent_failed_or_running(self):
        now = datetime.now(timezone.utc)
        for status in ("completed", "in_progress"):
            runs = [{"status": status, "created_at": now.isoformat()}]
            with patch("cloud_watchdog.gh") as api:
                self.assertEqual(cloud_watchdog.recover_own({"state": "active"}, runs,
                                 now - timedelta(days=3), now), [])
                api.assert_not_called()

    def test_disabled_publisher_and_missing_day_recover(self):
        now = datetime.now(timezone.utc)
        with patch("cloud_watchdog.gh") as api:
            repairs = cloud_watchdog.recover_own({"state": "disabled_inactivity"}, [], None, now)
            self.assertEqual(len(repairs), 2)
            self.assertEqual(api.call_count, 2)

    def test_cloud_workflow_has_schedule_source_and_serialization(self):
        text = Path(".github/workflows/upload.yml").read_text(encoding="utf-8")
        self.assertIn("cron: '0 5,11,17 * * *'", text)
        self.assertEqual(text.count("GDRIVE_FOLDER_ID: ${{ secrets.GDRIVE_FOLDER_ID }}"), 3)
        self.assertIn("group: tumblr-publisher", text)
        self.assertNotIn("Require local source", text)
        self.assertEqual(text, Path("cloud_publisher.yml").read_text(encoding="utf-8"))

    def test_watchdog_runs_separately_and_backup_has_no_publisher_trigger(self):
        primary = Path(".github/workflows/uploader-watchdog.yml").read_text(encoding="utf-8")
        backup = Path(".github/workflows/uploader-watchdog-retry.yml").read_text(encoding="utf-8")
        self.assertIn("group: tumblr-watchdog\n  queue: max", primary)
        self.assertIn("runs-on: ubuntu-24.04", primary)
        self.assertIn("workflow_run:", backup)
        self.assertIn("runs-on: ubuntu-22.04", backup)
        self.assertNotIn("upload.yml/dispatches", backup)
        self.assertEqual(cloud_watchdog.REPOS, ["tumblr-auto-uploader"])

    def test_backup_gate_only_accepts_runner_acquisition_failure(self):
        run = {"path": cloud_watchdog_retry.PRIMARY,
               "event": "schedule", "conclusion": "failure"}
        no_runner = [{"name": "audit", "conclusion": "cancelled",
                      "runner_id": 0, "steps": []}]
        self.assertTrue(cloud_watchdog_retry.should_retry(run, no_runner))
        self.assertFalse(cloud_watchdog_retry.should_retry(
            run, [{**no_runner[0], "steps": [{"name": "Audit"}]}]))
        self.assertFalse(cloud_watchdog_retry.should_retry(
            run, [{**no_runner[0], "runner_id": 123}]))
        self.assertFalse(cloud_watchdog_retry.should_retry(
            {**run, "path": ".github/workflows/upload.yml"}, no_runner))


if __name__ == "__main__":
    unittest.main()
