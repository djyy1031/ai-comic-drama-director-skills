import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "validate_director_representation.py"
TEMPLATE = ROOT / "assets" / "director-shot-representation.template.json"


class ValidatorTests(unittest.TestCase):
    def run_validator(self, payload):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "director.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(SCRIPT), str(path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

    def test_valid_representation_passes(self):
        data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        data["场景诊断"]["主场景类型"] = "对话与关系"
        data["场景诊断"]["主要剧情功能"] = "改变关系"
        data["场景诊断"]["情绪轨迹"] = "克制到坚定"
        data["镜头设计"][0]["镜头功能"] = "建立关系"
        data["镜头设计"][0]["存在理由"] = "明确两人距离与权力关系"
        for key in ["人物表演方案", "镜头执行与连续性检查"]:
            data[key]["状态"] = "PASS"
            data[key]["摘要"] = "本测试已提供相应检查结果"
        result = self.run_validator(data)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_empty_shot_purpose_fails(self):
        data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        result = self.run_validator(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("镜头功能为空", result.stdout)

    def test_unapproved_long_dialogue_shot_fails(self):
        data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        data["场景诊断"]["主场景类型"] = "对话与关系"
        data["场景诊断"]["主要剧情功能"] = "改变关系"
        data["场景诊断"]["情绪轨迹"] = "克制到坚定"
        shot = data["镜头设计"][0]
        shot["镜头功能"] = "推进指控"
        shot["存在理由"] = "呈现关系变化"
        shot["建议时长秒"] = 24
        result = self.run_validator(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("超过6秒", result.stdout)

    def test_language_segments_must_rebuild_original(self):
        data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        data["场景诊断"]["主场景类型"] = "对话与关系"
        data["场景诊断"]["主要剧情功能"] = "改变关系"
        data["场景诊断"]["情绪轨迹"] = "克制到坚定"
        data["不可修改原文台词"] = [{"说话人": "张三", "原文": "你必须把真相告诉我。"}]
        data["语言单元"] = [{
            "语言单元ID": "DIALOGUE-01",
            "类型": "对白",
            "说话人": "张三",
            "完整原文": "你必须把真相告诉我。",
            "所属分镜组": "EP001-SG01",
            "默认不跨组": True,
            "连续要求": "切镜时不得重新起句",
        }]
        shot = data["镜头设计"][0]
        shot["镜头功能"] = "建立关系"
        shot["存在理由"] = "明确两人距离"
        shot["语言片段"] = [{
            "语言单元ID": "DIALOGUE-01", "片段顺序": 1, "原文片段": "你必须把真相告诉我！",
            "开始方式": "动作触发开始", "开始触发": "张三放下账本后", "语言时长秒": 2.4,
            "时长依据": "ACTUAL_READ", "口型状态": "张三现场口型同步", "连续要求": "同一口气",
        }]
        result = self.run_validator(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("无法逐字拼回", result.stdout)

    def test_first_language_segment_requires_action_trigger_mode(self):
        data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        data["场景诊断"]["主场景类型"] = "对话与关系"
        data["场景诊断"]["主要剧情功能"] = "改变关系"
        data["场景诊断"]["情绪轨迹"] = "克制到坚定"
        data["不可修改原文台词"] = [{"说话人": "张三", "原文": "告诉我。"}]
        data["语言单元"] = [{"语言单元ID": "D1", "类型": "对白", "说话人": "张三", "完整原文": "告诉我。", "所属分镜组": "EP001-SG01", "默认不跨组": True, "连续要求": "不重启"}]
        shot = data["镜头设计"][0]
        shot["镜头功能"] = "推进质问"
        shot["存在理由"] = "形成动作与台词因果"
        shot["语言片段"] = [{"语言单元ID": "D1", "片段顺序": 1, "原文片段": "告诉我。", "开始方式": "无停顿承接", "开始触发": "张三放下账本后", "语言时长秒": 1.2, "时长依据": "ACTUAL_READ", "口型状态": "现场口型", "连续要求": "不重启"}]
        result = self.run_validator(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("动作触发开始", result.stdout)

    def test_execution_check_must_pass(self):
        data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        data["场景诊断"]["主场景类型"] = "对话与关系"
        data["场景诊断"]["主要剧情功能"] = "改变关系"
        data["场景诊断"]["情绪轨迹"] = "克制到坚定"
        data["镜头设计"][0]["镜头功能"] = "建立关系"
        data["镜头设计"][0]["存在理由"] = "明确两人距离"
        data["镜头执行与连续性检查"]["状态"] = "ERROR"
        result = self.run_validator(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("未通过", result.stdout)

    def test_group_transition_tail_must_match_last_shot(self):
        data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        data["场景诊断"]["主场景类型"] = "对话与关系"
        data["场景诊断"]["主要剧情功能"] = "改变关系"
        data["场景诊断"]["情绪轨迹"] = "克制到坚定"
        data["镜头设计"][0]["镜头功能"] = "建立关系"
        data["镜头设计"][0]["存在理由"] = "明确两人距离"
        data["组间转场设计"]["前组尾镜签名"] = "错误签名"
        result = self.run_validator(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("必须匹配本组最后一镜", result.stdout)

    def test_rejects_same_character_closeup_across_groups(self):
        data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        data["场景诊断"]["主场景类型"] = "对话与关系"
        data["场景诊断"]["主要剧情功能"] = "改变关系"
        data["场景诊断"]["情绪轨迹"] = "克制到坚定"
        shot = data["镜头设计"][0]
        shot["镜头功能"] = "情绪落点"
        shot["存在理由"] = "建立下一组反应动机"
        shot["主视觉主体"] = "张三"
        shot["镜头签名"] = "张三脸部特写|正面|沉默"
        shot["摄影机"]["景别"] = "脸部特写"
        transition = data["组间转场设计"]
        transition.update({
            "前组尾镜签名": shot["镜头签名"],
            "前组尾镜主体": "张三",
            "前组尾镜景别": "脸部特写",
            "后组首镜建议签名": "张三眼部特写|侧面|抬眼",
            "后组首镜建议主体": "张三",
            "后组首镜建议景别": "眼部特写",
        })
        result = self.run_validator(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("同一人物特写不能直接衔接", result.stdout)

    def test_allows_subject_change_across_groups(self):
        data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        for key in ["人物表演方案", "镜头执行与连续性检查"]:
            data[key]["状态"] = "PASS"
            data[key]["摘要"] = "本测试已提供相应检查结果"
        data["场景诊断"]["主场景类型"] = "对话与关系"
        data["场景诊断"]["主要剧情功能"] = "改变关系"
        data["场景诊断"]["情绪轨迹"] = "克制到坚定"
        shot = data["镜头设计"][0]
        shot["镜头功能"] = "情绪落点"
        shot["存在理由"] = "建立下一组反应动机"
        transition = data["组间转场设计"]
        transition.update({
            "前组尾镜签名": shot["镜头签名"],
            "前组尾镜主体": shot["主视觉主体"],
            "前组尾镜景别": shot["摄影机"]["景别"],
        })
        result = self.run_validator(data)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
