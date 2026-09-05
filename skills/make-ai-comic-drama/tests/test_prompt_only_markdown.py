from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).parents[1]
MODULE_PATH = SKILL_ROOT / "scripts" / "validate_prompt_only_markdown.py"
SPEC = importlib.util.spec_from_file_location("prompt_only_validator", MODULE_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


def valid_document(second_global: str = "统一画质。") -> str:
    def group(number: str, event: str, global_line: str, speech: str) -> str:
        return f'''## 分镜组{number} {event} 8秒

```text
【全局固定画质参数】
{global_line}
【全局通用负面提示词】
禁止字幕。
甲=甲音色=
乙=
测试房间=
【摄影机运动总设定】
摄影机保持对话轴线同侧。
【场景与光影】
室内白天，自然光从画面右侧进入。
【起始站位】
甲在画面左侧面向乙，乙在画面右侧面向甲。
【语言连续性总锁】
本组台词只说一次，逐镜无停顿承接。
【0.0—4.0秒】：甲放下茶杯后，甲（克制）朝向乙开始说：“{speech}”乙没有木站，乙抬眼观察甲。结束状态：甲右手离开茶杯。 视频严禁出现台词、内心独白与系统语音字幕。
【4.0—8.0秒】：乙反应近景，乙眉心轻收并缓慢吸气，甲保持等待。结束状态：乙准备回答。
```
'''

    return "# 测试集 Seedance 2.5纯分镜提示词 动作触发版\n\n" + group(
        "一", "提出请求", "统一画质。", "请听我说。"
    ) + "\n" + group("二", "等待回应", second_global, "我会等你的答复。")


class PromptOnlyMarkdownTests(unittest.TestCase):
    def test_valid_prompt_only_document_passes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "episode.md"
            path.write_text(valid_document(), encoding="utf-8")
            self.assertEqual(VALIDATOR.validate(path), [])

    def test_changed_global_prompt_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "episode.md"
            path.write_text(valid_document(second_global="第二组擅自改写画质。"), encoding="utf-8")
            errors = VALIDATOR.validate(path)
            self.assertTrue(any("全局控制提示词与第一组不完全一致" in error for error in errors))

    def test_missing_action_trigger_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "episode.md"
            content = valid_document().replace("甲放下茶杯后，", "甲看着乙，", 1)
            path.write_text(content, encoding="utf-8")
            errors = VALIDATOR.validate(path)
            self.assertTrue(any("没有明确动作或现场事件触发点" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
