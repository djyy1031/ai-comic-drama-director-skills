import importlib.util
import unittest
from pathlib import Path


MODULE = Path(__file__).parents[1] / 'scripts' / 'validate_prompt_light.py'
SPEC = importlib.util.spec_from_file_location('light_validator', MODULE)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def sample():
    return '''第43集｜总时长4秒｜共1个分镜组｜各组时长：4秒
## 分镜组一 惊觉 4秒
```text
【全局约束】16:9；无文字；无背景音乐。
林夜=林夜音色=
沈清月=沈清月音色=
神秘商店大厅=
【摄影机运动总设定】摄影机在桌侧，同轴推近。
【场景与光影】大厅幽蓝顶光，烛火暖色边光。
【起始站位】林夜在左，沈清月在右，均面向长桌。
【语言连续性总锁】林夜音色连续，原文只说一次。
【0—4秒】
摄影机镜头焦距50毫米，林夜近景，摄影机在桌侧向林夜推近。林夜带着确认后的平静，以短促肯定的语气对沈清月，切入后第0.1秒开始说：“明白了。”林夜说话时看着沈清月；沈清月抬眼看向林夜。
环境与动作音效：烛火低于对白，衣料轻响。
视频严禁出现台词、内心独白与系统语音字幕。
整体环境音效：烛火底声连贯，无背景音乐。
```
'''


class FullGroupContractTests(unittest.TestCase):
    def test_complete_group_passes(self):
        self.assertEqual(VALIDATOR.validate_full_groups(sample(), 30), [])

    def test_missing_old_contract_fails(self):
        no_assets = sample().replace('林夜=林夜音色=\n沈清月=沈清月音色=\n神秘商店大厅=\n', '')
        no_section = sample().replace('【场景与光影】大厅幽蓝顶光，烛火暖色边光。\n', '')
        self.assertTrue(any('等号资产绑定' in error for error in VALIDATOR.validate_full_groups(no_assets, 30)))
        self.assertTrue(any('四个固定栏目' in error for error in VALIDATOR.validate_full_groups(no_section, 30)))

    def test_episode_duration_and_count_fail(self):
        broken = sample().replace('总时长4秒｜共1个分镜组', '总时长8秒｜共2个分镜组')
        errors = VALIDATOR.validate_full_groups(broken, 30)
        self.assertTrue(any('组数' in error for error in errors))
        self.assertTrue(any('总时长' in error for error in errors))

    def test_shot_example_bypasses_full_group_contract(self):
        example = '【0—1秒】\n摄影机镜头焦距50毫米，林夜近景，摄影机在桌侧。\n环境与动作音效：静默。'
        self.assertEqual(VALIDATOR.validate_full_groups(example, 30), ['完整分集缺少“第X集｜总时长X秒｜共X个分镜组｜各组时长：...”基础信息'])

    def test_framing_requires_subject_before_shot_size(self):
        names = ['林夜', '沈清月']
        baseline = sample()
        self.assertEqual(VALIDATOR.validate(baseline, names, 30), [])
        unnamed_close = baseline.replace('摄影机镜头焦距50毫米，林夜近景', '摄影机镜头焦距50毫米，中近景，林夜胸口以上')
        self.assertTrue(any('镜头首句须先写被拍人物' in error for error in VALIDATOR.validate(unnamed_close, names, 30)))
        unnamed_pair = baseline.replace('摄影机镜头焦距50毫米，林夜近景', '摄影机镜头焦距28毫米，侧向双人中全景，林夜与沈清月')
        self.assertTrue(any('镜头首句须先写被拍人物' in error for error in VALIDATOR.validate(unnamed_pair, names, 30)))

    def test_dual_framing_names_both_subjects(self):
        names = ['林夜', '沈清月']
        baseline = sample()
        named_pair = baseline.replace('摄影机镜头焦距50毫米，林夜近景', '摄影机镜头焦距28毫米，林夜与沈清月双人中全景')
        self.assertEqual(VALIDATOR.validate(named_pair, names, 30), [])
        missing_second = baseline.replace('摄影机镜头焦距50毫米，林夜近景', '摄影机镜头焦距28毫米，林夜双人中全景，沈清月')
        self.assertTrue(any('双人景别须在开头写出两名' in error for error in VALIDATOR.validate(missing_second, names, 30)))

    def test_long_prop_closeup_fails_while_face_closeup_is_allowed(self):
        names = ['林夜', '沈清月']
        baseline = sample()
        prop = baseline.replace('摄影机镜头焦距50毫米，林夜近景', '摄影机镜头焦距65毫米，林夜手中水晶瓶局部特写')
        self.assertTrue(any('非脸部特写超过2秒' in error for error in VALIDATOR.validate(prop, names, 30)))
        face = baseline.replace('摄影机镜头焦距50毫米，林夜近景', '摄影机镜头焦距65毫米，林夜面部特写')
        self.assertFalse(any('非脸部特写超过2秒' in error for error in VALIDATOR.validate(face, names, 30)))

    def test_draft_still_requires_a_camera_choice_without_model_limit(self):
        names = ['林夜', '沈清月']
        baseline = sample()
        self.assertEqual(VALIDATOR.validate(baseline, names, None, shots_only=True), [])
        lens_only = baseline.replace('摄影机在桌侧向林夜推近', '摄影机在桌侧')
        self.assertTrue(any('摄影机缺少固定或具体运动选择' in error for error in VALIDATOR.validate(lens_only, names, None, shots_only=True)))
        self.assertTrue(any('完整组需提供实际模型' in error for error in VALIDATOR.validate(baseline, names, None)))

    def test_whole_scene_draft_requires_independent_groups(self):
        ungrouped = '【0—20秒】\n镜头一\n【20—38.5秒】\n镜头二'
        self.assertTrue(any('缺少独立分镜组' in error for error in VALIDATOR.validate_draft_groups(ungrouped, 30, True)))

    def test_draft_group_cap_and_local_clock(self):
        valid = '## 分镜组A｜20秒\n【0—10秒】\n甲\n【10—20秒】\n乙\n## 分镜组B｜18.5秒\n【0—18.5秒】\n丙'
        self.assertEqual(VALIDATOR.validate_draft_groups(valid, 30, True), [])
        too_long = valid.replace('分镜组A｜20秒', '分镜组A｜38.5秒').replace('【10—20秒】', '【10—38.5秒】')
        self.assertTrue(any('组时长超过模型上限' in error for error in VALIDATOR.validate_draft_groups(too_long, 30, True)))
        wrong_clock = valid.replace('【0—18.5秒】', '【20—38.5秒】')
        self.assertTrue(any('组内连续计时' in error for error in VALIDATOR.validate_draft_groups(wrong_clock, 30, True)))

    def test_rejects_bare_lens_and_cross_shot_instructions(self):
        names = ['林夜', '沈清月']
        baseline = sample()
        bare = baseline.replace('摄影机镜头焦距50毫米，林夜近景', '50mm，林夜近景')
        self.assertTrue(any('摄影机镜头焦距' in error for error in VALIDATOR.validate(bare, names, 30)))
        contaminated = baseline.replace('沈清月抬眼看向林夜。', '沈清月抬眼看向林夜。下一镜不能重新抬手。')
        self.assertTrue(any('跨镜剪辑指令' in error for error in VALIDATOR.validate(contaminated, names, 30)))

    def test_rejects_wrong_subtitle_line_and_format_residue(self):
        names = ['林夜', '沈清月']
        baseline = sample()
        wrong_subtitle = baseline.replace('视频严禁出现台词、内心独白与系统语音字幕。', '视频画面严禁出现台词、内心独白或系统语音字幕。')
        self.assertTrue(any('禁字幕句' in error for error in VALIDATOR.validate(wrong_subtitle, names, 30)))
        residue = baseline.replace('林夜说话时', '**林夜说话时')
        self.assertTrue(any('格式残留' in error for error in VALIDATOR.validate(residue, names, 30)))

    def test_natural_directed_speech_and_follow_camera_are_accepted(self):
        names = ['林夜', '沈清月']
        prompt = sample().replace('第0.1秒开始说：“明白了。”', '第0.1秒开始对沈清月说：“明白了。”')
        prompt = prompt.replace('摄影机在桌侧向林夜推近', '摄影机在桌侧跟随林夜')
        self.assertEqual(VALIDATOR.validate(prompt, names, 30), [])

    def test_silent_shot_can_state_no_dialogue_plainly(self):
        prompt = '''【0—2秒】
摄影机镜头焦距35毫米，林夜单人胸上中近景，摄影机在桌侧固定拍摄。林夜抬眼看向门口。
环境与动作音效：风声轻响；没有人声。'''
        self.assertEqual(VALIDATOR.validate(prompt, ['林夜'], 30, shots_only=True), [])


if __name__ == '__main__':
    unittest.main()
