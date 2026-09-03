from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "validate_project.py"
SPEC = importlib.util.spec_from_file_location("ai_drama_validate_project", MODULE_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def base_config(model: str) -> dict:
    return {
        "schema_version": "1.0",
        "project_name": "测试项目",
        "model_profile": model,
        "render_mode": "2D",
        "aspect_ratio": "9:16",
        "visual_style": "2D国漫",
        "genre": {"primary": "校园", "packs": []},
        "episode": {"target_seconds": None, "final_max_seconds": 180},
        "subtitle_policy": {
            "generate_dialogue_subtitles": False,
            "append_to_each_language_shot": True,
            "required_language_shot_suffix": "视频严禁出现台词、内心独白与系统语音字幕。",
            "allow_story_ui_text": True,
        },
    }


def base_manifest(model: str, duration: float, exception: str | None = None) -> dict:
    prompt = (
        "综合训练教室白天，李明站在讲台右侧，张三坐在最后一排。\n"
        f"【0.0-{duration:g}秒】：中景固定拍摄。"
        "对话：李明：（下颌轻收）【语气：平静】朝向张三“张三，你过来。” "
        "视频严禁出现台词、内心独白与系统语音字幕。"
    )
    return {
        "schema_version": "1.0",
        "episode": 1,
        "model_profile": model,
        "planned_final_duration_seconds": duration,
        "timeline_overhead_seconds": 0,
        "final_duration_seconds": duration,
        "shot_groups": [
            {
                "shot_group_id": "EP001-SG01",
                "duration_seconds": duration,
                "duration_exception_reason": exception,
                "scene_name": "综合训练教室",
                "story_event": "李明叫张三到讲台",
                "has_spoken_language": True,
                "start_blocking": {
                    "world_coordinates": "李明在讲台右侧，张三在最后一排",
                    "screen_coordinates": "李明在画面左前景，张三在画面右后景",
                },
                "shots": [
                    {
                        "shot_id": "S01",
                        "start_seconds": 0,
                        "end_seconds": duration,
                        "purpose": "完成事件",
                    }
                ],
                "assets": [
                    {
                        "asset_id": "CHAR-LM",
                        "canonical_name": "李明角色资产",
                        "necessity_score": 3,
                        "status": "READY",
                    }
                ],
                "clean_prompt": prompt,
            }
        ],
        "audits": {
            "script_fidelity": "PASS",
            "asset_coverage": "PASS",
            "continuity_generatability": "PASS",
        },
        "production_ready": True,
        "sound_plan": {
            "status": "READY",
            "cues": [
                {
                    "start_seconds": 0,
                    "end_seconds": duration,
                    "sound_type": "AMBIENCE",
                    "purpose": "锁定教室空间",
                    "rights_status": "ORIGINAL",
                }
            ],
        },
        "final_episode_ready": True,
    }


class ValidatorTests(unittest.TestCase):
    def test_rejects_missing_visual_configuration(self):
        config = base_config("seedance-2.5")
        config["visual_style"] = ""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_json(root / "project_config.json", config)
            write_json(
                root / "02_SHOTGROUPS/EP001/episode_manifest.json",
                base_manifest("seedance-2.5", 25),
            )
            result = VALIDATOR.validate_project(root, "planning")
            self.assertFalse(result.ok)
            self.assertTrue(any("visual_style不能为空" in item for item in result.errors))

    def make_project(self, model: str, manifest: dict) -> tuple[tempfile.TemporaryDirectory, Path]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        write_json(root / "project_config.json", base_config(model))
        write_json(root / "02_SHOTGROUPS/EP001/episode_manifest.json", manifest)
        return temp, root

    def validate(self, model: str, manifest: dict, stage: str = "planning"):
        temp, root = self.make_project(model, manifest)
        self.addCleanup(temp.cleanup)
        return VALIDATOR.validate_project(root, stage)

    def test_seedance_20_valid_at_15_seconds(self):
        result = self.validate("seedance-2.0", base_manifest("seedance-2.0", 15))
        self.assertTrue(result.ok, result.errors)

    def test_seedance_20_rejects_over_15_seconds(self):
        result = self.validate("seedance-2.0", base_manifest("seedance-2.0", 16))
        self.assertFalse(result.ok)
        self.assertTrue(any("不得超过15秒" in error for error in result.errors))

    def test_seedance_25_valid_between_20_and_30_seconds(self):
        result = self.validate("seedance-2.5", base_manifest("seedance-2.5", 25))
        self.assertTrue(result.ok, result.errors)

    def test_seedance_25_rejects_under_20_without_reason(self):
        result = self.validate("seedance-2.5", base_manifest("seedance-2.5", 15))
        self.assertFalse(result.ok)
        self.assertTrue(any("例外原因" in error for error in result.errors))

    def test_seedance_25_accepts_under_20_with_reason(self):
        manifest = base_manifest("seedance-2.5", 15, "场景切换，无法与相邻事件合并")
        result = self.validate("seedance-2.5", manifest)
        self.assertTrue(result.ok, result.errors)

    def test_rejects_model_profile_mismatch(self):
        result = self.validate("seedance-2.0", base_manifest("seedance-2.5", 15, "场景切换"))
        self.assertFalse(result.ok)
        self.assertTrue(any("与项目配置" in error for error in result.errors))

    def test_rejects_missing_language_shot_suffix(self):
        manifest = base_manifest("seedance-2.0", 15)
        manifest["shot_groups"][0]["clean_prompt"] = (
            "【0.0-15.0秒】：中景固定拍摄。"
            "对话：李明：（目光稳定）【语气：平静】朝向张三“张三，你过来。”"
        )
        result = self.validate("seedance-2.0", manifest)
        self.assertFalse(result.ok)
        self.assertTrue(any("含语言内容镜头" in error for error in result.errors))

    def test_group_final_suffix_does_not_replace_each_language_shot_suffix(self):
        manifest = base_manifest("seedance-2.0", 15)
        manifest["shot_groups"][0]["clean_prompt"] = (
            "【0.0-7.0秒】：中景固定拍摄。"
            "对话：李明：（平静）朝向张三“第一句。”\n"
            "【7.0-15.0秒】：近景固定拍摄。"
            "对话：张三：（迟疑）朝向李明“第二句。” "
            "视频严禁出现台词、内心独白与系统语音字幕。\n"
            "【全局锁定与禁令】\n"
            "视频严禁出现台词、内心独白与系统语音字幕。"
        )
        result = self.validate("seedance-2.0", manifest)
        self.assertFalse(result.ok)
        self.assertTrue(any("第1个含语言内容镜头" in error for error in result.errors))

    def test_language_shot_suffix_requires_preceding_space(self):
        manifest = base_manifest("seedance-2.0", 15)
        manifest["shot_groups"][0]["clean_prompt"] = (
            "【0.0-15.0秒】：中景固定拍摄。"
            "对话：李明：（平静）朝向张三“张三，你过来。”"
            "视频严禁出现台词、内心独白与系统语音字幕。"
        )
        result = self.validate("seedance-2.0", manifest)
        self.assertFalse(result.ok)
        self.assertTrue(any("含语言内容镜头" in error for error in result.errors))

    def test_detects_spoken_language_even_when_flag_is_false(self):
        manifest = base_manifest("seedance-2.0", 15)
        manifest["shot_groups"][0]["has_spoken_language"] = False
        result = self.validate("seedance-2.0", manifest)
        self.assertFalse(result.ok)
        self.assertTrue(any("has_spoken_language" in error for error in result.errors))

    def test_rejects_ambiguous_pronoun_outside_dialogue(self):
        manifest = base_manifest("seedance-2.0", 15)
        manifest["shot_groups"][0]["clean_prompt"] = (
            "李明站在综合训练教室，他突然转身。\n"
            "【0.0-15.0秒】：中景固定拍摄。"
            "对话：李明：（平静）朝向张三“张三，你过来。” "
            "视频严禁出现台词、内心独白与系统语音字幕。"
        )
        result = self.validate("seedance-2.0", manifest)
        self.assertFalse(result.ok)
        self.assertTrue(any("模糊指代" in error for error in result.errors))

    def test_allows_pronoun_inside_original_dialogue(self):
        manifest = base_manifest("seedance-2.0", 15)
        manifest["shot_groups"][0]["clean_prompt"] = (
            "李明站在综合训练教室。\n"
            "【0.0-15.0秒】：中景固定拍摄。"
            "对话：李明：（目光稳定）【语气：平静】朝向张三“他没有来。” "
            "视频严禁出现台词、内心独白与系统语音字幕。"
        )
        result = self.validate("seedance-2.0", manifest)
        self.assertTrue(result.ok, result.errors)

    def test_rejects_episode_over_180_seconds(self):
        manifest = base_manifest("seedance-2.0", 15)
        manifest["planned_final_duration_seconds"] = 181
        manifest["timeline_overhead_seconds"] = 166
        result = self.validate("seedance-2.0", manifest)
        self.assertFalse(result.ok)
        self.assertTrue(any("不超过180" in error for error in result.errors))

    def test_production_requires_mandatory_assets_ready(self):
        manifest = base_manifest("seedance-2.0", 15)
        manifest["shot_groups"][0]["assets"][0]["status"] = "PENDING"
        result = self.validate("seedance-2.0", manifest, "production")
        self.assertFalse(result.ok)
        self.assertTrue(any("尚未READY" in error for error in result.errors))

    def test_final_requires_sound_plan(self):
        manifest = base_manifest("seedance-2.0", 15)
        manifest["sound_plan"] = {"status": "PENDING", "cues": []}
        result = self.validate("seedance-2.0", manifest, "final")
        self.assertFalse(result.ok)
        self.assertTrue(any("sound_plan.status=READY" in error for error in result.errors))

    def test_final_sound_plan_must_cover_full_timeline(self):
        manifest = base_manifest("seedance-2.0", 15)
        manifest["sound_plan"]["cues"][0]["start_seconds"] = 2
        result = self.validate("seedance-2.0", manifest, "final")
        self.assertFalse(result.ok)
        self.assertTrue(any("必须从0秒开始覆盖" in error for error in result.errors))

    def test_rejects_shot_timeline_gap(self):
        manifest = base_manifest("seedance-2.0", 15)
        manifest["shot_groups"][0]["shots"] = [
            {"shot_id": "S01", "start_seconds": 0, "end_seconds": 5, "purpose": "建立空间"},
            {"shot_id": "S02", "start_seconds": 6, "end_seconds": 15, "purpose": "完成事件"},
        ]
        result = self.validate("seedance-2.0", manifest)
        self.assertFalse(result.ok)
        self.assertTrue(any("时间不连续" in error for error in result.errors))

    def test_seedance_25_rejects_over_30_seconds(self):
        result = self.validate("seedance-2.5", base_manifest("seedance-2.5", 31))
        self.assertFalse(result.ok)
        self.assertTrue(any("不得超过30秒" in error for error in result.errors))

    def test_valid_final_episode(self):
        result = self.validate("seedance-2.5", base_manifest("seedance-2.5", 25), "final")
        self.assertTrue(result.ok, result.errors)


if __name__ == "__main__":
    unittest.main()
