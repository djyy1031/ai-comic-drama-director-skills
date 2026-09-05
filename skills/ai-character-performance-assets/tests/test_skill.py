import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "validate_performance_plan.py"


def valid_payload():
    return {
        "规范版本": "1.0",
        "来源锚点": {"集": 1, "场": "1-1", "分镜组": "第一组"},
        "不可修改剧情事实": ["张三质问李四"],
        "不可修改原文台词": [{"说话人": "张三", "原文": "你为什么骗我？"}],
        "在场角色标准名称": ["张三", "李四"],
        "场景功能": "张三确认李四隐瞒事实，关系转为对立",
        "角色场景计划": [
            {"角色标准名称": "张三", "当前目标": "迫使李四承认隐瞒", "阻碍": "李四拒绝回答", "失败代价": "无法确认真相", "潜台词": "张三已经不再信任李四", "身体基线": "重心稳定，呼吸受控", "实际任务": "手中整理账本", "地位起点": "主动质询", "地位终点": "获得信息优势", "听与眼神规则": "视线在李四双眼与账本之间切换"},
            {"角色标准名称": "李四", "当前目标": "让张三停止追问", "阻碍": "张三掌握账本", "失败代价": "隐瞒被揭穿", "潜台词": "李四在拖延", "身体基线": "肩部略收，呼吸变浅", "实际任务": "擦拭桌面", "地位起点": "被动防守", "地位终点": "防线松动", "听与眼神规则": "听到关键字前先看账本，随后避开张三视线"},
        ],
        "语言单元": [{
            "语言单元ID": "对白一", "类型": "对白", "说话人": "张三", "完整原文": "你为什么骗我？",
            "所属分镜组": "第一组", "开始触发": "张三放下账本后", "时长依据": "ACTUAL_READ",
            "语言时长秒": 2.2, "默认不跨组": True, "连续要求": "切镜不重启、无停顿承接",
            "建议片段": [
                {"片段顺序": 1, "原文片段": "你为什么", "开始方式": "动作触发开始", "开始触发": "张三放下账本后", "声音状态": "压住怒意开始质问"},
                {"片段顺序": 2, "原文片段": "骗我？", "开始方式": "无停顿承接", "开始触发": "切到李四反应镜头时", "声音状态": "同一口气加重句尾"},
            ],
        }],
        "表演节拍": [
            {"顺序": 1, "触发事实": "张三放下账本", "当前策略": "直接施压", "主动角色": "张三", "目标对象": "李四", "语言单元ID": "对白一", "可见行为": "张三停止翻页，目光落到李四脸上", "听者反应": "李四在话尾前停止擦桌，视线先落到账本", "身体任务": "整理账本转为停止", "距离或地位变化": "空间距离不变，张三取得主动", "入节拍状态": "张三仍在核对账本", "出节拍状态": "李四的擦拭动作已经停止", "建议承载镜头功能": "双人关系镜头接听者反应"}
        ],
        "状态继承": {"入场状态": {}, "本场变化": ["李四停止擦桌"], "出场状态": {"李四": "防线松动"}},
        "风险与待确认": [],
    }


class SkillTests(unittest.TestCase):
    def run_validator(self, payload):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "plan.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            return subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True, encoding="utf-8")

    def test_structure_and_links(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: ai-character-performance-assets", skill)
        self.assertIn('version: "1.2.0"', skill)
        self.assertIn("表演是人物在阻力下", skill)
        for path in ROOT.rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            for link in __import__("re").findall(r"\]\(([^)#]+)", text):
                self.assertTrue((path.parent / link).exists(), f"missing link {path}: {link}")
        json.loads((ROOT / "assets/performance-plan.template.json").read_text(encoding="utf-8"))

    def test_valid_plan(self):
        result = self.run_validator(valid_payload())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rejects_changed_dialogue(self):
        data = valid_payload()
        data["语言单元"][0]["完整原文"] = "你为何欺骗我？"
        result = self.run_validator(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("未原样匹配", result.stdout)

    def test_rejects_segments_that_do_not_rebuild_original(self):
        data = valid_payload()
        data["语言单元"][0]["建议片段"][1]["原文片段"] = "骗我！"
        result = self.run_validator(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("无法逐字拼回", result.stdout)

    def test_rejects_missing_action_trigger(self):
        data = valid_payload()
        data["语言单元"][0]["建议片段"][0]["开始触发"] = ""
        result = self.run_validator(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("开始触发", result.stdout)

    def test_rejects_offscreen_character(self):
        data = valid_payload()
        data["表演节拍"][0]["主动角色"] = "王五"
        result = self.run_validator(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("白名单外主动角色", result.stdout)

    def test_every_visible_character_requires_performance_plan(self):
        data = valid_payload()
        data["角色场景计划"] = data["角色场景计划"][:1]
        result = self.run_validator(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("李四", result.stdout)
        self.assertIn("背景人物也不能木站", result.stdout)


if __name__ == "__main__":
    unittest.main()
