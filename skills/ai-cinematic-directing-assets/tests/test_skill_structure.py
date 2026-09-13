import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class SkillStructureTests(unittest.TestCase):
    def test_frontmatter_and_interface(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        self.assertIn("name: ai-cinematic-directing-assets", text)
        self.assertIn('version: "1.6.0"', text)
        self.assertIn("画面执行表达库", text)
        self.assertTrue((ROOT / "references/visual-execution-vocabulary.md").exists())
        self.assertIn("动作触发开口", text)
        self.assertIn("$ai-character-performance-assets", text)
        self.assertIn("$ai-shot-execution-continuity", text)
        self.assertIn("所有画面内人物", text)
        self.assertIn("禁止木站", text)
        interface = (ROOT / "agents/openai.yaml").read_text(encoding="utf-8")
        self.assertIn("AI影视导演语言资产库", interface)
        self.assertIn("allow_implicit_invocation: true", interface)

    def test_skill_links_exist(self):
        missing = []
        for source in ROOT.rglob("*.md"):
            content = source.read_text(encoding="utf-8")
            for link in re.findall(r"\]\(([^)]+)\)", content):
                if re.match(r"^[a-z]+://", link) or link.startswith("#"):
                    continue
                target = link.split("#", 1)[0]
                if not (source.parent / target).exists():
                    missing.append(f"{source.relative_to(ROOT)} -> {link}")
        self.assertEqual(missing, [])

    def test_required_modules_and_templates(self):
        required = [
            "references/director-intent-and-scene-classification.md",
            "references/shot-function-library.md",
            "references/performance-library.md",
            "references/camera-grammar-library.md",
            "references/motion-vfx-causality.md",
            "references/continuity-state-ledger.md",
            "references/domain-packs.md",
            "references/module-routing.md",
            "references/revision-engine.md",
            "references/director-shot-representation.md",
            "references/examples/index.md",
            "assets/director-request.template.json",
            "assets/directing-module-catalog.json",
            "assets/director-shot-representation.template.json",
            "assets/scene-state-ledger.template.json",
            "assets/revision-state.template.json",
            "scripts/validate_director_representation.py",
        ]
        self.assertEqual([name for name in required if not (ROOT / name).is_file()], [])

    def test_templates_are_valid_json(self):
        for path in (ROOT / "assets").glob("*.json"):
            json.loads(path.read_text(encoding="utf-8"))

    def test_callable_catalog_requires_conditions(self):
        catalog = json.loads((ROOT / "assets/directing-module-catalog.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(catalog["模块"]), 10)
        for module in catalog["模块"]:
            self.assertTrue(module["触发关键词"])
            self.assertTrue(module["使用条件"])
            self.assertTrue(module["禁用条件"])
            self.assertTrue(module["主要输出"])

    def test_no_fixed_shot_count_or_duration_filling(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("不给固定镜头数量", skill)
        self.assertIn("不按固定字数或标点机械切分", skill)
        self.assertIn("禁止把整段对白直接包装成一个", skill)
        self.assertIn("为什么存在", skill)


if __name__ == "__main__":
    unittest.main()
