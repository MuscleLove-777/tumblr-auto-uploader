# -*- coding: utf-8 -*-
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent


class RuntimeContractTests(unittest.TestCase):
    def test_runner_uses_real_python_and_forwards_arguments(self):
        text = (HERE / "run_local_dispatch.cmd").read_text(encoding="utf-8-sig")
        self.assertIn("pythoncore-3.14-64\\python.exe", text)
        self.assertIn("dispatch_local.py %*", text)
        self.assertNotIn("py -3", text)

    def test_runner_forces_utf8(self):
        text = (HERE / "run_local_dispatch.cmd").read_text(encoding="utf-8-sig")
        self.assertIn('set "PYTHONUTF8=1"', text)
        self.assertIn('set "PYTHONIOENCODING=utf-8"', text)

    def test_task_definition_has_three_daily_slots_and_resilience(self):
        text = (HERE / "install_scheduled_task.ps1").read_text(encoding="utf-8-sig")
        for hour in (2, 14, 20):
            self.assertIn(f"-Hour {hour} -Minute 0", text)
        self.assertIn("-AllowStartIfOnBatteries", text)
        self.assertIn("-DontStopIfGoingOnBatteries", text)
        self.assertIn("-WakeToRun", text)
        self.assertIn("-StartWhenAvailable", text)
        self.assertIn("-MultipleInstances IgnoreNew", text)

    def test_task_definition_starts_only_at_future_boundaries(self):
        text = (HERE / "install_scheduled_task.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("if ($FirstRun -le $Now)", text)
        self.assertIn("$FirstRun = $FirstRun.AddDays(1)", text)

    def test_line_notifications_do_not_fake_api_success(self):
        text = (HERE / ".github" / "workflows" / "upload.yml").read_text(
            encoding="utf-8-sig"
        )
        self.assertEqual(text.count("LINE_NOTIFY_SKIPPED credentials_unavailable"), 2)
        self.assertEqual(text.count("curl --fail-with-body --silent --show-error"), 2)
        self.assertNotIn("curl -s -X POST https://api.line.me", text)
        self.assertIn("if: ${{ always() && !(github.event_name", text)


if __name__ == "__main__":
    unittest.main()
