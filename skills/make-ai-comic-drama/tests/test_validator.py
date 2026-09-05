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
        "global_prompt_profile": "TEST_GLOBAL_V1",
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
    shots = []
    prompt_blocks = [
        "【全局固定画质参数】",
        "测试项目统一画质与画幅。",
        "【全局通用负面提示词】",
        "禁止字幕、背景音乐和画面漂移。",
        "李明=李明音色=",
        "张三=",
        "金融一班教室=",
        "【摄影机运动总设定】",
        "对话轴线稳定，摄影机保持轴线同侧。",
        "【场景与光影】",
        "金融一班教室白天，李明站在讲台右侧，张三坐在最后一排。",
    ]
    start = 0.0
    index = 1
    while start < duration:
        end = min(start + 5.0, duration)
        segments = []
        if index == 1:
            segments = [{
                "language_id": "DIA01",
                "segment_index": 1,
                "text": "张三，",
                "start_mode": "ACTION_TRIGGER",
                "start_trigger": "李明抬眼看向张三后",
                "spoken_duration_seconds": 0.8,
                "timing_basis": "ACTUAL_READ",
                "mouth_state": "李明现场口型同步",
                "delivery_continuity": "开始同一条完整对白",
            }]
        elif index == 2:
            segments = [{
                "language_id": "DIA01",
                "segment_index": 2,
                "text": "你过来。",
                "start_mode": "CONTINUE_WITHOUT_RESTART",
                "start_trigger": "切到张三反应镜头时",
                "spoken_duration_seconds": 1.6,
                "timing_basis": "ACTUAL_READ",
                "mouth_state": "李明画外连续声",
                "delivery_continuity": "无停顿承接上一镜",
            }]
        shots.append(
            {
                "shot_id": f"S{index:02d}",
                "start_seconds": start,
                "end_seconds": end,
                "shot_signature": f"镜头{index}|轴线同侧|测试主体",
                "purpose": "推进对话与人物反应",
                "existence_reason": "保持正常对话镜头节拍",
                "spoken_segments": segments,
            }
        )
        if index == 1:
            language = "李明抬眼看向张三后，李明（平静）朝向张三开始说：“张三，”"
        elif index == 2:
            language = "切到张三反应镜头时，李明声音转为画外连续声，无停顿承接上一镜继续说：“你过来。”"
        else:
            language = "李明与张三保持当前空间关系，画面继续推进。"
        suffix = " 视频严禁出现台词、内心独白与系统语音字幕。" if segments else ""
        prompt_blocks.append(f"【{start:g}-{end:g}秒】：50mm正常对话镜头。{language}{suffix}")
        start = end
        index += 1
    prompt = "\n".join(prompt_blocks)
    return {
        "schema_version": "1.0",
        "episode": 1,
        "model_profile": model,
        "planned_final_duration_seconds": duration,
        "timeline_overhead_seconds": 0,
        "final_duration_seconds": duration,
        "language_units": [{
            "language_id": "DIA01",
            "speaker": "李明",
            "kind": "DIALOGUE",
            "full_text": "张三，你过来。",
            "shot_group_ids": ["EP001-SG01"],
            "start_trigger": "李明抬眼看向张三后",
            "timing_basis": "ACTUAL_READ",
            "spoken_duration_seconds": 2.4,
            "continuity_requirement": "切镜无停顿、不重启呼吸和语气",
            "cross_group_exception": False,
            "cross_group_transition": None,
        }],
        "shot_groups": [
            {
                "shot_group_id": "EP001-SG01",
                "duration_seconds": duration,
                "duration_exception_reason": exception,
                "scene_name": "金融一班教室",
                "story_event": "李明叫张三到讲台",
                "has_spoken_language": True,
                "start_blocking": {
                    "world_coordinates": "李明在讲台右侧，张三在最后一排",
                    "screen_coordinates": "李明在画面左前景，张三在画面右后景",
                },
                "shots": shots,
                "prompt_asset_bindings": ["李明=李明音色=", "张三=", "金融一班教室="],
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
        manifest["shot_groups"][0]["clean_prompt"] = manifest["shot_groups"][0][
            "clean_prompt"
        ].replace(" 视频严禁出现台词、内心独白与系统语音字幕。", "", 1)
        result = self.validate("seedance-2.0", manifest)
        self.assertFalse(result.ok)
        self.assertTrue(any("含语言内容镜头" in error for error in result.errors))

    def test_group_final_suffix_does_not_replace_each_language_shot_suffix(self):
        manifest = base_manifest("seedance-2.0", 15)
        prompt = manifest["shot_groups"][0]["clean_prompt"]
        manifest["shot_groups"][0]["clean_prompt"] = (
            prompt.replace(" 视频严禁出现台词、内心独白与系统语音字幕。", "", 1)
            + "\n"
            "【全局锁定与禁令】\n"
            "视频严禁出现台词、内心独白与系统语音字幕。"
        )
        result = self.validate("seedance-2.0", manifest)
        self.assertFalse(result.ok)
        self.assertTrue(any("第1个含语言内容镜头" in error for error in result.errors))

    def test_language_shot_suffix_requires_preceding_space(self):
        manifest = base_manifest("seedance-2.0", 15)
        manifest["shot_groups"][0]["clean_prompt"] = manifest["shot_groups"][0][
            "clean_prompt"
        ].replace(
            " 视频严禁出现台词、内心独白与系统语音字幕。",
            "视频严禁出现台词、内心独白与系统语音字幕。",
            1,
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

    def test_requires_global_prompt_before_every_group(self):
        manifest = base_manifest("seedance-2.0", 15)
        manifest["shot_groups"][0]["clean_prompt"] = manifest["shot_groups"][0][
            "clean_prompt"
        ].replace("【全局固定画质参数】\n", "", 1)
        result = self.validate("seedance-2.0", manifest)
        self.assertFalse(result.ok)
        self.assertTrue(any("第一行必须是" in error for error in result.errors))

    def test_requires_prompt_asset_bindings_before_camera(self):
        manifest = base_manifest("seedance-2.0", 15)
        manifest["shot_groups"][0]["clean_prompt"] = manifest["shot_groups"][0][
            "clean_prompt"
        ].replace("金融一班教室=\n", "", 1)
        result = self.validate("seedance-2.0", manifest)
        self.assertFalse(result.ok)
        self.assertTrue(any("资产绑定" in error for error in result.errors))

    def test_rejects_old_standalone_language_track_block(self):
        manifest = base_manifest("seedance-2.0", 15)
        manifest["shot_groups"][0]["clean_prompt"] = manifest["shot_groups"][0][
            "clean_prompt"
        ].replace(
            "【摄影机运动总设定】",
            "【连续对白音轨总设定】\n音轨覆盖【0-10秒】\n【摄影机运动总设定】",
            1,
        )
        result = self.validate("seedance-2.0", manifest)
        self.assertFalse(result.ok)
        self.assertTrue(any("禁止使用独立计时" in error for error in result.errors))

    def test_rejects_language_segments_that_change_original(self):
        manifest = base_manifest("seedance-2.0", 15)
        manifest["shot_groups"][0]["shots"][1]["spoken_segments"][0]["text"] = "你走开。"
        manifest["shot_groups"][0]["clean_prompt"] = manifest["shot_groups"][0][
            "clean_prompt"
        ].replace("“你过来。”", "“你走开。”")
        result = self.validate("seedance-2.0", manifest)
        self.assertFalse(result.ok)
        self.assertTrue(any("无法逐字拼回" in error for error in result.errors))

    def test_rejects_missing_action_trigger_in_prompt(self):
        manifest = base_manifest("seedance-2.0", 15)
        manifest["shot_groups"][0]["clean_prompt"] = manifest["shot_groups"][0][
            "clean_prompt"
        ].replace("李明抬眼看向张三后，", "", 1)
        result = self.validate("seedance-2.0", manifest)
        self.assertFalse(result.ok)
        self.assertTrue(any("语言开始触发" in error for error in result.errors))

    def test_rejects_unapproved_cross_group_language(self):
        manifest = base_manifest("seedance-2.0", 15)
        manifest["language_units"][0]["shot_group_ids"] = ["EP001-SG01", "EP001-SG02"]
        result = self.validate("seedance-2.0", manifest)
        self.assertFalse(result.ok)
        self.assertTrue(any("默认不得跨分镜组" in error or "不存在的分镜组" in error for error in result.errors))

    def test_rejects_ambiguous_pronoun_outside_dialogue(self):
        manifest = base_manifest("seedance-2.0", 15)
        manifest["shot_groups"][0]["clean_prompt"] = (
            "李明站在金融一班教室，他突然转身。\n"
            + manifest["shot_groups"][0]["clean_prompt"]
        )
        result = self.validate("seedance-2.0", manifest)
        self.assertFalse(result.ok)
        self.assertTrue(any("模糊指代" in error for error in result.errors))

    def test_allows_pronoun_inside_original_dialogue(self):
        manifest = base_manifest("seedance-2.0", 15)
        manifest["language_units"][0]["full_text"] = "他没有来。"
        manifest["language_units"][0]["spoken_duration_seconds"] = 2.4
        manifest["shot_groups"][0]["shots"][0]["spoken_segments"][0]["text"] = "他没有"
        manifest["shot_groups"][0]["shots"][1]["spoken_segments"][0]["text"] = "来。"
        manifest["shot_groups"][0]["clean_prompt"] = (
            manifest["shot_groups"][0]["clean_prompt"]
            .replace("“张三，”", "“他没有”")
            .replace("“你过来。”", "“来。”")
        )
        result = self.validate("seedance-2.0", manifest)
        self.assertTrue(result.ok, result.errors)

    def test_rejects_unapproved_long_dialogue_shot(self):
        manifest = base_manifest("seedance-2.0", 15)
        group = manifest["shot_groups"][0]
        group["shots"] = [{
            "shot_id": "S01",
            "start_seconds": 0,
            "end_seconds": 15,
            "shot_signature": "中景|轴线同侧|整段对话",
            "purpose": "整段对话",
            "existence_reason": "错误地合并全部镜头",
            "spoken_segments": [
                deepcopy(manifest["shot_groups"][0]["shots"][0]["spoken_segments"][0]),
                deepcopy(manifest["shot_groups"][0]["shots"][1]["spoken_segments"][0]),
            ],
        }]
        group["clean_prompt"] = (
            "【全局固定画质参数】\n测试项目统一画质与画幅。\n"
            "【全局通用负面提示词】\n禁止字幕、背景音乐和画面漂移。\n"
            "李明=李明音色=\n张三=\n金融一班教室=\n"
            "【摄影机运动总设定】\n对话轴线稳定。\n"
            "【0-15秒】：中景承载整段对话。李明抬眼看向张三后，李明开始说：“张三，”"
            "切到张三反应镜头时，李明无停顿承接上一镜继续说：“你过来。” "
            "视频严禁出现台词、内心独白与系统语音字幕。"
        )
        result = self.validate("seedance-2.0", manifest)
        self.assertFalse(result.ok)
        self.assertTrue(any("单镜6秒上限" in error for error in result.errors))

    def test_allows_explicitly_approved_long_take(self):
        manifest = base_manifest("seedance-2.0", 15)
        group = manifest["shot_groups"][0]
        group["shots"] = [{
            "shot_id": "S01",
            "start_seconds": 0,
            "end_seconds": 15,
            "shot_signature": "中景|轴线同侧|批准长镜头",
            "purpose": "用户明确要求的一镜到底",
            "existence_reason": "保持不中断的压迫感",
            "spoken_segments": [
                deepcopy(manifest["shot_groups"][0]["shots"][0]["spoken_segments"][0]),
                deepcopy(manifest["shot_groups"][0]["shots"][1]["spoken_segments"][0]),
            ],
            "long_take_approved": True,
            "long_take_reason": "用户明确要求一镜到底，并设计持续走位与焦点变化",
        }]
        group["clean_prompt"] = (
            "【全局固定画质参数】\n测试项目统一画质与画幅。\n"
            "【全局通用负面提示词】\n禁止字幕、背景音乐和画面漂移。\n"
            "李明=李明音色=\n张三=\n金融一班教室=\n"
            "【摄影机运动总设定】\n对话轴线稳定。\n"
            "【0-15秒】：用户明确批准的一镜到底，人物持续走位且摄影机持续变焦。"
            "李明抬眼看向张三后，李明开始说：“张三，”"
            "切到张三反应镜头时，李明无停顿承接上一镜继续说：“你过来。” "
            "视频严禁出现台词、内心独白与系统语音字幕。"
        )
        result = self.validate("seedance-2.0", manifest)
        self.assertTrue(result.ok, result.errors)

    def test_rejects_prompt_collapsing_registered_shots(self):
        manifest = base_manifest("seedance-2.0", 15)
        manifest["shot_groups"][0]["clean_prompt"] = (
            "【0-15秒】：错误地把三个镜头合成一个长镜头。"
            "对话：李明：（平静）朝向张三“张三，你过来。” "
            "视频严禁出现台词、内心独白与系统语音字幕。"
        )
        result = self.validate("seedance-2.0", manifest)
        self.assertFalse(result.ok)
        self.assertTrue(any("禁止把多个镜头合并" in error for error in result.errors))

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
            {"shot_id": "S01", "start_seconds": 0, "end_seconds": 5, "purpose": "建立空间", "existence_reason": "建立方向"},
            {"shot_id": "S02", "start_seconds": 6, "end_seconds": 15, "purpose": "完成事件", "existence_reason": "完成落点"},
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
