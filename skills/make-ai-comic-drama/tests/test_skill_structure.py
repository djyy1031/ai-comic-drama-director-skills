from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).parents[1]

def parse_simple_frontmatter(text: str) -> dict:
    match = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.DOTALL)
    if not match:
        raise AssertionError("SKILL.md缺少有效frontmatter边界")
    result: dict[str, object] = {}
    current_mapping: dict[str, str] | None = None
    for raw_line in match.group(1).splitlines():
        if not raw_line.strip():
            continue
        if raw_line.startswith("  "):
            if current_mapping is None:
                raise AssertionError(f"无父级的嵌套字段：{raw_line}")
            key, value = raw_line.strip().split(":", 1)
            current_mapping[key] = value.strip().strip('"')
            continue
        key, value = raw_line.split(":", 1)
        value = value.strip()
        if value:
            result[key] = value.strip('"')
            current_mapping = None
        else:
            nested: dict[str, str] = {}
            result[key] = nested
            current_mapping = nested
    return result

class SkillStructureTests(unittest.TestCase):
    def test_frontmatter_and_name(self):
        content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = parse_simple_frontmatter(content)
        self.assertEqual(set(frontmatter), {"name", "description", "metadata"})
        self.assertEqual(frontmatter["name"], "make-ai-comic-drama")
        self.assertRegex(str(frontmatter["name"]), r"^[a-z0-9-]+$")
        self.assertLessEqual(len(str(frontmatter["name"])), 64)
        self.assertTrue(str(frontmatter["description"]).strip())
        self.assertLessEqual(len(str(frontmatter["description"])), 1024)

    def test_all_markdown_links_from_skill_exist(self):
        content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        links = re.findall(r"\]\(([^)]+)\)", content)
        local_links = [link for link in links if not re.match(r"^[a-z]+://", link)]
        self.assertTrue(local_links)
        missing = [link for link in local_links if not (SKILL_ROOT / link).exists()]
        self.assertEqual(missing, [])

    def test_all_local_markdown_links_in_references_exist(self):
        missing: list[str] = []
        for source in SKILL_ROOT.rglob("*.md"):
            content = source.read_text(encoding="utf-8")
            for link in re.findall(r"\]\(([^)]+)\)", content):
                if re.match(r"^[a-z]+://", link) or link.startswith("#"):
                    continue
                relative = link.split("#", 1)[0]
                if not (source.parent / relative).exists():
                    missing.append(f"{source.relative_to(SKILL_ROOT)} -> {link}")
        self.assertEqual(missing, [])

    def test_required_artifacts_exist(self):
        required = [
            "agents/openai.yaml",
            "references/model-seedance-2.0.md",
            "references/model-seedance-2.5.md",
            "references/global-3d-prompt.md",
            "references/global-live-action-period-prompt.md",
            "references/prompt-only-storyboard-delivery.md",
            "references/action-direction.md",
            "references/directing-asset-library.json",
            "references/director-routing.md",
            "references/examples/index.md",
            "references/examples/seedance-2.5-action-group.md",
            "references/examples/continuous-dialogue.md",
            "references/examples/continuity-and-assets.md",
            "scripts/init_project.py",
            "scripts/validate_project.py",
            "scripts/validate_prompt_only_markdown.py",
            "assets/AI漫剧生产信息表模板.xlsx",
            "assets/动作特效资产库模板.json",
            "assets/project-config.seedance-2.0.template.json",
            "assets/project-config.seedance-2.5.template.json",
            "assets/episode-manifest.seedance-2.0.template.json",
            "assets/episode-manifest.seedance-2.5.template.json",
        ]
        missing = [relative for relative in required if not (SKILL_ROOT / relative).is_file()]
        self.assertEqual(missing, [])

    def test_concrete_examples_are_discoverable_and_substantive(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        index = (SKILL_ROOT / "references/examples/index.md").read_text(encoding="utf-8")
        action = (SKILL_ROOT / "references/examples/seedance-2.5-action-group.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("references/approved-two-shots.md", skill)
        self.assertIn("seedance-2.5-action-group.md", index)
        self.assertIn("continuous-dialogue.md", index)
        self.assertIn("continuity-and-assets.md", index)
        self.assertIn("【空间与轴线】", action)
        self.assertIn("关键词初筛", action)
        self.assertIn("原文没有蓄力、机械变形、子弹时间和大规模爆炸", action)
        self.assertIn("结束状态", action)
        self.assertGreaterEqual(len(re.findall(r"^【.+?秒｜", action, re.MULTILINE)), 3)

    def test_directing_library_is_conditionally_callable(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        library = json.loads(
            (SKILL_ROOT / "references/directing-asset-library.json").read_text(encoding="utf-8")
        )
        template = json.loads(
            (SKILL_ROOT / "assets/动作特效资产库模板.json").read_text(encoding="utf-8")
        )
        self.assertIn("不为丰富而堆运镜", skill)
        self.assertIn("不扩大为全片方案或加载无关参考", skill)
        modules = library["提示词模块"]
        self.assertGreaterEqual(len(modules), 10)
        required = {"模块名称", "触发关键词", "使用条件", "提示词骨架", "建议资产", "不适用"}
        for module in modules:
            self.assertTrue(required.issubset(module))
            self.assertTrue(module["触发关键词"])
            self.assertTrue(module["使用条件"])
        self.assertGreaterEqual(len(library["可生产资产类型"]), 6)
        self.assertEqual(template["资产条目"][0]["必要性"], 0)

    def test_companion_directing_skill_routing_is_explicit(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        routing = (SKILL_ROOT / "references/director-routing.md").read_text(encoding="utf-8")
        workflow = (SKILL_ROOT / "references/workflow.md").read_text(encoding="utf-8")
        contract = (SKILL_ROOT / "references/data-contract.md").read_text(encoding="utf-8")
        self.assertIn("$ai-cinematic-directing-assets", skill)
        self.assertIn("$ai-character-performance-assets", skill)
        self.assertIn("$ai-shot-execution-continuity", skill)
        self.assertIn("导演摄影选择", skill)
        self.assertIn("每次制作完整分镜组或供审阅的镜头草稿都调用", skill)
        self.assertIn("景别、机位、焦段、固定或运镜及切点", skill)
        self.assertIn("Patrick 的轻量分镜模式", skill)
        self.assertIn("用户明确要求资产生产、全流程项目", skill)
        self.assertIn("FALLBACK_INTERNAL", routing)
        self.assertIn("PERFORMANCE_PLAN_READY", workflow)
        self.assertIn("SHOT_EXECUTION_CHECK_PASS", workflow)
        self.assertIn("DIRECTOR_INTENT_READY", workflow)
        self.assertIn("director_representations", contract)
        self.assertIn("performance_plans", contract)
        self.assertIn("execution_reports", contract)

    def test_model_templates_are_isolated(self):
        s20 = (SKILL_ROOT / "assets/project-config.seedance-2.0.template.json").read_text(encoding="utf-8")
        s25 = (SKILL_ROOT / "assets/project-config.seedance-2.5.template.json").read_text(encoding="utf-8")
        self.assertIn('"model_profile": "seedance-2.0"', s20)
        self.assertNotIn('"model_profile": "seedance-2.5"', s20)
        self.assertIn('"model_profile": "seedance-2.5"', s25)
        self.assertNotIn('"model_profile": "seedance-2.0"', s25)

    def test_3d_global_prompt_preserves_user_constraints(self):
        content = (SKILL_ROOT / "references/global-3d-prompt.md").read_text(encoding="utf-8")
        self.assertEqual(content.count("【全局通用负面提示词】"), 1)
        self.assertIn("标准50mm电影虚拟镜头无畸变", content)
        self.assertIn("禁止背景音乐、字幕、标题、Logo、水印和任何可读文字", content)
        self.assertIn("局部声明只对当前小镜头生效", content)
        self.assertIn("准确显示文字", content)
        self.assertIn("短促、可控摄影机反馈", content)

    def test_3d_prompt_binding_order_and_natural_episode_duration(self):
        prompt_format = (SKILL_ROOT / "references/prompt-format.md").read_text(encoding="utf-8")
        binding_position = prompt_format.index("林夜=林夜音色=")
        camera_position = prompt_format.index("【摄影机运动总设定】", binding_position)
        self.assertLess(binding_position, camera_position)
        self.assertIn("资产绑定区位于全局段之后", prompt_format)
        self.assertIn("不加“资产列表”标题", prompt_format)
        self.assertIn("只列本组实际调用项", prompt_format)
        self.assertIn("【场景与光影】", prompt_format)
        self.assertIn("【起始站位】", prompt_format)
        self.assertIn("【语言连续性总锁】", prompt_format)
        self.assertNotIn("【连续对白音轨总设定】", prompt_format)

        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn('version: "3.2.5"', skill)
        self.assertIn("第X集｜总时长X秒｜共X个分镜组", skill)
        self.assertIn("表演资产必须转写进最终逐镜画面", skill)
        self.assertIn("OS镜头优先呈现被思考的场景、人物或道具", skill)
        self.assertIn("摄影选择也必须落实到逐镜正文", skill)

    def test_prompt_only_delivery_mode_is_complete(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("默认范围与信息来源", skill)
        self.assertIn("完整分集的交付契约", skill)
        self.assertIn("validate_prompt_light.py", skill)
        self.assertIn("每次写分镜都必须读", skill)
        self.assertIn("references/prompt-contract.md", skill)
        self.assertIn("不要自动建立项目、制作资产", skill)

        for model in ("seedance-2.0", "seedance-2.5"):
            config = (SKILL_ROOT / f"assets/project-config.{model}.template.json").read_text(
                encoding="utf-8"
            )
            self.assertIn('"target_seconds": null', config)
            self.assertIn('"normal_min_seconds": 90', config)
            self.assertIn('"preferred_max_shot_groups": null', config)
            self.assertNotIn('seedance_2_5_preferred_group_seconds', config)

if __name__ == "__main__":
    unittest.main()
