import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validator", ROOT / "scripts" / "validate_asset_grounding.py")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def valid_package():
    return {
        "规范版本": "1.0",
        "来源": {"剧本": ["第1集"], "全局控制提示词": ["画质参数"], "用户说明": []},
        "资产目录": [
            {"标准名称": "祖父母房", "类型": "场景", "文件": "room.png", "检查状态": "VERIFIED", "证据方式": "查看原图", "可见或可听证据": ["参考图左侧有门"], "不可确认": ["门外完整格局"]},
            {"标准名称": "张三", "类型": "角色", "文件": "zhang.png", "检查状态": "VERIFIED", "证据方式": "查看原图", "可见或可听证据": ["深色短褐"], "不可确认": []},
        ],
        "场景空间锚定": [{"场景标准名称": "祖父母房", "参考资产": ["祖父母房"], "坐标表达方式": "REFERENCE_VIEW_ANCHORED", "参考视角说明": "从入口右前方看向窗墙", "固定结构": ["左侧门"], "固定陈设": ["床"], "出入口": ["左侧门"], "光源": ["左侧门外日光"], "遮挡": [], "可用人物区域": ["床前空地"], "可用摄影机区域": ["入口内侧"], "禁止穿越区域": ["墙体"], "不可确认区域": ["门外"], "冲突": [], "状态": "PASS"}],
        "角色身份锚定": [], "道具状态锚定": [], "声音绑定": [],
        "剧本资产映射": [{"来源锚点": "1-1", "所需资产": ["祖父母房", "张三"], "未解决": [], "状态": "PASS"}],
        "最终状态": "PASS",
    }


class SkillTests(unittest.TestCase):
    def test_files_and_version(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn('version: "1.0.1"', skill)
        self.assertIn("文件名匹配不等于内容正确", skill)
        self.assertTrue((ROOT / "agents" / "openai.yaml").exists())
        json.loads((ROOT / "assets" / "asset-grounding-package.template.json").read_text(encoding="utf-8"))

    def test_valid_package(self):
        self.assertEqual(VALIDATOR.validate(valid_package()), [])

    def test_filename_only_cannot_verify(self):
        data = valid_package()
        data["资产目录"][0]["可见或可听证据"] = []
        self.assertTrue(any("实际证据" in item for item in VALIDATOR.validate(data)))

    def test_unverified_required_asset_blocks_pass(self):
        data = valid_package()
        data["资产目录"][1]["检查状态"] = "UNVERIFIED"
        errors = VALIDATOR.validate(data)
        self.assertTrue(any("所需资产未核验" in item for item in errors))
        self.assertTrue(any("最终状态不能为PASS" in item for item in errors))

    def test_scene_conflict_blocks_pass(self):
        data = valid_package()
        data["场景空间锚定"][0]["冲突"] = ["门位置冲突"]
        self.assertTrue(any("存在冲突" in item for item in VALIDATOR.validate(data)))

    def test_unused_unverified_asset_does_not_block_current_mapping(self):
        data = valid_package()
        data["资产目录"].append({"标准名称": "备用声音", "类型": "声音", "文件": "", "检查状态": "UNVERIFIED", "证据方式": "", "可见或可听证据": [], "不可确认": ["尚未试听"]})
        self.assertEqual(VALIDATOR.validate(data), [])


if __name__ == "__main__":
    unittest.main()
