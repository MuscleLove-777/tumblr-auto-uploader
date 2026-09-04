# -*- coding: utf-8 -*-
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pool_loader


class PoolLoaderContractTests(unittest.TestCase):
    def _write_pool(self, root: Path, x_action: str) -> Path:
        path = root / "content_pool.json"
        path.write_text(
            json.dumps(
                {
                    "version": "test",
                    "lanes": {
                        "mature_muscle": {
                            "cta_lines": [
                                "未公開版はこちら → https://www.patreon.com/example",
                                "Xも更新中 → https://x.com/example",
                            ]
                        }
                    },
                    "platform_focus": {
                        "tumblr": {"action": "amplify"},
                        "x": {"action": x_action},
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return path

    def test_held_channel_cta_is_removed_and_revenue_cta_keeps_utm(self):
        with tempfile.TemporaryDirectory() as tmp:
            pool_path = self._write_pool(Path(tmp), "hold")
            with patch.object(pool_loader, "LOCAL_POOL", pool_path):
                insights = pool_loader.as_insights("mature_muscle", platform="tumblr")

        ctas = insights["recommended_ctas"]
        self.assertEqual(1, len(ctas))
        self.assertIn("patreon.com", ctas[0].lower())
        self.assertIn("utm_source=tumblr", ctas[0])
        self.assertFalse(any("x.com" in cta.lower() for cta in ctas))

    def test_active_channel_cta_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            pool_path = self._write_pool(Path(tmp), "amplify")
            with patch.object(pool_loader, "LOCAL_POOL", pool_path):
                insights = pool_loader.as_insights("mature_muscle", platform="tumblr")

        self.assertTrue(any("x.com" in cta.lower() for cta in insights["recommended_ctas"]))


if __name__ == "__main__":
    unittest.main()
