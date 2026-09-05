from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "init_project.py"
SPEC = importlib.util.spec_from_file_location("ai_drama_init_project", MODULE_PATH)
assert SPEC and SPEC.loader
INITIALIZER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = INITIALIZER
SPEC.loader.exec_module(INITIALIZER)


class InitProjectTests(unittest.TestCase):
    def test_requires_explicit_visual_configuration(self):
        with tempfile.TemporaryDirectory() as temp:
            args = argparse.Namespace(
                path=temp,
                name="缺少风格",
                model_profile="seedance-2.5",
                render_mode="3D",
                aspect_ratio="16:9",
                visual_style="",
                global_prompt_profile="GLOBAL_3D_V1",
                genre="校园求生",
            )
            with self.assertRaisesRegex(ValueError, "visual_style不能为空"):
                INITIALIZER.initialize(args)

    def test_copies_only_selected_model_template_and_workbook(self):
        with tempfile.TemporaryDirectory() as temp:
            args = argparse.Namespace(
                path=temp,
                name="测试项目",
                model_profile="seedance-2.5",
                render_mode="3D",
                aspect_ratio="9:16",
                visual_style="3D国漫",
                global_prompt_profile="GLOBAL_3D_V1",
                genre="修仙",
            )
            root = INITIALIZER.initialize(args)
            config = json.loads((root / "project_config.json").read_text(encoding="utf-8"))
            manifest_template = json.loads(
                (root / "02_SHOTGROUPS/episode_manifest.template.json").read_text(encoding="utf-8")
            )
            self.assertEqual(config["model_profile"], "seedance-2.5")
            self.assertEqual(config["global_prompt_profile"], "GLOBAL_3D_V1")
            self.assertIsNone(config["episode"]["target_seconds"])
            self.assertTrue(config["subtitle_policy"]["append_to_each_language_shot"])
            self.assertEqual(
                config["subtitle_policy"]["required_language_shot_suffix"],
                "视频严禁出现台词、内心独白与系统语音字幕。",
            )
            self.assertEqual(manifest_template["model_profile"], "seedance-2.5")
            self.assertTrue((root / "06_PRODUCTION_TABLES/AI漫剧生产信息表.xlsx").is_file())

    def test_refuses_nonempty_target(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "已有项目"
            target.mkdir()
            (target / "keep.txt").write_text("用户文件", encoding="utf-8")
            args = argparse.Namespace(
                path=temp,
                name="已有项目",
                model_profile="seedance-2.0",
                render_mode="2D",
                aspect_ratio="9:16",
                visual_style="2D国漫",
                global_prompt_profile="GLOBAL_2D_V1",
                genre="校园",
            )
            with self.assertRaises(FileExistsError):
                INITIALIZER.initialize(args)
            self.assertEqual((target / "keep.txt").read_text(encoding="utf-8"), "用户文件")


if __name__ == "__main__":
    unittest.main()
