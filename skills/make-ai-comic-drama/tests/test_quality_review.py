import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location('quality_validator', ROOT / 'scripts/validate_prompt_light.py')
V = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(V)

def scene(camera, performance):
    return f'【0—8秒】\n{camera}\n\n{performance}\n环境与动作音效：室内底声低于对白。'

class QualityReviewTests(unittest.TestCase):
    def test_fixed_observation_is_valid_without_movement_quota(self):
        prompt = scene('摄影机镜头焦距40毫米，张三与李四双人腰上中景。摄影机在长桌侧面，坐姿眼高固定拍摄，双手和两张脸都在画内。', '张三把杯子推到李四面前。李四低头看杯子，再抬眼看张三，右手慢慢握住杯柄。')
        self.assertEqual(V.review_quality(prompt, ['张三', '李四']), [])

    def test_old_emotion_template_requires_repair(self):
        prompt = scene('摄影机镜头焦距50毫米，张三单人胸上中近景。摄影机在桌侧固定拍摄。', '张三以难以置信又满脸无语的情绪说：“不是！”')
        self.assertTrue(any('情绪' in e for e in V.review_quality(prompt, ['张三'])))

    def test_emotion_words_inside_original_dialogue_are_preserved(self):
        prompt = scene('摄影机镜头焦距50毫米，张三单人胸上中近景。摄影机在桌侧固定拍摄。', '张三的右手停在桌上，眉头收紧，第0.1秒对李四说：“他现在以愤怒的情绪回答，已经内心崩溃了。”')
        self.assertEqual(V.review_quality(prompt, ['张三', '李四']), [])

    def test_move_without_end_framing_requires_repair(self):
        prompt = scene('摄影机镜头焦距50毫米，张三单人腰上中景。摄影机在桌側向张三缓慢推近。', '张三抬眼看门口，拿杯子的右手停下。')
        self.assertTrue(any('停止构图' in e for e in V.review_quality(prompt, ['张三'])))

    def test_decorative_camera_claim_requires_repair(self):
        prompt = scene('摄影机镜头焦距50毫米，张三单人腰上中景。摄影机在桌侧缓慢推近，增强压迫感，停在胸口以上。', '张三放下杯子，看向李四。')
        self.assertTrue(any('气氛评价' in e for e in V.review_quality(prompt, ['张三', '李四'])))

    def test_triggered_move_with_visible_end_is_valid(self):
        prompt = scene('摄影机镜头焦距50毫米，张三单人腰上中景。摄影机在桌侧，眼高朝张三拍；张三看见纸条时，摄影机缓慢向张三推近，停在脸和胸前纸条都能看清的位置。', '张三左手举纸条，右手停在鼠标上，眉间收紧，嘴唇微张。')
        self.assertEqual(V.review_quality(prompt, ['张三']), [])

    def test_camera_without_start_position_requires_repair(self):
        prompt = scene('摄影机镜头焦距50毫米，张三单人胸上中近景，摄影机固定拍摄。', '张三抬眼看向李四。')
        self.assertTrue(any('具体起点' in e for e in V.review_quality(prompt, ['张三', '李四'])))

    def test_plain_speech_and_camera_words_are_accepted(self):
        prompt = scene('摄影机镜头焦距40毫米，张三单人腰上中景。摄影机在桌侧，眼高朝张三拍；张三举起纸条时，摄影机缓慢向张三靠近，停在脸和纸条都可见的位置。', '张三第0.1秒用日常交代工作的自然口吻对李四说：“去看看门口。”')
        prompt += '\n' + V.SUBTITLE
        self.assertEqual(V.validate(prompt, ['张三', '李四'], 30, shots_only=True), [])

    def test_screen_data_is_not_misclassified_as_spoken_dialogue(self):
        prompt = '【0—2秒】\n摄影机镜头焦距65毫米，张三操作的屏幕局部特写。摄影机在桌面前沿固定拍摄。\n\n屏幕显示：“升力系数0.000078”。\n环境与动作音效：设备声持续，无对白。'
        self.assertEqual(V.validate(prompt, ['张三'], 30, shots_only=True), [])

    def test_non_prompt_commentary_after_fence_does_not_contaminate_shot(self):
        prompt = scene('摄影机镜头焦距40毫米，张三单人腰上中景。摄影机在桌侧固定拍摄。', '张三第0.1秒对李四说：“明白了。”')
        prompt += '\n' + V.SUBTITLE + '\n```\n\n文字审阅说明：下一镜是另一个独立片段。'
        self.assertEqual(V.validate(prompt, ['张三', '李四'], 30, shots_only=True), [])

if __name__ == '__main__':
    unittest.main()
