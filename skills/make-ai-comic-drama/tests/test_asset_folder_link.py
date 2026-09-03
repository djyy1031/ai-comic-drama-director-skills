from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "link_asset_folder.py"
SPEC = importlib.util.spec_from_file_location("asset_folder_link", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class AssetFolderLinkTests(unittest.TestCase):
    def test_matches_named_assets_without_marking_ready(self):
        assets = [
            {"asset_id": "A1", "canonical_name": "林舟", "asset_type": "CHARACTER", "status": "PENDING"},
            {"asset_id": "A2", "canonical_name": "综合训练教室", "asset_type": "SCENE", "status": "PENDING"},
        ]
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "林舟_角色设定.png").write_bytes(b"image")
            (folder / "未识别图片.png").write_bytes(b"image")
            files = MODULE.scan_files(folder)
            queue, unmatched = MODULE.match_assets(assets, files)
            self.assertEqual(queue[0]["match_status"], "已匹配")
            self.assertEqual(queue[0]["content_review_status"], "待逐项审核")
            self.assertFalse(queue[0]["may_mark_ready"])
            self.assertEqual(queue[1]["match_status"], "缺失")
            self.assertEqual(len(unmatched), 1)

    def test_multiple_candidates_require_review(self):
        assets = [{"asset_id": "A1", "canonical_name": "林舟", "asset_type": "CHARACTER"}]
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "林舟_正面.png").write_bytes(b"image")
            (folder / "林舟_侧面.png").write_bytes(b"image")
            queue, _ = MODULE.match_assets(assets, MODULE.scan_files(folder))
            self.assertEqual(queue[0]["match_status"], "多候选")
            self.assertFalse(queue[0]["may_mark_ready"])


if __name__ == "__main__":
    unittest.main()
