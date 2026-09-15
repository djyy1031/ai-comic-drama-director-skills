import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/validate_execution_report.py"


def shot(shot_id, screen_side, segments=None):
    return {
        "镜头ID": shot_id,
        "时长秒": 3,
        "主视觉主体": "张三" if shot_id == "镜头一" else "李四",
        "景别": "中景",
        "镜头签名": f"{shot_id}|中景|{screen_side}",
        "活动实体": ["张三", "李四", "账本", "客栈大厅"],
        "画面内人物": ["张三", "李四"],
        "第一帧": {"有效主体": "张三与李四", "动作状态": "两人已经隔桌对峙", "空间关系可读": True, "画面目的": "建立质询关系"},
        "人物空间关系": [
            {"角色标准名称": "张三", "世界位置": "柜台外侧", "画面位置": screen_side, "身体朝向": "躯干朝向李四", "视线目标": "李四双眼", "地标距离": "右手接触柜台上的账本", "移动方向": "原地不移动", "当前表演": "停止翻页，目光转向李四", "表演依据": "张三正在用账本迫使李四回答"},
            {"角色标准名称": "李四", "世界位置": "柜台内侧", "画面位置": "画面右侧" if screen_side == "画面左侧" else "画面左侧", "身体朝向": "躯干朝向张三", "视线目标": "账本", "地标距离": "站在柜台后半步", "移动方向": "原地不移动", "当前表演": "擦桌动作减慢，视线避开张三", "表演依据": "李四看见账本并听见质问"},
        ],
        "道具状态": [{"道具": "账本", "持有者": "张三", "左右手": "右手", "接触点": "掌心压住封面", "状态": "合上", "结果": "位置不变"}],
        "摄影机": {"轴线侧": "对话轴线南侧", "朝向": "朝北看柜台", "高度": "胸口高度", "距离": "距张三两米", "主要运镜": "固定机位", "停止位置": "原位", "最终焦点": "李四的反应"},
        "光线": {"主光来源": "东侧窗户日光", "主光方向": "画面右向左", "摄影机受光侧": "阴影侧", "曝光优先级": "保留窗外高光与人物面部层次", "色卡版本": "全剧色卡v1"},
        "动作物理": {"动作原因": "张三用账本施压", "驱动或发力": "右掌向下压住账本", "接触": "掌心与账本封面接触", "受力结果": "账本稳定在柜台上", "环境反馈": "纸页边缘轻微压平"},
        "语言片段": segments or [],
        "入镜状态": {"账本": "张三右手压住"},
        "出镜状态": {"账本": "张三右手继续压住"},
        "局部修复锁": ["账本始终由张三右手压在柜台上"],
        "问题": [],
        "状态": "PASS",
    }


def valid_payload():
    first = shot("镜头一", "画面左侧", [{"语言单元ID": "对白一", "片段顺序": 1, "原文片段": "你为什么", "开始方式": "动作触发开始", "开始触发": "张三放下账本后", "语言时长秒": 1.1, "时长依据": "ACTUAL_READ", "口型状态": "张三现场口型同步", "连续要求": "切镜不重启"}])
    second = shot("镜头二", "画面左侧", [{"语言单元ID": "对白一", "片段顺序": 2, "原文片段": "骗我？", "开始方式": "无停顿承接", "开始触发": "切到李四反应镜头时", "语言时长秒": 1.1, "时长依据": "ACTUAL_READ", "口型状态": "张三画外连续声", "连续要求": "同一口气继续"}])
    return {
        "规范版本": "1.3",
        "来源锚点": {"集": 1, "场": "1-1", "分镜组": "第一组"},
        "不可修改剧情事实": ["张三质问李四"],
        "不可修改原文台词": [{"说话人": "张三", "原文": "你为什么骗我？"}],
        "活动资产白名单": ["张三", "李四", "账本", "客栈大厅"],
        "画面内人物白名单": ["张三", "李四"],
        "场景空间地图": {"柜台": "大厅北侧"},
        "光线与色卡基线": {"主光": "东窗日光", "色卡版本": "全剧色卡v1"},
        "语言单元": [{"语言单元ID": "对白一", "类型": "对白", "说话人": "张三", "完整原文": "你为什么骗我？", "所属分镜组": "第一组", "默认不跨组": True, "连续要求": "切镜不重启、无停顿承接"}],
        "单镜检查": [first, second],
        "切镜连续性": [{"前镜": "镜头一", "后镜": "镜头二", "人物继承": "位置和朝向一致", "道具继承": "账本仍在张三右手下", "环境继承": "柜台状态一致", "轴线与屏幕方向": "保持轴线南侧", "光线继承": "东窗日光方向一致", "语言承接": "对白一无停顿承接", "问题": [], "状态": "PASS"}],
        "跨分镜组检查": {"是否末组": True, "下一组": "", "前组尾镜签名": "", "前组尾镜主体": "", "前组尾镜景别": "", "后组首镜签名": "", "后组首镜主体": "", "后组首镜景别": "", "转场方法": "", "连续锚点": "", "匹配剪辑明确批准": False, "匹配剪辑理由": "", "可见匹配依据": "", "问题": [], "状态": "PASS"},
        "最终裁决": {"状态": "PASS", "问题": [], "最早返修位置": "无"},
    }


class SkillTests(unittest.TestCase):
    def run_validator(self, payload):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            return subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True, encoding="utf-8")

    def test_structure_and_template(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: ai-shot-execution-continuity", text)
        self.assertIn('version: "1.6.0"', text)
        self.assertIn("成品资产一致性", text)
        self.assertIn("不默认改成一镜到底", text)
        json.loads((ROOT / "assets/execution-report.template.json").read_text(encoding="utf-8"))

    def test_valid_report(self):
        result = self.run_validator(valid_payload())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rejects_stale_entity(self):
        data = valid_payload()
        data["单镜检查"][0]["活动实体"].append("王五")
        result = self.run_validator(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("白名单外实体", result.stdout)

    def test_rejects_unapproved_long_dialogue_shot(self):
        data = valid_payload()
        data["单镜检查"] = [copy.deepcopy(data["单镜检查"][0])]
        data["单镜检查"][0]["时长秒"] = 24
        data["切镜连续性"] = []
        result = self.run_validator(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("超过6秒", result.stdout)
        self.assertIn("不能只有一个镜头", result.stdout)

    def test_requires_every_adjacent_cut(self):
        data = valid_payload()
        data["切镜连续性"] = []
        result = self.run_validator(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("逐对覆盖", result.stdout)

    def test_visible_background_character_cannot_be_omitted(self):
        data = valid_payload()
        data["单镜检查"][0]["人物空间关系"] = data["单镜检查"][0]["人物空间关系"][:1]
        result = self.run_validator(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("李四", result.stdout)
        self.assertIn("背景人物也不能木站", result.stdout)

    def test_rejects_language_segment_mismatch(self):
        data = valid_payload()
        data["单镜检查"][1]["语言片段"][0]["原文片段"] = "骗我！"
        result = self.run_validator(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("无法逐字拼回", result.stdout)

    def test_rejects_missing_action_trigger_mode(self):
        data = valid_payload()
        data["单镜检查"][0]["语言片段"][0]["开始方式"] = "无停顿承接"
        result = self.run_validator(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("动作触发开始", result.stdout)

    def test_rejects_same_character_closeup_across_groups(self):
        data = valid_payload()
        tail = data["单镜检查"][-1]
        tail["主视觉主体"] = "张三"
        tail["景别"] = "脸部特写"
        tail["镜头签名"] = "张三脸部特写|正面|停顿"
        data["跨分镜组检查"] = {
            "是否末组": False, "下一组": "第二组",
            "前组尾镜签名": tail["镜头签名"], "前组尾镜主体": "张三", "前组尾镜景别": "脸部特写",
            "后组首镜签名": "张三眼部特写|侧面|抬眼", "后组首镜主体": "张三", "后组首镜景别": "眼部特写",
            "转场方法": "动作承接", "连续锚点": "张三抬眼动作",
            "匹配剪辑明确批准": False, "匹配剪辑理由": "", "可见匹配依据": "", "问题": [], "状态": "PASS",
        }
        result = self.run_validator(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("同一人物特写不能直接衔接", result.stdout)

    def test_allows_subject_change_across_groups(self):
        data = valid_payload()
        tail = data["单镜检查"][-1]
        data["跨分镜组检查"] = {
            "是否末组": False, "下一组": "第二组",
            "前组尾镜签名": tail["镜头签名"], "前组尾镜主体": tail["主视觉主体"], "前组尾镜景别": tail["景别"],
            "后组首镜签名": "张三近景|正面|吸气", "后组首镜主体": "张三", "后组首镜景别": "近景",
            "转场方法": "视线匹配", "连续锚点": "李四看向张三，张三接住视线后吸气",
            "匹配剪辑明确批准": False, "匹配剪辑理由": "", "可见匹配依据": "", "问题": [], "状态": "PASS",
        }
        result = self.run_validator(data)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
