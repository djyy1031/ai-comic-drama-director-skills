from __future__ import annotations

import re
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).parents[1]


class SceneSkillStructureTests(unittest.TestCase):
    def test_frontmatter_name_and_version(self):
        content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(content.startswith("---\n"))
        self.assertIn("name: ai-comic-scene-assets", content)
        self.assertIn('version: "1.3.0"', content)

    def test_all_markdown_links_exist(self):
        missing = []
        for source in SKILL_ROOT.rglob("*.md"):
            content = source.read_text(encoding="utf-8")
            for link in re.findall(r"\]\(([^)]+)\)", content):
                if re.match(r"^[a-z]+://", link) or link.startswith("#"):
                    continue
                relative = link.split("#", 1)[0]
                if not (source.parent / relative).exists():
                    missing.append(f"{source.relative_to(SKILL_ROOT)} -> {link}")
        self.assertEqual(missing, [])

    def test_color_day_and_variant_contract_are_present(self):
        content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        for phrase in ("全剧色卡", "白天基础资产", "使用集数", "派生提示词"):
            self.assertIn(phrase, content)
        for relative in (
            "assets/scene-asset-request.template.json",
            "assets/scene-family-package.template.json",
            "assets/gpt-web-scene-batch.template.md",
            "references/color-and-environment-variants.md",
            "scripts/validate_scene_family.py",
        ):
            self.assertTrue((SKILL_ROOT / relative).is_file(), relative)


if __name__ == "__main__":
    unittest.main()
